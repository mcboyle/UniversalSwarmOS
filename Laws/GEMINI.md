# AGENTS.md -- codex entry point (what CLAUDE.md is to Claude Code)
READ FIRST (they bind you):
  /home/mboyle/bd-persist/FLEET_RULE-FLOOR.md (carried floor, <=4 KB -- READ THIS)
  /home/mboyle/bd-persist/FLEET_RULE.md (full law, rules 1-57: QUERY by heading, never read whole)
  /home/mboyle/CLAUDE.md (operator words)
  /home/mboyle/BulkDownloader/CLAUDE.md (repo contract; overrides for repo work)
Evidence: bd-persist/FLEET_RULE-EVIDENCE.md.
UPDATES ~30 CHARS + path. ASK only when two readings change work (named options, <=4); else decide, act, record.

MEASUREMENT: FOUND n / FOUND NONE / COULD NOT LOOK (UNKNOWN != permission) | PROVE PROBE CAN SAY YES | NAME DENOMINATOR from filesystem | DIFF INDEX AGAINST DECLARED BASE, never HEAD. BD_GATE_SCOPE: strictly 'module' or 'repo-wide'.

MECHANICS: bd-say.sh <tmux-session> "<=30 chars|path" (reaches Claude A/B + codex). codex queue --thread and SendMessage don't cross pools. Resume: codex resume --remote <sock> <UUID> <task.md>.
AGY SEATS: native background subagents (no tmux, no --remote-control). send_message(conversationId) + manage_subagents.
SEAT VERIFICATION: (1) live MCP tool, (2) ground truth from disk, (3) active plugins/hooks.

SAFETY: NO WORKTREE DELETED OR RESET, EVER. All 27 nodes accessible (Rule 21).

HOW TO WORK: minimal change, shortest path, no adjacent tidying | first tool call early | no chain-of-thought in output | NEW code ignores backward compat | never: delete worktree, weaken test/gate/assertion, unpin dependency (yt-dlp pin is order), rewrite untouched code.
HORIZON: future triggers never halt current execution early.
SHIP BEFORE HANDOFF: staged work driven to completion; never defer ready-to-ship.

MODELS: gpt-6-astra judgement | gpt-5.6-terra measurement | gpt-5.6-sol advisory | gpt-5.6-luna DISABLED (MRCR 41%).
CUTS: read bd-persist/CUT-WORKFLOW.md once per task packet.

IDEAS: backlog gate (Rule 24, never edit IMPROVEMENT_BACKLOG.md directly) | approval order (operator first, PM after) | neutral language (zero sensitive terms, beware automation identifier substrings).

REBASE: in-place conflict resolution | BD_REVIEW_SELFMUT=0 unless ordered | GATE: UTC RFC3339 WRITTEN-AT, CENSUS, PRECHECK: PASS, PATCH-SHA256: <hex> | IN-TRAIN STACKING for overlapping files.

## HTAP-9 MACHINE PERSONA
NO GREETINGS. NO EXPLANATIONS. NO FILLER. Updates ~30 chars.

## TOKEN EFFICIENCY & AST SLICING (ALL POOLS)
- AST: `ratf` MCP `ctx_slice`, never full-file ingestion. `bd-ast-diff` for symbolic deltas.
- TESTS: `bd-pytest-digest` (<=3 lines, <25 tokens). Never raw pytest.
- SATELLITE: trivial tasks -> Ollama/LiteLLM on ai-ollama01. `bd-prewarm-daemon` keeps cache warm.

## EPHEMERAL SANDBOXING & EVENT STREAMING
- RED tests: `vmware-clones` MCP only. Never on host.
- Cross-pool: `bd-bus` WAL, not .md polling.

## CODEX EFFICIENCY
- FAST-FAIL: `ruff_check` + `mypy_check` before patches.
- AST: `ratf.ctx_slice` instead of full files.
- CI: `bd-ci-taxonomy` before blind fixes.

## INFRASTRUCTURE ROUTING
- 27 nodes, 1.4+ TB idle RAM, 656 vCPUs. Heavy workloads off controller (10.0.70.164).
- RAG indexing -> wrk-test04 (10.0.70.82, 64-core).
- Satellite AI -> LiteLLM on ai-ollama01 (10.0.70.228) + ai-infer01 (10.0.70.125).
- Ephemeral VMs -> spr-pool (10.0.70.120, .149, .183, .185).
- Oracle: dual-node (Bittorrent 10.0.70.181:9222, BattleStation 10.0.10.137:9222). bd-oracle --oracle all --json. Gemini/ChatGPT/Claude A&B. $0 marginal cost. PIN 628895 authorized.

## CONTEXT GUARD
- Telemetry: bd-telemetry-guard.py, sub-minute polling for orchestrators.
- Ceilings: workers/lens <=150k tokens. PM/integrator <=250k tokens.
- Compaction: bd-binary-payload before /compact. (MessagePack binary serialization.)

## READ-ONLY SEATS (Rule 24)
audit/status/lens: never /compact, kill, or assign work.

## KNOWLEDGE SYNC
Undocumented bug/workflow/optimization -> publish_lesson MCP. No operator permission needed.

## ORACLE REASONING COMPLETION
CDP: wait for stop-button absence. Never return on interim thinking states.

## Rule 60: Single-Turn Compound Execution
Chain inspect+modify+verify+diff in single pipeline (bd-compound-exec). set -eo pipefail. <= 2 turns. No multi-turn hand-holding.

## Rule 61: VMware Cold Spare Elasticity
spare1-2 on, spare3-12 off (448 GB, 176 vCPUs). Power-on: toolsOk + DHCP + SSH. govc: .virtualMachines[], .summary.guest.ipAddress.

## Rule 74: Hard Output Cap & Zero-Prose (Protocol A)
<= 50 tokens: `<STATUS> <path>`. Evidence on disk. Escalations: `AMBIGUOUS: <path> | (1)/(2). Reply 1 or 2.`

## Rule 75: Differential PM Orders (Protocol C)
`ORDER: <id> | REF: <base> | TARGET: <sha> | ACTION: <task>`. No static rule re-broadcast.

## Rule 76: JSON Consensus (Protocol B)
`{"round":"<id>","seat":"<seat>","verdict":"BOARD|REFUTE","findings":[...]}`. BOARD -> []. REFUTE -> machine coordinates.

## Rule 77: 20-Turn Headless & PM RC
PM always --remote-control. Workers headless, BD_MAX_TURNS=20. Turn 20 -> RESUME_STATE.md + terminate.

## Rule 78: Pytest Digesting (Protocol D)
bd-pytest-digest: <= 3 lines, < 25 tokens, exit codes preserved. No naked pytest.

## Rule 79: Oracle Routing (Protocol E)
bd-oracle -> BattleStation (10.0.10.137:9222), $0 cost. API tokens for code/git/CI only.

## Rule 80: Pointer-Payload Decoupling (bd-blob-ptr)
>15 lines / >800 bytes -> CAS /var/tmp/bd-blobs/<sha256>.log + 4-line pointer. No raw output in context.

## Rule 81: Zero-Token Telemetry
No LLM polling. bd-telemetry-daemon.py (systemd) -> STATUS.txt + fleet_telemetry_live.json. Wakeups on anomalies only.

## Rule 82: 4-Pool Token Optimization
AGY: deduplicated GEMINI.md, lean_worker (<2,500 tok, 11 tools masked, 37 skills pruned).
Codex: builders -> gpt-6-astra/fable. Terra -> single-turn verifiers only.
Claude: BD_MAX_TURNS=20, bd-test (bd-blob-ptr + bd-pytest-digest).
Satellite: bd-satellite-router, 3.0s timeout, local Python fallback.
