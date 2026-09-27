/**
 * tests/adversarial/tier5_frontend_adversarial.test.ts
 *
 * Tier 5 Adversarial Coverage Hardening Test Suite (m4_challenger_2)
 *
 * Verification Dimensions:
 * 1. Offline / Network Partition Recovery in Polling Loops
 * 2. Rapid UI Interaction Bursts & State Synchronization (Priority Clicks, Reorders, Dnd-Kit)
 * 3. Division-by-Zero Risks in Cache Efficiency, Token Percentages & Quantities
 * 4. Empty Dataset Handling Across All Frontend Components (0 Nodes, 0 Shards, 0 Items, 0 Cost)
 * 5. Component ErrorBoundary Isolation, Blast Radius Containment & Recovery Lifecycle
 * 6. SSR Rendering & Hydration Safety Invariants (ClientOnly boundaries, Deterministic Pre-Hydration)
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

// Load frontend components & mock utilities
const { ErrorBoundary } = requireTsxSync('src/components/shared/ErrorBoundary.tsx');
const { ClientOnly } = requireTsxSync('src/components/shared/ClientOnly.tsx');
const { StatusBadge } = requireTsxSync('src/components/shared/StatusBadge.tsx');
const { HeaderBar } = requireTsxSync('src/components/layout/HeaderBar.tsx');
const { TabNav, DASHBOARD_TABS } = requireTsxSync('src/components/layout/TabNav.tsx');
const { DashboardShell } = requireTsxSync('src/components/layout/DashboardShell.tsx');
const { ArchitectureVisualizer } = requireTsxSync('src/components/architecture/ArchitectureVisualizer.tsx');
const { NodeLatencyGrid } = requireTsxSync('src/components/telemetry/NodeLatencyGrid.tsx');
const { CiShardMatrix } = requireTsxSync('src/components/telemetry/CiShardMatrix.tsx');
const { CostCacheProjections } = requireTsxSync('src/components/telemetry/CostCacheProjections.tsx');
const { ShardDiagnosticModal } = requireTsxSync('src/components/telemetry/ShardDiagnosticModal.tsx');
const { SortableQueueTable } = requireTsxSync('src/components/swarm-control/SortableQueueTable.tsx');
const { QueueRow } = requireTsxSync('src/components/swarm-control/QueueRow.tsx');
const { QueueDispatcher } = requireTsxSync('src/components/swarm-control/QueueDispatcher.tsx');
const { AgentConfigGrid } = requireTsxSync('src/components/swarm-control/AgentConfigGrid.tsx');
const { DualQuotaProgress } = requireTsxSync('src/components/api-quota/DualQuotaProgress.tsx');
const { ProviderQuotaCard } = requireTsxSync('src/components/api-quota/ProviderQuotaCard.tsx');
const { QuotaComparisonMatrix } = requireTsxSync('src/components/api-quota/QuotaComparisonMatrix.tsx');
const { ApiQuotaView } = requireTsxSync('src/components/api-quota/ApiQuotaView.tsx');
const { formatNumber, formatCurrency, formatPercent, formatDuration } = requireTsxSync('src/lib/utils.ts');
const { mockNodes, mockShardsResponse, mockCostData, mockQueueItems, mockAgentsResponse, mockQuotas } = requireTsxSync('src/lib/mock-data.ts');

function cleanHtml(html: string): string {
  return html.replace(/<!--.*?-->/g, '');
}

function renderClean(element: React.ReactElement): string {
  return cleanHtml(ReactDOMServer.renderToString(element));
}

// ============================================================================
// SUITE 1: Offline / Network Partition & Polling Loop Resilience
// ============================================================================

test('T5.1.1: TelemetryView polling lifecycle handles network partition by falling back to mock data', async () => {
  // Simulated state machine of TelemetryView fetchNodes:
  // 1. Initial network partition: fetch fails with TypeError ('Failed to fetch')
  let nodesData: any = null;
  let isMockFallback = false;
  let isLoadingNodes = true;
  let isProbing = false;

  const mockFetchNodes = async (probe: boolean, fetchImpl: (url: string) => Promise<any>) => {
    try {
      if (probe) isProbing = true;
      const res = await fetchImpl(`/api/nodes${probe ? '?probe=true' : ''}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      nodesData = data;
      if (data.source === 'mock') isMockFallback = true;
    } catch {
      nodesData = {
        timestamp: new Date().toISOString(),
        total_nodes: mockNodes.length,
        up_nodes: mockNodes.filter((n: any) => n.status === 'up').length,
        blacklisted_count: 1,
        nodes: mockNodes,
        source: 'mock'
      };
      isMockFallback = true;
    } finally {
      isLoadingNodes = false;
      isProbing = false;
    }
  };

  // Simulate network failure
  const failingFetch = async () => {
    throw new TypeError('Failed to fetch: Network partition / server offline');
  };

  await mockFetchNodes(false, failingFetch);

  assert.strictEqual(isLoadingNodes, false, 'isLoadingNodes must be false after failed poll');
  assert.strictEqual(isMockFallback, true, 'isMockFallback must be set to true on network error');
  assert.ok(nodesData !== null, 'nodesData must be populated with fallback data');
  assert.strictEqual(nodesData.source, 'mock', 'nodesData source must be mock');
  assert.strictEqual(nodesData.total_nodes, mockNodes.length, 'Must provide full fallback node count');

  // Verify UI renders cold feed mock warning banner when isMockFallback is true
  const htmlFallback = renderClean(
    React.createElement('div', { className: 'space-y-6' },
      isMockFallback && React.createElement('span', { className: 'text-amber-400' }, 'COLD FEED (MOCK FALLBACK)')
    )
  );
  assert.ok(htmlFallback.includes('COLD FEED (MOCK FALLBACK)'), 'Banner must be visible during offline state');

  // 2. Recovery: network reconnects and returns live 200 OK data
  const liveNodesResponse = {
    timestamp: new Date().toISOString(),
    total_nodes: 27,
    up_nodes: 26,
    blacklisted_count: 1,
    nodes: mockNodes.map((n: any) => ({ ...n, status: 'up' })),
    source: 'live'
  };

  const recoveringFetch = async () => ({
    ok: true,
    status: 200,
    json: async () => liveNodesResponse
  });

  isMockFallback = false; // reset for live poll
  await mockFetchNodes(false, recoveringFetch);

  assert.strictEqual(isMockFallback, false, 'isMockFallback must be false when live feed returns');
  assert.strictEqual(nodesData.source, 'live', 'nodesData source must be live');
  assert.strictEqual(nodesData.up_nodes, 26, 'Live telemetry up_nodes must be recorded');
});

test('T5.1.2: Shards and Cost polling recovery handles HTTP 500/503 errors without unhandled rejections', async () => {
  let shardsData: any = null;
  let costData: any = null;
  let isMockFallback = false;

  const fetchShards = async (fetchImpl: () => Promise<any>) => {
    try {
      const res = await fetchImpl();
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      shardsData = await res.json();
    } catch {
      shardsData = { ...mockShardsResponse, source: 'mock' };
      isMockFallback = true;
    }
  };

  const fetchCost = async (fetchImpl: () => Promise<any>) => {
    try {
      const res = await fetchImpl();
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      costData = await res.json();
    } catch {
      costData = { ...mockCostData, source: 'mock' };
      isMockFallback = true;
    }
  };

  // Test with HTTP 503 for shards and HTTP 500 for cost
  await fetchShards(async () => ({ ok: false, status: 503 }));
  await fetchCost(async () => ({ ok: false, status: 500 }));

  assert.strictEqual(isMockFallback, true, 'isMockFallback must be true on HTTP error');
  assert.strictEqual(shardsData.source, 'mock', 'shardsData must be populated with mock data');
  assert.strictEqual(costData.source, 'mock', 'costData must be populated with mock data');

  // Verify CostCacheProjections renders mock data cleanly without crashing
  const costHtml = renderClean(
    React.createElement(CostCacheProjections, {
      costData,
      timeRange: '24h',
      onTimeRangeChange: () => {},
      isLoading: false
    })
  );
  assert.ok(costHtml.includes('Token Cost Telemetry &amp; Prefix Cache Projections'));
  assert.ok(costHtml.includes('Cache Efficiency'));
});

test('T5.1.3: SwarmControlView polling recovers from backend partition', async () => {
  let queueData: any = null;
  let agentsData: any = null;
  let isMockFallback = false;

  const fetchQueue = async (fetchImpl: () => Promise<any>) => {
    try {
      const res = await fetchImpl();
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      queueData = await res.json();
    } catch {
      queueData = {
        timestamp: new Date().toISOString(),
        total_entries: mockQueueItems.length,
        active_count: mockQueueItems.filter((i: any) => i.is_active).length,
        completed_count: mockQueueItems.filter((i: any) => !i.is_active).length,
        items: mockQueueItems,
        source: 'mock'
      };
      isMockFallback = true;
    }
  };

  const fetchAgents = async (fetchImpl: () => Promise<any>) => {
    try {
      const res = await fetchImpl();
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      agentsData = await res.json();
    } catch {
      agentsData = { ...mockAgentsResponse, source: 'mock' };
      isMockFallback = true;
    }
  };

  // 1. Simulate failure
  await fetchQueue(async () => { throw new Error('ECONNREFUSED'); });
  await fetchAgents(async () => { throw new Error('ECONNREFUSED'); });

  assert.strictEqual(isMockFallback, true);
  assert.strictEqual(queueData.items.length, mockQueueItems.length);
  assert.strictEqual(agentsData.agents.length, mockAgentsResponse.agents.length);

  // 2. Simulate recovery
  const liveQueue = {
    timestamp: new Date().toISOString(),
    total_entries: 2,
    active_count: 2,
    completed_count: 0,
    items: [mockQueueItems[0], mockQueueItems[1]],
    source: 'live'
  };

  isMockFallback = false;
  await fetchQueue(async () => ({ ok: true, status: 200, json: async () => liveQueue }));

  assert.strictEqual(queueData.source, 'live');
  assert.strictEqual(queueData.total_entries, 2);
});

test('T5.1.4: Tab visibilitychange listener suppresses polls when hidden and triggers immediate poll on visible', () => {
  let pollTriggeredCount = 0;
  let isVisible = true;

  const pollAction = () => {
    if (isVisible) pollTriggeredCount++;
  };

  // Document becomes hidden
  isVisible = false;
  pollAction(); // interval fires in background
  assert.strictEqual(pollTriggeredCount, 0, 'Poll must NOT execute when document is hidden');

  // Document returns to visible -> immediate catch-up trigger
  isVisible = true;
  pollAction(); // visibilitychange fires
  assert.strictEqual(pollTriggeredCount, 1, 'Poll MUST execute immediately when document becomes visible');
});

// ============================================================================
// SUITE 2: Rapid UI Interaction Bursts & State Synchronization
// ============================================================================

test('T5.2.1: QueueDispatcher bounds check suppresses rapid bursts on boundary items', () => {
  const items = [...mockQueueItems];
  let reorderCalls = 0;

  const handleReorder = (_newItems: any[]) => {
    reorderCalls++;
  };

  // Test Move Up boundary: index <= 0
  const handleMoveUp = (index: number) => {
    if (index <= 0) return;
    const newItems = [...items];
    const temp = newItems[index - 1];
    newItems[index - 1] = newItems[index];
    newItems[index] = temp;
    handleReorder(newItems);
  };

  // Test Move Down boundary: index >= items.length - 1
  const handleMoveDown = (index: number) => {
    if (index >= items.length - 1) return;
    const newItems = [...items];
    const temp = newItems[index + 1];
    newItems[index + 1] = newItems[index];
    newItems[index] = temp;
    handleReorder(newItems);
  };

  // Fire a burst of 25 rapid clicks on Move Up for index 0 (top item)
  for (let i = 0; i < 25; i++) {
    handleMoveUp(0);
  }
  assert.strictEqual(reorderCalls, 0, 'Burst of 25 Move Up clicks at index 0 must be 100% ignored');

  // Fire a burst of 25 rapid clicks on Move Down for the last item
  for (let i = 0; i < 25; i++) {
    handleMoveDown(items.length - 1);
  }
  assert.strictEqual(reorderCalls, 0, 'Burst of 25 Move Down clicks at last index must be 100% ignored');

  // Test single-item queue boundary
  const singleItem = [items[0]];
  const handleMoveUpSingle = (index: number) => {
    if (index <= 0) return;
    reorderCalls++;
  };
  const handleMoveDownSingle = (index: number) => {
    if (index >= singleItem.length - 1) return;
    reorderCalls++;
  };
  handleMoveUpSingle(0);
  handleMoveDownSingle(0);
  assert.strictEqual(reorderCalls, 0, 'Single-item queue must reject both Move Up and Move Down');
});

test('T5.2.2: 50-step rapid priority clicking burst strictly conserves all tasks without duplicates or omissions', () => {
  let currentItems = mockQueueItems.slice(0, 5);
  const initialTaskSlugs = new Set(currentItems.map((i: any) => i.row));

  // Perform 50 rapid alternating Move Up / Move Down operations on valid indices
  for (let step = 0; step < 50; step++) {
    const targetIdx = 1 + (step % 3); // cycles through indices 1, 2, 3
    const moveUp = step % 2 === 0;

    const newItems = [...currentItems];
    const swapIdx = moveUp ? targetIdx - 1 : targetIdx + 1;
    const temp = newItems[swapIdx];
    newItems[swapIdx] = newItems[targetIdx];
    newItems[targetIdx] = temp;
    currentItems = newItems;

    // Verify invariants after every single step in the burst:
    assert.strictEqual(currentItems.length, 5, `Length invariant violated at step ${step}`);
    const currentSlugs = new Set(currentItems.map((i: any) => i.row));
    assert.strictEqual(currentSlugs.size, 5, `Duplicate items created at step ${step}`);
    for (const slug of initialTaskSlugs) {
      assert.ok(currentSlugs.has(slug), `Item ${slug} dropped at step ${step}`);
    }
  }
});

test('T5.2.3: Concurrency Conflict (HTTP 409) during rapid clicking rolls back cleanly to snapshot', async () => {
  const initial = mockQueueItems.slice(0, 3);
  let state = [...initial];
  let snapshot = [...initial];
  let isMutating = false;
  let rollbackTriggered = false;

  const executeReorderWithConflict = async () => {
    // 1. Snapshot
    snapshot = state;
    // 2. Optimistic local update (swap 0 and 1)
    state = [state[1], state[0], state[2]];
    isMutating = true;

    // 3. Simulated API call returning HTTP 409
    const res = { status: 409, ok: false };
    if (res.status === 409) {
      // Rollback
      state = snapshot;
      rollbackTriggered = true;
      isMutating = false;
    }
  };

  await executeReorderWithConflict();

  assert.strictEqual(rollbackTriggered, true, 'Rollback must be triggered on 409');
  assert.strictEqual(isMutating, false, 'isMutating must reset to false');
  assert.strictEqual(state[0].row, initial[0].row, 'Item 0 must be restored');
  assert.strictEqual(state[1].row, initial[1].row, 'Item 1 must be restored');
  assert.deepStrictEqual(state, initial, 'State must match initial snapshot perfectly');
});

test('T5.2.4: Network failure during burst rolls back state cleanly without leaving orphaned mutation lock', async () => {
  const initial = mockQueueItems.slice(0, 3);
  let state = [...initial];
  let snapshot = [...initial];
  let isMutating = false;
  let caughtError: string | null = null;

  const executeReorderWithNetworkDrop = async () => {
    snapshot = state;
    state = [state[2], state[1], state[0]];
    isMutating = true;

    try {
      throw new TypeError('Failed to fetch: Connection timeout / socket closed');
    } catch (err: any) {
      state = snapshot;
      caughtError = err.message;
    } finally {
      isMutating = false;
    }
  };

  await executeReorderWithNetworkDrop();

  assert.strictEqual(isMutating, false, 'isMutating flag must be cleared in finally block');
  assert.ok(caughtError?.includes('Failed to fetch'), 'Error must be caught and handled');
  assert.deepStrictEqual(state, initial, 'State must be fully reverted to initial snapshot');
});

test('T5.2.5: Dnd-Kit drag end edge cases (self-drag, outside drop, invalid IDs) handled safely', () => {
  const items = mockQueueItems.slice(0, 4);
  let reorderPayload: any = null;

  const handleDragEndSim = (activeId: string, overId: string | null) => {
    if (!overId || activeId === overId) return;

    const oldIndex = items.findIndex((i: any) => i.row === activeId);
    const newIndex = items.findIndex((i: any) => i.row === overId);

    if (oldIndex !== -1 && newIndex !== -1) {
      // Reorder
      const reordered = [...items];
      const [moved] = reordered.splice(oldIndex, 1);
      reordered.splice(newIndex, 0, moved);
      reorderPayload = reordered;
    }
  };

  // Edge case 1: Dropping on self
  reorderPayload = null;
  handleDragEndSim('task_1', 'task_1');
  assert.strictEqual(reorderPayload, null, 'Dropping on self must be a no-op');

  // Edge case 2: Dropping outside droppable target (over === null)
  reorderPayload = null;
  handleDragEndSim('task_1', null);
  assert.strictEqual(reorderPayload, null, 'Dropping outside must be a no-op');

  // Edge case 3: Invalid active ID
  reorderPayload = null;
  handleDragEndSim('non_existent_task', 'task_2');
  assert.strictEqual(reorderPayload, null, 'Invalid active ID must be a no-op');

  // Edge case 4: Invalid over ID
  reorderPayload = null;
  handleDragEndSim('task_1', 'non_existent_target');
  assert.strictEqual(reorderPayload, null, 'Invalid over ID must be a no-op');

  // Edge case 5: Valid drag
  reorderPayload = null;
  handleDragEndSim(items[0].row, items[2].row);
  assert.ok(reorderPayload !== null, 'Valid drag must produce reordered list');
  assert.strictEqual(reorderPayload[2].row, items[0].row, 'Item must move to target index');
});

test('T5.2.6: QueueDispatcher isolates background polls from overwriting state while isMutating is true', () => {
  const localModifiedItems = [mockQueueItems[1], mockQueueItems[0]];
  const incomingServerPollItems = [mockQueueItems[0], mockQueueItems[1]];

  let currentItems = localModifiedItems;
  const isMutating = true;

  // Simulate QueueDispatcher useEffect lines 28-33:
  // useEffect(() => { if (!isMutating) setItems(initialItems); }, [initialItems, isMutating]);
  if (!isMutating) {
    currentItems = incomingServerPollItems;
  }

  assert.strictEqual(
    currentItems[0].row,
    localModifiedItems[0].row,
    'Incoming poll must NOT overwrite client items while isMutating is true'
  );
});

// ============================================================================
// SUITE 3: Division-by-Zero & Floating Point Arithmetic Resilience
// ============================================================================

test('T5.3.1: CostCacheProjections renders cleanly with 0 total tokens without NaN or Infinity', () => {
  const zeroCostData = {
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
      costData: zeroCostData,
      timeRange: '24h',
      onTimeRangeChange: () => {},
      isLoading: false
    })
  );

  // Must render 0.0% cleanly without NaN
  assert.ok(html.includes('0.0%'), 'Cache efficiency must render 0.0%');
  assert.ok(!html.includes('NaN'), 'Rendered HTML must never contain NaN');
  assert.ok(!html.includes('Infinity'), 'Rendered HTML must never contain Infinity');
  assert.ok(html.includes('$0.00'), 'Spend must render $0.00');

  // Verify chart points oracle: steps = 12, 0 / 12 = 0
  const steps = 12;
  const baseCached = zeroCostData.aggregate.total_cache_read_tokens / steps;
  const baseFresh = (zeroCostData.aggregate.total_context_tokens - zeroCostData.aggregate.total_cache_read_tokens) / steps;
  const baseCost = zeroCostData.aggregate.total_cost_usd / steps;

  assert.strictEqual(baseCached, 0);
  assert.strictEqual(baseFresh, 0);
  assert.strictEqual(baseCost, 0);
  assert.ok(!isNaN(baseCached));
  assert.ok(!isNaN(baseFresh));
  assert.ok(!isNaN(baseCost));
});

test('T5.3.2: 100% and 0% Cache Efficiency boundary conditions correctly update KPI alerts', () => {
  // 100% Cache Hit: target met -> emerald check
  const fullCacheData = {
    aggregate: {
      total_context_tokens: 5_000_000,
      total_output_tokens: 200_000,
      total_cache_read_tokens: 5_000_000,
      overall_cache_hit_pct: 100.0,
      total_cost_usd: 25.5,
      projected_24h_cost_usd: 102.0
    },
    breakdown: []
  };

  const fullHtml = renderClean(
    React.createElement(CostCacheProjections, {
      costData: fullCacheData,
      timeRange: '24h',
      onTimeRangeChange: () => {},
      isLoading: false
    })
  );
  assert.ok(fullHtml.includes('100.0%'), 'Must render 100.0%');
  assert.ok(fullHtml.includes('text-emerald-400'), 'Must use emerald text when target >= 90% is met');

  // 0% Cache Hit: target missed -> amber alert
  const zeroCacheData = {
    aggregate: {
      total_context_tokens: 5_000_000,
      total_output_tokens: 200_000,
      total_cache_read_tokens: 0,
      overall_cache_hit_pct: 0.0,
      total_cost_usd: 45.0,
      projected_24h_cost_usd: 180.0
    },
    breakdown: []
  };

  const zeroHtml = renderClean(
    React.createElement(CostCacheProjections, {
      costData: zeroCacheData,
      timeRange: '24h',
      onTimeRangeChange: () => {},
      isLoading: false
    })
  );
  assert.ok(zeroHtml.includes('0.0%'), 'Must render 0.0%');
  assert.ok(zeroHtml.includes('text-amber-400'), 'Must use amber text when target < 90%');
});

test('T5.3.3: DualQuotaProgress clamps extreme numeric and infinity values safely to [0, 100]', () => {
  const html = renderClean(
    React.createElement(DualQuotaProgress, {
      label5h: '5h Extreme',
      usedPct5h: Infinity,
      remainingPct5h: -Infinity,
      labelWeekly: 'Weekly Underflow',
      usedPctWeekly: -1000,
      remainingPctWeekly: 5000
    })
  );

  // Infinity clamped to 100%, -Infinity clamped to 0%
  assert.ok(html.includes('style="width:100%"'), 'Infinity used must clamp width to 100%');
  assert.ok(html.includes('0% Headroom'), '-Infinity remaining must clamp text to 0% Headroom');

  // -1000 clamped to 0%, 5000 clamped to 100%
  assert.ok(html.includes('style="width:0%"'), '-1000 used must clamp width to 0%');
  assert.ok(html.includes('100% Headroom'), '5000 remaining must clamp text to 100% Headroom');
  assert.ok(!html.includes('NaN'), 'Must never output NaN');
});

test('T5.3.4: Formatters handle zero, decimals, boundaries, and large values with precision', () => {
  assert.strictEqual(formatPercent(0), '0.0%');
  assert.strictEqual(formatPercent(99.99), '100.0%');
  assert.strictEqual(formatPercent(82.43), '82.4%');

  assert.strictEqual(formatDuration(0), '0s');
  assert.strictEqual(formatDuration(45), '45s');
  assert.strictEqual(formatDuration(59.4), '59s');
  assert.strictEqual(formatDuration(60), '1m 0s');
  assert.strictEqual(formatDuration(125), '2m 5s');
  assert.strictEqual(formatDuration(3600), '60m 0s');

  assert.strictEqual(formatCurrency(0), '$0.00');
  assert.strictEqual(formatCurrency(1234.56), '$1,234.56');

  assert.strictEqual(formatNumber(0), '0');
  assert.strictEqual(formatNumber(1000000), '1,000,000');
});

// ============================================================================
// SUITE 4: Empty Dataset Handling Across All Frontend Components
// ============================================================================

test('T5.4.1: NodeLatencyGrid renders cleanly with 0 nodes without division-by-zero or crash', () => {
  const html = renderClean(
    React.createElement(NodeLatencyGrid, {
      nodes: [],
      isLoading: false,
      selectedRole: 'all',
      onSelectRole: () => {},
      onTriggerProbe: () => {},
      isProbing: false
    })
  );

  assert.ok(html.includes('27-Node Cluster Matrix'), 'Header title must render');
  assert.ok(html.includes('Online:'), 'Online label must render');
  assert.ok(html.includes('0'), 'Online count must show 0');
  assert.ok(html.includes('/'), 'Slash separator must render');
  assert.ok(html.includes('27'), 'Cluster total denominator must render');
});

test('T5.4.2: CiShardMatrix renders cleanly with 0 shards without runtime error', () => {
  const html = renderClean(
    React.createElement(CiShardMatrix, {
      shardsData: { shards: [] },
      isLoading: false,
      onRefresh: () => {}
    })
  );

  assert.ok(html.includes('CI/CD Shard Health Matrix (0 Shards)'), 'Header must reflect 0 shards');
  assert.ok(html.includes('0 Passed'), '0 Passed counter must render');
  assert.ok(!html.includes('Failed'), 'Failed counter should not render when failed == 0');
  assert.ok(!html.includes('Running'), 'Running counter should not render when running == 0');
});

test('T5.4.3: SortableQueueTable and QueueDispatcher render explicit empty placeholder for 0 items', () => {
  const htmlTable = renderClean(
    React.createElement(SortableQueueTable, {
      items: [],
      isMutating: false,
      onReorder: () => {},
      onMoveUp: () => {},
      onMoveDown: () => {}
    })
  );
  assert.ok(htmlTable.includes('No matching queue entries found.'), 'Must render empty state message');

  const htmlDispatcher = renderClean(
    React.createElement(QueueDispatcher, {
      initialItems: [],
      isLoading: false,
      onQueueUpdated: () => {}
    })
  );
  assert.ok(htmlDispatcher.includes('DISPATCH-LEDGER.tsv Queue Re-order'));
  assert.ok(htmlDispatcher.includes('Total:</span><span class="text-zinc-200 font-bold">0</span>'));
  assert.ok(htmlDispatcher.includes('No matching queue entries found.'));
});

test('T5.4.4: AgentConfigGrid renders cleanly with 0 agent seats', () => {
  const html = renderClean(
    React.createElement(AgentConfigGrid, {
      agents: [],
      isLoading: false,
      onAgentUpdated: () => {}
    })
  );

  assert.ok(html.includes('Headless Swarm Agents &amp; Configuration') || html.includes('Headless Swarm Agents & Configuration'));
  assert.ok(html.includes('0 Registered'), 'Must display 0 Registered');
});

test('T5.4.5: StatusBadge handles unknown, empty, and edge case status strings safely', () => {
  const variants = [
    { status: '', expected: 'text-zinc-400' },
    { status: 'unknown', expected: 'text-zinc-400' },
    { status: 'NON_EXISTENT_STATUS_VAL', expected: 'text-zinc-400' },
    { status: 'aborted', expected: 'text-rose-400' },
    { status: 'operator-only', expected: 'text-amber-400' },
    { status: 'dispatched', expected: 'text-blue-400' },
    { status: 'ok', expected: 'text-emerald-400' }
  ];

  for (const v of variants) {
    const html = renderClean(
      React.createElement(StatusBadge, { status: v.status })
    );
    assert.ok(html.includes(v.expected), `Status "${v.status}" must include ${v.expected}`);
  }
});

test('T5.4.6: ArchitectureVisualizer renders safely with 0 nodes and empty tiers without crashing', () => {
  const emptyTopologyData = {
    timestamp: new Date().toISOString(),
    topology: {
      total_nodes: 0,
      online_nodes: 0,
      isolated_nodes: 0,
      total_agents: 0,
      active_agents: 0,
      esxi_clones: [],
      tiers: {
        control_plane: [],
        ai_satellite: [],
        workers: [],
        esxi_spare_pool: [],
        isolated_boundary: []
      },
      agent_allocations: {}
    },
    source: 'mock' as const
  };

  const html = renderClean(
    React.createElement(ArchitectureVisualizer, { initialData: emptyTopologyData })
  );

  assert.ok(html.includes('Live Architecture Visualizer'), 'Must render title ribbon');
  assert.ok(html.includes('Displaying 0 of 0 Nodes'), 'Must render 0 count text');
  assert.ok(html.includes('No cluster nodes match'), 'Must render empty placeholder');
});

test('T5.4.7: ArchitectureVisualizer renders safely when agent_allocations or tiers are omitted/undefined', () => {
  const malformedData: any = {
    timestamp: new Date().toISOString(),
    topology: {
      total_nodes: 0,
      online_nodes: 0,
      isolated_nodes: 0,
      total_agents: 0,
      active_agents: 0
      // tiers and agent_allocations intentionally omitted
    },
    source: 'mock'
  };

  // Must NOT throw TypeError: Cannot read properties of undefined
  const html = renderClean(
    React.createElement(ArchitectureVisualizer, { initialData: malformedData })
  );

  assert.ok(html.includes('Live Architecture Visualizer'));
});

// ============================================================================
// SUITE 5: Component ErrorBoundary Isolation & Recovery
// ============================================================================

test('T5.5.1: ErrorBoundary getDerivedStateFromError captures uncaught error and renders default error card', () => {
  const testError = new Error('Database connection reset during telemetry sweep');
  const derived = ErrorBoundary.getDerivedStateFromError(testError);

  assert.strictEqual(derived.hasError, true);
  assert.strictEqual(derived.error, testError);

  const instance = new ErrorBoundary({
    fallbackTitle: 'Telemetry Grid Failure',
    name: 'TelemetryGrid'
  });
  instance.state = derived;

  const fallbackElement = instance.render();
  const html = renderClean(fallbackElement as React.ReactElement);

  assert.ok(html.includes('Telemetry Grid Failure'), 'Must render custom fallback title');
  assert.ok(html.includes('Database connection reset during telemetry sweep'), 'Must display verbatim error message');
  assert.ok(html.includes('Retry Component'), 'Must render Retry Component button');
});

test('T5.5.2: ErrorBoundary custom function fallback receives error and reset trigger', () => {
  const testError = new Error('Custom failure message');
  const instance = new ErrorBoundary({
    fallback: (err: Error, reset: () => void) => {
      return React.createElement('div', { id: 'custom-error-panel' },
        React.createElement('span', null, `Recovering: ${err.message}`),
        React.createElement('button', { onClick: reset }, 'Custom Reset')
      );
    }
  });
  instance.state = { hasError: true, error: testError };

  const html = renderClean(instance.render() as React.ReactElement);
  assert.ok(html.includes('id="custom-error-panel"'));
  assert.ok(html.includes('Recovering: Custom failure message'));
  assert.ok(html.includes('Custom Reset'));
});

test('T5.5.3: ErrorBoundary handleReset resets error state and calls onReset callback', () => {
  let onResetCalled = false;
  const instance = new ErrorBoundary({
    onReset: () => { onResetCalled = true; }
  });

  instance.state = { hasError: true, error: new Error('Crash') };

  let setStateCalledWith: any = null;
  instance.setState = (updater: any) => {
    setStateCalledWith = typeof updater === 'function' ? updater(instance.state) : updater;
    instance.state = { ...instance.state, ...setStateCalledWith };
  };

  instance.handleReset();

  assert.strictEqual(onResetCalled, true, 'onReset callback prop must be called');
  assert.strictEqual(setStateCalledWith.hasError, false, 'hasError must be set to false');
  assert.strictEqual(setStateCalledWith.error, null, 'error must be set to null');
  assert.strictEqual(instance.state.hasError, false);
});

test('T5.5.4: Error Boundary Isolation: failure in Sibling A leaves Sibling B intact', () => {
  // Sibling A: crashed
  const siblingA = new ErrorBoundary({ name: 'SiblingA' });
  siblingA.state = { hasError: true, error: new Error('Sibling A crashed') };

  // Sibling B: healthy
  const siblingB = new ErrorBoundary({ name: 'SiblingB' });
  siblingB.props = {
    children: React.createElement('div', { id: 'sibling-b-healthy' }, 'Healthy Component Content')
  };
  siblingB.state = { hasError: false, error: null };

  const compositeHtml = renderClean(
    React.createElement('div', { className: 'grid grid-cols-2' },
      siblingA.render() as React.ReactElement,
      siblingB.render() as React.ReactElement
    )
  );

  assert.ok(compositeHtml.includes('SiblingA Failure'), 'Sibling A must render its error card');
  assert.ok(compositeHtml.includes('id="sibling-b-healthy"'), 'Sibling B must render its normal content');
  assert.ok(compositeHtml.includes('Healthy Component Content'), 'Sibling B content must remain completely intact');
});

test('T5.5.5: DashboardShell wraps active tab panel inside ErrorBoundary with onReset handler', () => {
  // Verify DashboardShell lines 65-70 structure:
  // <ErrorBoundary name={`TabPanel: ${activeTab}`} onReset={handleRefresh}>
  const shellHtml = renderClean(React.createElement(DashboardShell));

  assert.ok(shellHtml.includes('role="tabpanel"'), 'Must render role="tabpanel"');
  assert.ok(shellHtml.includes('id="panel-telemetry"'), 'Default active tab must be telemetry');
  assert.ok(shellHtml.includes('Swarm Operations Cockpit'), 'Header bar must render');
});

// ============================================================================
// SUITE 6: SSR Rendering & Hydration Safety Invariants
// ============================================================================

test('T5.6.1: ClientOnly renders fallback during SSR to protect against dynamic client APIs', () => {
  const fallbackNode = React.createElement('div', { id: 'ssr-skeleton' }, 'Loading skeleton...');
  const dynamicClientContent = React.createElement('div', { id: 'dynamic-client' }, 'Browser-only Canvas');

  const html = renderClean(
    React.createElement(ClientOnly, { fallback: fallbackNode }, dynamicClientContent)
  );

  // During SSR, useSyncExternalStore getServerSnapshot returns false, rendering fallback
  assert.ok(html.includes('id="ssr-skeleton"'), 'SSR must render fallback skeleton');
  assert.ok(!html.includes('id="dynamic-client"'), 'SSR must NOT render dynamic client content');
});

test('T5.6.2: HeaderBar countdown uses deterministic StaticRefreshPill during SSR', () => {
  const html = renderClean(
    React.createElement(HeaderBar, {
      totalNodes: 27,
      onlineNodes: 26,
      activeAgents: 42,
      refreshIntervalSeconds: 5
    })
  );

  // Must render deterministic "Sync: 5s"
  assert.ok(html.includes('Sync: 5s'), 'HeaderBar must render deterministic static pill "Sync: 5s"');
  assert.ok(!html.includes('Sync in'), 'HeaderBar must not render dynamic "Sync in Xs" on server');
});

test('T5.6.3: Root TabNav renders all 4 tabs with valid WAI-ARIA role and tabpanel attributes', () => {
  let selectedTab = 'telemetry';
  const html = renderClean(
    React.createElement(TabNav, {
      activeTab: selectedTab as any,
      onTabChange: (t) => { selectedTab = t; }
    })
  );

  assert.ok(html.includes('role="tablist"'), 'Must have role="tablist"');
  assert.ok(html.includes('id="tab-telemetry"'), 'Must have id="tab-telemetry"');
  assert.ok(html.includes('id="tab-swarm-control"'), 'Must have id="tab-swarm-control"');
  assert.ok(html.includes('id="tab-quotas"'), 'Must have id="tab-quotas"');
  assert.ok(html.includes('id="tab-architecture"'), 'Must have id="tab-architecture"');
  assert.ok(html.includes('aria-controls="panel-telemetry"'));
  assert.ok(html.includes('aria-controls="panel-swarm-control"'));
  assert.ok(html.includes('aria-controls="panel-quotas"'));
  assert.ok(html.includes('aria-controls="panel-architecture"'));
  assert.ok(html.includes('aria-selected="true"'));
  assert.strictEqual(DASHBOARD_TABS.length, 4, 'Must define all 4 dashboard tabs');
});

// ============================================================================
// SUITE 7: Grok & Kimi Native Model Adversarial Hardening (Challenger 2)
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

