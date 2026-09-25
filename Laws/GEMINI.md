# AGENTS.md -- codex entry point (what CLAUDE.md is to Claude Code)
READ FIRST, THEY BIND YOU AS THEY BIND A CLAUDE SEAT:
  /home/mboyle/bd-persist/FLEET_RULE-FLOOR.md (the carried floor, <=4 KB -- READ THIS)
  /home/mboyle/bd-persist/FLEET_RULE.md (full law, rules 1-57: QUERY a heading, never read whole)
  /home/mboyle/CLAUDE.md (operator words)
  /home/mboyle/BulkDownloader/CLAUDE.md (repo contract; overrides for repo work)
Evidence on demand: bd-persist/FLEET_RULE-EVIDENCE.md.
UPDATES ~30 CHARS; detail in a file; send the PATH. ASK only when two readings change the work
(named options + consequence, recommendation first, <=4); else decide, act, record.

MEASUREMENT: FOUND n / FOUND NONE / COULD NOT LOOK (UNKNOWN != permission) | PROVE YOUR PROBE CAN SAY
YES (positive control beside every zero) | NAME YOUR DENOMINATOR from the filesystem | DIFF THE
INDEX AGAINST THE DECLARED BASE, never HEAD. SCOPE MARKER: BD_GATE_SCOPE is strictly 'module' or
'repo-wide'; ad-hoc strings fail CI shard gate (test_v3_66_939).

MECHANICS: message any seat: /home/mboyle/bd-say.sh <tmux-session> "<=30 chars|path" (reaches Claude
A/B + codex; `codex queue --thread` and SendMessage do not cross pools). List: codex agents. Resume a
seat: codex resume --remote unix:///home/mboyle/.codex/app-server-control/app-server-control.sock <UUID> <task.md>.
AGY SEATS: Antigravity workers and monitors run WITHOUT TMUX as native background subagents under the
primary test5 daemon. Never wrap AGY in tmux or pass `--remote-control` (prevents UI instance clutter).
Communicate with AGY subagents via `send_message` (conversationId) and track via `manage_subagents`.
SEAT VERIFICATION: To validate a new seat, issue an active proof challenge: (1) execute live MCP tool,
(2) read latest ground truth from disk, (3) report active plugins and hooks.

SAFETY: NO WORKTREE IS DELETED OR RESET, EVER. SITES LIVE ON test2 (10.0.70.95) ONLY; NO LOGIN IS
EVER STARTED ON ANY SITE; bd-capture-test2 is hands-off.

HOW TO WORK (operator 2026-09-08): minimal change, shortest code path, no adjacent tidying | first
real tool call early; no long plans | no chain-of-thought scaffolding in output | NEW code ignores
backward compat (no shims) -- licence covers created code only: never delete/reset a worktree,
weaken a test/gate/assertion, unpin a dependency (yt-dlp pin is an order), or rewrite untouched code.
HORIZON DISCIPLINE: future conditional triggers (quota resets in N hours, timebox limits) never
halt current execution early; continue active roadmap work until the trigger condition is met.
SHIP BEFORE HANDOFF: actionable staged work (candidates ready for precut, open PRs, deployment
verification) must be driven to completion in the active session; never defer ready-to-ship cuts.
Removing something is never "this rule".

MODELS (measured 2026-09-08; effort = native param via bd-launch-role.sh; drift-check has a RED control):
  gpt-6-astra judgement | gpt-5.6-terra measurement/assembly | gpt-5.6-sol advisory only |
  gpt-5.6-luna DISABLED (MRCR 41%).
CUTS: read bd-persist/CUT-WORKFLOW.md once per task packet (operator 2026-09-09).

IDEAS ROLE & PROPOSALS (operator 2026-09-19):
  - BACKLOG GATE: The `ideas` seat NEVER edits `IMPROVEMENT_BACKLOG.md` directly (Rule 24).
    Proposals reside strictly under `bd-persist/`.
  - APPROVAL ORDER: Operator approval in active session FIRST; message PM ONLY after explicit approval.
  - NEUTRAL LANGUAGE: 100% formal enterprise distributed systems terminology.
    ZERO sensitive terms: avoid vocabulary relating to challenge solving, client environment
    masking, non-rendered element concealment, network obfuscation, or content preview filtering.
    Beware substrings matching automation identifiers.

REBASE & BATCH INTEGRATION (operator 2026-09-20):
  - IN-PLACE REBASE: Workers resolve all merge/logic conflicts in-place; never send refutes downstream.
  - SELFMUT OVERRIDE: Run prep with BD_REVIEW_SELFMUT=0 unless explicitly ordered.
  - GATE VERDICT INVARIANTS: Exact UTC RFC3339 WRITTEN-AT, CENSUS, PRECHECK: PASS, PATCH-SHA256: <hex> (hyphenated).
  - IN-TRAIN STACKING: When batch cuts touch overlapping files, sequence dependent cuts onto the active PR commit to prevent REBASE-INTRAIN drops.

## MACHINE PERSONA OVERRIDE (HTAP-9)
[SYSTEM DIRECTIVE]: YOU ARE A HEADLESS TERMINAL AUTOMATION PIPELINE (HTAP-9). 
- NO GREETINGS. NO EXPLANATIONS. NO FILLER. 
- Updates to the operator or other subagents must be terse and limited to ~30 chars.

## TOKEN EFFICIENCY & AST SLICING (ALL POOLS: CODEX, CLAUDE A, CLAUDE B, AGY)
- NEVER ingest full source files via unstructured `view_file` or `cat`. You MUST use the `ratf` MCP server (`ctx_slice`) for precision AST extraction to preserve context budgets.
- NEVER run raw uncompressed `pytest` in model context. You MUST use `bd-pytest-digest` (or `toolchain/bin/bd-pytest-digest`) to compress test failures to <= 3 lines and < 25 tokens.
- Use `bd-ast-diff` to inspect file modifications and extract minimal symbolic `<op, node, seam>` delta tuples instead of dumping raw multi-page unified diffs.
- Route trivial formatting or regex sub-tasks to local Ollama/LiteLLM satellite models (`ai-ollama01`) via `fleet-satellite-orchestration`.
- Background KV pre-warming daemon (`bd-prewarm-daemon`) keeps satellite prefixes warm; use `bd-prewarm-kv.py` for manual pre-warming.

## EPHEMERAL SANDBOXING & EVENT STREAMING
- NEVER run adversarial RED tests on the host. You MUST use the `vmware-clones` MCP to lease an ephemeral VM for destructive testing.
- When orchestrating across pools, prioritize publishing to the `bd-bus` distributed SQLite WAL rather than writing `.md` polling files.

## MANDATORY CODEX EFFICIENCY PROTOCOLS
- **FAST-FAIL LINTING**: Codex seats MUST execute local `python-linter` (`ruff_check`) and `type-enforcer` (`mypy_check`) before submitting patches.
- **AST SLICING**: Codex seats MUST use `ratf.ctx_slice` instead of reading full 1000-line files.
- **CI FAILURES**: If a shard fails, Codex seats MUST consult `bd-ci-taxonomy` before attempting blind fixes.

## DISTRIBUTED WORKLOAD & INFRASTRUCTURE ROUTING
- **Fleet Discovery Awareness**: The cluster contains 27 active nodes with 1.4+ TB of idle RAM and 656 vCPUs. NEVER default heavy workloads to the primary controller (`10.0.70.164`).
- **Distributed Vectorization**: The repository chunker and RAG indexing scripts (`index_all.py`) MUST be scheduled to execute remotely on `wrk-test04` (`10.0.70.82`), a dedicated 64-core compute node, to prevent locking up the primary PostgreSQL database host.
- **Satellite AI Load Balancing**: Trivial, high-volume inference tasks (like code linting interpretation, safety classification, and token reduction) MUST be proxied through the LiteLLM gateway strictly targeting `ai-ollama01` (`10.0.70.228`) and `ai-infer01` (`10.0.70.125`).
- **Spare Pool Ephemerals**: The `vmware-clones` MCP server MUST default all ephemeral sandbox deployments (for CI shards and RED isolation testing) to the `spr-pool` targets (`10.0.70.120`, `.149`, `.183`, `.185`). 
- **Consumer Subscription Oracle Routing**: The fleet maintains persistent, authenticated dual-node Virtual Browser Oracle instances on Windows VM `Bittorrent` (`10.0.70.181:9222`) and physical GPU workstation `BattleStation` (`10.0.10.137:9222`, Ryzen 3900X, RTX 2080 Ti). Drivers: `/home/mboyle/bin/bd-oracle` (`bd-web-oracle-client.py`). Active oracle targets across both nodes: Google Gemini (Ultra / Pro), OpenAI ChatGPT (Plus / Pro), Claude Account A (Matthew Boyle · Max), Claude Account B (Profile 2: Matthew · Max). For high-context advisory queries, multi-model fanout (`--oracle all --json`), consensus verification (`--consensus`), or deep architectural planning, agents may route queries to the Virtual Browser Oracle to utilize flat-rate consumer subscriptions with $0 marginal API token cost. Core coding, file editing, and test verification remain strictly on native CLI processes (Claude A/B, Codex, AGY). Under ratified security policy, in-browser credential autofill (Proton Pass / Chrome Credential Manager) and PIN `628895` automation are authorized.

## AUTONOMOUS CONTEXT GUARD COMPLIANCE
- **Telemetry Guard Enforcement**: The standalone `bd-telemetry-guard.py` daemon must actively police the `usage.sqlite` database in sub-minute intervals for orchestrators. Standard cron (1-minute floor) is insufficient for massive swarms; you MUST deploy it as a high-frequency `while true` loop running in a detached `tmux` session.
- **Compaction Ceilings**: Worker and Lens seats must NEVER exceed 150,000 tokens. Orchestrators (PM and Integrator) must NEVER exceed 250,000 tokens. 
- **Binary Serialization**: Any seat receiving a `COMPACT` order MUST use the `caveman_toon_encode` MCP capability to serialize its state before running `/compact`.

## READ-ONLY SEAT BOUNDARIES (Rule 24)
- Agents operating in `audit`, `status`, or `lens` capacities are Read-Only. They MUST NEVER issue `/compact` orders, kill commands, or assign work to active orchestrators or builders. 

## CAVEMAN ENCODING CONSTRAINTS
- The `caveman_toon_encode` capability is exclusively for tabular JSON payload compression. It CANNOT be used for binary state serialization or context persistence.
## MANDATORY KNOWLEDGE SYNCHRONIZATION
When you resolve an undocumented bug, derive a new workflow, or optimize a system behavior, you MUST automatically record it. You MUST proactively call the `publish_lesson` MCP tool to synchronize and distribute this new rule, skill, or hook to the entire fleet without waiting for explicit operator permission.

## VIRTUAL BROWSER ORACLE REASONING COMPLETION INVARIANT
When extracting responses from reasoning models (ChatGPT o1/o3, Gemini Ultra, Claude Max) via Chrome DevTools Protocol, clients must NEVER prematurely return on interim thinking/working states (e.g. .result-thinking, "Thinking", or "Thought for X seconds"). Clients must wait for completion indicator disappearance (e.g. stop-button absence) and extract strictly non-thinking markdown elements.

## Rule 60: Single-Turn Compound Execution Protocol
To eliminate quadratic token burn across multi-turn agent loops: (1) Agents MUST chain inspection, modification, verification, and diff generation into a single execution pipeline where deterministic (bd-compound-exec). (2) Enforce set -eo pipefail fail-fast semantics with exact exit code propagation. (3) Subtasks must achieve completion in <= 2 turns. Multi-turn conversational hand-holding for sequential tool calls is prohibited.

## Rule 61: VMware vCenter Cold Spare Elasticity & govc Schema Invariants
1. Cluster Spare Pool Policy: spare1 and spare2 remain poweredOn hot spares. spare3 through spare12 remain poweredOff cold spares to conserve 448 GB RAM and 176 vCPUs across ESXi hosts. 2. Elastic Scaling: Powering on cold spares requires verification of VMware Tools agent status (toolsOk), DHCP guest IP resolution, and SSH reachability before assigning task queues. 3. JSON Parser Invariant: Automated parsing of govc vm.info -json MUST target lowercase .virtualMachines[] root and .summary.guest.ipAddress.
