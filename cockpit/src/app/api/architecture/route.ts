// src/app/api/architecture/route.ts
import { NextResponse } from 'next/server';
import fs from 'node:fs';
import { mockNodes, mockAgentsResponse } from '@/lib/mock-data';
import { discoverLiveAgents } from '@/lib/swarm-discovery';
import type {
  ClusterNode,
  AgentSeatConfig,
  EsxiCloneInfo,
  ArchitectureResponse
} from '@/lib/types';

export const dynamic = 'force-dynamic';

const BLACKLISTED_IP = '10.0.70.95'; // test2 (Fleet Rule 21: hands-off)
const LOCAL_IP = '10.0.70.164';
const ORACLE_WIN_IP = '10.0.70.181'; // External Windows VM Oracle Bridge

function getRoleFromFqdnOrName(fqdn: string, name: string): 'hub' | 'ops' | 'stg' | 'ai' | 'wrk-bd' | 'wrk-test' | 'spr-pool' {
  const combined = `${fqdn} ${name}`.toLowerCase();
  if (combined.includes('hub')) return 'hub';
  if (combined.includes('ops')) return 'ops';
  if (combined.includes('stg')) return 'stg';
  if (combined.includes('ai')) return 'ai';
  if (combined.includes('wrk-bd')) return 'wrk-bd';
  if (combined.includes('wrk-test') || combined.includes('test')) return 'wrk-test';
  if (combined.includes('spr') || combined.includes('spare')) return 'spr-pool';
  return 'wrk-test';
}

function parseClusterNodes(): ClusterNode[] {
  const hostsPath = '/etc/hosts';
  if (!fs.existsSync(hostsPath)) {
    return mockNodes;
  }

  const content = fs.readFileSync(hostsPath, 'utf8');
  const lines = content.split('\n');
  const nodes: ClusterNode[] = [];
  const seenIps = new Set<string>();

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    if (!trimmed.includes('10.0.70.')) continue;

    const parts = trimmed.split(/\s+/);
    const ip = parts[0];
    if (seenIps.has(ip)) continue;
    // Exclude Windows VM oracle bridge from the 27 Linux cluster nodes
    if (ip === ORACLE_WIN_IP) continue;
    seenIps.add(ip);

    const fqdn = parts[1] || '';
    const aliases = parts.slice(2);
    const name = aliases[0] || fqdn.split('.')[0] || ip;

    const role = getRoleFromFqdnOrName(fqdn, name);

    let tier = 'Worker Node';
    if (ip === LOCAL_IP || role === 'hub') tier = 'Primary Controller (Hub)';
    else if (role === 'ai') tier = 'AI Satellite';
    else if (role === 'ops') tier = 'Operations & CI Plane';
    else if (role === 'stg') tier = 'RAG Vector Store & Cache';
    else if (role === 'spr-pool') tier = 'ESXi Hypervisor / Spare Pool';
    else if (ip === BLACKLISTED_IP) tier = 'Target Site (Perimeter)';

    const is_blacklisted = ip === BLACKLISTED_IP;
    const is_local = ip === LOCAL_IP;

    nodes.push({
      name,
      fqdn,
      ip,
      role,
      tier,
      status: is_blacklisted ? 'operator-only' : (is_local ? 'up' : 'up'),
      latency_ms: is_local ? 0.05 : (is_blacklisted ? null : 0.32),
      is_local,
      is_blacklisted
    });
  }

  return nodes.length >= 25 ? nodes : mockNodes;
}

const ESXI_CLONES_FIXTURE: EsxiCloneInfo[] = [
  {
    id: 'clone-vm-01',
    name: 'vm-ephemeral-shard01',
    hypervisor_host: 'spr-pool-1 (10.0.70.120)',
    target_ip: '10.0.70.121',
    status: 'running',
    role: 'ci_shard_runner',
    vcpus: 4,
    memory_mb: 8192,
    active_workload: 'CI Shard 14: test_v3_66_939'
  },
  {
    id: 'clone-vm-02',
    name: 'vm-ephemeral-shard02',
    hypervisor_host: 'spr-pool-2 (10.0.70.149)',
    target_ip: '10.0.70.150',
    status: 'running',
    role: 'ephemeral_sandbox',
    vcpus: 4,
    memory_mb: 8192,
    active_workload: 'TSV Atomic Verification Worker'
  },
  {
    id: 'clone-vm-03',
    name: 'vm-ephemeral-red-iso',
    hypervisor_host: 'spr-pool-3 (10.0.70.183)',
    target_ip: '10.0.70.184',
    status: 'running',
    role: 'red_isolation',
    vcpus: 8,
    memory_mb: 16384,
    active_workload: 'Destructive Concurrency Sandbox'
  },
  {
    id: 'clone-vm-04',
    name: 'vm-ephemeral-standby',
    hypervisor_host: 'spr-pool-4 (10.0.70.185)',
    target_ip: '10.0.70.186',
    status: 'idle',
    role: 'ephemeral_sandbox',
    vcpus: 4,
    memory_mb: 8192,
    active_workload: 'Ready for lease'
  }
];

export async function GET(): Promise<NextResponse<ArchitectureResponse>> {
  try {
    const nodes = parseClusterNodes();
    const agents = discoverLiveAgents();

    const controlPlane = nodes.filter(n => n.role === 'hub' || n.role === 'ops' || n.role === 'stg');
    const aiSatellite = nodes.filter(n => n.role === 'ai');
    const workers = nodes.filter(n => (n.role === 'wrk-bd' || n.role === 'wrk-test') && !n.is_blacklisted);
    const esxiSparePool = nodes.filter(n => n.role === 'spr-pool');
    const isolatedBoundary = nodes.filter(n => n.is_blacklisted);

    // Map agents by host name and IP for visualizer lookup
    const agentAllocations: Record<string, AgentSeatConfig[]> = {};
    for (const a of agents) {
      const hostKey = a.host || 'hub-mesh01';
      if (!agentAllocations[hostKey]) {
        agentAllocations[hostKey] = [];
      }
      agentAllocations[hostKey].push(a);

      // Also key by node IP if matching
      const matchingNode = nodes.find(n => n.name === hostKey);
      if (matchingNode && matchingNode.ip !== hostKey) {
        if (!agentAllocations[matchingNode.ip]) {
          agentAllocations[matchingNode.ip] = [];
        }
        agentAllocations[matchingNode.ip].push(a);
      }
    }

    const onlineNodes = nodes.filter(n => n.status === 'up').length;
    const isolatedNodes = nodes.filter(n => n.is_blacklisted).length;
    const activeAgents = agents.filter(a => a.status === 'busy').length;

    return NextResponse.json({
      timestamp: new Date().toISOString(),
      topology: {
        total_nodes: nodes.length,
        online_nodes: onlineNodes,
        isolated_nodes: isolatedNodes,
        total_agents: agents.length,
        active_agents: activeAgents,
        esxi_clones: ESXI_CLONES_FIXTURE,
        tiers: {
          control_plane: controlPlane,
          ai_satellite: aiSatellite,
          workers,
          esxi_spare_pool: esxiSparePool,
          isolated_boundary: isolatedBoundary
        },
        agent_allocations: agentAllocations
      },
      source: 'live'
    });
  } catch (error) {
    console.error('[/api/architecture GET error]:', error);
    return NextResponse.json({
      timestamp: new Date().toISOString(),
      topology: {
        total_nodes: mockNodes.length,
        online_nodes: 26,
        isolated_nodes: 1,
        total_agents: mockAgentsResponse.total_agents,
        active_agents: mockAgentsResponse.active_agents,
        esxi_clones: ESXI_CLONES_FIXTURE,
        tiers: {
          control_plane: mockNodes.filter(n => n.role === 'hub' || n.role === 'ops' || n.role === 'stg'),
          ai_satellite: mockNodes.filter(n => n.role === 'ai'),
          workers: mockNodes.filter(n => (n.role === 'wrk-bd' || n.role === 'wrk-test') && !n.is_blacklisted),
          esxi_spare_pool: mockNodes.filter(n => n.role === 'spr-pool'),
          isolated_boundary: mockNodes.filter(n => n.is_blacklisted)
        },
        agent_allocations: {}
      },
      source: 'mock'
    });
  }
}
