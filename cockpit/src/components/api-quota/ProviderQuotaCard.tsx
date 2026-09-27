"use client";

import React from 'react';
import { cn } from '@/lib/utils';
import { DualQuotaProgress } from './DualQuotaProgress';
import { ResetCountdownClock } from './ResetCountdownClock';
import { Server, AlertTriangle, CheckCircle } from 'lucide-react';

export interface ProviderQuotaCardProps {
  title: string;
  provider: 'claude' | 'gemini' | 'codex' | 'agy-composite' | 'grok' | 'kimi';
  state: string;
  fiveHourMetric?: { usedPct: number; remainingPct: number; rawMode: 'used' | 'remaining' };
  weeklyMetric?: { usedPct: number; remainingPct: number; rawMode: 'used' | 'remaining' };
  // Composite AGY props
  geminiFiveHour?: { usedPct: number; remainingPct: number; rawMode: 'used' | 'remaining' };
  geminiWeekly?: { usedPct: number; remainingPct: number; rawMode: 'used' | 'remaining' };
  claudeGptFiveHour?: { usedPct: number; remainingPct: number; rawMode: 'used' | 'remaining' };
  claudeGptWeekly?: { usedPct: number; remainingPct: number; rawMode: 'used' | 'remaining' };
  resetsAt?: string | null;
  observedAt?: string;
  evidence: string;
  isOffPace?: boolean;
  routingBadge?: string;
}

export function ProviderQuotaCard({
  title,
  provider,
  state,
  fiveHourMetric,
  weeklyMetric,
  geminiFiveHour,
  geminiWeekly,
  claudeGptFiveHour,
  claudeGptWeekly,
  resetsAt,
  observedAt,
  evidence,
  isOffPace = false,
  routingBadge,
}: ProviderQuotaCardProps) {
  return (
    <div className={cn(
      "flex flex-col justify-between p-4 rounded-lg bg-zinc-900 border transition-all shadow-sm",
      isOffPace
        ? "border-amber-700/80 bg-zinc-900/90 ring-1 ring-amber-500/20"
        : provider === 'grok'
        ? "border-orange-800/60 hover:border-orange-700/80"
        : provider === 'kimi'
        ? "border-teal-800/60 hover:border-teal-700/80"
        : "border-zinc-800 hover:border-zinc-700"
    )}>
      {/* Card Header */}
      <div>
        <div className="flex items-start justify-between gap-2">
          <div>
            <h4 className="text-sm font-semibold text-zinc-100 tracking-tight flex items-center space-x-2">
              <span>{title}</span>
              {provider === 'grok' && (
                <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold uppercase bg-orange-950 text-orange-400 border border-orange-800">
                  xAI
                </span>
              )}
              {provider === 'kimi' && (
                <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold uppercase bg-teal-950 text-teal-400 border border-teal-800">
                  Moonshot
                </span>
              )}
            </h4>
            {routingBadge && (
              <span className={cn(
                "inline-block mt-1 px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider",
                isOffPace
                  ? "bg-amber-950/60 text-amber-400 border border-amber-800"
                  : provider === 'grok'
                  ? "bg-orange-950/60 text-orange-400 border border-orange-800"
                  : provider === 'kimi'
                  ? "bg-teal-950/60 text-teal-400 border border-teal-800"
                  : "bg-zinc-800 text-zinc-400"
              )}>
                {routingBadge}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-1.5">
            {state === 'OFF-PACE' ? (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-950 text-amber-400 border border-amber-800">
                <AlertTriangle className="w-3 h-3 mr-1" />
                OFF-PACE
              </span>
            ) : state === 'OK' || state === 'ACTIVE' ? (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                <CheckCircle className="w-3 h-3 mr-1" />
                {state}
              </span>
            ) : (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-zinc-800 text-zinc-400 border border-zinc-700">
                {state}
              </span>
            )}
          </div>
        </div>

        {/* Card Body: Dual Progress Bars */}
        <div className="mt-4 space-y-4">
          {provider === 'agy-composite' && geminiFiveHour && geminiWeekly ? (
            <div className="space-y-4">
              {/* Sub-track: Gemini */}
              <div className="p-2.5 rounded bg-zinc-950/60 border border-zinc-800/80">
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="font-semibold text-cyan-400 font-mono">AGY Gemini (Gemini 1.5 Pro)</span>
                  <span className="text-[10px] text-cyan-500 font-mono">Dual Quota</span>
                </div>
                <DualQuotaProgress
                  label5h="5h Headroom"
                  usedPct5h={geminiFiveHour.usedPct}
                  remainingPct5h={geminiFiveHour.remainingPct}
                  labelWeekly="Weekly Headroom"
                  usedPctWeekly={geminiWeekly.usedPct}
                  remainingPctWeekly={geminiWeekly.remainingPct}
                  accentColor="cyan"
                />
              </div>

              {/* Sub-track: Claude/GPT */}
              {claudeGptFiveHour && claudeGptWeekly && (
                <div className="p-2.5 rounded bg-zinc-950/60 border border-zinc-800/80">
                  <div className="flex items-center justify-between text-xs mb-2">
                    <span className="font-semibold text-blue-400 font-mono">AGY Claude / GPT Dynamic</span>
                    <span className="text-[10px] text-blue-500 font-mono">Dual Quota</span>
                  </div>
                  <DualQuotaProgress
                    label5h="5h Headroom"
                    usedPct5h={claudeGptFiveHour.usedPct}
                    remainingPct5h={claudeGptFiveHour.remainingPct}
                    labelWeekly="Weekly Headroom"
                    usedPctWeekly={claudeGptWeekly.usedPct}
                    remainingPctWeekly={claudeGptWeekly.remainingPct}
                    accentColor="blue"
                  />
                </div>
              )}
            </div>
          ) : provider === 'codex' ? (
            <div className="space-y-3">
              {weeklyMetric && (
                <div className="p-2.5 rounded bg-zinc-950/60 border border-zinc-800/80">
                  <div className="flex items-center justify-between text-xs mb-2">
                    <span className="font-semibold text-amber-400 font-mono">OpenAI Codex Fleet</span>
                    <span className="text-[10px] text-zinc-500 font-mono">Weekly Rate Limit</span>
                  </div>
                  <DualQuotaProgress
                    label5h="Headroom Status"
                    usedPct5h={fiveHourMetric ? fiveHourMetric.usedPct : (state === 'OK' ? 0 : 100)}
                    remainingPct5h={fiveHourMetric ? fiveHourMetric.remainingPct : (state === 'OK' ? 100 : 0)}
                    labelWeekly="Weekly Limit"
                    usedPctWeekly={weeklyMetric.usedPct}
                    remainingPctWeekly={weeklyMetric.remainingPct}
                    accentColor="amber"
                  />
                </div>
              )}
              <div className="p-2.5 rounded bg-zinc-950/60 border border-zinc-800 space-y-1">
                <div className="flex items-center space-x-2 text-xs text-zinc-300">
                  <Server className="w-3.5 h-3.5 text-amber-400" />
                  <span className="font-medium">Roster Status</span>
                </div>
                <p className="text-[11px] text-zinc-400 font-mono truncate" title={evidence}>
                  {evidence || 'Codex daemon app-server active'}
                </p>
              </div>
            </div>
          ) : fiveHourMetric && weeklyMetric ? (
            <DualQuotaProgress
              label5h="5-Hour Limit"
              usedPct5h={fiveHourMetric.usedPct}
              remainingPct5h={fiveHourMetric.remainingPct}
              labelWeekly="Weekly Limit"
              usedPctWeekly={weeklyMetric.usedPct}
              remainingPctWeekly={weeklyMetric.remainingPct}
              accentColor={
                provider === 'grok'
                  ? 'amber'
                  : provider === 'kimi'
                  ? 'cyan'
                  : 'purple'
              }
            />
          ) : null}
        </div>
      </div>

      {/* Card Footer: Reset Timer & Evidence */}
      <div className="mt-4 pt-3 border-t border-zinc-800/60 text-xs text-zinc-400 space-y-2">
        {resetsAt && (
          <div className="flex items-center justify-between">
            <span className="text-zinc-500 text-[11px]">5h Window Reset:</span>
            <ResetCountdownClock resetsAt={resetsAt} />
          </div>
        )}
        {observedAt && (
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-zinc-500">Observed:</span>
            <span className="font-mono text-zinc-300">{new Date(observedAt).toLocaleTimeString()}</span>
          </div>
        )}
        {evidence && provider !== 'codex' && (
          <p className="text-[10px] text-zinc-500 font-mono truncate" title={evidence}>
            Evidence: {evidence}
          </p>
        )}
      </div>
    </div>
  );
}
