"use client";

import React, { useMemo } from 'react';
import type { CostResponse } from '@/lib/types';
import { ClientOnly } from '@/components/shared/ClientOnly';
import { cn, formatNumber, formatCurrency, formatPercent } from '@/lib/utils';
import { DollarSign, Zap, TrendingUp, Layers, CheckCircle2, AlertCircle } from 'lucide-react';
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend
} from 'recharts';

interface CostCacheProjectionsProps {
  costData: CostResponse;
  timeRange: '5m' | '30m' | '1h' | '6h' | '24h' | '7d';
  onTimeRangeChange: (range: '5m' | '30m' | '1h' | '6h' | '24h' | '7d') => void;
  groupBy?: 'model' | 'thread';
  onGroupByChange?: (groupBy: 'model' | 'thread') => void;
  isLoading: boolean;
}

export function CostCacheProjections({
  costData,
  timeRange,
  onTimeRangeChange,
  groupBy = 'model',
  onGroupByChange,
}: CostCacheProjectionsProps) {
  const aggregate = costData.aggregate || {
    total_context_tokens: 0,
    total_output_tokens: 0,
    total_cache_read_tokens: 0,
    overall_cache_hit_pct: 0,
    total_cost_usd: 0,
    projected_24h_cost_usd: 0
  };

  const isCacheTargetMet = aggregate.overall_cache_hit_pct >= 90.0;
  const projected7DayUsd = aggregate.projected_24h_cost_usd * 7;

  // Generate timeline series for Recharts
  const chartSeries = useMemo(() => {
    const points = [];
    const steps = 12;
    const baseCached = aggregate.total_cache_read_tokens / steps;
    const baseFresh = (aggregate.total_context_tokens - aggregate.total_cache_read_tokens) / steps;
    const baseCost = aggregate.total_cost_usd / steps;

    const getIntervalLabel = (idx: number) => {
      const remaining = steps - idx;
      if (remaining === 0) return 'T-0';
      if (timeRange === '5m') return `T-${remaining * 25}s`;
      if (timeRange === '30m') return `T-${Math.round(remaining * 2.5)}m`;
      if (timeRange === '1h') return `T-${remaining * 5}m`;
      if (timeRange === '6h') return `T-${remaining * 30}m`;
      if (timeRange === '24h') return `T-${remaining * 2}h`;
      return `T-${Math.round(remaining * 0.6)}d`;
    };

    for (let i = 1; i <= steps; i++) {
      points.push({
        interval: getIntervalLabel(i),
        cachedTokens: Math.round(baseCached * (0.8 + 0.4 * (i / steps))),
        freshTokens: Math.round(baseFresh * (0.8 + 0.4 * (i / steps))),
        costUsd: Number((baseCost * i * 0.95).toFixed(2))
      });
    }
    return points;
  }, [aggregate, timeRange]);

  return (
    <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 space-y-4">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-zinc-800">
        <div className="flex items-center space-x-2">
          <Zap className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-zinc-100">
            Token Cost Telemetry & Prefix Cache Projections
          </h3>
        </div>

        {/* Group By & Time Range Selectors */}
        <div className="flex items-center space-x-3">
          {onGroupByChange && (
            <div className="flex items-center space-x-1 border-r border-zinc-800 pr-3">
              <span className="text-[10px] font-mono text-zinc-500 uppercase mr-1">Group:</span>
              {(['model', 'thread'] as const).map(mode => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => onGroupByChange(mode)}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono capitalize transition-colors ${
                    (groupBy || costData.group_by || 'model') === mode
                      ? 'bg-cyan-950/80 text-cyan-400 font-bold border border-cyan-800'
                      : 'bg-zinc-800/80 text-zinc-400 hover:bg-zinc-800 border border-zinc-800'
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>
          )}

          <div className="flex items-center space-x-1.5">
            {(['5m', '30m', '1h', '6h', '24h', '7d'] as const).map(range => (
              <button
                key={range}
                type="button"
                onClick={() => onTimeRangeChange(range)}
                className={`px-2.5 py-1 rounded text-xs font-mono transition-colors ${
                  timeRange === range
                    ? 'bg-zinc-700 text-zinc-100 font-bold border border-zinc-600'
                    : 'bg-zinc-800/80 text-zinc-400 hover:bg-zinc-800 border border-zinc-800'
                }`}
              >
                {range}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Cache Efficiency Card */}
        <div className="p-3 rounded bg-zinc-950/70 border border-zinc-800 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400">
            <span>Cache Efficiency</span>
            {isCacheTargetMet ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
            )}
          </div>
          <div className={`text-xl font-mono font-bold ${isCacheTargetMet ? 'text-emerald-400' : 'text-amber-400'}`}>
            {formatPercent(aggregate.overall_cache_hit_pct)}
          </div>
          <div className="text-[10px] text-zinc-500 font-mono">Target: &gt; 90.0%</div>
        </div>

        {/* Total Context Tokens */}
        <div className="p-3 rounded bg-zinc-950/70 border border-zinc-800 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400">
            <span>Total Context Tokens</span>
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div className="text-xl font-mono font-bold text-zinc-100">
            {formatNumber(aggregate.total_context_tokens)}
          </div>
          <div className="text-[10px] text-zinc-500 font-mono">
            Cached: {formatNumber(aggregate.total_cache_read_tokens)}
          </div>
        </div>

        {/* Cumulative Period Spend */}
        <div className="p-3 rounded bg-zinc-950/70 border border-zinc-800 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400">
            <span>Period Spend</span>
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="text-xl font-mono font-bold text-emerald-400">
            {formatCurrency(aggregate.total_cost_usd)}
          </div>
          <div className="text-[10px] text-zinc-500 font-mono">24h Proj: {formatCurrency(aggregate.projected_24h_cost_usd)}</div>
        </div>

        {/* 7-Day Spend Projection */}
        <div className="p-3 rounded bg-zinc-950/70 border border-zinc-800 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400">
            <span>7-Day Projected Burn</span>
            <TrendingUp className="w-3.5 h-3.5 text-purple-400" />
          </div>
          <div className="text-xl font-mono font-bold text-purple-300">
            {formatCurrency(projected7DayUsd)}
          </div>
          <div className="text-[10px] text-zinc-500 font-mono">Based on current velocity</div>
        </div>
      </div>

      {/* Chart Canvas Wrapped in ClientOnly to Guarantee Zero Hydration Mismatches */}
      <div className="h-72 w-full pt-2">
        <ClientOnly fallback={<div className="h-full flex items-center justify-center text-xs font-mono text-zinc-500">Loading Recharts Telemetry Canvas...</div>}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartSeries} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
              <XAxis dataKey="interval" stroke="#71717a" fontSize={11} fontFamily="monospace" />
              <YAxis
                yAxisId="tokens"
                stroke="#71717a"
                fontSize={11}
                fontFamily="monospace"
                tickFormatter={(val) => `${(val / 1_000_000).toFixed(0)}M`}
              />
              <YAxis
                yAxisId="cost"
                orientation="right"
                stroke="#10b981"
                fontSize={11}
                fontFamily="monospace"
                tickFormatter={(val) => `$${val}`}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', borderRadius: '6px' }}
                labelStyle={{ color: '#f4f4f5', fontFamily: 'monospace' }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace', paddingTop: '10px' }} />
              <Area
                yAxisId="tokens"
                type="monotone"
                dataKey="cachedTokens"
                name="Cached Tokens (Cyan)"
                fill="#06b6d4"
                fillOpacity={0.15}
                stroke="#06b6d4"
                strokeWidth={1.5}
              />
              <Area
                yAxisId="tokens"
                type="monotone"
                dataKey="freshTokens"
                name="Fresh Input Tokens (Purple)"
                fill="#a855f7"
                fillOpacity={0.15}
                stroke="#a855f7"
                strokeWidth={1.5}
              />
              <Line
                yAxisId="cost"
                type="monotone"
                dataKey="costUsd"
                name="Cumulative Spend USD ($)"
                stroke="#10b981"
                strokeWidth={2}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </ClientOnly>
      </div>

      {/* Model Breakdown Table */}
      {costData.breakdown && costData.breakdown.length > 0 && (
        <div className="pt-2 border-t border-zinc-800">
          <div className="text-xs font-mono text-zinc-400 mb-2 font-semibold">
            Token & Cost Breakdown by {costData.group_by === 'thread' ? 'Thread' : 'Model'}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500">
                  <th className="py-1.5 px-2">{costData.group_by === 'thread' ? 'Thread UUID' : 'Model Key'}</th>
                  <th className="py-1.5 px-2">Turns</th>
                  <th className="py-1.5 px-2">Total Context</th>
                  <th className="py-1.5 px-2">Cache Read</th>
                  <th className="py-1.5 px-2">Efficiency %</th>
                  <th className="py-1.5 px-2 text-right">Cost (USD)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40">
                {costData.breakdown.map((row) => {
                  const isGrok = row.key.toLowerCase().startsWith('grok');
                  const isKimi = row.key.toLowerCase().startsWith('kimi') || row.key.toLowerCase().startsWith('moonshot');
                  return (
                    <tr key={row.key} className="hover:bg-zinc-950/40 text-zinc-300">
                      <td className="py-1.5 px-2 font-semibold text-zinc-100">
                        <span className="flex items-center space-x-1.5">
                          <span className={cn(
                            isGrok ? "text-orange-400 font-bold" :
                            isKimi ? "text-teal-400 font-bold" :
                            row.key.startsWith('claude') ? "text-purple-300" :
                            row.key.startsWith('gpt') ? "text-amber-300" :
                            "text-zinc-100"
                          )}>
                            {row.key}
                          </span>
                          {isGrok && (
                            <span className="px-1 py-0.2 rounded text-[9px] uppercase font-bold bg-orange-950/70 text-orange-400 border border-orange-800/80">
                              xAI
                            </span>
                          )}
                          {isKimi && (
                            <span className="px-1 py-0.2 rounded text-[9px] uppercase font-bold bg-teal-950/70 text-teal-400 border border-teal-800/80">
                              Moonshot
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="py-1.5 px-2">{row.turns}</td>
                      <td className="py-1.5 px-2">{formatNumber(row.total_ctx)}</td>
                      <td className="py-1.5 px-2 text-cyan-400">{formatNumber(row.cache_read)}</td>
                      <td className="py-1.5 px-2">
                        <span className={row.cache_efficiency_pct >= 90 ? 'text-emerald-400 font-bold' : 'text-amber-400'}>
                          {formatPercent(row.cache_efficiency_pct)}
                        </span>
                      </td>
                      <td className="py-1.5 px-2 text-right text-emerald-400">{formatCurrency(row.cost_usd)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
