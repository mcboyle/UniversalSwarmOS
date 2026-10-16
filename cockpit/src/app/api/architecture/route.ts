import { NextResponse } from 'next/server';
import { readTopology } from '@/lib/fleet-telemetry';
export const dynamic = 'force-dynamic';
export async function GET() {
  const data = readTopology();
  const nodes = data.nodes.map(node => ({ ...node, fqdn: node.name, tier: 'UNKNOWN', role: 'UNKNOWN', latency_ms: null, is_local: null, is_blacklisted: false }));
  return NextResponse.json({ timestamp: new Date().toISOString(), source: data.hosts.state,
    topology: { total_nodes: data.hosts.state === 'live' ? nodes.length : null,
      online_nodes: data.hosts.state === 'live' ? nodes.filter(node => node.status === 'up').length : null,
      total_agents: data.occupancy.state === 'live' ? new Set(data.agents.map(agent => agent.seat)).size : null,
      active_agents: null, isolated_nodes: null, esxi_clones: null,
      tiers: { control_plane: [], ai_satellite: [], workers: nodes, esxi_spare_pool: [], isolated_boundary: [] },
      agent_allocations: Object.fromEntries(nodes.map(node => [node.name, node.agents])),
      unmapped_agents: data.agents.filter(agent => !agent.node) } });
}
