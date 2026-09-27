"use client";

import React, { useMemo } from 'react';
import type { ClusterNode } from '@/lib/types';
import { Server, ShieldAlert, Wifi, WifiOff } from 'lucide-react';

interface NodeLatencyGridProps {
  nodes: ClusterNode[];
  isLoading: boolean;
  selectedRole: string;
  onSelectRole: (role: string) => void;
  onTriggerProbe: () => void;
  isProbing: boolean;
}

const ROLES = [
  { id: 'all', label: 'All Nodes (27)' },
  { id: 'hub', label: 'Hub' },
  { id: 'ai', label: 'AI Satellites' },
  { id: 'ops', label: 'Ops & CI' },
  { id: 'stg', label: 'RAG/Cache' },
  { id: 'wrk-bd', label: 'BD Workers' },
  { id: 'wrk-test', label: 'Test Workers' },
  { id: 'spr-pool', label: 'Spare Pool' },
];

export function NodeLatencyGrid({
  nodes,
  selectedRole,
  onSelectRole,
}: NodeLatencyGridProps) {
  const filteredNodes = useMemo(() => {
    if (selectedRole === 'all') return nodes;
    return nodes.filter(n => n.role === selectedRole);
  }, [nodes, selectedRole]);

  const upCount = useMemo(() => nodes.filter(n => n.status === 'up').length, [nodes]);

  const getLatencyBadge = (node: ClusterNode) => {
    if (node.is_blacklisted || node.ip === '10.0.70.95') {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-amber-950/40 text-amber-400 border border-amber-700/50">
          <ShieldAlert className="w-3 h-3 mr-1" />
          Rule 21 Hands-Off
        </span>
      );
    }
    if (node.status === 'down') {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-red-950/60 text-red-400 border border-red-800">
          <WifiOff className="w-3 h-3 mr-1" />
          Down
        </span>
      );
    }
    const ms = node.latency_ms;
    if (ms === null) {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-zinc-800 text-zinc-400 border border-zinc-700">
          Unprobed
        </span>
      );
    }
    if (ms < 10) {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-950/60 text-emerald-400 border border-emerald-800">
          <Wifi className="w-3 h-3 mr-1" />
          {ms.toFixed(2)}ms
        </span>
      );
    }
    if (ms <= 50) {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-950/60 text-amber-400 border border-amber-800">
          <Wifi className="w-3 h-3 mr-1" />
          {ms.toFixed(2)}ms
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-rose-950/60 text-rose-400 border border-rose-800">
        <Wifi className="w-3 h-3 mr-1" />
        {ms.toFixed(2)}ms
      </span>
    );
  };

  return (
    <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 flex flex-col h-[520px]">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800">
        <div className="flex items-center space-x-2">
          <Server className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold text-zinc-100">
            27-Node Cluster Matrix (Subnet 10.0.70.*)
          </h3>
        </div>
        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="text-zinc-400">Online:</span>
          <span className="text-emerald-400 font-bold">{upCount}</span>
          <span className="text-zinc-600">/</span>
          <span className="text-zinc-300">27</span>
        </div>
      </div>

      {/* Role Filter Tabs */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {ROLES.map((r) => (
          <button
            key={r.id}
            type="button"
            onClick={() => onSelectRole(r.id)}
            className={`px-2 py-1 rounded text-[11px] font-mono transition-colors ${
              selectedRole === r.id
                ? 'bg-zinc-700 text-zinc-100 border border-zinc-600 font-bold'
                : 'bg-zinc-800/60 text-zinc-400 hover:bg-zinc-800 border border-zinc-800'
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>

      {/* Scrollable Node Cards Grid */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-2">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {filteredNodes.map((node) => {
            const isTest2 = node.ip === '10.0.70.95' || node.is_blacklisted;
            return (
              <div
                key={node.ip}
                className={`p-2.5 rounded border transition-all ${
                  isTest2
                    ? 'bg-amber-950/10 border-amber-700/40 hover:border-amber-600'
                    : node.is_local
                    ? 'bg-zinc-950/80 border-cyan-800/50 hover:border-cyan-700'
                    : 'bg-zinc-950/50 border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center space-x-1.5 truncate">
                    <span className="text-xs font-mono font-semibold text-zinc-200 truncate">
                      {node.name}
                    </span>
                    {node.is_local && (
                      <span className="px-1 py-0.2 rounded text-[9px] font-mono bg-cyan-950 text-cyan-400 border border-cyan-800">
                        LOCAL
                      </span>
                    )}
                  </div>
                  {getLatencyBadge(node)}
                </div>

                <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400">
                  <span>{node.ip}</span>
                  <span className="text-zinc-500 uppercase">{node.role || 'worker'}</span>
                </div>

                <div className="mt-2 pt-1.5 border-t border-zinc-900 flex items-center justify-between text-[10px] text-zinc-500 font-mono">
                  <span className="truncate">{node.tier}</span>
                  {isTest2 ? (
                    <span className="text-amber-400 font-bold">ISOLATED</span>
                  ) : (
                    <span>Status: {node.status}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
