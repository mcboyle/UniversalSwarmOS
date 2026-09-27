"use client";

import React from 'react';
import { AlertTriangle, AlertOctagon, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface HeadroomPaceAlertProps {
  poolName: string;
  alertType: 'OFF-PACE' | 'CRITICAL_HEADROOM' | 'APPROACHING_CEILING' | 'ROSTER_UNREACHABLE';
  message: string;
  ruleRef: string;
}

export function HeadroomPaceAlert({
  poolName,
  alertType,
  message,
  ruleRef,
}: HeadroomPaceAlertProps) {
  const isCritical = alertType === 'CRITICAL_HEADROOM';
  const isOffPace = alertType === 'OFF-PACE';

  return (
    <div className={cn(
      "flex items-start justify-between p-3 rounded-lg border text-xs shadow-sm transition-all",
      isCritical
        ? "bg-rose-950/40 border-rose-800/80 text-rose-200"
        : isOffPace
        ? "bg-amber-950/40 border-amber-800/80 text-amber-200"
        : "bg-blue-950/40 border-blue-800/80 text-blue-200"
    )}>
      <div className="flex items-start space-x-2.5">
        <div className="mt-0.5">
          {isCritical ? (
            <AlertOctagon className="w-4 h-4 text-rose-400" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          )}
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-bold tracking-tight text-zinc-100 font-sans">
              {poolName}: {alertType.replace('_', ' ')}
            </span>
            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-zinc-900/80 border border-zinc-700 text-zinc-300">
              {ruleRef}
            </span>
          </div>
          <p className="mt-0.5 text-zinc-300 font-mono text-[11px] leading-relaxed">
            {message}
          </p>
        </div>
      </div>

      <div className="ml-4 flex-shrink-0 text-right">
        <span className="text-[10px] font-mono text-zinc-400 uppercase">
          Rule 29 Action
        </span>
        <div className="text-[11px] font-mono text-emerald-400 font-semibold flex items-center justify-end space-x-1">
          <span>Shift to Pool B / Gemini</span>
          <ArrowRight className="w-3 h-3" />
        </div>
      </div>
    </div>
  );
}
