# Project: Cockpit Upgrade (Grok & Kimi Native Integration)

## Architecture
Next.js 14.2 App Router cockpit with React 18, Tailwind CSS, Recharts, and better-sqlite3 WAL query engine.
- Backend API: `src/app/api/*` (`cost`, `quotas`, `agents`, `nodes`, `shards`, `queue`, `architecture`).
- Database: SQLite WAL accounting database (`usage.sqlite`) storing `usage_responses` and `usage_occurrences`.
- Frontend UI: `src/components/*` (`telemetry`, `swarm-control`, `api-quota`, `architecture`, `layout`).
- Test Infrastructure: Node.js native test runner (`node --test --experimental-strip-types`), Python concurrency scripts, Headless Google Chrome (`/usr/bin/google-chrome-stable --headless=new --screenshot`).

## Code Layout & File Boundaries
- M1 Owner (Completed): `src/lib/types.ts`, `src/lib/mock-data.ts`, test drift fixes.
- M2 Owner (Backend Worker - Completed):
  - `src/app/api/cost/route.ts`
  - `src/app/api/quotas/route.ts`
  - `src/lib/swarm-discovery.ts`
  - `scripts/init_test_db.py`
- M3 Owner (Frontend Worker - Completed):
  - `src/components/swarm-control/AgentConfigGrid.tsx`
  - `src/components/api-quota/QuotaComparisonMatrix.tsx`
  - `src/components/api-quota/ApiQuotaView.tsx`
  - `src/components/api-quota/ProviderQuotaCard.tsx`
  - `src/components/telemetry/CostCacheProjections.tsx`
- M4 Owner (E2E Test Writer - Completed):
  - `tests/e2e/grok_kimi_usage.test.ts`
  - `tests/e2e/grok_kimi_api_db.test.ts`
  - `scripts/run_browser_e2e_screenshots.sh`
  - `TEST_READY.md`
- M5 Owner (Verification Panel - Completed):
  - `reviewer_1`, `reviewer_2`, `challenger_1`, `challenger_2`, `auditor_1`

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | F1: Workspace Bootstrap | Sync base source tree to cockpit_upgrade, link node_modules, fix Rule 21 test drift | M1 | Survey Obs 1 & 4 |
| 2 | F2: Domain Type Contracts | Extend AgentSeatConfig ('grok'\|'kimi') and QuotaResponse in types.ts | M1 | Survey Obs 3 |
| 3 | F3: Model Pricing & Aggregation | Add Grok & Kimi to MODEL_RATES in cost/route.ts, verify SQL aggregation math | M2 | Survey Obs 1.3 |
| 4 | F4: Backend Quota API | Expose grok and kimi pool headroom and reset times in quotas/route.ts | M2 | Survey Obs 1.5 |
| 5 | F5: Swarm Agent Discovery | Recognize bd-grok-* and bd-kimi-* seats in swarm-discovery.ts | M2 | Survey Obs 1.4 |
| 6 | F6: Test Fixtures & DB Ingestion | Seed Grok and Kimi usage rows in init_test_db.py and mock-data.ts | M2 | Survey Obs 1.2 |
| 7 | F7: Swarm Control UI Upgrade | Update AgentConfigGrid.tsx (MODELS_BY_TYPE, filters, badges, active status) | M3 | Survey Obs 1.2 |
| 8 | F8: Telemetry Breakdown UI | Verify dynamic rendering of Grok & Kimi in CostCacheProjections.tsx | M3 | Survey Obs 1.2 |
| 9 | F9: Quota Command Center UI | Add Grok & Kimi cards and comparison columns in ApiQuotaView / Matrix | M3 | Survey Obs 1.2 |
| 10 | F10: Unit Aggregation Tests | Unit tests validating token aggregation math and pricing for Grok & Kimi (AC1) | M4 | AC1 |
| 11 | F11: Scripted DB & API Tests | Automated verification of SQLite ingestion and API endpoints for Grok & Kimi (AC2) | M4 | AC2 |
| 12 | F12: Browser E2E & Screenshot Verification | Browser test script + headless Chrome screenshot capture + agent-as-judge (AC3/AC4) | M4 | AC3, AC4 |
| 13 | F13: Full-Stack Verification & Adversarial Hardening | Execute all tests, visual inspection, adversarial coverage, forensic integrity audit | M5 | AC1-AC4, Gate |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Workspace Bootstrap & Contracts | Sync source tree, symlink node_modules, extend types.ts & mock-data.ts, fix Rule 21 drift | none | DONE |
| 2 | M2: Backend Usage Tracking & APIs | Update cost/route.ts rates, quotas/route.ts, swarm-discovery.ts, init_test_db.py | M1 | DONE |
| 3 | M3: Frontend Dashboard UI Upgrade | AgentConfigGrid, ProviderQuotaCard, QuotaComparisonMatrix, ApiQuotaView | M1, M2 | DONE |
| 4 | M4: E2E Test Suite Creation | Design & implement unit tests (AC1), DB/API tests (AC2), Browser E2E runner (AC3/AC4) | M1 | DONE |
| 5 | M5: Full-Stack Verification & Hardening | Run 100% tests, capture & visually inspect screenshots, run forensic integrity audit | M2, M3, M4 | DONE |

## Interface Contracts
### types.ts ↔ APIs & Components
```ts
export interface AgentSeatConfig {
  seat: string;
  role: string;
  type: 'antigravity' | 'claude' | 'codex' | 'grok' | 'kimi';
  host: string;
  pid: number | null;
  claimed_at: string;
  model: string;
  status: 'idle' | 'busy' | 'offline' | 'paused';
  current_cut?: string;
  turn_cap?: number;
  reasoning_effort?: 'none' | 'low' | 'medium' | 'high' | 'native';
}

export interface ProviderStandardQuota {
  name: string;
  state: 'OK' | 'LIMITED' | 'UNKNOWN' | string;
  five_hour_used_pct: number;
  weekly_used_pct: number;
  resets_at: string | null;
  evidence: string;
}

export interface QuotaResponse {
  timestamp: string;
  pools: {
    claude_a: ClaudePoolQuota;
    claude_b: ClaudePoolQuota;
    codex: CodexQuota;
    antigravity: AntigravityQuota;
    grok?: ProviderStandardQuota;
    kimi?: ProviderStandardQuota;
  };
  source?: 'live' | 'mock';
}
```

### Backend Pricing Contract (`MODEL_RATES`)
```ts
'grok-2': { input: 2.0, output: 10.0, cacheRead: 0.20 },
'grok-2-mini': { input: 0.5, output: 2.0, cacheRead: 0.05 },
'grok-beta': { input: 5.0, output: 15.0, cacheRead: 0.50 },
'grok-3': { input: 3.0, output: 15.0, cacheRead: 0.30 },
'kimi-k1.5': { input: 1.0, output: 3.0, cacheRead: 0.15 },
'kimi-latest': { input: 1.0, output: 3.0, cacheRead: 0.15 },
'moonshot-v1-128k': { input: 1.2, output: 3.6, cacheRead: 0.20 },
'moonshot-v1-32k': { input: 1.2, output: 3.6, cacheRead: 0.20 },
'moonshot-v1-8k': { input: 1.2, output: 3.6, cacheRead: 0.20 },
```
