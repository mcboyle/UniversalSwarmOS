"use client";

import React from 'react';
import type { ClaudePoolQuota, AntigravityQuota, CodexQuota, ProviderStandardQuota } from '@/lib/types';
import { cn } from '@/lib/utils';
import { CheckCircle2, AlertCircle } from 'lucide-react';
import { ResetCountdownClock } from './ResetCountdownClock';

export interface QuotaComparisonMatrixProps {
  claudeA: ClaudePoolQuota;
  claudeB: ClaudePoolQuota;
  antigravity: AntigravityQuota;
  codex?: CodexQuota;
  grok?: ProviderStandardQuota;
  kimi?: ProviderStandardQuota;
}

export function QuotaComparisonMatrix({
  claudeA,
  claudeB,
  antigravity,
  codex,
  grok,
  kimi,
}: QuotaComparisonMatrixProps) {
  // Claude Computations
  const claudeA_5h_headroom = Math.max(0, 100 - claudeA.five_hour_used_pct);
  const claudeA_week_headroom = Math.max(0, 100 - claudeA.weekly_used_pct);

  const claudeB_5h_headroom = Math.max(0, 100 - claudeB.five_hour_used_pct);
  const claudeB_week_headroom = Math.max(0, 100 - claudeB.weekly_used_pct);

  // Codex Computations
  const codex_week_used = codex?.weekly_used_pct ?? 83;
  const codex_week_headroom = Math.max(0, 100 - codex_week_used);

  // Gemini Computations (Natively reports remaining)
  const gemini_5h_headroom = antigravity.gemini.five_hour_remaining_pct;
  const gemini_5h_used = Math.max(0, 100 - gemini_5h_headroom);
  const gemini_week_headroom = antigravity.gemini.weekly_remaining_pct;
  const gemini_week_used = Math.max(0, 100 - gemini_week_headroom);

  // Claude/GPT Computations
  const claudeGpt_5h_headroom = antigravity.claude_gpt.five_hour_remaining_pct;
  const claudeGpt_5h_used = Math.max(0, 100 - claudeGpt_5h_headroom);
  const claudeGpt_week_headroom = antigravity.claude_gpt.weekly_remaining_pct;
  const claudeGpt_week_used = Math.max(0, 100 - claudeGpt_week_headroom);

  // Grok Computations (Natively reports used)
  const grok_5h_used = grok?.five_hour_used_pct ?? 28;
  const grok_5h_headroom = Math.max(0, 100 - grok_5h_used);
  const grok_week_used = grok?.weekly_used_pct ?? 42;
  const grok_week_headroom = Math.max(0, 100 - grok_week_used);
  const grok_state = grok?.state ?? 'OK';

  // Kimi Computations (Natively reports used)
  const kimi_5h_used = kimi?.five_hour_used_pct ?? 15;
  const kimi_5h_headroom = Math.max(0, 100 - kimi_5h_used);
  const kimi_week_used = kimi?.weekly_used_pct ?? 35;
  const kimi_week_headroom = Math.max(0, 100 - kimi_week_used);
  const kimi_state = kimi?.state ?? 'OK';

  const getHeadroomPill = (headroom: number) => {
    if (headroom <= 10) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-bold bg-rose-950/60 text-rose-400 border border-rose-800">
          {headroom}% CRIT
        </span>
      );
    }
    if (headroom <= 20) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-bold bg-amber-950/60 text-amber-400 border border-amber-800">
          {headroom}% LOW
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-800">
        {headroom}% OK
      </span>
    );
  };

  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950 shadow-md">
      <table className="w-full text-left text-xs">
        <thead className="bg-zinc-900/90 text-zinc-400 font-mono text-[11px] uppercase border-b border-zinc-800">
          <tr>
            <th className="py-3 px-4 font-semibold text-zinc-300">Limit Dimension</th>
            <th className="py-3 px-4 font-semibold text-purple-400 border-l border-zinc-800/60">
              Claude Pool A (Anthropic)
            </th>
            <th className="py-3 px-4 font-semibold text-purple-300 border-l border-zinc-800/60">
              Claude Pool B (Anthropic)
            </th>
            <th className="py-3 px-4 font-semibold text-amber-400 border-l border-zinc-800/60">
              Codex Fleet Pool (OpenAI)
            </th>
            <th className="py-3 px-4 font-semibold text-cyan-400 border-l border-zinc-800/60 bg-cyan-950/20">
              AGY Gemini (Google)
            </th>
            <th className="py-3 px-4 font-semibold text-blue-400 border-l border-zinc-800/60">
              AGY Claude/GPT
            </th>
            <th className="py-3 px-4 font-semibold text-orange-400 border-l border-zinc-800/60 bg-orange-950/20">
              Grok Fleet Pool (xAI)
            </th>
            <th className="py-3 px-4 font-semibold text-teal-400 border-l border-zinc-800/60 bg-teal-950/20">
              Kimi Fleet Pool (Moonshot)
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/60 font-mono">
          {/* Row 1: 5-Hour Headroom Remaining */}
          <tr className="hover:bg-zinc-900/40 transition-colors">
            <td className="py-2.5 px-4 font-sans font-medium text-zinc-300">
              <div className="flex items-center space-x-1.5">
                <span className="text-zinc-100 font-semibold">5-Hour Headroom</span>
                <span className="text-[10px] text-zinc-500 font-mono">(Available)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(claudeA_5h_headroom)}
                <span className="text-zinc-400 text-[11px]">({claudeA.five_hour_used_pct}% used)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(claudeB_5h_headroom)}
                <span className="text-zinc-400 text-[11px]">({claudeB.five_hour_used_pct}% used)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold">
              <div className="flex items-center space-x-2">
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-bold bg-amber-950/60 text-amber-300 border border-amber-800/80">
                  WEEKLY METERED
                </span>
                <span className="text-zinc-500 text-[11px]">(No 5h cap)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold bg-cyan-950/10">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(gemini_5h_headroom)}
                <span className="text-zinc-400 text-[11px]">({gemini_5h_used}% used)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(claudeGpt_5h_headroom)}
                <span className="text-zinc-400 text-[11px]">({claudeGpt_5h_used}% used)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold bg-orange-950/10">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(grok_5h_headroom)}
                <span className="text-zinc-400 text-[11px]">({grok_5h_used}% used)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold bg-teal-950/10">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(kimi_5h_headroom)}
                <span className="text-zinc-400 text-[11px]">({kimi_5h_used}% used)</span>
              </div>
            </td>
          </tr>

          {/* Row 2: 5-Hour Used % */}
          <tr className="hover:bg-zinc-900/40 transition-colors bg-zinc-900/20">
            <td className="py-2.5 px-4 font-sans text-zinc-400">
              5-Hour Consumption (Used %)
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200">
              <span className="font-semibold">{claudeA.five_hour_used_pct}%</span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[Reported]</span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200">
              <span className="font-semibold">{claudeB.five_hour_used_pct}%</span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[Reported]</span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200">
              <span className="font-semibold text-zinc-400">N/A</span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[Weekly Pool]</span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200 bg-cyan-950/10">
              <span className="font-semibold">{gemini_5h_used}%</span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[100 - rem]</span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200">
              <span className="font-semibold">{claudeGpt_5h_used}%</span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[100 - rem]</span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200 bg-orange-950/10">
              <span className="font-semibold">{grok_5h_used}%</span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[Reported]</span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200 bg-teal-950/10">
              <span className="font-semibold">{kimi_5h_used}%</span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[Reported]</span>
            </td>
          </tr>

          {/* Row 3: Weekly Headroom Remaining */}
          <tr className="hover:bg-zinc-900/40 transition-colors">
            <td className="py-2.5 px-4 font-sans font-medium text-zinc-300">
              <div className="flex items-center space-x-1.5">
                <span className="text-zinc-100 font-semibold">Weekly Headroom</span>
                <span className="text-[10px] text-zinc-500 font-mono">(7-Day)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(claudeA_week_headroom)}
                <span className="text-zinc-400 text-[11px]">({claudeA.weekly_used_pct}% used)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(claudeB_week_headroom)}
                <span className="text-zinc-400 text-[11px]">({claudeB.weekly_used_pct}% used)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(codex_week_headroom)}
                <span className="text-zinc-400 text-[11px]">({codex_week_used}% used)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold bg-cyan-950/10">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(gemini_week_headroom)}
                <span className="text-zinc-400 text-[11px]">({gemini_week_used}% used)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(claudeGpt_week_headroom)}
                <span className="text-zinc-400 text-[11px]">({claudeGpt_week_used}% used)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold bg-orange-950/10">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(grok_week_headroom)}
                <span className="text-zinc-400 text-[11px]">({grok_week_used}% used)</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 font-semibold bg-teal-950/10">
              <div className="flex items-center space-x-2">
                {getHeadroomPill(kimi_week_headroom)}
                <span className="text-zinc-400 text-[11px]">({kimi_week_used}% used)</span>
              </div>
            </td>
          </tr>

          {/* Row 4: Weekly Used % */}
          <tr className="hover:bg-zinc-900/40 transition-colors bg-zinc-900/20">
            <td className="py-2.5 px-4 font-sans text-zinc-400">
              Weekly Consumption (Used %)
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200">
              <span className={cn("font-semibold", claudeA.weekly_used_pct > 80 && "text-amber-400")}>
                {claudeA.weekly_used_pct}%
              </span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[Reported]</span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200">
              <span className="font-semibold">{claudeB.weekly_used_pct}%</span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[Reported]</span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200">
              <span className={cn("font-semibold", codex_week_used > 80 && "text-amber-400")}>
                {codex_week_used}%
              </span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[Reported]</span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200 bg-cyan-950/10">
              <span className="font-semibold">{gemini_week_used}%</span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[100 - rem]</span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200">
              <span className="font-semibold">{claudeGpt_week_used}%</span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[100 - rem]</span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200 bg-orange-950/10">
              <span className={cn("font-semibold", grok_week_used > 80 && "text-amber-400")}>
                {grok_week_used}%
              </span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[Reported]</span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-200 bg-teal-950/10">
              <span className={cn("font-semibold", kimi_week_used > 80 && "text-amber-400")}>
                {kimi_week_used}%
              </span>
              <span className="text-[10px] text-zinc-500 ml-1.5">[Reported]</span>
            </td>
          </tr>

          {/* Row 5: Telemetry Direction Invariant */}
          <tr className="hover:bg-zinc-900/40 transition-colors">
            <td className="py-2.5 px-4 font-sans text-zinc-400">
              Telemetry Direction
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-300">
              <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-purple-300">
                Native: USED %
              </span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-300">
              <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-purple-300">
                Native: USED %
              </span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-300">
              <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-amber-300 font-bold border border-amber-800/60">
                Native: USED %
              </span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-300 bg-cyan-950/10">
              <span className="px-1.5 py-0.5 rounded bg-cyan-900/40 text-[10px] text-cyan-300 font-bold border border-cyan-800/60">
                Native: REMAINING %
              </span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-300">
              <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-blue-300">
                Native: REMAINING %
              </span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-300 bg-orange-950/10">
              <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-orange-400 font-bold border border-orange-800/60">
                Native: USED %
              </span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-300 bg-teal-950/10">
              <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-teal-400 font-bold border border-teal-800/60">
                Native: USED %
              </span>
            </td>
          </tr>

          {/* Row 6: Rate Limit / Pace State */}
          <tr className="hover:bg-zinc-900/40 transition-colors">
            <td className="py-2.5 px-4 font-sans text-zinc-400">
              Operational Status
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60">
              {claudeA.state === 'OFF-PACE' ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-amber-950/80 text-amber-400 border border-amber-800">
                  <AlertCircle className="w-3 h-3 mr-1" />
                  OFF-PACE
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800">
                  <CheckCircle2 className="w-3 h-3 mr-1" />
                  {claudeA.state}
                </span>
              )}
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-zinc-800 text-zinc-300 border border-zinc-700">
                {claudeB.state}
              </span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60">
              {codex_week_headroom <= 20 ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-amber-950/80 text-amber-400 border border-amber-800">
                  <AlertCircle className="w-3 h-3 mr-1" />
                  METERED ({codex_week_headroom}% REM)
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800">
                  <CheckCircle2 className="w-3 h-3 mr-1" />
                  {codex?.state || 'OK'}
                </span>
              )}
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 bg-cyan-950/10">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800">
                <CheckCircle2 className="w-3 h-3 mr-1" />
                HEALTHY
              </span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800">
                <CheckCircle2 className="w-3 h-3 mr-1" />
                HEALTHY
              </span>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 bg-orange-950/10">
              {grok_state === 'OFF-PACE' ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-amber-950/80 text-amber-400 border border-amber-800">
                  <AlertCircle className="w-3 h-3 mr-1" />
                  OFF-PACE
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800">
                  <CheckCircle2 className="w-3 h-3 mr-1" />
                  {grok_state}
                </span>
              )}
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 bg-teal-950/10">
              {kimi_state === 'OFF-PACE' ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-amber-950/80 text-amber-400 border border-amber-800">
                  <AlertCircle className="w-3 h-3 mr-1" />
                  OFF-PACE
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800">
                  <CheckCircle2 className="w-3 h-3 mr-1" />
                  {kimi_state}
                </span>
              )}
            </td>
          </tr>

          {/* Row 7: Reset Cadence */}
          <tr className="hover:bg-zinc-900/40 transition-colors">
            <td className="py-2.5 px-4 font-sans text-zinc-400">
              Reset Cadence
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60">
              <ResetCountdownClock resetsAt={claudeA.resets_at} />
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60">
              <ResetCountdownClock resetsAt={claudeB.resets_at} />
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60">
              {codex?.resets_at ? (
                <div className="flex flex-col space-y-0.5">
                  <ResetCountdownClock resetsAt={codex.resets_at} />
                  <span className="text-[10px] text-zinc-500">Tue 8:20 PM</span>
                </div>
              ) : (
                <span className="text-zinc-500 text-[11px]">Tue 8:20 PM</span>
              )}
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 bg-cyan-950/10 text-zinc-300 text-[11px]">
              <div className="flex flex-col space-y-0.5">
                <span className="text-cyan-400 font-semibold">5h: in ~1h 14m</span>
                <span className="text-zinc-400 text-[10px]">Wk: in 5d 18h</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 text-zinc-300 text-[11px]">
              <div className="flex flex-col space-y-0.5">
                <span className="text-blue-400 font-semibold">100% Remaining</span>
                <span className="text-zinc-400 text-[10px]">Unused</span>
              </div>
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 bg-orange-950/10 text-zinc-300 text-[11px]">
              {grok?.resets_at ? (
                <ResetCountdownClock resetsAt={grok.resets_at} />
              ) : (
                <span className="text-zinc-500 text-[11px]">Rolling 5h</span>
              )}
            </td>
            <td className="py-2.5 px-4 border-l border-zinc-800/60 bg-teal-950/10 text-zinc-300 text-[11px]">
              {kimi?.resets_at ? (
                <ResetCountdownClock resetsAt={kimi.resets_at} />
              ) : (
                <span className="text-zinc-500 text-[11px]">Rolling 5h</span>
              )}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
