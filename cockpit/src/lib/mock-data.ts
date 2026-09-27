// src/lib/mock-data.ts
import type {
  QueueItem,
  QuotaResponse,
  CostResponse,
  ClusterNode,
  ShardsResponse,
  AgentsResponse,
  CiShardStatus,
  ArchitectureResponse
} from './types';

export const mockQueueItems: QueueItem[] = [
  { index: 0, timestamp: '2026-09-22T23:02:30Z', seat: 'bd-worker-W1-A', row: 'row1017', status: 'dispatched', brief_path: '/home/mboyle/briefs/ORDERS-1017.md', is_active: true },
  { index: 1, timestamp: '2026-09-22T23:02:36Z', seat: 'bd-worker-W2-B', row: 'row1032', status: 'dispatched', brief_path: '/home/mboyle/briefs/ORDERS-1032.md', is_active: true },
  { index: 2, timestamp: '2026-09-22T23:02:42Z', seat: 'bd-worker-W3-A', row: 'row1060', status: 'dispatched', brief_path: '/home/mboyle/briefs/ORDERS-1060.md', is_active: true },
  { index: 3, timestamp: '2026-09-22T22:56:10Z', seat: 'bd-worker-W5-A', row: 'row1033-red', status: 'started', brief_path: '/home/mboyle/briefs/ORDERS-1033.md', is_active: true },
  { index: 4, timestamp: '2026-09-22T22:42:01Z', seat: 'bd-worker-W4-B', row: 'row1078', status: 'done', brief_path: '/home/mboyle/briefs/ORDERS-1078.md', is_active: false },
  { index: 5, timestamp: '2026-09-22T22:46:01Z', seat: 'bd-worker-W2-B', row: 'row1015-red', status: 'done', brief_path: '/home/mboyle/briefs/ORDERS-1015.md', is_active: false }
];

export const mockQuotas: QuotaResponse = {
  timestamp: '2026-09-22T23:00:00Z',
  pools: {
    claude_a: {
      name: 'Claude Pool A',
      state: 'OFF-PACE',
      five_hour_used_pct: 19,
      weekly_used_pct: 82,
      resets_at: '2026-09-23T02:09:59Z',
      evidence: 'weekly_all at 82% at 52% of week (> +10)'
    },
    claude_b: {
      name: 'Claude Pool B',
      state: 'UNKNOWN',
      five_hour_used_pct: 8,
      weekly_used_pct: 31,
      resets_at: '2026-09-22T02:10:00Z',
      evidence: 'usage cache 89943s old (> 14400s)'
    },
    codex: {
      name: 'Codex Fleet Pool',
      state: 'UNKNOWN',
      evidence: '0 of 15 roster host(s) answered'
    },
    antigravity: {
      name: 'Antigravity Dynamic Pool',
      observed_at: '2026-09-21T10:16:10Z',
      gemini: {
        five_hour_remaining_pct: 93,
        weekly_remaining_pct: 46
      },
      claude_gpt: {
        five_hour_remaining_pct: 100,
        weekly_remaining_pct: 72
      }
    },
    grok: {
      name: 'Grok Fleet Pool (xAI)',
      state: 'OK',
      five_hour_used_pct: 0,
      weekly_used_pct: 4,
      resets_at: '2026-10-03T20:42:00Z',
      evidence: 'Weekly SuperGrok: 4% used (resets October 3, 2026 at 8:42 PM)'
    },
    kimi: {
      name: 'Kimi Fleet Pool (Moonshot)',
      state: 'OK',
      five_hour_used_pct: 0,
      weekly_used_pct: 1,
      resets_at: '2026-10-26T00:00:00Z',
      evidence: '5h: 0% used; Pro total: 0.6% used (resets 2026-10-26)'
    }
  },
  source: 'mock'
};

export const mockCostData: CostResponse = {
  since: '2026-09-22T17:00:00Z',
  group_by: 'model',
  total_responses: 4563,
  aggregate: {
    total_context_tokens: 773743308,
    total_output_tokens: 3223696,
    total_cache_read_tokens: 758197779,
    overall_cache_hit_pct: 97.99,
    total_cost_usd: 154.20,
    projected_24h_cost_usd: 616.80
  },
  breakdown: [
    {
      key: 'claude-fable-5-1',
      turns: 2044,
      total_ctx: 390098464,
      out_tokens: 2054854,
      cache_read: 384048871,
      cache_efficiency_pct: 98.45,
      mean_ctx: 190850,
      max_ctx: 687166,
      cost_usd: 78.12
    },
    {
      key: 'claude-opus-5',
      turns: 663,
      total_ctx: 181447546,
      out_tokens: 486123,
      cache_read: 180627332,
      cache_efficiency_pct: 99.55,
      mean_ctx: 273676,
      max_ctx: 565329,
      cost_usd: 36.30
    },
    {
      key: 'gpt-5.6-terra',
      turns: 1210,
      total_ctx: 120500000,
      out_tokens: 450000,
      cache_read: 114000000,
      cache_efficiency_pct: 94.61,
      mean_ctx: 99586,
      max_ctx: 412000,
      cost_usd: 24.50
    },
    {
      key: 'grok-2',
      turns: 580,
      total_ctx: 72400000,
      out_tokens: 610000,
      cache_read: 69100000,
      cache_efficiency_pct: 95.44,
      mean_ctx: 124827,
      max_ctx: 380000,
      cost_usd: 16.40
    },
    {
      key: 'kimi-k1.5',
      turns: 890,
      total_ctx: 112000000,
      out_tokens: 1250000,
      cache_read: 108500000,
      cache_efficiency_pct: 96.87,
      mean_ctx: 125842,
      max_ctx: 450000,
      cost_usd: 12.80
    }
  ],
  source: 'mock'
};

export const mockNodes: ClusterNode[] = [
  { name: 'hub-mesh01', fqdn: 'hub-mesh01.mesh.local', ip: '10.0.70.164', role: 'hub', tier: 'Primary Controller', status: 'up', latency_ms: 0.05, is_local: true, is_blacklisted: false },
  { name: 'ops-mcp01', fqdn: 'ops-mcp01.mesh.local', ip: '10.0.70.25', role: 'ops', tier: 'Operations & CI', status: 'up', latency_ms: 0.25, is_local: false, is_blacklisted: false },
  { name: 'ops-cicd01', fqdn: 'ops-cicd01.mesh.local', ip: '10.0.70.162', role: 'ops', tier: 'Operations & CI', status: 'up', latency_ms: 0.28, is_local: false, is_blacklisted: false },
  { name: 'ops-test01', fqdn: 'ops-test01.mesh.local', ip: '10.0.70.107', role: 'ops', tier: 'Operations & CI', status: 'up', latency_ms: 0.31, is_local: false, is_blacklisted: false },
  { name: 'stg-cache01', fqdn: 'stg-cache01.mesh.local', ip: '10.0.70.182', role: 'stg', tier: 'RAG & Cache', status: 'up', latency_ms: 0.30, is_local: false, is_blacklisted: false },
  { name: 'stg-cache02', fqdn: 'stg-cache02.mesh.local', ip: '10.0.70.224', role: 'stg', tier: 'RAG & Cache', status: 'up', latency_ms: 0.33, is_local: false, is_blacklisted: false },
  { name: 'ai-srv01', fqdn: 'ai-srv01.mesh.local', ip: '10.0.70.72', role: 'ai', tier: 'AI Satellite', status: 'up', latency_ms: 0.35, is_local: false, is_blacklisted: false },
  { name: 'ai-dev01', fqdn: 'ai-dev01.mesh.local', ip: '10.0.70.81', role: 'ai', tier: 'AI Satellite', status: 'up', latency_ms: 0.36, is_local: false, is_blacklisted: false },
  { name: 'ai-infer01', fqdn: 'ai-infer01.mesh.local', ip: '10.0.70.125', role: 'ai', tier: 'AI Satellite', status: 'up', latency_ms: 0.32, is_local: false, is_blacklisted: false },
  { name: 'ai-ollama01', fqdn: 'ai-ollama01.mesh.local', ip: '10.0.70.228', role: 'ai', tier: 'AI Satellite', status: 'up', latency_ms: 0.34, is_local: false, is_blacklisted: false },
  { name: 'wrk-bd01', fqdn: 'wrk-bd01.mesh.local', ip: '10.0.70.50', role: 'wrk-bd', tier: 'Worker', status: 'up', latency_ms: 0.38, is_local: false, is_blacklisted: false },
  { name: 'wrk-bd02', fqdn: 'wrk-bd02.mesh.local', ip: '10.0.70.51', role: 'wrk-bd', tier: 'Worker', status: 'up', latency_ms: 0.37, is_local: false, is_blacklisted: false },
  { name: 'wrk-bd03', fqdn: 'wrk-bd03.mesh.local', ip: '10.0.70.52', role: 'wrk-bd', tier: 'Worker', status: 'up', latency_ms: 0.39, is_local: false, is_blacklisted: false },
  { name: 'wrk-bd04', fqdn: 'wrk-bd04.mesh.local', ip: '10.0.70.53', role: 'wrk-bd', tier: 'Worker', status: 'up', latency_ms: 0.40, is_local: false, is_blacklisted: false },
  { name: 'wrk-bd05', fqdn: 'wrk-bd05.mesh.local', ip: '10.0.70.54', role: 'wrk-bd', tier: 'Worker', status: 'up', latency_ms: 0.41, is_local: false, is_blacklisted: false },
  { name: 'wrk-test01', fqdn: 'wrk-test01.mesh.local', ip: '10.0.70.83', role: 'wrk-test', tier: 'Worker', status: 'up', latency_ms: 0.35, is_local: false, is_blacklisted: false },
  { name: 'wrk-test02', fqdn: 'wrk-test02.mesh.local', ip: '10.0.70.95', role: 'wrk-test', tier: 'Target Site', status: 'operator-only', latency_ms: null, is_local: false, is_blacklisted: true },
  { name: 'wrk-test03', fqdn: 'wrk-test03.mesh.local', ip: '10.0.70.80', role: 'wrk-test', tier: 'Worker', status: 'up', latency_ms: 0.34, is_local: false, is_blacklisted: false },
  { name: 'wrk-test04', fqdn: 'wrk-test04.mesh.local', ip: '10.0.70.82', role: 'wrk-test', tier: 'Worker', status: 'up', latency_ms: 0.36, is_local: false, is_blacklisted: false },
  { name: 'wrk-test05', fqdn: 'wrk-test05.mesh.local', ip: '10.0.70.85', role: 'wrk-test', tier: 'Worker', status: 'up', latency_ms: 0.37, is_local: false, is_blacklisted: false },
  { name: 'wrk-test06', fqdn: 'wrk-test06.mesh.local', ip: '10.0.70.249', role: 'wrk-test', tier: 'Worker', status: 'up', latency_ms: 0.38, is_local: false, is_blacklisted: false },
  { name: 'wrk-test07', fqdn: 'wrk-test07.mesh.local', ip: '10.0.70.84', role: 'wrk-test', tier: 'Worker', status: 'up', latency_ms: 0.36, is_local: false, is_blacklisted: false },
  { name: 'spr-pool01', fqdn: 'spr-pool01.mesh.local', ip: '10.0.70.120', role: 'spr-pool', tier: 'Spare Pool', status: 'up', latency_ms: 0.42, is_local: false, is_blacklisted: false },
  { name: 'spr-pool02', fqdn: 'spr-pool02.mesh.local', ip: '10.0.70.183', role: 'spr-pool', tier: 'Spare Pool', status: 'up', latency_ms: 0.43, is_local: false, is_blacklisted: false },
  { name: 'spr-pool03', fqdn: 'spr-pool03.mesh.local', ip: '10.0.70.184', role: 'spr-pool', tier: 'Spare Pool', status: 'up', latency_ms: 0.41, is_local: false, is_blacklisted: false },
  { name: 'spr-pool04', fqdn: 'spr-pool04.mesh.local', ip: '10.0.70.185', role: 'spr-pool', tier: 'Spare Pool', status: 'up', latency_ms: 0.44, is_local: false, is_blacklisted: false },
  { name: 'spr-pool05', fqdn: 'spr-pool05.mesh.local', ip: '10.0.70.149', role: 'spr-pool', tier: 'Spare Pool', status: 'up', latency_ms: 0.45, is_local: false, is_blacklisted: false }
];

export const EXPECTED_42_SHARDS: string[] = [
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

const mockShardsList: CiShardStatus[] = EXPECTED_42_SHARDS.map((name, i) => ({
  name,
  category: name.startsWith('unit-') ? 'python_unit' :
            name.startsWith('int-') ? 'postgres_integration' :
            name.includes('vitest') ? 'vitest_node' : 'browser_e2e',
  status: 'success',
  duration_s: 10 + (i % 30)
}));

export const mockShardsResponse: ShardsResponse = {
  timestamp: '2026-09-22T23:00:00Z',
  repo: 'Mboyle/BD-ci',
  run_id: '16',
  total_shards: 42,
  status: { completed: 42, running: 0, queued: 0 },
  conclusion: { success: 42, failure: 0 },
  failed_shards: [],
  shards: mockShardsList,
  recent_harness_runs: [
    { timestamp: '2026-09-22T22:50:36Z', status: 'PASS', test: 'test_conductor_cycle.py', exit_code: 0, duration_s: 6 }
  ],
  recent_gate_yields: [
    { timestamp: '2026-09-22T21:22:01Z', tool: 'bd-collect-gate', verdict: 'pass', cut_or_test: 'rowh265ok', details: 'tests=1/1 precut=0' }
  ],
  source: 'mock'
};

export const mockAgentsResponse: AgentsResponse = {
  timestamp: '2026-09-22T23:00:00Z',
  total_agents: 5,
  active_agents: 2,
  agents: [
    { seat: 'bd-worker-W1-A', role: 'worker', type: 'claude', host: 'hub-mesh01', pid: 1124238, claimed_at: '2026-09-22T21:08:28Z', model: 'claude-opus-5-5', status: 'busy', current_cut: 'row1017' },
    { seat: 'bd-agy-worker-g1', role: 'worker', type: 'antigravity', host: 'hub-mesh01', pid: 3697945, claimed_at: '2026-09-21T23:21:01Z', model: 'gemini-1.5-pro', status: 'idle' },
    { seat: 'bd-cx-worker-swap', role: 'worker', type: 'codex', host: 'hub-mesh01', pid: 184512, claimed_at: '2026-09-22T20:00:00Z', model: 'gpt-5.6-terra', status: 'idle' },
    { seat: 'bd-grok-worker-1', role: 'worker', type: 'grok', host: 'wrk-bd01', pid: 219481, claimed_at: '2026-09-22T21:40:00Z', model: 'grok-2', status: 'busy', current_cut: 'row1045' },
    { seat: 'bd-kimi-worker-1', role: 'worker', type: 'kimi', host: 'wrk-bd02', pid: 310842, claimed_at: '2026-09-22T22:15:00Z', model: 'kimi-k1.5', status: 'idle' }
  ],
  source: 'mock'
};

export const mockArchitectureResponse: ArchitectureResponse = {
  timestamp: '2026-09-22T23:00:00Z',
  topology: {
    total_nodes: mockNodes.length,
    online_nodes: 26,
    isolated_nodes: 1,
    total_agents: mockAgentsResponse.total_agents,
    active_agents: mockAgentsResponse.active_agents,
    esxi_clones: [
      {
        id: 'clone-vm-01',
        name: 'vm-ephemeral-shard01',
        hypervisor_host: 'spr-pool-1 (10.0.70.120)',
        target_ip: '10.0.70.121',
        status: 'running',
        role: 'ci_shard_runner',
        vcpus: 4,
        memory_mb: 8192,
        active_workload: 'CI Shard 14: test_v3_66_939'
      },
      {
        id: 'clone-vm-02',
        name: 'vm-ephemeral-shard02',
        hypervisor_host: 'spr-pool-2 (10.0.70.149)',
        target_ip: '10.0.70.150',
        status: 'running',
        role: 'ephemeral_sandbox',
        vcpus: 4,
        memory_mb: 8192,
        active_workload: 'TSV Atomic Verification Worker'
      },
      {
        id: 'clone-vm-03',
        name: 'vm-ephemeral-red-iso',
        hypervisor_host: 'spr-pool-3 (10.0.70.183)',
        target_ip: '10.0.70.184',
        status: 'running',
        role: 'red_isolation',
        vcpus: 8,
        memory_mb: 16384,
        active_workload: 'Destructive Concurrency Sandbox'
      },
      {
        id: 'clone-vm-04',
        name: 'vm-ephemeral-standby',
        hypervisor_host: 'spr-pool-4 (10.0.70.185)',
        target_ip: '10.0.70.186',
        status: 'idle',
        role: 'ephemeral_sandbox',
        vcpus: 4,
        memory_mb: 8192,
        active_workload: 'Ready for lease'
      }
    ],
    tiers: {
      control_plane: mockNodes.filter(n => n.role === 'hub' || n.role === 'ops' || n.role === 'stg'),
      ai_satellite: mockNodes.filter(n => n.role === 'ai'),
      workers: mockNodes.filter(n => (n.role === 'wrk-bd' || n.role === 'wrk-test') && !n.is_blacklisted),
      esxi_spare_pool: mockNodes.filter(n => n.role === 'spr-pool'),
      isolated_boundary: mockNodes.filter(n => n.is_blacklisted)
    },
    agent_allocations: {
      'hub-mesh01': mockAgentsResponse.agents
    }
  },
  source: 'mock'
};

