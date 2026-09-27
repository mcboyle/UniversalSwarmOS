// src/app/api/cost/route.ts
import { NextRequest, NextResponse } from 'next/server';
import fs from 'node:fs';
import path from 'node:path';
import Database from 'better-sqlite3';
import { getReadOnlyDb } from '@/lib/db';
import { withDbRetry } from '@/lib/db-retry';
import { mockCostData } from '@/lib/mock-data';
import type { CostResponse, ModelUsageSummary } from '@/lib/types';

export const dynamic = 'force-dynamic';

// Pricing per million tokens (approximate blended rates)
const MODEL_RATES: Record<string, { input: number; output: number; cacheRead: number }> = {
  'claude-opus-5': { input: 15.0, output: 75.0, cacheRead: 1.5 },
  'claude-opus-5-5': { input: 15.0, output: 75.0, cacheRead: 1.5 },
  'claude-opus-4-6': { input: 15.0, output: 75.0, cacheRead: 1.5 },
  'claude-opus-4-8': { input: 15.0, output: 75.0, cacheRead: 1.5 },
  'claude-sonnet-5': { input: 3.0, output: 15.0, cacheRead: 0.3 },
  'claude-sonnet-4-6': { input: 3.0, output: 15.0, cacheRead: 0.3 },
  'claude-fable-5-1': { input: 3.0, output: 15.0, cacheRead: 0.3 },
  'claude-haiku-4-5': { input: 0.8, output: 4.0, cacheRead: 0.08 },
  'claude-haiku-4-5-20251001': { input: 0.8, output: 4.0, cacheRead: 0.08 },
  'gpt-5.6-terra': { input: 2.5, output: 10.0, cacheRead: 0.25 },
  'gpt-6-astra': { input: 2.5, output: 10.0, cacheRead: 0.25 },
  'gpt-5.6-sol': { input: 2.0, output: 8.0, cacheRead: 0.20 },
  'gpt-6-sol': { input: 2.0, output: 8.0, cacheRead: 0.20 },
  'gemini-1.5-pro': { input: 1.25, output: 5.0, cacheRead: 0.3125 },
  'gemini-3.1-pro': { input: 1.25, output: 5.0, cacheRead: 0.3125 },
  'gemini-3.8-flash-high': { input: 0.15, output: 0.60, cacheRead: 0.0375 },
  'gemini-3.8-flash-medium': { input: 0.15, output: 0.60, cacheRead: 0.0375 },
  'gemini-3.8-flash-low': { input: 0.15, output: 0.60, cacheRead: 0.0375 },
  // Grok (xAI) Models
  'grok-2': { input: 2.0, output: 10.0, cacheRead: 0.20 },
  'grok-2-mini': { input: 0.5, output: 2.0, cacheRead: 0.05 },
  'grok-beta': { input: 5.0, output: 15.0, cacheRead: 0.50 },
  'grok-3': { input: 3.0, output: 15.0, cacheRead: 0.30 },
  'grok-4.7-build-fast': { input: 2.0, output: 10.0, cacheRead: 0.20 },
  // Kimi (Moonshot AI) Models
  'kimi-k1.5': { input: 1.0, output: 3.0, cacheRead: 0.15 },
  'kimi-latest': { input: 1.0, output: 3.0, cacheRead: 0.15 },
  'kimi-code/kimi-for-coding': { input: 1.0, output: 3.0, cacheRead: 0.15 },
  'moonshot-v1-128k': { input: 1.2, output: 3.6, cacheRead: 0.20 },
  'moonshot-v1-32k': { input: 1.2, output: 3.6, cacheRead: 0.20 },
  'moonshot-v1-8k': { input: 1.2, output: 3.6, cacheRead: 0.20 },
  'trivial': { input: 0.8, output: 4.0, cacheRead: 0.08 },
  default: { input: 3.0, output: 15.0, cacheRead: 0.3 }
};

const CODEX_STATE_DB = '/home/mboyle/.codex/state_5.sqlite';
const AGY_CONVERSATIONS_DB = '/home/mboyle/.gemini/antigravity-cli/conversation_summaries.db';
const AGY_SUMMARY_JSON = '/home/mboyle/bd-persist/AGY-20-TURNS-SUMMARY.json';
const USAGE_TSV = '/home/mboyle/bd-persist/usage.tsv';
const CACHE_VERIFY_TSV = '/home/mboyle/bd-persist/accounting/cache_pipeline_verify.tsv';

function getCodexNameMap(): Map<string, string> {
  const map = new Map<string, string>();
  if (fs.existsSync(CODEX_STATE_DB)) {
    let db: Database.Database | null = null;
    try {
      db = new Database(CODEX_STATE_DB, { readonly: true, timeout: 2000 });
      const rows = db.prepare('SELECT id, agent_nickname, cwd FROM threads WHERE updated_at > 0').all() as Array<{
        id: string;
        agent_nickname: string | null;
        cwd: string | null;
      }>;
      for (const r of rows) {
        let friendly: string | null = null;
        if (r.cwd) {
          const base = path.basename(r.cwd);
          if (['audit', 'codex', 'trainer', 'review', 'hunt'].some(k => base.includes(k))) {
            friendly = base.startsWith('bd-cx-') ? base : `bd-cx-${base}`;
          }
        }
        if (!friendly && r.agent_nickname) friendly = `bd-cx-${r.agent_nickname}`;
        if (!friendly) friendly = `bd-cx-${r.id.slice(0, 8)}`;
        map.set(r.id, friendly);
      }
    } catch {} finally {
      if (db) try { db.close(); } catch {}
    }
  }
  return map;
}

interface TsvUsageRow {
  timestamp: string;
  timestampMs: number;
  seat: string;
  backend: string;
  model: string;
  conv_id: string;
  status: string;
  input_tokens: number;
  output_tokens: number;
  thinking_tokens: number;
  cache_read_tokens: number;
  total_tokens: number;
  duration_s: number;
}

function parseTsvFile(filePath: string, seenSignatures: Set<string>, rows: TsvUsageRow[]) {
  if (!fs.existsSync(filePath)) return;
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n');
    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;
      if (line.startsWith('timestamp_utc') || line.startsWith('pool\t')) continue;
      const parts = line.split('\t');
      if (parts.length < 8) continue;

      const ts = parts[0]?.trim();
      const seat = parts[1]?.trim() || 'bd-worker';
      const backend = parts[2]?.trim() || '';
      const model = parts[3]?.trim() || 'unknown';
      const conv_id = parts[4]?.trim() || '';
      const status = parts[5]?.trim() || '';
      const input_tokens = parseInt(parts[6], 10) || 0;
      const output_tokens = parseInt(parts[7], 10) || 0;
      const thinking_tokens = parseInt(parts[8], 10) || 0;
      const raw_cache = parseInt(parts[9], 10) || 0;
      const cache_read_tokens = Math.min(input_tokens, raw_cache);
      const total_tokens = parseInt(parts[10], 10) || (input_tokens + output_tokens);
      const duration_s = parseFloat(parts[11]) || 0;

      const tsMs = Date.parse(ts);
      if (isNaN(tsMs)) continue;

      const sig = `${ts}|${seat}|${conv_id}|${input_tokens}|${output_tokens}|${cache_read_tokens}`;
      if (seenSignatures.has(sig)) continue;
      seenSignatures.add(sig);

      rows.push({
        timestamp: ts,
        timestampMs: tsMs,
        seat,
        backend,
        model,
        conv_id,
        status,
        input_tokens,
        output_tokens,
        thinking_tokens,
        cache_read_tokens,
        total_tokens,
        duration_s
      });
    }
  } catch {}
}

function getLiveTsvData(since: string, sinceParam: string | null): {
  threads: ModelUsageSummary[];
  models: ModelUsageSummary[];
  totalTurns: number;
  totalContext: number;
  totalOutput: number;
  totalCacheRead: number;
  totalCost: number;
} {
  const seenSignatures = new Set<string>();
  const allRows: TsvUsageRow[] = [];
  parseTsvFile(CACHE_VERIFY_TSV, seenSignatures, allRows);
  parseTsvFile(USAGE_TSV, seenSignatures, allRows);

  let maxTsMs = 0;
  for (const r of allRows) {
    if (r.timestampMs > maxTsMs) maxTsMs = r.timestampMs;
  }

  // Determine window duration if sinceParam was relative
  let windowMs: number | null = null;
  const isRelative = !sinceParam || sinceParam === 'null' || sinceParam === 'undefined' ||
    sinceParam.endsWith('m') || sinceParam.endsWith('h') || sinceParam.endsWith('d');

  if (!sinceParam || sinceParam === 'null' || sinceParam === 'undefined') {
    windowMs = 6 * 3600 * 1000;
  } else if (sinceParam.endsWith('m')) {
    const val = parseFloat(sinceParam.slice(0, -1));
    windowMs = (isNaN(val) || val <= 0 ? 5 : val) * 60 * 1000;
  } else if (sinceParam.endsWith('h')) {
    const val = parseFloat(sinceParam.slice(0, -1));
    windowMs = (isNaN(val) || val <= 0 ? 6 : val) * 3600 * 1000;
  } else if (sinceParam.endsWith('d')) {
    const val = parseFloat(sinceParam.slice(0, -1));
    windowMs = (isNaN(val) || val <= 0 ? 1 : val) * 86400 * 1000;
  }

  // 1. Try real-time cutoff
  let matchingRows = allRows.filter(r => r.timestamp >= since);

  // 2. If 0 rows found and this was a relative query, anchor to maxTsMs
  if (matchingRows.length === 0 && isRelative && windowMs !== null && maxTsMs > 0) {
    const anchoredSince = new Date(maxTsMs - windowMs).toISOString();
    matchingRows = allRows.filter(r => r.timestamp >= anchoredSince);
  }

  const threadMap = new Map<string, {
    key: string;
    turns: number;
    total_ctx: number;
    out_tokens: number;
    cache_read: number;
    max_ctx: number;
    model: string;
  }>();

  const modelMap = new Map<string, {
    turns: number;
    total_ctx: number;
    out_tokens: number;
    cache_read: number;
    max_ctx: number;
  }>();

  for (const r of matchingRows) {
    const safeCache = Math.min(r.input_tokens, r.cache_read_tokens);

    // Threads
    const threadKey = r.seat || 'bd-worker';
    const prevThread = threadMap.get(threadKey) || {
      key: threadKey,
      turns: 0,
      total_ctx: 0,
      out_tokens: 0,
      cache_read: 0,
      max_ctx: 0,
      model: r.model
    };
    prevThread.turns += 1;
    prevThread.total_ctx += r.input_tokens;
    prevThread.out_tokens += r.output_tokens;
    prevThread.cache_read += safeCache;
    prevThread.max_ctx = Math.max(prevThread.max_ctx, r.input_tokens);
    prevThread.model = r.model;
    threadMap.set(threadKey, prevThread);

    // Models
    const prevModel = modelMap.get(r.model) || {
      turns: 0,
      total_ctx: 0,
      out_tokens: 0,
      cache_read: 0,
      max_ctx: 0
    };
    prevModel.turns += 1;
    prevModel.total_ctx += r.input_tokens;
    prevModel.out_tokens += r.output_tokens;
    prevModel.cache_read += safeCache;
    prevModel.max_ctx = Math.max(prevModel.max_ctx, r.input_tokens);
    modelMap.set(r.model, prevModel);
  }

  // Load historical benchmark from AGY-20-TURNS-SUMMARY.json only if query range covers 2026-09-20
  const summaryDateCutoff = '2026-09-20T23:59:59Z';
  if (fs.existsSync(AGY_SUMMARY_JSON) && since <= summaryDateCutoff) {
    try {
      const summaryData = JSON.parse(fs.readFileSync(AGY_SUMMARY_JSON, 'utf8'));
      const turns = summaryData.turns || [];
      const totalTurns = turns.length || summaryData.total_turns || 20;

      const isCumulativeCache = turns.length > 1 &&
        Number(turns[turns.length - 1].cache_read_tokens || 0) > Number(turns[0].cache_read_tokens || 0) &&
        turns.every((t: any, i: number) => i === 0 || Number(t.cache_read_tokens || 0) >= Number(turns[i - 1].cache_read_tokens || 0));

      const isCumulativeOut = turns.length > 1 &&
        Number(turns[turns.length - 1].output_tokens || 0) > Number(turns[0].output_tokens || 0) &&
        turns.every((t: any, i: number) => i === 0 || Number(t.output_tokens || 0) >= Number(turns[i - 1].output_tokens || 0));

      let totalIn = 0;
      let totalOut = 0;
      let totalCache = 0;
      let maxCtx = 0;
      for (let i = 0; i < turns.length; i++) {
        const t = turns[i];
        const inp = Number(t.input_tokens || 0);
        const outRaw = Number(t.output_tokens || 0);
        const crRaw = Number(t.cache_read_tokens || 0);

        const out = isCumulativeOut
          ? (i === 0 ? outRaw : Math.max(0, outRaw - Number(turns[i - 1].output_tokens || 0)))
          : outRaw;
        const cr = isCumulativeCache
          ? (i === 0 ? crRaw : Math.max(0, crRaw - Number(turns[i - 1].cache_read_tokens || 0)))
          : crRaw;

        totalIn += inp;
        totalOut += out;
        totalCache += Math.min(inp, cr);
        if (inp > maxCtx) maxCtx = inp;
      }
      totalCache = Math.min(totalIn, totalCache);

      threadMap.set('bd-agy-ci-runner', {
        key: 'bd-agy-ci-runner',
        turns: totalTurns,
        total_ctx: totalIn,
        out_tokens: totalOut,
        cache_read: totalCache,
        max_ctx: maxCtx,
        model: 'gemini-3.8-flash-high'
      });

      const m = modelMap.get('gemini-3.8-flash-high') || {
        turns: 0,
        total_ctx: 0,
        out_tokens: 0,
        cache_read: 0,
        max_ctx: 0
      };
      m.turns += totalTurns;
      m.total_ctx += totalIn;
      m.out_tokens += totalOut;
      m.cache_read += totalCache;
      m.max_ctx = Math.max(m.max_ctx, maxCtx);
      modelMap.set('gemini-3.8-flash-high', m);
    } catch {}
  }

  const threads: ModelUsageSummary[] = [];
  for (const [key, t] of threadMap.entries()) {
    const rate = MODEL_RATES[t.model] || MODEL_RATES.default;
    const safeCache = Math.min(t.total_ctx, t.cache_read);
    const freshInput = Math.max(0, t.total_ctx - safeCache);
    const cost_usd = (freshInput / 1_000_000) * rate.input +
                     (safeCache / 1_000_000) * rate.cacheRead +
                     (t.out_tokens / 1_000_000) * rate.output;
    const efficiency = t.total_ctx > 0 ? Math.min(100, (safeCache / t.total_ctx) * 100) : 0;

    threads.push({
      key: t.key,
      turns: t.turns,
      total_ctx: t.total_ctx,
      out_tokens: t.out_tokens,
      cache_read: safeCache,
      cache_efficiency_pct: Math.round(efficiency * 100) / 100,
      mean_ctx: t.turns > 0 ? Math.round(t.total_ctx / t.turns) : 0,
      max_ctx: t.max_ctx,
      cost_usd: Math.round(cost_usd * 100) / 100
    });
  }

  const models: ModelUsageSummary[] = [];
  let totalTurns = 0;
  let totalContext = 0;
  let totalOutput = 0;
  let totalCacheRead = 0;
  let totalCost = 0;

  for (const [modelKey, m] of modelMap.entries()) {
    const rate = MODEL_RATES[modelKey] || MODEL_RATES.default;
    const safeCache = Math.min(m.total_ctx, m.cache_read);
    const freshInput = Math.max(0, m.total_ctx - safeCache);
    const cost_usd = (freshInput / 1_000_000) * rate.input +
                     (safeCache / 1_000_000) * rate.cacheRead +
                     (m.out_tokens / 1_000_000) * rate.output;
    const efficiency = m.total_ctx > 0 ? Math.min(100, (safeCache / m.total_ctx) * 100) : 0;

    models.push({
      key: modelKey,
      turns: m.turns,
      total_ctx: m.total_ctx,
      out_tokens: m.out_tokens,
      cache_read: safeCache,
      cache_efficiency_pct: Math.round(efficiency * 100) / 100,
      mean_ctx: m.turns > 0 ? Math.round(m.total_ctx / m.turns) : 0,
      max_ctx: m.max_ctx,
      cost_usd: Math.round(cost_usd * 100) / 100
    });

    totalTurns += m.turns;
    totalContext += m.total_ctx;
    totalOutput += m.out_tokens;
    totalCacheRead += safeCache;
    totalCost += cost_usd;
  }

  return {
    threads,
    models,
    totalTurns,
    totalContext,
    totalOutput,
    totalCacheRead,
    totalCost
  };
}

function parseSinceParam(sinceParam: string | null): string {
  if (!sinceParam || sinceParam === 'undefined' || sinceParam === 'null') {
    return new Date(Date.now() - 6 * 3600 * 1000).toISOString();
  }
  if (sinceParam.endsWith('m')) {
    const val = parseFloat(sinceParam.slice(0, -1));
    if (isNaN(val) || val <= 0) {
      return new Date(Date.now() - 5 * 60 * 1000).toISOString();
    }
    return new Date(Date.now() - val * 60 * 1000).toISOString();
  }
  if (sinceParam.endsWith('h')) {
    const val = parseFloat(sinceParam.slice(0, -1));
    if (isNaN(val) || val <= 0) {
      return new Date(Date.now() - 6 * 3600 * 1000).toISOString();
    }
    return new Date(Date.now() - val * 3600 * 1000).toISOString();
  }
  if (sinceParam.endsWith('d')) {
    const val = parseFloat(sinceParam.slice(0, -1));
    if (isNaN(val) || val <= 0) {
      return new Date(Date.now() - 24 * 3600 * 1000).toISOString();
    }
    return new Date(Date.now() - val * 24 * 3600 * 1000).toISOString();
  }
  // Try parsing ISO date
  const parsed = Date.parse(sinceParam);
  if (!isNaN(parsed)) {
    return new Date(parsed).toISOString();
  }
  return new Date(Date.now() - 6 * 3600 * 1000).toISOString();
}

function parseLimitParam(limitParam: string | null): number {
  if (!limitParam) return 50;
  const parsed = parseInt(limitParam, 10);
  if (isNaN(parsed) || parsed <= 0) return 50;
  return Math.min(parsed, 500);
}

interface CacheEntry {
  expiresAt: number;
  data: CostResponse;
}
const liveResponseCache = new Map<string, CacheEntry>();

export async function GET(req: NextRequest): Promise<NextResponse<CostResponse>> {
  const { searchParams } = new URL(req.url);
  const sinceParam = searchParams.get('since');
  const rawLimit = searchParams.get('limit');
  const groupByParam = searchParams.get('group_by');
  const groupBy: 'model' | 'thread' = groupByParam === 'thread' ? 'thread' : 'model';
  const limit = parseLimitParam(rawLimit);
  const since = parseSinceParam(sinceParam);

  const testDbHeader = req.headers.get('x-test-db-path');
  const isCustomDb = !!(testDbHeader && fs.existsSync(testDbHeader));
  const isProductionDb = !isCustomDb && !process.env.USAGE_DB_PATH;
  let customDbInstance: Database.Database | null = null;

  const cacheKey = `${isCustomDb ? testDbHeader : 'live'}_${since}_${groupBy}_${limit}`;
  if (isProductionDb) {
    const cached = liveResponseCache.get(cacheKey);
    if (cached && Date.now() < cached.expiresAt) {
      return NextResponse.json(cached.data);
    }
  }

  try {
    const db = isCustomDb
      ? (customDbInstance = new Database(testDbHeader!, { readonly: true, fileMustExist: true, timeout: 5000 }))
      : getReadOnlyDb();
    if (!db) {
      return NextResponse.json({ ...mockCostData, since, group_by: groupBy, source: 'mock' });
    }

    // Execute queries wrapped in withDbRetry for 100% deadlock immunity
    const result = await withDbRetry(() => {
      let breakdownRows: ModelUsageSummary[] = [];
      let effectiveGroupBy: 'model' | 'thread' = groupBy;

      if (groupBy === 'thread') {
        const tableCheck = db.prepare(`
          SELECT count(*) as count FROM sqlite_master WHERE type='table' AND name='usage_occurrences'
        `).get() as { count: number };

        if (tableCheck && tableCheck.count > 0) {
          // Global aggregates for the thread window
          const aggStmt = db.prepare(`
            SELECT
              COUNT(*) as total_responses,
              COALESCE(SUM(COALESCE(json_extract(usage, '$.input_tokens'), 0)), 0) as total_context_tokens,
              COALESCE(SUM(COALESCE(json_extract(usage, '$.output_tokens'), 0)), 0) as total_output_tokens,
              COALESCE(SUM(MAX(COALESCE(json_extract(usage, '$.cache_read_input_tokens'), 0), COALESCE(json_extract(usage, '$.cached_input_tokens'), 0))), 0) as total_cache_read_tokens
            FROM usage_responses
            WHERE timestamp >= ? AND quarantined = 0
          `);
          const aggRow = aggStmt.get(since) as {
            total_responses: number;
            total_context_tokens: number;
            total_output_tokens: number;
            total_cache_read_tokens: number;
          } | undefined;

          const totalResponses = Number(aggRow?.total_responses || 0);
          const totalContext = Number(aggRow?.total_context_tokens || 0);
          const totalOutput = Number(aggRow?.total_output_tokens || 0);
          const totalCacheRead = Number(aggRow?.total_cache_read_tokens || 0);

          if (totalResponses === 0) {
            return {
              totalResponses: 0,
              totalContext: 0,
              totalOutput: 0,
              totalCacheRead: 0,
              totalCost: 0,
              effectiveGroupBy: 'thread' as const,
              breakdown: [] as ModelUsageSummary[]
            };
          }

          // Compute totalCost from model rates
          const costStmt = db.prepare(`
            SELECT
              COALESCE(model, 'unknown') as model,
              COALESCE(SUM(COALESCE(json_extract(usage, '$.input_tokens'), 0)), 0) as total_ctx,
              COALESCE(SUM(COALESCE(json_extract(usage, '$.output_tokens'), 0)), 0) as out_tokens,
              COALESCE(SUM(MAX(COALESCE(json_extract(usage, '$.cache_read_input_tokens'), 0), COALESCE(json_extract(usage, '$.cached_input_tokens'), 0))), 0) as cache_read
            FROM usage_responses
            WHERE timestamp >= ? AND quarantined = 0
            GROUP BY model
          `);
          const costRows = costStmt.all(since) as Array<{
            model: string;
            total_ctx: number;
            out_tokens: number;
            cache_read: number;
          }>;

          let totalCost = 0;
          for (const row of costRows) {
            const rate = MODEL_RATES[row.model] || MODEL_RATES.default;
            const freshInput = Math.max(0, row.total_ctx - row.cache_read);
            const cost = (freshInput / 1_000_000) * rate.input +
                         (row.cache_read / 1_000_000) * rate.cacheRead +
                         (row.out_tokens / 1_000_000) * rate.output;
            totalCost += cost;
          }

          // Deduplicate (provider, response_id, thread) to prevent double-counting across log sources
          const threadStmt = db.prepare(`
            SELECT
              COALESCE(o.thread, 'unknown') as key,
              COUNT(DISTINCT r.response_id) as turns,
              COALESCE(SUM(COALESCE(json_extract(r.usage, '$.input_tokens'), 0)), 0) as total_ctx,
              COALESCE(SUM(COALESCE(json_extract(r.usage, '$.output_tokens'), 0)), 0) as out_tokens,
              COALESCE(SUM(MAX(COALESCE(json_extract(r.usage, '$.cache_read_input_tokens'), 0), COALESCE(json_extract(r.usage, '$.cached_input_tokens'), 0))), 0) as cache_read,
              COALESCE(MAX(COALESCE(json_extract(r.usage, '$.input_tokens'), 0)), 0) as max_ctx,
              COALESCE(r.model, 'unknown') as sample_model
            FROM usage_responses r
            JOIN (
              SELECT DISTINCT provider, response_id, thread
              FROM usage_occurrences
            ) o ON r.provider = o.provider AND r.response_id = o.response_id
            WHERE r.timestamp >= ? AND r.quarantined = 0
            GROUP BY o.thread
            ORDER BY total_ctx DESC
            LIMIT ?
          `);

          const rawThreads = threadStmt.all(since, limit) as Array<{
            key: string;
            turns: number;
            total_ctx: number;
            out_tokens: number;
            cache_read: number;
            max_ctx: number;
            sample_model: string;
          }>;

          breakdownRows = rawThreads.map((t) => {
            const rate = MODEL_RATES[t.sample_model] || MODEL_RATES.default;
            const freshInput = Math.max(0, t.total_ctx - t.cache_read);
            const cost_usd = (freshInput / 1_000_000) * rate.input +
                             (t.cache_read / 1_000_000) * rate.cacheRead +
                             (t.out_tokens / 1_000_000) * rate.output;
            const efficiency = t.total_ctx > 0 ? (t.cache_read / t.total_ctx) * 100 : 0;

            return {
              key: t.key,
              turns: Number(t.turns),
              total_ctx: Number(t.total_ctx),
              out_tokens: Number(t.out_tokens),
              cache_read: Number(t.cache_read),
              cache_efficiency_pct: Math.round(efficiency * 100) / 100,
              mean_ctx: t.turns > 0 ? Math.round(t.total_ctx / t.turns) : 0,
              max_ctx: Number(t.max_ctx),
              cost_usd: Math.round(cost_usd * 100) / 100
            };
          });

          return {
            totalResponses,
            totalContext,
            totalOutput,
            totalCacheRead,
            totalCost,
            effectiveGroupBy: 'thread' as const,
            breakdown: breakdownRows
          };
        } else {
          // Table doesn't exist, fall back to model
          effectiveGroupBy = 'model';
        }
      }

      // Single-query authoritative aggregation when grouping by model
      const modelStmt = db.prepare(`
        SELECT
          COALESCE(model, 'unknown') as key,
          COUNT(*) as turns,
          COALESCE(SUM(COALESCE(json_extract(usage, '$.input_tokens'), 0)), 0) as total_ctx,
          COALESCE(SUM(COALESCE(json_extract(usage, '$.output_tokens'), 0)), 0) as out_tokens,
          COALESCE(SUM(MAX(COALESCE(json_extract(usage, '$.cache_read_input_tokens'), 0), COALESCE(json_extract(usage, '$.cached_input_tokens'), 0))), 0) as cache_read,
          COALESCE(MAX(COALESCE(json_extract(usage, '$.input_tokens'), 0)), 0) as max_ctx
        FROM usage_responses
        WHERE timestamp >= ? AND quarantined = 0
        GROUP BY model
        ORDER BY total_ctx DESC
      `);

      const rawModels = modelStmt.all(since) as Array<{
        key: string;
        turns: number;
        total_ctx: number;
        out_tokens: number;
        cache_read: number;
        max_ctx: number;
      }>;

      let totalResponses = 0;
      let totalContext = 0;
      let totalOutput = 0;
      let totalCacheRead = 0;
      let totalCost = 0;

      breakdownRows = rawModels.map((m) => {
        totalResponses += Number(m.turns);
        totalContext += Number(m.total_ctx);
        totalOutput += Number(m.out_tokens);
        totalCacheRead += Number(m.cache_read);

        const rate = MODEL_RATES[m.key] || MODEL_RATES.default;
        const freshInput = Math.max(0, m.total_ctx - m.cache_read);
        const cost_usd = (freshInput / 1_000_000) * rate.input +
                         (m.cache_read / 1_000_000) * rate.cacheRead +
                         (m.out_tokens / 1_000_000) * rate.output;
        totalCost += cost_usd;
        const efficiency = m.total_ctx > 0 ? Math.min(100, (m.cache_read / m.total_ctx) * 100) : 0;

        return {
          key: m.key,
          turns: Number(m.turns),
          total_ctx: Number(m.total_ctx),
          out_tokens: Number(m.out_tokens),
          cache_read: Number(m.cache_read),
          cache_efficiency_pct: Math.round(efficiency * 100) / 100,
          mean_ctx: m.turns > 0 ? Math.round(m.total_ctx / m.turns) : 0,
          max_ctx: Number(m.max_ctx),
          cost_usd: Math.round(cost_usd * 100) / 100
        };
      });

      return {
        totalResponses,
        totalContext,
        totalOutput,
        totalCacheRead,
        totalCost,
        effectiveGroupBy: 'model' as const,
        breakdown: breakdownRows.slice(0, limit)
      };
    });

    if (isProductionDb) {
      const liveData = getLiveTsvData(since, sinceParam);
      if (result.effectiveGroupBy === 'model') {
        const mergedModelMap = new Map<string, ModelUsageSummary>();
        for (const m of result.breakdown) {
          mergedModelMap.set(m.key, { ...m });
        }
        for (const m of liveData.models) {
          const prev = mergedModelMap.get(m.key);
          if (prev) {
            prev.turns += m.turns;
            prev.total_ctx += m.total_ctx;
            prev.out_tokens += m.out_tokens;
            prev.cache_read += m.cache_read;
            prev.max_ctx = Math.max(prev.max_ctx, m.max_ctx);
            prev.cost_usd = Math.round((prev.cost_usd + m.cost_usd) * 100) / 100;
            const eff = prev.total_ctx > 0 ? (prev.cache_read / prev.total_ctx) * 100 : 0;
            prev.cache_efficiency_pct = Math.round(eff * 100) / 100;
            prev.mean_ctx = prev.turns > 0 ? Math.round(prev.total_ctx / prev.turns) : 0;
          } else {
            mergedModelMap.set(m.key, { ...m });
          }
        }
        result.totalResponses += liveData.totalTurns;
        result.totalContext += liveData.totalContext;
        result.totalOutput += liveData.totalOutput;
        result.totalCacheRead += liveData.totalCacheRead;
        result.totalCost += liveData.totalCost;
        result.breakdown = Array.from(mergedModelMap.values()).sort((a, b) => b.total_ctx - a.total_ctx).slice(0, limit);
      } else if (result.effectiveGroupBy === 'thread') {
        const codexMap = getCodexNameMap();
        // Rename and coalesce codex threads
        const mergedThreadMap = new Map<string, ModelUsageSummary>();
        for (const t of result.breakdown) {
          let name = codexMap.get(t.key) || t.key;
          if (name.startsWith('01a0')) {
            name = `bd-cx-${name.slice(0, 8)}`;
          }
          const prev = mergedThreadMap.get(name);
          if (prev) {
            prev.turns += t.turns;
            prev.total_ctx += t.total_ctx;
            prev.out_tokens += t.out_tokens;
            prev.cache_read += t.cache_read;
            prev.max_ctx = Math.max(prev.max_ctx, t.max_ctx);
            prev.cost_usd = Math.round((prev.cost_usd + t.cost_usd) * 100) / 100;
            const eff = prev.total_ctx > 0 ? (prev.cache_read / prev.total_ctx) * 100 : 0;
            prev.cache_efficiency_pct = Math.round(eff * 100) / 100;
            prev.mean_ctx = prev.turns > 0 ? Math.round(prev.total_ctx / prev.turns) : 0;
          } else {
            mergedThreadMap.set(name, { ...t, key: name });
          }
        }
        // Merge TSV threads
        for (const t of liveData.threads) {
          const prev = mergedThreadMap.get(t.key);
          if (prev) {
            prev.turns += t.turns;
            prev.total_ctx += t.total_ctx;
            prev.out_tokens += t.out_tokens;
            prev.cache_read += t.cache_read;
            prev.max_ctx = Math.max(prev.max_ctx, t.max_ctx);
            prev.cost_usd = Math.round((prev.cost_usd + t.cost_usd) * 100) / 100;
            const eff = prev.total_ctx > 0 ? (prev.cache_read / prev.total_ctx) * 100 : 0;
            prev.cache_efficiency_pct = Math.round(eff * 100) / 100;
            prev.mean_ctx = prev.turns > 0 ? Math.round(prev.total_ctx / prev.turns) : 0;
          } else {
            mergedThreadMap.set(t.key, { ...t });
          }
        }
        result.totalResponses += liveData.totalTurns;
        result.totalContext += liveData.totalContext;
        result.totalOutput += liveData.totalOutput;
        result.totalCacheRead += liveData.totalCacheRead;
        result.totalCost += liveData.totalCost;

        result.breakdown = Array.from(mergedThreadMap.values()).sort((a, b) => b.total_ctx - a.total_ctx).slice(0, limit);
      }
    }

    const overallCacheHit = result.totalContext > 0
      ? Math.min(100, (result.totalCacheRead / result.totalContext) * 100)
      : 0;

    // Projected 24h cost extrapolated from the queried window
    const projected24hCost = result.totalCost * 4;

    const responsePayload: CostResponse = {
      since,
      group_by: result.effectiveGroupBy,
      total_responses: result.totalResponses,
      aggregate: {
        total_context_tokens: result.totalContext,
        total_output_tokens: result.totalOutput,
        total_cache_read_tokens: result.totalCacheRead,
        overall_cache_hit_pct: Math.round(overallCacheHit * 100) / 100,
        total_cost_usd: Math.round(result.totalCost * 100) / 100,
        projected_24h_cost_usd: Math.round(projected24hCost * 100) / 100
      },
      breakdown: result.breakdown,
      source: 'live'
    };

    if (isProductionDb) {
      liveResponseCache.set(cacheKey, {
        expiresAt: Date.now() + 2500,
        data: responsePayload
      });
      if (liveResponseCache.size > 100) {
        const now = Date.now();
        for (const [k, v] of liveResponseCache) {
          if (v.expiresAt <= now) liveResponseCache.delete(k);
        }
      }
    }

    return NextResponse.json(responsePayload);
  } catch (error) {
    console.error('[/api/cost GET error]:', error);
    return NextResponse.json({ ...mockCostData, since, group_by: groupBy, source: 'mock' });
  } finally {
    if (customDbInstance) {
      try {
        customDbInstance.close();
      } catch {}
    }
  }
}
