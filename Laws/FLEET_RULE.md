# FLEET_RULE.md -- THE OPERATIVE LAW. Injected at SessionStart and every PreCompact. Every rule binds.
# Receipts for each rule: bd-persist/FLEET_RULE-EVIDENCE.md (on demand). Terse by design: AI readers.

## COMMUNICATION
 1. UPDATES ~30 CHARS. Detail -> FILE, send PATH. No preamble/recap/narration. Completion is a
    file. EXCEPTION: an operator-requested digest/plan/report/answer prints in full.
    Line test: would the operator act differently without it? No -> cut it.
 2. BOOTSTRAPS EXEMPT: only launch role prompt sent with BD_SAY_KIND=bootstrap; guard AND caller
    must both assert it.
 3. PM ASKS INTERACTIVELY: named options + consequence, recommendation first, <=4. Ask only when two
    readings change the work.
 4. WHEN SOMETHING RESOLVES, SAY WHAT IS LEFT ("nothing remaining" / "cannot tell"); re-derive.
 5. CADENCE: <=30-char update /10 min while operator PRESENT; 2-hourly DIGEST (<=25 lines,
    bd-persist/DIGEST.md) while AWAY. Events always emit. bd-pm-beat.sh writes; bd-staleness-check RED if it stops.

## MEASUREMENT
 6. THREE OUTCOMES: FOUND n / FOUND NONE / COULD NOT LOOK. UNKNOWN IS NEVER PERMISSION.
 7. PROVE PROBE CAN SAY YES BEFORE REPORTING NO. Positive control beside every zero.
 8. NAME YOUR DENOMINATOR, derived FROM FILESYSTEM, never from handed list.
 9. DIFF INDEX AGAINST DECLARED BASE, NEVER AGAINST HEAD.
10. ANCHOR PROCESS PROBE (invocation `^bash /path` or PID). Pattern matches own shell;
    a uniform count across hosts is the tell.
11. CITE HEADING, NEVER LINE, in files taking insertions.
12. MEASUREMENT LIST != ACTION LIST; converting re-derives every entry.
13. RUN PRECUT, THEN RESTORE, THEN WRITE DONE.md; porcelain empty of regenerated paths.
14. EVERY DECISION WRITTEN WITH EVIDENCE WHEN TAKEN, never reconstructed.

## VERDICTS AND REVIEW
15. LINE 1 EXACTLY `VERDICT: BOARD|REFUTE|BOUNCE`, DONE.md `VERDICT: PATCH|UNKNOWN`, terminal `VERDICT: LANDED`.
    THE PREFIX IS REQUIRED; anything else routes nowhere.
16. RECORD TREE JUDGED: `git -C <wt> write-tree` (INDEX tree) or PATCH-SHA256 = sha256 of
    `git diff --cached --full-index <declared-base>` (--full-index: abbrev-independent, H606).
    Base tree / HEAD^{tree} identify the generation, not the object.
17. A LENS NEVER JUDGES A CUT IT BUILT.
18. BRIEF'S "SKIP THIS" CAN BE WRONG; LENS OUTRANKS. Measure numstat before excluding.
19. REFUSAL CORRECT when order unsourced or premise refuted by measurement.
    An invitation to refuse is not a mechanism: a brief that can be wrong needs a check.
20. WRITE LOCATION NAMED SEPARATELY FROM READ LOCATION. Never write into cut you were sent
    to read. Routers glob only `<cut>/.review/VERDICT-*.md`.

## AUTHORITY, SAFETY, BOUNDARIES
22. NO WORKTREE DELETED OR RESET, EVER. Assign/reset = deletion by another name.
23. LOCAL CUT AUTHORITATIVE over codex copy.
24. READ-ONLY SEATS (codexwatch, verify, cartograph, audit, ideas, nurse, status) never write a
    tree, assign work, or stop/restart a seat.
25. DECLINED QUESTION != HOLD; fall back to standing authority.
26. KNOW WHICH SEAT YOU ARE, WITH EVIDENCE (pane title is label; compaction summary is a
    claim). No evidence -> issue nothing, ask.
27. TOOLS FROM THE REPO: ./venv/bin/python toolchain/bin/<tool>. NEVER a bare bd-<tool>.
28. OPERATOR PRESENCE = bd-persist/OPERATOR-PRESENCE.md (watcher seat). File absent = AWAY.

## BUDGET AND ROUTING
29. ROUTE ON EACH ACCOUNT'S 5-HOUR HEADROOM. O828 (2026-09-15, operator): NO stop/throttle percentages -- run until provider limits.
    IDLE IS NOT CAPACITY. An unseen limit is UNKNOWN.
30. OWN CONTEXT: <95% normal; at 95% start nothing but compaction-safety; at 98% halt tasks.
31. CLOSURES RIDE TRAIN THAT CLOSES THEM (register commit on train, O309); dedicated register
    cut is for CORRECTIONS only; regenerate AFTER the close.
31b. bd-verdict-write-hook.sh WARNS, never refuses (blocking write hook loses work); refusals
    belong at the collect gate.
32. SMALL-FIX LANE: diff EXACTLY REPRODUCED BY NAMED DETERMINISTIC GENERATOR, no product source,
    no new path, no weakened assertion, on an already-cleared cut, may skip a new lens round /
    clearance / re-freeze. NEVER skips exact-head CI, merged-tree proof, deploy verification, or the
    record naming the generator. Typed content is not in this lane.

## EFFICIENCY (standing operator rules)
33. SPEND OPERATOR'S CONTEXT LIKE HIS MONEY: read slice; never re-derive established or
    re-read to verify a clean edit; batch independent calls; every message costs HIS context.
33b. READ SLICES, NEVER FILES: bd MCP tools (law/ask/brief/row/log_slice/collect_gate/lane_status/evidence) or bounded
    grep/head -c; never cat a file over 4 KB into context; tool output you did not need is the most expensive text
    there is (O586: 98% of fleet tokens are per-turn context re-reads).
33c. RECORD LENGTH CAP (O589): VERDICT/DONE/landing/NOTE/RULING file <=40 lines, <=4 KB: line 1
    verdict, object (tree/sha), commands with rc and counts, what is left. No narrative, no history.
    FILE NAMES <=60 chars (a 200-char name is re-read by every ls, message and inbox batch).
    Output tokens cost 5x input and every record is read by 3+ seats. Longer = detail file, linked.
34. TOOL THAT COSTS A ROUND IS FIXED OR FILED BEFORE MOVING ON, with proving acceptance.
    Two occurrences = a class. An unrecorded workaround is a trap.

## ROUTING AND VISIBILITY
35. BOARD VISIBLE ONLY IN `<cut>/.review/VERDICT-*.md`; other verdict dirs unread.
35b. REVIEW.LOG EMITTER CONVENTION (H266): Put candidate id in first four whitespace fields
    when the line is a statement about that id (`<ts> <SEAT> <ID> ...`). A line that merely mentions
    an id in trailing prose keeps it past field 4 so boardgate's 4-field window does not falsely match.
36. VERDICT RECORDS ITS OBJECT (rule 16). mtime != staleness. Hook warns; collect gate refuses.
37. ONE DECISION, ONE PLACE: model/effort derive from bd-launch-role.sh; bd-codex-drift-check.sh
    proves it. A tool that exists twice (~/ and harness/) is fixed in both, proven by cmp.
38. RC ENABLED IN ARGV != RC WORKING; operator seeing seat is the test. Claude: the three
    DISABLE_* env vars kill RC (launcher strips them). Codex: attach `--remote unix://<socket>`
    or the app cannot see it. ListAgents proves nothing. AGY (O855/O855b/O862, 2026-09-19): non-RC seats run IN TMUX via bd-launch-agy.sh (~20 max,
    flash-high default); `--rc` (Remote Control) only for primary roles, cap 5-6 (launcher exit 9 on the 7th);
    fan-out inside AGY uses native subagents under one RC parent. Proof of seat readiness requires an active verification challenge:
    live MCP tool invocation, ground-truth rule read from disk, and self-attested hook/plugin enumeration.
39. bd-say REACHES TMUX POOL (Claude A/B, codex). SendMessage and `codex queue` do not cross pools.
    AGY subagents run without tmux; communicate via `send_message` (conversationId) and track via
    `manage_subagents`. A file carries content, never reaches a seat. rc=6 = target pane holds a dialog:
    a refusal, not a broken channel; the return path fails the same way -- read say.log.
40. ROUTINE -> bd-status (ACK/LANDED/FROZEN/queued/refuted/boarded/prepped/claimed/counts).
    ESCALATION -> PM (limit/stall/outage, operator-class decision, HIGH finding, unresolvable
    refusal, anything marked FABLE). Lens questions -> adjudicator.
41. HERMETIC GIT FIXTURES: Any test/tool creating scratch git commits must pass explicit config
    flags (`git -c user.name=Test -c user.email=test@example.com commit ...`) or set GIT_COMMITTER_*
    env vars; never assume ambient global git config on CI runners or sandboxes.
42. STATIC CENSUS SUBSTRING GUARDS: Any static sweep over `tests/test_*.py` (1,700+ files) must apply
    cheap raw-text substring guards (`if needle not in raw: continue`) before invoking expensive
    parsers (`ast.parse()`, `tokenize.tokenize()`, or heavy regex passes).
43. CLAUDE RC ENDPOINT INVARIANT: Remote Control (`--remote-control`) strictly refused by Claude Code
    unless `ANTHROPIC_BASE_URL` resolves directly to `https://api.anthropic.com`. Because `settings.json`
    env values outrank shell environment variables and `env -u`, any launch of `--remote-control` MUST
    explicitly pass `--settings '{"env":{"ANTHROPIC_BASE_URL":"https://api.anthropic.com","ENABLE_TOOL_SEARCH":"true"}}'`
    to guarantee the bridge binds to the operator's mobile and web app.
44. ASYNCHRONOUS MARKER FLUSH SYNCHRONIZATION: Reading filesystem sync marker written by
    another process must never rely solely on `marker.exists()` or `marker.is_file()`. Inode creation is
    non-atomic with data flush, exposing 0-byte windows. The reader MUST poll until the file is non-empty
    and terminates with an expected delimiter (`marker.read_text().endswith('\n')`), or use atomic
    filesystem replacement (`os.replace`). Dynamic timestamps must use static fixed-noon epochs to prevent
    midnight calendar traversal flakes.
45. PLAYWRIGHT ASYNC/SYNC TEARDOWN PARITY: Any fixture/test helper initializing external OS
    daemon (`Xvfb`), subshell process group, database connection pool, or asynchronous driver (`playwright`,
    `asyncio`) MUST guarantee cleanup in a `try...finally` block. Subprocesses must terminate via
    `os.killpg()`, and Playwright contexts must execute both `context.close()` and `pw.stop()` before
    returning control to pytest to prevent event loop leaks across persistent workers.
46. CI MATRIX CAPABILITY PARITY: Every test file enumerated in `.github/workflows/ci.yml` must align
    with the capability boundary of its assigned shard. Browser tests (`playwright`, Chromium) belong
    exclusively to `download-chain` or `template-selectors`; Node tests belong to `frontend-vitest` or
    `parity-graph`. Placing a browser-dependent test on a pure-Python shard lacking Chromium is an
    architectural defect; missing dependencies must fail closed rather than skip.
47. MONKEYPATCH GLOBAL PURGE CONTRACT: Any test runner harness, fixture, or patch mechanism modifying
    module-level singletons or ambient global state (such as `_MonkeyPatch`, `bulk_downloader.app._SITE_RUNTIME_*`,
    `_BOOTED_PATHS`) MUST implement an isolated context manager (`with monkeypatch.context() as m:`) and
    guarantee complete restoration in a `finally:` block. Un-reset module globals cause inter-test
    contamination, boot path collisions, and dirty working tree gate refusals.
48. FASTMCP STDIO TRANSPORT PURITY: FastMCP servers over stdio transports must guarantee absolute
    byte purity on `sys.stdout`. Unhandled print statements, raw traceback dumps, and third-party library
    warnings (such as Pydantic forward-reference resolution warnings) must be suppressed or redirected to
    stderr/logfiles to prevent JSON-RPC frame corruption. FastMCP script modules should reside directly in
    user site-packages (`~/.local/lib/python3.12/site-packages/`) to avoid PEP 668 packaging conflicts.
49. INFRASTRUCTURE FABRIC ADDRESSING & SSO REALM PARITY: Hypervisor, network, and storage automation
    scripts must never target gateway routers (`.1` addresses) for management API endpoints. VMware
    vCenter Server Appliance (`10.0.20.70` / `vc04.boylenet.themfboyles.com`) must authenticate via the
    active SSO realm (`Administrator@boylenet.themfboyles.com`), managing all cluster VMs centrally across
    both clusters. Individual ESXi hypervisors (`10.0.20.41-44`) must authenticate directly via local
    `root` credentials for hardware and host-level recovery.
50. HERMETIC INFERENCE CONTAINER MODEL MOUNTING: Model inference containers (TEI, vLLM, Ollama) must never
    depend on runtime external model downloads from public CDNs. Model weights and configs must be pre-fetched
    into local filesystem storage using `curl -sL` and mounted read-only (`/model:ro`) using `--model-id /model`
    to guarantee immunity against relative redirect syntax shifts and upstream rate limits.
51. DUAL-RESOLVER LOCAL DNS ISOLATION: Local DNS server containers (CoreDNS) on nodes with active
    `systemd-resolved` must explicitly bind to `127.0.0.1:53` (TCP/UDP), preserving `127.0.0.53` for system
    resolution and avoiding wildcard `0.0.0.0:53` bind collisions.
52. PHYSICAL OUT-OF-BAND (iLO/ILOM) REDFISH INVARIANT: Physical ProLiant hypervisors (`esxi01`–`esxi04`)
    out-of-band management operates on subnet `10.0.10.0/24` via HPE iLO 4/5 Redfish REST APIs
    (`10.0.10.10`, `10.0.10.20`, `10.0.10.252`, `10.0.10.40`). The gateway at `.1` is the UniFi Dream
    Machine SE and must never be targeted as an iLO. Bare-metal power cycling, thermal sensor telemetry,
    and chassis health inspection must target `/redfish/v1/Systems/1/` with basic authentication
    (`~/.bd-import/ILOM.txt`), providing emergency out-of-band recovery when hypervisor hostagents or
    network interfaces hang.
53. VSPHERE DYNAMIC SCALING & SPARE POOL CONSERVATION: All primary test runner VMs (`test3big`, `test4`,
    `Test5`) and hot spare nodes (`Spare1`, `spare2`) must maintain `cpuHotAddEnabled=true` and
    `memoryHotAddEnabled=true` to allow zero-downtime resource expansion. Modifying vCPU or RAM on VMs
    without hot-add requires a clean guest shutdown (`govc vm.power -s`) before executing `govc vm.change`.
    Idle spares (`spare3`–`spare12`) must remain powered down, preserving 448 GB RAM and 176 vCPUs for
    the shared vSAN/vSphere cluster pool, with exact-count pre-warmed hot spares limited to 2.
54. TRI-AGENT ECOSYSTEM PARITY & SKILL SYNCHRONIZATION: Any new MCP tool server, custom agent skill
    (`~/.agents/skills/`), or plugin integrated into the fleet MUST be registered and symlinked across
    all three active agent platforms: Antigravity (`mcp_config.json`), Claude Code (`~/.claude.json` &
    `~/.claude/skills/`), and OpenAI Codex (`~/.codex/config.toml` & `~/.codex/skills/`). Multi-agent
    seats across Pools A, B, and C must maintain identical tool capabilities and skill discovery.
55. PM MODEL DESIGNATION INVARIANT: Primary PM seat model across fleet orchestrators strictly
    designated as `claude-fable-5-1` on `high` effort (`PM_MODEL.md`). Automated launchers
    (`bd-launch-role.sh`, `bd-launch-agy.sh`) must bind `pm`, `pm-b`, and `agy-pm` to `fable` with high
    effort unless explicitly re-ordered by an operator directive.
57. CANONICAL REGISTER PROMOTION & CHECKSUM INVARIANT: When product proposals approved by the
    operator, the holding seat MUST:
    (1) Write the promoted rows with status 'OPEN' to 'harness-work/ROW-xxx-yyy-register.rows'.
    (2) Update 'IMPROVEMENT_BACKLOG.md' rows to 'OPEN' and recompute the canonical marker
        '<!-- canonical-task-register schema=1 rows=N open=M ids-sha256=H -->', where H is the SHA256 of
        ','.join(all_ids).
    (3) Dispatch a terse reply '<=30 chars + path' directly to the PM inbox ('bd-persist/inbox/PM/').
    (4) Record the transaction in 'bd-persist/role-state/<role>.md'.

## EXTREME EDGE OPTIMIZATIONS (SWARM V3)
58. PRECISION AST SLICING: Never ingest full source files via unstructured `view_file` or `cat`. You MUST use the `ratf.ctx_slice` MCP tool for precision AST extraction to preserve context budgets.
59. LOCAL SATELLITE OFFLOADING: Route trivial/deterministic tasks (formatting, regex, linting, log parsing) to local Ollama/LiteLLM satellite models (`ai-ollama01`) via `fleet-satellite-orchestration` to reserve premium Fable/Opus quota.

## VIRTUAL BROWSER ORACLE REASONING COMPLETION INVARIANT
When extracting responses from reasoning models (ChatGPT o1/o3, Gemini Ultra, Claude Max) via Chrome DevTools Protocol, clients must NEVER prematurely return on interim thinking/working states (e.g. .result-thinking, "Thinking", or "Thought for X seconds"). Clients must wait for completion indicator disappearance (e.g. stop-button absence) and extract strictly non-thinking markdown elements.

## Rule 60: Single-Turn Compound Execution Protocol
To eliminate quadratic token burn across multi-turn agent loops: (1) Agents MUST chain inspection, modification, verification, and diff generation into a single execution pipeline where deterministic (bd-compound-exec). (2) Enforce set -eo pipefail fail-fast semantics with exact exit code propagation. (3) Subtasks must achieve completion in <= 2 turns. Multi-turn conversational hand-holding for sequential tool calls is prohibited.

## Rule 61: VMware vCenter Cold Spare Elasticity & govc Schema Invariants
1. Cluster Spare Pool Policy: spare1 and spare2 remain poweredOn hot spares. spare3 through spare12 remain poweredOff cold spares to conserve 448 GB RAM and 176 vCPUs across ESXi hosts. 2. Elastic Scaling: Powering on cold spares requires verification of VMware Tools agent status (toolsOk), DHCP guest IP resolution, and SSH reachability before assigning task queues. 3. JSON Parser Invariant: Automated parsing of govc vm.info -json MUST target lowercase .virtualMachines[] root and .summary.guest.ipAddress.

## CURRENT STATE -- READ AFTER A COMPACTION, BEFORE ACTING
    bd-persist/role-state/<role>.md (bd-role-state.sh get) | bd-persist/WORKING.md (live, /1 min)
    /home/mboyle/bd-role-claim.sh who-all | bd-persist/CUT-WORKFLOW.md | OPERATOR_DECISIONS.md (grep O-number)
Seats come up via bd-restart.sh (staged, evidence-gated). Up != assigned; fresh context ASKS before dispatching.
