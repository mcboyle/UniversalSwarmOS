const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');
const resolve = Module._resolveFilename;
Module._resolveFilename = function (name, parent, ...args) {
  return resolve.call(this, name.startsWith('@/') ? path.join(root, 'src', name.slice(2)) : name, parent, ...args);
};
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true }
}).outputText, filename);
const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'cockpit-o1599-'));
process.env.FLEET_PERSIST_DIR = fixture;
process.env.COCKPIT_LIVE_CLAUDE_ROOTS = '[]';
process.env.HOST_STATE_PATH = path.join(fixture, 'HOST-STATE.tsv');
fs.writeFileSync(process.env.HOST_STATE_PATH, 'alpha\t10.0.70.1\tup\t2026-10-01T12:00:00Z\nbeta\t10.0.70.95\tNOT-PROBED\t2026-10-01T12:00:00Z\n');
fs.writeFileSync(path.join(fixture, 'ROLE-OCCUPANCY.tsv'), '# role\tseat\tpid\thost\tclaimed_at\nworker\tseat-a\t123\talpha\t2026-10-01T12:00:00Z\n');
fs.writeFileSync(path.join(fixture, 'USAGE.tsv'), 'pool\tfive_hour_pct\tresets_at\tweekly_pct\tfetched_at\nA\t0\t-\t94\t2026-10-01T12:00:00Z\nB\t-\t-\t-\t2026-10-01T12:00:00Z\n');
fs.writeFileSync(path.join(fixture, 'STATUS.md'), '# BD STATUS 2026-10-01T12:00:00Z\nmain: abcdef 1.2.3 open rows: 4\nqueue: 3 briefs waiting\n## Claude sessions\nsecret-session token-NEVER-EXPORT\n');

test('read-only accounting leaves writer journal unchanged', () => {
  const Database = require('better-sqlite3');
  const filename = path.join(fixture, 'journal.sqlite');
  const writer = new Database(filename);
  writer.exec('CREATE TABLE proof(value INTEGER); INSERT INTO proof VALUES (7)');
  writer.close();
  const db = require('../src/lib/db.ts');
  db.closeDb();
  const reader = db.getReadOnlyDb({ dbPath: filename });
  assert.equal(reader.prepare('SELECT value FROM proof').get().value, 7);
  assert.equal(reader.pragma('journal_mode', { simple: true }), 'delete', 'ACCOUNTING_READ_ONLY_JOURNAL: reader must not change writer journal');
  assert.throws(() => reader.exec('INSERT INTO proof VALUES (8)'), /readonly/i);
  db.closeDb();
});

test('architecture derives inventory from HOST ledger including test2', async () => {
  const response = await require('../src/app/api/architecture/route.ts').GET();
  const data = await response.json();
  assert.equal(data.topology.total_nodes, 2, 'HOST_LEDGER_DENOMINATOR: topology must use the live host ledger');
  assert.equal(data.source, 'live');
  const nodes = Object.values(data.topology.tiers).flat();
  assert.ok(nodes.some(node => node.ip === '10.0.70.95' && !node.is_blacklisted));
  assert.equal(data.topology.agent_allocations.alpha.length, 1);
});

test('partial ledgers retain complete rows and missing inventory stays UNKNOWN', () => {
  const telemetry = require('../src/lib/fleet-telemetry.ts');
  fs.appendFileSync(process.env.HOST_STATE_PATH, 'broken\t10.0.70.3\t');
  fs.appendFileSync(path.join(fixture, 'ROLE-OCCUPANCY.tsv'), 'worker\ttorn-seat\t4\talpha');
  assert.equal(telemetry.readTopology().nodes.length, 2, 'TORN_HOST_ROW');
  assert.equal(telemetry.readTopology().agents.length, 1, 'TORN_ROLE_ROW');
  const saved = process.env.HOST_STATE_PATH;
  process.env.HOST_STATE_PATH = path.join(fixture, 'absent.tsv');
  assert.equal(telemetry.readSnapshot().topology.total_nodes, null, 'MISSING_HOST_IS_UNKNOWN');
  process.env.HOST_STATE_PATH = saved;
});

test('zero quota is measured and missing percentage is UNKNOWN', () => {
  const data = require('../src/lib/fleet-telemetry.ts').readQuotas();
  assert.equal(data.quotas.find(row => row.name === 'Claude A').five_hour_used_pct, 0, 'MEASURED_ZERO');
  assert.equal(data.quotas.find(row => row.name === 'Claude B').five_hour_used_pct, null, 'UNKNOWN_NOT_ZERO');
  assert.equal(data.quotas.find(row => row.name === 'codex').weekly_used_pct, null, 'MISSING_POOL_UNKNOWN');
});

test('STATUS projection never exposes pane text', () => {
  const data = require('../src/lib/fleet-telemetry.ts').readSnapshot();
  assert.equal(data.steering.queued, 3);
  assert.equal(data.steering.open_rows, 4);
  assert.ok(!JSON.stringify(data).includes('token-NEVER-EXPORT'), 'STATUS_SECRET_SENTINEL');
});

test('accounting deduplicates responses and propagates unknown prices', () => {
  const Database = require('better-sqlite3');
  const filename = path.join(fixture, 'usage.sqlite');
  const writer = new Database(filename);
  writer.exec('CREATE TABLE usage_responses(provider TEXT, response_id TEXT, timestamp TEXT, model TEXT, usage TEXT, quarantined INTEGER); CREATE TABLE usage_occurrences(provider TEXT, response_id TEXT, host TEXT, thread TEXT)');
  const insert = writer.prepare('INSERT INTO usage_responses VALUES(?,?,?,?,?,?)');
  const timestamp = new Date(Date.now() - 60_000).toISOString();
  insert.run('claude', 'shared-id', timestamp, 'claude-opus-5-5', JSON.stringify({input_tokens:1000, cache_read_input_tokens:600, cached_input_tokens:600, cache_creation_input_tokens:100, output_tokens:200}), 0);
  insert.run('codex', 'shared-id', timestamp, 'unknown-model', JSON.stringify({input_tokens:200, cached_input_tokens:100, cache_creation_input_tokens:0, output_tokens:20}), 0);
  insert.run('claude', 'quarantined', timestamp, 'claude-opus-5-5', JSON.stringify({input_tokens:9999}), 1);
  insert.run('claude', 'synth-fixture', timestamp, 'claude-opus-5-5', JSON.stringify({input_tokens:9999}), 0);
  insert.run('claude', 'message-placeholder', timestamp, '<synthetic>', JSON.stringify({input_tokens:9999}), 0);
  writer.exec("INSERT INTO usage_occurrences VALUES('claude','shared-id','a','x'),('claude','shared-id','b','x')");
  writer.close();
  process.env.USAGE_DB_PATH = filename;
  const telemetry = require('../src/lib/fleet-telemetry.ts');
  const data = telemetry.readCost();
  assert.equal(data.source, 'live');
  assert.equal(data.total_responses, 2, 'RESPONSE_DENOMINATOR');
  assert.equal(data.totals.total_ctx, 1200);
  assert.equal(data.totals.cache_read, 700, 'CACHE_MAX_NOT_SUM');
  assert.equal(data.totals.fresh_tokens, 500);
  assert.equal(data.aggregate.total_cost_usd, null, 'UNKNOWN_PRICE_TOTAL');
  assert.equal(data.aggregate.projected_24h_cost_usd, null);
  assert.equal(data.aggregate.priced_responses, 1);
  assert.ok(Math.abs(data.aggregate.priced_cost_usd - 0.00612) < 1e-9, 'CREATION_NOT_DOUBLE_BILLED');
  assert.equal(data.series.length, 1, 'MEASURED_TIME_SERIES');
  const reader = new Database(filename, {readonly:true});
  assert.equal(reader.pragma('journal_mode', {simple:true}), 'delete', 'URI_READER_PRESERVES_JOURNAL');
  assert.equal(reader.prepare('SELECT COUNT(*) AS n FROM usage_responses').get().n, 5);
  reader.close();
  process.env.USAGE_DB_PATH = path.join(fixture, 'absent.sqlite');
  assert.equal(telemetry.readCost().source, 'unknown');
  assert.ok(!fs.existsSync(process.env.USAGE_DB_PATH), 'NO_DATABASE_CREATED');
});

test('malformed nonempty sources and torn timestamps are UNKNOWN', () => {
  const telemetry = require('../src/lib/fleet-telemetry.ts');
  const usage = path.join(fixture, 'USAGE.tsv'), status = path.join(fixture, 'STATUS.md');
  const originalUsage = fs.readFileSync(usage), originalStatus = fs.readFileSync(status);
  fs.writeFileSync(usage, 'pool\tfive_hour_pct\tfetched_at\nA\t');
  assert.equal(telemetry.readQuotas().observation.state, 'unknown', 'MALFORMED_USAGE_SOURCE');
  fs.writeFileSync(status, 'partially written status file');
  assert.equal(telemetry.readSteering().observation.state, 'unknown', 'MALFORMED_STATUS_SOURCE');
  const originalHosts = fs.readFileSync(process.env.HOST_STATE_PATH);
  fs.writeFileSync(process.env.HOST_STATE_PATH, 'torn\t10.0.70.2\tup\t2026');
  assert.equal(telemetry.readTopology().hosts.state, 'unknown', 'TORN_TIMESTAMP');
  fs.writeFileSync(usage, originalUsage); fs.writeFileSync(status, originalStatus); fs.writeFileSync(process.env.HOST_STATE_PATH, originalHosts);
});

test('unavailable accounting has UNKNOWN pricing coverage', () => {
  process.env.USAGE_DB_PATH = path.join(fixture, 'absent.sqlite');
  const data = require('../src/lib/fleet-telemetry.ts').readCost();
  assert.equal(data.aggregate.unpriced_responses, null, 'MISSING_COVERAGE_UNKNOWN');
});

test('accounting source time and subsecond cutoff are measured exactly', () => {
  const Database = require('better-sqlite3');
  const filename = path.join(fixture, 'boundary.sqlite');
  const writer = new Database(filename);
  writer.exec('CREATE TABLE usage_responses(timestamp TEXT, model TEXT, usage TEXT, quarantined INTEGER, response_id TEXT, provider TEXT)');
  const insert = writer.prepare('INSERT INTO usage_responses VALUES(?,?,?,?,?,?)');
  const payload = JSON.stringify({input_tokens:100, cached_input_tokens:50, cache_creation_input_tokens:0, output_tokens:10});
  insert.run('2026-10-01T14:00:00.999999+02:00', 'known', payload, 0, 'before', 'codex');
  insert.run('2026-10-01T12:00:01Z', 'known', payload, 0, 'at', 'codex');
  writer.close();
  const { execFileSync } = require('node:child_process');
  const helper = path.resolve(root, '../infra/scripts');
  const code = "import sys,json; sys.path.insert(0,sys.argv[1]); from cockpit_usage import read_usage; print(json.dumps(read_usage(sys.argv[2],until='2026-10-01T12:00:01Z')))";
  const data = JSON.parse(execFileSync('python3', ['-c', code, helper, filename], {encoding:'utf8'}));
  assert.equal(data.total_responses, 1, 'EXACT_SUBSECOND_CUTOFF');
  assert.equal(data.observed_at, '2026-10-01T12:00:01Z', 'ACCOUNTING_PERSISTED_SOURCE_TIME');
});
