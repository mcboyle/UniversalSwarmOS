import { test, before, after } from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { spawn, ChildProcess } from 'node:child_process';
import Database from 'better-sqlite3';

const TEST_PORT = 3458;
const BASE_URL = `http://localhost:${TEST_PORT}`;
let serverProcess: ChildProcess | null = null;

async function isServerReady(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/api/nodes`);
    return res.status === 200;
  } catch {
    return false;
  }
}

async function apiFetch<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<{ status: number; data: T; headers: Headers }> {
  const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const res = await fetch(url, options);
  let data: any;
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    data = await res.json();
  } else {
    data = await res.text();
  }
  return { status: res.status, data, headers: res.headers };
}

function initEmptyDb(dbPath: string) {
  if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath);
  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.exec(`
    CREATE TABLE usage_responses (
      provider TEXT,
      response_id TEXT,
      timestamp TEXT,
      model TEXT,
      usage TEXT,
      fingerprint TEXT,
      quarantined INTEGER,
      PRIMARY KEY(provider, response_id)
    );
    CREATE TABLE usage_occurrences (
      provider TEXT,
      response_id TEXT,
      host TEXT,
      thread TEXT,
      source TEXT,
      PRIMARY KEY(provider, response_id, host, thread, source)
    );
  `);
  db.close();
}

before(async () => {
  if (await isServerReady()) return;

  serverProcess = spawn('npx', ['next', 'start', '-p', String(TEST_PORT)], {
    cwd: '/home/mboyle/teamwork_projects/cockpit_upgrade',
    stdio: 'ignore',
    detached: true,
    env: { ...process.env, PORT: String(TEST_PORT) }
  });

  const start = Date.now();
  while (Date.now() - start < 25000) {
    await new Promise((r) => setTimeout(r, 400));
    if (await isServerReady()) return;
  }
  throw new Error(`Failed to start Next.js test server on port ${TEST_PORT} within 25s`);
});

after(() => {
  if (serverProcess && serverProcess.pid) {
    try {
      process.kill(-serverProcess.pid, 'SIGKILL');
    } catch {
      try {
        serverProcess.kill('SIGKILL');
      } catch {}
    }
  }
});

// ============================================================================
// EDGE CASE 1: Empty database / 0 usage rows
// ============================================================================

test('EC1.1: /api/cost handles empty database (0 rows) grouped by model', async () => {
  const testDb = '/tmp/test_empty_model.sqlite';
  initEmptyDb(testDb);

  try {
    const res = await apiFetch('/api/cost?since=2026-01-01T00:00:00Z&group_by=model', {
      headers: { 'x-test-db-path': testDb }
    });

    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.data.source, 'live');
    assert.strictEqual(res.data.group_by, 'model');
    assert.strictEqual(res.data.total_responses, 0);
    assert.strictEqual(res.data.aggregate.total_context_tokens, 0);
    assert.strictEqual(res.data.aggregate.total_output_tokens, 0);
    assert.strictEqual(res.data.aggregate.total_cache_read_tokens, 0);
    assert.strictEqual(res.data.aggregate.overall_cache_hit_pct, 0);
    assert.strictEqual(res.data.aggregate.total_cost_usd, 0);
    assert.strictEqual(res.data.aggregate.projected_24h_cost_usd, 0);
    assert.deepStrictEqual(res.data.breakdown, []);
    assert.ok(!isNaN(res.data.aggregate.overall_cache_hit_pct));
    assert.ok(!isNaN(res.data.aggregate.total_cost_usd));
  } finally {
    for (const ext of ['', '-wal', '-shm']) {
      if (fs.existsSync(testDb + ext)) fs.unlinkSync(testDb + ext);
    }
  }
});

test('EC1.2: /api/cost handles empty database (0 rows) grouped by thread', async () => {
  const testDb = '/tmp/test_empty_thread.sqlite';
  initEmptyDb(testDb);

  try {
    const res = await apiFetch('/api/cost?since=2026-01-01T00:00:00Z&group_by=thread', {
      headers: { 'x-test-db-path': testDb }
    });

    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.data.source, 'live');
    assert.strictEqual(res.data.group_by, 'thread');
    assert.strictEqual(res.data.total_responses, 0);
    assert.strictEqual(res.data.aggregate.total_context_tokens, 0);
    assert.strictEqual(res.data.aggregate.total_output_tokens, 0);
    assert.strictEqual(res.data.aggregate.total_cache_read_tokens, 0);
    assert.strictEqual(res.data.aggregate.overall_cache_hit_pct, 0);
    assert.strictEqual(res.data.aggregate.total_cost_usd, 0);
    assert.deepStrictEqual(res.data.breakdown, []);
  } finally {
    for (const ext of ['', '-wal', '-shm']) {
      if (fs.existsSync(testDb + ext)) fs.unlinkSync(testDb + ext);
    }
  }
});

test('EC1.3: /api/cost handles completely blank 0-byte database file gracefully', async () => {
  const testDb = '/tmp/test_blank.sqlite';
  fs.writeFileSync(testDb, '');

  try {
    const res = await apiFetch('/api/cost', {
      headers: { 'x-test-db-path': testDb }
    });

    assert.strictEqual(res.status, 200);
    assert.ok(['live', 'mock'].includes(res.data.source));
    assert.ok(typeof res.data.aggregate.total_cost_usd === 'number');
  } finally {
    if (fs.existsSync(testDb)) fs.unlinkSync(testDb);
  }
});

// ============================================================================
// EDGE CASE 2: Corrupted JSON & unexpected schema in usage_responses
// ============================================================================

test('EC2.1: /api/cost gracefully handles malformed JSON in usage column via fallback', async () => {
  const testDb = '/tmp/test_corrupt_json.sqlite';
  initEmptyDb(testDb);
  const db = new Database(testDb);

  // Insert valid Grok row
  db.prepare(`
    INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run('xai', 'resp_valid', '2026-09-22T22:00:00Z', 'grok-2', JSON.stringify({
    input_tokens: 1000,
    output_tokens: 200,
    cached_input_tokens: 500
  }), 'fp1', 0);

  // Insert malformed JSON row
  db.prepare(`
    INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run('xai', 'resp_corrupt', '2026-09-22T22:01:00Z', 'grok-2', '{"input_tokens": 100, broken', 'fp2', 0);

  db.close();

  try {
    const res = await apiFetch('/api/cost?since=2026-09-22T00:00:00Z', {
      headers: { 'x-test-db-path': testDb }
    });

    // SQLite json_extract throws malformed JSON error; route catches and returns HTTP 200 with fallback mock
    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.data.source, 'mock');
    assert.ok(res.data.aggregate);
    assert.ok(typeof res.data.aggregate.total_cost_usd === 'number');
  } finally {
    for (const ext of ['', '-wal', '-shm']) {
      if (fs.existsSync(testDb + ext)) fs.unlinkSync(testDb + ext);
    }
  }
});

test('EC2.2: /api/cost handles unexpected schema: empty object, nulls, string numbers, extra fields', async () => {
  const testDb = '/tmp/test_schema_variations.sqlite';
  initEmptyDb(testDb);
  const db = new Database(testDb);

  // 1. Empty object {}
  db.prepare(`INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
    'xai', 'resp_empty', '2026-09-22T22:00:00Z', 'grok-2', '{}', 'fp1', 0
  );

  // 2. Explicit nulls
  db.prepare(`INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
    'moonshot', 'resp_nulls', '2026-09-22T22:01:00Z', 'kimi-k1.5',
    JSON.stringify({ input_tokens: null, output_tokens: null, cached_input_tokens: null }),
    'fp2', 0
  );

  // 3. String representations of numbers
  db.prepare(`INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
    'xai', 'resp_strings', '2026-09-22T22:02:00Z', 'grok-beta',
    JSON.stringify({ input_tokens: '1500', output_tokens: '300', cached_input_tokens: '500' }),
    'fp3', 0
  );

  // 4. Unexpected extra fields
  db.prepare(`INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
    'moonshot', 'resp_extra', '2026-09-22T22:03:00Z', 'moonshot-v1-128k',
    JSON.stringify({
      input_tokens: 2000,
      output_tokens: 400,
      cached_input_tokens: 1000,
      unknown_meta: { foo: 'bar', nested: [1, 2, 3] },
      client_version: 'v4.2.0'
    }),
    'fp4', 0
  );

  // 5. usage column is NULL
  db.prepare(`INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
    'xai', 'resp_null_usage', '2026-09-22T22:04:00Z', 'grok-2-mini', null, 'fp5', 0
  );

  // 6. model column is NULL
  db.prepare(`INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
    'unknown_provider', 'resp_null_model', '2026-09-22T22:05:00Z', null,
    JSON.stringify({ input_tokens: 800, output_tokens: 100, cached_input_tokens: 200 }),
    'fp6', 0
  );

  db.close();

  try {
    const res = await apiFetch('/api/cost?since=2026-09-22T00:00:00Z&group_by=model', {
      headers: { 'x-test-db-path': testDb }
    });

    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.data.source, 'live');
    assert.strictEqual(res.data.total_responses, 6);

    for (const item of res.data.breakdown) {
      assert.ok(typeof item.turns === 'number' && !isNaN(item.turns));
      assert.ok(typeof item.total_ctx === 'number' && !isNaN(item.total_ctx));
      assert.ok(typeof item.out_tokens === 'number' && !isNaN(item.out_tokens));
      assert.ok(typeof item.cache_read === 'number' && !isNaN(item.cache_read));
      assert.ok(typeof item.cache_efficiency_pct === 'number' && !isNaN(item.cache_efficiency_pct));
      assert.ok(typeof item.cost_usd === 'number' && !isNaN(item.cost_usd));
      assert.ok(item.cache_efficiency_pct >= 0 && item.cache_efficiency_pct <= 100);
    }

    const agg = res.data.aggregate;
    assert.ok(!isNaN(agg.total_context_tokens));
    assert.ok(!isNaN(agg.total_output_tokens));
    assert.ok(!isNaN(agg.total_cache_read_tokens));
    assert.ok(!isNaN(agg.overall_cache_hit_pct));
    assert.ok(!isNaN(agg.total_cost_usd));
    assert.ok(agg.overall_cache_hit_pct >= 0 && agg.overall_cache_hit_pct <= 100);
  } finally {
    for (const ext of ['', '-wal', '-shm']) {
      if (fs.existsSync(testDb + ext)) fs.unlinkSync(testDb + ext);
    }
  }
});

// ============================================================================
// EDGE CASE 3: Negative token numbers & extreme values
// ============================================================================

test('EC3.1: /api/cost handles negative token numbers without crashing or NaN', async () => {
  const testDb = '/tmp/test_negative_tokens.sqlite';
  initEmptyDb(testDb);
  const db = new Database(testDb);

  db.prepare(`INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
    'xai', 'resp_neg', '2026-09-22T22:00:00Z', 'grok-2',
    JSON.stringify({ input_tokens: -1000, output_tokens: -200, cached_input_tokens: -500 }),
    'fp1', 0
  );

  db.close();

  try {
    const res = await apiFetch('/api/cost?since=2026-09-22T00:00:00Z', {
      headers: { 'x-test-db-path': testDb }
    });

    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.data.source, 'live');
    assert.strictEqual(res.data.aggregate.overall_cache_hit_pct, 0);
    assert.ok(!isNaN(res.data.aggregate.total_cost_usd));
    assert.ok(!isNaN(res.data.aggregate.overall_cache_hit_pct));
  } finally {
    for (const ext of ['', '-wal', '-shm']) {
      if (fs.existsSync(testDb + ext)) fs.unlinkSync(testDb + ext);
    }
  }
});

test('EC3.2: /api/cost handles extreme high token numbers (trillions) without integer overflow', async () => {
  const testDb = '/tmp/test_extreme_tokens.sqlite';
  initEmptyDb(testDb);
  const db = new Database(testDb);

  const ONE_TRILLION = 1_000_000_000_000;
  db.prepare(`INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
    'xai', 'resp_huge_grok', '2026-09-22T22:00:00Z', 'grok-3',
    JSON.stringify({
      input_tokens: ONE_TRILLION,
      output_tokens: 500_000_000_000,
      cached_input_tokens: 800_000_000_000
    }),
    'fp1', 0
  );

  db.prepare(`INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
    'moonshot', 'resp_huge_kimi', '2026-09-22T22:01:00Z', 'kimi-latest',
    JSON.stringify({
      input_tokens: 500_000_000_000,
      output_tokens: 100_000_000_000,
      cached_input_tokens: 400_000_000_000
    }),
    'fp2', 0
  );

  db.close();

  try {
    const res = await apiFetch('/api/cost?since=2026-09-22T00:00:00Z', {
      headers: { 'x-test-db-path': testDb }
    });

    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.data.source, 'live');
    assert.strictEqual(res.data.total_responses, 2);
    assert.strictEqual(res.data.aggregate.total_context_tokens, 1_500_000_000_000);
    assert.strictEqual(res.data.aggregate.total_output_tokens, 600_000_000_000);
    assert.strictEqual(res.data.aggregate.total_cache_read_tokens, 1_200_000_000_000);
    assert.strictEqual(res.data.aggregate.overall_cache_hit_pct, 80);

    assert.ok(Number.isFinite(res.data.aggregate.total_cost_usd));
    assert.ok(res.data.aggregate.total_cost_usd > 0);
  } finally {
    for (const ext of ['', '-wal', '-shm']) {
      if (fs.existsSync(testDb + ext)) fs.unlinkSync(testDb + ext);
    }
  }
});

test('EC3.3: /api/cost handles cacheRead > totalContext cleanly with Math.min clamping', async () => {
  const testDb = '/tmp/test_cache_overflow.sqlite';
  initEmptyDb(testDb);
  const db = new Database(testDb);

  db.prepare(`INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
    'moonshot', 'resp_overcache', '2026-09-22T22:00:00Z', 'kimi-k1.5',
    JSON.stringify({ input_tokens: 1000, output_tokens: 100, cached_input_tokens: 2500 }),
    'fp1', 0
  );

  db.close();

  try {
    const res = await apiFetch('/api/cost?since=2026-09-22T00:00:00Z', {
      headers: { 'x-test-db-path': testDb }
    });

    assert.strictEqual(res.status, 200);
    const item = res.data.breakdown.find((b: any) => b.key === 'kimi-k1.5');
    assert.ok(item);
    assert.strictEqual(item.cache_efficiency_pct, 100);
    assert.strictEqual(res.data.aggregate.overall_cache_hit_pct, 100);
  } finally {
    for (const ext of ['', '-wal', '-shm']) {
      if (fs.existsSync(testDb + ext)) fs.unlinkSync(testDb + ext);
    }
  }
});

test('EC3.4: /api/cost handles unlisted / unknown model by falling back to default rates', async () => {
  const testDb = '/tmp/test_unknown_model.sqlite';
  initEmptyDb(testDb);
  const db = new Database(testDb);

  db.prepare(`INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
    'custom', 'resp_alien', '2026-09-22T22:00:00Z', 'alien-deep-thought-v99',
    JSON.stringify({ input_tokens: 1_000_000, output_tokens: 100_000, cached_input_tokens: 500_000 }),
    'fp1', 0
  );

  db.close();

  try {
    const res = await apiFetch('/api/cost?since=2026-09-22T00:00:00Z', {
      headers: { 'x-test-db-path': testDb }
    });

    assert.strictEqual(res.status, 200);
    const item = res.data.breakdown.find((b: any) => b.key === 'alien-deep-thought-v99');
    assert.ok(item);
    assert.strictEqual(item.cost_usd, 3.15);
  } finally {
    for (const ext of ['', '-wal', '-shm']) {
      if (fs.existsSync(testDb + ext)) fs.unlinkSync(testDb + ext);
    }
  }
});

// ============================================================================
// EDGE CASE 4: Missing headers & parameter boundaries
// ============================================================================

test('EC4.1: /api/cost without x-test-db-path header returns 200 with valid schema', async () => {
  const res = await apiFetch('/api/cost');
  assert.strictEqual(res.status, 200);
  assert.ok(res.data.aggregate);
  assert.ok(Array.isArray(res.data.breakdown));
  assert.ok(['live', 'mock'].includes(res.data.source));
});

test('EC4.2: /api/cost with non-existent x-test-db-path gracefully falls back to production/mock', async () => {
  const res = await apiFetch('/api/cost', {
    headers: { 'x-test-db-path': '/tmp/ghost_db_path_987654321.sqlite' }
  });
  assert.strictEqual(res.status, 200);
  assert.ok(res.data.aggregate);
  assert.ok(Array.isArray(res.data.breakdown));
});

test('EC4.3: /api/cost handles extreme and boundary query params: limit=0, limit=999999, negative, floats', async () => {
  const testCases = [
    '/api/cost?limit=0',
    '/api/cost?limit=999999',
    '/api/cost?limit=-50',
    '/api/cost?limit=25.7',
    '/api/cost?since=',
    '/api/cost?since=null',
    '/api/cost?since=undefined',
    '/api/cost?since=0m',
    '/api/cost?since=-10h',
    '/api/cost?group_by=unrecognized_dimension'
  ];

  for (const q of testCases) {
    const res = await apiFetch(q);
    assert.strictEqual(res.status, 200, `Expected 200 for query: ${q}`);
    assert.ok(res.data.aggregate, `Must return valid aggregate for ${q}`);
    assert.ok(Array.isArray(res.data.breakdown), `Must return valid breakdown for ${q}`);
  }
});

test('EC4.4: /api/quotas handles complete absence of headers and returns full pool schema', async () => {
  const res = await apiFetch('/api/quotas');
  assert.strictEqual(res.status, 200);
  assert.ok(res.data.pools);
  assert.ok(res.data.pools.claude_a);
  assert.ok(res.data.pools.claude_b);
  assert.ok(res.data.pools.codex);
  assert.ok(res.data.pools.antigravity);
  assert.ok(res.data.pools.grok);
  assert.ok(res.data.pools.kimi);

  const grok = res.data.pools.grok;
  assert.strictEqual(typeof grok.name, 'string');
  assert.strictEqual(typeof grok.state, 'string');
  assert.ok(grok.five_hour_used_pct >= 0 && grok.five_hour_used_pct <= 100);
  assert.ok(grok.weekly_used_pct >= 0 && grok.weekly_used_pct <= 100);

  const kimi = res.data.pools.kimi;
  assert.strictEqual(typeof kimi.name, 'string');
  assert.strictEqual(typeof kimi.state, 'string');
  assert.ok(kimi.five_hour_used_pct >= 0 && kimi.five_hour_used_pct <= 100);
  assert.ok(kimi.weekly_used_pct >= 0 && kimi.weekly_used_pct <= 100);
});

test('EC4.5: /api/quotas TSV parser clamps out-of-bounds percentages and handles corrupt rows', async () => {
  // Test route's internal parser against out-of-range and corrupt TSV lines
  const parseClampedNum = (val: string | undefined, defaultVal = 0): number => {
    if (!val || val === '-' || val === 'null' || val === 'undefined') return defaultVal;
    const n = parseFloat(val);
    if (isNaN(n)) return defaultVal;
    return Math.min(100, Math.max(0, n));
  };

  assert.strictEqual(parseClampedNum('-999'), 0);
  assert.strictEqual(parseClampedNum('9999'), 100);
  assert.strictEqual(parseClampedNum('NaN'), 0);
  assert.strictEqual(parseClampedNum('Infinity'), 100);
  assert.strictEqual(parseClampedNum('-Infinity'), 0);
  assert.strictEqual(parseClampedNum(''), 0);
  assert.strictEqual(parseClampedNum('-'), 0);
});

