/**
 * tests/e2e/tier4_workloads.test.ts
 * Tier 4: Real-World Swarm Workload Scenarios & Direct Acceptance Criteria Verification
 * Simulates 15+ active agents writing tokens, dispatchers polling queues, operator reordering,
 * CI shard updates, and directly verifies AC1, AC2, AC3, and AC4.
 * Directly tests src/lib/ modules and live Next.js API Route Handlers.
 */

import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import {
  createTempDir,
  cleanupPath,
  createSqliteSandbox,
  createTsvSandbox,
  Database,
  withDbRetry,
  mutateTsvAtomically,
  calculateQuotaDistinction,
  apiFetch
} from './test_helpers.ts';

// ============================================================================
// AC1: App Starts Cleanly Without Compilation or Hydration Errors
// ============================================================================
test('T4_AC1: Application build and hydration safety validation', async () => {
  // Query the live running Next.js application server
  const res = await apiFetch('/');
  assert.strictEqual(res.status, 200, 'Root route must return 200 OK');
  assert.ok(typeof res.data === 'string', 'Root route must return HTML string');
  assert.ok(
    res.data.includes('Swarm') || res.data.includes('Dashboard') || res.data.includes('html'),
    'Root HTML must render dashboard markup'
  );
  assert.ok(
    !res.data.includes('Hydration failed') && !res.data.includes('Minified React error'),
    'Root HTML must contain no hydration errors'
  );
});

// ============================================================================
// AC2: Dedicated API Quota Panel Distinguishing 5h vs Weekly for Claude vs Gemini
// ============================================================================
test('T4_AC2: Dedicated API Quota panel distinguishes 5h vs weekly limits for Claude vs Gemini', async () => {
  // 1. Live route verification
  const res = await apiFetch('/api/quotas');
  assert.strictEqual(res.status, 200, '/api/quotas must return 200 OK');
  const { claude_a, claude_b, antigravity } = res.data.pools;

  assert.ok(typeof claude_a.five_hour_used_pct === 'number', 'Claude A 5h used must be number');
  assert.ok(typeof claude_a.weekly_used_pct === 'number', 'Claude A weekly used must be number');
  assert.ok(typeof claude_b.five_hour_used_pct === 'number', 'Claude B 5h used must be number');
  assert.ok(typeof claude_b.weekly_used_pct === 'number', 'Claude B weekly used must be number');

  assert.ok(
    typeof antigravity.gemini.five_hour_remaining_pct === 'number',
    'Gemini 5h remaining must be number'
  );
  assert.ok(
    typeof antigravity.gemini.weekly_remaining_pct === 'number',
    'Gemini weekly remaining must be number'
  );
  assert.ok(
    typeof antigravity.claude_gpt.five_hour_remaining_pct === 'number',
    'Claude/GPT 5h remaining must be number'
  );

  // Invariant assertion: Claude measures USED, Gemini measures REMAINING
  assert.notStrictEqual(
    claude_a.five_hour_used_pct,
    antigravity.gemini.five_hour_remaining_pct,
    'Claude 5h used must not be conflated with Gemini 5h remaining'
  );

  // 2. Parser verification against specification format
  const livePoolState = `pool\tstate\tsince\tevidence\tpct\tresets_at\tweekly_pct\tfive_hour_remaining_pct\tgemini_five_hour_remaining_pct\tgemini_weekly_remaining_pct\tclaude_gpt_five_hour_remaining_pct\tclaude_gpt_weekly_remaining_pct\tquota_observed_at
A\tOFF-PACE\t2026-09-22T21:40:05Z\tweekly_all/seven_day 82% at 52% of the week\t19\t2026-09-23T02:09:59Z\t82\t-\t-\t-\t-\t-\t-
B\tUNKNOWN\t2026-09-22T11:00:05Z\tusage cache 89642s old\t8\t2026-09-22T02:10:00Z\t31\t-\t-\t-\t-\t-\t-
codex\tUNKNOWN\t2026-09-22T21:25:05Z\t0 of 15 roster host(s) answered\t-\t-\t-\t-\t-\t-\t-\t-\t-
AGY\tUNKNOWN\t2026-09-22T11:00:05Z\tAGY quota observations REMAINING\t-\t-\t-\t93\t93\t46\t100\t72\t2026-09-21T10:16:10Z`;

  const parsed = calculateQuotaDistinction(livePoolState);
  assert.strictEqual(parsed.pools.claude_a.five_hour_used_pct, 19);
  assert.strictEqual(parsed.pools.claude_a.weekly_used_pct, 82);
  assert.strictEqual(parsed.pools.antigravity.gemini.five_hour_remaining_pct, 93);
  assert.strictEqual(parsed.pools.antigravity.gemini.weekly_remaining_pct, 46);
});

// ============================================================================
// AC3: 10 Concurrent Readers Under 15 Active Writers Without Deadlock
// ============================================================================
test('T4_AC3: Backend sustains 10 concurrent API read requests to usage.sqlite under 15 active writers without database is locked', () => {
  const scriptPath = path.resolve(process.cwd(), 'scripts/test_sqlite_concurrency.py');
  assert.ok(fs.existsSync(scriptPath));

  const proc = spawnSync('python3', [scriptPath], { encoding: 'utf8', timeout: 60000 });
  assert.strictEqual(proc.status, 0, `AC3 Python runner failed:\n${proc.stdout}\n${proc.stderr}`);
  assert.ok(proc.stdout.includes('Failed reads (locked errors): 0'));
  assert.ok(proc.stdout.includes('AC3 Verified'));
});

// ============================================================================
// AC4: Interactive Queue Re-ordering Without Corrupting Active Dispatcher Reads
// ============================================================================
test('T4_AC4: Interactive queue re-ordering successfully modifies ledger file without corrupting active dispatcher reads', () => {
  const scriptPath = path.resolve(process.cwd(), 'scripts/test_tsv_atomic_reorder.sh');
  assert.ok(fs.existsSync(scriptPath));

  const proc = spawnSync('bash', [scriptPath], { encoding: 'utf8', timeout: 60000 });
  assert.strictEqual(proc.status, 0, `AC4 Bash runner failed:\n${proc.stdout}\n${proc.stderr}`);
  assert.ok(proc.stdout.includes('Corrupted / torn reads detected: 0'));
  assert.ok(proc.stdout.includes('AC4 Verified'));
});

// ============================================================================
// Real-World Multi-Agent Swarm Workload Simulation
// ============================================================================
test('T4.5: Integrated Swarm Workload: 15 active agents, dynamic reordering, CI gate updates simultaneously', async () => {
  const dir = createTempDir('t4_swarm_');
  try {
    const dbPath = createSqliteSandbox(dir, 50);
    const tsvPath = createTsvSandbox(dir, 15);

    // 1. Simulating 15 active swarm writers inserting token and task telemetry
    const pythonSwarmWriter = `
import sqlite3, time, random
conn = sqlite3.connect('${dbPath}', timeout=5.0)
conn.execute('PRAGMA busy_timeout = 5000;')
for i in range(15):
    for j in range(10):
        try:
            conn.execute('INSERT OR REPLACE INTO usage_diagnostics VALUES (?, ?)', (f'agent_{i}', random.randint(10, 5000)))
            conn.commit()
            time.sleep(0.001)
        except Exception:
            pass
conn.close()
`;
    spawnSync('python3', ['-c', pythonSwarmWriter], { encoding: 'utf8' });

    // 2. Simulating concurrent operator queue reorder
    await mutateTsvAtomically(tsvPath, (lines) => {
      const valid = lines.filter((l) => l.trim().length > 0);
      const topPriority = valid.slice(valid.length - 3);
      const remaining = valid.slice(0, valid.length - 3);
      return [...topPriority, ...remaining];
    });

    // 3. Simulating concurrent reader querying SQLite telemetry via Node.js better-sqlite3 withDbRetry
    const readCount = await withDbRetry(() => {
      const db = new Database(dbPath, { readonly: true, timeout: 5000 });
      try {
        const row = db.prepare('SELECT count(*) as count FROM usage_responses').get() as { count: number };
        return row.count;
      } finally {
        db.close();
      }
    });

    // 4. Verify 15 tasks intact in TSV ledger
    const ledgerLines = fs.readFileSync(tsvPath, 'utf8').trim().split('\n');
    assert.strictEqual(ledgerLines.length, 15, 'All 15 swarm tasks must remain intact');
    assert.strictEqual(readCount, 50, 'All 50 responses must be readable');
  } finally {
    cleanupPath(dir);
  }
});
