# Original User Request

## 2026-09-22T13:53:40Z

# Teamwork Project Prompt — Draft

> Status: Step 1 — Eliciting project idea
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: [none — teamwork routes from the description]

The goal is to deeply audit all local MCP servers, fleet rules, and configuration resources to identify underutilized capabilities, expand them, and engineer a robust chunking script to completely index the `BulkDownloader` and `bd-persist` directories into the RAG knowledge base without hitting the 3-minute MCP timeout limit.

Working directory: ~/teamwork_projects/fleet_audit
Integrity mode: development

## Requirements

### R1. Repository Indexing Script
Write a Python script that chunks the `BulkDownloader` and `bd-persist` directories into smaller, discrete subdirectory batches. It must iteratively call the `context-mode` MCP `ctx_index` tool on these batches to index the entire filesystem without triggering the 3-minute MCP timeout.

### R2. Fleet Resource Audit
Audit the available local MCP servers (`vmware-clones`, `bd-bus`, `ratf`, etc.). Identify at least two heavily underutilized resources and draft a concrete technical implementation plan for how the fleet could integrate them (e.g., using `vm_clone` for ephemeral review sandboxes).

## Acceptance Criteria

### Execution & Verification
- [ ] A script `index_all.py` is written and can be executed without crashing.
- [ ] The script successfully indexes >10,000 files into the knowledge base without hitting a `context deadline exceeded` error.
- [ ] A markdown report `MCP_AUDIT.md` is generated detailing the underutilized tools and the proposed architecture to integrate them.

---
*Next: when approved → delegate via invoke_subagent*

## 2026-09-22T13:58:21Z

USER INSTRUCTION INJECTION: The user explicitly requested that you must actively poll the fleet VMs and VMware via the `vmware-clones` MCP server (using `vm_info`, `vm_list`, etc.) to ensure that the VMs have the resources they need for the sandboxing plan. If resources are insufficient, you must factor that in. Do not just blindly recommend cloning without checking hardware capacity first.

## 2026-09-22T15:09:57Z

The user has requested that `/home/mboyle/bd-cuts/` be added to the vector indexing queue. Please update the `index_all.py` script or append `bd-cuts` to your current batch payload so that all active cut branches, verdicts, and PR drafts are indexed and easily searchable by the fleet. Ensure that any `.git` or `venv` folders inside `bd-cuts` are excluded.

## 2026-09-22T15:29:50Z

The user has requested a comprehensive capability and resource scan of the remaining 26 fleet VMs in the `mesh.local` cluster (listed in `/etc/hosts` under `10.0.70.*`). The previous audit only scanned `10.0.70.164`.

Please write and execute a parallel SSH script (`pssh` or standard bash `&` loop) to query all 26 remote fleet VMs. You must gather:
1. Docker container lists (`docker ps`)
2. Listening TCP ports (`ss -tulpn`)
3. Load averages and memory usage (`free -m`, `uptime`)
4. Any running MCP or AI services (Ollama, LiteLLM, TEI).

Compile this into a structured markdown report `FLEET_WIDE_AUDIT.md` in the `teamwork_projects` directory. Do not run any destructive commands.

## 2026-09-22T18:14:38Z

# Teamwork Project Prompt — Draft

> Status: Launched.
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Full multi-agent team

Build a universal Knowledge Distribution Protocol (a unified MCP tool/server and daemon) that empowers any autonomous agent in the fleet (Claude A/B, AGY) to dynamically create, verify, and distribute new rules, skills, plugins, and hooks. When an agent discovers a new behavior, they can call this tool to propose a lesson. The system must verify the addition and automatically synchronize it across all required entry points (`CLAUDE.md`, `AGENTS.md`, `FLEET_RULE.md`, and active custom skill folders) so the entire fleet learns it instantly.

Working directory: ~/teamwork_projects/fleet_sync_tool
Integrity mode: development

## Requirements

### R1. Universal Agent Interface
Expose a callable interface (e.g., an MCP server with a `publish_lesson` tool, or a unified CLI script) that any native agent or Codex seat can invoke. It must accept structured input for either a new "Rule" or a new "Skill/Plugin".

### R2. Fleet-Wide Synchronization Engine
Implement the core logic to parse the submission and intelligently splice it into the correct locations. Rules must be appended to `CLAUDE.md`, `AGENTS.md`, and `bd-persist/FLEET_RULE.md`. Skills must be written into the correct Antigravity `skills/` directory structure with a valid `SKILL.md` frontmatter.

### R3. Syntax & Safety Verification
Before committing any changes to the core fleet files, the system must validate the submission (e.g., ensuring Markdown is valid, preventing duplicate rules, checking JSON/YAML syntax for skills) to prevent corruption of the fleet's prompting environment.

## Acceptance Criteria

### Programmatic Verification Tests
- [ ] A provided test script (`test_publish_rule.sh "Mock Rule 99"`) successfully executes with a `0` exit code, and a subsequent `grep` confirms the string exists in `CLAUDE.md`, `AGENTS.md`, and `FLEET_RULE.md`.
- [ ] A provided test script (`test_publish_skill.sh "mock-skill"`) successfully generates a complete directory structure containing a `SKILL.md` file with valid YAML frontmatter.
- [ ] Providing intentionally malformed input to the interface fails safely (non-zero exit code) and does **not** alter or corrupt any of the fleet files.

## 2026-09-22T22:50:30Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Full multi-agent team

Build a production-ready Next.js / React Heterogeneous Swarm Architecture Dashboard. It must visualize the live fleet of Claude and Antigravity (AGY) agents, track token cost efficiency, display CI/CD shard health, and provide interactive controls for the swarm.

Working directory: ~/teamwork_projects/heterogeneous_swarm_dashboard
Integrity mode: development

## Requirements

### R1. Frontend Architecture & Telemetry
Build a Next.js/React standalone application. It must include real-time visualizations for distributed node latency, CI/CD shard health, and historical cost/prefix cache projections.

### R2. Interactive Swarm Control
Implement a control panel allowing operators to dynamically re-order the `DISPATCH-LEDGER.tsv` queue and adjust active agent configurations.

### R3. API Quota & Limit Tracking
The system must actively track, calculate, and display both the 5-hour and weekly API rate limits across all integrated models (Claude A/B, Codex, AGY Claude/GPT, and AGY Gemini).

### R4. Resilient Local Data Integration
The backend must read from the local `usage.sqlite` and TSV ledgers asynchronously. It must use read-retry logic or WAL mode to prevent deadlocks when 15+ agents are writing to the database simultaneously.

## Acceptance Criteria

### Verification & Testing
- [ ] The application starts successfully via `npm run dev` (or equivalent) without compilation or hydration errors.
- [ ] The UI renders a dedicated API Quota panel that distinguishes between 5-hour limits and weekly limits for Claude vs Gemini.
- [ ] The backend can sustain 10 concurrent API read requests to `usage.sqlite` without throwing `sqlite3.OperationalError: database is locked`.
- [ ] Interactive queue re-ordering successfully modifies the underlying ledger file without corrupting active dispatcher reads.

## 2026-09-23T01:00:54Z

# Teamwork Project — Bug Fixes & Feature Additions

> Goal: Fix the E2E bugs discovered by the operator and implement the missing Architecture Visualizer.
> Requested team: Small, focused team

Working directory: ~/teamwork_projects/heterogeneous_swarm_dashboard
Integrity mode: development

## Requirements

### R1. Fix Broken React State & Interactivity
- **Auto-Refresh Bug**: The UI's auto-refresh timer resets the user's active tab/view state. Ensure React state is preserved across polling intervals.
- **Dead Buttons**: Implement the missing `onClick` handlers for the interactive Swarm Control buttons (e.g. queue re-ordering) so they actually mutate the backend or local state.

### R2. Fix Usage Chart Data Accuracy
The `usage.sqlite` data aggregation is incorrect. The charts are rendering the wrong metrics. Ensure the backend SQL queries correctly group by model/thread and aggregate the input/output tokens accurately according to the `usage_occurrences` and `usage_responses` schema.

### R3. Implement Live Architecture Visualizer
The dashboard is missing the "Live Visualizer of The Heterogeneous Swarm Architecture". 
- Add a dedicated component or tab that renders a live architectural topology diagram (e.g., using `reactflow` or a similar diagramming library, or simple CSS grids) representing the 27 nodes, the ESXi clones, and the active agents.

## Acceptance Criteria

### Verification
- [ ] The auto-refresh no longer resets the active tab or scroll position.
- [ ] At least one interactive button successfully triggers a backend mutation.
- [ ] The usage metrics align mathematically with raw `sqlite3` queries.
- [ ] The Live Architecture Visualizer component renders without crashing and visually represents the swarm nodes.
