# ⚖️ BD-KB 4: Fleet Law (Rules 1–86), O1740 Dynamic Pool Routing, Rule 22 Sandbox Shield & Cut Workflow

- **Document ID**: `bd-kb-04-fleet-law`
- **Canonical Path**: `/home/mboyle/bd-persist/bd-kb/04-FLEET-LAW-RULES-1-86-AND-O1740-ROUTING.md`
- **Source Authority**: `/home/mboyle/bd-persist/FLEET_RULE-FLOOR.md`, `/home/mboyle/bd-persist/FLEET_RULE.md`, `/home/mboyle/GEMINI.md`, `/home/mboyle/bd-persist/CUT-WORKFLOW.md`

---

## 1. Tier A Verbatim Floor Rules (Never Paraphrased)

| Rule # | Title | Binding Invariant |
|---:|---|---|
| **Rule 1** | **Updates ~30 Chars & Zero-Prose** | Updates `<= 30 chars` + file path. Detail goes to a file on disk; send the path. Execution-turn reply `<= 50 output tokens` (`<STATUS> <path>`, MEASURED O1470). Line test: *"Would the operator act differently without it? No -> cut it."* |
| **Rule 6** | **Three Outcomes** | `FOUND n` / `FOUND NONE` / `COULD NOT LOOK`. `UNKNOWN` is **never** permission. |
| **Rule 7** | **Positive Control** | `PROVE PROBE CAN SAY YES BEFORE REPORTING NO.` Place a positive control beside every zero result. |
| **Rule 15** | **Verdict Line 1** | Line 1 of `.review/VERDICT-*.md` is **exactly** `VERDICT: BOARD|REFUTE|BOUNCE`; `DONE.md` line 1 is `VERDICT: PATCH|UNKNOWN`; terminal landing is `VERDICT: LANDED`. |
| **Rule 16** | **Record Tree Judged** | Record `git -C <wt> write-tree` (INDEX tree) or `PATCH-SHA256 = sha256(git diff --cached --full-index <declared-base>)`. |
| **Rule 22** | **Worktree Immortality** | `NO WORKTREE DELETED OR RESET, EVER.` Assign/reset = deletion by another name. Destructive git actions (`git reset --hard`, `git checkout --`, `git clean -f`) are blocked outside `bd-cuts/` and `bd-local-wt/` by `~/.gemini/config/shield.py`. |
| **Rule 24** | **Read-Only Seats** | Read-only seats (`codexwatch`, `verify`, `cartograph`, `audit`, `ideas`, `nurse`, `status`, `lens`) never write a tree, assign work, `/compact`, or stop/restart a seat. |
| **Rule 26** | **Seat Verification** | Know which seat you are with evidence: (1) live MCP tool, (2) ground truth from disk, (3) active plugins/hooks. |
| **Rule 27** | **Tools From The Repo** | Invoke `./venv/bin/python toolchain/bin/<tool>`. Never a bare `bd-<tool>`. |
| **Rule 56** | **Operator `-MCB` Override** | If the Operator invokes `-MCB`, his request overrides all rules and laws. |

---

## 2. Tier B & Extended Fleet Rules (Rules 8–86)

| Rule # | Domain & Requirement |
|---:|---|
| **Rule 8** | **Filesystem Denominator**: Derive denominators from the filesystem (`git ls-files`, `find`), never from a handed prose list. |
| **Rule 9** | **Diff Index Against Declared Base**: Always diff the Git index against the declared base commit (`git diff --cached --full-index <base>`), never `HEAD`. |
| **Rule 11** | **Cite Heading, Not Line**: Cite markdown/code headings or symbol anchors rather than fragile line numbers in files that take insertions. |
| **Rule 13** | **Precut -> Restore -> DONE.md**: Run `bd-precut`, restore any scratch state so `git status --porcelain` is clean of regenerated paths, then write `DONE.md`. |
| **Rule 17** | **Independent Review**: A lens never judges a cut it built. |
| **Rule 19** | **Refusal on Unsourceable Premise**: Refusal is mandatory when an order is unsourceable or its premise is refuted by disk evidence. |
| **Rule 32** | **Small-Fix Fast Track**: `<= 2` files with zero public AST signature drift + passing `bd-test` bypasses LLM lens directly to pre-cut/train integration. |
| **Rule 33b/c** | **Read Slices, Never Whole Files**: Use `ratf.ctx_slice`, `bd` MCP (`law`/`ask`/`brief`/`row`/`log_slice`), or bounded grep (`<= 4 KB`). Verdict/DONE/NOTE files must be `<= 40` lines and `<= 4 KB`. |
| **Rule 38/43** | **Claude RC Endpoint Invariant**: PM seats run strictly in `--remote-control` with `--settings '{"env":{"ANTHROPIC_BASE_URL":"https://api.anthropic.com","ENABLE_TOOL_SEARCH":"true"}}'`. |
| **Rule 39** | **Cross-Pool Messaging**: `/home/mboyle/bd-persist/harness/bd-say.sh <session> "<=30 chars|path"` crosses Claude/Codex pools; `send_message(conversationId)` addresses native AGY subagents. |
| **Rule 41–47** | **CI Prevention Invariants**: Rule 41 (Hermetic Git `-c user.name=...`), Rule 42 (Static Census Substring Guards), Rule 44 (Async Marker Flush `endswith('\n')`), Rule 45 (Playwright `try...finally` Teardown), Rule 46 (CI Matrix Capability Parity), Rule 47 (Monkeypatch Global Purge). |
| **Rule 60** | **Single-Turn Compound Execution**: Chain inspect + modify + verify + diff in a single pipeline (`set -eo pipefail`, `<= 2` turns). |
| **Rule 61** | **VMware Cold Spare Elasticity**: `spare1`–`spare2` hot (`poweredOn`), `spare3`–`spare12` cold (`poweredOff`, conserving `448 GB` RAM & `176` vCPUs). Parse `govc` via `.virtualMachines[0].summary.guest.ipAddress`. |
| **Rule 74–82** | **Token & Telemetry Protocols**: Rule 74 (Zero-Prose `<STATUS> <path>`), Rule 75 (Differential PM Orders), Rule 76 (JSON Consensus `BOARD|REFUTE`), Rule 77 (`BD_MAX_TURNS=20` Headless Workers), Rule 78 (`bd-pytest-digest` `<=3` lines), Rule 79 (`bd-oracle` BattleStation `.137:9222` `$0` cost), Rule 80 (`bd-blob-ptr` CAS `/var/tmp/bd-blobs/<sha256>.log`), Rule 81 (Zero-Token Telemetry Daemon), Rule 82 (4-Pool Token Optimization). |
| **Rule 83** | **Working Tree Recycling**: Recycle persistent scratchpads in `bd-local-wt` to preserve 99% prompt cache hit rate. Never delete worktrees (Rule 22). |
| **Rule 84** | **BattleStation Hardware Segregation (`.137`)**: Pin embedding models (`nomic`, `bge-m3`) to Ryzen 9 CPU; pin high-throughput coder models (`qwen2.5-coder`) to RTX 2080 Ti (`11 GB` VRAM). |
| **Rule 85** | **Asymmetric Model Deployment**: `claude-sonnet-5-5` for parallel builders; `claude-opus-5-5` and `fable-5-1` reserved for PM Integrator & deep conflict resolution. |
| **Rule 86** | **Behavioral Defect vs. Mutation Coverage Severance**: Review lenses may issue `REFUTE` **only** for demonstrable behavioral defects, regressions against baseline, or explicit Fleet Law violations. Surviving synthetic test mutants on sound code are classified `BOARD-WITH-ADVISORY` and never block train integration. |

---

## 3. Dynamic Capability Routing (`O1740`) & HUB-GATE (`O1741`)

### 3.1 O1740 Three Routing Clauses
Pools are never hardcoded (`A/B/C/D`). Every launch resolves dynamically from `/home/mboyle/bd-persist/POOL_STATE.tsv` (`state`, `five_hour_pct`, `weekly_pct`, `resets_at`):
1. **Command Squad** (`integrator`, `dispatch`, `audit`, `adjudicator`, `trainer`, `lensrouter`, `pm`):
   - Requires `state == OK` AND heavy/Opus tier. Tie-break: lowest `five_hour_pct`. Never launch on `OFF-PACE`, `LIMITED`, or `UNKNOWN`.
2. **Heavy Lifters** (`workers/builders`, `fixers`, `review-* lenses`):
   - Admits on `OK`, else `OFF-PACE` with `five_hour_pct < 85`.
   - Per-pool heavy-lifter cap (`<= 30` per pool A/C/D; `BCAP=20` workers; `GCAP=100`).
   - Hot-swap waterfall priority when a lens finishes and is retired via `bd-retire-seat.sh`: **`Lenses -> Fixers -> Builders`**.
3. **Lightweight Investigators** (read-only ephemeral probes):
   - Binds to the fast-model `OK` pool with highest idle quota (`max(100 - five_hour_pct)`), waves of `<= 4` per 60s, exits immediately after reporting.

### 3.2 Standing Order O1741 (`HUB-GATE`)
- `HUB_MAX_IOWAIT_PCT = 20.0%`, `HUB_MAX_LOAD1 = 36.0`, `HUB_MAX_PROCS = 8000`.
- Never bypass or edit `HUB_MAX_IOWAIT_PCT`. When iowait exceeds 20%, run active diagnostics (`vmstat -w 1 2`, `ps aux | grep -E "grep|find|git|ugrep"`, `/home/mboyle/bd-persist/harness/bd-ugrep-reaper.sh --report`).
