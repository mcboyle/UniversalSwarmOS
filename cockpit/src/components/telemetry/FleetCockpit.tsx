'use client';

import { useEffect, useState } from 'react';
import { Activity, ArrowUpRight, Clock3, Cpu, Layers3, Radio, RefreshCw, Server, ShieldCheck } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { HISTORY_RANGES, longQuotaWindow } from '@/lib/fleet-types';
import type { FleetSnapshot, SourceObservation, HistoryRange, PlatformModel, FleetQuota } from '@/lib/fleet-types';

const sections = [['architecture', 'Architecture Topology'], ['quotas', 'API Quota & Headroom'],
  ['telemetry', 'Distributed Telemetry'], ['steering', 'Swarm Steering']];
const numeric = (value: number | null | undefined, suffix = '') => value == null ? 'UNKNOWN' : `${new Intl.NumberFormat('en', { maximumFractionDigits: 1, notation: value >= 100_000 ? 'compact' : 'standard' }).format(value)}${suffix}`;
const money = (value: number | null | undefined) => value == null ? 'UNKNOWN' : `$${value.toFixed(2)}`;
const time = (value: string | null | undefined) => value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'UNKNOWN';
function resetIn(value: string | null, now: number) {
  if (!value) return 'UNKNOWN';
  const remaining = Date.parse(value) - now;
  if (remaining <= 0) return 'Window elapsed';
  const minutes = Math.ceil(remaining / 60_000);
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}
function Source({ value }: { value?: SourceObservation }) {
  const label = !value || value.state === 'unknown' ? 'UNKNOWN' : value.stale ? 'STALE' : 'OBSERVED';
  return <span className={`rounded-full border px-2 py-1 text-[10px] tracking-widest ${label === 'OBSERVED' ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300' : 'border-amber-500/20 bg-amber-500/10 text-amber-300'}`}>{label}</span>;
}
function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="rounded-xl border border-white/[0.07] bg-[#101722] px-5 py-4">
    <div className="text-xs text-slate-400">{label}</div><div className={`${value === 'UNKNOWN' ? 'text-lg' : 'text-3xl'} mt-2 font-semibold tracking-tight text-slate-100`}>{value}</div>
    <div className="mt-2 text-[11px] text-slate-500">{detail}</div></div>;
}
function Meter({ value, reason }: { value: number | null; reason?: string }) {
  if (value == null) return <span className="block max-w-48 text-[11px] text-amber-300">{reason || 'No percentage reported by the quota probe'}</span>;
  return <div className="min-w-24"><div className="mb-1.5 text-xs tabular-nums">{value.toFixed(1)}%</div>
    <div role="meter" aria-label="Quota used" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value} className="h-1.5 rounded-full bg-slate-800">
      <div className={`h-full rounded-full ${value > 90 ? 'bg-amber-400' : 'bg-sky-400'}`} style={{ width: `${value}%` }} /></div></div>;
}
function Empty({ message = 'UNKNOWN · awaiting a live observation' }: { message?: string }) {
  return <div className="flex min-h-40 items-center justify-center text-sm text-slate-500">{message}</div>;
}

const platformLabels: Record<string, string> = { claude: 'Claude (A–D)', codex: 'Codex', agy: 'AGY (Gemini)', grok: 'Grok', kimi: 'Kimi' };
const modelColumns = [['turns', 'Responses'], ['total_ctx', 'Input'], ['out_tokens', 'Output'],
  ['cache_read', 'Cache read'], ['cache_creation_tokens', 'Cache creation'], ['cost_usd', 'Estimated cost']] as const;
function quotaHeadroom(quota: FleetQuota) {
  if (quota.stale || quota.status === 'auth_failed' || quota.status === 'unavailable')
    return `${quota.name}: UNKNOWN · ${quota.reason || 'Current observation is stale or unavailable'}`;
  const long = longQuotaWindow(quota);
  return `${quota.name}: 5h ${quota.five_hour_used_pct === null ? `UNKNOWN (${quota.five_hour_reason || quota.reason || 'not reported'})` : `${numeric(100 - quota.five_hour_used_pct)}% remaining`}; ${long.label.toLowerCase()} ${long.value === null ? 'UNKNOWN (not reported)' : `${numeric(100 - long.value)}% remaining`}`;
}
function PlatformTable({ rows, rangeLabel }: { rows: PlatformModel[]; rangeLabel: string }) {
  return <div className="space-y-3">
    <h3 className="text-sm font-semibold">Telemetry by platform and model</h3>
    <p className="text-[11px] text-slate-400">Current = responses retained in the last 5 minutes. Current usage and history refresh every 30 seconds; history follows the selected range. Shared account/pool headroom stays current; exact per-model and historical quota limits are UNKNOWN.</p>
    <p className="text-[11px] text-slate-500">Responses are distinct measured usage records, not request attempts. A normalized optional zero is UNKNOWN unless retained raw fields prove it. Scroll across for all metrics.</p>
    <div className="max-h-[36rem] overflow-auto rounded-xl border border-white/[0.06]">
      <table aria-label="Telemetry by platform and model" className="min-w-[1120px] w-full text-left text-xs">
        <thead className="sticky top-0 z-10 bg-[#101722] text-[10px] uppercase tracking-wider text-slate-500"><tr>
          {['Platform', 'Model ID', 'Window', ...modelColumns.map(([, label]) => label), 'Shared account / pool headroom'].map(label => <th key={label} className="px-3 py-3 font-normal">{label}</th>)}
        </tr></thead>
        <tbody>{rows.flatMap(row => (['current', 'history'] as const).map(window => {
          const value = row[window];
          return <tr key={JSON.stringify([row.provider, row.model, window])} data-platform={row.platform} data-provider={row.provider} data-model={row.model || 'UNKNOWN'} data-window={window} className="border-t border-white/[0.05] align-top">
            <td className="px-3 py-3 text-sky-300">{platformLabels[row.platform] || row.provider}</td>
            <td className="max-w-[220px] px-3 py-3"><span className="break-all font-mono text-slate-200" title={row.model || 'No verified model identity'}>{row.model || 'UNKNOWN'}</span>
              {window === 'history' && row.coverage.first_at && row.coverage.last_at && <p className="mt-1 text-[10px] text-slate-500">{row.coverage.first_at.slice(0, 10)} – {row.coverage.last_at.slice(0, 10)} UTC</p>}</td>
            <td className="max-w-[220px] px-3 py-3"><span className="text-slate-300">{window === 'current' ? 'Current · last 5m' : rangeLabel}</span>
              {value.reason && <p className="mt-1 text-[10px] text-slate-500">{value.reason}</p>}</td>
            {modelColumns.map(([key]) => {
              const metric = value.metrics?.[key];
              const reason = value.reason || value.unknown_metrics[key] || (metric == null ? 'No measured value retained for this metric' : undefined);
              return <td key={key} data-metric={key} data-value={metric == null ? 'UNKNOWN' : String(metric)} title={reason} className="px-3 py-3 font-mono text-slate-300">{key === 'cost_usd' ? metric == null ? 'UNKNOWN' : `$${metric.toFixed(4)}` : numeric(metric)}
                {metric == null && !value.reason && <p className="mt-1 max-w-[160px] font-sans text-[10px] text-slate-500">{reason}</p>}</td>;
            })}
            <td className="max-w-[250px] px-3 py-3 text-[10px] text-slate-500"><a href="#quotas" className="text-sky-400">{row.quota_scope}</a>
              {row.quotas?.map(quota => <p key={quota.name} className="mt-1">{quotaHeadroom(quota)}</p>)}</td>
          </tr>;
        }))}</tbody>
      </table>
    </div>
  </div>;
}

export function FleetCockpit() {
  const [snapshot, setSnapshot] = useState<FleetSnapshot | null>(null);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<HistoryRange>('all');
  useEffect(() => {
    let pending = false, disposed = false;
    const controller = new AbortController();
    const load = async () => {
      if (pending) return;
      pending = true;
      try {
        const response = await fetch(`/api/fleet?range=${range}`, { cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new Error('Telemetry unavailable');
        const data: FleetSnapshot = await response.json();
        if (!disposed) { setSnapshot(data); setError(false); }
      } catch {
        if (!disposed) { setSnapshot(null); setError(true); }
      } finally { pending = false; if (!disposed) setLoading(false); }
    };
    void load();
    const timer = window.setInterval(load, 5000);
    return () => { disposed = true; controller.abort(); window.clearInterval(timer); };
  }, [refresh, range]);
  const now = snapshot ? Date.parse(snapshot.timestamp) : Date.now();
  const totals = snapshot?.telemetry.totals;
  const cost = snapshot?.telemetry.aggregate;
  const steering = snapshot?.steering;
  const history = snapshot?.telemetry;
  const rangeLabel = HISTORY_RANGES.find(([key]) => key === range)?.[1] || range;
  const coverage = history?.coverage;
  const utcDate = (value: string) => new Date(value).toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
  const historyEmpty = history?.source === 'live' ? history.total_responses === 0 ? 'No responses recorded in this window' : 'Cache metrics were not recorded for these responses' : loading ? 'Loading historical observations…' : history?.reason || 'Accounting observations unavailable';
  return <div className="min-h-screen bg-[#080d15] text-slate-200">
    <header className="sticky top-0 z-20 border-b border-white/[0.07] bg-[#080d15]/95 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1800px] items-center justify-between gap-4 px-5 py-4 lg:px-8">
        <div className="flex items-center gap-3"><span className="rounded-xl border border-sky-400/20 bg-sky-400/10 p-2.5 text-sky-300"><Layers3 size={21} /></span>
          <div><div className="text-base font-semibold tracking-tight">Swarm Cockpit</div><div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Fleet operations / live telemetry</div></div></div>
        <div className="flex items-center gap-4 text-xs text-slate-400"><span className="hidden items-center gap-2 sm:flex"><Radio size={13} className={error ? 'text-amber-400' : 'text-sky-400'} />{error ? 'Refresh UNKNOWN' : loading ? 'Connecting' : 'Live · every 5s'}</span>
          <span className="hidden font-mono md:inline">{time(snapshot?.timestamp)}</span>
          <button onClick={() => { setLoading(true); setRefresh(value => value + 1); }} aria-label="Refresh fleet telemetry" className="rounded-lg border border-white/10 p-2 hover:bg-white/5"><RefreshCw size={15} className={loading ? 'animate-spin' : ''} /></button></div>
      </div>
      <nav aria-label="Dashboard panels" className="mx-auto flex max-w-[1800px] gap-6 overflow-x-auto px-5 pb-3 text-xs lg:px-8">
        {sections.map(([id, title]) => <a key={id} href={`#${id}`} className="whitespace-nowrap text-slate-400 transition hover:text-sky-300">{title}</a>)}
      </nav>
    </header>
    <main className="mx-auto max-w-[1800px] space-y-6 p-5 lg:p-8">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs uppercase tracking-[0.2em] text-sky-400">Operations overview</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight lg:text-3xl">One fleet. Four live perspectives.</h1>
        <p className="mt-2 text-sm text-slate-500">Hardware observations, quota windows, measured tokens, and registered seats.</p></div>
        <div className="flex items-center gap-2 text-[11px] text-slate-500"><ShieldCheck size={14} />Read-only observations</div></div>
      {error && <div role="alert" className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-300">Live refresh unavailable. Current fleet state is UNKNOWN.</div>}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.07] bg-[#101722] p-4">
        <label className="flex items-center gap-3 text-sm text-slate-300">History range
          <select aria-label="History range" value={range} onChange={event => { setSnapshot(null); setLoading(true); setRange(event.target.value as HistoryRange); }} className="rounded-lg border border-white/10 bg-[#080d15] px-3 py-2 text-sky-300">
            {HISTORY_RANGES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></label>
        <p className="text-[11px] text-slate-500">History refreshes every 30s. Topology, quotas and seats remain current.</p>
      </div>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Metric label="Inventory nodes" value={numeric(snapshot?.topology.total_nodes)} detail={`${numeric(snapshot?.topology.online_nodes)} recorded up · see observation age`} />
        <Metric label="Registered seats" value={numeric(steering?.total_agents)} detail="Occupancy claims · process liveness unverified" />
        <Metric label={`Responses / ${rangeLabel}`} value={numeric(snapshot?.telemetry.total_responses)} detail="Ledger and retained VM archives · counted once" />
        <Metric label="Prefix cache efficiency" value={numeric(totals?.cache_efficiency_pct, '%')} detail="Measured cache reads / input tokens" />
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <section id="architecture" className="scroll-mt-32 rounded-2xl border border-white/[0.07] bg-[#101722]">
          <div className="flex items-center justify-between border-b border-white/[0.06] p-5"><div className="flex items-center gap-3"><Server size={18} className="text-sky-400" /><h2 className="font-semibold">Architecture Topology</h2></div><Source value={snapshot?.sources.hosts} /></div>
          <div className="p-5"><p className="mb-4 text-xs text-slate-500">Every inventory host, mapped to its registered seats. Status retains the ledger observation.</p>
            {snapshot?.topology.nodes.length ? <div className="grid max-h-[360px] grid-cols-2 gap-2 overflow-y-auto pr-1 md:grid-cols-3">
              {snapshot.topology.nodes.map(node => <div key={node.ip} className="rounded-lg border border-white/[0.07] bg-[#0b111c] p-3">
                <div className="flex items-center justify-between gap-2"><span className="truncate text-xs font-medium">{node.name}</span><span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${node.stale || node.status === 'UNKNOWN' ? 'bg-amber-400' : node.status === 'up' ? 'bg-emerald-400' : 'bg-rose-400'}`} /></div>
                <div className="mt-1 font-mono text-[10px] text-slate-500">{node.ip}</div>
                <div className="mt-3 flex flex-wrap justify-between gap-x-2 gap-y-1 text-[10px]"><span className={node.stale ? 'text-amber-300' : 'text-slate-400'}>{node.status}{node.stale ? ' · STALE' : ''}</span>
                  <span>{snapshot.sources.roles.state === 'live' ? `${new Set(node.agents.map(agent => agent.seat)).size} seats` : 'UNKNOWN seats'}</span></div>
                <div title={node.observed_at} className="mt-1 text-[10px] text-slate-600">Observed {new Date(node.observed_at).toLocaleDateString()} {time(node.observed_at)}</div>
                {!!node.agents.length && <div className="mt-2 truncate text-[10px] text-sky-300" title={node.agents.map(agent => agent.seat).join(', ')}>{node.agents.map(agent => agent.seat).join(', ')}</div>}
              </div>)}
            </div> : <Empty />}
            {!!snapshot?.topology.unmapped_agents.length && <div className="mt-3 text-xs text-amber-300">{snapshot.topology.unmapped_agents.length} seat claims have UNKNOWN node mappings.</div>}
          </div>
        </section>
        <section id="quotas" className="scroll-mt-32 rounded-2xl border border-white/[0.07] bg-[#101722]">
          <div className="flex items-center justify-between border-b border-white/[0.06] p-5"><div className="flex items-center gap-3"><Clock3 size={18} className="text-violet-400" /><h2 className="font-semibold">API Quota &amp; Headroom</h2></div><Source value={snapshot?.sources.quotas} /></div>
          <div className="p-5"><p className="mb-3 text-[11px] text-slate-500">Current provider observations. Scroll across for windows and reset details.</p><div className="overflow-x-auto"><table className="w-full min-w-[590px] text-left text-xs"><thead className="text-[10px] uppercase tracking-wider text-slate-500"><tr><th className="pb-4 font-normal">Provider / pool</th><th className="pb-4 font-normal">5h used</th><th className="pb-4 font-normal">Longer window</th><th className="pb-4 font-normal">5h reset</th></tr></thead>
            <tbody>{snapshot?.quotas.map(quota => { const window = longQuotaWindow(quota); return <tr key={quota.name} className="border-t border-white/[0.05]">
              <td className="py-3 pr-4"><div className="whitespace-nowrap font-medium">{quota.name}</div><div className="mt-1 text-[10px] text-slate-500">{quota.status?.replace('_', ' ').toUpperCase()} {quota.observed_at ? `${time(quota.observed_at)}${quota.stale ? ' · STALE' : ''}` : '· No current observation'}</div>{quota.reason && <div className="mt-1 max-w-52 text-[10px] text-amber-300">{quota.reason}</div>}</td>
              <td className="py-3 pr-5"><Meter value={quota.five_hour_used_pct} reason={quota.five_hour_reason || quota.reason} /></td><td className="py-3 pr-5"><div className="mb-1 text-[10px] text-slate-500">{window.label}</div><Meter value={window.value} reason={quota.long_window_reason || quota.reason} /></td>
              <td title={quota.resets_at || undefined} className="py-3 text-[11px] text-slate-400">{quota.resets_at ? resetIn(quota.resets_at, now) : 'Reset not reported'}{quota.weekly_resets_at && <div className="mt-1 text-[9px] text-slate-500">Weekly: {new Date(quota.weekly_resets_at).toLocaleDateString()}</div>}</td>
            </tr>; })}</tbody></table></div>{!snapshot && <Empty message={loading ? 'Loading provider observations…' : 'Provider observations unavailable'} />}</div>
        </section>
      </div>
      <section id="telemetry" data-history-range={history?.range || ''} className="scroll-mt-32 rounded-2xl border border-white/[0.07] bg-[#101722]">
        <div className="flex items-center justify-between border-b border-white/[0.06] p-5"><div className="flex items-center gap-3"><Activity size={18} className="text-emerald-400" /><h2 className="font-semibold">Distributed Telemetry</h2></div><Source value={snapshot?.sources.accounting} /></div>
        <div className="space-y-5 p-5">
          <div className="space-y-1 text-xs text-slate-400" aria-live="polite">
            <p>{rangeLabel}{history?.since && history.until ? ` · ${new Date(history.since).toLocaleString('en', { timeZone: 'UTC' })} – ${new Date(history.until).toLocaleString('en', { timeZone: 'UTC' })} UTC` : ' · Loading…'}</p>
            {coverage?.first_at && coverage.last_at && <p>Retained coverage: {utcDate(coverage.first_at)} – {utcDate(coverage.last_at)} UTC{coverage.partial_window ? '. Selected range extends before retained records.' : '.'}</p>}
            {coverage?.backfill && <p>{coverage.backfill.inspected_hosts != null ? `${coverage.backfill.inspected_hosts}/${coverage.backfill.total_hosts} fleet VMs inspected; ${coverage.backfill.inaccessible_hosts} inaccessible. ` : ''}{coverage.backfill.reason}{coverage.backfill.unsupported_events ? `${numeric(coverage.backfill.unsupported_events)} legacy usage events lack verified response identities and are excluded from totals.` : ''}</p>}
            {history?.total_responses === 0 && <p>No responses recorded in this window.</p>}
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Metric label="Input tokens" value={numeric(totals?.total_ctx)} detail={`${numeric(totals?.fresh_tokens)} fresh`} />
          <Metric label="Cache reads" value={numeric(totals?.cache_read)} detail={`${numeric(totals?.cache_creation_tokens)} cache creation`} />
          <Metric label={`Estimated cost / ${rangeLabel}`} value={money(cost?.total_cost_usd)} detail={`${money(cost?.priced_cost_usd)} priced subtotal · ${numeric(cost?.unpriced_responses)} unpriced responses`} />
          <Metric label="Estimated 24h projection" value={money(cost?.projected_24h_cost_usd)} detail={`Extrapolated from ${rangeLabel.toLowerCase()}; requires complete coverage and prices`} />
        </div>
          <p className="text-[11px] text-slate-500">Overview and charts use retained normalized accounting. Detailed model rows disclose incomplete raw-field provenance. Configured price estimates; unknown model rates or cache creation prices leave the full cost UNKNOWN.</p>
          {history?.platform_models ? <PlatformTable rows={history.platform_models} rangeLabel={rangeLabel} /> : <Empty message={history?.reason || 'UNKNOWN · accounting ledger unavailable'} />}
          <div className="grid gap-6 lg:grid-cols-2"><div><h3 className="mb-4 text-xs text-slate-400">Cache efficiency by platform and model</h3>
            {snapshot?.telemetry.breakdown.some(row => row.cache_efficiency_pct !== null) ? <div className="h-60"><ResponsiveContainer width="100%" height="100%"><BarChart data={snapshot.telemetry.breakdown.map(row => ({ ...row, label: `${row.provider || 'UNKNOWN'} / ${row.key}` }))} margin={{ left: -15, bottom: 40 }}>
              <CartesianGrid stroke="#243043" vertical={false} /><XAxis dataKey="label" tickFormatter={value => String(value).length > 18 ? `${String(value).slice(0, 17)}…` : String(value)} tick={{ fontSize: 9, fill: '#64748b' }} interval="preserveStartEnd" angle={-30} textAnchor="end" height={70} /><YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#64748b' }} />
              <Tooltip contentStyle={{ background: '#101722', border: '1px solid #243043', borderRadius: 8 }} /><Bar dataKey="cache_efficiency_pct" name="Measured cache %" fill="#38bdf8" radius={[3, 3, 0, 0]} />
            </BarChart></ResponsiveContainer></div> : <Empty message={historyEmpty} />}</div>
            <div><h3 className="mb-4 text-xs text-slate-400">Prefix cache efficiency / {rangeLabel.toLowerCase()} · UTC</h3>
              {snapshot?.telemetry.series.some(row => row.cache_efficiency_pct !== null) ? <div className="h-60"><ResponsiveContainer width="100%" height="100%"><LineChart data={snapshot.telemetry.series} margin={{ left: -15 }}>
                <CartesianGrid stroke="#243043" vertical={false} /><XAxis dataKey="hour" tickFormatter={value => (history?.bucket_seconds || 0) >= 3600 ? new Date(String(value)).toLocaleDateString('en', { month: 'short', day: 'numeric', timeZone: 'UTC' }) : `${String(value).slice(11, 16)}`} tick={{ fontSize: 10, fill: '#64748b' }} minTickGap={24} /><YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#64748b' }} />
                <Tooltip labelFormatter={value => `${new Date(String(value)).toLocaleString('en', { timeZone: 'UTC' })} UTC`} contentStyle={{ background: '#101722', border: '1px solid #243043', borderRadius: 8 }} /><Line dataKey="cache_efficiency_pct" name="Measured cache %" stroke="#34d399" strokeWidth={2} dot={false} connectNulls={false} />
              </LineChart></ResponsiveContainer></div> : <Empty message={historyEmpty} />}</div></div>
        </div>
      </section>
      <section id="steering" className="scroll-mt-32 rounded-2xl border border-white/[0.07] bg-[#101722]">
        <div className="flex items-center justify-between border-b border-white/[0.06] p-5"><div className="flex items-center gap-3"><Cpu size={18} className="text-amber-400" /><h2 className="font-semibold">Swarm Steering</h2></div><div className="flex gap-2"><Source value={snapshot?.sources.status} /><Source value={snapshot?.sources.roles} /></div></div>
        <div className="p-5"><div className="mb-5 flex flex-wrap gap-5 text-xs text-slate-400">
          {[['Working', steering?.working], ['Idle', steering?.idle], ['Queued', steering?.queued], ['Open rows', steering?.open_rows]].map(([label, value]) => <div key={String(label)}>{label} <span className="ml-2 font-mono text-slate-200">{numeric(value as number | null | undefined)}</span></div>)}
          <div>Version <span className="ml-2 font-mono text-slate-200">{steering?.version || 'UNKNOWN'}</span></div></div>
          <p className="mb-4 text-[11px] text-slate-500">Registered role assignments. Model configuration and process liveness are UNKNOWN in the occupancy ledger.</p>
          <div className="max-h-80 overflow-auto"><table className="w-full text-left text-xs"><thead className="sticky top-0 bg-[#101722] text-[10px] uppercase tracking-wider text-slate-500"><tr>{['Seat', 'Role', 'Node', 'PID claim', 'Model'].map(label => <th key={label} className="pb-3 font-normal">{label}</th>)}</tr></thead>
            <tbody>{steering?.agents.map(agent => <tr key={`${agent.role}:${agent.seat}:${agent.host}`} className="border-t border-white/[0.05]">
              <td className="py-3 pr-4 font-mono text-sky-300">{agent.seat}</td><td className="pr-4">{agent.role}</td><td className="pr-4 text-slate-400">{agent.node || 'UNKNOWN'}</td><td className="pr-4 font-mono text-slate-500">{agent.pid}</td><td className="text-slate-600">UNKNOWN</td>
            </tr>)}</tbody></table>{!steering?.agents.length && <Empty />}</div>
        </div>
      </section>
      <footer className="flex flex-wrap items-center justify-between gap-3 py-2 text-[10px] text-slate-600"><span className="flex items-center gap-2"><ArrowUpRight size={12} />Fleet ledgers · accounting responses · no generated telemetry</span>
        <span>{snapshot ? `Snapshot ${new Date(snapshot.timestamp).toLocaleString()}` : 'Snapshot UNKNOWN'}</span></footer>
    </main>
  </div>;
}
