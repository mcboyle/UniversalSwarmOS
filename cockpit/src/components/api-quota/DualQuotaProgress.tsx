"use client";

import React from 'react';
import { cn } from '@/lib/utils';

export interface DualQuotaProgressProps {
  label5h: string;
  usedPct5h: number;
  remainingPct5h: number;
  labelWeekly: string;
  usedPctWeekly: number;
  remainingPctWeekly: number;
  accentColor?: 'purple' | 'cyan' | 'blue' | 'amber' | 'default';
}

export function DualQuotaProgress({
  label5h,
  usedPct5h,
  remainingPct5h,
  labelWeekly,
  usedPctWeekly,
  remainingPctWeekly,
  accentColor = 'default',
}: DualQuotaProgressProps) {
  // Clamping
  const u5h = Math.min(100, Math.max(0, usedPct5h));
  const r5h = Math.min(100, Math.max(0, remainingPct5h));

  const uWeek = Math.min(100, Math.max(0, usedPctWeekly));
  const rWeek = Math.min(100, Math.max(0, remainingPctWeekly));

  const getGradient = (used: number, remaining: number) => {
    if (remaining <= 10 || used >= 90) {
      return 'from-rose-600 to-rose-400';
    }
    if (remaining <= 20 || used >= 80) {
      return 'from-amber-600 to-amber-400';
    }
    if (accentColor === 'cyan') return 'from-cyan-600 to-cyan-400';
    if (accentColor === 'blue') return 'from-blue-600 to-blue-400';
    if (accentColor === 'purple') return 'from-purple-600 to-purple-400';
    if (accentColor === 'amber') return 'from-amber-600 to-amber-400';
    return 'from-emerald-600 to-emerald-400';
  };

  return (
    <div className="space-y-3 font-mono">
      {/* 5-Hour Progress */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="text-zinc-300 font-sans font-medium text-[11px]">{label5h}</span>
          <div className="space-x-1.5 text-[11px]">
            <span className={cn(
              "font-bold",
              r5h <= 10 ? "text-rose-400" : r5h <= 20 ? "text-amber-400" : "text-emerald-400"
            )}>
              {r5h}% Headroom
            </span>
            <span className="text-zinc-500 text-[10px]">({u5h}% used)</span>
          </div>
        </div>

        <div className="relative w-full h-2 rounded-full bg-zinc-800 overflow-hidden">
          {/* 80% Warning Marker */}
          <div className="absolute top-0 bottom-0 right-[20%] w-[1px] bg-zinc-600 z-10" title="80% Warning Threshold" />
          <div
            className={cn("h-full rounded-full transition-all duration-500 bg-gradient-to-r", getGradient(u5h, r5h))}
            style={{ width: `${u5h}%` }}
          />
        </div>
      </div>

      {/* Weekly Progress */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="text-zinc-300 font-sans font-medium text-[11px]">{labelWeekly}</span>
          <div className="space-x-1.5 text-[11px]">
            <span className={cn(
              "font-bold",
              rWeek <= 10 ? "text-rose-400" : rWeek <= 20 ? "text-amber-400" : "text-zinc-300"
            )}>
              {rWeek}% Headroom
            </span>
            <span className="text-zinc-500 text-[10px]">({uWeek}% used)</span>
          </div>
        </div>

        <div className="relative w-full h-2 rounded-full bg-zinc-800 overflow-hidden">
          {/* 80% Warning Marker */}
          <div className="absolute top-0 bottom-0 right-[20%] w-[1px] bg-zinc-600 z-10" title="80% Warning Threshold" />
          <div
            className={cn("h-full rounded-full transition-all duration-500 bg-gradient-to-r", getGradient(uWeek, rWeek))}
            style={{ width: `${uWeek}%` }}
          />
        </div>
      </div>
    </div>
  );
}
