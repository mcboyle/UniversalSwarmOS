const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const resolve = Module._resolveFilename;
Module._resolveFilename = function(name, parent, ...args) {
  return resolve.call(this, name.startsWith('@/') ? path.join(root, 'src', name.slice(2)) : name, parent, ...args);
};
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}
}).outputText, filename);
const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'cockpit-history-'));
process.env.FLEET_PERSIST_DIR = fixture;
process.env.USAGE_DB_PATH = path.join(fixture, 'usage.sqlite');
process.env.COCKPIT_HISTORY_DB = path.join(fixture, 'history.sqlite');
process.env.COCKPIT_LIVE_CLAUDE_ROOTS = '[]';
const Database = require('better-sqlite3');
const schema = 'CREATE TABLE usage_responses(provider TEXT, response_id TEXT, timestamp TEXT, model TEXT, usage TEXT, quarantined INTEGER, PRIMARY KEY(provider,response_id))';
const usage = JSON.stringify({input_tokens:100,cached_input_tokens:40,cache_creation_input_tokens:0,output_tokens:10});
const end = '2026-10-01T12:00:00Z';
for (const [filename, rows] of [[process.env.USAGE_DB_PATH, [['new','2026-10-01T11:58:00Z'],['ten-min','2026-10-01T11:50:00Z']]],
  [process.env.COCKPIT_HISTORY_DB, [['new','2026-10-01T11:58:00Z'],['forty-five-day','2026-08-17T12:00:00Z'],['four-hundred-day','2025-08-27T12:00:00Z']]]]) {
  const db = new Database(filename); db.exec(schema);
  for (const [id, timestamp] of rows) db.prepare('INSERT INTO usage_responses VALUES(?,?,?,?,?,?)').run('codex',id,timestamp,'gpt-6-sol',usage,0);
  db.close();
}
function query(range) {
  const code = "import sys,json;sys.path.insert(0,sys.argv[1]);from cockpit_usage import read_usage;print(json.dumps(read_usage(sys.argv[2],until=sys.argv[3],range_name=sys.argv[4],history_filename=sys.argv[5])))";
  return JSON.parse(execFileSync('python3',['-c',code,path.resolve(root,'../infra/scripts'),process.env.USAGE_DB_PATH,end,range,process.env.COCKPIT_HISTORY_DB],{encoding:'utf8'}));
}
test('all thirteen ranges include retained archives once and preserve exact windows', () => {
  const expected = {all:4,'5m':1,'30m':2,'1h':2,'6h':2,'12h':2,'24h':2,'7d':2,'14d':2,'30d':2,'3mo':3,'6mo':3,'1yr':3};
  for (const [range, count] of Object.entries(expected)) {
    const data=query(range);
    assert.equal(data.total_responses,count,`HISTORICAL_RANGE_${range}_NOT_SIX_HOURS`);
    assert.equal(data.range,range);
    assert.equal(data.coverage.first_at,'2025-08-27T12:00:00Z','ARCHIVE_COVERAGE_INCLUDES_OLD_RECORDS');
    assert.ok(data.series.length <= 400,'BOUNDED_MEASURED_BUCKETS');
  }
  assert.equal(query('all').totals.total_ctx,400,'CROSS_LEDGER_RESPONSE_DEDUP');
  assert.equal(query('5m').bucket_seconds,10,'SHORT_RANGE_MINUTE_DETAIL');
});
test('calendar ranges clamp dates and invalid ranges fail rather than becoming six hours', () => {
  const code = "import sys;sys.path.insert(0,sys.argv[1]);from cockpit_usage import range_start;import datetime as d;print(range_start('1yr',d.datetime(2024,2,29,tzinfo=d.timezone.utc)).isoformat())";
  assert.equal(execFileSync('python3',['-c',code,path.resolve(root,'../infra/scripts')],{encoding:'utf8'}).trim(),'2023-02-28T00:00:00+00:00');
  assert.throws(()=>query('bad-range'),/./,'INVALID_RANGE_NOT_DEFAULTED');
});
test('API defaults to all history and validates the requested range',async()=>{
  const route=require('../src/app/api/cost/route.ts');
  const response=await route.GET(new Request('http://localhost/api/cost'));
  assert.equal((await response.json()).total_responses,4,'ALL_HISTORY_IS_NOT_6H');
  const invalid=await route.GET(new Request('http://localhost/api/cost?range=bogus'));
  assert.equal(invalid.status,400,'INVALID_RANGE_NOT_CAUGHT_AS_UNKNOWN');
  const fleet=await require('../src/app/api/fleet/route.ts').GET(new Request('http://localhost/api/fleet?range=5m'));
  assert.equal((await fleet.json()).telemetry.range,'5m','SELECTED_RANGE_REACHES_FLEET');
});
test('Kimi live watcher exposes monthly usage without relabeling it weekly; stale Grok has a cause',()=>{
  fs.mkdirSync(path.join(fixture,'logs'));
  fs.writeFileSync(path.join(fixture,'logs/kimi-usage-watch.log'),`${new Date().toISOString()} run: five=0 monthly=17 f403=0 state=OK old= tier80= tier95= stopped=0\nsecret-token-NEVER-EXPORT\n`);
  fs.writeFileSync(path.join(fixture,'GROK_STATE.tsv'),'pool\tstate\tfive_hour_used_pct\tweekly_used_pct\tresets_at\tevidence\ngrok\tOK\t0\t4\t-\tWeekly SuperGrok: 4% used\n');
  const old = new Date('2026-09-27T12:00:00Z'); fs.utimesSync(path.join(fixture,'GROK_STATE.tsv'),old,old);
  const rows=require('../src/lib/fleet-telemetry.ts').readQuotas().quotas;
  const kimi=rows.find(row=>row.name==='Kimi');
  assert.equal(kimi.five_hour_used_pct,0,'KIMI_REAL_MEASURED_ZERO');
  assert.equal(kimi.monthly_used_pct,17,'KIMI_MONTHLY_NOT_WEEKLY');
  assert.equal(kimi.weekly_used_pct,null);
  assert.equal(kimi.status,'observed');
  const grok=rows.find(row=>row.name==='xAI');
  assert.match(grok.reason,/stale/i,'GROK_COLLECTION_CAUSE_EXPLICIT');
  assert.notEqual(grok.status,'auth_failed','NO_FABRICATED_AUTH_CAUSE');
  assert.ok(!JSON.stringify(rows).includes('secret-token-NEVER-EXPORT'));
});
test('verified auth failures and API-only limits are explicit, and missing evidence stays unverified',()=>{
  fs.writeFileSync(path.join(fixture,'USAGE.tsv'),'pool\tfive_hour_pct\tfetched_at\tstate\tproduct\ngrok\t-\t'+new Date().toISOString()+'\tAUTH_FAILED\tapi\n');
  let grok=require('../src/lib/fleet-telemetry.ts').readQuotas().quotas.find(row=>row.name==='xAI');
  assert.equal(grok.status,'auth_failed','AUTH_FAILURE_IS_EXPLICIT');
  assert.equal(grok.five_hour_reason,'No 5h window: API rate limits','API_HAS_NO_SUBSCRIPTION_5H');
  fs.writeFileSync(path.join(fixture,'USAGE.tsv'),'pool\tfive_hour_pct\tfetched_at\ngrok\t-\t'+new Date().toISOString()+'\n');
  grok=require('../src/lib/fleet-telemetry.ts').readQuotas().quotas.find(row=>row.name==='xAI');
  assert.match(grok.five_hour_reason,/unverified/i,'UNKNOWN_PLAN_DOES_NOT_MEAN_NO_LIMIT');
});
test('future readings cannot suppress real quota data; limit errors differ from auth failures',()=>{
  fs.writeFileSync(path.join(fixture,'USAGE.tsv'),'pool\tfive_hour_pct\tfetched_at\n');
  const now=new Date().toISOString(),future=new Date(Date.now()+86400000).toISOString();
  const log=path.join(fixture,'logs/kimi-usage-watch.log');
  fs.writeFileSync(log,`${now} run: five=99 monthly=17 f403=0 state=LIMITED old=\n${future} run: five=0 monthly=0 f403=0 state=OK old=\n`);
  let kimi=require('../src/lib/fleet-telemetry.ts').readQuotas().quotas.find(row=>row.name==='Kimi');
  assert.equal(kimi.five_hour_used_pct,99,'FUTURE_QUOTA_IS_NOT_FRESH');
  assert.equal(kimi.status,'limited','LIMITED_STATE_IS_NOT_OBSERVED_OK');
  fs.writeFileSync(log,`${now} run: five=100 monthly=17 f403=1 state=LIMITED old=\n`);
  kimi=require('../src/lib/fleet-telemetry.ts').readQuotas().quotas.find(row=>row.name==='Kimi');
  assert.equal(kimi.status,'limited','QUOTA_403_IS_NOT_AUTH_FAILURE');
  fs.writeFileSync(path.join(fixture,'USAGE.tsv'),`pool\tfive_hour_pct\tweekly_pct\tfetched_at\tstate\nkimi\t10\t20\t${now}\tAUTH_FAILED\n`);
  kimi=require('../src/lib/fleet-telemetry.ts').readQuotas().quotas.find(row=>row.name==='Kimi');
  assert.equal(kimi.status,'auth_failed','EQUAL_TIME_AUTH_FAILURE_HAS_PRECEDENCE');
  assert.equal(kimi.five_hour_used_pct,null,'AUTH_FAILED_PERCENTAGE_IS_NOT_CURRENT');
});
test('coarsening conserves more than four hundred measured daily buckets',()=>{
  const filename=path.join(fixture,'long-history.sqlite');
  const db=new Database(filename);db.exec(schema);
  const insert=db.prepare('INSERT INTO usage_responses VALUES(?,?,?,?,?,0)');
  for(let i=0;i<500;i++) insert.run('codex',`real-${i}`,new Date(Date.UTC(2024,0,1)+i*86400000).toISOString(),'gpt-6-sol',usage);
  db.close();
  const code="import sys,json;sys.path.insert(0,sys.argv[1]);from cockpit_usage import read_usage;print(json.dumps(read_usage(sys.argv[2],until='2026-10-01T12:00:00Z',range_name='all')))";
  const data=JSON.parse(execFileSync('python3',['-c',code,path.resolve(root,'../infra/scripts'),filename],{encoding:'utf8'}));
  assert.ok(data.series.length<=400,'ACTUAL_COARSENING_IS_BOUNDED');
  assert.equal(data.total_responses,500,'COARSENED_TURNS_CONSERVED');
  assert.equal(data.series.reduce((n,row)=>n+row.turns,0),500);
  assert.equal(data.series.reduce((n,row)=>n+row.total_ctx,0),50000,'COARSENED_TOKENS_CONSERVED');
});
test('monthly exhaustion and partial observed windows retain their specific meaning',()=>{
  const now=new Date().toISOString();
  fs.writeFileSync(path.join(fixture,'USAGE.tsv'),'pool\tfive_hour_pct\tfetched_at\n');
  fs.writeFileSync(path.join(fixture,'logs/kimi-usage-watch.log'),`${now} run: five=0 monthly=100 f403=0 state=OK old=\n`);
  let rows=require('../src/lib/fleet-telemetry.ts').readQuotas().quotas;
  assert.equal(rows.find(row=>row.name==='Kimi').status,'limited','MONTHLY_EXHAUSTION_IS_LIMITED');
  fs.writeFileSync(path.join(fixture,'USAGE.tsv'),`pool\tfive_hour_pct\tweekly_pct\tfetched_at\ngrok\t-\t12\t${now}\n`);
  rows=require('../src/lib/fleet-telemetry.ts').readQuotas().quotas;
  assert.equal(rows.find(row=>row.name==='xAI').status,'observed','WEEKLY_OBSERVATION_IS_NOT_UNAVAILABLE');
});
test('a priced history subset cannot project complete fleet spend with inaccessible sources',()=>{
  const filename=path.join(fixture,'partial-coverage.sqlite');
  fs.copyFileSync(process.env.COCKPIT_HISTORY_DB,filename);
  const db=new Database(filename);db.exec('CREATE TABLE history_metadata(key TEXT PRIMARY KEY,value TEXT)');
  db.prepare('INSERT INTO history_metadata VALUES(?,?)').run('coverage',JSON.stringify({inspected_hosts:1,total_hosts:2,inaccessible_hosts:1,unsupported_events:3}));db.close();
  process.env.COCKPIT_HISTORY_DB=filename;
  const data=require('../src/lib/fleet-telemetry.ts').readCost('all');
  assert.ok(data.aggregate.total_cost_usd>0,'RETAINED_PRICED_COST_STILL_MEASURED');
  assert.equal(data.aggregate.projected_24h_cost_usd,null,'INCOMPLETE_FLEET_COVERAGE_PREVENTS_PROJECTION');
});
test('a partial Kimi monthly or legacy weekly observation remains visible with the actual period',()=>{
  const now=new Date().toISOString();
  fs.writeFileSync(path.join(fixture,'USAGE.tsv'),'pool\tfive_hour_pct\tfetched_at\n');
  fs.writeFileSync(path.join(fixture,'logs/kimi-usage-watch.log'),`${now} run: five=- monthly=17 f403=0 state=OK old=\n`);
  let kimi=require('../src/lib/fleet-telemetry.ts').readQuotas().quotas.find(row=>row.name==='Kimi');
  assert.equal(kimi.status,'observed','PARTIAL_MONTHLY_OBSERVATION_REMAINS_OBSERVED');
  assert.match(kimi.reason,/monthly.*observed/i);
  fs.writeFileSync(path.join(fixture,'USAGE.tsv'),`pool\tfive_hour_pct\tweekly_pct\tfetched_at\nkimi\t-\t12\t${now}\n`);
  kimi=require('../src/lib/fleet-telemetry.ts').readQuotas().quotas.find(row=>row.name==='Kimi');
  const {longQuotaWindow}=require('../src/lib/fleet-types.ts');
  assert.deepEqual(longQuotaWindow(kimi),{label:'Weekly',value:12},'VERIFIED_LEGACY_WEEKLY_IS_NOT_HIDDEN_AS_MONTHLY_UNKNOWN');
  assert.deepEqual(longQuotaWindow({...kimi,monthly_used_pct:0}),{label:'Monthly',value:0},'MEASURED_MONTHLY_ZERO_IS_NOT_FALLBACK');
});
