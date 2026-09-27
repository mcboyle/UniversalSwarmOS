/**
 * tests/e2e/test_helpers.ts
 * Shared utilities, oracles, sandboxes, and verification contracts for E2E testing tiers.
 * Re-exports directly from src/lib/ to guarantee 100% genuine code verification.
 */

import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';
import { execSync } from 'node:child_process';
import Database from 'better-sqlite3';

// --- Direct Re-exports from Project Implementation ---

export {
  getReadOnlyDb,
  resolveDbPath,
  ensureWalMode,
  queryAll,
  queryOne,
  getDbDiagnostics,
  closeDb,
  resetDbPathCache
} from '../../src/lib/db.ts';

export {
  withDbRetry,
  isSqliteBusyError,
  calculateFullJitterDelay,
  type RetryOptions
} from '../../src/lib/db-retry.ts';

export {
  mutateTsvAtomically,
  parseDispatchLedgerLines,
  reorderDispatchLedgerRows,
  type DispatchLedgerRow
} from '../../src/lib/atomic-tsv.ts';

export {
  cn,
  formatNumber,
  formatCurrency,
  formatPercent,
  formatDuration
} from '../../src/lib/utils.ts';

import {
  mockNodes,
  mockQuotas,
  mockAgentsResponse,
  mockCostData,
  mockQueueItems,
  mockShardsResponse,
  EXPECTED_42_SHARDS
} from '../../src/lib/mock-data.ts';

export const mockShards = mockShardsResponse.shards;
export const mockAgents = mockAgentsResponse.agents;

export {
  mockNodes,
  mockQuotas,
  mockAgentsResponse,
  mockCostData,
  mockQueueItems,
  mockShardsResponse,
  EXPECTED_42_SHARDS
};

export { Database };

// --- HTTP API Verification Client ---

export const TEST_PORT = process.env.TEST_PORT ? parseInt(process.env.TEST_PORT, 10) : 3456;
export const BASE_URL = `http://localhost:${TEST_PORT}`;

export async function apiFetch<T = any>(
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

// --- Types & Interfaces ---

export interface QuotaPoolClaude {
  name: string;
  state: string;
  five_hour_used_pct: number;
  weekly_used_pct: number;
  resets_at: string;
  evidence: string;
}

export interface QuotaPoolAGY {
  name: string;
  observed_at: string;
  gemini: {
    five_hour_remaining_pct: number;
    weekly_remaining_pct: number;
  };
  claude_gpt: {
    five_hour_remaining_pct: number;
    weekly_remaining_pct: number;
  };
}

export interface QuotaResponse {
  timestamp: string;
  pools: {
    claude_a: QuotaPoolClaude;
    claude_b: QuotaPoolClaude;
    codex: { name: string; state: string; evidence: string };
    antigravity: QuotaPoolAGY;
  };
}

export interface ClusterNode {
  name: string;
  ip: string;
  role: 'hub' | 'ops' | 'stg' | 'ai' | 'wrk-bd' | 'wrk-test' | 'spr-pool';
  status: 'up' | 'down' | 'isolated';
  latency_ms: number | null;
  is_blacklisted?: boolean;
}

export interface CiShard {
  id: string;
  name: string;
  category: 'pure-python' | 'browser-provisioned' | 'node-provisioned' | 'postgres';
  status: 'success' | 'failure' | 'running' | 'queued';
  duration_seconds: number;
  taxonomy_code?: string;
  diagnostic?: string;
}

export interface QueueRow {
  timestamp: string;
  seat: string;
  row_id: string;
  status: 'queued' | 'dispatched' | 'started' | 'done' | 'aborted' | 'resent';
  brief_path: string;
}

export interface AgentConfig {
  seat: string;
  role: string;
  type: 'claude' | 'codex' | 'antigravity';
  model: string;
  reasoning_effort?: 'none' | 'low' | 'medium' | 'high' | 'native';
  turn_cap: number;
  status: 'active' | 'idle' | 'busy' | 'paused';
  current_cut?: string;
}

// --- 27-Node Cluster Specification Ground Truth ---

export const EXPECTED_CLUSTER_NODES: { name: string; ip: string; role: ClusterNode['role']; isolated?: boolean }[] = [
  { name: 'hub-mesh01', ip: '10.0.70.164', role: 'hub' },
  { name: 'ops-mcp01', ip: '10.0.70.25', role: 'ops' },
  { name: 'ops-cicd01', ip: '10.0.70.162', role: 'ops' },
  { name: 'ops-test01', ip: '10.0.70.107', role: 'ops' },
  { name: 'stg-cache01', ip: '10.0.70.182', role: 'stg' },
  { name: 'stg-cache02', ip: '10.0.70.224', role: 'stg' },
  { name: 'ai-srv01', ip: '10.0.70.72', role: 'ai' },
  { name: 'ai-dev01', ip: '10.0.70.81', role: 'ai' },
  { name: 'ai-infer01', ip: '10.0.70.125', role: 'ai' },
  { name: 'ai-ollama01', ip: '10.0.70.228', role: 'ai' },
  { name: 'wrk-bd01', ip: '10.0.70.50', role: 'wrk-bd' },
  { name: 'wrk-bd02', ip: '10.0.70.51', role: 'wrk-bd' },
  { name: 'wrk-bd03', ip: '10.0.70.52', role: 'wrk-bd' },
  { name: 'wrk-bd04', ip: '10.0.70.53', role: 'wrk-bd' },
  { name: 'wrk-bd05', ip: '10.0.70.54', role: 'wrk-bd' },
  { name: 'wrk-test01', ip: '10.0.70.83', role: 'wrk-test' },
  { name: 'wrk-test02', ip: '10.0.70.95', role: 'wrk-test', isolated: true }, // test2 strictly blacklisted!
  { name: 'wrk-test03', ip: '10.0.70.80', role: 'wrk-test' },
  { name: 'wrk-test04', ip: '10.0.70.82', role: 'wrk-test' },
  { name: 'wrk-test05', ip: '10.0.70.85', role: 'wrk-test' },
  { name: 'wrk-test06', ip: '10.0.70.249', role: 'wrk-test' },
  { name: 'wrk-test07', ip: '10.0.70.84', role: 'wrk-test' },
  { name: 'spr-pool01', ip: '10.0.70.120', role: 'spr-pool' },
  { name: 'spr-pool02', ip: '10.0.70.183', role: 'spr-pool' },
  { name: 'spr-pool03', ip: '10.0.70.184', role: 'spr-pool' },
  { name: 'spr-pool04', ip: '10.0.70.185', role: 'spr-pool' },
  { name: 'spr-pool05', ip: '10.0.70.149', role: 'spr-pool' },
];

export const BLACKLISTED_HOST_IP = '10.0.70.95';

// --- 42 CI Shards Specification Ground Truth ---

export const EXPECTED_42_SHARD_NAMES: string[] = [
  'application-safety', 'toolchain', 'artifacts-pins', 'regen-idempotence',
  'download-chain', 'template-selectors', 'frontend-vitest', 'parity-graph',
  'parity-vitest-b', 'postgres-integration', 'unit-accounting', 'unit-cli',
  'unit-dispatch', 'unit-evidence', 'unit-fleet', 'unit-harness', 'unit-lens',
  'unit-mining', 'unit-parsing', 'unit-rebase', 'unit-retry', 'unit-roles',
  'unit-router', 'unit-rules', 'unit-sandbox', 'unit-sqlite', 'unit-telemetry',
  'unit-tsv', 'unit-types', 'unit-vector', 'unit-vmware', 'unit-wal',
  'unit-workflow', 'int-api-routes', 'int-auth-bypass', 'int-cache-hit',
  'int-concurrency', 'int-deadlock', 'int-flock-swap', 'int-health-matrix',
  'int-latency-grid', 'int-quota-math'
];

export const CI_TAXONOMY_CODES = [
  'BD-CI-01', 'BD-CI-02', 'BD-CI-03', 'BD-CI-04', 'BD-CI-05',
  'BD-CI-06', 'BD-CI-07', 'BD-CI-08', 'BD-CI-09'
];

// --- Isolated Test Fixtures & Sandboxes ---

export function createTempDir(prefix = 'hs_test_'): string {
  const dir = path.join(os.tmpdir(), `${prefix}${Date.now()}_${crypto.randomBytes(4).toString('hex')}`);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export function cleanupPath(targetPath: string): void {
  try {
    if (fs.existsSync(targetPath)) {
      fs.rmSync(targetPath, { recursive: true, force: true });
    }
  } catch {}
}

/**
 * Creates an isolated SQLite database fixture in WAL mode with the usage_responses schema
 */
export function createSqliteSandbox(dir: string, rowCount = 50): string {
  const dbPath = path.join(dir, 'test_usage.sqlite');
  const initScript = path.resolve(process.cwd(), 'scripts/init_test_db.py');
  execSync(`python3 "${initScript}" "${dbPath}" ${rowCount}`, { stdio: 'pipe' });
  return dbPath;
}

/**
 * Creates an isolated TSV ledger fixture matching DISPATCH-LEDGER.tsv format
 */
export function createTsvSandbox(dir: string, rowCount = 10): string {
  const tsvPath = path.join(dir, 'DISPATCH-LEDGER.tsv');
  const lines: string[] = [];
  for (let i = 1; i <= rowCount; i++) {
    const status = i === 1 ? 'started' : i <= 3 ? 'done' : 'dispatched';
    lines.push(`2026-09-22T20:${String(i).padStart(2, '0')}:00Z\tbd-worker-${i}\trow${i}\t${status}\t/home/mboyle/bd-persist/briefs/brief_${i}.md`);
  }
  fs.writeFileSync(tsvPath, lines.join('\n') + '\n', 'utf8');
  return tsvPath;
}

/**
 * Quota calculations parser adhering to POOL_STATE.tsv specification
 */
export function calculateQuotaDistinction(poolStateTsvContent: string): QuotaResponse {
  const lines = poolStateTsvContent.trim().split('\n');
  
  let claudeA: QuotaPoolClaude = {
    name: 'Claude Pool A',
    state: 'UNKNOWN',
    five_hour_used_pct: 0,
    weekly_used_pct: 0,
    resets_at: '',
    evidence: ''
  };
  let claudeB: QuotaPoolClaude = {
    name: 'Claude Pool B',
    state: 'UNKNOWN',
    five_hour_used_pct: 0,
    weekly_used_pct: 0,
    resets_at: '',
    evidence: ''
  };
  let codex = { name: 'Codex Fleet Pool', state: 'UNKNOWN', evidence: '' };
  let antigravity: QuotaPoolAGY = {
    name: 'Antigravity Dynamic Pool',
    observed_at: '',
    gemini: { five_hour_remaining_pct: 100, weekly_remaining_pct: 100 },
    claude_gpt: { five_hour_remaining_pct: 100, weekly_remaining_pct: 100 }
  };

  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split('\t');
    const pool = cols[0];
    if (pool === 'A') {
      claudeA = {
        name: 'Claude Pool A',
        state: cols[1] || 'UNKNOWN',
        five_hour_used_pct: cols[4] && cols[4] !== '-' ? Number(cols[4]) : 0,
        weekly_used_pct: cols[6] && cols[6] !== '-' ? Number(cols[6]) : 0,
        resets_at: cols[5] && cols[5] !== '-' ? cols[5] : '',
        evidence: cols[3] || ''
      };
    } else if (pool === 'B') {
      claudeB = {
        name: 'Claude Pool B',
        state: cols[1] || 'UNKNOWN',
        five_hour_used_pct: cols[4] && cols[4] !== '-' ? Number(cols[4]) : 0,
        weekly_used_pct: cols[6] && cols[6] !== '-' ? Number(cols[6]) : 0,
        resets_at: cols[5] && cols[5] !== '-' ? cols[5] : '',
        evidence: cols[3] || ''
      };
    } else if (pool === 'codex') {
      codex = {
        name: 'Codex Fleet Pool',
        state: cols[1] || 'UNKNOWN',
        evidence: cols[3] || ''
      };
    } else if (pool === 'AGY') {
      antigravity = {
        name: 'Antigravity Dynamic Pool',
        observed_at: cols[12] && cols[12] !== '-' ? cols[12] : new Date().toISOString(),
        gemini: {
          five_hour_remaining_pct: cols[8] && cols[8] !== '-' ? Number(cols[8]) : 100,
          weekly_remaining_pct: cols[9] && cols[9] !== '-' ? Number(cols[9]) : 100
        },
        claude_gpt: {
          five_hour_remaining_pct: cols[10] && cols[10] !== '-' ? Number(cols[10]) : 100,
          weekly_remaining_pct: cols[11] && cols[11] !== '-' ? Number(cols[11]) : 100
        }
      };
    }
  }

  return {
    timestamp: new Date().toISOString(),
    pools: {
      claude_a: claudeA,
      claude_b: claudeB,
      codex,
      antigravity
    }
  };
}
