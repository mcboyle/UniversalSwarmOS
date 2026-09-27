'use client';

import React, { useRef, type KeyboardEvent } from 'react';
import { Activity, Layers, Gauge, Cpu } from 'lucide-react';
import { cn } from '@/lib/utils';

export type TabId = 'telemetry' | 'swarm-control' | 'quotas' | 'architecture';

export interface TabItem {
  id: TabId;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  pillText?: string;
  pillColor?: 'default' | 'emerald' | 'amber' | 'cyan';
}

export const DASHBOARD_TABS: TabItem[] = [
  {
    id: 'telemetry',
    label: 'Telemetry & Infrastructure',
    icon: Activity,
    pillText: '27 Nodes / 42 Shards',
    pillColor: 'cyan',
  },
  {
    id: 'swarm-control',
    label: 'Swarm Control & Queue',
    icon: Layers,
    pillText: 'DISPATCH-LEDGER',
    pillColor: 'default',
  },
  {
    id: 'quotas',
    label: 'API Quotas & Headroom',
    icon: Gauge,
    pillText: '5h vs Weekly (Rule 29)',
    pillColor: 'emerald',
  },
  {
    id: 'architecture',
    label: 'Architecture Topology',
    icon: Cpu,
    pillText: '27 Nodes / ESXi',
    pillColor: 'cyan',
  },
];

export interface TabNavProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

export function TabNav({ activeTab, onTabChange }: TabNavProps) {
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const currentIndex = DASHBOARD_TABS.findIndex((t) => t.id === activeTab);
    let targetIndex = -1;

    if (e.key === 'ArrowRight') {
      targetIndex = (currentIndex + 1) % DASHBOARD_TABS.length;
    } else if (e.key === 'ArrowLeft') {
      targetIndex = (currentIndex - 1 + DASHBOARD_TABS.length) % DASHBOARD_TABS.length;
    } else if (e.key === 'Home') {
      targetIndex = 0;
    } else if (e.key === 'End') {
      targetIndex = DASHBOARD_TABS.length - 1;
    }

    if (targetIndex >= 0) {
      e.preventDefault();
      const targetTab = DASHBOARD_TABS[targetIndex];
      onTabChange(targetTab.id);
      tabRefs.current[targetIndex]?.focus();
    }
  };

  return (
    <div
      role="tablist"
      aria-label="Swarm Dashboard Views"
      onKeyDown={handleKeyDown}
      className="flex items-center space-x-1 border-b border-zinc-800 bg-zinc-950/80 px-4 pt-1"
    >
      {DASHBOARD_TABS.map((tab, idx) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;

        return (
          <button
            key={tab.id}
            ref={(el) => {
              tabRefs.current[idx] = el;
            }}
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={isActive}
            aria-controls={`panel-${tab.id}`}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onTabChange(tab.id)}
            className={cn(
              'group relative flex items-center space-x-2.5 px-3 py-2 text-xs font-medium rounded-t-md transition-all outline-none',
              isActive
                ? 'bg-zinc-900 text-zinc-100 border-t border-x border-zinc-800'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/40'
            )}
          >
            <Icon
              className={cn(
                'h-3.5 w-3.5 transition-colors',
                isActive ? 'text-emerald-400' : 'text-zinc-500 group-hover:text-zinc-400'
              )}
            />
            <span className="tracking-tight">{tab.label}</span>

            {tab.pillText && (
              <span
                className={cn(
                  'rounded px-1.5 py-0.2 text-[10px] font-mono border',
                  isActive
                    ? 'bg-zinc-800 text-zinc-200 border-zinc-700'
                    : 'bg-zinc-900 text-zinc-500 border-zinc-800 group-hover:text-zinc-400'
                )}
              >
                {tab.pillText}
              </span>
            )}

            {/* Active bottom highlight indicator */}
            {isActive && (
              <span className="absolute inset-x-0 -bottom-[1px] h-[2px] bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
            )}
          </button>
        );
      })}
    </div>
  );
}
