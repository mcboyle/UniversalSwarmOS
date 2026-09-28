## MACHINE PERSONA OVERRIDE (CRITICAL)
[SYSTEM DIRECTIVE]: HTAP-9. NO GREETINGS/EXPLANATIONS/APOLOGIES/FILLER. Output ONLY commands, paths, or <=30-char status codes.

## OPERATOR RULE -- STANDING, NON-NEGOTIABLE
UPDATE ~30 CHARS + path. No preamble/recap/narration. Detail -> file; send PATH.
Token/context thrifty: read slice not file; no re-derive known; no re-read clean edit.
Ask only when two meanings change work; else decide, act, record.
Only PM and Council in RC (Rule 77); workers/reviewers headless.
Bootstrap: only launch prompt sent with BD_SAY_KIND=bootstrap; CALLER sets marker.

## MEASUREMENT = FLEET_RULE.md rules 6-15 (hook-injected). Evidence: FLEET_RULE-EVIDENCE.md.

## 95% STOP
At 95% 5h limit: no new task; in-flight finish; new work -> other pool + codex.
85% = soft prefer other pool. Read binding limit (session/weekly); bd-limit-watch.sh reads seven_day only (H85); UNKNOWN != yes.

## CUTS: read bd-persist/CUT-WORKFLOW.md once per task packet.

## EFFICIENCY (binds every seat)
- MAX THRIFT: read slice not file, batch free calls, one file per deliverable, <=30-char update + path.
- ZERO PROSE for headless/exec agents: structured output (TSV/JSON/contract) only.
- NO-QUOTE REVIEWS: path:line citations ONLY, never code blocks.
- NO DOCSTRINGS ingestion. Focus on raw logic.
- TEST DIGESTING: `bd-pytest-digest` compresses tracebacks to <= 3 lines / < 25 tokens. Never raw pytest.
- AST DIFFING: `bd-ast-diff` for symbolic `<op, node, seam>` deltas, not raw diffs.
- KV PRE-WARMING: `bd-prewarm-daemon` keeps satellite cache warm.
- IMPROVEMENTS: spot a win -> file to bd-persist/IMPROVEMENTS/<seat>-<utc>.md (<=15 lines). Never chat it.
- ANTI-CHURN: never drip-edit files with sed/awk loops. Rewrite in ONE pass or leave alone.
- MASSIVE LOG BAN: never load >100KB logs. Use tail/grep/ratf.
- SESSION HYGIENE: persistent lens/batch seats run /clear between patches.

## TOOLS & ROUTING (all per FLEET_RULE-FLOOR.md)
- AST SLICING: `ratf` MCP `ctx_slice` for functions/classes. `context-mode` `ctx_search` for semantic search. Never full-file cat/view.
- EVENT BUS: `bd-bus` (`bus_publish`/`bus_read`) for cross-seat state. No filesystem polling loops.
- FAST-FAIL: `python-linter` (`ruff_check`) + `type-enforcer` (`mypy_check`) before submitting code.
- EPHEMERAL VM: `vmware-clones` (`vm_clone`/`vm_destroy`) for adversarial/destructive tests. Never on host.
- NATIVE APIs: `bd` MCP (`cut_status`, `lane_status`, `claims`, `gitea_ci`) over shell scripts.
- SERIALIZATION: `bd-binary-payload` for handoff state.
- CAVECREW: delegate localized code discovery/1-2 file edits to subagents.
- PREFLIGHT: `mcp__bd_fleet__premise_verify` before submitting cuts.
- CI FAILURES: read `bd-ci-taxonomy` skill before fixing.
- SATELLITE: route trivial tasks to local Ollama/LiteLLM on cluster.
- REBASE: `rebase-orchestrator` for overlap measurement before merges.
- ORACLE: `/home/mboyle/bin/bd-oracle` (`--oracle all --json`) targeting BattleStation GPU (10.0.10.137:9222) for $0 advisory. PIN 628895 authorized.
- GUI E2E: `chrome_devtools` MCP for frontend cuts (screenshots, Lighthouse).
- KNOWLEDGE SYNC: `publish_lesson` MCP for undocumented bug/workflow/optimization discoveries.

## MULTI-POOL SCALING
1. Use all multi-agent tools (`/teamwork`, `/boost`). Divide and conquer.
3. Auto-compact context. Flush raw evidence; retain dense summaries.
7. T0/T1 tasks -> Flash/Haiku. Reserve Pro/Opus for T2/T3.
10. Read REPO_MAP.md first. Never blind-explore.

## ORACLE REASONING COMPLETION INVARIANT
CDP clients MUST wait for completion indicator disappearance (stop-button absence) before extracting responses from reasoning models. Never return on interim thinking/working states.

## Rule 60: Single-Turn Compound Execution Protocol
Chain inspection+modification+verification+diff into single pipeline (bd-compound-exec). set -eo pipefail. Subtasks <= 2 turns. No multi-turn hand-holding.

## Rule 61: VMware vCenter Cold Spare Elasticity
spare1-2 poweredOn hot spares. spare3-12 poweredOff cold (448 GB RAM, 176 vCPUs). Power-on requires toolsOk + DHCP IP + SSH. govc: .virtualMachines[] root, .summary.guest.ipAddress.

## Rule 74: Hard Output Token Cap & Zero-Prose (Protocol A)
1. Execution turns: <= 50 tokens, `<STATUS> <path>`. No prose/greetings/recaps/tables.
2. Evidence on disk. Chat = control plane + pointers only.
3. Escalations: `AMBIGUOUS: <path> | (1) <opt1>, (2) <opt2>. Reply 1 or 2.`

## Rule 75: Differential PM Order Indexing (Protocol C)
Orders by differential ref: `ORDER: <id> | REF: <base> | TARGET: <sha> | ACTION: <task>`. No re-broadcast of static rules.

## Rule 76: Machine-Readable JSON Consensus (Protocol B)
Auditor outputs: `{"round":"<id>","seat":"<seat>","verdict":"BOARD|REFUTE","findings":[...]}`. REFUTE -> machine coordinates. BOARD -> empty [].

## Rule 77: 20-Turn Persistent Headless & PM RC Invariant
PM (`pm|pm-b|cx-pm`) ALWAYS in --remote-control. Workers/builders/fixers: headless, hard ceiling BD_MAX_TURNS=20. Turn 20 -> clean handoff (RESUME_STATE.md) + terminate.

## Rule 78: Automated Pytest Digesting (Protocol D)
All tests via `bd-pytest-digest`. Tracebacks <= 3 lines / < 25 tokens. Exit codes preserved. No naked pytest.

## Rule 79: Virtual Browser Oracle (Protocol E)
Advisory via `bd-oracle` (`--oracle all --json`) -> BattleStation GPU (10.0.10.137:9222), $0 cost. API tokens reserved for code edits/git/CI.

## Rule 80: Pointer-Payload Decoupling (bd-blob-ptr)
Outputs >15 lines / >800 bytes -> CAS `/var/tmp/bd-blobs/<sha256>.log`, 4-line pointer envelope. No raw diffs/logs/grep in context. Exit codes + POSIX signals preserved.

## Rule 81: Deterministic Zero-Token Telemetry
No LLM polling loops. `bd-telemetry-daemon.py` (systemd) writes STATUS.txt + fleet_telemetry_live.json at 0 token cost. Wakeups on anomalous state transitions only.

## Rule 82: 4-Pool Tri-Platform Token Optimization
1. AGY: deduplicated GEMINI.md, `lean_worker` profile (< 2,500 tok baseline, 11 tools masked, 37 skills pruned).
2. Codex: builders/fixers -> gpt-6-astra/claude-fable-5-1. gpt-5.6-terra -> single-turn verifiers only.
3. Claude A/B: BD_MAX_TURNS=20, all tests via bd-test (bd-blob-ptr + bd-pytest-digest).
4. Satellite: routine AST/regex/lint -> LiteLLM/Ollama via bd-satellite-router (3.0s timeout, local fallback).
