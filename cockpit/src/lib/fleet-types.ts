export type Availability = 'live' | 'unknown';
export const HISTORY_RANGES = [ ['all', 'All history'], ['5m', 'Last 5m'], ['30m', 'Last 30m'], ['1h', 'Last 1h'],
  ['6h', 'Last 6h'], ['12h', 'Last 12h'], ['24h', 'Last 24h'], ['7d', 'Last 7 days'], ['14d', 'Last 14 days'],
  ['30d', 'Last 30 days'], ['3mo', 'Last 3 months'], ['6mo', 'Last 6 months'], ['1yr', 'Last 1 year'] ] as const;
export type HistoryRange = typeof HISTORY_RANGES[number][0];
export interface SourceObservation { state: Availability; observed_at: string | null; stale: boolean; }
export interface FleetAgent { role: string; seat: string; pid: number; host: string; node: string | null; claimed_at: string; model: null; }
export interface FleetNode { name: string; ip: string; status: string; observed_at: string; stale: boolean; agents: FleetAgent[]; }
export interface FleetQuota { name: string; five_hour_used_pct: number | null; weekly_used_pct: number | null;
  resets_at: string | null; weekly_resets_at: string | null; observed_at: string | null; stale: boolean;
  monthly_used_pct?: number | null; status?: 'observed' | 'unavailable' | 'auth_failed' | 'limited' | 'stale';
  reason?: string; five_hour_reason?: string; long_window_reason?: string; }
export function longQuotaWindow(quota: FleetQuota): { label: 'Monthly' | 'Weekly'; value: number | null } {
  const monthly = quota.monthly_used_pct != null || (quota.name === 'Kimi' && quota.weekly_used_pct === null);
  return { label: monthly ? 'Monthly' : 'Weekly', value: monthly ? quota.monthly_used_pct ?? null : quota.weekly_used_pct };
}
export interface UsageSummary { turns: number; total_ctx: number | null; cache_read: number | null;
  fresh_tokens: number | null; cache_creation_tokens: number | null; out_tokens: number | null; cache_efficiency_pct: number | null; }
export interface PlatformWindow { metrics: (UsageSummary & { cost_usd?: number | null }) | null;
  reason: string | null; unknown_metrics: Record<string, string>; }
export interface PlatformModel { platform: string; provider: string; model: string | null;
  coverage: { first_at: string | null; last_at: string | null }; current: PlatformWindow; history: PlatformWindow;
  quota_scope?: string; quotas?: FleetQuota[]; }
export interface FleetCost { source: Availability; reason?: string; observed_at?: string | null; since?: string; until?: string; window_hours?: number;
  range?: HistoryRange; bucket_seconds?: number;
  current_window?: { since: string; until: string; seconds: number }; platform_models?: PlatformModel[];
  coverage?: { first_at: string | null; last_at: string | null; partial_window: boolean; source_counts: Record<string, number>;
    backfill: { inspected_hosts?: number; total_hosts?: number; inaccessible_hosts?: number; unsupported_events?: number;
      collected_at?: string; reason?: string } | null };
  total_responses: number | null; totals: UsageSummary | null;
  breakdown: (UsageSummary & { key: string; provider?: string; cost_usd: number | null })[];
  series: (UsageSummary & { hour: string })[];
  aggregate: { total_cost_usd: number | null; priced_cost_usd: number | null; projected_24h_cost_usd: number | null;
    priced_responses: number | null; unpriced_responses: number | null; pricing: string };
}
export interface FleetSnapshot {
  timestamp: string; sources: Record<string, SourceObservation>;
  topology: { total_nodes: number | null; online_nodes: number | null; nodes: FleetNode[]; unmapped_agents: FleetAgent[] };
  quotas: FleetQuota[];
  steering: { agents: FleetAgent[]; total_agents: number | null; working: number | null; idle: number | null;
    gone: number | null; unknown: number | null; queued: number | null; open_rows: number | null; version: string | null; observed_at: string | null };
  telemetry: FleetCost;
}
