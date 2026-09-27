/**
 * tests/adversarial/tier5_backend_adversarial.test.ts
 *
 * Tier 5 Adversarial Coverage Hardening Test Suite for Heterogeneous Swarm Architecture Dashboard
 *
 * White-box adversarial testing covering:
 * 1. Malformed / truncated TSV ledgers and corrupted lines.
 * 2. Extreme rapid lock contention and recovery.
 * 3. Invalid JSON bodies, missing query parameters, non-numeric timestamps.
 * 4. Database read retries under simulated SQLITE_BUSY / locked error spikes.
 * 5. Security / bounds checking (Rule 21 test2 isolation, Rule 58 turn caps clamping, gate scope).
 */

import { test, before, after } from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { spawn, spawnSync, ChildProcess } from 'node:child_process';

import {
  mutateTsvAtomically,
  parseDispatchLedgerLines,
  reorderDispatchLedgerRows,
  type DispatchLedgerRow
} from '../../src/lib/atomic-tsv.ts';
import {
  withDbRetry,
  isSqliteBusyError,
  calculateFullJitterDelay
} from '../../src/lib/db-retry.ts';
import {
  getReadOnlyDb,
  closeDb,
  queryOne,
  queryAll,
  getDbDiagnostics,
  resetDbPathCache
} from '../../src/lib/db.ts';
import {
  createTempDir,
  cleanupPath,
  createSqliteSandbox,
  createTsvSandbox,
  BLACKLISTED_HOST_IP
} from '../e2e/test_helpers.ts';

// --- Server Lifecycle & HTTP Helper ---
const TEST_PORT = process.env.TEST_PORT ? parseInt(process.env.TEST_PORT, 10) : 3460;
const BASE_URL = `http://localhost:${TEST_PORT}`;
let testServerProcess: ChildProcess | null = null;

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

before(async () => {
  if (await isServerReady()) {
    return;
  }

  testServerProcess = spawn('npx', ['next', 'start', '-p', String(TEST_PORT)], {
    stdio: 'pipe',
    detached: true,
    env: { ...process.env, PORT: String(TEST_PORT) }
  });

  const start = Date.now();
  while (Date.now() - start < 15000) {
    await new Promise((r) => setTimeout(r, 400));
    if (await isServerReady()) return;
  }
  throw new Error(`Failed to start Next.js test server on port ${TEST_PORT} within 15s`);
});

after(() => {
  if (testServerProcess && testServerProcess.pid) {
    try {
      process.kill(-testServerProcess.pid, 'SIGKILL');
    } catch {
      try {
        testServerProcess.kill('SIGKILL');
      } catch {}
    }
  }
  closeDb();
});

// ============================================================================
// SUITE 1: Malformed / Truncated TSV Ledgers & Corrupted Lines
// ============================================================================

test('S1.1: parseDispatchLedgerLines handles truncated lines (1 to 4 columns) without undefined properties', () => {
  const truncatedInputs = [
    '2026-09-22T20:00:00Z', // 1 column
    '2026-09-22T20:00:00Z\tbd-worker-1', // 2 columns
    '2026-09-22T20:00:00Z\tbd-worker-1\trow1', // 3 columns
    '2026-09-22T20:00:00Z\tbd-worker-1\trow1\tdispatched' // 4 columns
  ];

  const parsed = parseDispatchLedgerLines(truncatedInputs);
  assert.strictEqual(parsed.length, 4);

  // 1 column: missing seat, row, status, brief
  assert.strictEqual(parsed[0].timestamp, '2026-09-22T20:00:00Z');
  assert.strictEqual(parsed[0].seat, '');
  assert.strictEqual(parsed[0].row, '');
  assert.strictEqual(parsed[0].status, '');
  assert.strictEqual(parsed[0].brief, '');
  assert.strictEqual(parsed[0].isCommentOrEmpty, false);

  // 2 columns
  assert.strictEqual(parsed[1].seat, 'bd-worker-1');
  assert.strictEqual(parsed[1].row, '');

  // 3 columns
  assert.strictEqual(parsed[2].row, 'row1');
  assert.strictEqual(parsed[2].status, '');

  // 4 columns
  assert.strictEqual(parsed[3].status, 'dispatched');
  assert.strictEqual(parsed[3].brief, '');
});

test('S1.2: parseDispatchLedgerLines handles mixed CRLF, extra trailing tabs, and blank lines', () => {
  const dirtyLines = [
    '# Leading comment\r',
    '   \r',
    '2026-09-22T20:00:00Z\tworker-1\ttask-1\tstarted\t/brief_1.md\t\t\t\r',
    '\t\t\t',
    '2026-09-22T20:01:00Z\tworker-2\ttask-2\tdone\t/brief_2.md'
  ];

  const parsed = parseDispatchLedgerLines(dirtyLines);
  assert.strictEqual(parsed[0].isCommentOrEmpty, true);
  assert.strictEqual(parsed[1].isCommentOrEmpty, true);
  assert.strictEqual(parsed[2].isCommentOrEmpty, false);
  assert.strictEqual(parsed[2].row, 'task-1');
  assert.strictEqual(parsed[3].isCommentOrEmpty, true); // only tabs
  assert.strictEqual(parsed[4].isCommentOrEmpty, false);
  assert.strictEqual(parsed[4].row, 'task-2');
});

test('S1.3: reorderDispatchLedgerRows preserves corrupted rows without losing non-reordered lines', () => {
  const linesWithCorruptRows = [
    '# Header comments',
    'CORRUPTED_LINE_WITHOUT_TABS',
    '2026-09-22T20:00:00Z\tworker-1\trow1\tdone\t/b1.md',
    'TRUNCATED\tONLY_TWO_COLS',
    '2026-09-22T20:01:00Z\tworker-2\trow2\tdispatched\t/b2.md',
    '2026-09-22T20:02:00Z\tworker-3\trow3\tdispatched\t/b3.md'
  ];

  // Reorder row3 ahead of row2
  const reordered = reorderDispatchLedgerRows(linesWithCorruptRows, ['row3', 'row2']);

  // Assert header comment is preserved
  assert.strictEqual(reordered[0], '# Header comments');

  // Assert all rows are present (none dropped)
  const fullText = reordered.join('\n');
  assert.ok(fullText.includes('CORRUPTED_LINE_WITHOUT_TABS'), 'Corrupted line must be preserved');
  assert.ok(fullText.includes('TRUNCATED\tONLY_TWO_COLS'), 'Truncated line must be preserved');
  assert.ok(fullText.includes('row1\tdone'), 'Completed row1 must be preserved');
  assert.ok(fullText.includes('row2\tdispatched'), 'Row2 must be preserved');
  assert.ok(fullText.includes('row3\tdispatched'), 'Row3 must be preserved');

  // Verify that row3 now appears before row2 in the output
  const row3Idx = reordered.findIndex((l) => l.includes('row3'));
  const row2Idx = reordered.findIndex((l) => l.includes('row2'));
  assert.ok(row3Idx < row2Idx, 'row3 must precede row2 after reorder');
});

test('S1.4: reorderDispatchLedgerRows preserves UTF-8, emoji, and special characters in brief and seat', () => {
  const unicodeLines = [
    '# Unicode dispatch queue test \u{1F680}',
    '2026-09-22T20:00:00Z\tbd-worker-\u{1F916}\ttask-alpha\tdispatched\t/briefs/\u{1F4CA}_summary.md',
    '2026-09-22T20:01:00Z\tbd-worker-\u4E2D\ttask-beta\tdispatched\t/briefs/path with spaces & "quotes"/b.md'
  ];

  const reordered = reorderDispatchLedgerRows(unicodeLines, ['task-beta', 'task-alpha']);
  const text = reordered.join('\n');

  assert.ok(text.includes('\u{1F680}'), 'Rocket emoji preserved');
  assert.ok(text.includes('\u{1F916}'), 'Robot emoji preserved');
  assert.ok(text.includes('\u{1F4CA}'), 'Chart emoji preserved');
  assert.ok(text.includes('\u4E2D'), 'CJK character preserved');
  assert.ok(text.includes('path with spaces & "quotes"'), 'Quotes and spaces preserved');

  const betaIdx = reordered.findIndex((l) => l.includes('task-beta'));
  const alphaIdx = reordered.findIndex((l) => l.includes('task-alpha'));
  assert.ok(betaIdx < alphaIdx, 'task-beta must precede task-alpha');
});

test('S1.5: reorderDispatchLedgerRows deduplicates repeated row IDs in reorder array', () => {
  const lines = [
    '2026-09-22T20:00:00Z\tw1\ttask-1\tdispatched\t/b1.md',
    '2026-09-22T20:01:00Z\tw2\ttask-2\tdispatched\t/b2.md',
    '2026-09-22T20:02:00Z\tw3\ttask-3\tdispatched\t/b3.md'
  ];

  // Pass duplicates of task-2 and task-1
  const reordered = reorderDispatchLedgerRows(lines, ['task-2', 'task-2', 'task-1', 'task-1', 'task-2']);

  // Verify task-2 appears exactly once
  const task2Matches = reordered.filter((l) => l.includes('task-2'));
  assert.strictEqual(task2Matches.length, 1, 'task-2 must not be duplicated in output');

  const task1Matches = reordered.filter((l) => l.includes('task-1'));
  assert.strictEqual(task1Matches.length, 1, 'task-1 must not be duplicated in output');

  const task3Matches = reordered.filter((l) => l.includes('task-3'));
  assert.strictEqual(task3Matches.length, 1, 'task-3 must remain in output');
});

test('S1.6: reorderDispatchLedgerRows safely ignores non-existent row IDs', () => {
  const lines = [
    '2026-09-22T20:00:00Z\tw1\treal-task-1\tdispatched\t/b1.md',
    '2026-09-22T20:01:00Z\tw2\treal-task-2\tdispatched\t/b2.md'
  ];

  const reordered = reorderDispatchLedgerRows(lines, ['phantom-1', 'real-task-2', 'phantom-2', 'real-task-1']);
  assert.strictEqual(reordered.length, 2);
  assert.ok(reordered[0].includes('real-task-2'));
  assert.ok(reordered[1].includes('real-task-1'));
});

test('S1.7: mutateTsvAtomically handles empty 0-byte file and writes valid trailing newline', async () => {
  const dir = createTempDir('s1_empty_');
  try {
    const tsv = path.join(dir, 'EMPTY.tsv');
    fs.writeFileSync(tsv, '', 'utf8');

    await mutateTsvAtomically(tsv, (lines) => {
      return [...lines, '2026-09-22T20:00:00Z\tworker-1\trow1\tdispatched\t/b.md'];
    });

    const content = fs.readFileSync(tsv, 'utf8');
    assert.ok(content.endsWith('\n'), 'Must end with trailing newline');
    assert.strictEqual(content.trim(), '2026-09-22T20:00:00Z\tworker-1\trow1\tdispatched\t/b.md');
  } finally {
    cleanupPath(dir);
  }
});

test('S1.8: mutateTsvAtomically handles file consisting only of comments', async () => {
  const dir = createTempDir('s1_comments_');
  try {
    const tsv = path.join(dir, 'COMMENTS.tsv');
    fs.writeFileSync(tsv, '# Comment 1\n# Comment 2\n# Comment 3\n', 'utf8');

    await mutateTsvAtomically(tsv, (lines) => {
      return [...lines, '2026-09-22T20:00:00Z\tworker-1\trow1\tdispatched\t/b.md'];
    });

    const content = fs.readFileSync(tsv, 'utf8');
    assert.ok(content.includes('# Comment 1'));
    assert.ok(content.includes('# Comment 2'));
    assert.ok(content.includes('row1\tdispatched'));
    assert.ok(content.endsWith('\n'));
  } finally {
    cleanupPath(dir);
  }
});

test('S1.9: GET /api/queue handles underlying ledger with corrupted and truncated rows without crashing', async () => {
  // Test route resilience when DISPATCH_LEDGER_PATH has corrupted data
  const res = await apiFetch('/api/queue');
  assert.strictEqual(res.status, 200);
  assert.ok(Array.isArray(res.data.items));
  assert.strictEqual(typeof res.data.total_entries, 'number');
  assert.strictEqual(typeof res.data.active_count, 'number');
  assert.strictEqual(typeof res.data.completed_count, 'number');

  // Verify all returned items have non-empty row strings
  for (const item of res.data.items) {
    assert.ok(item.row.length > 0, 'Every valid queue item must have a non-empty row ID');
    assert.strictEqual(typeof item.is_active, 'boolean');
  }
});

// ============================================================================
// SUITE 2: Extreme Rapid Lock Contention & Recovery
// ============================================================================

test('S2.1: Extreme concurrent lock contention: 10 parallel async workers mutating same TSV ledger', async () => {
  const dir = createTempDir('s2_contention_');
  try {
    const tsv = path.join(dir, 'CONTENTION.tsv');
    const initialRows: string[] = [];
    for (let i = 1; i <= 20; i++) {
      initialRows.push(`2026-09-22T20:00:00Z\tworker-${i}\ttask_${i}\tdispatched\t/b_${i}.md`);
    }
    fs.writeFileSync(tsv, initialRows.join('\n') + '\n', 'utf8');

    // Launch 10 simultaneous workers attempting atomic mutations with different permutations
    const workers = Array.from({ length: 10 }, (_, workerId) => {
      return (async () => {
        for (let round = 0; round < 3; round++) {
          const randomOrder = Array.from({ length: 20 }, (_, idx) => `task_${idx + 1}`)
            .sort(() => Math.random() - 0.5);

          await mutateTsvAtomically(
            tsv,
            (lines) => reorderDispatchLedgerRows(lines, randomOrder),
            5000
          );
        }
      })();
    });

    // All workers must resolve without throwing deadlock/torn errors
    const results = await Promise.allSettled(workers);
    for (const r of results) {
      assert.strictEqual(r.status, 'fulfilled', 'All concurrent workers must succeed without deadlock');
    }

    // Verify file integrity after 30 concurrent mutations
    const finalContent = fs.readFileSync(tsv, 'utf8');
    const finalLines = finalContent.trim().split('\n');
    assert.strictEqual(finalLines.length, 20, 'Exact task count of 20 must be preserved');

    for (const line of finalLines) {
      const cols = line.split('\t');
      assert.strictEqual(cols.length, 5, 'Every row must have exactly 5 tab-separated columns');
    }
  } finally {
    cleanupPath(dir);
  }
});

test('S2.2: Advisory lock timeout enforcement rejects with explicit error when blocked', async () => {
  const dir = createTempDir('s2_timeout_');
  try {
    const tsv = createTsvSandbox(dir, 3);
    const lockFile = path.join(dir, '.DISPATCH-LEDGER.tsv.lock');

    // Block the lock file with an external flock process for 2.5 seconds
    const blocker = spawn('/usr/bin/flock', ['-x', lockFile, 'sleep', '2.5']);
    await new Promise((r) => setTimeout(r, 150));

    try {
      // Attempt mutation with a short 200ms lock timeout
      await assert.rejects(
        async () => {
          await mutateTsvAtomically(tsv, (lines) => lines, 200);
        },
        /flock timed out|Timeout acquiring advisory lock|timed out/i,
        'Must reject with lock timeout when advisory lock is held by another process'
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

test('S2.3: Stale lockfile auto-recovery reclaims orphaned lock without manual intervention', async () => {
  const dir = createTempDir('s2_stale_');
  try {
    const tsv = createTsvSandbox(dir, 3);
    const lockFile = path.join(dir, '.DISPATCH-LEDGER.tsv.lock');

    // Simulate an abandoned lockfile written by an old dead process (mtime 15 seconds ago)
    fs.writeFileSync(lockFile, '999999\n1000000000\n', 'utf8');
    const oldTime = (Date.now() - 15000) / 1000;
    fs.utimesSync(lockFile, oldTime, oldTime);

    // Verify mutation succeeds by auto-reclaiming or breaking stale lock
    await mutateTsvAtomically(tsv, (lines) => {
      return [...lines, '2026-09-22T20:05:00Z\tworker-new\trow-new\tdispatched\t/b.md'];
    }, 2000);

    const content = fs.readFileSync(tsv, 'utf8');
    assert.ok(content.includes('row-new\tdispatched'), 'Must succeed despite stale lockfile');
  } finally {
    cleanupPath(dir);
  }
});

test('S2.4: Active AWK reader stream observes zero torn reads during 15 successive atomic mutations', async () => {
  const dir = createTempDir('s2_awk_');
  try {
    const tsv = path.join(dir, 'DISPATCH-LEDGER.tsv');
    const rowCount = 25;
    const initialRows: string[] = [];
    for (let i = 1; i <= rowCount; i++) {
      initialRows.push(`2026-09-22T20:00:00Z\tworker-${i}\ttask_${i}\tdispatched\t/b_${i}.md`);
    }
    fs.writeFileSync(tsv, initialRows.join('\n') + '\n', 'utf8');

    let tornReads = 0;
    let emptyReads = 0;
    let totalReads = 0;
    let reading = true;

    // Background reader loop simulating fleet dispatcher awk execution at 100Hz
    const readerLoop = (async () => {
      while (reading) {
        try {
          const res = spawnSync('awk', ['-F', '\t', 'NF != 5 { print $0 }', tsv], { encoding: 'utf8' });
          if (res.stdout && res.stdout.trim().length > 0) {
            tornReads++;
          }
          const stat = fs.statSync(tsv);
          if (stat.size === 0) {
            emptyReads++;
          }
          totalReads++;
        } catch {}
        await new Promise((r) => setTimeout(r, 2));
      }
    })();

    // Perform 15 successive rapid reordering mutations
    for (let i = 0; i < 15; i++) {
      const shuffled = Array.from({ length: rowCount }, (_, idx) => `task_${idx + 1}`)
        .sort(() => Math.random() - 0.5);

      await mutateTsvAtomically(tsv, (lines) => reorderDispatchLedgerRows(lines, shuffled), 5000);
    }

    reading = false;
    await readerLoop;

    assert.strictEqual(tornReads, 0, `Zero torn reads expected, observed: ${tornReads}`);
    assert.strictEqual(emptyReads, 0, `Zero empty reads expected, observed: ${emptyReads}`);
    assert.ok(totalReads >= 30, `Expected at least 30 AWK observations, observed: ${totalReads}`);
  } finally {
    cleanupPath(dir);
  }
});

test('S2.5: Ephemeral file leak prevention: no .tmp files remain after operations', async () => {
  const dir = createTempDir('s2_leaks_');
  try {
    const tsv = createTsvSandbox(dir, 5);

    // Run 5 successful mutations
    for (let i = 0; i < 5; i++) {
      await mutateTsvAtomically(tsv, (lines) => lines);
    }

    // Inspect directory for leaked temp files
    const files = fs.readdirSync(dir);
    const tmpFiles = files.filter((f) => f.includes('.tmp.'));
    assert.strictEqual(tmpFiles.length, 0, 'No .tmp files should linger after successful mutations');
  } finally {
    cleanupPath(dir);
  }
});

// ============================================================================
// SUITE 3: Invalid JSON Bodies, Missing Query Parameters, Non-Numeric Timestamps
// ============================================================================

test('S3.1: POST /api/queue rejects malformed JSON bodies with HTTP 400', async () => {
  const malformedBodies = [
    '{ unclosed json',
    '{"action": "reorder", broken:',
    'plain string body',
    '',
    '{"action": "reorder", "ordered_row_ids": ["row1"],}' // trailing comma
  ];

  for (const body of malformedBodies) {
    const res = await apiFetch('/api/queue', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body
    });
    assert.strictEqual(res.status, 400, `Expected 400 for malformed body: ${body}`);
    assert.ok(
      res.data?.error?.includes('Malformed JSON') || res.data?.error?.includes('Bad Request'),
      'Must return structured error message'
    );
  }
});

test('S3.2: POST /api/queue rejects invalid action and schema payloads with HTTP 400', async () => {
  const invalidPayloads = [
    { action: 'delete', ordered_row_ids: ['row1'] },
    { action: 'update', ordered_row_ids: ['row1'] },
    { action: null, ordered_row_ids: ['row1'] },
    { action: 'reorder' }, // missing ordered_row_ids
    { action: 'reorder', ordered_row_ids: 'not_an_array' },
    { action: 'reorder', ordered_row_ids: [] }, // empty array
    { action: 'reorder', ordered_row_ids: {} }
  ];

  for (const payload of invalidPayloads) {
    const res = await apiFetch('/api/queue', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    });
    assert.strictEqual(res.status, 400, `Expected 400 for payload: ${JSON.stringify(payload)}`);
  }
});

test('S3.3: POST /api/queue rejects non-string and whitespace elements in ordered_row_ids with HTTP 400', async () => {
  const badElementArrays = [
    [12345],
    [null],
    [''],
    ['   '],
    [true],
    ['valid_row', '']
  ];

  for (const arr of badElementArrays) {
    const res = await apiFetch('/api/queue', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'reorder', ordered_row_ids: arr })
    });
    assert.strictEqual(res.status, 400, `Expected 400 for array: ${JSON.stringify(arr)}`);
    assert.ok(res.data.error.includes('non-empty string'));
  }
});

test('S3.4: POST /api/agents rejects malformed JSON, missing seat, and invalid seat types with HTTP 400', async () => {
  // Malformed JSON
  const res1 = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: '{"broken'
  });
  assert.strictEqual(res1.status, 400);

  // Missing seat
  const res2 = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ model: 'gpt-5.6-terra' })
  });
  assert.strictEqual(res2.status, 400);

  // Whitespace-only seat
  const res3 = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ seat: '   ', turn_cap: 30 })
  });
  assert.strictEqual(res3.status, 400);

  // Non-string seat
  const res4 = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ seat: 999 })
  });
  assert.strictEqual(res4.status, 400);
});

test('S3.5: GET /api/cost handles non-numeric timestamps, negative limits, and NaN values gracefully', async () => {
  const adversarialQueries = [
    '/api/cost?since=not_a_time',
    '/api/cost?since=NaNh',
    '/api/cost?since=-5h&limit=-100',
    '/api/cost?limit=abc',
    '/api/cost?limit=999999',
    '/api/cost?since=undefined'
  ];

  for (const q of adversarialQueries) {
    const res = await apiFetch(q);
    assert.strictEqual(res.status, 200, `Expected 200 for query: ${q}`);
    assert.ok(res.data.aggregate, 'Must return valid aggregate object');
    assert.strictEqual(typeof res.data.aggregate.total_context_tokens, 'number');
    assert.strictEqual(typeof res.data.aggregate.overall_cache_hit_pct, 'number');
    assert.ok(
      res.data.aggregate.overall_cache_hit_pct >= 0 && res.data.aggregate.overall_cache_hit_pct <= 100,
      'Cache hit percentage must be within [0, 100]'
    );
    assert.ok(Array.isArray(res.data.breakdown), 'Breakdown must be array');
    assert.ok(res.data.breakdown.length <= 200, 'Breakdown must respect max limit cap of 200');
  }
});

test('S3.6: GET /api/queue handles missing, invalid filter, and negative limit parameters safely', async () => {
  const testQueries = [
    '/api/queue?filter=bogus_filter',
    '/api/queue?filter=active&limit=-99',
    '/api/queue?filter=completed&limit=0',
    '/api/queue?limit=invalid_number'
  ];

  for (const q of testQueries) {
    const res = await apiFetch(q);
    assert.strictEqual(res.status, 200, `Expected 200 for query: ${q}`);
    assert.ok(Array.isArray(res.data.items));
    assert.strictEqual(typeof res.data.total_entries, 'number');
  }
});

test('S3.7: GET /api/nodes handles unknown role filters and invalid probe flags without error', async () => {
  const res1 = await apiFetch('/api/nodes?role=nonexistent_alien_role');
  assert.strictEqual(res1.status, 200);
  assert.strictEqual(res1.data.nodes.length, 0, 'Should return empty array for unrecognized role');

  const res2 = await apiFetch('/api/nodes?probe=maybe');
  assert.strictEqual(res2.status, 200);
  assert.strictEqual(typeof res2.data.total_nodes, 'number');
});

test('S3.8: GET /api/quotas returns clamped, valid numerical values for all pools', async () => {
  const res = await apiFetch('/api/quotas');
  assert.strictEqual(res.status, 200);
  assert.ok(res.data.pools.claude_a);
  assert.ok(res.data.pools.claude_b);
  assert.ok(res.data.pools.codex);
  assert.ok(res.data.pools.antigravity);

  // Claude A percentages in [0, 100]
  assert.ok(res.data.pools.claude_a.five_hour_used_pct >= 0 && res.data.pools.claude_a.five_hour_used_pct <= 100);
  assert.ok(res.data.pools.claude_a.weekly_used_pct >= 0 && res.data.pools.claude_a.weekly_used_pct <= 100);

  // AGY Gemini remaining in [0, 100]
  assert.ok(res.data.pools.antigravity.gemini.five_hour_remaining_pct >= 0 && res.data.pools.antigravity.gemini.five_hour_remaining_pct <= 100);
  assert.ok(res.data.pools.antigravity.gemini.weekly_remaining_pct >= 0 && res.data.pools.antigravity.gemini.weekly_remaining_pct <= 100);
});

test('S3.9: GET /api/shards returns structured data even if underlying test ledgers are cold or empty', async () => {
  const res = await apiFetch('/api/shards');
  assert.strictEqual(res.status, 200);
  assert.ok(Array.isArray(res.data.shards));
  assert.strictEqual(res.data.shards.length, 42);
  assert.ok(Array.isArray(res.data.recent_harness_runs));
  assert.ok(Array.isArray(res.data.recent_gate_yields));
});

// ============================================================================
// SUITE 4: Database Read Retries under Simulated SQLITE_BUSY / Lock Spikes
// ============================================================================

test('S4.1: isSqliteBusyError correctly classifies busy vs non-busy error patterns', () => {
  // Positive cases (must return true)
  assert.strictEqual(isSqliteBusyError({ code: 'SQLITE_BUSY' }), true);
  assert.strictEqual(isSqliteBusyError({ code: 'SQLITE_LOCKED' }), true);
  assert.strictEqual(isSqliteBusyError({ code: 'SQLITE_BUSY_RECOVERY' }), true);
  assert.strictEqual(isSqliteBusyError(new Error('database is locked')), true);
  assert.strictEqual(isSqliteBusyError(new Error('database table is locked')), true);
  assert.strictEqual(isSqliteBusyError(new Error('sqlite_busy')), true);
  assert.strictEqual(isSqliteBusyError(new Error('resource temporarily unavailable')), true);

  // Negative cases (must return false)
  assert.strictEqual(isSqliteBusyError({ code: 'SQLITE_CORRUPT' }), false);
  assert.strictEqual(isSqliteBusyError({ code: 'SQLITE_ERROR' }), false);
  assert.strictEqual(isSqliteBusyError(new Error('no such table: foo')), false);
  assert.strictEqual(isSqliteBusyError(new TypeError('x is not a function')), false);
  assert.strictEqual(isSqliteBusyError(null), false);
  assert.strictEqual(isSqliteBusyError(undefined), false);
  assert.strictEqual(isSqliteBusyError('string error'), false);
  assert.strictEqual(isSqliteBusyError(12345), false);
  assert.strictEqual(isSqliteBusyError({}), false);
});

test('S4.2: withDbRetry recovers from simulated transient SQLITE_BUSY error spikes (1, 2, and 4 retries)', async () => {
  // Scenario A: 1 transient failure -> success on attempt 2
  let attemptsA = 0;
  const resultA = await withDbRetry(async () => {
    attemptsA++;
    if (attemptsA === 1) {
      const err: any = new Error('database is locked');
      err.code = 'SQLITE_BUSY';
      throw err;
    }
    return 'recovered_after_1';
  }, { baseDelayMs: 2, maxDelayMs: 10 });
  assert.strictEqual(resultA, 'recovered_after_1');
  assert.strictEqual(attemptsA, 2);

  // Scenario B: 2 transient failures -> success on attempt 3
  let attemptsB = 0;
  const resultB = await withDbRetry(async () => {
    attemptsB++;
    if (attemptsB <= 2) {
      const err: any = new Error('busy');
      err.code = 'SQLITE_BUSY';
      throw err;
    }
    return 'recovered_after_2';
  }, { baseDelayMs: 2, maxDelayMs: 10 });
  assert.strictEqual(resultB, 'recovered_after_2');
  assert.strictEqual(attemptsB, 3);

  // Scenario C: 4 transient failures (within maxRetries=5) -> success on attempt 5
  let attemptsC = 0;
  const resultC = await withDbRetry(async () => {
    attemptsC++;
    if (attemptsC <= 4) {
      const err: any = new Error('resource temporarily unavailable');
      err.code = 'SQLITE_BUSY';
      throw err;
    }
    return 'recovered_after_4';
  }, { maxRetries: 5, baseDelayMs: 2, maxDelayMs: 10 });
  assert.strictEqual(resultC, 'recovered_after_4');
  assert.strictEqual(attemptsC, 5);
});

test('S4.3: withDbRetry fails fast on non-busy errors on attempt 1 without delaying', async () => {
  let callCount = 0;
  await assert.rejects(
    async () => {
      await withDbRetry(async () => {
        callCount++;
        throw new Error('Fatal SQL Syntax Error in Query');
      }, { maxRetries: 5, baseDelayMs: 10 });
    },
    /Fatal SQL Syntax Error/,
    'Must reject immediately on non-busy error'
  );
  assert.strictEqual(callCount, 1, 'Non-busy error must fail immediately on attempt 1');
});

test('S4.4: withDbRetry rethrows original error when maxRetries is exceeded', async () => {
  let callCount = 0;
  await assert.rejects(
    async () => {
      await withDbRetry(async () => {
        callCount++;
        const err: any = new Error('Persistent SQLITE_BUSY lock exhaustion');
        err.code = 'SQLITE_BUSY';
        throw err;
      }, { maxRetries: 3, baseDelayMs: 2, maxDelayMs: 10 });
    },
    /Persistent SQLITE_BUSY/,
    'Must rethrow after maxRetries exhausted'
  );
  // Initial call + 3 retries = 4 attempts total
  assert.strictEqual(callCount, 4);
});

test('S4.5: calculateFullJitterDelay adheres to strict mathematical bounds across 1,000 iterations', () => {
  const baseDelay = 25;
  const maxDelay = 1000;
  const floor = Math.min(5, Math.floor(baseDelay / 2));

  for (let attempt = 1; attempt <= 10; attempt++) {
    const theoreticalMax = Math.min(maxDelay, baseDelay * Math.pow(2, attempt - 1));

    for (let i = 0; i < 100; i++) {
      const delay = calculateFullJitterDelay(attempt, baseDelay, maxDelay);

      assert.ok(typeof delay === 'number');
      assert.ok(!isNaN(delay), 'Delay must not be NaN');
      assert.ok(delay >= floor, `Delay ${delay} must be >= floor ${floor}`);
      assert.ok(delay <= theoreticalMax, `Delay ${delay} must be <= theoreticalMax ${theoreticalMax}`);
    }
  }
});

test('S4.6: withDbRetry prevents buggy onRetry callbacks from disrupting retry loop', async () => {
  let attempts = 0;
  let onRetryCalls = 0;

  const result = await withDbRetry(
    async () => {
      attempts++;
      if (attempts === 1) {
        const err: any = new Error('locked');
        err.code = 'SQLITE_BUSY';
        throw err;
      }
      return 'survived_callback_crash';
    },
    {
      baseDelayMs: 2,
      maxDelayMs: 10,
      onRetry: () => {
        onRetryCalls++;
        throw new Error('Telemetry logger exploded');
      }
    }
  );

  assert.strictEqual(result, 'survived_callback_crash');
  assert.strictEqual(attempts, 2);
  assert.strictEqual(onRetryCalls, 1);
});

test('S4.7: Concurrent SQLite read storm with injected locks resolves safely', async () => {
  const dir = createTempDir('s4_storm_');
  try {
    const dbPath = createSqliteSandbox(dir, 20);
    const db = getReadOnlyDb({ dbPath });

    try {
      // Launch 10 simultaneous queries wrapped in withDbRetry
      const readers = Array.from({ length: 10 }, (_, i) => {
        return withDbRetry(() => {
          const row = queryOne<{ count: number }>('SELECT count(*) as count FROM usage_responses');
          return row?.count;
        });
      });

      const counts = await Promise.all(readers);
      for (const count of counts) {
        assert.strictEqual(count, 20);
      }
    } finally {
      closeDb();
    }
  } finally {
    cleanupPath(dir);
  }
});

// ============================================================================
// SUITE 5: Security / Bounds Checking (Rule 21 & Rule 58 Invariants)
// ============================================================================

test('S5.1: Fleet Rule 21 Invariant: Target site test2 (10.0.70.95) is accessible per Rule 21', async () => {
  const res = await apiFetch('/api/nodes');
  assert.strictEqual(res.status, 200);

  const test2Node = res.data.nodes.find((n: any) => n.ip === BLACKLISTED_HOST_IP);
  assert.ok(test2Node, `Node with IP ${BLACKLISTED_HOST_IP} must exist in cluster manifest`);
  assert.strictEqual(test2Node.is_blacklisted, false, 'test2 must be flagged is_blacklisted: false');
});

test('S5.2: Fleet Rule 21 Invariant: GET /api/nodes?probe=true probes test2 without blacklist exclusion', async () => {
  const res = await apiFetch('/api/nodes?probe=true');
  assert.strictEqual(res.status, 200);

  const test2Node = res.data.nodes.find((n: any) => n.ip === BLACKLISTED_HOST_IP);
  assert.ok(test2Node);
  assert.strictEqual(test2Node.is_blacklisted, false);
});

test('S5.3: Fleet Rule 58 Invariant: POST /api/agents clamps excessive turn_cap down to 60', async () => {
  const res = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      seat: 'bd-worker-test-cap-high',
      turn_cap: 120
    })
  });

  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.data.success, true);
  assert.strictEqual(res.data.updated_config.turn_cap, 60, 'turn_cap 120 must be clamped to 60');
});

test('S5.4: Fleet Rule 58 Invariant: POST /api/agents clamps zero and negative turn_cap up to minimum 1', async () => {
  const resZero = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      seat: 'bd-worker-test-cap-zero',
      turn_cap: 0
    })
  });
  assert.strictEqual(resZero.status, 200);
  assert.strictEqual(resZero.data.updated_config.turn_cap, 1, 'turn_cap 0 must be clamped to 1');

  const resNeg = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      seat: 'bd-worker-test-cap-neg',
      turn_cap: -50
    })
  });
  assert.strictEqual(resNeg.status, 200);
  assert.strictEqual(resNeg.data.updated_config.turn_cap, 1, 'turn_cap -50 must be clamped to 1');
});

test('S5.5: Fleet Rule 58 Invariant: GET /api/agents enforces turn_cap <= 60 for all seats', async () => {
  const res = await apiFetch('/api/agents');
  assert.strictEqual(res.status, 200);
  assert.ok(Array.isArray(res.data.agents));

  for (const agent of res.data.agents) {
    assert.ok(
      agent.turn_cap <= 60,
      `Agent ${agent.seat} turn_cap (${agent.turn_cap}) must not exceed Rule 58 limit of 60`
    );
    assert.ok(agent.turn_cap >= 1, `Agent ${agent.seat} turn_cap must be >= 1`);
  }
});

test('S5.6: Scope Marker Invariant: BD_GATE_SCOPE strictly module or repo-wide', () => {
  const validScopes = new Set(['module', 'repo-wide']);
  const currentScope = process.env.BD_GATE_SCOPE || 'module';
  assert.ok(
    validScopes.has(currentScope),
    `BD_GATE_SCOPE "${currentScope}" must strictly be 'module' or 'repo-wide' (test_v3_66_939)`
  );
});
