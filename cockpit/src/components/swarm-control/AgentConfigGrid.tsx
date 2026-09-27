"use client";

import React, { useState, useMemo } from 'react';
import type { AgentSeatConfig } from '@/lib/types';
import { Bot, Check, Search, Radio } from 'lucide-react';
import { toast } from 'sonner';

interface AgentConfigGridProps {
  agents: AgentSeatConfig[];
  isLoading: boolean;
  onAgentUpdated: () => void;
}

const MODELS_BY_TYPE = {
  claude: [
    'claude-opus-5-5',
    'claude-opus-5',
    'claude-sonnet-5',
    'claude-sonnet-4-6',
    'claude-fable-5-1',
    'claude-haiku-4-5',
    'claude-haiku-4-5-20251001'
  ],
  codex: [
    'gpt-6-astra',
    'gpt-6-sol',
    'gpt-5.6-terra',
    'gpt-5.6-sol'
  ],
  antigravity: [
    'gemini-3.8-flash-high',
    'gemini-3.8-flash-medium',
    'gemini-3.8-flash-low',
    'gemini-3.1-pro',
    'gemini-1.5-pro',
    'gemini-1.5-flash',
    'claude-sonnet-4-6',
    'gpt-6-sol'
  ],
  grok: [
    'grok-4.7-build-fast',
    'grok-3',
    'grok-2',
    'grok-2-mini',
    'grok-beta'
  ],
  kimi: [
    'kimi-code/kimi-for-coding',
    'kimi-latest',
    'kimi-k1.5',
    'moonshot-v1-128k',
    'moonshot-v1-32k',
    'moonshot-v1-8k'
  ]
};

export function AgentConfigGrid({
  agents,
  onAgentUpdated
}: AgentConfigGridProps) {
  const [savingSeat, setSavingSeat] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<'all' | 'live' | 'antigravity' | 'codex' | 'claude' | 'grok' | 'kimi'>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Local state map for inline edits
  const [localConfigs, setLocalConfigs] = useState<Record<string, Partial<AgentSeatConfig>>>({});

  const activeCount = agents.filter(a => a.status === 'busy').length;

  const sortedAndFilteredAgents = useMemo(() => {
    return agents
      .filter(agent => {
        if (filterType === 'live' && agent.status !== 'busy') return false;
        if (filterType === 'antigravity' && agent.type !== 'antigravity') return false;
        if (filterType === 'codex' && agent.type !== 'codex') return false;
        if (filterType === 'claude' && agent.type !== 'claude') return false;
        if (filterType === 'grok' && agent.type !== 'grok') return false;
        if (filterType === 'kimi' && agent.type !== 'kimi') return false;
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          return agent.seat.toLowerCase().includes(q) ||
                 agent.role.toLowerCase().includes(q) ||
                 agent.host.toLowerCase().includes(q) ||
                 agent.model.toLowerCase().includes(q);
        }
        return true;
      })
      .sort((a, b) => {
        // Active / busy agents first
        if (a.status === 'busy' && b.status !== 'busy') return -1;
        if (b.status === 'busy' && a.status !== 'busy') return 1;
        return a.seat.localeCompare(b.seat);
      });
  }, [agents, filterType, searchQuery]);

  const getSeatConfig = (agent: AgentSeatConfig) => {
    return {
      model: localConfigs[agent.seat]?.model ?? agent.model,
      reasoning_effort: localConfigs[agent.seat]?.reasoning_effort ?? agent.reasoning_effort ?? 'medium',
      turn_cap: localConfigs[agent.seat]?.turn_cap ?? agent.turn_cap ?? 25,
      status: localConfigs[agent.seat]?.status ?? agent.status
    };
  };

  const handleFieldChange = (seat: string, field: string, value: any) => {
    setLocalConfigs(prev => ({
      ...prev,
      [seat]: {
        ...prev[seat],
        [field]: value
      }
    }));
  };

  const handleSave = async (seat: string) => {
    const config = localConfigs[seat];
    if (!config) return;

    setSavingSeat(seat);
    try {
      const res = await fetch('/api/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seat, ...config })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      toast.success(`Agent config for ${seat} updated.`);
      onAgentUpdated();
    } catch (err: any) {
      toast.error(`Failed to update ${seat}: ${err.message}`);
    } finally {
      setSavingSeat(null);
    }
  };

  return (
    <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 flex flex-col h-[640px]">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-zinc-800 mb-2">
        <div className="flex items-center space-x-2">
          <Bot className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-zinc-100">
            Headless Swarm Agents & Configuration
          </h3>
        </div>
        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="text-emerald-400 font-bold flex items-center space-x-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>{activeCount} Live</span>
          </span>
          <span className="text-zinc-500">/</span>
          <span className="text-zinc-400">{agents.length} Registered</span>
        </div>
      </div>

      {/* Quick Filter & Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-zinc-800/80 mb-2.5">
        <div className="flex items-center space-x-1 text-[11px] font-mono">
          {[
            { id: 'all', label: `All (${agents.length})` },
            { id: 'live', label: `Live (${activeCount})` },
            { id: 'antigravity', label: 'AGY' },
            { id: 'codex', label: 'Codex' },
            { id: 'claude', label: 'Claude' },
            { id: 'grok', label: 'Grok' },
            { id: 'kimi', label: 'Kimi' },
          ].map(f => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilterType(f.id as any)}
              className={`px-2 py-0.5 rounded transition-colors ${
                filterType === f.id
                  ? 'bg-zinc-800 text-cyan-400 font-bold border border-zinc-700'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="Filter seat, role..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="px-2 py-0.5 rounded bg-zinc-950 border border-zinc-800 text-[11px] font-mono text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-700 w-36"
        />
      </div>

      {/* Agents Scrollable List */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-3">
        {sortedAndFilteredAgents.map((agent) => {
          const cfg = getSeatConfig(agent);
          const isDirty = localConfigs[agent.seat] !== undefined;
          const availableModels = MODELS_BY_TYPE[agent.type as keyof typeof MODELS_BY_TYPE] || MODELS_BY_TYPE.claude;

          return (
            <div
              key={agent.seat}
              className="p-3 rounded bg-zinc-950/70 border border-zinc-800/90 space-y-2.5 font-mono text-xs"
            >
              {/* Card Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="font-bold text-zinc-100">{agent.seat}</span>
                  <span className={`px-1.5 py-0.2 rounded text-[10px] uppercase font-bold ${
                    agent.type === 'antigravity'
                      ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                      : agent.type === 'codex'
                      ? 'bg-amber-950 text-amber-400 border border-amber-800'
                      : agent.type === 'grok'
                      ? 'bg-orange-950 text-orange-400 border border-orange-800'
                      : agent.type === 'kimi'
                      ? 'bg-teal-950 text-teal-400 border border-teal-800'
                      : 'bg-indigo-950 text-indigo-400 border border-indigo-800'
                  }`}>
                    {agent.type}
                  </span>
                  {cfg.status === 'busy' ? (
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800 flex items-center space-x-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      <span>LIVE</span>
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.2 rounded text-[10px] text-zinc-500 bg-zinc-900 border border-zinc-800">
                      IDLE
                    </span>
                  )}
                </div>

                <div className="text-[11px] text-zinc-500">
                  Host: {agent.host}
                </div>
              </div>

              {/* Form Controls */}
              <div className="grid grid-cols-2 gap-2">
                {/* Model Selector */}
                <div>
                  <label className="text-[10px] text-zinc-500 block mb-1">MODEL</label>
                  <select
                    value={cfg.model}
                    onChange={(e) => handleFieldChange(agent.seat, 'model', e.target.value)}
                    className="w-full p-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs focus:outline-none focus:border-zinc-700"
                  >
                    {availableModels.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>

                {/* Reasoning Effort */}
                <div>
                  <label className="text-[10px] text-zinc-500 block mb-1">REASONING EFFORT</label>
                  <select
                    value={cfg.reasoning_effort}
                    onChange={(e) => handleFieldChange(agent.seat, 'reasoning_effort', e.target.value)}
                    className="w-full p-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs focus:outline-none focus:border-zinc-700 capitalize"
                  >
                    {['none', 'low', 'medium', 'high', 'native'].map(eff => (
                      <option key={eff} value={eff}>{eff}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Turn Cap Slider (Rule 58: Hard Cap 60) */}
              <div>
                <div className="flex items-center justify-between text-[10px] text-zinc-500 mb-1">
                  <span>TURN CAP (FLEET RULE 58: MAX 60)</span>
                  <span className="text-zinc-300 font-bold">{cfg.turn_cap} turns</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="60"
                  value={cfg.turn_cap}
                  onChange={(e) => handleFieldChange(agent.seat, 'turn_cap', parseInt(e.target.value, 10))}
                  className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                />
              </div>

              {/* Status and Action Buttons */}
              <div className="flex items-center justify-between pt-1 border-t border-zinc-900">
                <div className="flex items-center space-x-1.5">
                  <span className="text-[10px] text-zinc-500">STATUS:</span>
                  <select
                    value={cfg.status}
                    onChange={(e) => handleFieldChange(agent.seat, 'status', e.target.value)}
                    className="p-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-200 text-[11px] focus:outline-none"
                  >
                    {['idle', 'busy', 'paused', 'offline'].map(st => (
                      <option key={st} value={st}>{st}</option>
                    ))}
                  </select>
                </div>

                <button
                  type="button"
                  onClick={() => handleSave(agent.seat)}
                  disabled={!isDirty || savingSeat === agent.seat}
                  className="inline-flex items-center px-2.5 py-1 rounded bg-emerald-950/80 hover:bg-emerald-900 text-emerald-400 border border-emerald-800 disabled:opacity-30 disabled:pointer-events-none transition-colors text-[11px]"
                >
                  <Check className="w-3 h-3 mr-1" />
                  {savingSeat === agent.seat ? 'Saving...' : 'Apply'}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
