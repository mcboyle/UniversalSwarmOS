// src/app/api/queue/route.ts
import { NextRequest, NextResponse } from 'next/server';
import fs from 'node:fs';
import { mutateTsvAtomically, reorderDispatchLedgerRows } from '@/lib/atomic-tsv';
import { mockQueueItems } from '@/lib/mock-data';
import type { QueueItem, QueueResponse, QueueReorderPayload, QueueReorderResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';

function resolveLedgerPath(req?: NextRequest): string {
  const customHeader = req?.headers.get('x-test-ledger-path');
  if (customHeader && fs.existsSync(customHeader)) {
    return customHeader;
  }
  if (process.env.DISPATCH_LEDGER_PATH && fs.existsSync(process.env.DISPATCH_LEDGER_PATH)) {
    return process.env.DISPATCH_LEDGER_PATH;
  }
  const defaultPath = '/home/mboyle/bd-persist/DISPATCH-LEDGER.tsv';
  if (fs.existsSync(defaultPath)) {
    return defaultPath;
  }
  return defaultPath;
}

export async function GET(req: NextRequest): Promise<NextResponse<QueueResponse>> {
  try {
    const ledgerPath = resolveLedgerPath(req);
    if (!fs.existsSync(ledgerPath)) {
      return NextResponse.json({
        timestamp: new Date().toISOString(),
        total_entries: mockQueueItems.length,
        active_count: mockQueueItems.filter(i => i.is_active).length,
        completed_count: mockQueueItems.filter(i => !i.is_active).length,
        items: mockQueueItems,
        source: 'mock'
      });
    }

    const content = fs.readFileSync(ledgerPath, 'utf8');
    const lines = content.split('\n');
    const items: QueueItem[] = [];
    const activeStatuses = new Set(['dispatched', 'started', 'resent', 'nudged1', 'nudged2', 'nudged3', 'nudged4']);

    let idx = 0;
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const [timestamp, seat, row, status, brief_path] = line.split('\t');
      if (!row) continue;

      const is_active = activeStatuses.has((status || '').toLowerCase());
      items.push({
        index: idx++,
        timestamp: timestamp || '',
        seat: seat || '',
        row: row || '',
        status: status || 'dispatched',
        brief_path: brief_path || '',
        is_active
      });
    }

    // Optional query parameter filtering
    const { searchParams } = new URL(req.url);
    const filter = searchParams.get('filter'); // 'active' | 'completed' | 'all'
    const limitParam = searchParams.get('limit');
    const limit = limitParam ? Math.max(1, parseInt(limitParam, 10)) : 500;

    let filteredItems = items;
    if (filter === 'active') {
      filteredItems = items.filter(i => i.is_active);
    } else if (filter === 'completed') {
      filteredItems = items.filter(i => !i.is_active);
    }

    const returnedItems = filteredItems.slice(-limit);

    return NextResponse.json({
      timestamp: new Date().toISOString(),
      total_entries: items.length,
      active_count: items.filter(i => i.is_active).length,
      completed_count: items.filter(i => !i.is_active).length,
      items: returnedItems,
      source: 'live'
    });
  } catch (error: any) {
    console.error('[/api/queue GET error]:', error);
    return NextResponse.json({
      timestamp: new Date().toISOString(),
      total_entries: mockQueueItems.length,
      active_count: mockQueueItems.filter(i => i.is_active).length,
      completed_count: mockQueueItems.filter(i => !i.is_active).length,
      items: mockQueueItems,
      source: 'mock'
    });
  }
}

export async function POST(req: NextRequest): Promise<NextResponse<QueueReorderResponse | { error: string; details?: string }>> {
  return handleReorder(req);
}

export async function PUT(req: NextRequest): Promise<NextResponse<QueueReorderResponse | { error: string; details?: string }>> {
  return handleReorder(req);
}

async function handleReorder(req: NextRequest): Promise<NextResponse<any>> {
  let body: QueueReorderPayload;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: 'Bad Request: Malformed JSON body' },
      { status: 400 }
    );
  }

  // Schema Validation
  if (!body || typeof body !== 'object' || body.action !== 'reorder') {
    return NextResponse.json(
      { error: "Bad Request: 'action' field must be 'reorder'" },
      { status: 400 }
    );
  }

  if (!Array.isArray(body.ordered_row_ids) || body.ordered_row_ids.length === 0) {
    return NextResponse.json(
      { error: "Bad Request: 'ordered_row_ids' must be a non-empty array of strings" },
      { status: 400 }
    );
  }

  for (const id of body.ordered_row_ids) {
    if (typeof id !== 'string' || id.trim().length === 0) {
      return NextResponse.json(
        { error: "Bad Request: all elements in 'ordered_row_ids' must be non-empty strings" },
        { status: 400 }
      );
    }
  }

  const ledgerPath = resolveLedgerPath(req);

  try {
    // If ledger doesn't exist yet, ensure directory exists and write empty or initial file
    await mutateTsvAtomically(
      ledgerPath,
      (lines) => reorderDispatchLedgerRows(lines, body.ordered_row_ids),
      5000 // 5-second lock timeout
    );

    return NextResponse.json({
      success: true,
      reordered_count: body.ordered_row_ids.length,
      timestamp: new Date().toISOString(),
      message: 'Queue reordered successfully with zero torn reads'
    });
  } catch (error: any) {
    console.error('[/api/queue reorder error]:', error);
    if (
      error.message?.includes('Timeout acquiring advisory lock') ||
      error.message?.includes('Timeout acquiring lock') ||
      error.message?.includes('flock timed out')
    ) {
      return NextResponse.json(
        { error: 'Conflict: Ledger is locked by concurrent operation. Please retry.', details: error.message },
        { status: 409 }
      );
    }
    return NextResponse.json(
      { error: 'Internal Server Error: Failed to mutate queue ledger', details: error.message },
      { status: 500 }
    );
  }
}
