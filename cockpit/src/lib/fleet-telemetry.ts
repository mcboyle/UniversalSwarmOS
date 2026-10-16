import fs from 'node:fs';
import path from 'node:path';
import { isIP } from 'node:net';
import { execFileSync } from 'node:child_process';
import type { FleetSnapshot, FleetNode, FleetAgent, FleetQuota, FleetCost, SourceObservation, HistoryRange, UsageSummary, PlatformWindow } from './fleet-types';
import { HISTORY_RANGES } from './fleet-types';

const MODEL_RATES: Record<string, { input: number; output: number; cacheRead: number; cacheWrite?: number; pricingSource?: string }> = {
  'claude-opus-5': { input: 5, output: 25, cacheRead: 0.5, cacheWrite: 10, pricingSource: 'https://platform.claude.com/docs/en/about-claude/pricing; 1h cache-write estimate; TTL unavailable in normalized DB' },
  'claude-opus-5-5': { input: 4, output: 20, cacheRead: 0.2, cacheWrite: 8, pricingSource: 'https://platform.claude.com/docs/en/about-claude/pricing; 1h cache-write estimate; TTL unavailable in normalized DB' },
  'claude-opus-4-6': { input: 15.0, output: 75.0, cacheRead: 1.5 },
  'claude-opus-4-8': { input: 5, output: 25, cacheRead: 0.5, cacheWrite: 10, pricingSource: 'https://platform.claude.com/docs/en/about-claude/pricing; 1h cache-write estimate; TTL unavailable in normalized DB' },
  'claude-sonnet-5': { input: 3.0, output: 15.0, cacheRead: 0.3 },
  'claude-sonnet-4-6': { input: 3.0, output: 15.0, cacheRead: 0.3 },
  'claude-fable-5-1': { input: 10, output: 50, cacheRead: 0.25, cacheWrite: 20, pricingSource: 'https://platform.claude.com/docs/en/about-claude/pricing; 1h cache-write estimate; TTL unavailable in normalized DB' },
  'claude-haiku-4-5': { input: 0.8, output: 4.0, cacheRead: 0.08 },
  'claude-haiku-4-5-20251001': { input: 0.8, output: 4.0, cacheRead: 0.08 },
  'gpt-5.6-terra': { input: 2.5, output: 10.0, cacheRead: 0.25 },
  'gpt-6-astra': { input: 2.5, output: 10.0, cacheRead: 0.25 },
  'gpt-5.6-sol': { input: 2.0, output: 8.0, cacheRead: 0.20 },
  'gpt-6-sol': { input: 2.0, output: 8.0, cacheRead: 0.20 },
  'gemini-1.5-pro': { input: 1.25, output: 5.0, cacheRead: 0.3125 },
  'gemini-3.1-pro': { input: 1.25, output: 5.0, cacheRead: 0.3125 },
  'gemini-3.8-flash-high': { input: 0.15, output: 0.60, cacheRead: 0.0375 },
  'gemini-3.8-flash-medium': { input: 0.15, output: 0.60, cacheRead: 0.0375 },
  'gemini-3.8-flash-low': { input: 0.15, output: 0.60, cacheRead: 0.0375 },
  // Grok (xAI) Models
  'grok-2': { input: 2.0, output: 10.0, cacheRead: 0.20 },
  'grok-2-mini': { input: 0.5, output: 2.0, cacheRead: 0.05 },
  'grok-beta': { input: 5.0, output: 15.0, cacheRead: 0.50 },
  'grok-3': { input: 3.0, output: 15.0, cacheRead: 0.30 },
  'grok-4.7-build-fast': { input: 2.0, output: 10.0, cacheRead: 0.20 },
  // Kimi (Moonshot AI) Models
  'kimi-k1.5': { input: 1.0, output: 3.0, cacheRead: 0.15 },
  'kimi-latest': { input: 1.0, output: 3.0, cacheRead: 0.15 },
  'kimi-code/kimi-for-coding': { input: 1.0, output: 3.0, cacheRead: 0.15 },
  'moonshot-v1-128k': { input: 1.2, output: 3.6, cacheRead: 0.20 },
  'moonshot-v1-32k': { input: 1.2, output: 3.6, cacheRead: 0.20 },
  'moonshot-v1-8k': { input: 1.2, output: 3.6, cacheRead: 0.20 },
  'trivial': { input: 0.8, output: 4.0, cacheRead: 0.08 },
  default: { input: 3.0, output: 15.0, cacheRead: 0.3 }
};
const base = () => process.env.FLEET_PERSIST_DIR || '/home/mboyle/bd-persist';
const stale = (date: string | null) => !date || !Number.isFinite(Date.parse(date)) || Date.now() - Date.parse(date) > 600_000 || Date.parse(date) > Date.now() + 60_000;
const date = (value?: string) => value && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value)) ? value : null;
const observationDate = (value?: string) => date(value) && Date.parse(value!) <= Date.now() + 60_000 ? value! : null;
const percent = (value?: string) => value && /^\d+(\.\d+)?$/.test(value) && Number(value) <= 100 ? Number(value) : null;
function file(name: string): { content: string | null; observation: SourceObservation } {
  try {
    const filename = name === 'HOST-STATE.tsv' ? process.env.HOST_STATE_PATH || path.join(base(), name) : path.join(base(), name);
    const content = fs.readFileSync(filename, 'utf8');
    const observed_at = fs.statSync(filename).mtime.toISOString();
    return { content: content.trim() ? content : null, observation: { state: content.trim() ? 'live' : 'unknown', observed_at, stale: stale(observed_at) } };
  } catch { return { content: null, observation: { state: 'unknown', observed_at: null, stale: true } }; }
}
export function readTopology() {
  const hosts = file('HOST-STATE.tsv'), occupancy = file('ROLE-OCCUPANCY.tsv');
  const nodes: FleetNode[] = [], agents: FleetAgent[] = [];
  const seen = new Set<string>();
  for (const line of hosts.content?.split('\n') || []) {
    const [name, ip, state, observed] = line.replace(/\r$/, '').split('\t');
    if (!name || !isIP(ip || '') || !state || !date(observed) || seen.has(ip)) continue;
    seen.add(ip);
    nodes.push({ name, ip, status: state.toLowerCase() === 'up' ? 'up' : state.toLowerCase() === 'down' ? 'down' : 'UNKNOWN',
      observed_at: observed, stale: stale(observed), agents: [] });
  }
  const aliases = new Map<string, string>();
  for (const node of nodes) { aliases.set(node.name, node.name); aliases.set(node.ip, node.name); }
  try {
    const content = fs.readFileSync(process.env.FLEET_HOSTS_FILE || '/etc/hosts', 'utf8');
    for (const line of content.split('\n')) {
      const [ip, ...names] = line.split('#')[0].trim().split(/\s+/);
      const node = nodes.find(item => item.ip === ip);
      if (node) for (const name of names) aliases.set(name, node.name);
    }
  } catch { /* Unresolved host aliases remain visible as UNKNOWN. */ }
  const claimKeys = new Set<string>();
  for (const line of occupancy.content?.split('\n') || []) {
    if (line.startsWith('#')) continue;
    const [role, seat, pid, host, claimed_at] = line.replace(/\r$/, '').split('\t');
    const key = `${role}\t${seat}\t${host}`;
    if (!role || !seat || !/^\d+$/.test(pid || '') || Number(pid) < 1 || !host || !date(claimed_at) || claimKeys.has(key)) continue;
    claimKeys.add(key);
    const agent: FleetAgent = { role, seat, pid: Number(pid), host, node: aliases.get(host) || null, claimed_at, model: null };
    agents.push(agent);
    nodes.find(node => node.name === agent.node)?.agents.push(agent);
  }
  if (!nodes.length) hosts.observation.state = 'unknown';
  if (!agents.length) occupancy.observation.state = 'unknown';
  return { nodes, agents, hosts: hosts.observation, occupancy: occupancy.observation };
}
export function readQuotas() {
  const usage = file('USAGE.tsv');
  const quotas: FleetQuota[] = [];
  const lines = usage.content?.split('\n').filter(line => line.trim() && !line.startsWith('#')) || [];
  const headers = (lines.shift() || '').replace(/\r$/, '').split('\t');
  let accepted = 0;
  const validHeaders = headers.includes('pool') && headers.includes('fetched_at') && (headers.includes('five_hour_pct') || headers.includes('five_hour_remaining_pct'));
  for (const line of validHeaders ? lines : []) {
    const values = line.replace(/\r$/, '').split('\t');
    if (values.length < headers.length) continue;
    const row: Record<string, string> = Object.fromEntries(headers.map((key, i) => [key, values[i]]));
    if (!row.pool || row.pool === 'pool') continue;
    const observed_at = observationDate(row.quota_observed_at) || observationDate(row.fetched_at);
    if (!observed_at) continue;
    accepted++;
    const common = { resets_at: date(row.resets_at), weekly_resets_at: date(row.weekly_resets), observed_at, stale: stale(observed_at) };
    if (row.pool === 'AGY') {
      for (const [label, prefix] of [['Gemini (AGY)', 'gemini'], ['Claude/GPT (AGY)', 'claude_gpt']]) {
        const five = percent(row[`${prefix}_five_hour_remaining_pct`]), weekly = percent(row[`${prefix}_weekly_remaining_pct`]);
        quotas.push({ name: label, five_hour_used_pct: five === null ? null : 100 - five, weekly_used_pct: weekly === null ? null : 100 - weekly, ...common });
      }
    } else {
      const used = percent(row.five_hour_pct), remaining = percent(row.five_hour_remaining_pct);
      const isGrok = /^(grok|xai)$/i.test(row.pool), isKimi = /^kimi$/i.test(row.pool);
      const name = isGrok ? 'xAI' : isKimi ? 'Kimi' : /^[A-D]$/.test(row.pool) ? `Claude ${row.pool}` : row.pool;
      const auth = /^(AUTH_FAILED|AUTH_ERROR|UNAUTHORIZED|INVALID_SESSION)$/i.test(row.state || '');
      const api = /^(api|xai-api|kimi-api)$/i.test(row.product || '');
      const five = api || auth ? null : used ?? (remaining === null ? null : 100 - remaining);
      quotas.push({ name, five_hour_used_pct: five, weekly_used_pct: api || auth ? null : percent(row.weekly_pct),
        monthly_used_pct: auth ? null : percent(row.monthly_pct), ...common,
        status: auth ? 'auth_failed' : common.stale ? 'stale' : /^(LIMITED|RATE_LIMITED)$/i.test(row.state || '') ? 'limited' : five === null && percent(row.weekly_pct) === null && percent(row.monthly_pct) === null ? 'unavailable' : 'observed',
        reason: auth ? 'Authentication failed: quota probe could not authenticate' : api ? 'API request/token rate limits apply' : five === null ? '5h percentage not reported by the quota probe' : undefined,
        five_hour_reason: api ? 'No 5h window: API rate limits' : (isGrok || isKimi) && five === null ? '5h window unverified for the configured product' : undefined,
        long_window_reason: api ? 'No subscription window: API rate limits' : undefined });
    }
  }
  // Kimi's active /usage watcher measures 5h + MONTHLY, not weekly.
  // Read a bounded tail and project only the structured numeric result.
  let watcher: string = '';
  try {
    const filename = path.join(base(), 'logs/kimi-usage-watch.log');
    const fd = fs.openSync(filename, 'r');
    try { const size = fs.fstatSync(fd).size, tail = Buffer.alloc(Math.min(size, 65536));
      fs.readSync(fd, tail, 0, tail.length, Math.max(0, size - tail.length)); watcher = tail.toString('utf8');
    } finally { fs.closeSync(fd); }
  } catch { /* Missing watcher is reported as unavailable below. */ }
  const kimiReadings = [...watcher.matchAll(/^(\S+) run: five=(\d+|-) monthly=(\d+|-) f403=([01]) state=(\w+)[^\n]*\n/gm)];
  const reading = kimiReadings.reverse().find(match => observationDate(match[1]));
  if (reading && !quotas.some(row => row.name === 'Kimi' && row.observed_at && Date.parse(row.observed_at) >= Date.parse(reading[1]))) {
    const observed_at = observationDate(reading[1]), five = percent(reading[2]), monthly = percent(reading[3]);
    const limited = reading[4] === '1' || /^(LIMITED|RATE_LIMITED|LIMIT)$/i.test(reading[5]) || (five !== null && five >= 98) || monthly === 100;
    const row: FleetQuota = { name: 'Kimi', five_hour_used_pct: five, weekly_used_pct: null, monthly_used_pct: monthly,
      resets_at: null, weekly_resets_at: null, observed_at, stale: stale(observed_at),
      status: stale(observed_at) ? 'stale' : limited ? 'limited' : five !== null || monthly !== null ? 'observed' : 'unavailable',
      reason: stale(observed_at) ? 'Kimi quota observation is stale' : reading[4] === '1' ? '5-hour usage limit reached (provider 403); authentication was not reported as failed' : monthly === 100 ? 'Kimi monthly quota is exhausted' : limited ? 'Kimi quota is limited or at the fleet stop threshold' : five !== null && monthly !== null ? 'Kimi /usage: 5h and monthly limits observed' : monthly !== null ? 'Kimi /usage: monthly limit observed; 5h percentage unavailable' : five !== null ? 'Kimi /usage: 5h limit observed; monthly percentage unavailable' : 'Kimi /usage probe did not return a percentage; cause unverified',
      five_hour_reason: five === null ? '5h percentage unavailable from the /usage probe' : undefined,
      long_window_reason: monthly === null ? 'Monthly percentage unavailable from the /usage probe' : undefined };
    const existing = quotas.findIndex(quota => quota.name === 'Kimi');
    if (existing >= 0) quotas[existing] = row; else quotas.push(row);
    accepted++;
  }
  if (!quotas.some(row => row.name === 'xAI')) {
    const legacy = file('GROK_STATE.tsv');
    const row = legacy.content?.split('\n').find(line => /^grok\t/i.test(line))?.split('\t');
    const weeklyObserved = row && /Weekly SuperGrok:\s*\d/.test(row[5] || '');
    quotas.push({ name: 'xAI', five_hour_used_pct: null, weekly_used_pct: weeklyObserved ? percent(row![3]) : null,
      resets_at: null, weekly_resets_at: weeklyObserved ? date(row![4]) : null, observed_at: null, stale: true,
      status: 'unavailable', reason: row ? 'Quota snapshot is stale; current Grok quota collection is inactive' : 'Grok quota collection is inactive; no current provider observation',
      five_hour_reason: weeklyObserved ? '5h limit not reported: last observed SuperGrok window was weekly' : '5h window unverified for the configured Grok product',
      long_window_reason: weeklyObserved ? undefined : 'Weekly quota unavailable: current Grok quota collection is inactive' });
  }
  for (const name of ['Claude A', 'Claude B', 'Claude C', 'Claude D', 'codex', 'Gemini (AGY)', 'Claude/GPT (AGY)', 'xAI', 'Kimi']) {
    if (!quotas.some(quota => quota.name.toLowerCase() === name.toLowerCase())) quotas.push({ name, five_hour_used_pct: null,
      weekly_used_pct: null, resets_at: null, weekly_resets_at: null, observed_at: null, stale: true,
      status: 'unavailable', reason: name === 'Kimi' ? 'Kimi /usage watcher has no retained observation' : 'Quota collection has no observation for this pool',
      five_hour_reason: name === 'Kimi' ? '5h percentage unavailable from the /usage probe' : undefined,
      long_window_reason: name === 'Kimi' ? 'Monthly percentage unavailable from the /usage probe' : undefined });
  }
  if (!accepted) usage.observation.state = 'unknown';
  const times = quotas.map(quota => quota.observed_at).filter((value): value is string => value !== null);
  usage.observation.observed_at = times.sort((a, b) => Date.parse(b) - Date.parse(a))[0] || null;
  usage.observation.stale = stale(usage.observation.observed_at);
  return { quotas, observation: usage.observation };
}
export function readSteering() {
  const status = file('STATUS.md'), content = status.content || '';
  const poll = content.match(/^POLL[^\n]*working=(\d+)\s+idle=(\d+)\s+gone=(\d+)\s+unknown=(\d+)\s+queued=(\d+)/m);
  const main = content.match(/^main:\s+\S+\s+([\w.-]+)\s+open rows:\s*(\d+)/m);
  const queue = content.match(/^queue:\s*(\d+) briefs waiting/m);
  const observed_at = date(content.match(/^# BD STATUS (\S+)/)?.[1]);
  return { observation: { ...status.observation, state: observed_at && (main || queue || poll) ? 'live' as const : 'unknown' as const, observed_at, stale: stale(observed_at) },
    data: { working: poll ? Number(poll[1]) : null, idle: poll ? Number(poll[2]) : null, gone: poll ? Number(poll[3]) : null,
      unknown: poll ? Number(poll[4]) : null, queued: queue ? Number(queue[1]) : poll ? Number(poll[5]) : null,
      open_rows: main ? Number(main[2]) : null, version: main?.[1] || null, observed_at } };
}
export function parseHistoryRange(value: string | null): HistoryRange | null {
  return value === null ? 'all' : HISTORY_RANGES.some(([range]) => range === value) ? value as HistoryRange : null;
}
const historyCache = new Map<string, { at: number; data: FleetCost }>();
function unknownPlatforms(reason: string) {
  return ['claude', 'codex', 'agy', 'grok', 'kimi'].map(platform => ({ platform, provider: platform, model: null,
    coverage: { first_at: null, last_at: null },
    current: { metrics: null, reason: platform === 'grok' ? 'History only: Grok retired 2026-09-28 (O1468)' : reason, unknown_metrics: {} },
    history: { metrics: null, reason, unknown_metrics: {} } }));
}
function priceUsage(model: string, row: UsageSummary): { cost: number | null; reason?: string } {
  const rate = model === 'default' ? undefined : MODEL_RATES[model];
  if (!rate) return { cost: null, reason: 'No configured price estimate for this measured model ID' };
  if (row.fresh_tokens === null || row.cache_read === null || row.out_tokens === null || row.cache_creation_tokens === null)
    return { cost: null, reason: 'Measured input, output, cache read and cache creation are required for a cost estimate' };
  if (row.cache_creation_tokens > 0 && rate.cacheWrite === undefined)
    return { cost: null, reason: 'Cache creation price or cache lifetime is unavailable for this model' };
  return { cost: ((row.fresh_tokens - row.cache_creation_tokens) * rate.input + row.cache_creation_tokens * (rate.cacheWrite ?? rate.input) + row.cache_read * rate.cacheRead + row.out_tokens * rate.output) / 1_000_000 };
}
function priceWindow(model: string | null, window: PlatformWindow): PlatformWindow {
  if (!window.metrics) return window;
  const priced = priceUsage(model || 'UNKNOWN', window.metrics);
  return { ...window, metrics: { ...window.metrics, cost_usd: priced.cost },
    unknown_metrics: { ...window.unknown_metrics, ...(priced.reason ? { cost_usd: priced.reason } : {}) } };
}
export function readCost(range: HistoryRange = '6h'): FleetCost {
  const aggregate = { total_cost_usd: null as number | null, priced_cost_usd: null as number | null,
    projected_24h_cost_usd: null as number | null, priced_responses: null as number | null, unpriced_responses: null as number | null,
    pricing: 'Configured rate estimates; cache lifetime and unknown model rates are unavailable' };
  try {
    const database = process.env.USAGE_DB_PATH || path.join(base(), 'accounting/usage.sqlite');
    const history = process.env.COCKPIT_HISTORY_DB || path.join(base(), 'harness-work/COCKPIT-O1612/history.sqlite');
    const cacheKey = `${database}:${history}:${range}`;
    const cached = historyCache.get(cacheKey);
    if (cached && Date.now() - cached.at < 30_000) return cached.data;
    const script = process.env.COCKPIT_USAGE_READER || path.resolve(process.cwd(), '../infra/scripts/cockpit_usage.py');
    const raw = JSON.parse(execFileSync('python3', [script, '--database', database, '--range', range,
      '--history-database', history], { encoding: 'utf8', timeout: 30_000, maxBuffer: 2 * 1024 * 1024 })) as FleetCost;
    if (raw.source !== 'live') return { ...raw, platform_models: unknownPlatforms(raw.reason || 'Accounting ledger unavailable'), aggregate };
    aggregate.priced_responses = 0; aggregate.unpriced_responses = 0;
    let priced = 0;
    raw.breakdown = raw.breakdown.map(row => {
      const cost = priceUsage(row.key, row).cost;
      if (cost === null) aggregate.unpriced_responses = (aggregate.unpriced_responses ?? 0) + row.turns;
      else { priced += cost; aggregate.priced_responses = (aggregate.priced_responses ?? 0) + row.turns; }
      return { ...row, cost_usd: cost };
    });
    raw.platform_models = raw.platform_models?.map(row => ({ ...row,
      current: priceWindow(row.model, row.current), history: priceWindow(row.model, row.history) }));
    if (aggregate.priced_responses) aggregate.priced_cost_usd = priced;
    if (raw.total_responses && !aggregate.unpriced_responses) {
      aggregate.total_cost_usd = priced;
      const backfill = raw.coverage?.backfill;
      const complete = !raw.coverage?.partial_window && (!backfill || (!backfill.inaccessible_hosts && !backfill.unsupported_events && !backfill.reason));
      aggregate.projected_24h_cost_usd = raw.window_hours && complete ? priced * 24 / raw.window_hours : null;
    }
    const data = { ...raw, aggregate };
    historyCache.set(cacheKey, { at: Date.now(), data });
    return data;
  } catch { return { source: 'unknown', reason: 'Accounting ledger unavailable', total_responses: null, totals: null, breakdown: [], series: [],
    platform_models: unknownPlatforms('Accounting ledger unavailable'), aggregate }; }
}
export function readSnapshot(range: HistoryRange = 'all'): FleetSnapshot {
  const topology = readTopology(), quotas = readQuotas(), steering = readSteering(), telemetry = readCost(range);
  const scopes: Record<string, string> = {
    claude: 'Shared Claude pools A–D; per-model and per-response pool attribution unavailable',
    codex: 'Shared Codex account; per-model quota attribution unavailable',
    agy: 'Shared AGY Gemini and Claude/GPT budget groups; exact per-model quota attribution unavailable',
    grok: 'History only: Grok retired 2026-09-28; current model quota unavailable',
    kimi: 'Shared Kimi account; per-model quota attribution unavailable'
  };
  const models = telemetry.platform_models?.map(row => ({ ...row,
    quota_scope: scopes[row.platform] || 'Provider quota attribution unavailable',
    quotas: quotas.quotas.filter(quota => row.platform === 'claude' ? /^Claude [A-D]$/.test(quota.name) :
      row.platform === 'agy' ? quota.name.includes('(AGY)') :
      row.platform === 'codex' ? /^codex/i.test(quota.name) : row.platform === 'kimi' ? quota.name === 'Kimi' : false) }));
  return { timestamp: new Date().toISOString(), sources: { hosts: topology.hosts, roles: topology.occupancy,
    quotas: quotas.observation, status: steering.observation,
    accounting: { state: telemetry.source, observed_at: telemetry.observed_at || null, stale: stale(telemetry.observed_at || null) } },
    topology: { total_nodes: topology.hosts.state === 'live' ? topology.nodes.length : null,
      online_nodes: topology.hosts.state === 'live' ? topology.nodes.filter(node => node.status === 'up').length : null,
      nodes: topology.nodes, unmapped_agents: topology.agents.filter(agent => agent.node === null) },
    quotas: quotas.quotas, steering: { ...steering.data, agents: topology.agents,
      total_agents: topology.occupancy.state === 'live' ? new Set(topology.agents.map(agent => agent.seat)).size : null }, telemetry: { ...telemetry, platform_models: models } };
}
