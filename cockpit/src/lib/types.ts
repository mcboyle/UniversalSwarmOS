// src/lib/types.ts

// ==========================================
// 1. Quota & Rate Limit Types
// ==========================================

export interface ClaudePoolQuota {
  name: string;
  state: 'OK' | 'OFF-PACE' | 'FAILOVER' | 'STOP' | 'LIMITED' | 'UNKNOWN' | string;
  five_hour_used_pct: number;
  weekly_used_pct: number;
  resets_at: string | null;
  evidence: string;
}

export interface CodexQuota {
  name: string;
  state: 'OK' | 'LIMITED' | 'UNKNOWN' | string;
  evidence: string;
  weekly_used_pct?: number;
  resets_at?: string | null;
}

export interface AntigravityQuota {
  name: string;
  observed_at: string;
  state?: string;
  gemini: {
    five_hour_remaining_pct: number;
    weekly_remaining_pct: number;
  };
  claude_gpt: {
    five_hour_remaining_pct: number;
    weekly_remaining_pct: number;
  };
}

export interface ProviderStandardQuota {
  name: string;
  state: 'OK' | 'LIMITED' | 'UNKNOWN' | string;
  five_hour_used_pct: number;
  weekly_used_pct: number;
  resets_at: string | null;
  evidence: string;
}

export interface QuotaResponse {
  timestamp: string;
  pools: {
    claude_a: ClaudePoolQuota;
    claude_b: ClaudePoolQuota;
    codex: CodexQuota;
    antigravity: AntigravityQuota;
    grok?: ProviderStandardQuota;
    kimi?: ProviderStandardQuota;
  };
  source?: 'live' | 'mock';
}

// ==========================================
// 2. Swarm Queue Types
// ==========================================

export interface QueueItem {
  index: number;
  timestamp: string;
  seat: string;
  row: string; // Task slug (e.g. "row1033", "row1015-red")
  status: 'dispatched' | 'started' | 'done' | 'aborted' | 'gone' | 'resent' | 'nudged1' | 'nudged2' | 'nudged3' | 'nudged4' | string;
  brief_path: string;
  is_active: boolean;
}

export interface QueueResponse {
  timestamp: string;
  total_entries: number;
  active_count: number;
  completed_count: number;
  items: QueueItem[];
  source?: 'live' | 'mock';
}

export interface QueueReorderPayload {
  action: 'reorder';
  ordered_row_ids: string[]; // List of row task slugs in desired priority order
  target?: string;
}

export interface QueueReorderResponse {
  success: boolean;
  reordered_count: number;
  timestamp: string;
  message: string;
}

// ==========================================
// 3. Token Cost & Cache Telemetry Types
// ==========================================

export interface ModelUsageSummary {
  key: string;
  turns: number;
  total_ctx: number;
  out_tokens: number;
  cache_read: number;
  cache_efficiency_pct: number;
  mean_ctx: number;
  max_ctx: number;
  cost_usd: number;
}

export interface CostAggregate {
  total_context_tokens: number;
  total_output_tokens: number;
  total_cache_read_tokens: number;
  overall_cache_hit_pct: number;
  total_cost_usd: number;
  projected_24h_cost_usd: number;
}

export interface CostResponse {
  since: string;
  group_by: string;
  total_responses: number;
  aggregate: CostAggregate;
  breakdown: ModelUsageSummary[];
  source?: 'live' | 'mock';
}

// ==========================================
// 4. Cluster Node Topology Types
// ==========================================

export interface ClusterNode {
  name: string;
  fqdn: string;
  ip: string;
  tier: string;
  role?: 'hub' | 'ops' | 'stg' | 'ai' | 'wrk-bd' | 'wrk-test' | 'spr-pool' | string;
  status: 'up' | 'down' | 'operator-only' | 'unprobed' | 'isolated' | string;
  latency_ms: number | null;
  is_local: boolean;
  is_blacklisted: boolean;
}

export interface NodesResponse {
  timestamp: string;
  total_nodes: number;
  up_nodes: number;
  blacklisted_count: number;
  nodes: ClusterNode[];
  source?: 'live' | 'mock';
}

// ==========================================
// 5. CI/CD Shard Health Types
// ==========================================

export interface CiShardStatus {
  name: string;
  category: 'python_unit' | 'browser_e2e' | 'vitest_node' | 'postgres_integration' | 'gate_scope' | string;
  status: 'success' | 'failure' | 'running' | 'queued' | 'skipped' | string;
  duration_s: number | null;
  error_class?: string; // e.g. "BD-CI-01", "BD-CI-04"
  error_summary?: string;
}

export interface HarnessRunRecord {
  timestamp: string;
  status: 'PASS' | 'FAIL' | string;
  test: string;
  exit_code: number;
  duration_s: number;
}

export interface GateYieldRecord {
  timestamp: string;
  tool: string;
  verdict: 'pass' | 'caught' | 'UNKNOWN' | 'fail' | string;
  cut_or_test: string;
  details: string;
}

export interface ShardsResponse {
  timestamp: string;
  repo: string;
  run_id: string;
  total_shards: number;
  status: {
    completed: number;
    running: number;
    queued: number;
  };
  conclusion: {
    success: number;
    failure: number;
  };
  failed_shards: string[];
  shards: CiShardStatus[];
  recent_harness_runs: HarnessRunRecord[];
  recent_gate_yields: GateYieldRecord[];
  source?: 'gitea' | 'local_ledger' | 'mock';
}

// ==========================================
// 6. Agent Configuration & Swarm Types
// ==========================================

export interface AgentSeatConfig {
  seat: string;
  role: string;
  type: 'antigravity' | 'claude' | 'codex' | 'grok' | 'kimi';
  host: string;
  pid: number | null;
  claimed_at: string;
  model: string;
  status: 'idle' | 'busy' | 'offline' | 'paused';
  current_cut?: string;
  turn_cap?: number;
  reasoning_effort?: 'none' | 'low' | 'medium' | 'high' | 'native';
}

export interface AgentsResponse {
  timestamp: string;
  total_agents: number;
  active_agents: number;
  agents: AgentSeatConfig[];
  source?: 'live' | 'mock';
}

export interface AgentConfigUpdatePayload {
  seat: string;
  model?: string;
  reasoning_effort?: 'none' | 'low' | 'medium' | 'high' | 'native';
  turn_cap?: number;
  status?: 'idle' | 'busy' | 'offline' | 'paused';
}

// ==========================================
// 7. Architecture Visualizer & Topology Types
// ==========================================

export interface EsxiCloneInfo {
  id: string;
  name: string;
  hypervisor_host: string;
  target_ip: string;
  status: 'running' | 'idle' | 'provisioning' | 'offline';
  role: 'ephemeral_sandbox' | 'ci_shard_runner' | 'red_isolation';
  vcpus: number;
  memory_mb: number;
  active_workload?: string;
}

export interface ArchitectureTopology {
  total_nodes: number;
  online_nodes: number;
  isolated_nodes: number;
  total_agents: number;
  active_agents: number;
  esxi_clones: EsxiCloneInfo[];
  tiers: {
    control_plane: ClusterNode[];
    ai_satellite: ClusterNode[];
    workers: ClusterNode[];
    esxi_spare_pool: ClusterNode[];
    isolated_boundary: ClusterNode[];
  };
  agent_allocations: Record<string, AgentSeatConfig[]>;
}

export interface ArchitectureResponse {
  timestamp: string;
  topology: ArchitectureTopology;
  source: 'live' | 'mock';
}
