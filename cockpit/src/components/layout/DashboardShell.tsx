'use client';

import React, { useState, useCallback } from 'react';
import { HeaderBar } from '@/components/layout/HeaderBar';
import { TabNav, type TabId } from '@/components/layout/TabNav';
import { ErrorBoundary } from '@/components/shared/ErrorBoundary';
import { ClientOnly } from '@/components/shared/ClientOnly';
import { TelemetryView } from '@/components/telemetry/TelemetryView';
import { SwarmControlView } from '@/components/swarm-control/SwarmControlView';
import { ApiQuotaView } from '@/components/api-quota/ApiQuotaView';
import { ArchitectureVisualizer } from '@/components/architecture/ArchitectureVisualizer';
import { mockAgentsResponse } from '@/lib/mock-data';

function TabSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-12 bg-zinc-900 rounded-lg w-full" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="h-96 bg-zinc-900 rounded-lg" />
        <div className="h-96 bg-zinc-900 rounded-lg" />
      </div>
      <div className="h-64 bg-zinc-900 rounded-lg w-full" />
    </div>
  );
}

export function DashboardShell() {
  const [activeTab, setActiveTab] = useState<TabId>('telemetry');
  const [isLive, setIsLive] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [liveStats, setLiveStats] = useState<{
    totalNodes: number;
    onlineNodes: number;
    activeAgents: number;
  }>({
    totalNodes: 27,
    onlineNodes: 26,
    activeAgents: 7
  });

  const fetchLiveStats = useCallback(async () => {
    try {
      const [agentsRes, nodesRes] = await Promise.all([
        fetch('/api/agents'),
        fetch('/api/nodes')
      ]);
      if (agentsRes.ok && nodesRes.ok) {
        const agentsData = await agentsRes.json();
        const nodesData = await nodesRes.json();
        setLiveStats({
          totalNodes: nodesData.total_nodes ?? 27,
          onlineNodes: nodesData.up_nodes ?? 26,
          activeAgents: agentsData.active_agents ?? 7
        });
      }
    } catch {}
  }, []);

  React.useEffect(() => {
    fetchLiveStats();
    const interval = setInterval(fetchLiveStats, 5000);
    const handleRefreshEvent = () => fetchLiveStats();
    window.addEventListener('swarm:refresh', handleRefreshEvent);
    return () => {
      clearInterval(interval);
      window.removeEventListener('swarm:refresh', handleRefreshEvent);
    };
  }, [fetchLiveStats]);

  // Preserve activeTab across browser sessions/reloads on client
  React.useEffect(() => {
    try {
      const savedTab = localStorage.getItem('swarm_dashboard_active_tab') as TabId;
      if (savedTab && ['telemetry', 'swarm-control', 'quotas', 'architecture'].includes(savedTab)) {
        setActiveTab(savedTab);
      }
    } catch {}
  }, []);

  const handleTabChange = useCallback((tab: TabId) => {
    setActiveTab(tab);
    try {
      localStorage.setItem('swarm_dashboard_active_tab', tab);
    } catch {}
  }, []);

  // Manual or timer-triggered refresh: maintains React state and DOM scroll position
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('swarm:refresh'));
    }
    fetchLiveStats();
    setTimeout(() => {
      setIsRefreshing(false);
    }, 600);
  }, [fetchLiveStats]);

  const handleToggleMode = useCallback(() => {
    setIsLive((prev) => !prev);
    handleRefresh();
  }, [handleRefresh]);

  return (
    <div className="flex flex-col min-h-screen bg-zinc-950 text-zinc-100 font-sans">
      {/* Top Operations Ribbon */}
      <HeaderBar
        totalNodes={liveStats.totalNodes}
        onlineNodes={liveStats.onlineNodes}
        activeAgents={liveStats.activeAgents}
        isLive={isLive}
        isRefreshing={isRefreshing}
        onRefresh={handleRefresh}
        onToggleMode={handleToggleMode}
        refreshIntervalSeconds={5}
      />

      {/* High-Density Tab Switcher */}
      <TabNav activeTab={activeTab} onTabChange={handleTabChange} />

      {/* Main Content Area */}
      <main className="flex-1 p-4 max-w-[1600px] w-full mx-auto">
        <ErrorBoundary name={`TabPanel: ${activeTab}`} onReset={handleRefresh}>
          <div
            role="tabpanel"
            id={`panel-${activeTab}`}
            aria-labelledby={`tab-${activeTab}`}
            className="w-full space-y-4"
          >
            {activeTab === 'telemetry' && (
              <ClientOnly fallback={<TabSkeleton />}>
                <TelemetryView />
              </ClientOnly>
            )}

            {activeTab === 'swarm-control' && (
              <ClientOnly fallback={<TabSkeleton />}>
                <SwarmControlView />
              </ClientOnly>
            )}

            {activeTab === 'quotas' && (
              <ClientOnly fallback={<TabSkeleton />}>
                <ApiQuotaView />
              </ClientOnly>
            )}

            {activeTab === 'architecture' && (
              <ClientOnly fallback={<TabSkeleton />}>
                <ArchitectureVisualizer />
              </ClientOnly>
            )}
          </div>
        </ErrorBoundary>
      </main>
    </div>
  );
}
