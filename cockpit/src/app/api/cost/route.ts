import { NextResponse } from 'next/server';
import { readCost, parseHistoryRange } from '@/lib/fleet-telemetry';
export const dynamic = 'force-dynamic';
export async function GET(request: Request) {
  const range = parseHistoryRange(request ? new URL(request.url).searchParams.get('range') : null);
  if (!range) return NextResponse.json({ error: 'Unsupported history range' }, { status: 400 });
  return NextResponse.json(readCost(range));
}
