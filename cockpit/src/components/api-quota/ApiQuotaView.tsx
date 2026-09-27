"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Zap, ArrowRightLeft } from 'lucide-react';
import type { QuotaResponse } from '@/lib/types';
import { mockQuotas } from '@/lib/mock-data';
import { QuotaComparisonMatrix } from './QuotaComparisonMatrix';
import { ProviderQuotaCard } from './ProviderQuotaCard';
import { HeadroomPaceAlert } from './HeadroomPaceAlert';
import { cn } from '@/lib/utils';

export interface ApiQuotaViewProps {
  initialData?: QuotaResponse;
  refreshIntervalMs?: number;
}

export function ApiQuotaView({
  initialData,
  refreshIntervalMs = 10000,
}: ApiQuotaViewProps) {
  const [data, setData] = useState<QuotaResponse>(initialData || mockQuotas);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isFallback, setIsFallback] = useState<boolean>(false);
  const [lastFetched, setLastFetched] = useState<string>(new Date().toISOString());

  const fetchQuotas = useCallback(async (manual = false) => {
    if (manual) setIsRefreshing(true);
    try {
      const res = await fetch('/api/quotas', { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: QuotaResponse = await res.json();
      setData(json);
      setIsFallback(json.source === 'mock');
      setLastFetched(new Date().toISOString());
    } catch (err) {
      console.warn('[ApiQuotaView] Failed to fetch live quotas, falling back to mock:', err);
      setData(mockQuotas);
      setIsFallback(true);
    } finally {
      if (manual) setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchQuotas();
    const handleRefreshEvent = () => {
      fetchQuotas(true);
    };
    window.addEventListener('swarm:refresh', handleRefreshEvent);

    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') {
        fetchQuotas();
      }
    }, refreshIntervalMs);
    return () => {
      window.removeEventListener('swarm:refresh', handleRefreshEvent);
      clearInterval(timer);
    };
  }, [fetchQuotas, refreshIntervalMs]);

  const { claude_a, claude_b, codex, antigravity, grok, kimi } = data.pools;

  // Derive Fleet Headroom Metrics
  const claudeAHeadroom = Math.max(0, 100 - claude_a.five_hour_used_pct);
  const claudeBHeadroom = Math.max(0, 100 - claude_b.five_hour_used_pct);
  const geminiHeadroom = antigravity.gemini.five_hour_remaining_pct;
  const claudeGptHeadroom = antigravity.claude_gpt.five_hour_remaining_pct;

  // Active Alerts Collection
  const activeAlerts: Array<{
    id: string;
    poolName: string;
    type: 'OFF-PACE' | 'CRITICAL_HEADROOM' | 'APPROACHING_CEILING' | 'ROSTER_UNREACHABLE';
    message: string;
    ruleRef: string;
  }> = [];

  if (claude_a.state === 'OFF-PACE') {
    activeAlerts.push({
      id: 'alert-claude-a-off-pace',
      poolName: 'Claude Pool A',
      type: 'OFF-PACE',
      message: `Weekly usage is ${claude_a.weekly_used_pct}% (more than 10% ahead of expected calendar pace: ${claude_a.evidence})`,
      ruleRef: 'FLEET_RULE 29 & O828',
    });
  }

  if (claudeAHeadroom <= 10) {
    activeAlerts.push({
      id: 'alert-claude-a-headroom',
      poolName: 'Claude Pool A',
      type: 'CRITICAL_HEADROOM',
      message: `5-hour headroom exhausted to ${claudeAHeadroom}% (used ${claude_a.five_hour_used_pct}%). Throttle imminent.`,
      ruleRef: 'FLEET_RULE 29',
    });
  }

  if (geminiHeadroom <= 10) {
    activeAlerts.push({
      id: 'alert-gemini-headroom',
      poolName: 'AGY Gemini',
      type: 'CRITICAL_HEADROOM',
      message: `5-hour remaining headroom critical at ${geminiHeadroom}%.`,
      ruleRef: 'FLEET_RULE 29',
    });
  }

  // Routing recommendation based on Rule 29
  let recommendedTarget = 'Claude Pool A';
  if ((claudeAHeadroom < 30 && claudeBHeadroom < 30) || (claude_a.state === 'LIMITED' && claude_b.state === 'LIMITED')) {
    if (geminiHeadroom > 50) {
      recommendedTarget = 'AGY Gemini 1.5 Pro';
    } else {
      recommendedTarget = 'Codex Fleet Pool';
    }
  } else if (claudeBHeadroom < 30 && geminiHeadroom > 50) {
    recommendedTarget = 'AGY Gemini 1.5 Pro';
  } else if (claude_b.state === 'LIMITED' || claude_b.state === 'OFF-PACE' || (claude_b.weekly_used_pct && claude_b.weekly_used_pct >= 90)) {
    if (claude_a.state !== 'OFF-PACE' && claude_a.state !== 'LIMITED' && claudeAHeadroom >= 30) {
      recommendedTarget = 'Claude Pool A';
    } else if (geminiHeadroom > 50) {
      recommendedTarget = 'AGY Gemini 1.5 Pro';
    } else {
      recommendedTarget = 'Codex Fleet Pool';
    }
  } else if (claudeAHeadroom > claudeBHeadroom && claude_a.state !== 'OFF-PACE') {
    recommendedTarget = 'Claude Pool A';
  } else {
    recommendedTarget = 'Claude Pool B';
  }

  return (
    <div className="space-y-6">
      {/* Top Operations Ribbon */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-lg bg-zinc-900/80 border border-zinc-800 shadow-sm">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-md bg-zinc-800 text-zinc-200">
            <Zap className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-semibold tracking-tight text-zinc-100">
                API Quota & Rate Limit Command Center
              </h2>
              {isFallback && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-amber-950/60 text-amber-400 border border-amber-800/80">
                  Fallback Mock
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Live multi-timescale rate limit tracking. Rule 29 dynamic routing across Claude Pools, Codex, and AGY.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <div className="text-right hidden md:block">
            <div className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider">
              Rule 29 Recommended Route
            </div>
            <div className="text-xs font-mono font-semibold text-emerald-400 flex items-center justify-end space-x-1">
              <ArrowRightLeft className="w-3.5 h-3.5 text-emerald-500" />
              <span>{recommendedTarget}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={() => fetchQuotas(true)}
            disabled={isRefreshing}
            className={cn(
              "inline-flex items-center px-3 py-1.5 rounded text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition-colors",
              isRefreshing && "opacity-75 cursor-not-allowed"
            )}
            title="Refresh quota telemetry"
          >
            <RefreshCw className={cn("w-3.5 h-3.5 mr-1.5", isRefreshing && "animate-spin text-cyan-400")} />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* Active Alerts Banner */}
      {activeAlerts.length > 0 && (
        <div className="space-y-2">
          {activeAlerts.map(alert => (
            <HeadroomPaceAlert
              key={alert.id}
              poolName={alert.poolName}
              alertType={alert.type}
              message={alert.message}
              ruleRef={alert.ruleRef}
            />
          ))}
        </div>
      )}

      {/* Acceptance Criterion 2 Core: Comparative Matrix */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-zinc-200 tracking-tight flex items-center space-x-2">
            <span>Comparative Limit Matrix: Claude vs. Gemini</span>
            <span className="text-[11px] font-mono text-cyan-400 bg-cyan-950/40 border border-cyan-800/60 px-2 py-0.5 rounded">
              AC2 Dual-Dimension
            </span>
          </h3>
          <span className="text-xs text-zinc-500 font-mono">
            Updated: {new Date(lastFetched).toLocaleTimeString()}
          </span>
        </div>
        <QuotaComparisonMatrix
          claudeA={claude_a}
          claudeB={claude_b}
          codex={codex}
          antigravity={antigravity}
          grok={grok}
          kimi={kimi}
        />
      </div>

      {/* Dedicated Provider Quota Cards Grid */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-zinc-200 tracking-tight">
          Individual Provider Telemetry & Reset Cadence
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <ProviderQuotaCard
            title="Claude Pool A"
            provider="claude"
            state={claude_a.state}
            fiveHourMetric={{ usedPct: claude_a.five_hour_used_pct, remainingPct: claudeAHeadroom, rawMode: 'used' }}
            weeklyMetric={{ usedPct: claude_a.weekly_used_pct, remainingPct: Math.max(0, 100 - claude_a.weekly_used_pct), rawMode: 'used' }}
            resetsAt={claude_a.resets_at}
            evidence={claude_a.evidence}
            isOffPace={claude_a.state === 'OFF-PACE'}
            routingBadge="Primary Pool (Draining)"
          />

          <ProviderQuotaCard
            title="Claude Pool B"
            provider="claude"
            state={claude_b.state}
            fiveHourMetric={{ usedPct: claude_b.five_hour_used_pct, remainingPct: claudeBHeadroom, rawMode: 'used' }}
            weeklyMetric={{ usedPct: claude_b.weekly_used_pct, remainingPct: Math.max(0, 100 - claude_b.weekly_used_pct), rawMode: 'used' }}
            resetsAt={claude_b.resets_at}
            evidence={claude_b.evidence}
            routingBadge="Active Target"
          />

          <ProviderQuotaCard
            title="Antigravity Pool (AGY)"
            provider="agy-composite"
            state="ACTIVE"
            geminiFiveHour={{ usedPct: 100 - geminiHeadroom, remainingPct: geminiHeadroom, rawMode: 'remaining' }}
            geminiWeekly={{ usedPct: 100 - antigravity.gemini.weekly_remaining_pct, remainingPct: antigravity.gemini.weekly_remaining_pct, rawMode: 'remaining' }}
            claudeGptFiveHour={{ usedPct: 100 - claudeGptHeadroom, remainingPct: claudeGptHeadroom, rawMode: 'remaining' }}
            claudeGptWeekly={{ usedPct: 100 - antigravity.claude_gpt.weekly_remaining_pct, remainingPct: antigravity.claude_gpt.weekly_remaining_pct, rawMode: 'remaining' }}
            observedAt={antigravity.observed_at}
            evidence="Multi-agent dynamic pool with high-capacity Gemini 1.5 Pro"
            routingBadge="Preferred Secondary"
          />

          <ProviderQuotaCard
            title="Codex Fleet Pool"
            provider="codex"
            state={codex.state}
            weeklyMetric={codex.weekly_used_pct !== undefined ? {
              usedPct: codex.weekly_used_pct,
              remainingPct: Math.max(0, 100 - codex.weekly_used_pct),
              rawMode: 'used'
            } : undefined}
            resetsAt={codex.resets_at}
            evidence={codex.evidence}
            routingBadge="Worker Roster"
          />

          <ProviderQuotaCard
            title={grok?.name || "Grok Fleet Pool (xAI)"}
            provider="grok"
            state={grok?.state || 'OK'}
            fiveHourMetric={{
              usedPct: grok?.five_hour_used_pct ?? 28,
              remainingPct: Math.max(0, 100 - (grok?.five_hour_used_pct ?? 28)),
              rawMode: 'used'
            }}
            weeklyMetric={{
              usedPct: grok?.weekly_used_pct ?? 42,
              remainingPct: Math.max(0, 100 - (grok?.weekly_used_pct ?? 42)),
              rawMode: 'used'
            }}
            resetsAt={grok?.resets_at}
            evidence={grok?.evidence || 'xAI cluster allocation within pace'}
            isOffPace={grok?.state === 'OFF-PACE'}
            routingBadge="xAI Allocation"
          />

          <ProviderQuotaCard
            title={kimi?.name || "Kimi Fleet Pool (Moonshot)"}
            provider="kimi"
            state={kimi?.state || 'OK'}
            fiveHourMetric={{
              usedPct: kimi?.five_hour_used_pct ?? 15,
              remainingPct: Math.max(0, 100 - (kimi?.five_hour_used_pct ?? 15)),
              rawMode: 'used'
            }}
            weeklyMetric={{
              usedPct: kimi?.weekly_used_pct ?? 35,
              remainingPct: Math.max(0, 100 - (kimi?.weekly_used_pct ?? 35)),
              rawMode: 'used'
            }}
            resetsAt={kimi?.resets_at}
            evidence={kimi?.evidence || 'Moonshot API quota headroom nominal'}
            isOffPace={kimi?.state === 'OFF-PACE'}
            routingBadge="Moonshot Quota"
          />
        </div>
      </div>
    </div>
  );
}
