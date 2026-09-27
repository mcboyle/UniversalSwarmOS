# Heterogeneous Swarm Architecture Dashboard: E2E Test Infrastructure Specification

**Document Version**: 1.0.0  
**Author**: `e2e_test_writer_1` (E2E Test Engineer / QA Specialist)  
**Status**: ACTIVE  
**Path**: `/home/mboyle/teamwork_projects/heterogeneous_swarm_dashboard/TEST_INFRA.md`  

---

## 1. Testing Philosophy & Methodology

The Heterogeneous Swarm Architecture Dashboard orchestrates and visualizes mission-critical distributed fleet operations across 27 cluster nodes, multi-model LLM API quotas (Claude, Codex, AGY Gemini, AGY Claude/GPT), real-time CI/CD shard matrices, and live task dispatch queues (`DISPATCH-LEDGER.tsv`).

To guarantee operational resilience, our testing infrastructure adheres to the following principles:

1. **Opaque-Box Verification**: Tests validate observable system behavior, HTTP contracts, POSIX filesystem invariants, and database concurrency guarantees from the outside. Tests do not rely on internal implementation scaffolding or white-box shortcuts.
2. **Authoritative Ground-Truth Oracles**: Every test assertion is derived from verified ground-truth specifications:
   - Token accounting: `usage.sqlite` schema and SQLite WAL concurrency semantics.
   - Task dispatch: `DISPATCH-LEDGER.tsv` 5-column tab-separated grammar and atomic `rename(2)` invariants.
   - API Quota headroom: `POOL_STATE.tsv` 5-hour percentage used vs AGY 5-hour percentage remaining.
   - Cluster topology: `/etc/hosts` 27-node mapping, with strictly zero probing of `test2` (`10.0.70.95`).
   - CI/CD shard taxonomy: 42 matrix shards and `bd-ci-taxonomy` signatures (`BD-CI-01` through `BD-CI-09`).
3. **No Facade Testing**: Every test exercises genuine multi-threaded or multi-process concurrency, file I/O, network parsing, or contract verification. Tests are equipped with positive and negative controls.
4. **Non-Destructive Sandbox Isolation**: Tests must never mutate live operational production stores (`/home/mboyle/bd-persist/DISPATCH-LEDGER.tsv` or `/home/mboyle/bd-persist/accounting/usage.sqlite`). Tests execute against isolated high-fidelity sandboxes and mirrors with exact schema parity.

---

## 2. Acceptance Criteria Verification Matrix

| AC ID | Acceptance Criterion Statement | Authoritative Source | Verification Target & Mechanism | Pass Condition |
|---|---|---|---|---|
| **AC1** | Application starts cleanly via `npm run dev` / build without compilation or hydration errors. | `ORIGINAL_REQUEST.md:115`, `PROJECT.md:6-15` | Next.js build verification, syntax validation, `ClientOnly` hydration safety check. | Exit code 0, no unhandled hydration warnings or compilation failures. |
| **AC2** | UI renders a dedicated API Quota panel that distinguishes between 5-hour limits and weekly limits for Claude vs Gemini. | `ORIGINAL_REQUEST.md:116`, `PROJECT.md:57-75`, `POOL_STATE.tsv` | `/api/quotas` payload contract & quota calculation engine. | Explicit separation of 5h vs weekly limits, correct percentage semantics (used vs remaining), distinct provider pools. |
| **AC3** | Backend sustains 10 concurrent API read requests to `usage.sqlite` under 15 active writers without `database is locked`. | `ORIGINAL_REQUEST.md:117`, `PROJECT.md:33`, `survey_explorer_be_3` | SQLite WAL mode, `PRAGMA busy_timeout=5000`, `mode=ro` connection URI, exponential backoff retry. | Zero `sqlite3.OperationalError: database is locked` exceptions across >=500 read operations under 15 simultaneous writers. |
| **AC4** | Interactive queue re-ordering successfully modifies ledger file without corrupting active dispatcher reads. | `ORIGINAL_REQUEST.md:118`, `PROJECT.md:34, 77-92`, `bd-dispatch.sh` | Atomic TSV rewrite harness with flock + tempfile + `fsync` + `rename(2)` during active `awk` loop readers. | Zero torn/partial reads (<5 columns or missing lines) across >=1,000 rapid dispatcher polling reads during concurrent reorders. |

---

## 3. Tiered Test Architecture

The test suite is structured into four progressive tiers executed by the master runner:

```text
tests/e2e/
├── run_all_e2e.sh               # Master test runner (executes all tiers, aggregates TAP output, exit 0)
├── tier1_features.test.ts       # Tier 1: Feature Coverage (>=5 test cases per feature for F1..F12)
├── tier2_boundaries.test.ts     # Tier 2: Boundary & Corner Cases (>=5 test cases per feature for F1..F12)
├── tier3_concurrency.test.ts    # Tier 3: Concurrency & Cross-Feature Interactions
└── tier4_workloads.test.ts      # Tier 4: Real-World Swarm Workload Scenarios
```

### Tier 1: Feature Coverage (>=5 Tests per Feature, >=60 Tests Total)
Exhaustive verification of the primary behavior (happy path) for all 12 inventoried features in `PROJECT.md`:
- **F1 (SQLite WAL & Read-Retry Engine)**:
  1. WAL mode verification (`PRAGMA journal_mode = wal`).
  2. Busy timeout enforcement (`PRAGMA busy_timeout >= 5000`).
  3. Read-only connection enforcement (`mode=ro`).
  4. Exponential backoff retry on transient locks.
  5. Telemetry record extraction accuracy from `usage_responses`.
- **F2 (Atomic TSV Queue Mutator)**:
  1. Advisory lock file acquisition (`.lock`).
  2. Temporary file generation on same filesystem mount.
  3. Fsync flush prior to rename.
  4. Atomic rename replacement (`rename(2)`).
  5. Inode replacement verification without truncation.
- **F3 (Backend API Route Handlers)**:
  1. `/api/nodes` returns valid 27-node topology.
  2. `/api/shards` returns 42 matrix shard statuses.
  3. `/api/quotas` returns 4-pool quota structure.
  4. `/api/cost` returns token telemetry and cache efficiency.
  5. `/api/queue` returns ordered dispatch tasks.
- **F4 (Dedicated API Quota Panel)**:
  1. Claude A 5-hour utilization calculation.
  2. Claude B weekly utilization calculation.
  3. AGY Gemini 5-hour vs weekly remaining headroom calculation.
  4. AGY Claude/GPT 5-hour vs weekly remaining headroom calculation.
  5. Codex pool state representation.
- **F5 (Zero-Mismatch Hydration & Layout Shell)**:
  1. Root cockpit layout structure and dark theme class hierarchy.
  2. 3-tab navigation model (Telemetry, Swarm Control, API Quota).
  3. `ClientOnly` hydration wrapper mounting safety.
  4. Mock store fallback when live feeds are cold.
  5. Error boundary encapsulation.
- **F6 (Distributed Node Latency Grid)**:
  1. 27-node cluster mapping verification.
  2. Role classification (`hub`, `ops`, `stg`, `ai`, `wrk-bd`, `wrk-test`, `spr-pool`).
  3. Latency gauge thresholds (<1ms optimal).
  4. Strict blacklisting of `test2` (`10.0.70.95`) from network probing.
  5. Filter by node role functionality.
- **F7 (CI/CD Shard Health Matrix)**:
  1. 42 matrix shards enumerated according to `ci.yml`.
  2. Shard category groupings (Pure-Python, Browser-Provisioned, Node-Provisioned, Postgres).
  3. Duration tracking and status badge assignment.
  4. Diagnostic classification using `bd-ci-taxonomy` codes (`BD-CI-01` to `BD-CI-09`).
  5. Precut gate ledger outcome mapping.
- **F8 (Historical Cost & Prefix Cache Projections)**:
  1. Cached token vs fresh token segregation.
  2. Cache efficiency percentage calculation (`cached / total >= 90%`).
  3. Daily token spend aggregation.
  4. 7-day predictive spend projection trendline.
  5. Model-specific cost weighting (Claude Opus/Sonnet vs GPT vs Gemini).
- **F9 (Interactive Swarm Queue Re-ordering)**:
  1. Pending task prioritization reordering.
  2. Preservation of in-flight (`started`) and historical (`done`) tasks.
  3. Optimistic UI update contract validation.
  4. Up/Down single-step movement validation.
  5. Persistence to TSV ledger with timestamp integrity.
- **F10 (Active Agent Configuration Matrix)**:
  1. Live seat discovery from role state claims.
  2. Model assignment inspection (Astra, Terra, Sol, AGY).
  3. Reasoning effort parameter inspection.
  4. Turn cap enforcement inspection (Rule 58).
  5. Dynamic agent status reflection (`active`, `idle`, `paused`).
- **F11 (End-to-End Test Suite Track)**:
  1. Automated runner execution (`run_all_e2e.sh`).
  2. Clean TAP/diagnostic result reporting.
  3. Zero external test framework dependencies (native Node 22 test runner).
  4. Exit code 0 propagation on 100% pass.
  5. Exit code non-zero propagation on any test failure.
- **F12 (Adversarial Hardening Track)**:
  1. Injected transient database lock handling.
  2. Handling of partial or malformed TSV row inputs.
  3. Network timeout handling on external probes.
  4. Unrecognized CI shard error classification fallback.
  5. Disk full simulation handling during tempfile creation.

---

### Tier 2: Boundary & Corner Cases (>=5 Tests per Feature, >=60 Tests Total)
Systematic stress-testing of operational boundaries, invalid data combinations, extremes, and resource starvation across all 12 features:
- **F1**: Zero-length DB, corrupt DB header, busy timeout exceeded, read during checkpoint, URI query injection.
- **F2**: Empty TSV file, single-line TSV, missing newline at EOF, non-writable target directory, cross-device link handling (`EXDEV`).
- **F3**: Malformed JSON payloads, unknown HTTP methods (PATCH/DELETE), negative limits/offsets, excessive payload sizes (>1MB), empty query params.
- **F4**: 0% quota used, 100% quota exhausted, negative percentages, null resets_at timestamps, missing AGY provider sub-keys.
- **F5**: Null client window object during SSR, unrendered chart dimensions (0x0 container), missing route parameters, deeply nested error boundary triggers.
- **F6**: Unreachable nodes (100% packet loss), node with DNS/hostname resolution failure, blacklisted test2 probe attempt rejection, extreme latency (>10,000ms), 0-node empty config.
- **F7**: Shard with 0 duration, shard with execution timeout (>3600s), unknown shard failure string not in `bd-ci-taxonomy`, Gitea API 500 error response, truncated HARNESS ledger.
- **F8**: 0 tokens total (division by zero guard), 100% cache hit rate (0 fresh tokens), 0% cache hit rate (100% fresh tokens), negative cost inputs, non-chronological timestamps.
- **F9**: Reordering with duplicate task IDs, reordering with empty array, reordering with nonexistent task IDs, reordering while file is read-only, simultaneous reorders with conflicting permutations.
- **F10**: Agent with unrecognized model name, invalid reasoning effort level, turn cap = 0, agent with whitespace-only seat name, missing role-state markdown file.
- **F11**: Test runner handling missing test files, test runner under interrupted SIGINT, test runner under non-standard terminal dimensions, test runner output pipe buffering, test runner running with zero permissions.
- **F12**: High-frequency concurrent locks, Unicode special characters in task brief, CRLF line endings in TSV ledger, corrupted JSON in usage payload, NaN propagation guards in quota metrics.

---

### Tier 3: Concurrency & Cross-Feature Interactions
Multi-threaded and multi-process test scenarios exercising cross-subsystem interactions:
1. **Concurrent SQLite Reads During Bulk Ingest**: 10 parallel reader threads querying `/api/cost` while a writer process executes continuous transactions against `usage.sqlite`.
2. **TSV Queue Re-ordering During Dispatcher Polling**: Multiple processes querying `DISPATCH-LEDGER.tsv` via `awk` at 50Hz while interactive re-ordering operations execute atomic replacements.
3. **Simultaneous Quota Refresh & Usage Ingestion**: Telemetry calculation running concurrently with live `POOL_STATE.tsv` updates.
4. **CI Shard Ingestion During Dashboard Telemetry Polling**: Rapid shard status updates while `/api/shards` and `/api/nodes` are queried simultaneously.
5. **Cross-Feature Race Condition Safety**: Atomic TSV lock contention resolution with timeout fail-safes.

---

### Tier 4: Real-World Swarm Workload Scenarios
Comprehensive end-to-end simulation of an active multi-agent fleet operations session:
1. **15+ Active Swarm Writers Simulation**: 15 background writer threads simulating autonomous agents (Claude A, Claude B, Codex, AGY workers) continuously inserting token usage rows into `usage.sqlite`.
2. **10 Concurrent API Readers**: 10 continuous polling threads requesting telemetry and quota stats at high frequency.
3. **Active Dispatcher Queue Monitoring**: Continuous background loop simulating `bd-dispatch.sh` polling the next eligible pending task from `DISPATCH-LEDGER.tsv`.
4. **Operator Queue Reordering**: Dynamic operator task prioritizations reordering the queue mid-stream.
5. **CI Shard Status Influx**: Simultaneous arrival of 42 CI shard gate results with pass/fail transitions.
6. **Zero-Lock Invariant Check**: Total assertion that across the entire workload, zero `database is locked` errors occur and zero torn/empty reads occur in the dispatch queue.

---

## 4. Test Runners and Execution Protocols

### Master Runner: `tests/e2e/run_all_e2e.sh`
The master automated runner orchestrates all tiers sequentially or concurrently, captures output, formats structured TAP/JUnit summaries, and returns a strict binary exit status (0 = PASS, 1 = FAIL):

```bash
#!/usr/bin/env bash
# Usage:
bash /home/mboyle/teamwork_projects/heterogeneous_swarm_dashboard/tests/e2e/run_all_e2e.sh
```

### Execution Options
- Run individual tier:
  ```bash
  node --test --experimental-strip-types tests/e2e/tier1_features.test.ts
  node --test --experimental-strip-types tests/e2e/tier2_boundaries.test.ts
  node --test --experimental-strip-types tests/e2e/tier3_concurrency.test.ts
  node --test --experimental-strip-types tests/e2e/tier4_workloads.test.ts
  ```
- Run Python/Bash Concurrency Stress Harnesses:
  ```bash
  python3 scripts/test_sqlite_concurrency.py
  bash scripts/test_tsv_atomic_reorder.sh
  ```

---

## 5. Pass/Fail Gates & Publication Criteria

The E2E Test Suite enters `TEST_READY` status when:
1. All Tier 1 feature tests pass (100% pass rate across all 12 features).
2. All Tier 2 boundary tests pass (100% pass rate across edge cases).
3. Tier 3 and Tier 4 concurrency and swarm workload tests sustain zero `database is locked` errors and zero torn TSV reads.
4. All 4 Acceptance Criteria (AC1, AC2, AC3, AC4) are empirically verified and validated.
5. `run_all_e2e.sh` exits cleanly with code 0.
6. `TEST_READY.md` is generated and published at the project root.
