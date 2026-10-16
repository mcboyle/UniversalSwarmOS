import { NextResponse } from 'next/server';
import { readTopology } from '@/lib/fleet-telemetry';
export const dynamic = 'force-dynamic';
export async function GET() {
  const data = readTopology();
  return NextResponse.json({ timestamp: new Date().toISOString(), source: data.hosts.state,
    total_nodes: data.hosts.state === 'live' ? data.nodes.length : null,
    up_nodes: data.hosts.state === 'live' ? data.nodes.filter(node => node.status === 'up').length : null,
    blacklisted_count: 0, nodes: data.nodes, observation: data.hosts });
}
