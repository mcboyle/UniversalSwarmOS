// src/app/api/agents/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { mockAgentsResponse } from '@/lib/mock-data';
import { discoverLiveAgents, loadOverrides, saveOverrides } from '@/lib/swarm-discovery';
import type { AgentsResponse, AgentConfigUpdatePayload } from '@/lib/types';

export const dynamic = 'force-dynamic';

export async function GET(): Promise<NextResponse<AgentsResponse>> {
  try {
    const agents = discoverLiveAgents();

    return NextResponse.json({
      timestamp: new Date().toISOString(),
      total_agents: agents.length,
      active_agents: agents.filter(a => a.status === 'busy').length,
      agents,
      source: 'live'
    });
  } catch (error) {
    console.error('[/api/agents GET error]:', error);
    return NextResponse.json({ ...mockAgentsResponse, timestamp: new Date().toISOString(), source: 'mock' });
  }
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  return handleAgentUpdate(req);
}

export async function PUT(req: NextRequest): Promise<NextResponse> {
  return handleAgentUpdate(req);
}

async function handleAgentUpdate(req: NextRequest): Promise<NextResponse> {
  let body: AgentConfigUpdatePayload;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Malformed JSON payload' }, { status: 400 });
  }

  if (!body || typeof body !== 'object' || !body.seat || typeof body.seat !== 'string' || body.seat.trim().length === 0) {
    return NextResponse.json({ error: "Missing or invalid 'seat' parameter" }, { status: 400 });
  }

  const overrides = loadOverrides();
  const clampedTurnCap = body.turn_cap !== undefined ? Math.max(1, Math.min(60, body.turn_cap)) : undefined;

  overrides[body.seat] = {
    ...overrides[body.seat],
    ...(body.model ? { model: body.model } : {}),
    ...(body.reasoning_effort ? { reasoning_effort: body.reasoning_effort } : {}),
    ...(clampedTurnCap !== undefined ? { turn_cap: clampedTurnCap } : {}),
    ...(body.status ? { status: body.status } : {})
  };

  saveOverrides(overrides);

  return NextResponse.json({
    success: true,
    seat: body.seat,
    updated_config: overrides[body.seat],
    agent: overrides[body.seat],
    timestamp: new Date().toISOString()
  });
}
