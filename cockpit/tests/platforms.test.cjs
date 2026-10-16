const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const resolve = Module._resolveFilename;
Module._resolveFilename = function(name, parent, ...args) {
  return resolve.call(this, name.startsWith('@/') ? path.join(root, 'src', name.slice(2)) : name, parent, ...args);
};
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true }
}).outputText, filename);
const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'cockpit-platforms-'));
process.env.FLEET_PERSIST_DIR = fixture;
process.env.USAGE_DB_PATH = path.join(fixture, 'usage.sqlite');
process.env.COCKPIT_HISTORY_DB = path.join(fixture, 'history.sqlite');
process.env.COCKPIT_LIVE_CLAUDE_ROOTS = '[]';
const Database = require('better-sqlite3');
const schema = 'CREATE TABLE usage_responses(provider TEXT, response_id TEXT, timestamp TEXT, model TEXT, usage TEXT, quarantined INTEGER, PRIMARY KEY(provider,response_id))';
const end = '2026-10-01T12:00:00Z';
const measured = { input_tokens: 100, cached_input_tokens: 40, cache_creation_input_tokens: 10, output_tokens: 20 };
for (const filename of [process.env.USAGE_DB_PATH, process.env.COCKPIT_HISTORY_DB]) {
  const db = new Database(filename); db.exec(schema); db.close();
}
const main = new Database(process.env.USAGE_DB_PATH);
const insert = main.prepare('INSERT INTO usage_responses VALUES(?,?,?,?,?,?)');
insert.run('claude', 'shared-id', '2026-10-01T11:58:00Z', 'claude-opus-5-5', JSON.stringify(measured), 0);
insert.run('codex', 'shared-id', '2026-10-01T11:59:00Z', 'claude-opus-5-5', JSON.stringify({ ...measured, input_tokens: 200 }), 0);
insert.run('claude', 'older', '2026-09-01T12:00:00Z', 'claude-opus-5-5', JSON.stringify(measured), 0);
insert.run('grok', 'retained', '2026-09-27T12:00:00Z', 'grok-4.7-build-fast', JSON.stringify(measured), 0);
insert.run('kimi', 'missing', '2026-09-30T12:00:00Z', 'kimi-code/kimi-for-coding', JSON.stringify({ input_tokens: 50 }), 0);
insert.run('agy', 'synth_gemini_0', '2026-10-01T11:59:00Z', 'gemini-3.1-pro', JSON.stringify(measured), 0);
insert.run('codex', 'quarantine', '2026-10-01T11:59:00Z', 'claude-opus-5-5', JSON.stringify(measured), 1);
main.close();
const archive = new Database(process.env.COCKPIT_HISTORY_DB);
archive.exec('CREATE TABLE metric_provenance(provider TEXT,response_id TEXT,fields TEXT,PRIMARY KEY(provider,response_id))');
archive.prepare('INSERT INTO usage_responses VALUES(?,?,?,?,?,0)').run('claude', 'zero-proven', '2026-10-01T11:59:00Z', 'claude-opus-5', JSON.stringify({ input_tokens: 100, cached_input_tokens: 0, cache_creation_input_tokens: 0, output_tokens: 20 }));
archive.prepare('INSERT INTO metric_provenance VALUES(?,?,?)').run('claude', 'zero-proven', JSON.stringify({ cache_read: true, creation_tokens: true }));
archive.prepare('INSERT INTO usage_responses VALUES(?,?,?,?,?,0)').run('codex', 'shared-id', '2026-10-01T11:59:00Z', 'claude-opus-5-5', JSON.stringify({ ...measured, input_tokens: 999 }));
archive.prepare('INSERT INTO usage_responses VALUES(?,?,?,?,?,0)').run('codex', 'quarantine', '2026-10-01T11:59:00Z', 'claude-opus-5-5', JSON.stringify(measured));
archive.close();
function query(range) {
  const code = "import sys,json;sys.path.insert(0,sys.argv[1]);from cockpit_usage import read_usage;print(json.dumps(read_usage(sys.argv[2],until=sys.argv[3],range_name=sys.argv[4],history_filename=sys.argv[5])))";
  return JSON.parse(execFileSync('python3', ['-c', code, path.resolve(root, '../infra/scripts'), process.env.USAGE_DB_PATH, end, range, process.env.COCKPIT_HISTORY_DB], { encoding: 'utf8' }));
}
test('the same model and response ID on different platforms remain separate measurements', () => {
  const data = query('all');
  const rows = data.breakdown.filter(row => row.key === 'claude-opus-5-5');
  assert.equal(rows.length, 2, 'PLATFORM_MODEL_COLLAPSE: separate providers were merged');
  assert.equal(rows.find(row => row.provider === 'claude').total_ctx, 200);
  assert.equal(rows.find(row => row.provider === 'codex').total_ctx, 200, 'PRIMARY_WINS_AND_QUARANTINE_SUPPRESSES_ARCHIVE');
  assert.equal(data.total_responses, 6);
});
test('current five minutes and chosen history share an exact cutoff and preserve per-model coverage', () => {
  const all = query('all');
  assert.ok(Array.isArray(all.platform_models), 'PLATFORM_WINDOWS_MISSING: current/model history not exposed');
  const row = all.platform_models.find(row => row.provider === 'claude' && row.model === 'claude-opus-5-5');
  assert.equal(row.current.metrics.turns, 1, 'CURRENT_FIVE_MINUTES_NOT_ALL_HISTORY');
  assert.equal(row.history.metrics.turns, 2);
  assert.equal(row.coverage.first_at, '2026-09-01T12:00:00Z');
  assert.equal(all.current_window.since, '2026-10-01T11:55:00+00:00');
  assert.equal(all.current_window.until, end.replace('Z', '+00:00'));
  const short = query('5m').platform_models.find(row => row.provider === 'claude' && row.model === 'claude-opus-5-5');
  assert.equal(short.history.metrics.turns, 1);
  assert.equal(short.current.metrics.turns, 1);
});
test('all requested platforms stay visible; missing metrics and retired current data are explained', () => {
  const data = query('all');
  assert.ok(Array.isArray(data.platform_models), 'PLATFORM_AVAILABILITY_MISSING');
  assert.deepEqual(new Set(data.platform_models.map(row => row.platform)), new Set(['claude', 'codex', 'agy', 'grok', 'kimi']));
  const agy = data.platform_models.find(row => row.platform === 'agy');
  assert.equal(agy.history.metrics, null, 'SYNTHETIC_GEMINI_IS_NOT_MEASURED_USAGE');
  assert.match(agy.history.reason, /decoded|verified|retained/i);
  const grok = data.platform_models.find(row => row.platform === 'grok');
  assert.equal(grok.current.metrics, null, 'RETIRED_PLATFORM_IS_HISTORY_ONLY');
  assert.match(grok.current.reason, /retired.*2026-09-28/i);
  assert.equal(grok.history.metrics.turns, 1);
  const kimi = data.platform_models.find(row => row.platform === 'kimi');
  assert.equal(kimi.current.metrics, null, 'ABSENT_OBSERVATION_IS_NOT_ZERO');
  assert.equal(kimi.history.metrics.out_tokens, null);
  assert.match(kimi.history.unknown_metrics.out_tokens, /missing|valid|measured/i);
  assert.equal(kimi.history.metrics.cache_read, null);
});
test('model telemetry preserves current shared quota scope and never assigns pool headroom to a model', () => {
  const now = new Date().toISOString();
  fs.writeFileSync(path.join(fixture, 'USAGE.tsv'), `pool\tproduct\tfive_hour_pct\tresets_at\tweekly_pct\tweekly_resets\tstate\tfetched_at\nA\tClaude\t25\t-\t30\t-\tOK\t${now}\n`);
  const snapshot = require('../src/lib/fleet-telemetry.ts').readSnapshot('all');
  assert.ok(Array.isArray(snapshot.telemetry.platform_models), 'API_MODEL_WINDOWS_MISSING');
  const row = snapshot.telemetry.platform_models.find(row => row.platform === 'claude' && row.model === 'claude-opus-5-5');
  assert.equal(row.quota_scope, 'Shared Claude pools A–D; per-model and per-response pool attribution unavailable');
  assert.ok(!('five_hour_used_pct' in row), 'POOL_PERCENT_IS_NOT_A_MODEL_LIMIT');
  assert.equal(row.quotas.find(quota => quota.name === 'Claude A').five_hour_used_pct, 25);
  assert.ok(Math.abs(row.history.metrics.cost_usd - 0.001376) < 1e-12, 'MODEL_COST_USES_ITS_OWN_RETAINED_USAGE');
});
test('proved raw zero remains zero while absent raw cache provenance stays unknown', () => {
  const data = query('all');
  const proved = data.platform_models.find(row => row.model === 'claude-opus-5');
  assert.equal(proved.history.metrics.cache_read, 0, 'RAW_PROVENANCE_PRESERVES_MEASURED_ZERO');
  assert.equal(proved.history.metrics.cache_creation_tokens, 0);
  assert.equal(proved.history.metrics.total_ctx, 100);
  assert.equal(data.platform_models.find(row => row.platform === 'kimi').history.metrics.cache_read, null);
});
test('truthy malformed provenance cannot turn an absent cache observation into measured zero', () => {
  const code = "import sys,json;sys.path.insert(0,sys.argv[1]);from cockpit_usage import strict_measurement;row={'input_tokens':100,'cache_read':0,'creation_tokens':0,'fresh_tokens':100,'output_tokens':1};print(json.dumps(strict_measurement('codex',row,{'cache_read':'false','creation_tokens':1})[0]))";
  const row = JSON.parse(execFileSync('python3', ['-c', code, path.resolve(root, '../infra/scripts')], { encoding: 'utf8' }));
  assert.equal(row.cache_read, null, 'ONLY_BOOLEAN_RAW_PROOF_CAN_ESTABLISH_ZERO');
  assert.equal(row.creation_tokens, null);
  assert.equal(row.input_tokens, 100);
});
test('an unavailable accounting source leaves all platforms visible with a reason and no zeros', () => {
  process.env.USAGE_DB_PATH = path.join(fixture, 'does-not-exist.sqlite');
  const data = require('../src/lib/fleet-telemetry.ts').readCost('1yr');
  assert.equal(data.source, 'unknown');
  assert.equal(data.total_responses, null);
  assert.equal(data.platform_models.length, 5, 'UNAVAILABLE_SOURCE_STILL_NAMES_EACH_PLATFORM');
  for (const row of data.platform_models) {
    assert.equal(row.history.metrics, null);
    assert.match(row.history.reason, /accounting ledger unavailable/i);
  }
  assert.ok(!fs.existsSync(process.env.USAGE_DB_PATH), 'READ_ONLY_MISSING_LEDGER_WAS_NOT_CREATED');
});
