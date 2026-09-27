/**
 * tests/adversarial/tier5_frontend_grok_kimi_adversarial.test.ts
 *
 * Frontend Adversarial Stress & SSR Hardening for Grok & Kimi Components
 * (Challenger 2 / Milestone 5)
 *
 * Targeted Components & Stress Dimensions:
 * 1. AgentConfigGrid: 0 agents, 100 agents with mixed models (Grok, Kimi, Claude, Codex, AGY),
 *    unknown model types, status-based sorting, active count calculation, and filter buttons.
 * 2. QuotaComparisonMatrix: undefined/null grok and kimi props, extreme headroom numbers (0%, 100%, 150%),
 *    OFF-PACE state indicators, and countdown timer fallbacks.
 * 3. ProviderQuotaCard: extreme headroom numbers (0%, 100%, 150%, out-of-bounds, negative),
 *    provider branding (Grok xAI orange, Kimi Moonshot teal), and state transitions.
 * 4. CostCacheProjections: 0 tokens (division-by-zero protection), astronomical token numbers (85B+ tokens),
 *    model breakdown tables for Grok and Kimi variants with branding badges.
 * 5. ApiQuotaView: full SSR rendering lifecycle with live/mock sources, missing pool objects,
 *    and multi-timescale rate limit displays.
 * 6. Global Zero-Crash & Zero-NaN / Zero-Infinity Invariant Enforcement.
 */

import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import React from 'react';
import ReactDOMServer from 'react-dom/server';

const require = createRequire(import.meta.url);
const swc = require('next/dist/build/swc');

const moduleCache: Record<string, any> = {};

function requireTsxSync(filePath: string): any {
  const absPath = path.resolve(filePath);
  if (moduleCache[absPath]) return moduleCache[absPath];

  const code = fs.readFileSync(absPath, 'utf8');
  const transformed = swc.transformSync(code, {
    jsc: {
      parser: { syntax: 'typescript', tsx: true },
      transform: { react: { runtime: 'classic' } }
    },
    module: { type: 'commonjs' }
  });

  const m: { exports: any } = { exports: {} };
  const customRequire = (id: string) => {
    if (id.startsWith('@/')) {
      const rel = id.replace('@/', 'src/');
      let target = path.resolve(rel);
      if (!fs.existsSync(target)) {
        if (fs.existsSync(target + '.ts')) target += '.ts';
        else if (fs.existsSync(target + '.tsx')) target += '.tsx';
      }
      return requireTsxSync(target);
    }
    if (id.startsWith('./') || id.startsWith('../')) {
      let target = path.resolve(path.dirname(absPath), id);
      if (!fs.existsSync(target)) {
        if (fs.existsSync(target + '.ts')) target += '.ts';
        else if (fs.existsSync(target + '.tsx')) target += '.tsx';
      }
      return requireTsxSync(target);
    }
    return require(id);
  };

  const fn = new Function('require', 'module', 'exports', 'React', transformed.code);
  fn(customRequire, m, m.exports, React);
  moduleCache[absPath] = m.exports;
  return m.exports;
}

// Load target frontend components and utilities
const { AgentConfigGrid } = requireTsxSync('src/components/swarm-control/AgentConfigGrid.tsx');
const { QuotaComparisonMatrix } = requireTsxSync('src/components/api-quota/QuotaComparisonMatrix.tsx');
const { ProviderQuotaCard } = requireTsxSync('src/components/api-quota/ProviderQuotaCard.tsx');
const { DualQuotaProgress } = requireTsxSync('src/components/api-quota/DualQuotaProgress.tsx');
const { CostCacheProjections } = requireTsxSync('src/components/telemetry/CostCacheProjections.tsx');
const { ApiQuotaView } = requireTsxSync('src/components/api-quota/ApiQuotaView.tsx');
const { formatNumber, formatCurrency, formatPercent } = requireTsxSync('src/lib/utils.ts');
const { mockQuotas, mockCostData } = requireTsxSync('src/lib/mock-data.ts');

function cleanHtml(html: string): string {
  return html.replace(/<!--.*?-->/g, '');
}

function renderClean(element: React.ReactElement): string {
  return cleanHtml(ReactDOMServer.renderToString(element));
}

// ============================================================================
// SUITE 1: AgentConfigGrid Adversarial Stress (0 agents, 100 agents, mixed types)
// ============================================================================

test('T5.7.1: AgentConfigGrid renders cleanly with 0 agent seats without crash or NaN', () => {
  const html = renderClean(
    React.createElement(AgentConfigGrid, {
      agents: [],
      isLoading: false,
      onAgentUpdated: () => {}
    })
  );

  assert.ok(html.includes('Headless Swarm Agents'), 'Header must render');
  assert.ok(html.includes('0 Live'), 'Must display 0 Live');
  assert.ok(html.includes('0 Registered'), 'Must display 0 Registered');
  assert.ok(html.includes('All (0)'), 'Filter button must show All (0)');
  assert.ok(html.includes('Live (0)'), 'Filter button must show Live (0)');
  assert.ok(html.includes('>Grok<'), 'Grok filter button must render');
  assert.ok(html.includes('>Kimi<'), 'Kimi filter button must render');
  assert.ok(!html.includes('NaN'), 'Must never output NaN');
});

test('T5.7.2: AgentConfigGrid scales cleanly to 100 agents with mixed model types and statuses', () => {
  const types = ['claude', 'codex', 'antigravity', 'grok', 'kimi'] as const;
  const statuses = ['busy', 'idle', 'paused', 'offline'] as const;

  const grokModels = ['grok-2', 'grok-2-mini', 'grok-beta'];
  const kimiModels = ['kimi-k1.5', 'moonshot-v1-128k', 'moonshot-v1-32k', 'moonshot-v1-8k'];

  const agents: any[] = [];
  for (let i = 0; i < 100; i++) {
    const t = types[i % types.length];
    const s = statuses[i % statuses.length];
    let model = 'claude-sonnet-5';
    if (t === 'grok') model = grokModels[i % grokModels.length];
    else if (t === 'kimi') model = kimiModels[i % kimiModels.length];
    else if (t === 'codex') model = 'gpt-6-astra';
    else if (t === 'antigravity') model = 'gemini-3.8-flash-high';

    agents.push({
      seat: `agent-${String(i).padStart(3, '0')}`,
      role: `worker-role-${i % 10}`,
      type: t,
      host: `10.0.70.${100 + (i % 27)}`,
      pid: 1000 + i,
      claimed_at: new Date(Date.now() - i * 60000).toISOString(),
      model,
      status: s,
      turn_cap: (i % 60) + 1,
      reasoning_effort: (['none', 'low', 'medium', 'high', 'native'] as const)[i % 5]
    });
  }

  const expectedActive = agents.filter(a => a.status === 'busy').length;
  assert.strictEqual(agents.length, 100);
  assert.strictEqual(expectedActive, 25);

  const html = renderClean(
    React.createElement(AgentConfigGrid, {
      agents,
      isLoading: false,
      onAgentUpdated: () => {}
    })
  );

  // Verify counters
  assert.ok(html.includes(`${expectedActive} Live`), `Must display ${expectedActive} Live`);
  assert.ok(html.includes('100 Registered'), 'Must display 100 Registered');

  // Verify Grok distinctive branding & models
  assert.ok(html.includes('bg-orange-950 text-orange-400 border border-orange-800'), 'Must render Grok orange badges');
  assert.ok(html.includes('value="grok-2"'), 'Must offer grok-2 option');
  assert.ok(html.includes('value="grok-2-mini"'), 'Must offer grok-2-mini option');
  assert.ok(html.includes('value="grok-beta"'), 'Must offer grok-beta option');

  // Verify Kimi distinctive branding & models
  assert.ok(html.includes('bg-teal-950 text-teal-400 border border-teal-800'), 'Must render Kimi teal badges');
  assert.ok(html.includes('value="kimi-k1.5"'), 'Must offer kimi-k1.5 option');
  assert.ok(html.includes('value="moonshot-v1-128k"'), 'Must offer moonshot-v1-128k option');
  assert.ok(html.includes('value="moonshot-v1-32k"'), 'Must offer moonshot-v1-32k option');
  assert.ok(html.includes('value="moonshot-v1-8k"'), 'Must offer moonshot-v1-8k option');

  // Verify Fleet Rule 58 Turn Cap label
  assert.ok(html.includes('TURN CAP (FLEET RULE 58: MAX 60)'), 'Must render Fleet Rule 58 turn cap constraint');

  // Verify sorting invariant: busy agents must appear before non-busy agents
  const busyIndex = html.indexOf('>LIVE<');
  const idleIndex = html.indexOf('>IDLE<');
  assert.ok(busyIndex !== -1, 'Must find LIVE status badge');
  assert.ok(idleIndex !== -1, 'Must find IDLE status badge');
  assert.ok(busyIndex < idleIndex, 'LIVE agents must precede IDLE agents in sorted DOM');

  assert.ok(!html.includes('NaN'), '100-agent rendering must never contain NaN');
});

test('T5.7.3: AgentConfigGrid handles agents with unknown types and omitted optional fields gracefully', () => {
  const malformedAgents = [
    {
      seat: 'agent-malformed-001',
      role: 'investigator',
      type: 'unknown_agent_type' as any,
      host: '10.0.70.99',
      pid: null,
      claimed_at: '2026-09-27T00:00:00Z',
      model: 'unknown-model',
      status: 'idle' as const,
      // Omitted turn_cap and reasoning_effort
    }
  ];

  const html = renderClean(
    React.createElement(AgentConfigGrid, {
      agents: malformedAgents,
      isLoading: false,
      onAgentUpdated: () => {}
    })
  );

  // Defaults to 25 turns and medium reasoning
  assert.ok(html.includes('25 turns'), 'Must fallback omitted turn_cap to default 25');
  assert.ok(html.includes('agent-malformed-001'), 'Must render seat name');
  assert.ok(!html.includes('NaN'), 'Must never output NaN');
});

// ============================================================================
// SUITE 2: QuotaComparisonMatrix Adversarial Stress (undefined/null props & extremes)
// ============================================================================

test('T5.7.4: QuotaComparisonMatrix renders safely when grok and kimi props are undefined', () => {
  const html = renderClean(
    React.createElement(QuotaComparisonMatrix, {
      claudeA: mockQuotas.pools.claude_a,
      claudeB: mockQuotas.pools.claude_b,
      antigravity: mockQuotas.pools.antigravity,
      codex: mockQuotas.pools.codex,
      grok: undefined,
      kimi: undefined
    })
  );

  // Verify headers render with brand colors
  assert.ok(html.includes('Grok Fleet Pool (xAI)'), 'Header must include Grok');
  assert.ok(html.includes('Kimi Fleet Pool (Moonshot)'), 'Header must include Kimi');
  assert.ok(html.includes('bg-orange-950/20'), 'Grok header must have orange background accent');
  assert.ok(html.includes('bg-teal-950/20'), 'Kimi header must have teal background accent');

  // Verify default fallback numbers (Grok: 28% used -> 72% OK; Kimi: 15% used -> 85% OK)
  assert.ok(html.includes('72% OK'), 'Grok 5h headroom must fallback to 72% OK');
  assert.ok(html.includes('(28% used)'), 'Grok 5h used must fallback to 28% used');
  assert.ok(html.includes('85% OK'), 'Kimi 5h headroom must fallback to 85% OK');
  assert.ok(html.includes('(15% used)'), 'Kimi 5h used must fallback to 15% used');

  // Verify weekly default fallbacks (Grok: 42% used -> 58% OK; Kimi: 35% used -> 65% OK)
  assert.ok(html.includes('58% OK'), 'Grok weekly headroom must fallback to 58% OK');
  assert.ok(html.includes('(42% used)'), 'Grok weekly used must fallback to 42% used');
  assert.ok(html.includes('65% OK'), 'Kimi weekly headroom must fallback to 65% OK');
  assert.ok(html.includes('(35% used)'), 'Kimi weekly used must fallback to 35% used');

  // Reset cadence fallback
  assert.ok(html.includes('Rolling 5h'), 'Undefined resets_at must fallback to "Rolling 5h"');

  assert.ok(!html.includes('NaN'), 'Undefined props must never produce NaN');
});

test('T5.7.5: QuotaComparisonMatrix renders safely when grok and kimi props are explicitly null', () => {
  const html = renderClean(
    React.createElement(QuotaComparisonMatrix, {
      claudeA: mockQuotas.pools.claude_a,
      claudeB: mockQuotas.pools.claude_b,
      antigravity: mockQuotas.pools.antigravity,
      codex: mockQuotas.pools.codex,
      grok: null as any,
      kimi: null as any
    })
  );

  assert.ok(html.includes('Grok Fleet Pool (xAI)'));
  assert.ok(html.includes('Kimi Fleet Pool (Moonshot)'));
  assert.ok(html.includes('72% OK'));
  assert.ok(html.includes('85% OK'));
  assert.ok(!html.includes('NaN'), 'Explicit null props must never produce NaN');
});

test('T5.7.6: QuotaComparisonMatrix correctly reflects extreme headroom boundaries (0%, 100%, 150%) and OFF-PACE', () => {
  const extremeGrok = {
    name: 'Grok Fleet Pool (xAI)',
    state: 'OFF-PACE',
    five_hour_used_pct: 100, // 0% headroom -> CRIT
    weekly_used_pct: 150,    // 150% used -> clamped to 0% headroom -> CRIT
    resets_at: '2026-09-27T08:00:00Z',
    evidence: 'Exhausted during deep reasoning run'
  };

  const extremeKimi = {
    name: 'Kimi Fleet Pool (Moonshot)',
    state: 'OK',
    five_hour_used_pct: 0,   // 100% headroom -> OK
    weekly_used_pct: -20,    // Negative usage anomaly -> Math.max(0, 100 - (-20)) = 120% -> OK
    resets_at: null,
    evidence: 'Fresh allocation'
  };

  const html = renderClean(
    React.createElement(QuotaComparisonMatrix, {
      claudeA: mockQuotas.pools.claude_a,
      claudeB: mockQuotas.pools.claude_b,
      antigravity: mockQuotas.pools.antigravity,
      codex: mockQuotas.pools.codex,
      grok: extremeGrok,
      kimi: extremeKimi
    })
  );

  // Grok 0% headroom -> 0% CRIT
  assert.ok(html.includes('0% CRIT'), '100% and 150% used must render 0% CRIT');
  assert.ok(html.includes('bg-rose-950/60 text-rose-400 border border-rose-800'), '0% CRIT must use rose border and text');
  // Grok OFF-PACE status
  assert.ok(html.includes('OFF-PACE'), 'Must render Grok OFF-PACE badge');

  // Kimi 0% used -> 100% headroom -> 100% OK
  assert.ok(html.includes('100% OK'), '0% used must render 100% OK');

  assert.ok(!html.includes('NaN'), 'Extreme boundaries must never produce NaN');
});

// ============================================================================
// SUITE 3: ProviderQuotaCard Extreme Headroom & Provider Branding
// ============================================================================

test('T5.7.7: ProviderQuotaCard handles 0% headroom (100% used) with critical styling', () => {
  const html = renderClean(
    React.createElement(ProviderQuotaCard, {
      title: 'Grok Fleet Pool (xAI)',
      provider: 'grok',
      state: 'LIMITED',
      fiveHourMetric: { usedPct: 100, remainingPct: 0, rawMode: 'used' },
      weeklyMetric: { usedPct: 100, remainingPct: 0, rawMode: 'used' },
      resetsAt: '2026-09-27T06:00:00Z',
      evidence: 'Rate limit ceiling reached'
    })
  );

  assert.ok(html.includes('Grok Fleet Pool (xAI)'), 'Title must render');
  assert.ok(html.includes('xAI'), 'xAI badge must render');
  assert.ok(html.includes('border-orange-800/60'), 'Grok card must have orange border');
  assert.ok(html.includes('0% Headroom'), 'Must display 0% Headroom');
  assert.ok(html.includes('(100% used)'), 'Must display (100% used)');
  assert.ok(html.includes('style="width:100%"'), 'Progress bar must fill to 100%');
  assert.ok(html.includes('from-rose-600 to-rose-400'), 'Must use rose gradient for critical headroom');
  assert.ok(!html.includes('NaN'), 'Must never output NaN');
});

test('T5.7.8: ProviderQuotaCard handles 100% headroom (0% used) with pristine styling', () => {
  const html = renderClean(
    React.createElement(ProviderQuotaCard, {
      title: 'Kimi Fleet Pool (Moonshot)',
      provider: 'kimi',
      state: 'OK',
      fiveHourMetric: { usedPct: 0, remainingPct: 100, rawMode: 'used' },
      weeklyMetric: { usedPct: 0, remainingPct: 100, rawMode: 'used' },
      resetsAt: null,
      evidence: 'All allocations unused'
    })
  );

  assert.ok(html.includes('Kimi Fleet Pool (Moonshot)'), 'Title must render');
  assert.ok(html.includes('Moonshot'), 'Moonshot badge must render');
  assert.ok(html.includes('border-teal-800/60'), 'Kimi card must have teal border');
  assert.ok(html.includes('100% Headroom'), 'Must display 100% Headroom');
  assert.ok(html.includes('(0% used)'), 'Must display (0% used)');
  assert.ok(html.includes('style="width:0%"'), 'Progress bar width must be 0%');
  assert.strictEqual(html.includes('5h Window Reset:'), false, 'Null resetsAt must omit 5h Window Reset section');
  assert.ok(!html.includes('NaN'), 'Must never output NaN');
});

test('T5.7.9: ProviderQuotaCard clamps out-of-bounds 150% headroom safely to [0, 100]', () => {
  const html = renderClean(
    React.createElement(ProviderQuotaCard, {
      title: 'Grok Fleet Pool (xAI)',
      provider: 'grok',
      state: 'OK',
      fiveHourMetric: { usedPct: -50, remainingPct: 150, rawMode: 'used' },
      weeklyMetric: { usedPct: 150, remainingPct: -50, rawMode: 'used' },
      resetsAt: null,
      evidence: 'Anomalous negative / overflow metric probe'
    })
  );

  // -50% used clamped to 0%, 150% remaining clamped to 100%
  assert.ok(html.includes('style="width:0%"'), 'Negative used must clamp width to 0%');
  assert.ok(html.includes('100% Headroom'), 'Overflow remaining must clamp to 100% Headroom');

  // 150% used clamped to 100%, -50% remaining clamped to 0%
  assert.ok(html.includes('style="width:100%"'), 'Overflow used must clamp width to 100%');
  assert.ok(html.includes('0% Headroom'), 'Negative remaining must clamp to 0% Headroom');

  assert.ok(!html.includes('NaN'), 'Must never output NaN');
});

// ============================================================================
// SUITE 4: CostCacheProjections (0 tokens, huge numbers, Grok & Kimi breakdown)
// ============================================================================

test('T5.7.10: CostCacheProjections renders cleanly with 0 tokens and empty breakdown', () => {
  const zeroData = {
    aggregate: {
      total_context_tokens: 0,
      total_output_tokens: 0,
      total_cache_read_tokens: 0,
      overall_cache_hit_pct: 0,
      total_cost_usd: 0,
      projected_24h_cost_usd: 0
    },
    breakdown: []
  };

  const html = renderClean(
    React.createElement(CostCacheProjections, {
      costData: zeroData,
      timeRange: '24h',
      onTimeRangeChange: () => {},
      isLoading: false
    })
  );

  assert.ok(html.includes('0.0%'), 'Cache efficiency must render 0.0%');
  assert.ok(html.includes('0'), 'Token count must render 0');
  assert.ok(html.includes('$0.00'), 'Spend must render $0.00');
  assert.ok(!html.includes('NaN'), 'Rendered HTML must never contain NaN');
  assert.ok(!html.includes('Infinity'), 'Rendered HTML must never contain Infinity');
});

test('T5.7.11: CostCacheProjections renders Grok & Kimi breakdown rows with 0 tokens cleanly', () => {
  const dataWithZeroModels = {
    aggregate: {
      total_context_tokens: 0,
      total_output_tokens: 0,
      total_cache_read_tokens: 0,
      overall_cache_hit_pct: 0,
      total_cost_usd: 0,
      projected_24h_cost_usd: 0
    },
    breakdown: [
      { key: 'grok-2', turns: 0, total_ctx: 0, cache_read: 0, cache_efficiency_pct: 0, cost_usd: 0 },
      { key: 'kimi-k1.5', turns: 0, total_ctx: 0, cache_read: 0, cache_efficiency_pct: 0, cost_usd: 0 }
    ]
  };

  const html = renderClean(
    React.createElement(CostCacheProjections, {
      costData: dataWithZeroModels,
      timeRange: '24h',
      onTimeRangeChange: () => {},
      isLoading: false
    })
  );

  assert.ok(html.includes('grok-2'), 'Must list grok-2 in breakdown');
  assert.ok(html.includes('xAI'), 'Must render xAI badge for grok-2');
  assert.ok(html.includes('text-orange-400 font-bold'), 'Grok row must have orange text');

  assert.ok(html.includes('kimi-k1.5'), 'Must list kimi-k1.5 in breakdown');
  assert.ok(html.includes('Moonshot'), 'Must render Moonshot badge for kimi-k1.5');
  assert.ok(html.includes('text-teal-400 font-bold'), 'Kimi row must have teal text');

  assert.ok(!html.includes('NaN'), 'Zero token rows must never produce NaN');
  assert.ok(!html.includes('Infinity'), 'Zero token rows must never produce Infinity');
});

test('T5.7.12: CostCacheProjections scales to 85 Billion tokens without numeric overflow or NaN', () => {
  const hugeData = {
    aggregate: {
      total_context_tokens: 85_000_000_000,
      total_output_tokens: 4_500_000_000,
      total_cache_read_tokens: 80_750_000_000,
      overall_cache_hit_pct: 95.0,
      total_cost_usd: 175_840.50,
      projected_24h_cost_usd: 703_362.00
    },
    breakdown: [
      { key: 'grok-2', turns: 12000, total_ctx: 25_000_000_000, cache_read: 23_750_000_000, cache_efficiency_pct: 95.0, cost_usd: 51_250.00 },
      { key: 'grok-2-mini', turns: 35000, total_ctx: 15_000_000_000, cache_read: 14_250_000_000, cache_efficiency_pct: 95.0, cost_usd: 12_000.00 },
      { key: 'grok-beta', turns: 5000, total_ctx: 10_000_000_000, cache_read: 9_500_000_000, cache_efficiency_pct: 95.0, cost_usd: 35_000.00 },
      { key: 'kimi-k1.5', turns: 18000, total_ctx: 20_000_000_000, cache_read: 19_000_000_000, cache_efficiency_pct: 95.0, cost_usd: 38_000.00 },
      { key: 'moonshot-v1-128k', turns: 10000, total_ctx: 15_000_000_000, cache_read: 14_250_000_000, cache_efficiency_pct: 95.0, cost_usd: 39_590.50 }
    ]
  };

  const html = renderClean(
    React.createElement(CostCacheProjections, {
      costData: hugeData,
      timeRange: '24h',
      onTimeRangeChange: () => {},
      isLoading: false
    })
  );

  // Formatter verifications for astronomical numbers
  assert.ok(html.includes('85,000,000,000'), 'Must format 85B with commas');
  assert.ok(html.includes('80,750,000,000'), 'Must format 80.75B cached with commas');
  assert.ok(html.includes('$175,840.50'), 'Must format $175,840.50 spend with currency symbol');

  // 7-Day projection: 703362 * 7 = 4,923,534.00
  assert.ok(html.includes('$4,923,534.00'), 'Must project 7-day spend to $4,923,534.00');

  // Model breakdown table entries
  assert.ok(html.includes('grok-2'), 'Must include grok-2');
  assert.ok(html.includes('grok-2-mini'), 'Must include grok-2-mini');
  assert.ok(html.includes('grok-beta'), 'Must include grok-beta');
  assert.ok(html.includes('kimi-k1.5'), 'Must include kimi-k1.5');
  assert.ok(html.includes('moonshot-v1-128k'), 'Must include moonshot-v1-128k');

  // Chart computation oracle
  const steps = 12;
  const baseCached = hugeData.aggregate.total_cache_read_tokens / steps;
  const baseFresh = (hugeData.aggregate.total_context_tokens - hugeData.aggregate.total_cache_read_tokens) / steps;
  const baseCost = hugeData.aggregate.total_cost_usd / steps;

  assert.ok(Number.isFinite(baseCached), 'baseCached must be finite');
  assert.ok(Number.isFinite(baseFresh), 'baseFresh must be finite');
  assert.ok(Number.isFinite(baseCost), 'baseCost must be finite');

  for (let i = 1; i <= steps; i++) {
    const cachedTokens = Math.round(baseCached * (0.8 + 0.4 * (i / steps)));
    const freshTokens = Math.round(baseFresh * (0.8 + 0.4 * (i / steps)));
    const costUsd = Number((baseCost * i * 0.95).toFixed(2));
    assert.ok(Number.isFinite(cachedTokens), `Step ${i} cachedTokens must be finite`);
    assert.ok(Number.isFinite(freshTokens), `Step ${i} freshTokens must be finite`);
    assert.ok(Number.isFinite(costUsd), `Step ${i} costUsd must be finite`);
  }

  assert.ok(!html.includes('NaN'), 'Huge number rendering must never contain NaN');
  assert.ok(!html.includes('Infinity'), 'Huge number rendering must never contain Infinity');
});

// ============================================================================
// SUITE 5: Full ApiQuotaView SSR & Global Zero-Crash Invariant
// ============================================================================

test('T5.7.13: ApiQuotaView renders complete layout with Grok and Kimi cards without SSR error', () => {
  const html = renderClean(
    React.createElement(ApiQuotaView, {
      initialData: mockQuotas,
      refreshIntervalMs: 10000
    })
  );

  assert.ok(html.includes('API Quota &amp; Rate Limit Command Center') || html.includes('API Quota & Rate Limit Command Center'));
  assert.ok(html.includes('Grok Fleet Pool (xAI)'), 'Must render Grok provider card');
  assert.ok(html.includes('Kimi Fleet Pool (Moonshot)'), 'Must render Kimi provider card');
  assert.ok(html.includes('xAI Allocation'), 'Must render Grok routing badge');
  assert.ok(html.includes('Moonshot Quota'), 'Must render Kimi routing badge');
  assert.ok(!html.includes('NaN'), 'ApiQuotaView SSR must never contain NaN');
  assert.ok(!html.includes('Infinity'), 'ApiQuotaView SSR must never contain Infinity');
});

test('T5.7.14: ApiQuotaView renders safely when grok and kimi pools are omitted from initialData', () => {
  const minimalQuotas = {
    timestamp: new Date().toISOString(),
    pools: {
      claude_a: mockQuotas.pools.claude_a,
      claude_b: mockQuotas.pools.claude_b,
      codex: mockQuotas.pools.codex,
      antigravity: mockQuotas.pools.antigravity
    }
  };

  const html = renderClean(
    React.createElement(ApiQuotaView, {
      initialData: minimalQuotas as any,
      refreshIntervalMs: 10000
    })
  );

  // Even without grok/kimi in response, cards default safely
  assert.ok(html.includes('Grok Fleet Pool (xAI)'));
  assert.ok(html.includes('Kimi Fleet Pool (Moonshot)'));
  assert.ok(!html.includes('NaN'), 'Minimal quotas must never produce NaN');
});

test('T5.7.15: Global Regex Sweep across all component renders confirms zero NaN / Infinity strings', () => {
  const testComponents = [
    React.createElement(AgentConfigGrid, { agents: [], isLoading: false, onAgentUpdated: () => {} }),
    React.createElement(QuotaComparisonMatrix, {
      claudeA: mockQuotas.pools.claude_a,
      claudeB: mockQuotas.pools.claude_b,
      antigravity: mockQuotas.pools.antigravity,
      codex: mockQuotas.pools.codex,
      grok: mockQuotas.pools.grok,
      kimi: mockQuotas.pools.kimi
    }),
    React.createElement(ProviderQuotaCard, {
      title: 'Grok Test',
      provider: 'grok',
      state: 'OK',
      fiveHourMetric: { usedPct: 50, remainingPct: 50, rawMode: 'used' },
      weeklyMetric: { usedPct: 50, remainingPct: 50, rawMode: 'used' },
      evidence: 'test'
    }),
    React.createElement(ProviderQuotaCard, {
      title: 'Kimi Test',
      provider: 'kimi',
      state: 'OK',
      fiveHourMetric: { usedPct: 50, remainingPct: 50, rawMode: 'used' },
      weeklyMetric: { usedPct: 50, remainingPct: 50, rawMode: 'used' },
      evidence: 'test'
    }),
    React.createElement(CostCacheProjections, {
      costData: mockCostData,
      timeRange: '24h',
      onTimeRangeChange: () => {},
      isLoading: false
    })
  ];

  for (let i = 0; i < testComponents.length; i++) {
    const html = renderClean(testComponents[i]);
    // Match isolated word "NaN" or "$NaN" or "Infinity"
    assert.strictEqual(
      /\bNaN\b/.test(html),
      false,
      `Component #${i} rendered illegal NaN token`
    );
    assert.strictEqual(
      /\bInfinity\b/.test(html),
      false,
      `Component #${i} rendered illegal Infinity token`
    );
  }
});
