"use client";

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import type {
  ArchitectureResponse,
  ArchitectureTopology,
  ClusterNode,
  EsxiCloneInfo,
  AgentSeatConfig
} from '@/lib/types';
import { mockArchitectureResponse } from '@/lib/mock-data';
import {
  Server,
  Cpu,
  Bot,
  Shield,
  Layers,
  Search,
  Activity,
  Box,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Terminal,
  Database,
  Radio,
  Eye,
  LayoutGrid,
  Network,
  X
} from 'lucide-react';

interface ArchitectureVisualizerProps {
  initialData?: ArchitectureResponse;
}

function createFallbackNode(info: {
  name: string;
  ip: string;
  role?: 'hub' | 'ops' | 'stg' | 'ai' | 'wrk-bd' | 'wrk-test' | 'spr-pool' | string;
  tier: string;
  status?: string;
  latency_ms?: number | null;
  is_local?: boolean;
  is_blacklisted?: boolean;
}): ClusterNode {
  return {
    name: info.name,
    fqdn: `${info.name}.boylenet`,
    ip: info.ip,
    role: info.role || 'wrk-bd',
    tier: info.tier,
    status: info.status || 'up',
    latency_ms: info.latency_ms !== undefined ? info.latency_ms : 0.3,
    is_local: info.is_local ?? false,
    is_blacklisted: info.is_blacklisted ?? false,
  };
}

export function ArchitectureVisualizer({ initialData }: ArchitectureVisualizerProps) {
  const [data, setData] = useState<ArchitectureResponse>(initialData || mockArchitectureResponse);
  const [isLoading, setIsLoading] = useState<boolean>(!initialData);
  const [selectedTier, setSelectedTier] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedNode, setSelectedNode] = useState<ClusterNode | null>(null);
  const [viewMode, setViewMode] = useState<'split' | 'graph' | 'grid'>('split');
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  const inspectorRef = useRef<HTMLDivElement | null>(null);

  const fetchTopology = useCallback(async () => {
    try {
      const res = await fetch('/api/architecture');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: ArchitectureResponse = await res.json();
      setData(json);
    } catch (err) {
      console.warn('[ArchitectureVisualizer] Failed to load /api/architecture:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTopology();

    const handleRefresh = () => {
      fetchTopology();
    };

    window.addEventListener('swarm:refresh', handleRefresh);
    const interval = setInterval(fetchTopology, 6000);

    return () => {
      window.removeEventListener('swarm:refresh', handleRefresh);
      clearInterval(interval);
    };
  }, [fetchTopology]);

  const topology: ArchitectureTopology | undefined = data?.topology;

  // Flatten all nodes for quick search
  const allNodes: ClusterNode[] = useMemo(() => {
    if (!topology || !topology.tiers) return [];
    const t = topology.tiers;
    return [
      ...(t.control_plane || []),
      ...(t.ai_satellite || []),
      ...(t.workers || []),
      ...(t.esxi_spare_pool || []),
      ...(t.isolated_boundary || [])
    ];
  }, [topology]);

  // Filtered nodes based on active tier and search query
  const filteredNodes = useMemo(() => {
    return allNodes.filter(node => {
      if (selectedTier !== 'all') {
        if (selectedTier === 'control' && !['hub', 'ops', 'stg'].includes(node.role || '')) return false;
        if (selectedTier === 'ai' && node.role !== 'ai') return false;
        if (selectedTier === 'workers' && (!['wrk-bd', 'wrk-test'].includes(node.role || '') || node.is_blacklisted)) return false;
        if (selectedTier === 'esxi' && node.role !== 'spr-pool') return false;
        if (selectedTier === 'isolated' && !node.is_blacklisted) return false;
      }

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          node.name.toLowerCase().includes(q) ||
          node.ip.toLowerCase().includes(q) ||
          (node.fqdn && node.fqdn.toLowerCase().includes(q)) ||
          (node.role && node.role.toLowerCase().includes(q))
        );
      }

      return true;
    });
  }, [allNodes, selectedTier, searchQuery]);

  const handleSelectNode = useCallback((node: ClusterNode) => {
    setSelectedNode(prev => (prev?.ip === node.ip ? null : node));
    if (selectedNode?.ip !== node.ip) {
      setTimeout(() => {
        if (typeof inspectorRef.current?.scrollIntoView === 'function') {
          inspectorRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }, 50);
    }
  }, [selectedNode]);

  const getAgentBadgeColor = (type: string) => {
    switch (type) {
      case 'antigravity':
        return 'bg-cyan-950 text-cyan-400 border-cyan-800';
      case 'codex':
        return 'bg-amber-950 text-amber-400 border-amber-800';
      case 'grok':
        return 'bg-orange-950 text-orange-400 border-orange-800';
      case 'kimi':
        return 'bg-teal-950 text-teal-400 border-teal-800';
      case 'claude':
      default:
        return 'bg-indigo-950 text-indigo-400 border-indigo-800';
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner Ribbon */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-3 rounded-lg bg-zinc-900 border border-zinc-800">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded bg-zinc-800 text-cyan-400">
            <Cpu className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-zinc-100 uppercase tracking-wide">
              Live Architecture Visualizer & Heterogeneous Swarm Topology
            </h2>
            <p className="text-xs text-zinc-400">
              27 Cluster Nodes (10.0.70.*) • VMware ESXi Ephemeral Clones • Multi-Model Agent Placements
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* View Mode Selector */}
          <div className="flex items-center bg-zinc-950/80 p-0.5 rounded border border-zinc-800">
            <button
              type="button"
              onClick={() => setViewMode('split')}
              className={`px-2 py-1 rounded text-xs font-mono flex items-center space-x-1 transition-colors ${
                viewMode === 'split' ? 'bg-zinc-800 text-cyan-400 font-bold' : 'text-zinc-400 hover:text-zinc-200'
              }`}
              title="Split View (Topology Diagram + Node Matrix)"
            >
              <Eye className="w-3 h-3" />
              <span>Split</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('graph')}
              className={`px-2 py-1 rounded text-xs font-mono flex items-center space-x-1 transition-colors ${
                viewMode === 'graph' ? 'bg-zinc-800 text-cyan-400 font-bold' : 'text-zinc-400 hover:text-zinc-200'
              }`}
              title="Interactive Topology Graph"
            >
              <Network className="w-3 h-3" />
              <span>Diagram</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('grid')}
              className={`px-2 py-1 rounded text-xs font-mono flex items-center space-x-1 transition-colors ${
                viewMode === 'grid' ? 'bg-zinc-800 text-cyan-400 font-bold' : 'text-zinc-400 hover:text-zinc-200'
              }`}
              title="Node Specification Grid"
            >
              <LayoutGrid className="w-3 h-3" />
              <span>Grid</span>
            </button>
          </div>

          <button
            type="button"
            onClick={fetchTopology}
            disabled={isLoading}
            className="inline-flex items-center px-3 py-1.5 rounded text-xs font-mono bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh Topology
          </button>
        </div>
      </div>

      {/* High-Level Fleet Topology KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 rounded bg-zinc-950/70 border border-zinc-800 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400">
            <span>Cluster Mesh Nodes</span>
            <Server className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div className="text-xl font-mono font-bold text-zinc-100">
            {topology?.total_nodes || 27} Nodes
          </div>
          <div className="text-[10px] text-emerald-400 font-mono">
            {topology?.online_nodes || 26} Online • 1 Isolated (test2)
          </div>
        </div>

        <div className="p-3 rounded bg-zinc-950/70 border border-zinc-800 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400">
            <span>ESXi Ephemeral Clones</span>
            <Box className="w-3.5 h-3.5 text-purple-400" />
          </div>
          <div className="text-xl font-mono font-bold text-purple-300">
            {topology?.esxi_clones?.length || 4} Sandboxes
          </div>
          <div className="text-[10px] text-zinc-500 font-mono">
            Leased on spr-pool (10.0.70.120..185)
          </div>
        </div>

        <div className="p-3 rounded bg-zinc-950/70 border border-zinc-800 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400">
            <span>Active Swarm Seats</span>
            <Bot className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="text-xl font-mono font-bold text-emerald-400">
            {topology?.active_agents ?? 19} Agents
          </div>
          <div className="text-[10px] text-zinc-500 font-mono">
            Claude / Codex / AGY / Grok / Kimi
          </div>
        </div>

        <div className="p-3 rounded bg-zinc-950/70 border border-zinc-800 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400">
            <span>Interconnect Latency</span>
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="text-xl font-mono font-bold text-emerald-400">
            &lt; 0.50 ms
          </div>
          <div className="text-[10px] text-zinc-500 font-mono">
            Sub-millisecond intra-rack mesh
          </div>
        </div>
      </div>

      {/* INTERACTIVE SWARM ARCHITECTURE TOPOLOGY VISUALIZER DIAGRAM */}
      {(viewMode === 'split' || viewMode === 'graph') && (
        <div className="p-4 rounded-lg bg-zinc-950 border border-zinc-800 shadow-xl space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-zinc-800/80">
            <div className="flex items-center space-x-2">
              <Network className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-semibold text-zinc-100 uppercase tracking-wider font-mono">
                Interactive Multi-Tier Swarm Topology Map
              </h3>
            </div>
            <div className="flex items-center space-x-3 text-[10px] font-mono text-zinc-400">
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>Controller Core</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-cyan-400" />
                <span>AI Satellites</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-amber-400" />
                <span>Workers</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-purple-400" />
                <span>ESXi Pool</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-rose-400" />
                <span>Rule 21 Target</span>
              </span>
            </div>
          </div>

          <div className="relative w-full overflow-hidden rounded bg-gradient-to-b from-zinc-950 via-zinc-900/40 to-zinc-950 border border-zinc-800/50 p-2">
            <svg
              viewBox="0 0 1000 460"
              className="w-full h-auto select-none"
              style={{ minHeight: '340px' }}
            >
              <defs>
                {/* Glow Filters */}
                <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                <filter id="glow-emerald" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="4" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                <filter id="glow-rose" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                {/* Gradients */}
                <linearGradient id="link-grad-ai" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.8" />
                </linearGradient>
                <linearGradient id="link-grad-ops" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity="0.8" />
                </linearGradient>
                <linearGradient id="link-grad-wrk" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.8" />
                </linearGradient>
                <linearGradient id="link-grad-esxi" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#a855f7" stopOpacity="0.8" />
                </linearGradient>
              </defs>

              {/* Topology Background Clusters / Tier Enclosures */}
              {/* Operations & CI Plane (Top Left) */}
              <rect x="30" y="20" width="280" height="150" rx="10" fill="#18181b" fillOpacity="0.5" stroke="#27272a" strokeWidth="1" strokeDasharray="4 4" />
              <text x="45" y="42" fill="#71717a" fontSize="10" fontFamily="monospace" fontWeight="bold">TIER 1: OPERATIONS &amp; CI PLANE</text>

              {/* AI Satellite Tier (Top Right) */}
              <rect x="690" y="20" width="280" height="150" rx="10" fill="#18181b" fillOpacity="0.5" stroke="#083344" strokeWidth="1" strokeDasharray="4 4" />
              <text x="705" y="42" fill="#06b6d4" fontSize="10" fontFamily="monospace" fontWeight="bold">TIER 2: AI SATELLITES (TEI / OLLAMA)</text>

              {/* Worker Mesh Cluster (Bottom Left to Center) */}
              <rect x="30" y="270" width="620" height="170" rx="10" fill="#18181b" fillOpacity="0.5" stroke="#451a03" strokeWidth="1" strokeDasharray="4 4" />
              <text x="45" y="292" fill="#f59e0b" fontSize="10" fontFamily="monospace" fontWeight="bold">TIER 3: HETEROGENEOUS WORKER MESH (12 NODES)</text>

              {/* ESXi Spare Pool & Ephemeral Sandboxes (Bottom Right) */}
              <rect x="670" y="270" width="300" height="170" rx="10" fill="#18181b" fillOpacity="0.5" stroke="#3b0764" strokeWidth="1" strokeDasharray="4 4" />
              <text x="685" y="292" fill="#c084fc" fontSize="10" fontFamily="monospace" fontWeight="bold">TIER 4: ESXi SPARE POOL &amp; SANDBOXES</text>

              {/* Interconnect Vectors from Central Hub (500, 200) */}
              {/* Hub to Operations */}
              <path d="M 450 180 Q 300 150 200 140" fill="none" stroke="url(#link-grad-ops)" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.6" />
              {/* Hub to AI Satellites */}
              <path d="M 550 180 Q 700 150 800 140" fill="none" stroke="url(#link-grad-ai)" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.6" />
              {/* Hub to Worker Mesh */}
              <path d="M 470 230 Q 350 270 300 310" fill="none" stroke="url(#link-grad-wrk)" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.6" />
              {/* Hub to ESXi Hypervisors */}
              <path d="M 530 230 Q 650 270 750 310" fill="none" stroke="url(#link-grad-esxi)" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.6" />
              {/* Hub to Target Site test2 */}
              <path d="M 500 240 L 590 390" fill="none" stroke="#e11d48" strokeWidth="1.5" strokeDasharray="2 4" opacity="0.7" />

              {/* Dynamic Animated Pulse Beams */}
              <circle cx="500" cy="200" r="42" fill="none" stroke="#10b981" strokeWidth="1" opacity="0.25">
                <animate attributeName="r" values="30;60;30" dur="4s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.4;0.05;0.4" dur="4s" repeatCount="indefinite" />
              </circle>

              {/* --- CENTRAL CONTROLLER HUB NODE --- */}
              {(() => {
                const hubNode: ClusterNode = allNodes.find(n => n.ip === '10.0.70.164') || createFallbackNode({
                  name: 'hub-mesh01',
                  ip: '10.0.70.164',
                  role: 'hub',
                  tier: 'Primary Controller',
                  status: 'up',
                  latency_ms: 0.05,
                  is_local: true,
                  is_blacklisted: false,
                });
                const isSelected = selectedNode?.ip === hubNode.ip;
                const agentsOnHub = topology?.agent_allocations?.['hub-mesh01'] || [];

                return (
                  <g
                    transform="translate(430, 160)"
                    className="cursor-pointer transition-all"
                    onClick={() => handleSelectNode(hubNode)}
                    onMouseEnter={() => setHoveredNode(hubNode.ip)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    <rect
                      x="0"
                      y="0"
                      width="140"
                      height="80"
                      rx="8"
                      fill="#09090b"
                      stroke={isSelected ? '#06b6d4' : '#10b981'}
                      strokeWidth={isSelected ? '2.5' : '1.5'}
                      filter="url(#glow-emerald)"
                    />
                    <circle cx="18" cy="20" r="4" fill="#10b981" />
                    <text x="28" y="24" fill="#f4f4f5" fontSize="11" fontFamily="monospace" fontWeight="bold">hub-mesh01</text>
                    <text x="28" y="38" fill="#71717a" fontSize="9" fontFamily="monospace">10.0.70.164 • Core</text>
                    <rect x="12" y="48" width="116" height="20" rx="4" fill="#052e16" stroke="#166534" strokeWidth="0.5" />
                    <text x="18" y="62" fill="#4ade80" fontSize="9" fontFamily="monospace" fontWeight="bold">
                      {agentsOnHub.length} Agents Assigned
                    </text>
                  </g>
                );
              })()}

              {/* --- TIER 1: OPERATIONS & CI (ops-mcp01, ops-cicd01, ops-test01, stg-cache01, stg-cache02) --- */}
              {[
                { name: 'ops-mcp01', ip: '10.0.70.25', x: 45, y: 55 },
                { name: 'ops-cicd01', ip: '10.0.70.162', x: 175, y: 55 },
                { name: 'ops-test01', ip: '10.0.70.107', x: 45, y: 110 },
                { name: 'stg-cache01', ip: '10.0.70.182', x: 175, y: 110 }
              ].map(nodeInfo => {
                const node: ClusterNode = allNodes.find(n => n.ip === nodeInfo.ip) || createFallbackNode({
                  name: nodeInfo.name,
                  ip: nodeInfo.ip,
                  role: 'ops',
                  tier: 'Operations',
                  status: 'up',
                  latency_ms: 0.32,
                  is_local: false,
                });
                const isSelected = selectedNode?.ip === node.ip;
                return (
                  <g
                    key={node.ip}
                    transform={`translate(${nodeInfo.x}, ${nodeInfo.y})`}
                    className="cursor-pointer"
                    onClick={() => handleSelectNode(node)}
                    onMouseEnter={() => setHoveredNode(node.ip)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    <rect
                      x="0"
                      y="0"
                      width="120"
                      height="45"
                      rx="6"
                      fill="#09090b"
                      stroke={isSelected ? '#06b6d4' : '#3f3f46'}
                      strokeWidth={isSelected ? '2' : '1'}
                    />
                    <circle cx="12" cy="16" r="3" fill="#10b981" />
                    <text x="20" y="19" fill="#f4f4f5" fontSize="10" fontFamily="monospace" fontWeight="bold">{node.name}</text>
                    <text x="20" y="33" fill="#71717a" fontSize="8" fontFamily="monospace">{node.ip}</text>
                  </g>
                );
              })}

              {/* --- TIER 2: AI SATELLITES (ai-srv01, ai-dev01, ai-infer01, ai-ollama01) --- */}
              {[
                { name: 'ai-srv01', ip: '10.0.70.72', x: 705, y: 55, svc: 'LiteLLM Gateway' },
                { name: 'ai-dev01', ip: '10.0.70.81', x: 835, y: 55, svc: 'RAG Dev Cache' },
                { name: 'ai-infer01', ip: '10.0.70.125', x: 705, y: 110, svc: 'TEI Embeddings' },
                { name: 'ai-ollama01', ip: '10.0.70.228', x: 835, y: 110, svc: 'Ollama Inference' }
              ].map(nodeInfo => {
                const node: ClusterNode = allNodes.find(n => n.ip === nodeInfo.ip) || createFallbackNode({
                  name: nodeInfo.name,
                  ip: nodeInfo.ip,
                  role: 'ai',
                  tier: 'AI Satellite',
                  status: 'up',
                  latency_ms: 0.32,
                  is_local: false,
                });
                const isSelected = selectedNode?.ip === node.ip;
                return (
                  <g
                    key={node.ip}
                    transform={`translate(${nodeInfo.x}, ${nodeInfo.y})`}
                    className="cursor-pointer"
                    onClick={() => handleSelectNode(node)}
                    onMouseEnter={() => setHoveredNode(node.ip)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    <rect
                      x="0"
                      y="0"
                      width="120"
                      height="45"
                      rx="6"
                      fill="#09090b"
                      stroke={isSelected ? '#06b6d4' : '#0e7490'}
                      strokeWidth={isSelected ? '2' : '1'}
                      filter={isSelected ? 'url(#glow-cyan)' : undefined}
                    />
                    <circle cx="12" cy="16" r="3" fill="#06b6d4" />
                    <text x="20" y="19" fill="#f4f4f5" fontSize="10" fontFamily="monospace" fontWeight="bold">{node.name}</text>
                    <text x="20" y="33" fill="#0891b2" fontSize="8" fontFamily="monospace">{nodeInfo.svc}</text>
                  </g>
                );
              })}

              {/* --- TIER 3: WORKER MESH (wrk-bd01..05, wrk-test01..07) --- */}
              {[
                { name: 'wrk-bd01', ip: '10.0.70.50', x: 45, y: 310 },
                { name: 'wrk-bd02', ip: '10.0.70.51', x: 145, y: 310 },
                { name: 'wrk-bd03', ip: '10.0.70.52', x: 245, y: 310 },
                { name: 'wrk-bd04', ip: '10.0.70.53', x: 345, y: 310 },
                { name: 'wrk-bd05', ip: '10.0.70.54', x: 445, y: 310 },
                { name: 'wrk-test01', ip: '10.0.70.83', x: 545, y: 310 },
                { name: 'wrk-test03', ip: '10.0.70.80', x: 45, y: 375 },
                { name: 'wrk-test04', ip: '10.0.70.82', x: 145, y: 375 },
                { name: 'wrk-test05', ip: '10.0.70.85', x: 245, y: 375 },
                { name: 'wrk-test06', ip: '10.0.70.249', x: 345, y: 375 },
                { name: 'wrk-test07', ip: '10.0.70.84', x: 445, y: 375 }
              ].map(nodeInfo => {
                const node: ClusterNode = allNodes.find(n => n.ip === nodeInfo.ip) || createFallbackNode({
                  name: nodeInfo.name,
                  ip: nodeInfo.ip,
                  role: 'wrk-bd',
                  tier: 'Worker Node',
                  status: 'up',
                  latency_ms: 0.32,
                  is_local: false,
                });
                const isSelected = selectedNode?.ip === node.ip;
                const rawNodeAgents = topology?.agent_allocations?.[node.name] || topology?.agent_allocations?.[node.ip];
                const agentsOnNode = Array.isArray(rawNodeAgents) ? rawNodeAgents : [];
                const liveCount = agentsOnNode.filter(a => a.status === 'busy').length;

                return (
                  <g
                    key={node.ip}
                    transform={`translate(${nodeInfo.x}, ${nodeInfo.y})`}
                    className="cursor-pointer"
                    onClick={() => handleSelectNode(node)}
                    onMouseEnter={() => setHoveredNode(node.ip)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    <rect
                      x="0"
                      y="0"
                      width="92"
                      height="50"
                      rx="5"
                      fill="#09090b"
                      stroke={isSelected ? '#06b6d4' : liveCount > 0 ? '#10b981' : '#3f3f46'}
                      strokeWidth={isSelected ? '2' : '1'}
                    />
                    <circle cx="10" cy="14" r="3" fill={liveCount > 0 ? '#10b981' : '#71717a'} />
                    <text x="18" y="17" fill="#f4f4f5" fontSize="9" fontFamily="monospace" fontWeight="bold">{node.name}</text>
                    <text x="18" y="29" fill="#71717a" fontSize="7.5" fontFamily="monospace">{node.ip}</text>
                    {agentsOnNode.length > 0 && (
                      <text x="10" y="42" fill={liveCount > 0 ? '#34d399' : '#a1a1aa'} fontSize="7" fontFamily="monospace">
                        {agentsOnNode.length} seat(s) {liveCount > 0 ? `(${liveCount} live)` : ''}
                      </text>
                    )}
                  </g>
                );
              })}

              {/* --- TIER 4: ESXi HYPERVISORS (spr-pool01..05) & SANDBOXES --- */}
              {[
                { name: 'spr-pool01', ip: '10.0.70.120', x: 685, y: 310 },
                { name: 'spr-pool02', ip: '10.0.70.183', x: 780, y: 310 },
                { name: 'spr-pool03', ip: '10.0.70.184', x: 875, y: 310 },
                { name: 'spr-pool04', ip: '10.0.70.185', x: 685, y: 375 },
                { name: 'spr-pool05', ip: '10.0.70.149', x: 780, y: 375 }
              ].map(nodeInfo => {
                const node: ClusterNode = allNodes.find(n => n.ip === nodeInfo.ip) || createFallbackNode({
                  name: nodeInfo.name,
                  ip: nodeInfo.ip,
                  role: 'spr-pool',
                  tier: 'Spare Pool',
                  status: 'up',
                  latency_ms: 0.42,
                  is_local: false,
                });
                const isSelected = selectedNode?.ip === node.ip;
                return (
                  <g
                    key={node.ip}
                    transform={`translate(${nodeInfo.x}, ${nodeInfo.y})`}
                    className="cursor-pointer"
                    onClick={() => handleSelectNode(node)}
                    onMouseEnter={() => setHoveredNode(node.ip)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    <rect
                      x="0"
                      y="0"
                      width="88"
                      height="50"
                      rx="5"
                      fill="#09090b"
                      stroke={isSelected ? '#06b6d4' : '#6b21a8'}
                      strokeWidth={isSelected ? '2' : '1'}
                    />
                    <circle cx="10" cy="14" r="3" fill="#c084fc" />
                    <text x="18" y="17" fill="#f4f4f5" fontSize="9" fontFamily="monospace" fontWeight="bold">{node.name}</text>
                    <text x="18" y="29" fill="#71717a" fontSize="7.5" fontFamily="monospace">{node.ip}</text>
                    <text x="10" y="42" fill="#c084fc" fontSize="7" fontFamily="monospace">ESXi Hypervisor</text>
                  </g>
                );
              })}

              {/* --- RULE 21 ISOLATED TARGET SITE (wrk-test02 / 10.0.70.95) --- */}
              {(() => {
                const isoNode: ClusterNode = allNodes.find(n => n.ip === '10.0.70.95') || createFallbackNode({
                  name: 'wrk-test02',
                  ip: '10.0.70.95',
                  role: 'wrk-test',
                  tier: 'Target Site',
                  status: 'operator-only',
                  latency_ms: null,
                  is_local: false,
                  is_blacklisted: true,
                });
                const isSelected = selectedNode?.ip === isoNode.ip;

                return (
                  <g
                    transform="translate(875, 375)"
                    className="cursor-pointer"
                    onClick={() => handleSelectNode(isoNode)}
                    onMouseEnter={() => setHoveredNode(isoNode.ip)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    <rect
                      x="0"
                      y="0"
                      width="88"
                      height="50"
                      rx="5"
                      fill="#450a0a"
                      stroke={isSelected ? '#06b6d4' : '#e11d48'}
                      strokeWidth={isSelected ? '2' : '1.5'}
                      strokeDasharray="2 2"
                      filter="url(#glow-rose)"
                    />
                    <circle cx="10" cy="14" r="3" fill="#f43f5e" />
                    <text x="18" y="17" fill="#fecdd3" fontSize="9" fontFamily="monospace" fontWeight="bold">{isoNode.name}</text>
                    <text x="18" y="29" fill="#fda4af" fontSize="7.5" fontFamily="monospace">{isoNode.ip}</text>
                    <text x="10" y="42" fill="#fb7185" fontSize="7" fontFamily="monospace" fontWeight="bold">ISOLATED (R21)</text>
                  </g>
                );
              })()}
            </svg>
          </div>
        </div>
      )}

      {/* SELECTED NODE INSPECTOR DRAWER (Rendered Prominently with Auto-Focus) */}
      {selectedNode && (
        <div
          ref={inspectorRef}
          className="p-4 rounded-lg bg-zinc-900 border-2 border-cyan-500 shadow-2xl space-y-3 font-mono text-xs transition-all animate-in fade-in duration-200"
        >
          <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
            <div className="flex items-center space-x-2">
              <Server className="w-4 h-4 text-cyan-400" />
              <h3 className="text-sm font-semibold text-zinc-100">
                Node Specification: {selectedNode.name} ({selectedNode.ip})
              </h3>
            </div>
            <button
              type="button"
              onClick={() => setSelectedNode(null)}
              className="inline-flex items-center px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-zinc-100 border border-zinc-700 text-[11px] space-x-1"
            >
              <X className="w-3 h-3" />
              <span>Close Inspector</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="p-2.5 rounded bg-zinc-950/70 border border-zinc-800 space-y-1">
              <div className="text-[10px] text-zinc-500 uppercase">FQDN &amp; Networking</div>
              <div className="text-zinc-200 font-semibold">{selectedNode.fqdn || selectedNode.name}</div>
              <div className="text-zinc-400 text-[11px]">IP: {selectedNode.ip}</div>
              <div className="text-zinc-400 text-[11px]">Subnet: 10.0.70.0/24 (mesh.local)</div>
            </div>

            <div className="p-2.5 rounded bg-zinc-950/70 border border-zinc-800 space-y-1">
              <div className="text-[10px] text-zinc-500 uppercase">Architecture Classification</div>
              <div className="text-cyan-400 font-semibold">{selectedNode.tier}</div>
              <div className="text-zinc-400 text-[11px]">Role: {selectedNode.role || 'worker'}</div>
              <div className="text-zinc-400 text-[11px]">
                Status: <span className={selectedNode.is_blacklisted ? 'text-rose-400' : 'text-emerald-400'}>{selectedNode.status}</span>
              </div>
            </div>

            <div className="p-2.5 rounded bg-zinc-950/70 border border-zinc-800 space-y-1">
              <div className="text-[10px] text-zinc-500 uppercase">Fleet Safety Protocol</div>
              {selectedNode.is_blacklisted ? (
                <div className="text-rose-400 text-[11px]">
                  Fleet Rule 21: Strictly isolated target site. Zero automated probes or logins permitted.
                </div>
              ) : selectedNode.is_local ? (
                <div className="text-emerald-400 text-[11px]">
                  Primary controller host (10.0.70.164). Heavy indexing redirected to wrk-test04.
                </div>
              ) : (
                <div className="text-zinc-400 text-[11px]">
                  Standard cluster mesh node. TCP port 22 probed for health checks.
                </div>
              )}
            </div>
          </div>

          {/* Assigned Swarm Agent Seats on this Node */}
          {(() => {
            const rawSelected = topology?.agent_allocations?.[selectedNode.name] ||
                                topology?.agent_allocations?.[selectedNode.ip] ||
                                (selectedNode.is_local ? topology?.agent_allocations?.['hub-mesh01'] : []);
            const selectedAgents = (Array.isArray(rawSelected) ? rawSelected : []) as AgentSeatConfig[];

            return (
              <div className="p-3 rounded bg-zinc-950/70 border border-zinc-800 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-[10px] text-zinc-500 uppercase flex items-center space-x-1.5">
                    <Bot className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Assigned Swarm Agent Seats ({selectedAgents.length})</span>
                  </div>
                  {selectedAgents.filter((a: AgentSeatConfig) => a.status === 'busy').length > 0 && (
                    <span className="text-[10px] text-emerald-400 font-bold flex items-center space-x-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      <span>{selectedAgents.filter((a: AgentSeatConfig) => a.status === 'busy').length} Live Running</span>
                    </span>
                  )}
                </div>

                {selectedAgents.length === 0 ? (
                  <div className="text-zinc-500 text-[11px] italic py-1">
                    No autonomous swarm agents currently assigned to this node.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 pt-1">
                    {selectedAgents.map((agent: AgentSeatConfig) => (
                      <div
                        key={agent.seat}
                        className={`p-2 rounded border flex flex-col justify-between space-y-1 ${
                          agent.status === 'busy'
                            ? 'bg-zinc-900/90 border-emerald-800/80 shadow-sm'
                            : 'bg-zinc-900/50 border-zinc-800'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-zinc-100">{agent.seat}</span>
                          <span
                            className={`px-1.5 py-0.2 rounded text-[9px] uppercase font-bold border flex items-center space-x-1 ${
                              agent.status === 'busy'
                                ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
                                : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                            }`}
                          >
                            {agent.status === 'busy' && (
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                            )}
                            <span>{agent.status}</span>
                          </span>
                        </div>
                        <div className="text-[10px] text-zinc-400 flex items-center justify-between">
                          <span>Role: <span className="text-zinc-300 font-medium">{agent.role}</span></span>
                          <span className={`px-1 rounded text-[8px] uppercase font-bold border ${getAgentBadgeColor(agent.type)}`}>
                            {agent.type}
                          </span>
                        </div>
                        <div className="text-[10px] text-zinc-500 truncate">
                          Model: <span className="text-cyan-400 font-mono">{agent.model}</span>
                        </div>
                        {agent.pid && (
                          <div className="text-[9px] text-zinc-500">
                            PID: <span className="text-zinc-400 font-mono">{agent.pid}</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      )}

      {/* Tier Filter Tabs & Search Bar */}
      {(viewMode === 'split' || viewMode === 'grid') && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-zinc-900 border border-zinc-800">
            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { id: 'all', label: 'All 27 Nodes' },
                { id: 'control', label: 'Control Plane' },
                { id: 'ai', label: 'AI Satellites' },
                { id: 'workers', label: 'Workers' },
                { id: 'esxi', label: 'ESXi Spare Pool' },
                { id: 'isolated', label: 'Isolated Boundary' }
              ].map(tier => (
                <button
                  key={tier.id}
                  type="button"
                  onClick={() => setSelectedTier(tier.id)}
                  className={`px-2.5 py-1 rounded text-xs font-mono transition-colors ${
                    selectedTier === tier.id
                      ? 'bg-zinc-700 text-zinc-100 font-bold border border-zinc-600'
                      : 'bg-zinc-800/80 text-zinc-400 hover:bg-zinc-800 border border-zinc-800'
                  }`}
                >
                  {tier.label}
                </button>
              ))}
            </div>

            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-zinc-500" />
              <input
                type="text"
                placeholder="Search node, IP, or role..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1 rounded bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-zinc-600"
              />
            </div>
          </div>

          {/* Main Grid: 27 Nodes Architectural Topology */}
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs font-mono text-zinc-400">
              <span>Displaying {filteredNodes.length} of {allNodes.length} Nodes</span>
              <span className="text-[11px] text-zinc-500">Click any node card to inspect hardware &amp; agent seats</span>
            </div>

            {filteredNodes.length === 0 ? (
              <div className="h-32 flex items-center justify-center text-xs font-mono text-zinc-500 border border-dashed border-zinc-800 rounded">
                No cluster nodes match the selected tier or search criteria.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {filteredNodes.map((node) => {
                  const isBlacklisted = node.is_blacklisted;
                  const isLocal = node.is_local;
                  const isSelected = selectedNode?.ip === node.ip;
                  const rawAgents = topology?.agent_allocations?.[node.name] ||
                                    topology?.agent_allocations?.[node.ip] ||
                                    (isLocal ? topology?.agent_allocations?.['hub-mesh01'] : []);
                  const agentsOnNode = Array.isArray(rawAgents) ? rawAgents : [];

                  return (
                    <div
                      key={node.ip}
                      onClick={() => handleSelectNode(node)}
                      className={`p-3 rounded-lg border font-mono text-xs cursor-pointer transition-all ${
                        isSelected
                          ? 'bg-zinc-900 border-cyan-500 ring-1 ring-cyan-500 shadow-lg'
                          : isBlacklisted
                          ? 'bg-zinc-950/80 border-rose-900/60 hover:border-rose-700'
                          : isLocal
                          ? 'bg-zinc-950/80 border-emerald-900/60 hover:border-emerald-700'
                          : 'bg-zinc-950/80 border-zinc-800 hover:border-zinc-700'
                      }`}
                    >
                      {/* Node Top Header */}
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-1.5">
                          {isBlacklisted ? (
                            <Shield className="w-3.5 h-3.5 text-rose-400" />
                          ) : isLocal ? (
                            <Terminal className="w-3.5 h-3.5 text-emerald-400" />
                          ) : node.role === 'ai' ? (
                            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
                          ) : node.role === 'spr-pool' ? (
                            <Box className="w-3.5 h-3.5 text-purple-400" />
                          ) : (
                            <Server className="w-3.5 h-3.5 text-zinc-400" />
                          )}
                          <span className="font-bold text-zinc-100">{node.name}</span>
                        </div>

                        {isBlacklisted ? (
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-rose-950/80 text-rose-400 border border-rose-800">
                            ISOLATED
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-950/80 text-emerald-400 border border-emerald-800 flex items-center space-x-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                            <span>ONLINE</span>
                          </span>
                        )}
                      </div>

                      {/* Node Metadata Details */}
                      <div className="space-y-1 text-[11px] text-zinc-400">
                        <div className="flex justify-between">
                          <span className="text-zinc-500">IP:</span>
                          <span className="text-zinc-200">{node.ip}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500">Tier:</span>
                          <span className="text-zinc-300 truncate max-w-[150px]">{node.tier}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500">Latency:</span>
                          <span className={node.latency_ms !== null && node.latency_ms !== undefined ? 'text-emerald-400' : 'text-zinc-500'}>
                            {node.latency_ms !== null && node.latency_ms !== undefined ? `${node.latency_ms} ms` : 'N/A (hands-off)'}
                          </span>
                        </div>
                      </div>

                      {/* Assigned Swarm Agents Chip Ribbon */}
                      {agentsOnNode && agentsOnNode.length > 0 && (() => {
                        const activeCountOnNode = agentsOnNode.filter((a: AgentSeatConfig) => a.status === 'busy').length;
                        const sortedAgents = [...agentsOnNode].sort((a: AgentSeatConfig, b: AgentSeatConfig) => {
                          if (a.status === 'busy' && b.status !== 'busy') return -1;
                          if (b.status === 'busy' && a.status !== 'busy') return 1;
                          return 0;
                        });
                        return (
                          <div className="mt-2.5 pt-2 border-t border-zinc-800/80">
                            <div className="text-[10px] text-zinc-500 mb-1 flex items-center justify-between">
                              <span className="flex items-center space-x-1">
                                <Bot className="w-3 h-3 text-cyan-400" />
                                <span>{agentsOnNode.length} Assigned Seat(s)</span>
                              </span>
                              {activeCountOnNode > 0 && (
                                <span className="text-emerald-400 font-bold flex items-center space-x-1">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                  <span>{activeCountOnNode} Live</span>
                                </span>
                              )}
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {sortedAgents.slice(0, 3).map((agent: AgentSeatConfig) => (
                                <span
                                  key={agent.seat}
                                  className={`px-1.5 py-0.2 rounded text-[9px] uppercase font-bold border flex items-center space-x-1 ${getAgentBadgeColor(agent.type)}`}
                                >
                                  {agent.status === 'busy' && (
                                    <span className="w-1 h-1 rounded-full bg-emerald-400" />
                                  )}
                                  <span>{agent.seat}</span>
                                </span>
                              ))}
                              {sortedAgents.length > 3 && (
                                <span className="text-[9px] text-zinc-500 self-center">
                                  +{sortedAgents.length - 3} more
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}

      {/* ESXi Hypervisors & Ephemeral Clones Architecture Section */}
      <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <div className="flex items-center space-x-2">
            <Box className="w-4 h-4 text-purple-400" />
            <h3 className="text-sm font-semibold text-zinc-100">
              VMware ESXi Ephemeral Clones &amp; Sandbox Sub-Architecture
            </h3>
          </div>
          <span className="text-xs font-mono text-zinc-400">
            Dedicated Spare Pool (Rule 24 &amp; 38)
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {(topology?.esxi_clones || []).map((clone: EsxiCloneInfo) => (
            <div
              key={clone.id}
              className="p-3 rounded bg-zinc-950/80 border border-zinc-800 space-y-2 font-mono text-xs"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-purple-300">{clone.name}</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                  clone.status === 'running'
                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
                }`}>
                  {clone.status}
                </span>
              </div>

              <div className="text-[11px] text-zinc-400 space-y-0.5">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Host:</span>
                  <span className="text-zinc-300">{clone.hypervisor_host}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">IP:</span>
                  <span className="text-zinc-300">{clone.target_ip}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Resources:</span>
                  <span className="text-zinc-300">{clone.vcpus} vCPU • {clone.memory_mb ? Math.round(clone.memory_mb / 1024) : 8} GB</span>
                </div>
              </div>

              <div className="pt-1.5 border-t border-zinc-800/80 text-[10px] text-cyan-400 truncate">
                Workload: {clone.active_workload || 'Idle'}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
