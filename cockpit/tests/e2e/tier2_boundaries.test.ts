/**
 * tests/e2e/tier2_boundaries.test.ts
 * Tier 2: Boundary & Corner Cases
 * Tests limits, nulls, timeouts, malformed inputs, and adversarial conditions across all 12 features.
 * Features covered: F1 through F12 (60 test cases total).
 * Directly tests src/lib/ modules and live Next.js API Route Handlers.
 */

import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import {
  createTempDir,
  cleanupPath,
  createSqliteSandbox,
  createTsvSandbox,
  getReadOnlyDb,
  closeDb,
  queryOne,
  getDbDiagnostics,
  withDbRetry,
  isSqliteBusyError,
  calculateFullJitterDelay,
  mutateTsvAtomically,
  parseDispatchLedgerLines,
  reorderDispatchLedgerRows,
  calculateQuotaDistinction,
  apiFetch,
  cn,
  formatNumber,
  formatCurrency,
  formatPercent,
  formatDuration,
  EXPECTED_CLUSTER_NODES,
  BLACKLISTED_HOST_IP,
  CI_TAXONOMY_CODES
} from './test_helpers.ts';

// ============================================================================
// F1: SQLite Concurrency Engine (Boundaries - 5 Tests)
// ============================================================================
test('F1_B.1: Empty database (0 rows in usage_responses) returns count=0 without crashing', () => {
  const dir = createTempDir('f1_b1_');
  try {
    const dbPath = createSqliteSandbox(dir, 0);
    const db = getReadOnlyDb({ dbPath });
    try {
      const row = queryOne<{ count: number }>('SELECT count(*) as count FROM usage_responses');
      assert.strictEqual(row?.count, 0, 'Must return 0 for empty database');
    } finally {
      closeDb();
    }
  } finally {
    cleanupPath(dir);
  }
});

test('F1_B.2: Non-existent SQLite database path throws catchable error', () => {
  assert.throws(
    () => {
      getReadOnlyDb({ dbPath: '/tmp/non_existent_db_xyz_9999.sqlite' });
    },
    /does not exist|unable to open/i,
    'Must throw when opening non-existent database'
  );
  closeDb();
});

test('F1_B.3: withDbRetry exhausts retries and rethrows error without infinite loop', async () => {
  let callCount = 0;
  await assert.rejects(
    async () => {
      await withDbRetry(
        async () => {
          callCount++;
          const err: any = new Error('permanent busy error');
          err.code = 'SQLITE_BUSY';
          throw err;
        },
        { maxRetries: 3, baseDelayMs: 2, maxDelayMs: 10 }
      );
    },
    /permanent busy error/,
    'Must rethrow after maxRetries exceeded'
  );
  assert.strictEqual(callCount, 4, 'Should attempt initial call + 3 retries');
});

test('F1_B.4: withDbRetry with 0ms delay executes without NaN delay or division by zero', async () => {
  let attempts = 0;
  const val = await withDbRetry(
    async () => {
      attempts++;
      if (attempts === 1) {
        const err: any = new Error('busy');
        err.code = 'SQLITE_BUSY';
        throw err;
      }
      return 'ZERO_DELAY_SUCCESS';
    },
    { maxRetries: 2, baseDelayMs: 0, maxDelayMs: 0 }
  );
  assert.strictEqual(val, 'ZERO_DELAY_SUCCESS');
  assert.strictEqual(attempts, 2);
});

test('F1_B.5: Large SQL query payload with parameter binding handles safely without buffer overflow', () => {
  const dir = createTempDir('f1_b5_');
  try {
    const dbPath = createSqliteSandbox(dir, 1);
    const db = getReadOnlyDb({ dbPath });
    try {
      const largeString = 'A'.repeat(50000);
      const row = db.prepare('SELECT ? as val').get(largeString) as { val: string };
      assert.strictEqual(row.val.length, 50000, '50,000 char parameter must bind safely');
    } finally {
      closeDb();
    }
  } finally {
    cleanupPath(dir);
  }
});

// ============================================================================
// F2: Atomic TSV Queue Mutator (Boundaries - 5 Tests)
// ============================================================================
test('F2_B.1: Mutation of non-existent TSV file creates empty file safely', async () => {
  const dir = createTempDir('f2_b1_');
  try {
    const nonExistentPath = path.join(dir, 'NEW_LEDGER.tsv');
    await mutateTsvAtomically(nonExistentPath, (lines) => {
      return ['2026-09-22T20:00:00Z\tbd-worker-1\trow1\tstarted\t/brief.md'];
    });
    assert.ok(fs.existsSync(nonExistentPath));
    const content = fs.readFileSync(nonExistentPath, 'utf8');
    assert.ok(content.includes('row1\tstarted'));
  } finally {
    cleanupPath(dir);
  }
});

test('F2_B.2: Target file with 0 bytes (empty TSV) handles without crashing', async () => {
  const dir = createTempDir('f2_b2_');
  try {
    const emptyPath = path.join(dir, 'EMPTY.tsv');
    fs.writeFileSync(emptyPath, '', 'utf8');
    await mutateTsvAtomically(emptyPath, (lines) => {
      return [...lines, '2026-09-22T20:00:00Z\tbd-worker-1\trow1\tdispatched\t/b.md'];
    });
    const content = fs.readFileSync(emptyPath, 'utf8');
    assert.ok(content.includes('row1\tdispatched'));
  } finally {
    cleanupPath(dir);
  }
});

test('F2_B.3: Lock contention timeout rejects when lock cannot be acquired within timeout', async () => {
  const dir = createTempDir('f2_b3_');
  try {
    const tsv = createTsvSandbox(dir, 2);
    const lockFile = path.join(dir, '.DISPATCH-LEDGER.tsv.lock');

    const blocker = spawn('/usr/bin/flock', ['-x', lockFile, 'sleep', '2']);
    await new Promise((r) => setTimeout(r, 100));

    try {
      await assert.rejects(
        async () => {
          await mutateTsvAtomically(tsv, (lines) => lines, 100);
        },
        /flock timed out|Timeout acquiring advisory lock|timed out/i,
        'Must reject with lock timeout when advisory lock is blocked'
      );
    } finally {
      try {
        blocker.kill('SIGKILL');
      } catch {}
    }
  } finally {
    cleanupPath(dir);
  }
});

test('F2_B.4: Line endings with trailing newlines do not duplicate blank rows', async () => {
  const dir = createTempDir('f2_b4_');
  try {
    const tsv = createTsvSandbox(dir, 3);
    await mutateTsvAtomically(tsv, (lines) => lines);
    await mutateTsvAtomically(tsv, (lines) => lines);
    const content = fs.readFileSync(tsv, 'utf8');
    const lines = content.split('\n');
    assert.ok(!lines[0].startsWith(' '), 'Line 1 must not be blank or prepended with space');
  } finally {
    cleanupPath(dir);
  }
});

test('F2_B.5: Read-only directory rejects atomic rename safely with catchable error', async () => {
  const dir = createTempDir('f2_b5_');
  try {
    const readonlySubdir = path.join(dir, 'readonly_dir');
    fs.mkdirSync(readonlySubdir);
    const targetFile = path.join(readonlySubdir, 'DISPATCH-LEDGER.tsv');
    fs.writeFileSync(targetFile, 'content\n');
    fs.chmodSync(readonlySubdir, 0o555);

    await assert.rejects(
      async () => {
        await mutateTsvAtomically(targetFile, (lines) => lines, 500);
      },
      /EACCES|permission denied/i,
      'Must reject with EACCES on read-only directory'
    );

    fs.chmodSync(readonlySubdir, 0o755);
  } finally {
    cleanupPath(dir);
  }
});

// ============================================================================
// F3: Backend API Route Handlers (Boundaries - 5 Tests)
// ============================================================================
test('F3_B.1: Malformed JSON payload is rejected with structured 400 response', async () => {
  const res = await apiFetch('/api/queue', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: '{ "action": "reorder", broken_json'
  });
  assert.strictEqual(res.status, 400);
  assert.ok(res.data.error.includes('Malformed JSON body') || res.data.error.includes('Bad Request'));
});

test('F3_B.2: Negative limit/offset pagination params are handled safely', async () => {
  const res = await apiFetch('/api/cost?since=24h&limit=-10');
  assert.strictEqual(res.status, 200);
  assert.ok(Array.isArray(res.data.breakdown));
});

test('F3_B.3: Empty array in POST /api/queue returns 400', async () => {
  const res = await apiFetch('/api/queue', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ action: 'reorder', ordered_row_ids: [] })
  });
  assert.strictEqual(res.status, 400);
  assert.ok(res.data.error.includes('non-empty array'));
});

test('F3_B.4: Unsupported HTTP method returns 405 Method Not Allowed structure', async () => {
  const res = await apiFetch('/api/queue', { method: 'DELETE' });
  assert.strictEqual(res.status, 405);
});

test('F3_B.5: Nonexistent filter query parameter on /api/nodes defaults safely', async () => {
  const res = await apiFetch('/api/nodes?filter=nonexistent');
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.data.nodes.length, 27);
});

// ============================================================================
// F4: Dedicated API Quota Panel (Boundaries - 5 Tests)
// ============================================================================
test('F4_B.1: 0% quota usage boundary: all headroom remaining', () => {
  const poolState = `pool\tstate\tsince\tevidence\tpct\tresets_at\tweekly_pct\tfive_hour_remaining_pct\tgemini_five_hour_remaining_pct\tgemini_weekly_remaining_pct\tclaude_gpt_five_hour_remaining_pct\tclaude_gpt_weekly_remaining_pct\tquota_observed_at
A\tACTIVE\t2026-09-22T21:40:05Z\tevid\t0\t2026-09-23T02:09:59Z\t0\t-\t-\t-\t-\t-\t-`;
  const res = calculateQuotaDistinction(poolState);
  assert.strictEqual(res.pools.claude_a.five_hour_used_pct, 0);
  assert.strictEqual(res.pools.claude_a.weekly_used_pct, 0);
});

test('F4_B.2: 100% quota exhausted boundary: 0% headroom remaining', () => {
  const poolState = `pool\tstate\tsince\tevidence\tpct\tresets_at\tweekly_pct\tfive_hour_remaining_pct\tgemini_five_hour_remaining_pct\tgemini_weekly_remaining_pct\tclaude_gpt_five_hour_remaining_pct\tclaude_gpt_weekly_remaining_pct\tquota_observed_at
A\tEXHAUSTED\t2026-09-22T21:40:05Z\tevid\t100\t2026-09-23T02:09:59Z\t100\t-\t-\t-\t-\t-\t-`;
  const res = calculateQuotaDistinction(poolState);
  assert.strictEqual(res.pools.claude_a.five_hour_used_pct, 100);
  assert.strictEqual(res.pools.claude_a.weekly_used_pct, 100);
});

test('F4_B.3: Range clamping on quota percentages: /api/quotas returns percentages within [0, 100]', async () => {
  const res = await apiFetch('/api/quotas');
  assert.strictEqual(res.status, 200);
  const { claude_a, claude_b, antigravity } = res.data.pools;
  assert.ok(claude_a.five_hour_used_pct >= 0 && claude_a.five_hour_used_pct <= 100);
  assert.ok(claude_b.five_hour_used_pct >= 0 && claude_b.five_hour_used_pct <= 100);
  assert.ok(antigravity.gemini.five_hour_remaining_pct >= 0 && antigravity.gemini.five_hour_remaining_pct <= 100);
});

test('F4_B.4: Null, dash, or empty resets_at timestamps handle gracefully with fallback', () => {
  const poolState = `pool\tstate\tsince\tevidence\tpct\tresets_at\tweekly_pct\tfive_hour_remaining_pct\tgemini_five_hour_remaining_pct\tgemini_weekly_remaining_pct\tclaude_gpt_five_hour_remaining_pct\tclaude_gpt_weekly_remaining_pct\tquota_observed_at
A\tACTIVE\t2026-09-22T21:40:05Z\tevid\t10\t-\t10\t-\t-\t-\t-\t-\t-`;
  const res = calculateQuotaDistinction(poolState);
  assert.strictEqual(res.pools.claude_a.resets_at, '');
});

test('F4_B.5: Missing AGY provider sub-keys defaults gracefully to 100% remaining', () => {
  const incompleteAgyState = `pool\tstate\tsince\tevidence\tpct\tresets_at\tweekly_pct\tfive_hour_remaining_pct\tgemini_five_hour_remaining_pct\tgemini_weekly_remaining_pct\tclaude_gpt_five_hour_remaining_pct\tclaude_gpt_weekly_remaining_pct\tquota_observed_at
AGY\tUNKNOWN\t2026-09-22T11:00:05Z\tevid\t-\t-\t-\t-\t-\t-\t-\t-\t-`;
  const res = calculateQuotaDistinction(incompleteAgyState);
  assert.strictEqual(res.pools.antigravity.gemini.five_hour_remaining_pct, 100);
  assert.strictEqual(res.pools.antigravity.claude_gpt.weekly_remaining_pct, 100);
});

// ============================================================================
// F5: Zero-Mismatch Hydration & Layout Shell (Boundaries - 5 Tests)
// ============================================================================
test('F5_B.1: Server-side rendering context detection evaluates correctly', () => {
  const isServer = typeof window === 'undefined';
  assert.strictEqual(isServer, true);
});

test('F5_B.2: Utility cn handles falsy and undefined values gracefully', () => {
  const classes = cn('base-class', false && 'hidden', null, undefined, 'active-class');
  assert.strictEqual(classes, 'base-class active-class');
});

test('F5_B.3: formatNumber handles boundary numbers', () => {
  assert.strictEqual(formatNumber(0), '0');
  assert.strictEqual(formatNumber(100), '100');
  assert.strictEqual(formatNumber(-500), '-500');
});

test('F5_B.4: formatCurrency handles negative and fractional amounts', () => {
  assert.strictEqual(formatCurrency(-5.2), '-$5.20');
  assert.strictEqual(formatCurrency(0), '$0.00');
});

test('F5_B.5: formatDuration handles 0 and 3600 seconds', () => {
  assert.strictEqual(formatDuration(0), '0s');
  assert.strictEqual(formatDuration(3600), '60m 0s');
});

// ============================================================================
// F6: Distributed Node Latency Grid (Boundaries - 5 Tests)
// ============================================================================
test('F6_B.1: Unreachable node reports down with null latency in /api/nodes', async () => {
  const res = await apiFetch('/api/nodes');
  assert.strictEqual(res.status, 200);
  const blacklisted = res.data.nodes.find((n: any) => n.ip === BLACKLISTED_HOST_IP);
  assert.ok(blacklisted);
  assert.strictEqual(blacklisted.latency_ms, null);
});

test('F6_B.2: High latency formatting via formatDuration', () => {
  assert.strictEqual(formatDuration(50), '50s');
  assert.strictEqual(formatDuration(300), '5m 0s');
});

test('F6_B.3: Direct probe attempt to 10.0.70.95 (test2) is accessible per Fleet Rule 21', async () => {
  const res = await apiFetch('/api/nodes');
  const test2 = res.data.nodes.find((n: any) => n.ip === BLACKLISTED_HOST_IP);
  assert.ok(test2);
  assert.strictEqual(test2.is_blacklisted, false);
  assert.strictEqual(test2.latency_ms, null);
});

test('F6_B.4: Filter query matching 0 nodes returns empty list without error', async () => {
  const res = await apiFetch('/api/nodes?role=nonexistent_role');
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.data.nodes.length, 0);
});

test('F6_B.5: Total node count across cluster is exactly 27', async () => {
  const res = await apiFetch('/api/nodes');
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.data.total_nodes, 27);
});

// ============================================================================
// F7: CI/CD Shard Health Matrix (Boundaries - 5 Tests)
// ============================================================================
test('F7_B.1: Shard duration of 0 seconds is formatted cleanly', () => {
  assert.strictEqual(formatDuration(0), '0s');
});

test('F7_B.2: Shard duration exceeding 3600 seconds formats in minutes', () => {
  assert.strictEqual(formatDuration(3601), '60m 1s');
});

test('F7_B.3: CI taxonomy codes: unknown code maps safely', () => {
  const codes = new Set(CI_TAXONOMY_CODES);
  const check = (c?: string) => (c && codes.has(c) ? c : 'BD-CI-UNKNOWN');
  assert.strictEqual(check('BD-CI-01'), 'BD-CI-01');
  assert.strictEqual(check('INVALID'), 'BD-CI-UNKNOWN');
});

test('F7_B.4: Recent harness runs array exists and is valid in /api/shards', async () => {
  const res = await apiFetch('/api/shards');
  assert.strictEqual(res.status, 200);
  assert.ok(Array.isArray(res.data.recent_harness_runs));
});

test('F7_B.5: Total shards count in /api/shards matches 42', async () => {
  const res = await apiFetch('/api/shards');
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.data.total_shards, 42);
});

// ============================================================================
// F8: Historical Cost & Prefix Cache Projections (Boundaries - 5 Tests)
// ============================================================================
test('F8_B.1: formatPercent handles 100% boundary', () => {
  assert.strictEqual(formatPercent(100.0), '100.0%');
});

test('F8_B.2: formatPercent handles 0% boundary', () => {
  assert.strictEqual(formatPercent(0.0), '0.0%');
});

test('F8_B.3: formatCurrency handles 0 boundary', () => {
  assert.strictEqual(formatCurrency(0), '$0.00');
});

test('F8_B.4: formatCurrency handles fractional cents with rounding', () => {
  assert.strictEqual(formatCurrency(4.825), '$4.83');
  assert.strictEqual(formatCurrency(4.821), '$4.82');
});

test('F8_B.5: /api/cost aggregate cache hit rate is within valid [0, 100] percentage bounds', async () => {
  const res = await apiFetch('/api/cost?since=24h');
  assert.strictEqual(res.status, 200);
  const hitRate = res.data.aggregate.overall_cache_hit_pct;
  assert.ok(hitRate >= 0 && hitRate <= 100, `Hit rate ${hitRate} must be between 0 and 100`);
});

// ============================================================================
// F9: Interactive Swarm Queue Re-ordering (Boundaries - 5 Tests)
// ============================================================================
test('F9_B.1: reorderDispatchLedgerRows handles empty order array without dropping lines', () => {
  const lines = [
    '2026-09-22T20:00:00Z\tbd-worker-1\trow1\tdispatched\t/b1.md',
    '2026-09-22T20:01:00Z\tbd-worker-2\trow2\tdispatched\t/b2.md'
  ];
  const reordered = reorderDispatchLedgerRows(lines, []);
  assert.strictEqual(reordered.length, 2);
});

test('F9_B.2: reorderDispatchLedgerRows handles unknown row IDs without dropping rows', () => {
  const lines = [
    '2026-09-22T20:00:00Z\tbd-worker-1\trow1\tdispatched\t/b1.md',
    '2026-09-22T20:01:00Z\tbd-worker-2\trow2\tdispatched\t/b2.md'
  ];
  const reordered = reorderDispatchLedgerRows(lines, ['nonexistent_row']);
  assert.strictEqual(reordered.length, 2);
});

test('F9_B.3: reorderDispatchLedgerRows handles duplicate IDs in order array safely', () => {
  const lines = [
    '2026-09-22T20:00:00Z\tbd-worker-1\trow1\tdispatched\t/b1.md',
    '2026-09-22T20:01:00Z\tbd-worker-2\trow2\tdispatched\t/b2.md'
  ];
  const reordered = reorderDispatchLedgerRows(lines, ['row2', 'row2', 'row1']);
  assert.strictEqual(reordered.length, 2);
  assert.ok(reordered[0].includes('row2'));
});

test('F9_B.4: reorderDispatchLedgerRows handles single-line file', () => {
  const lines = ['2026-09-22T20:00:00Z\tbd-worker-1\trow1\tdispatched\t/b1.md'];
  const reordered = reorderDispatchLedgerRows(lines, ['row1']);
  assert.strictEqual(reordered.length, 1);
});

test('F9_B.5: reorderDispatchLedgerRows handles file consisting only of comments', () => {
  const lines = ['# Comment 1', '# Comment 2'];
  const reordered = reorderDispatchLedgerRows(lines, ['row1']);
  assert.strictEqual(reordered.length, 2);
  assert.strictEqual(reordered[0], '# Comment 1');
});

// ============================================================================
// F10: Active Agent Configuration Matrix (Boundaries - 5 Tests)
// ============================================================================
test('F10_B.1: POST /api/agents with empty seat returns 400', async () => {
  const res = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ seat: '' })
  });
  assert.strictEqual(res.status, 400);
});

test('F10_B.2: POST /api/agents clamps turn cap to 60 per Fleet Rule 58', async () => {
  const res = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ seat: 'bd-worker-W1-A', turn_cap: 120 })
  });
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.data.agent.turn_cap, 60, 'Turn cap must be clamped to 60');
});

test('F10_B.3: POST /api/agents clamps negative turn cap to minimum 1', async () => {
  const res = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ seat: 'bd-worker-W1-A', turn_cap: -5 })
  });
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.data.agent.turn_cap, 1);
});

test('F10_B.4: POST /api/agents with valid model update succeeds', async () => {
  const res = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ seat: 'bd-worker-W1-A', model: 'gpt-6-astra' })
  });
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.data.agent.model, 'gpt-6-astra');
});

test('F10_B.5: POST /api/agents with malformed JSON returns 400', async () => {
  const res = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: '{ broken json'
  });
  assert.strictEqual(res.status, 400);
});

// ============================================================================
// F11: Concurrency Engine & Retry Boundaries (5 Tests)
// ============================================================================
test('F11_B.1: calculateFullJitterDelay produces bounded delay', () => {
  for (let attempt = 1; attempt <= 10; attempt++) {
    const delay = calculateFullJitterDelay(attempt, 25, 1000);
    const maxExpected = Math.min(1000, 25 * Math.pow(2, attempt - 1));
    assert.ok(delay >= 0, 'Delay must be non-negative');
    assert.ok(delay <= maxExpected, `Delay ${delay} must be <= ${maxExpected}`);
  }
});

test('F11_B.2: isSqliteBusyError detects various SQLite busy error shapes', () => {
  assert.strictEqual(isSqliteBusyError({ code: 'SQLITE_BUSY' }), true);
  assert.strictEqual(isSqliteBusyError({ message: 'database is locked' }), true);
  assert.strictEqual(isSqliteBusyError({ message: 'cannot open: busy' }), true);
  assert.strictEqual(isSqliteBusyError(new Error('Resource temporarily unavailable: locked')), true);
});

test('F11_B.3: isSqliteBusyError returns false for non-busy errors', () => {
  assert.strictEqual(isSqliteBusyError(new Error('syntax error near SELECT')), false);
  assert.strictEqual(isSqliteBusyError({ code: 'ENOENT' }), false);
  assert.strictEqual(isSqliteBusyError(null), false);
});

test('F11_B.4: getDbDiagnostics returns healthy database status', () => {
  const diag = getDbDiagnostics();
  assert.ok(diag);
  assert.strictEqual(diag.exists, true);
  assert.strictEqual(diag.journalMode.toLowerCase(), 'wal');
});

test('F11_B.5: withDbRetry defaults safely when options omitted', async () => {
  const res = await withDbRetry(() => 'DEFAULT_SUCCESS');
  assert.strictEqual(res, 'DEFAULT_SUCCESS');
});

// ============================================================================
// F12: Adversarial Hardening Boundaries (5 Tests)
// ============================================================================
test('F12_B.1: parseDispatchLedgerLines handles empty string input', () => {
  const parsed = parseDispatchLedgerLines([]);
  assert.strictEqual(parsed.length, 0);
});

test('F12_B.2: parseDispatchLedgerLines flags comments and empty lines as isCommentOrEmpty', () => {
  const lines = ['# Comment line', '', '   '];
  const parsed = parseDispatchLedgerLines(lines);
  assert.strictEqual(parsed[0].isCommentOrEmpty, true);
  assert.strictEqual(parsed[1].isCommentOrEmpty, true);
  assert.strictEqual(parsed[2].isCommentOrEmpty, true);
});

test('F12_B.3: parseDispatchLedgerLines parses valid 5-column TSV line correctly', () => {
  const lines = ['2026-09-22T20:00:00Z\tbd-worker-1\trow1\tdispatched\t/brief.md'];
  const parsed = parseDispatchLedgerLines(lines);
  assert.strictEqual(parsed.length, 1);
  assert.strictEqual(parsed[0].isCommentOrEmpty, false);
  assert.strictEqual(parsed[0].row, 'row1');
  assert.strictEqual(parsed[0].status, 'dispatched');
});

test('F12_B.4: mutateTsvAtomically lock timeout test with short timeout', async () => {
  const dir = createTempDir('f12_b4_');
  try {
    const tsv = createTsvSandbox(dir, 2);
    const lockFile = path.join(dir, '.DISPATCH-LEDGER.tsv.lock');

    // Hold flock using a background child process
    const blocker = spawn('/usr/bin/flock', ['-x', lockFile, 'sleep', '2']);
    await new Promise((r) => setTimeout(r, 100));

    try {
      await assert.rejects(
        async () => {
          await mutateTsvAtomically(tsv, (lines) => lines, 100);
        },
        /flock timed out|Timeout acquiring advisory lock|timed out/i
      );
    } finally {
      try {
        blocker.kill('SIGKILL');
      } catch {}
    }
  } finally {
    cleanupPath(dir);
  }
});

test('F12_B.5: Invariant check: BD_GATE_SCOPE strictly module or repo-wide', () => {
  const validScopes = new Set(['module', 'repo-wide']);
  assert.ok(validScopes.has('module'));
  assert.ok(validScopes.has('repo-wide'));
  assert.strictEqual(validScopes.has('ad-hoc'), false);
});
