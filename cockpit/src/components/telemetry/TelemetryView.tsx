"use client";

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { NodeLatencyGrid } from './NodeLatencyGrid';
import { CiShardMatrix } from './CiShardMatrix';
import { CostCacheProjections } from './CostCacheProjections';
import { ArchitectureVisualizer } from '@/components/architecture/ArchitectureVisualizer';
import { ErrorBoundary } from '@/components/shared/ErrorBoundary';
import { mockNodes, mockShardsResponse, mockCostData } from '@/lib/mock-data';
import type { NodesResponse, ShardsResponse, CostResponse } from '@/lib/types';
import { RefreshCw, Activity, AlertCircle } from 'lucide-react';

export function TelemetryView() {
  const [nodesData, setNodesData] = useState<NodesResponse | null>(null);
  const [shardsData, setShardsData] = useState<ShardsResponse | null>(null);
  const [costData, setCostData] = useState<CostResponse | null>(null);

  const [isLoadingNodes, setIsLoadingNodes] = useState<boolean>(true);
  const [isLoadingShards, setIsLoadingShards] = useState<boolean>(true);
  const [isLoadingCost, setIsLoadingCost] = useState<boolean>(true);

  const [isProbing, setIsProbing] = useState<boolean>(false);
  const [timeRange, setTimeRange] = useState<'5m' | '30m' | '1h' | '6h' | '24h' | '7d'>('24h');
  const [groupBy, setGroupBy] = useState<'model' | 'thread'>('model');
  const [subView, setSubView] = useState<'topology' | 'matrix' | 'combined'>('combined');
  const [selectedRole, setSelectedRole] = useState<string>('all');
  const [isMockFallback, setIsMockFallback] = useState<boolean>(false);

  const isVisibleRef = useRef<boolean>(true);

  const fetchNodes = useCallback(async (probe = false) => {
    try {
      if (probe) setIsProbing(true);
      const res = await fetch(`/api/nodes${probe ? '?probe=true' : ''}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: NodesResponse = await res.json();
      setNodesData(data);
      if (data.source === 'mock') setIsMockFallback(true);
    } catch {
      setNodesData({
        timestamp: new Date().toISOString(),
        total_nodes: mockNodes.length,
        up_nodes: mockNodes.filter(n => n.status === 'up').length,
        blacklisted_count: 1,
        nodes: mockNodes,
        source: 'mock'
      });
      setIsMockFallback(true);
    } finally {
      setIsLoadingNodes(false);
      setIsProbing(false);
    }
  }, []);

  const fetchShards = useCallback(async () => {
    try {
      const res = await fetch('/api/shards');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ShardsResponse = await res.json();
      setShardsData(data);
    } catch {
      setShardsData({ ...mockShardsResponse, source: 'mock' });
      setIsMockFallback(true);
    } finally {
      setIsLoadingShards(false);
    }
  }, []);

  const fetchCost = useCallback(async (range: string, group?: string) => {
    try {
      const g = group || groupBy;
      const res = await fetch(`/api/cost?since=${range}&group_by=${g}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: CostResponse = await res.json();
      setCostData(data);
    } catch {
      setCostData({ ...mockCostData, source: 'mock' });
      setIsMockFallback(true);
    } finally {
      setIsLoadingCost(false);
    }
  }, [groupBy]);

  // Polling loops with window focus awareness
  useEffect(() => {
    fetchNodes(false);
    fetchShards();
    fetchCost(timeRange);

    const handleVisibility = () => {
      isVisibleRef.current = document.visibilityState === 'visible';
      if (isVisibleRef.current) {
        fetchNodes(false);
        fetchShards();
        fetchCost(timeRange);
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);

    const nodeInterval = setInterval(() => {
      if (isVisibleRef.current) fetchNodes(false);
    }, 3000);

    const shardInterval = setInterval(() => {
      if (isVisibleRef.current) fetchShards();
    }, 5000);

    const costInterval = setInterval(() => {
      if (isVisibleRef.current) fetchCost(timeRange);
    }, 15000);

    const handleRefreshEvent = () => {
      fetchNodes(false);
      fetchShards();
      fetchCost(timeRange);
    };

    window.addEventListener('swarm:refresh', handleRefreshEvent);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('swarm:refresh', handleRefreshEvent);
      clearInterval(nodeInterval);
      clearInterval(shardInterval);
      clearInterval(costInterval);
    };
  }, [fetchNodes, fetchShards, fetchCost, timeRange]);

  return (
    <div className="space-y-6">
      {/* Top Banner Ribbon */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-3 rounded-lg bg-zinc-900 border border-zinc-800">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded bg-zinc-800 text-zinc-300">
            <Activity className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-zinc-100 uppercase tracking-wide">
              Distributed Telemetry & Pipeline Observability
            </h2>
            <p className="text-xs text-zinc-400">
              Subnet 10.0.70.* matrix, 42 CI test matrix shards, and token cache telemetry
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {/* Sub-view toggle */}
          <div className="flex items-center space-x-1 bg-zinc-950/80 p-1 rounded border border-zinc-800">
            {(['combined', 'topology', 'matrix'] as const).map((view) => (
              <button
                key={view}
                type="button"
                onClick={() => setSubView(view)}
                className={`px-2.5 py-1 rounded text-xs font-mono capitalize transition-colors ${
                  subView === view
                    ? 'bg-zinc-800 text-cyan-400 font-bold border border-zinc-700'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {view === 'combined' ? 'Full View' : view === 'topology' ? 'Architecture Visualizer' : 'Latency Matrix'}
              </button>
            ))}
          </div>

          {isMockFallback && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-amber-950/40 text-amber-400 border border-amber-800">
              <AlertCircle className="w-3 h-3 mr-1" />
              COLD FEED (MOCK FALLBACK)
            </span>
          )}
          <button
            type="button"
            onClick={() => fetchNodes(true)}
            disabled={isProbing}
            className="inline-flex items-center px-3 py-1.5 rounded text-xs font-mono bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isProbing ? 'animate-spin' : ''}`} />
            {isProbing ? 'Probing Fleet...' : 'Probe Fleet TCP'}
          </button>
        </div>
      </div>

      {/* Live Visualizer of The Heterogeneous Swarm Architecture */}
      {(subView === 'combined' || subView === 'topology') && (
        <ErrorBoundary fallbackTitle="Architecture Visualizer Error">
          <ArchitectureVisualizer />
        </ErrorBoundary>
      )}

      {/* Grid: 27-Node Latency Matrix & CI Shards Matrix */}
      {(subView === 'combined' || subView === 'matrix') && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ErrorBoundary fallbackTitle="Node Latency Grid Error">
            <NodeLatencyGrid
              nodes={nodesData?.nodes || mockNodes}
              isLoading={isLoadingNodes}
              selectedRole={selectedRole}
              onSelectRole={setSelectedRole}
              onTriggerProbe={() => fetchNodes(true)}
              isProbing={isProbing}
            />
          </ErrorBoundary>

          <ErrorBoundary fallbackTitle="CI/CD Shard Matrix Error">
            <CiShardMatrix
              shardsData={shardsData || mockShardsResponse}
              isLoading={isLoadingShards}
              onRefresh={fetchShards}
            />
          </ErrorBoundary>
        </div>
      )}

      {/* Recharts Composite Cost & Prefix Cache Visualization */}
      <ErrorBoundary fallbackTitle="Cost & Cache Projections Error">
        <CostCacheProjections
          costData={costData || mockCostData}
          timeRange={timeRange}
          onTimeRangeChange={(r) => {
            setTimeRange(r);
            fetchCost(r, groupBy);
          }}
          groupBy={groupBy}
          onGroupByChange={(g) => {
            setGroupBy(g);
            fetchCost(timeRange, g);
          }}
          isLoading={isLoadingCost}
        />
      </ErrorBoundary>
    </div>
  );
}
