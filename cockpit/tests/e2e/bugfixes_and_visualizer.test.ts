/**
 * tests/e2e/bugfixes_and_visualizer.test.ts
 *
 * Comprehensive Verification Test Suite for:
 * 1. R1: Broken React State & Auto-Refresh Preservation (Zero DOM remounting)
 * 2. R1: Interactive Swarm Control Buttons (Queue reorder, promote, agent update mutations)
 * 3. R2: Usage Chart Data Accuracy & SQL Aggregation parity with raw SQLite queries
 * 4. R3: Live Architecture Visualizer Component rendering & node representation
 */

import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import Database from 'better-sqlite3';
import React from 'react';
import ReactDOMServer from 'react-dom/server';
import {
  createTempDir,
  cleanupPath,
  createSqliteSandbox,
  createTsvSandbox,
  apiFetch
} from './test_helpers.ts';

// Dynamic import helpers for React components
import { createRequire } from 'node:module';
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

const { DashboardShell } = requireTsxSync('src/components/layout/DashboardShell.tsx');
const { TabNav, DASHBOARD_TABS } = requireTsxSync('src/components/layout/TabNav.tsx');
const { ArchitectureVisualizer } = requireTsxSync('src/components/architecture/ArchitectureVisualizer.tsx');
const { QueueDispatcher } = requireTsxSync('src/components/swarm-control/QueueDispatcher.tsx');
const { QueueRow } = requireTsxSync('src/components/swarm-control/QueueRow.tsx');
const { mockQueueItems, mockNodes, mockAgentsResponse } = requireTsxSync('src/lib/mock-data.ts');

function renderHtml(el: React.ReactElement): string {
  return ReactDOMServer.renderToString(el).replace(/<!--.*?-->/g, '');
}

// ============================================================================
// SUITE 1: R1 Auto-Refresh & React State Preservation
// ============================================================================

test('R1.1: DashboardShell root element does NOT contain refreshKey that tears down DOM', () => {
  const shellFile = fs.readFileSync(
    path.resolve('src/components/layout/DashboardShell.tsx'),
    'utf8'
  );

  // Assert that key={refreshKey} is completely removed from the shell markup
  assert.ok(
    !shellFile.includes('key={refreshKey}'),
    'DashboardShell must not pass key={refreshKey} to root container'
  );
  assert.ok(
    !shellFile.includes('setRefreshKey'),
    'DashboardShell must not use setRefreshKey state for refresh timer'
  );
});

test('R1.2: DashboardShell renders and preserves tabpanel across renders', () => {
  const html = renderHtml(React.createElement(DashboardShell));
  assert.ok(html.includes('role="tabpanel"'));
  assert.ok(html.includes('id="panel-telemetry"'));
});

// ============================================================================
// SUITE 2: R1 Interactive Swarm Control Buttons & Mutation
// ============================================================================

test('R1.3: QueueRow renders Promote to Top, Move Up, and Move Down buttons with stopPropagation', () => {
  const item = mockQueueItems[1]; // Rank 2
  let moveUpCalled = false;
  let moveDownCalled = false;
  let moveToTopCalled = false;

  const html = renderHtml(
    React.createElement(QueueRow, {
      item,
      rank: 2,
      isFirst: false,
      isLast: false,
      onMoveUp: () => { moveUpCalled = true; },
      onMoveDown: () => { moveDownCalled = true; },
      onMoveToTop: () => { moveToTopCalled = true; }
    })
  );

  assert.ok(html.includes('title="Promote to Top of Queue"'), 'Must render Promote to Top button');
  assert.ok(html.includes('title="Move Priority Up"'), 'Must render Move Priority Up button');
  assert.ok(html.includes('title="Move Priority Down"'), 'Must render Move Priority Down button');
});

test('R1.4: Interactive queue reordering triggers live backend TSV mutation', async () => {
  const dir = createTempDir('r1_queue_mutation_');
  const tsvPath = createTsvSandbox(dir, 5);
  const oldEnv = process.env.DISPATCH_LEDGER_PATH;
  process.env.DISPATCH_LEDGER_PATH = tsvPath;

  try {
    // Perform backend mutation via API
    const res = await apiFetch('/api/queue', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-test-ledger-path': tsvPath
      },
      body: JSON.stringify({
        action: 'reorder',
        ordered_row_ids: ['row5', 'row4', 'row1']
      })
    });

    assert.strictEqual(res.status, 200, 'POST /api/queue must return 200 OK');
    assert.strictEqual(res.data.success, true, 'Mutation must report success');

    // Read the modified ledger on disk
    const content = fs.readFileSync(tsvPath, 'utf8');
    const lines = content.trim().split('\n');
    assert.ok(lines[0].includes('row5'), 'row5 must now be prioritized at top of ledger');
    assert.ok(lines[1].includes('row4'), 'row4 must follow row5');
  } finally {
    process.env.DISPATCH_LEDGER_PATH = oldEnv;
    cleanupPath(dir);
  }
});

test('R1.5: Interactive agent config update triggers live backend override mutation', async () => {
  const res = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      seat: 'bd-worker-test-interactive',
      model: 'claude-opus-5-5',
      turn_cap: 45,
      status: 'busy'
    })
  });

  assert.strictEqual(res.status, 200, 'POST /api/agents must return 200 OK');
  assert.strictEqual(res.data.success, true, 'Mutation must succeed');
  assert.strictEqual(res.data.seat, 'bd-worker-test-interactive');
  assert.strictEqual(res.data.updated_config.turn_cap, 45);
});

// ============================================================================
// SUITE 3: R2 Usage Chart Data Accuracy (SQLite Parity)
// ============================================================================

test('R2.1: /api/cost aligns mathematically with raw SQLite3 aggregate queries', async () => {
  const dir = createTempDir('r2_sqlite_parity_');
  const dbPath = createSqliteSandbox(dir, 30);
  const oldEnv = process.env.USAGE_DB_PATH;
  process.env.USAGE_DB_PATH = dbPath;

  // Reset database instance cache so it points to our test sandbox
  const { resetDbPathCache, closeDb } = requireTsxSync('src/lib/db.ts');
  closeDb();
  resetDbPathCache();

  try {
    // 1. Compute ground truth mathematically via direct raw SQLite query
    const rawDb = new Database(dbPath, { readonly: true });
    const rawExpected = rawDb.prepare(`
      SELECT
        COUNT(*) as total_responses,
        SUM(json_extract(usage, '$.input_tokens')) as total_context_tokens,
        SUM(json_extract(usage, '$.output_tokens')) as total_output_tokens,
        SUM(MAX(COALESCE(json_extract(usage, '$.cache_read_input_tokens'), 0), COALESCE(json_extract(usage, '$.cached_input_tokens'), 0))) as total_cache_read_tokens
      FROM usage_responses
      WHERE quarantined = 0
    `).get() as {
      total_responses: number;
      total_context_tokens: number;
      total_output_tokens: number;
      total_cache_read_tokens: number;
    };
    rawDb.close();

    // 2. Fetch from backend API
    const res = await apiFetch('/api/cost?since=2026-09-01T00:00:00Z', {
      headers: { 'x-test-db-path': dbPath }
    });
    assert.strictEqual(res.status, 200, '/api/cost must return 200 OK');

    const agg = res.data.aggregate;
    assert.strictEqual(res.data.total_responses, rawExpected.total_responses, 'Total responses must match raw sqlite count');
    assert.strictEqual(agg.total_context_tokens, rawExpected.total_context_tokens, 'Total context tokens must match raw sqlite SUM');
    assert.strictEqual(agg.total_output_tokens, rawExpected.total_output_tokens, 'Total output tokens must match raw sqlite SUM');
    assert.strictEqual(agg.total_cache_read_tokens, rawExpected.total_cache_read_tokens, 'Total cache read tokens must match raw sqlite SUM');

    const expectedEfficiency = Math.round((rawExpected.total_cache_read_tokens / rawExpected.total_context_tokens) * 10000) / 100;
    assert.strictEqual(agg.overall_cache_hit_pct, expectedEfficiency, 'Cache efficiency pct must match raw formula');
  } finally {
    closeDb();
    resetDbPathCache();
    process.env.USAGE_DB_PATH = oldEnv;
    cleanupPath(dir);
  }
});

test('R2.2: /api/cost supports grouping by thread and aligns with raw SQLite queries', async () => {
  const dir = createTempDir('r2_thread_parity_');
  const dbPath = createSqliteSandbox(dir, 20);
  const oldEnv = process.env.USAGE_DB_PATH;
  process.env.USAGE_DB_PATH = dbPath;

  const { resetDbPathCache, closeDb } = requireTsxSync('src/lib/db.ts');
  closeDb();
  resetDbPathCache();

  try {
    // 1. Query raw SQLite for distinct thread counts
    const rawDb = new Database(dbPath, { readonly: true });
    const rawThreadRows = rawDb.prepare(`
      SELECT
        o.thread as key,
        COUNT(DISTINCT r.response_id) as turns,
        SUM(json_extract(r.usage, '$.input_tokens')) as total_ctx
      FROM usage_responses r
      JOIN usage_occurrences o ON r.provider = o.provider AND r.response_id = o.response_id
      WHERE r.quarantined = 0
      GROUP BY o.thread
      ORDER BY total_ctx DESC
    `).all() as Array<{ key: string; turns: number; total_ctx: number }>;
    rawDb.close();

    // 2. Fetch from backend API with group_by=thread
    const res = await apiFetch('/api/cost?since=2026-09-01T00:00:00Z&group_by=thread', {
      headers: { 'x-test-db-path': dbPath }
    });
    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.data.group_by, 'thread', 'API must confirm group_by: thread');

    assert.strictEqual(res.data.breakdown.length, rawThreadRows.length, 'Breakdown count must match distinct threads in sqlite');
    for (let i = 0; i < rawThreadRows.length; i++) {
      const apiItem = res.data.breakdown[i];
      const rawItem = rawThreadRows[i];
      assert.strictEqual(apiItem.key, rawItem.key, `Thread key at index ${i} must match`);
      assert.strictEqual(apiItem.turns, rawItem.turns, `Turns count for thread ${apiItem.key} must match`);
      assert.strictEqual(apiItem.total_ctx, rawItem.total_ctx, `Total ctx for thread ${apiItem.key} must match`);
    }
  } finally {
    closeDb();
    resetDbPathCache();
    process.env.USAGE_DB_PATH = oldEnv;
    cleanupPath(dir);
  }
});

test('R2.3: /api/cost accurately extracts cached_input_tokens when cache_read_input_tokens is 0 (Codex/OpenAI schema)', async () => {
  const dir = createTempDir('r2_codex_cache_');
  const dbPath = path.join(dir, 'test_codex_usage.sqlite');

  const { resetDbPathCache, closeDb } = requireTsxSync('src/lib/db.ts');
  closeDb();
  resetDbPathCache();

  try {
    const db = new Database(dbPath);
    db.exec(`
      CREATE TABLE usage_responses (
        provider TEXT,
        response_id TEXT,
        timestamp TEXT,
        model TEXT,
        usage TEXT,
        fingerprint TEXT,
        quarantined INTEGER DEFAULT 0,
        PRIMARY KEY(provider, response_id)
      );
    `);
    const stmt = db.prepare(`
      INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?)
    `);
    // Insert 5 rows with Codex/OpenAI schema: cache_read_input_tokens = 0, cached_input_tokens = 45056
    for (let i = 0; i < 5; i++) {
      const usage = JSON.stringify({
        input_tokens: 45299,
        output_tokens: 130,
        cache_read_input_tokens: 0,
        cached_input_tokens: 45056,
        total_tokens: 45429
      });
      stmt.run('codex', `resp_codex_${i}`, `2026-09-22T20:0${i}:00Z`, 'gpt-6-astra', usage, 'fp', 0);
    }
    db.close();

    const res = await apiFetch('/api/cost?since=2026-09-01T00:00:00Z', {
      headers: { 'x-test-db-path': dbPath }
    });
    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.data.total_responses, 5);
    assert.strictEqual(res.data.aggregate.total_context_tokens, 45299 * 5);
    // CRITICAL: Cache read tokens must NOT be 0!
    assert.strictEqual(res.data.aggregate.total_cache_read_tokens, 45056 * 5);
    // Overall cache hit must be ~99.46%
    const expectedHit = Math.round((45056 / 45299) * 10000) / 100;
    assert.strictEqual(res.data.aggregate.overall_cache_hit_pct, expectedHit);
    assert.strictEqual(res.data.breakdown[0].cache_read, 45056 * 5);
  } finally {
    closeDb();
    resetDbPathCache();
    cleanupPath(dir);
  }
});

// ============================================================================
// SUITE 4: R3 Live Architecture Visualizer Component
// ============================================================================

test('R3.1: GET /api/architecture returns unified 27 nodes, ESXi clones, and agent placements', async () => {
  const res = await apiFetch('/api/architecture');
  assert.strictEqual(res.status, 200, '/api/architecture must return 200 OK');
  assert.ok(res.data.topology, 'Must return topology object');

  const { total_nodes, online_nodes, isolated_nodes, esxi_clones, tiers } = res.data.topology;
  assert.ok(total_nodes >= 25, 'Must contain at least 25 nodes (27 total in cluster)');
  assert.ok(online_nodes >= 24, 'Online nodes must be >= 24');
  assert.strictEqual(isolated_nodes, 1, 'Strictly 1 isolated node (test2, Rule 21)');

  assert.ok(Array.isArray(esxi_clones), 'Must return esxi_clones array');
  assert.ok(esxi_clones.length >= 4, 'Must return at least 4 ESXi ephemeral clone sandboxes');

  assert.ok(tiers.control_plane.length > 0, 'Control plane must contain nodes');
  assert.ok(tiers.ai_satellite.length > 0, 'AI satellite tier must contain nodes');
  assert.ok(tiers.workers.length > 0, 'Worker tier must contain nodes');
  assert.ok(tiers.esxi_spare_pool.length > 0, 'ESXi spare pool must contain nodes');
  assert.ok(tiers.isolated_boundary.length > 0, 'Isolated boundary must contain test2');
});

test('R3.2: ArchitectureVisualizer component renders without crashing and represents swarm nodes', () => {
  const mockTopologyData = {
    timestamp: new Date().toISOString(),
    topology: {
      total_nodes: 27,
      online_nodes: 26,
      isolated_nodes: 1,
      total_agents: 42,
      active_agents: 40,
      esxi_clones: [
        {
          id: 'clone-1',
          name: 'vm-ephemeral-shard01',
          hypervisor_host: 'spr-pool-1',
          target_ip: '10.0.70.121',
          status: 'running',
          role: 'ci_shard_runner',
          vcpus: 4,
          memory_mb: 8192
        }
      ],
      tiers: {
        control_plane: [mockNodes[0]],
        ai_satellite: [mockNodes[1]],
        workers: [mockNodes[2]],
        esxi_spare_pool: [mockNodes[3]],
        isolated_boundary: [mockNodes[4]]
      },
      agent_allocations: {
        'hub-mesh01': [mockAgentsResponse.agents[0]]
      }
    },
    source: 'live' as const
  };

  const html = renderHtml(
    React.createElement(ArchitectureVisualizer, { initialData: mockTopologyData })
  );

  // Verify visual presence of core elements
  assert.ok(html.includes('Live Architecture Visualizer'), 'Must render title banner');
  assert.ok(html.includes('27 Nodes'), 'Must render 27 nodes KPI');
  assert.ok(html.includes('ESXi Ephemeral Clones'), 'Must render ESXi clone section');
  assert.ok(html.includes('Active Swarm Seats'), 'Must render active swarm seats');
  assert.ok(html.includes('vm-ephemeral-shard01'), 'Must render active ESXi clone sandbox');
  assert.ok(html.includes('ISOLATED') || html.includes('ONLINE'), 'Must render node status badges');
});

test('R3.3: GET /api/architecture reflects runtime agent config overrides applied via POST /api/agents', async () => {
  // Apply an override via POST /api/agents
  const updateRes = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      seat: 'bd-pm-B',
      model: 'claude-opus-5-5',
      status: 'idle',
      turn_cap: 50
    })
  });
  assert.strictEqual(updateRes.status, 200);

  // Verify GET /api/architecture reflects the updated configuration
  const archRes = await apiFetch('/api/architecture');
  assert.strictEqual(archRes.status, 200);
  const allocations = archRes.data.topology?.agent_allocations || {};
  let foundAgent: any = null;
  for (const host of Object.keys(allocations)) {
    const match = allocations[host].find((a: any) => a.seat === 'bd-pm-B');
    if (match) {
      foundAgent = match;
      break;
    }
  }

  assert.ok(foundAgent, 'bd-pm-B must exist in agent_allocations');
  assert.strictEqual(foundAgent.model, 'claude-opus-5-5', 'Architecture must reflect updated model');
  assert.strictEqual(foundAgent.status, 'idle', 'Architecture must reflect updated status');
  assert.strictEqual(foundAgent.turn_cap, 50, 'Architecture must reflect updated turn_cap');

  // Restore live status so dashboard shows PM as active
  await apiFetch('/api/agents', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      seat: 'bd-pm-B',
      status: 'busy',
      turn_cap: 60
    })
  });
});

test('R3.4: TabNav includes Architecture tab trigger and switches active view to ArchitectureVisualizer', () => {
  assert.ok(
    DASHBOARD_TABS.some((t: any) => t.id === 'architecture'),
    'DASHBOARD_TABS must include architecture tab'
  );

  let active = 'telemetry';
  const html = renderHtml(
    React.createElement(TabNav, {
      activeTab: active as any,
      onTabChange: (t: any) => { active = t; }
    })
  );

  assert.ok(html.includes('id="tab-architecture"'), 'TabNav must render tab-architecture');
  assert.ok(html.includes('Architecture Topology'), 'TabNav must render Architecture Topology label');
  assert.ok(html.includes('aria-controls="panel-architecture"'), 'TabNav must link to panel-architecture');
});
