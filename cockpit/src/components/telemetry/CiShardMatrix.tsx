"use client";

import React, { useState, useMemo } from 'react';
import type { ShardsResponse, CiShardStatus } from '@/lib/types';
import { ShardDiagnosticModal } from './ShardDiagnosticModal';
import { formatDuration } from '@/lib/utils';
import { ShieldCheck, AlertTriangle, CheckCircle, PlayCircle, Clock } from 'lucide-react';

interface CiShardMatrixProps {
  shardsData: ShardsResponse;
  isLoading: boolean;
  onRefresh: () => void;
}

export function CiShardMatrix({ shardsData }: CiShardMatrixProps) {
  const [selectedShard, setSelectedShard] = useState<CiShardStatus | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>('all');

  const shards = shardsData.shards || [];

  const filteredShards = useMemo(() => {
    if (filterCategory === 'all') return shards;
    return shards.filter(s => s.category === filterCategory);
  }, [shards, filterCategory]);

  const summary = useMemo(() => {
    const total = shards.length;
    const passed = shards.filter(s => s.status === 'success' || s.status === 'PASS').length;
    const failed = shards.filter(s => s.status === 'failure' || s.status === 'FAIL').length;
    const running = shards.filter(s => s.status === 'running' || s.status === 'RUNNING').length;
    return { total, passed, failed, running };
  }, [shards]);

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'success' || s === 'pass') {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-950/60 text-emerald-400 border border-emerald-800">
          <CheckCircle className="w-3 h-3 mr-1" />
          PASS
        </span>
      );
    }
    if (s === 'running') {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-950/60 text-blue-400 border border-blue-800 animate-pulse">
          <PlayCircle className="w-3 h-3 mr-1" />
          RUNNING
        </span>
      );
    }
    if (s === 'failure' || s === 'fail') {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-rose-950/80 text-rose-400 border border-rose-800">
          <AlertTriangle className="w-3 h-3 mr-1" />
          FAIL
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-zinc-800 text-zinc-400 border border-zinc-700">
        <Clock className="w-3 h-3 mr-1" />
        QUEUED
      </span>
    );
  };

  return (
    <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 flex flex-col h-[520px]">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold text-zinc-100">
            CI/CD Shard Health Matrix ({summary.total} Shards)
          </h3>
        </div>
        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="text-emerald-400 font-bold">{summary.passed} Passed</span>
          {summary.failed > 0 && (
            <span className="text-rose-400 font-bold">{summary.failed} Failed</span>
          )}
          {summary.running > 0 && (
            <span className="text-blue-400 font-bold">{summary.running} Running</span>
          )}
        </div>
      </div>

      {/* Category Filters */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {[
          { id: 'all', label: 'All Shards' },
          { id: 'python_unit', label: 'Python Unit' },
          { id: 'browser_e2e', label: 'Browser E2E' },
          { id: 'vitest_node', label: 'Vitest / Node' },
          { id: 'postgres_integration', label: 'Postgres Service' },
        ].map(cat => (
          <button
            key={cat.id}
            type="button"
            onClick={() => setFilterCategory(cat.id)}
            className={`px-2 py-1 rounded text-[11px] font-mono transition-colors ${
              filterCategory === cat.id
                ? 'bg-zinc-700 text-zinc-100 border border-zinc-600 font-bold'
                : 'bg-zinc-800/60 text-zinc-400 hover:bg-zinc-800 border border-zinc-800'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Shards Matrix */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-1.5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {filteredShards.map(shard => (
            <div
              key={shard.name}
              onClick={() => setSelectedShard(shard)}
              className="p-2.5 rounded bg-zinc-950/60 border border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-950 cursor-pointer transition-all flex items-center justify-between"
            >
              <div className="truncate mr-2">
                <div className="text-xs font-mono font-medium text-zinc-200 truncate">
                  {shard.name}
                </div>
                <div className="text-[10px] font-mono text-zinc-500 uppercase mt-0.5">
                  {shard.category.replace('_', ' ')}
                </div>
              </div>
              <div className="flex items-center space-x-2 shrink-0">
                <span className="text-[11px] font-mono text-zinc-400">
                  {shard.duration_s !== null ? formatDuration(shard.duration_s) : '-'}
                </span>
                {getStatusBadge(shard.status)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Diagnostic Modal */}
      {selectedShard && (
        <ShardDiagnosticModal
          shard={selectedShard}
          onClose={() => setSelectedShard(null)}
        />
      )}
    </div>
  );
}
