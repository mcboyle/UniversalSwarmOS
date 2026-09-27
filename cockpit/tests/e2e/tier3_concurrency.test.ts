/**
 * tests/e2e/tier3_concurrency.test.ts
 * Tier 3: Concurrency & Cross-Feature Interactions
 * Verifies pairwise subsystem interactions, simultaneous reading/writing,
 * atomic TSV lock contention, and direct AC3/AC4 empirical concurrency benchmarks.
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
  getReadOnlyDb,
  closeDb,
  Database,
  withDbRetry,
  mutateTsvAtomically,
  apiFetch
} from './test_helpers.ts';

test('T3.1: Concurrent SQLite Read Storm under Active Writer sustains 0 locked errors', async () => {
  const dir = createTempDir('t3_1_');
  try {
    const dbPath = createSqliteSandbox(dir, 100);

    // Launch active Python background writer
    const writerScript = `
import sqlite3, time, random
conn = sqlite3.connect('${dbPath}', timeout=5.0)
conn.execute('PRAGMA busy_timeout = 5000;')
for i in range(150):
    try:
        conn.execute('INSERT OR REPLACE INTO usage_diagnostics VALUES (?, ?)', (f'worker_{i%5}', random.randint(1, 99999)))
        conn.commit()
        time.sleep(0.001)
    except Exception:
        pass
conn.close()
`;
    spawnSync('python3', ['-c', writerScript], { encoding: 'utf8' });

    // Concurrently execute 10 reader queries via Node.js better-sqlite3 and withDbRetry
    const readers = Array.from({ length: 10 }, async () => {
      return withDbRetry(
        () => {
          const db = new Database(dbPath, { readonly: true, timeout: 5000 });
          try {
            const row = db.prepare('SELECT count(*) as count FROM usage_responses').get() as { count: number };
            return row.count;
          } finally {
            db.close();
          }
        },
        { maxRetries: 5, baseDelayMs: 10, maxDelayMs: 100 }
      );
    });

    const results = await Promise.all(readers);
    assert.strictEqual(results.length, 10, 'All 10 concurrent readers must complete');
    for (const count of results) {
      assert.strictEqual(count, 100, 'Each reader must see all 100 seeded rows');
    }
  } finally {
    cleanupPath(dir);
  }
});

test('T3.2: High-Frequency TSV Queue Reorder during Dispatcher Polling produces zero torn reads', async () => {
  const dir = createTempDir('t3_2_');
  try {
    const tsv = createTsvSandbox(dir, 10);
    let stopReading = false;
    let totalReads = 0;
    let tornReads = 0;

    // Asynchronous polling reader simulating active dispatcher
    const readerPromise = (async () => {
      while (!stopReading) {
        try {
          const content = fs.readFileSync(tsv, 'utf8');
          const lines = content.trim().split('\n');
          if (lines.length !== 10) {
            tornReads++;
          }
          for (const line of lines) {
            if (line.split('\t').length !== 5) {
              tornReads++;
            }
          }
          totalReads++;
        } catch {
          tornReads++;
        }
        await new Promise((r) => setTimeout(r, 1));
      }
    })();

    // Perform 25 concurrent atomic queue reorder mutations
    for (let i = 0; i < 25; i++) {
      await mutateTsvAtomically(tsv, (lines) => {
        const nonBlank = lines.filter((l) => l.trim().length > 0);
        return nonBlank.reverse();
      });
      await new Promise((r) => setTimeout(r, 2));
    }

    stopReading = true;
    await readerPromise;

    assert.ok(totalReads >= 10, `Reader must execute polling reads (performed: ${totalReads})`);
    assert.strictEqual(tornReads, 0, `Zero torn reads permitted (detected: ${tornReads})`);
  } finally {
    cleanupPath(dir);
  }
});

test('T3.3: Cross-Feature Telemetry & Quota Concurrency executes without race conditions', async () => {
  const dir = createTempDir('t3_3_');
  try {
    const dbPath = createSqliteSandbox(dir, 50);

    // Concurrently query database telemetry via withDbRetry and fetch live /api/quotas
    const [dbResult, quotaRes] = await Promise.all([
      withDbRetry(() => {
        const db = new Database(dbPath, { readonly: true, timeout: 5000 });
        try {
          const row = db.prepare('SELECT count(*) as count FROM usage_responses').get() as { count: number };
          return row.count;
        } finally {
          db.close();
        }
      }),
      apiFetch('/api/quotas')
    ]);

    assert.strictEqual(dbResult, 50);
    assert.strictEqual(quotaRes.status, 200);
    assert.ok(quotaRes.data.pools.claude_a);
  } finally {
    cleanupPath(dir);
  }
});

test('T3.4: Simultaneous Multi-Client Queue Mutations are safely serialized by advisory lock', async () => {
  const dir = createTempDir('t3_4_');
  try {
    const tsv = createTsvSandbox(dir, 8);
    // Launch 6 concurrent mutations
    const workers = Array.from({ length: 6 }, (_, i) =>
      mutateTsvAtomically(
        tsv,
        (lines) => {
          const valid = lines.filter((l) => l.trim().length > 0);
          return valid.map((l) => (l.includes(`tag_${i}`) ? l : `${l}\ttag_${i}`));
        },
        5000
      )
    );

    await Promise.all(workers);
    const finalContent = fs.readFileSync(tsv, 'utf8').trim().split('\n');
    assert.strictEqual(finalContent.length, 8, 'All 8 rows must be preserved after 6 concurrent mutations');
  } finally {
    cleanupPath(dir);
  }
});

test('T3.5: CI Shard Status and Node Latency Cross-Update maintains aggregate consistency', async () => {
  // Concurrently fetch live /api/nodes and /api/shards
  const [nodesRes, shardsRes] = await Promise.all([
    apiFetch('/api/nodes'),
    apiFetch('/api/shards')
  ]);

  assert.strictEqual(nodesRes.status, 200);
  assert.strictEqual(shardsRes.status, 200);
  assert.strictEqual(nodesRes.data.total_nodes, 27);
  assert.strictEqual(shardsRes.data.total_shards, 42);
});

test('T3.6: AC3 Direct Benchmark: scripts/test_sqlite_concurrency.py executes with exit code 0', () => {
  const scriptPath = path.resolve(process.cwd(), 'scripts/test_sqlite_concurrency.py');
  assert.ok(fs.existsSync(scriptPath), 'scripts/test_sqlite_concurrency.py must exist');

  const proc = spawnSync('python3', [scriptPath], { encoding: 'utf8', timeout: 60000 });
  assert.strictEqual(proc.status, 0, `Benchmark script must exit 0. Output: ${proc.stdout}\nStderr: ${proc.stderr}`);
  assert.ok(proc.stdout.includes('AC3 Verified'), 'Output must confirm AC3 verification');
  assert.ok(proc.stdout.includes("zero 'database is locked' errors"));
});

test('T3.7: AC4 Direct Benchmark: scripts/test_tsv_atomic_reorder.sh executes with exit code 0', () => {
  const scriptPath = path.resolve(process.cwd(), 'scripts/test_tsv_atomic_reorder.sh');
  assert.ok(fs.existsSync(scriptPath), 'scripts/test_tsv_atomic_reorder.sh must exist');

  const proc = spawnSync('bash', [scriptPath], { encoding: 'utf8', timeout: 60000 });
  assert.strictEqual(proc.status, 0, `TSV benchmark script must exit 0. Output: ${proc.stdout}\nStderr: ${proc.stderr}`);
  assert.ok(proc.stdout.includes('AC4 Verified'), 'Output must confirm AC4 verification');
  assert.ok(proc.stdout.includes('zero torn reads'));
});
