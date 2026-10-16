import { NextResponse } from 'next/server';
import { readSteering } from '@/lib/fleet-telemetry';
export const dynamic = 'force-dynamic';
export async function GET() {
  const data = readSteering();
  return NextResponse.json({ timestamp: new Date().toISOString(), source: data.observation.state,
    active_count: data.data.working, total_entries: null, completed_count: null, items: [],
    queued: data.data.queued, steering: data.data, observation: data.observation });
}
