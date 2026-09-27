'use client';

import React, { useState, useEffect } from 'react';
import {
  Server,
  Users,
  RefreshCw,
  Radio,
  Clock,
  ShieldCheck,
} from 'lucide-react';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { ClientOnly } from '@/components/shared/ClientOnly';
import { cn } from '@/lib/utils';

export interface HeaderBarProps {
  totalNodes?: number;
  onlineNodes?: number;
  activeAgents?: number;
  isLive?: boolean;
  isRefreshing?: boolean;
  onRefresh?: () => void;
  onToggleMode?: () => void;
  refreshIntervalSeconds?: number;
}

/**
 * Inner component for ticking countdown - runs purely on client via ClientOnly wrapper
 */
function LiveRefreshTicker({
  intervalSeconds,
  isRefreshing,
  onRefresh,
}: {
  intervalSeconds: number;
  isRefreshing?: boolean;
  onRefresh?: () => void;
}) {
  const [secondsRemaining, setSecondsRemaining] = useState(intervalSeconds);

  useEffect(() => {
    setSecondsRemaining(intervalSeconds);
    const interval = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          onRefresh?.();
          return intervalSeconds;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [intervalSeconds, onRefresh]);

  return (
    <span className="flex items-center space-x-1 font-mono text-[11px] text-zinc-400">
      <Clock className="h-3 w-3 text-zinc-500" />
      <span>Sync in {secondsRemaining}s</span>
    </span>
  );
}

function StaticRefreshPill({ intervalSeconds }: { intervalSeconds: number }) {
  return (
    <span className="flex items-center space-x-1 font-mono text-[11px] text-zinc-400">
      <Clock className="h-3 w-3 text-zinc-500" />
      <span>Sync: {intervalSeconds}s</span>
    </span>
  );
}

export function HeaderBar({
  totalNodes = 27,
  onlineNodes = 26,
  activeAgents = 42,
  isLive = true,
  isRefreshing = false,
  onRefresh,
  onToggleMode,
  refreshIntervalSeconds = 5,
}: HeaderBarProps) {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-zinc-800 bg-zinc-950/95 backdrop-blur px-4 py-2.5 flex items-center justify-between">
      {/* Brand & System Identity */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2">
          <div className="flex h-7 w-7 items-center justify-center rounded bg-zinc-900 border border-zinc-700 text-emerald-400">
            <Radio className="h-4 w-4 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-semibold tracking-wide text-zinc-100 uppercase">
                Swarm Operations Cockpit
              </span>
              <StatusBadge status="online" label="Fleet Online" size="sm" />
            </div>
            <span className="text-[10px] font-mono text-zinc-500 block leading-tight">
              Heterogeneous Autonomous Multi-Model Mesh
            </span>
          </div>
        </div>
      </div>

      {/* High-Density Quick Telemetry Indicators */}
      <div className="hidden md:flex items-center space-x-4 border-x border-zinc-800 px-4">
        {/* Node Cluster Density */}
        <div
          className="flex items-center space-x-2 text-xs"
          title="27 nodes in cluster (10.0.70.*) | test2 (10.0.70.95) isolated"
        >
          <Server className="h-3.5 w-3.5 text-zinc-400" />
          <span className="text-zinc-400">Cluster:</span>
          <span className="font-mono font-medium text-zinc-100">
            {onlineNodes}/{totalNodes} Nodes
          </span>
          <span className="text-[10px] font-mono text-zinc-500 bg-zinc-900 px-1 py-0.2 rounded border border-zinc-800">
            test2 isolated
          </span>
        </div>

        {/* Active Autonomous Agent Count */}
        <div className="flex items-center space-x-2 text-xs" title="Live claimed agent seats">
          <Users className="h-3.5 w-3.5 text-zinc-400" />
          <span className="text-zinc-400">Agents:</span>
          <span className="font-mono font-medium text-emerald-400">
            {activeAgents} Active
          </span>
        </div>

        {/* Prefix Cache Efficiency Target */}
        <div className="flex items-center space-x-2 text-xs" title="Rule 58: Target >90% prefix cache">
          <ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />
          <span className="text-zinc-400">Cache Target:</span>
          <span className="font-mono font-medium text-cyan-400">&gt;90%</span>
        </div>
      </div>

      {/* Sync Controls & Connection State */}
      <div className="flex items-center space-x-3">
        {/* Hydration-safe live countdown */}
        <ClientOnly fallback={<StaticRefreshPill intervalSeconds={refreshIntervalSeconds} />}>
          <LiveRefreshTicker
            intervalSeconds={refreshIntervalSeconds}
            isRefreshing={isRefreshing}
            onRefresh={onRefresh}
          />
        </ClientOnly>

        {/* Manual Refresh Button */}
        <button
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          aria-label="Refresh Swarm Telemetry"
          className="p-1.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800 focus:outline-none focus:ring-1 focus:ring-zinc-600 disabled:opacity-50"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', isRefreshing && 'animate-spin text-emerald-400')} />
        </button>

        {/* Live vs Mock Switcher */}
        <button
          type="button"
          onClick={onToggleMode}
          title={isLive ? 'Active Live Feed (Click to switch to Mock)' : 'Mock Snapshot Mode (Click to switch to Live)'}
          className={cn(
            'inline-flex items-center space-x-1.5 px-2 py-1 rounded text-xs font-mono border transition-colors',
            isLive
              ? 'bg-emerald-950/30 text-emerald-400 border-emerald-800/60 hover:bg-emerald-950/50'
              : 'bg-amber-950/30 text-amber-400 border-amber-800/60 hover:bg-amber-950/50'
          )}
        >
          <span className={cn('h-1.5 w-1.5 rounded-full', isLive ? 'bg-emerald-400' : 'bg-amber-400')} />
          <span>{isLive ? 'LIVE' : 'MOCK'}</span>
        </button>
      </div>
    </header>
  );
}
