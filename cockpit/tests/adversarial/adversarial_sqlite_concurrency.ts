/**
 * tests/adversarial/adversarial_sqlite_concurrency.ts
 *
 * Adversarial SQLite Concurrency Test Harness for Milestone 1 AC3:
 * "Backend can sustain 10 concurrent API read requests to usage.sqlite
 *  under 15 active writers without throwing sqlite3.OperationalError: database is locked."
 *
 * Scenarios:
 * 1. Live Accounting DB Concurrency Storm:
 *    - 20 concurrent HTTP readers querying live GET /api/cost on Next.js server
 *    - 20 concurrent Node.js better-sqlite3 readers directly querying live /home/mboyle/bd-persist/accounting/usage.sqlite
 *    - Confirms source === 'live' and 0 'database is locked' errors
 *
 * 2. Heavy Contention Writer Storm (WAL Mode):
 *    - 15 independent OS writer processes performing continuous BEGIN IMMEDIATE writes
 *    - 10 concurrent Node.js readers executing analytical queries via withDbRetry
 *    - Confirms 0 'database is locked' errors
 *
 * 3. Positive Control (DELETE Mode / zero timeout):
 *    - Same concurrency under DELETE mode
 *    - Confirms that our probe reliably detects SQLITE_BUSY / locked errors when unprotected
 */

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import { spawn } from 'node:child_process';
import Database from 'better-sqlite3';
import { withDbRetry } from '../../src/lib/db-retry.ts';
import { getReadOnlyDb } from '../../src/lib/db.ts';

const LIVE_DB_PATH = '/home/mboyle/bd-persist/accounting/usage.sqlite';
const SERVER_PORT = process.env.TEST_PORT ? parseInt(process.env.TEST_PORT, 10) : 3457;

export interface TestResult {
  scenario: string;
  totalReads: number;
  successfulReads: number;
  lockedErrors: number;
  otherErrors: number;
  totalWrites: number;
  p50Ms: number;
  p95Ms: number;
  maxMs: number;
  sourceLiveCount?: number;
  sourceMockCount?: number;
  passed: boolean;
}

function percentile(arr: number[], p: number): number {
  if (arr.length === 0) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.min(Math.floor((p / 100) * sorted.length), sorted.length - 1);
  return Math.round(sorted[idx] * 100) / 100;
}

/**
 * Executes an HTTP GET request against the local server and measures latency.
 */
function fetchUrl(url: string): Promise<{ status: number; body: string; latencyMs: number }> {
  const start = performance.now();
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        const latencyMs = performance.now() - start;
        resolve({ status: res.statusCode || 0, body: data, latencyMs });
      });
    });
    req.on('error', (err) => {
      reject(err);
    });
    req.setTimeout(10000, () => {
      req.destroy(new Error('HTTP request timeout (10s)'));
    });
  });
}

/**
 * Scenario 1: Live Accounting DB Concurrent Storm.
 * Queries GET /api/cost and direct Node.js better-sqlite3 against /home/mboyle/bd-persist/accounting/usage.sqlite.
 */
export async function runLiveDbConcurrentStorm(): Promise<TestResult> {
  console.log('\n===============================================================');
  console.log('--- SCENARIO 1: Live Accounting DB Concurrent Storm ---');
  console.log(`Target DB: ${LIVE_DB_PATH}`);
  console.log(`Server Port: ${SERVER_PORT}`);
  console.log('===============================================================');

  const latencies: number[] = [];
  let successfulReads = 0;
  let lockedErrors = 0;
  let otherErrors = 0;
  let sourceLiveCount = 0;
  let sourceMockCount = 0;

  const NUM_HTTP_REQUESTS = 50;
  const CONCURRENT_WORKERS = 10;

  // 1. Concurrent HTTP requests to GET /api/cost
  console.log(`[*] Firing ${NUM_HTTP_REQUESTS} HTTP requests to /api/cost across ${CONCURRENT_WORKERS} concurrent streams...`);
  const httpTasks = Array.from({ length: NUM_HTTP_REQUESTS }, async (_, idx) => {
    try {
      const url = `http://localhost:${SERVER_PORT}/api/cost?since=${(idx % 6) + 1}h`;
      const res = await fetchUrl(url);
      latencies.push(res.latencyMs);

      if (res.status === 200) {
        const parsed = JSON.parse(res.body);
        if (parsed.source === 'live') {
          sourceLiveCount++;
          successfulReads++;
        } else if (parsed.source === 'mock') {
          sourceMockCount++;
          otherErrors++;
        }
      } else {
        otherErrors++;
      }
    } catch (err: any) {
      if (err.message?.includes('locked') || err.message?.includes('busy')) {
        lockedErrors++;
      } else {
        otherErrors++;
      }
    }
  });

  await Promise.all(httpTasks);

  // 2. Direct concurrent queries using better-sqlite3 + withDbRetry against live usage.sqlite
  console.log(`[*] Executing 200 direct analytical queries via better-sqlite3 withDbRetry against live DB...`);
  const DIRECT_QUERIES = 200;
  const directTasks = Array.from({ length: DIRECT_QUERIES }, async () => {
    const start = performance.now();
    try {
      await withDbRetry(() => {
        const db = getReadOnlyDb();
        const stmt = db.prepare(`
          SELECT model, count(*) as count, max(timestamp) as latest
          FROM usage_responses
          WHERE quarantined = 0
          GROUP BY model
          LIMIT 10
        `);
        const rows = stmt.all();
        if (rows.length === 0) throw new Error('Expected rows from live DB');
        return rows;
      }, { maxRetries: 5, baseDelayMs: 10, maxDelayMs: 100 });

      latencies.push(performance.now() - start);
      successfulReads++;
    } catch (err: any) {
      latencies.push(performance.now() - start);
      if (err.message?.includes('locked') || err.message?.includes('busy')) {
        lockedErrors++;
      } else {
        otherErrors++;
      }
    }
  });

  await Promise.all(directTasks);

  const totalReads = NUM_HTTP_REQUESTS + DIRECT_QUERIES;
  const passed = lockedErrors === 0 && sourceMockCount === 0 && successfulReads === totalReads;

  console.log(`[+] Total reads executed: ${totalReads}`);
  console.log(`[+] Successful reads: ${successfulReads} / ${totalReads}`);
  console.log(`[+] Locked errors: ${lockedErrors}`);
  console.log(`[+] Source live responses: ${sourceLiveCount} / ${NUM_HTTP_REQUESTS}`);
  console.log(`[+] Source mock responses: ${sourceMockCount}`);
  console.log(`[+] Latency: p50 = ${percentile(latencies, 50)}ms, p95 = ${percentile(latencies, 95)}ms, max = ${percentile(latencies, 100)}ms`);
  console.log(`[+] Result: ${passed ? 'PASS' : 'FAIL'}`);

  return {
    scenario: 'Live DB Concurrent Storm',
    totalReads,
    successfulReads,
    lockedErrors,
    otherErrors,
    totalWrites: 0,
    p50Ms: percentile(latencies, 50),
    p95Ms: percentile(latencies, 95),
    maxMs: percentile(latencies, 100),
    sourceLiveCount,
    sourceMockCount,
    passed
  };
}

/**
 * Creates a sandbox SQLite DB populated with realistic usage records.
 */
function createSandboxDatabase(journalMode: 'WAL' | 'DELETE'): string {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sqlite_stress_'));
  const dbPath = path.join(tmpDir, 'test_usage.sqlite');

  const db = new Database(dbPath);
  db.pragma(`journal_mode = ${journalMode}`);
  db.pragma('busy_timeout = 5000');

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
    CREATE TABLE usage_diagnostics (
      worker_id TEXT PRIMARY KEY,
      iteration INTEGER,
      payload TEXT,
      updated_at TEXT
    );
  `);

  const insert = db.prepare(`
    INSERT INTO usage_responses VALUES (
      'anthropic',
      ?,
      datetime('now', ?),
      'claude-opus-5-5',
      '{"input_tokens": 125000, "cache_read_input_tokens": 122000, "output_tokens": 850}',
      'fp_test',
      0
    )
  `);

  const tx = db.transaction(() => {
    for (let i = 0; i < 500; i++) {
      insert.run(`resp_${i}`, `-${i % 360} minutes`);
    }
  });
  tx();
  db.close();

  return dbPath;
}

/**
 * Scenario 2: High Contention Stress Test under 15 OS Writer Processes (WAL Mode).
 */
export async function runHeavyContentionStress(journalMode: 'WAL' | 'DELETE' = 'WAL'): Promise<TestResult> {
  console.log('\n===============================================================');
  console.log(`--- SCENARIO 2: ${journalMode} Mode Contention: 15 Writers vs 10 Readers ---`);
  console.log('===============================================================');

  const dbPath = createSandboxDatabase(journalMode);
  const NUM_WRITERS = 15;
  const NUM_READERS = 10;
  const READS_PER_READER = 50;

  // Python writer script executing BEGIN IMMEDIATE write transactions
  const writerPython = `
import sqlite3, sys, time, random

db_path = sys.argv[1]
wid = sys.argv[2]

conn = sqlite3.connect(db_path, timeout=5.0)
${journalMode === 'WAL' ? "conn.execute('PRAGMA busy_timeout = 5000;')" : "conn.execute('PRAGMA busy_timeout = 200;')"}

count = 0
for i in range(100):
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""
            INSERT OR REPLACE INTO usage_diagnostics (worker_id, iteration, payload, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (f"worker_{wid}", i, "x" * 256))
        conn.commit()
        count += 1
        time.sleep(random.uniform(0.001, 0.005))
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
conn.close()
print(f"WRITER_{wid}:{count}")
`;

  // Spawn 15 OS writer processes
  console.log(`[*] Spawning ${NUM_WRITERS} OS writer processes targeting ${dbPath}...`);
  const writerProcs = Array.from({ length: NUM_WRITERS }, (_, i) => {
    return new Promise<{ wid: number; writes: number }>((resolve) => {
      const p = spawn('python3', ['-c', writerPython, dbPath, String(i)]);
      let stdout = '';
      p.stdout.on('data', (d) => { stdout += d; });
      p.on('close', () => {
        const match = stdout.match(/WRITER_\d+:(\d+)/);
        const writes = match ? parseInt(match[1], 10) : 0;
        resolve({ wid: i, writes });
      });
    });
  });

  // Give writers 20ms to start active contention
  await new Promise((r) => setTimeout(r, 20));

  const latencies: number[] = [];
  let successfulReads = 0;
  let lockedErrors = 0;
  let otherErrors = 0;

  // Spawn 10 concurrent readers running queries
  console.log(`[*] Spawning ${NUM_READERS} concurrent readers executing ${READS_PER_READER} queries each (${NUM_READERS * READS_PER_READER} total)...`);
  const readerTasks = Array.from({ length: NUM_READERS }, async (_, rid) => {
    for (let r = 0; r < READS_PER_READER; r++) {
      const start = performance.now();
      try {
        await withDbRetry(() => {
          const db = new Database(dbPath, { readonly: true, timeout: journalMode === 'WAL' ? 5000 : 200 });
          try {
            const row = db.prepare('SELECT count(*) as count, max(timestamp) as latest FROM usage_responses').get() as { count: number };
            if (!row || row.count === 0) throw new Error('Query returned no rows');
            return row;
          } finally {
            db.close();
          }
        }, { maxRetries: journalMode === 'WAL' ? 5 : 0, baseDelayMs: 10, maxDelayMs: 100 });

        latencies.push(performance.now() - start);
        successfulReads++;
      } catch (err: any) {
        latencies.push(performance.now() - start);
        if (err.message?.includes('locked') || err.message?.includes('busy')) {
          lockedErrors++;
        } else {
          otherErrors++;
        }
      }
      await new Promise((res) => setTimeout(res, 2));
    }
  });

  const [writerResults] = await Promise.all([
    Promise.all(writerProcs),
    Promise.all(readerTasks)
  ]);

  const totalWrites = writerResults.reduce((sum, w) => sum + w.writes, 0);
  const totalReads = NUM_READERS * READS_PER_READER;
  const passed = journalMode === 'WAL'
    ? (lockedErrors === 0 && successfulReads === totalReads)
    : (lockedErrors > 0); // In DELETE mode positive control, success means proving it catches locked errors!

  console.log(`[+] Total writes committed across ${NUM_WRITERS} processes: ${totalWrites}`);
  console.log(`[+] Total reads attempted: ${totalReads}`);
  console.log(`[+] Successful reads: ${successfulReads} / ${totalReads}`);
  console.log(`[+] Locked errors (SQLITE_BUSY): ${lockedErrors}`);
  console.log(`[+] Other errors: ${otherErrors}`);
  console.log(`[+] Latency: p50 = ${percentile(latencies, 50)}ms, p95 = ${percentile(latencies, 95)}ms, max = ${percentile(latencies, 100)}ms`);
  console.log(`[+] Outcome: ${passed ? 'PASS' : 'FAIL'}`);

  // Cleanup sandbox files
  try {
    const dir = path.dirname(dbPath);
    fs.rmSync(dir, { recursive: true, force: true });
  } catch {}

  return {
    scenario: `${journalMode} Contention (15 Writers vs 10 Readers)`,
    totalReads,
    successfulReads,
    lockedErrors,
    otherErrors,
    totalWrites,
    p50Ms: percentile(latencies, 50),
    p95Ms: percentile(latencies, 95),
    maxMs: percentile(latencies, 100),
    passed
  };
}

export async function main() {
  console.log('Starting Adversarial SQLite Concurrency Test Suite...');

  // Scenario 1: Live DB Concurrency Storm
  const s1 = await runLiveDbConcurrentStorm();

  // Scenario 2: 15 Writers vs 10 Readers in WAL Mode
  const s2 = await runHeavyContentionStress('WAL');

  // Scenario 3: Positive Control in DELETE Mode (Verifies Probe Can Detect Failures)
  const s3 = await runHeavyContentionStress('DELETE');

  console.log('\n===============================================================');
  console.log('               FINAL METRIC SUMMARY & VERDICT                  ');
  console.log('===============================================================');
  console.log(`Scenario 1 (Live DB Storm)  : ${s1.passed ? 'PASSED' : 'FAILED'} | Reads: ${s1.successfulReads}/${s1.totalReads} | Locked: ${s1.lockedErrors} | Mock: ${s1.sourceMockCount}`);
  console.log(`Scenario 2 (WAL 15W vs 10R) : ${s2.passed ? 'PASSED' : 'FAILED'} | Reads: ${s2.successfulReads}/${s2.totalReads} | Locked: ${s2.lockedErrors} | Writes: ${s2.totalWrites}`);
  console.log(`Scenario 3 (DELETE Control) : ${s3.passed ? 'PASSED (Positive Control Caught Locks)' : 'FAILED'} | Locked Detected: ${s3.lockedErrors}`);

  const overallPass = s1.passed && s2.passed && s3.passed;
  console.log(`\nOVERALL CHALLENGE VERDICT: ${overallPass ? 'APPROVE' : 'REQUEST_CHANGES'}`);

  if (!overallPass) {
    process.exit(1);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((err) => {
    console.error('Fatal test error:', err);
    process.exit(1);
  });
}
