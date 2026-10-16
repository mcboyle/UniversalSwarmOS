import { NextResponse } from 'next/server';
import { readTopology } from '@/lib/fleet-telemetry';
export const dynamic = 'force-dynamic';
export async function GET() {
  const data = readTopology();
  return NextResponse.json({ timestamp: new Date().toISOString(), source: data.occupancy.state,
    total_agents: data.occupancy.state === 'live' ? new Set(data.agents.map(agent => agent.seat)).size : null,
    active_agents: null, agents: data.agents, observation: data.occupancy });
}
