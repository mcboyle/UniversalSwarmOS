import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
export async function GET() {
  return NextResponse.json({ timestamp: new Date().toISOString(), source: 'unknown', total_shards: null, shards: [],
    reason: 'Shard execution is not measured by the cockpit source ledgers', recent_harness_runs: [], recent_gate_yields: [] });
}
