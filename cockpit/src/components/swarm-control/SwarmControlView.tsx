"use client";

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { QueueDispatcher } from './QueueDispatcher';
import { AgentConfigGrid } from './AgentConfigGrid';
import { ErrorBoundary } from '@/components/shared/ErrorBoundary';
import { mockQueueItems, mockAgentsResponse } from '@/lib/mock-data';
import type { QueueResponse, AgentsResponse } from '@/lib/types';
import { Sliders, AlertCircle } from 'lucide-react';

export function SwarmControlView() {
  const [queueData, setQueueData] = useState<QueueResponse | null>(null);
  const [agentsData, setAgentsData] = useState<AgentsResponse | null>(null);
  const [isLoadingQueue, setIsLoadingQueue] = useState<boolean>(true);
  const [isLoadingAgents, setIsLoadingAgents] = useState<boolean>(true);
  const [isMockFallback, setIsMockFallback] = useState<boolean>(false);

  const isVisibleRef = useRef<boolean>(true);

  const fetchQueue = useCallback(async () => {
    try {
      const res = await fetch('/api/queue');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: QueueResponse = await res.json();
      setQueueData(data);
      if (data.source === 'mock') setIsMockFallback(true);
    } catch {
      setQueueData({
        timestamp: new Date().toISOString(),
        total_entries: mockQueueItems.length,
        active_count: mockQueueItems.filter(i => i.is_active).length,
        completed_count: mockQueueItems.filter(i => !i.is_active).length,
        items: mockQueueItems,
        source: 'mock'
      });
      setIsMockFallback(true);
    } finally {
      setIsLoadingQueue(false);
    }
  }, []);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch('/api/agents');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: AgentsResponse = await res.json();
      setAgentsData(data);
    } catch {
      setAgentsData({ ...mockAgentsResponse, source: 'mock' });
      setIsMockFallback(true);
    } finally {
      setIsLoadingAgents(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
    fetchAgents();

    const handleVisibility = () => {
      isVisibleRef.current = document.visibilityState === 'visible';
      if (isVisibleRef.current) {
        fetchQueue();
        fetchAgents();
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);

    // Queue polled every 2s for responsive state changes
    const queueInterval = setInterval(() => {
      if (isVisibleRef.current) fetchQueue();
    }, 2000);

    // Agents polled every 5s
    const agentsInterval = setInterval(() => {
      if (isVisibleRef.current) fetchAgents();
    }, 5000);

    const handleRefreshEvent = () => {
      fetchQueue();
      fetchAgents();
    };

    window.addEventListener('swarm:refresh', handleRefreshEvent);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('swarm:refresh', handleRefreshEvent);
      clearInterval(queueInterval);
      clearInterval(agentsInterval);
    };
  }, [fetchQueue, fetchAgents]);

  return (
    <div className="space-y-6">
      {/* Top Banner Ribbon */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-3 rounded-lg bg-zinc-900 border border-zinc-800">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded bg-zinc-800 text-zinc-300">
            <Sliders className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-zinc-100 uppercase tracking-wide">
              Interactive Swarm Steering & Dispatch Control
            </h2>
            <p className="text-xs text-zinc-400">
              Atomic DISPATCH-LEDGER.tsv priority scheduling and real-time agent seat parameters
            </p>
          </div>
        </div>

        {isMockFallback && (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-amber-950/40 text-amber-400 border border-amber-800">
            <AlertCircle className="w-3 h-3 mr-1" />
            COLD FEED (MOCK DATA)
          </span>
        )}
      </div>

      {/* Two-Column Cockpit Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Left Column: Queue Dispatcher (7 cols) */}
        <div className="xl:col-span-7">
          <ErrorBoundary fallbackTitle="Queue Dispatcher Error">
            <QueueDispatcher
              initialItems={queueData?.items || mockQueueItems}
              isLoading={isLoadingQueue}
              onQueueUpdated={fetchQueue}
            />
          </ErrorBoundary>
        </div>

        {/* Right Column: Agent Configuration Grid (5 cols) */}
        <div className="xl:col-span-5">
          <ErrorBoundary fallbackTitle="Agent Config Grid Error">
            <AgentConfigGrid
              agents={agentsData?.agents || mockAgentsResponse.agents}
              isLoading={isLoadingAgents}
              onAgentUpdated={fetchAgents}
            />
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
}
