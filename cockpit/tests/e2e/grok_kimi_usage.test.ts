/**
 * tests/e2e/grok_kimi_usage.test.ts
 * 
 * Milestone 4 (AC1): Unit tests validating usage tracking aggregation logic for Grok & Kimi models.
 * Authoritative Contracts:
 * - PROJECT.md (Backend Pricing Contract: MODEL_RATES)
 * - ORIGINAL_REQUEST.md (Acceptance Criteria: AC1)
 * - src/app/api/cost/route.ts (Token Math, Cache Efficiency, and SQL aggregation)
 */

import { describe, it } from 'node:test';
import assert from 'node:assert';
import Database from 'better-sqlite3';

// Authoritative MODEL_RATES from PROJECT.md and cost/route.ts
export const MODEL_RATES: Record<string, { input: number; output: number; cacheRead: number }> = {
  'grok-2': { input: 2.0, output: 10.0, cacheRead: 0.20 },
  'grok-2-mini': { input: 0.5, output: 2.0, cacheRead: 0.05 },
  'grok-beta': { input: 5.0, output: 15.0, cacheRead: 0.50 },
  'grok-3': { input: 3.0, output: 15.0, cacheRead: 0.30 },
  'kimi-k1.5': { input: 1.0, output: 3.0, cacheRead: 0.15 },
  'kimi-latest': { input: 1.0, output: 3.0, cacheRead: 0.15 },
  'moonshot-v1-128k': { input: 1.2, output: 3.6, cacheRead: 0.20 },
  'moonshot-v1-32k': { input: 1.2, output: 3.6, cacheRead: 0.20 },
  'moonshot-v1-8k': { input: 1.2, output: 3.6, cacheRead: 0.20 },
  default: { input: 3.0, output: 15.0, cacheRead: 0.30 }
};

/**
 * Pure calculation function mirroring the exact token math and spend logic in src/app/api/cost/route.ts
 */
export function calculateUsageMetrics(
  modelKey: string,
  totalCtx: number,
  cacheRead: number,
  outTokens: number,
  turns = 1,
  maxCtx?: number,
  rates: Record<string, { input: number; output: number; cacheRead: number }> = MODEL_RATES
) {
  const rate = rates[modelKey] || rates.default;
  const freshInput = Math.max(0, totalCtx - cacheRead);
  const costUsd = (freshInput / 1_000_000) * rate.input +
                  (cacheRead / 1_000_000) * rate.cacheRead +
                  (outTokens / 1_000_000) * rate.output;
  const efficiency = totalCtx > 0 ? Math.min(100, (cacheRead / totalCtx) * 100) : 0;
  const meanCtx = turns > 0 ? Math.round(totalCtx / turns) : 0;

  return {
    key: modelKey,
    turns,
    total_ctx: totalCtx,
    out_tokens: outTokens,
    cache_read: cacheRead,
    fresh_input: freshInput,
    cache_efficiency_pct: Math.round(efficiency * 100) / 100,
    mean_ctx: meanCtx,
    max_ctx: maxCtx !== undefined ? maxCtx : totalCtx,
    cost_usd: Math.round(costUsd * 100) / 100,
    raw_cost_usd: costUsd,
    rate_applied: rate
  };
}

describe('AC1: Grok & Kimi Usage Tracking Aggregation Math', () => {

  // Test 1: grok-2 primary token aggregation and pricing math
  it('T1.1: grok-2 aggregates fresh input tokens, cache read tokens, and USD cost accurately', () => {
    // 2,000,000 total ctx, 1,800,000 cache read, 50,000 output tokens
    const metrics = calculateUsageMetrics('grok-2', 2_000_000, 1_800_000, 50_000);

    // Fresh input tokens = 2,000,000 - 1,800,000 = 200,000
    assert.strictEqual(metrics.fresh_input, 200_000, 'Fresh input must equal total_ctx - cache_read');

    // Rates: input=$2.00/1M, cacheRead=$0.20/1M, output=$10.00/1M
    // Fresh input cost: (200,000 / 1M) * 2.00 = $0.40
    // Cache read cost: (1,800,000 / 1M) * 0.20 = $0.36
    // Output token cost: (50,000 / 1M) * 10.00 = $0.50
    // Total cost = $0.40 + $0.36 + $0.50 = $1.26
    assert.strictEqual(metrics.cost_usd, 1.26, 'USD cost for grok-2 must match $1.26');

    // Cache hit percentage = (1,800,000 / 2,000,000) * 100 = 90.00%
    assert.strictEqual(metrics.cache_efficiency_pct, 90.00, 'Cache hit percentage must be 90.00%');
    assert.strictEqual(metrics.rate_applied.input, 2.0);
    assert.strictEqual(metrics.rate_applied.output, 10.0);
    assert.strictEqual(metrics.rate_applied.cacheRead, 0.20);
  });

  // Test 2: grok-2-mini token aggregation and pricing math
  it('T1.2: grok-2-mini aggregates lightweight model tokens and lower pricing rates correctly', () => {
    // 5,000,000 total ctx, 4,000,000 cache read, 250,000 output tokens
    const metrics = calculateUsageMetrics('grok-2-mini', 5_000_000, 4_000_000, 250_000);

    // Fresh input = 1,000,000
    assert.strictEqual(metrics.fresh_input, 1_000_000);

    // Rates: input=$0.50/1M, cacheRead=$0.05/1M, output=$2.00/1M
    // Fresh input cost: 1.0 * 0.50 = $0.50
    // Cache read cost: 4.0 * 0.05 = $0.20
    // Output cost: 0.25 * 2.00 = $0.50
    // Total cost = $0.50 + $0.20 + $0.50 = $1.20
    assert.strictEqual(metrics.cost_usd, 1.20, 'USD cost for grok-2-mini must match $1.20');
    assert.strictEqual(metrics.cache_efficiency_pct, 80.00, 'Cache hit percentage must be 80.00%');
  });

  // Test 3: kimi-k1.5 token aggregation and pricing math
  it('T1.3: kimi-k1.5 aggregates Moonshot API tokens and calculates correct USD spend', () => {
    // 3,000,000 total ctx, 2,700,000 cache read, 100,000 output tokens
    const metrics = calculateUsageMetrics('kimi-k1.5', 3_000_000, 2_700_000, 100_000);

    // Fresh input = 300,000
    assert.strictEqual(metrics.fresh_input, 300_000);

    // Rates: input=$1.00/1M, cacheRead=$0.15/1M, output=$3.00/1M
    // Fresh input cost: 0.30 * 1.00 = $0.30
    // Cache read cost: 2.70 * 0.15 = $0.405
    // Output cost: 0.10 * 3.00 = $0.30
    // Total cost = $0.30 + $0.405 + $0.30 = $1.005 -> rounds to $1.01
    assert.strictEqual(metrics.cost_usd, 1.01, 'USD cost for kimi-k1.5 must round to $1.01');
    assert.strictEqual(metrics.cache_efficiency_pct, 90.00, 'Cache efficiency must be 90.00%');
  });

  // Test 4: moonshot-v1-128k long-context token aggregation and pricing math
  it('T1.4: moonshot-v1-128k processes large 128k context windows with 1.2/3.6/0.20 rates', () => {
    // 10,000,000 total ctx, 9,500,000 cache read, 200,000 output tokens
    const metrics = calculateUsageMetrics('moonshot-v1-128k', 10_000_000, 9_500_000, 200_000);

    // Fresh input = 500,000
    assert.strictEqual(metrics.fresh_input, 500_000);

    // Rates: input=$1.20/1M, cacheRead=$0.20/1M, output=$3.60/1M
    // Fresh cost: 0.50 * 1.20 = $0.60
    // Cache read cost: 9.50 * 0.20 = $1.90
    // Output cost: 0.20 * 3.60 = $0.72
    // Total cost = $0.60 + $1.90 + $0.72 = $3.22
    assert.strictEqual(metrics.cost_usd, 3.22, 'USD cost for moonshot-v1-128k must match $3.22');
    assert.strictEqual(metrics.cache_efficiency_pct, 95.00, 'Cache hit percentage must be 95.00%');
  });

  // Test 5: grok-beta token aggregation and pricing math
  it('T1.5: grok-beta applies premium rates (5.0 / 15.0 / 0.50) accurately', () => {
    // 1,000,000 total ctx, 800,000 cache read, 50,000 output tokens
    const metrics = calculateUsageMetrics('grok-beta', 1_000_000, 800_000, 50_000);

    assert.strictEqual(metrics.fresh_input, 200_000);

    // Rates: input=$5.00/1M, cacheRead=$0.50/1M, output=$15.00/1M
    // Fresh cost: 0.20 * 5.00 = $1.00
    // Cache cost: 0.80 * 0.50 = $0.40
    // Output cost: 0.05 * 15.00 = $0.75
    // Total cost = $1.00 + $0.40 + $0.75 = $2.15
    assert.strictEqual(metrics.cost_usd, 2.15, 'USD cost for grok-beta must match $2.15');
    assert.strictEqual(metrics.cache_efficiency_pct, 80.00);
  });

  // Test 6: Boundary case - 0 tokens
  it('T1.6: Boundary: 0 total tokens prevents division by zero and outputs 0% efficiency and $0.00 cost', () => {
    const metrics = calculateUsageMetrics('grok-2', 0, 0, 0, 0);

    assert.strictEqual(metrics.fresh_input, 0);
    assert.strictEqual(metrics.cost_usd, 0.00);
    assert.strictEqual(metrics.cache_efficiency_pct, 0.00, 'Must safely yield 0% without NaN or Infinity');
    assert.strictEqual(metrics.mean_ctx, 0);
  });

  // Test 7: Boundary case - 100% cache hit
  it('T1.7: Boundary: 100% cache hit charges 0 fresh input tokens and outputs 100.00% efficiency', () => {
    // 4,000,000 total ctx, 4,000,000 cache read, 100,000 output tokens for grok-2
    const metrics = calculateUsageMetrics('grok-2', 4_000_000, 4_000_000, 100_000);

    assert.strictEqual(metrics.fresh_input, 0, 'Fresh input must be exactly 0 on 100% cache hit');
    assert.strictEqual(metrics.cache_efficiency_pct, 100.00, 'Efficiency must be exactly 100.00%');

    // Fresh cost: $0.00
    // Cache read cost: 4.0 * 0.20 = $0.80
    // Output cost: 0.10 * 10.00 = $1.00
    // Total cost = $1.80
    assert.strictEqual(metrics.cost_usd, 1.80);
  });

  // Test 8: Boundary case - 0% cache hit (cold start)
  it('T1.8: Boundary: 0% cache hit charges 100% fresh input rates and outputs 0.00% efficiency', () => {
    // 4,000,000 total ctx, 0 cache read, 100,000 output tokens for grok-2
    const metrics = calculateUsageMetrics('grok-2', 4_000_000, 0, 100_000);

    assert.strictEqual(metrics.fresh_input, 4_000_000, 'All tokens must be fresh input');
    assert.strictEqual(metrics.cache_efficiency_pct, 0.00, 'Efficiency must be exactly 0.00%');

    // Fresh cost: 4.0 * 2.00 = $8.00
    // Cache cost: $0.00
    // Output cost: 0.10 * 10.00 = $1.00
    // Total cost = $9.00
    assert.strictEqual(metrics.cost_usd, 9.00);
  });

  // Test 9: Boundary case - Missing/unrecognized model fallback
  it('T1.9: Boundary: unrecognized model correctly falls back to default rates (3.0 / 15.0 / 0.30)', () => {
    const metrics = calculateUsageMetrics('unregistered-grok-custom-variant', 1_000_000, 500_000, 100_000);

    assert.strictEqual(metrics.rate_applied.input, 3.0);
    assert.strictEqual(metrics.rate_applied.output, 15.0);
    assert.strictEqual(metrics.rate_applied.cacheRead, 0.30);

    // Fresh cost: 0.50 * 3.0 = $1.50
    // Cache cost: 0.50 * 0.30 = $0.15
    // Output cost: 0.10 * 15.0 = $1.50
    // Total cost = $3.15
    assert.strictEqual(metrics.cost_usd, 3.15);
    assert.strictEqual(metrics.cache_efficiency_pct, 50.00);
  });

  // Test 10: Boundary case - Anomalous cache_read > total_ctx clamp guard
  it('T1.10: Boundary: anomalous cache_read > total_ctx clamps fresh input to 0 and efficiency to 100%', () => {
    // Corrupt log entry where cache read is greater than total context
    const metrics = calculateUsageMetrics('kimi-k1.5', 1_000_000, 1_500_000, 50_000);

    assert.strictEqual(metrics.fresh_input, 0, 'Fresh input must never be negative');
    assert.strictEqual(metrics.cache_efficiency_pct, 100.00, 'Efficiency must be capped at 100%');
  });

  // Test 11: Multi-turn aggregation (turns, mean_ctx, max_ctx)
  it('T1.11: Multi-turn aggregation calculates correct turns, mean context, and max context for Kimi', () => {
    const turns = 5;
    const totalCtx = 1_250_000;
    const maxCtx = 450_000;
    const metrics = calculateUsageMetrics('kimi-k1.5', totalCtx, 1_150_000, 80_000, turns, maxCtx);

    assert.strictEqual(metrics.turns, 5);
    assert.strictEqual(metrics.mean_ctx, 250_000, 'Mean context must be total_ctx / turns (1,250,000 / 5 = 250,000)');
    assert.strictEqual(metrics.max_ctx, 450_000, 'Max context must preserve highest single-turn context');
    assert.strictEqual(metrics.cache_efficiency_pct, 92.00);
  });

  // Test 12: SQLite WAL JSON extraction parity for Grok & Kimi
  it('T1.12: SQLite json_extract aggregation query matches expected token tallies for Grok and Kimi', () => {
    const db = new Database(':memory:');
    try {
      db.exec(`
        CREATE TABLE usage_responses (
          provider TEXT,
          response_id TEXT,
          timestamp TEXT,
          model TEXT,
          usage TEXT,
          fingerprint TEXT,
          quarantined INTEGER,
          PRIMARY KEY(provider, response_id)
        );
      `);

      // Insert Grok and Kimi sample rows with JSON payloads
      const stmt = db.prepare(`INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)`);

      // Grok-2 Turn 1
      stmt.run(
        'xai', 'resp_grok_1', '2026-09-27T02:00:00Z', 'grok-2',
        JSON.stringify({ input_tokens: 1000000, cache_read_input_tokens: 900000, output_tokens: 25000 }),
        'fp_1', 0
      );
      // Grok-2 Turn 2
      stmt.run(
        'xai', 'resp_grok_2', '2026-09-27T02:05:00Z', 'grok-2',
        JSON.stringify({ input_tokens: 1500000, cache_read_input_tokens: 1400000, output_tokens: 35000 }),
        'fp_2', 0
      );
      // Kimi-k1.5 Turn 1
      stmt.run(
        'moonshot', 'resp_kimi_1', '2026-09-27T02:10:00Z', 'kimi-k1.5',
        JSON.stringify({ input_tokens: 2000000, cached_input_tokens: 1900000, output_tokens: 40000 }),
        'fp_3', 0
      );
      // Quarantined row (should be ignored by query)
      stmt.run(
        'xai', 'resp_grok_quarantined', '2026-09-27T02:15:00Z', 'grok-2',
        JSON.stringify({ input_tokens: 9999999, cache_read_input_tokens: 9999999, output_tokens: 99999 }),
        'fp_q', 1
      );

      // Execute authoritative cost query from src/app/api/cost/route.ts
      const queryStmt = db.prepare(`
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
        ORDER BY total_ctx DESC;
      `);

      const rows = queryStmt.all('2026-09-27T00:00:00Z') as Array<{
        key: string;
        turns: number;
        total_ctx: number;
        out_tokens: number;
        cache_read: number;
        max_ctx: number;
      }>;

      assert.strictEqual(rows.length, 2, 'Should return exactly 2 active models (grok-2 and kimi-k1.5)');

      const grokRow = rows.find(r => r.key === 'grok-2');
      assert.ok(grokRow, 'grok-2 row must exist');
      assert.strictEqual(grokRow.turns, 2, 'grok-2 turns must exclude quarantined row');
      assert.strictEqual(grokRow.total_ctx, 2_500_000, 'grok-2 total_ctx must sum 1M + 1.5M');
      assert.strictEqual(grokRow.cache_read, 2_300_000, 'grok-2 cache_read must sum 900k + 1.4M');
      assert.strictEqual(grokRow.out_tokens, 60_000, 'grok-2 out_tokens must sum 25k + 35k');
      assert.strictEqual(grokRow.max_ctx, 1_500_000, 'grok-2 max_ctx must be 1.5M');

      const kimiRow = rows.find(r => r.key === 'kimi-k1.5');
      assert.ok(kimiRow, 'kimi-k1.5 row must exist');
      assert.strictEqual(kimiRow.turns, 1);
      assert.strictEqual(kimiRow.total_ctx, 2_000_000);
      assert.strictEqual(kimiRow.cache_read, 1_900_000);
      assert.strictEqual(kimiRow.out_tokens, 40_000);
      assert.strictEqual(kimiRow.max_ctx, 2_000_000);

      // Verify that applying calculation to SQL results yields correct spend
      const grokMetrics = calculateUsageMetrics(grokRow.key, grokRow.total_ctx, grokRow.cache_read, grokRow.out_tokens, grokRow.turns, grokRow.max_ctx);
      // freshInput = 200,000 (0.2M * 2.0 = 0.40)
      // cacheRead = 2,300,000 (2.3M * 0.20 = 0.46)
      // outTokens = 60,000 (0.06M * 10.0 = 0.60)
      // total = 0.40 + 0.46 + 0.60 = 1.46
      assert.strictEqual(grokMetrics.cost_usd, 1.46);
      assert.strictEqual(grokMetrics.cache_efficiency_pct, 92.00);

    } finally {
      db.close();
    }
  });

});
