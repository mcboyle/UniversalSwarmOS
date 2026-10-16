import { NextResponse } from 'next/server';
import { readQuotas } from '@/lib/fleet-telemetry';
export const dynamic = 'force-dynamic';
export async function GET() {
  const data = readQuotas();
  return NextResponse.json({ timestamp: new Date().toISOString(), source: data.observation.state,
    quotas: data.quotas, observation: data.observation });
}
