/**
 * tests/e2e/grok_kimi_api_db.test.ts
 * 
 * Milestone 4 (AC2): Scripted DB & API endpoint verification for Grok & Kimi models.
 * Tests:
 * 1. Isolated SQLite WAL database fixture generation with Grok and Kimi responses/occurrences.
 * 2. Direct SQLite query engine verification (group_by model, thread join, quarantine filter).
 * 3. /api/cost endpoint verification with x-test-db-path header and fallback mock data.
 * 4. /api/quotas endpoint verification confirming grok and kimi pool objects.
 * 5. /api/agents endpoint verification confirming grok and kimi agent seats.
 */

import { describe, it, before, after } from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { spawn, type ChildProcess } from 'node:child_process';
import Database from 'better-sqlite3';
import { mockCostData, mockQuotas, mockAgentsResponse } from '../../src/lib/mock-data.ts';

const TEST_PORT = process.env.TEST_PORT ? parseInt(process.env.TEST_PORT, 10) : 3456;
const BASE_URL = `http://localhost:${TEST_PORT}`;

let serverProcess: ChildProcess | null = null;
let testDir: string = '';
let testDbPath: string = '';

async function isServerReady(port: number): Promise<boolean> {
  try {
    const res = await fetch(`http://localhost:${port}/api/nodes`, { signal: AbortSignal.timeout(1000) });
    return res.ok || res.status === 200;
  } catch {
    return false;
  }
}

async function ensureTestServer(): Promise<void> {
  const ready = await isServerReady(TEST_PORT);
  if (ready) return;

  return new Promise<void>((resolve, reject) => {
    serverProcess = spawn('npx', ['next', 'start', '-p', String(TEST_PORT)], {
      cwd: process.cwd(),
      stdio: 'pipe',
      detached: false
    });

    const timeout = setTimeout(() => {
      if (serverProcess) serverProcess.kill('SIGTERM');
      reject(new Error(`Test server failed to start on port ${TEST_PORT} within 20s`));
    }, 20000);

    const checkInterval = setInterval(async () => {
      if (await isServerReady(TEST_PORT)) {
        clearInterval(checkInterval);
        clearTimeout(timeout);
        resolve();
      }
    }, 500);
  });
}

function createGrokKimiDatabase(dbPath: string): void {
  const db = new Database(dbPath);
  try {
    db.exec(`
      PRAGMA journal_mode = WAL;
      PRAGMA busy_timeout = 5000;

      CREATE TABLE IF NOT EXISTS usage_responses (
        provider TEXT,
        response_id TEXT,
        timestamp TEXT,
        model TEXT,
        usage TEXT,
        fingerprint TEXT,
        quarantined INTEGER DEFAULT 0,
        PRIMARY KEY(provider, response_id)
      );

      CREATE TABLE IF NOT EXISTS usage_diagnostics (
        kind TEXT PRIMARY KEY,
        count INTEGER
      );

      CREATE TABLE IF NOT EXISTS usage_occurrences (
        provider TEXT,
        response_id TEXT,
        host TEXT,
        thread TEXT,
        source TEXT,
        PRIMARY KEY(provider, response_id, host, thread, source)
      );
    `);

    const insertResp = db.prepare(`
      INSERT OR REPLACE INTO usage_responses (provider, response_id, timestamp, model, usage, fingerprint, quarantined)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);

    const insertOcc = db.prepare(`
      INSERT OR REPLACE INTO usage_occurrences (provider, response_id, host, thread, source)
      VALUES (?, ?, ?, ?, ?)
    `);

    // 1. Grok-2 Turn
    const grok2Usage = JSON.stringify({
      input_tokens: 1_200_000,
      cached_input_tokens: 1_100_000,
      cache_read_input_tokens: 1_100_000,
      output_tokens: 45_000,
      total_tokens: 1_245_000
    });
    insertResp.run('xai', 'resp_grok2_1', '2026-09-27T02:00:00Z', 'grok-2', grok2Usage, 'fp_grok2', 0);
    insertOcc.run('xai', 'resp_grok2_1', 'wrk-bd01', 'bd-grok-worker-1', '/home/mboyle/bd-persist/logs/grok_1.jsonl');

    // 2. Grok-2-mini Turn
    const grokMiniUsage = JSON.stringify({
      input_tokens: 2_500_000,
      cached_input_tokens: 2_000_000,
      cache_read_input_tokens: 2_000_000,
      output_tokens: 80_000,
      total_tokens: 2_580_000
    });
    insertResp.run('xai', 'resp_grok_mini_1', '2026-09-27T02:10:00Z', 'grok-2-mini', grokMiniUsage, 'fp_grok_mini', 0);
    insertOcc.run('xai', 'resp_grok_mini_1', 'wrk-bd02', 'bd-grok-worker-2', '/home/mboyle/bd-persist/logs/grok_mini.jsonl');

    // 3. Kimi-k1.5 Turn
    const kimiUsage = JSON.stringify({
      input_tokens: 1_800_000,
      cached_input_tokens: 1_650_000,
      cache_read_input_tokens: 1_650_000,
      output_tokens: 50_000,
      total_tokens: 1_850_000
    });
    insertResp.run('moonshot', 'resp_kimi_1', '2026-09-27T02:15:00Z', 'kimi-k1.5', kimiUsage, 'fp_kimi', 0);
    insertOcc.run('moonshot', 'resp_kimi_1', 'wrk-bd03', 'bd-kimi-worker-1', '/home/mboyle/bd-persist/logs/kimi_1.jsonl');

    // 4. Moonshot-v1-128k Turn
    const moonshotUsage = JSON.stringify({
      input_tokens: 5_000_000,
      cached_input_tokens: 4_600_000,
      cache_read_input_tokens: 4_600_000,
      output_tokens: 120_000,
      total_tokens: 5_120_000
    });
    insertResp.run('moonshot', 'resp_moonshot_1', '2026-09-27T02:20:00Z', 'moonshot-v1-128k', moonshotUsage, 'fp_moonshot', 0);
    insertOcc.run('moonshot', 'resp_moonshot_1', 'wrk-bd04', 'bd-kimi-worker-2', '/home/mboyle/bd-persist/logs/moonshot_1.jsonl');

    // 5. Quarantined Turn (should be filtered out by WHERE quarantined = 0)
    const quarantinedUsage = JSON.stringify({
      input_tokens: 9_999_999,
      cached_input_tokens: 9_999_999,
      cache_read_input_tokens: 9_999_999,
      output_tokens: 99_999,
      total_tokens: 10_099_998
    });
    insertResp.run('xai', 'resp_quarantined', '2026-09-27T02:25:00Z', 'grok-2', quarantinedUsage, 'fp_bad', 1);

    // Diagnostics
    db.prepare('INSERT OR REPLACE INTO usage_diagnostics VALUES (?, ?)').run('grok_ingest', 2);
    db.prepare('INSERT OR REPLACE INTO usage_diagnostics VALUES (?, ?)').run('kimi_ingest', 2);

  } finally {
    db.close();
  }
}

describe('AC2: Scripted DB & API Endpoint Verification for Grok & Kimi', () => {

  before(async () => {
    testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ac2_grok_kimi_'));
    testDbPath = path.join(testDir, 'usage_test.sqlite');
    createGrokKimiDatabase(testDbPath);
    await ensureTestServer();
  });

  after(() => {
    if (serverProcess) {
      serverProcess.kill('SIGTERM');
      serverProcess = null;
    }
    try {
      if (fs.existsSync(testDir)) {
        fs.rmSync(testDir, { recursive: true, force: true });
      }
    } catch {}
  });

  // 1. Database Generation & Schema Integrity
  it('T2.1: SQLite test database generates with valid WAL journal mode and Grok/Kimi schema', () => {
    assert.ok(fs.existsSync(testDbPath), 'Database file must exist on disk');
    const db = new Database(testDbPath, { readonly: true });
    try {
      const journalMode = db.pragma('journal_mode', { simple: true }) as string;
      assert.strictEqual(journalMode.toLowerCase(), 'wal', 'Database must operate in WAL journal mode');

      const tables = db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all() as Array<{ name: string }>;
      const tableNames = tables.map(t => t.name);
      assert.ok(tableNames.includes('usage_responses'), 'usage_responses table must exist');
      assert.ok(tableNames.includes('usage_occurrences'), 'usage_occurrences table must exist');
      assert.ok(tableNames.includes('usage_diagnostics'), 'usage_diagnostics table must exist');
    } finally {
      db.close();
    }
  });

  // 2. Direct SQLite Query Verification by Model
  it('T2.2: SQLite aggregation query correctly groups and extracts Grok and Kimi usage metrics', () => {
    const db = new Database(testDbPath, { readonly: true });
    try {
      const stmt = db.prepare(`
        SELECT
          COALESCE(model, 'unknown') as key,
          COUNT(*) as turns,
          COALESCE(SUM(COALESCE(json_extract(usage, '$.input_tokens'), 0)), 0) as total_ctx,
          COALESCE(SUM(COALESCE(json_extract(usage, '$.output_tokens'), 0)), 0) as out_tokens,
          COALESCE(SUM(MAX(COALESCE(json_extract(usage, '$.cache_read_input_tokens'), 0), COALESCE(json_extract(usage, '$.cached_input_tokens'), 0))), 0) as cache_read,
          COALESCE(MAX(COALESCE(json_extract(usage, '$.input_tokens'), 0)), 0) as max_ctx
        FROM usage_responses
        WHERE timestamp >= ? AND quarantined = 0
        GROUP BY model
        ORDER BY total_ctx DESC;
      `);

      const rows = stmt.all('2026-09-27T00:00:00Z') as Array<{
        key: string;
        turns: number;
        total_ctx: number;
        out_tokens: number;
        cache_read: number;
        max_ctx: number;
      }>;

      assert.strictEqual(rows.length, 4, 'Must return 4 models (moonshot-v1-128k, grok-2-mini, kimi-k1.5, grok-2)');

      const grok2 = rows.find(r => r.key === 'grok-2');
      assert.ok(grok2, 'grok-2 must be in results');
      assert.strictEqual(grok2.turns, 1, 'Quarantined grok-2 row must be excluded');
      assert.strictEqual(grok2.total_ctx, 1_200_000);
      assert.strictEqual(grok2.cache_read, 1_100_000);
      assert.strictEqual(grok2.out_tokens, 45_000);

      const grokMini = rows.find(r => r.key === 'grok-2-mini');
      assert.ok(grokMini, 'grok-2-mini must be in results');
      assert.strictEqual(grokMini.total_ctx, 2_500_000);
      assert.strictEqual(grokMini.cache_read, 2_000_000);
      assert.strictEqual(grokMini.out_tokens, 80_000);

      const kimi = rows.find(r => r.key === 'kimi-k1.5');
      assert.ok(kimi, 'kimi-k1.5 must be in results');
      assert.strictEqual(kimi.total_ctx, 1_800_000);
      assert.strictEqual(kimi.cache_read, 1_650_000);
      assert.strictEqual(kimi.out_tokens, 50_000);

      const moonshot = rows.find(r => r.key === 'moonshot-v1-128k');
      assert.ok(moonshot, 'moonshot-v1-128k must be in results');
      assert.strictEqual(moonshot.total_ctx, 5_000_000);
      assert.strictEqual(moonshot.cache_read, 4_600_000);
      assert.strictEqual(moonshot.out_tokens, 120_000);
    } finally {
      db.close();
    }
  });

  // 3. Direct SQLite Query Verification by Thread
  it('T2.3: SQLite thread join query correctly links Grok and Kimi occurrences to agent threads', () => {
    const db = new Database(testDbPath, { readonly: true });
    try {
      const stmt = db.prepare(`
        SELECT
          o.thread as thread,
          r.model as model,
          COUNT(*) as turns,
          COALESCE(SUM(COALESCE(json_extract(r.usage, '$.input_tokens'), 0)), 0) as total_ctx
        FROM usage_occurrences o
        JOIN usage_responses r ON o.provider = r.provider AND o.response_id = r.response_id
        WHERE r.quarantined = 0
        GROUP BY o.thread, r.model
        ORDER BY o.thread ASC;
      `);

      const rows = stmt.all() as Array<{ thread: string; model: string; turns: number; total_ctx: number }>;
      assert.strictEqual(rows.length, 4);

      const grokThread1 = rows.find(r => r.thread === 'bd-grok-worker-1');
      assert.ok(grokThread1, 'bd-grok-worker-1 thread must be recorded');
      assert.strictEqual(grokThread1.model, 'grok-2');
      assert.strictEqual(grokThread1.total_ctx, 1_200_000);

      const kimiThread1 = rows.find(r => r.thread === 'bd-kimi-worker-1');
      assert.ok(kimiThread1, 'bd-kimi-worker-1 thread must be recorded');
      assert.strictEqual(kimiThread1.model, 'kimi-k1.5');
      assert.strictEqual(kimiThread1.total_ctx, 1_800_000);
    } finally {
      db.close();
    }
  });

  // 4. Test /api/cost with x-test-db-path Header
  it('T2.4: /api/cost endpoint aggregates custom SQLite sandbox and returns grok and kimi in breakdown', async () => {
    const res = await fetch(`${BASE_URL}/api/cost?since=24h&group_by=model`, {
      headers: {
        'x-test-db-path': testDbPath
      }
    });

    assert.strictEqual(res.status, 200, '/api/cost must return HTTP 200');
    const data = await res.json();
    assert.ok(Array.isArray(data.breakdown), 'Response must include breakdown array');

    const grok2Entry = data.breakdown.find((b: any) => b.key === 'grok-2');
    assert.ok(grok2Entry, 'grok-2 must appear in /api/cost breakdown');
    assert.strictEqual(grok2Entry.turns, 1);
    assert.strictEqual(grok2Entry.total_ctx, 1_200_000);
    assert.strictEqual(grok2Entry.cache_read, 1_100_000);
    assert.strictEqual(grok2Entry.out_tokens, 45_000);
    // Cost calculation: (100k fresh * 2.0) + (1.1M cache * 0.20) + (45k out * 10.0) = 0.20 + 0.22 + 0.45 = $0.87
    assert.strictEqual(grok2Entry.cost_usd, 0.87, 'Cost for grok-2 must match $0.87');
    assert.strictEqual(grok2Entry.cache_efficiency_pct, 91.67);

    const kimiEntry = data.breakdown.find((b: any) => b.key === 'kimi-k1.5');
    assert.ok(kimiEntry, 'kimi-k1.5 must appear in /api/cost breakdown');
    assert.strictEqual(kimiEntry.turns, 1);
    assert.strictEqual(kimiEntry.total_ctx, 1_800_000);
    assert.strictEqual(kimiEntry.cache_read, 1_650_000);
    // Cost calculation: (150k fresh * 1.0) + (1.65M cache * 0.15) + (50k out * 3.0) = 0.15 + 0.2475 + 0.15 = $0.5475 -> 0.55
    assert.strictEqual(kimiEntry.cost_usd, 0.55);
    assert.strictEqual(kimiEntry.cache_efficiency_pct, 91.67);
  });

  // 5. Test /api/cost Fallback Mock Telemetry
  it('T2.5: /api/cost fallback mock telemetry contains verified Grok and Kimi breakdown rows', () => {
    assert.ok(mockCostData.breakdown, 'mockCostData must include breakdown');
    const grokMock = mockCostData.breakdown.find(b => b.key === 'grok-2');
    assert.ok(grokMock, 'grok-2 must exist in mockCostData');
    assert.ok(grokMock.total_ctx > 0, 'grok-2 context tokens must be positive');
    assert.ok(grokMock.cache_efficiency_pct >= 90.0, 'grok-2 mock efficiency must exceed 90% target');

    const kimiMock = mockCostData.breakdown.find(b => b.key === 'kimi-k1.5');
    assert.ok(kimiMock, 'kimi-k1.5 must exist in mockCostData');
    assert.ok(kimiMock.total_ctx > 0, 'kimi-k1.5 context tokens must be positive');
    assert.ok(kimiMock.cache_efficiency_pct >= 90.0, 'kimi-k1.5 mock efficiency must exceed 90% target');
  });

  // 6. Test /api/quotas Live Endpoint
  it('T2.6: /api/quotas endpoint returns grok and kimi pool objects with five_hour and weekly usage', async () => {
    const res = await fetch(`${BASE_URL}/api/quotas`);
    assert.strictEqual(res.status, 200, '/api/quotas must return HTTP 200');

    const data = await res.json();
    assert.ok(data.pools, 'Quota response must include pools object');

    // Verify Grok Pool Quota
    assert.ok(data.pools.grok, 'pools.grok must be defined');
    const grok = data.pools.grok;
    assert.ok(typeof grok.name === 'string', 'grok quota must have name');
    assert.ok(typeof grok.five_hour_used_pct === 'number', 'five_hour_used_pct must be number');
    assert.ok(grok.five_hour_used_pct >= 0 && grok.five_hour_used_pct <= 100, 'five_hour_used_pct must be clamped [0, 100]');
    assert.ok(typeof grok.weekly_used_pct === 'number', 'weekly_used_pct must be number');
    assert.ok(grok.weekly_used_pct >= 0 && grok.weekly_used_pct <= 100, 'weekly_used_pct must be clamped [0, 100]');
    assert.ok(typeof grok.state === 'string', 'state must be string');
    assert.ok(typeof grok.evidence === 'string', 'evidence must be string');

    // Verify Kimi Pool Quota
    assert.ok(data.pools.kimi, 'pools.kimi must be defined');
    const kimi = data.pools.kimi;
    assert.ok(typeof kimi.name === 'string', 'kimi quota must have name');
    assert.ok(typeof kimi.five_hour_used_pct === 'number', 'five_hour_used_pct must be number');
    assert.ok(kimi.five_hour_used_pct >= 0 && kimi.five_hour_used_pct <= 100, 'five_hour_used_pct must be clamped [0, 100]');
    assert.ok(typeof kimi.weekly_used_pct === 'number', 'weekly_used_pct must be number');
    assert.ok(kimi.weekly_used_pct >= 0 && kimi.weekly_used_pct <= 100, 'weekly_used_pct must be clamped [0, 100]');
    assert.ok(typeof kimi.state === 'string', 'state must be string');
    assert.ok(typeof kimi.evidence === 'string', 'evidence must be string');
  });

  // 7. Test /api/quotas Fallback Contract
  it('T2.7: mockQuotas fixture defines standard quotas for Grok and Kimi pools', () => {
    assert.ok(mockQuotas.pools.grok, 'mockQuotas.pools.grok must exist');
    assert.strictEqual(mockQuotas.pools.grok.name, 'Grok Fleet Pool (xAI)');
    assert.strictEqual(mockQuotas.pools.grok.state, 'OK');
    assert.ok(mockQuotas.pools.grok.five_hour_used_pct >= 0);
    assert.ok(mockQuotas.pools.grok.weekly_used_pct >= 0);

    assert.ok(mockQuotas.pools.kimi, 'mockQuotas.pools.kimi must exist');
    assert.strictEqual(mockQuotas.pools.kimi.name, 'Kimi Fleet Pool (Moonshot)');
    assert.strictEqual(mockQuotas.pools.kimi.state, 'OK');
    assert.ok(mockQuotas.pools.kimi.five_hour_used_pct >= 0);
    assert.ok(mockQuotas.pools.kimi.weekly_used_pct >= 0);
  });

  // 8. Test /api/agents Live Endpoint
  it('T2.8: /api/agents endpoint discovers and exposes grok and kimi agent seats', async () => {
    const res = await fetch(`${BASE_URL}/api/agents`);
    assert.strictEqual(res.status, 200, '/api/agents must return HTTP 200');

    const data = await res.json();
    assert.ok(Array.isArray(data.agents), '/api/agents must return agents array');

    const grokAgent = data.agents.find((a: any) => a.type === 'grok' || a.seat.toLowerCase().includes('grok'));
    assert.ok(grokAgent, 'At least one grok agent seat must be returned');
    assert.strictEqual(grokAgent.type, 'grok', 'Agent type must be "grok"');
    assert.ok(grokAgent.model.toLowerCase().includes('grok'), 'Model must be a grok model');
    assert.ok(['idle', 'busy', 'offline', 'paused'].includes(grokAgent.status), 'Status must be valid');

    const kimiAgent = data.agents.find((a: any) => a.type === 'kimi' || a.seat.toLowerCase().includes('kimi'));
    assert.ok(kimiAgent, 'At least one kimi agent seat must be returned');
    assert.strictEqual(kimiAgent.type, 'kimi', 'Agent type must be "kimi"');
    assert.ok(kimiAgent.model.toLowerCase().includes('kimi') || kimiAgent.model.toLowerCase().includes('moonshot'), 'Model must be a kimi model');
    assert.ok(['idle', 'busy', 'offline', 'paused'].includes(kimiAgent.status), 'Status must be valid');
  });

  // 9. Test /api/agents Mock Fallback
  it('T2.9: mockAgentsResponse fixture contains verified Grok and Kimi seats with correct types', () => {
    const grokMock = mockAgentsResponse.agents.find(a => a.type === 'grok');
    assert.ok(grokMock, 'mockAgentsResponse must include grok agent');
    assert.strictEqual(grokMock.type, 'grok');
    assert.strictEqual(grokMock.model, 'grok-2');

    const kimiMock = mockAgentsResponse.agents.find(a => a.type === 'kimi');
    assert.ok(kimiMock, 'mockAgentsResponse must include kimi agent');
    assert.strictEqual(kimiMock.type, 'kimi');
    assert.strictEqual(kimiMock.model, 'kimi-k1.5');
  });

});
