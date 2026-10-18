---
name: boylenet-autonomous-mods
description: Reference and operating guide for Boylenet's Autonomous Mods, PreToolUse/PostToolUse Hooks, .82 64-core Ramdisk Pytest Interceptor, HiveMind Auto-Publishers, and OpenWebUI Inlet/Outlet Filters across Claude Code, Codex, Kimi, AGY, and OpenWebUI.
---

# Boylenet Autonomous Mods, Hooks & Filters (`boylenet-autonomous-mods`)

Documents the autonomous background modifications, safety shields, ramdisk pytest acceleration mods, episodic HiveMind auto-publishers, and OpenWebUI pipeline filters active across Claude Code, OpenAI Codex, Kimi K2.8, Antigravity (AGY), and OpenWebUI (`:8090` & `.72:8080`).

---

## 1. Autonomous Platform Mods (`bd-swarm-mod`)

Controlled centrally via `/home/mboyle/bin/bd-swarm-mod`:
```bash
/home/mboyle/bin/bd-swarm-mod status
/home/mboyle/bin/bd-swarm-mod enable all
/home/mboyle/bin/bd-swarm-mod test
```

### Mod 1: Autonomous Infra & Quota Context Injector (`bd-auto-infra-context-hook.py`)
- **Path**: `/home/mboyle/bin/bd-auto-infra-context-hook.py`
- **Behavior**: Injects a compact (`<=65 tokens`) real-time header containing `POOL_STATE.tsv` O1740 pool availability, `.72`/`.83` benchmark lock status, `bd-airgap` mode, and `:4079` gateway readiness at session start across Claude Code, Codex, Kimi, and AGY.

### Mod 2: Anti-Hallucination & Worktree Shield (`shield.py`, Rule 22)
- **Path**: `/home/mboyle/.gemini/config/shield.py`
- **Behavior**: Intercepts `PreToolUse` across AGY and Claude Code to block destructive Git operations (`git reset --hard`, `git checkout --`, `git clean`, worktree deletion) outside authorized sandboxes (`/home/mboyle/bd-cuts/` and `/home/mboyle/bd-local-wt/`).

### Mod 3: `.82` 64-Core `/dev/shm` Ramdisk Pytest & Digest Mod (Rule 78 & Rule 80)
- **Paths**: `/home/mboyle/bin/bd-pytest-digest`, `/home/mboyle/bin/bd-blob-ptr`, `/home/mboyle/bin/bd-test-ramdisk-mod.py`
- **Behavior**:
  1. Syncs candidate deltas to `10.0.70.82` (`wrk-test04`, 64-core `/dev/shm` ramdisk) so pytest runs with zero controller CPU contention.
  2. Compresses test output to `<=3 lines, <25 tokens` via `bd-pytest-digest` while storing full logs in `/var/tmp/bd-blobs/<sha256>.log` via `bd-blob-ptr`.

### Mod 4: HiveMind & `bd-bus` Autonomous Lesson Publisher (`bd-hivemind-auto-publish-hook.py`)
- **Paths**: `/home/mboyle/bin/bd-local-mcp-bridge.py`, `/home/mboyle/bin/bd-hivemind-auto-publish-hook.py`
- **Behavior**: Automatically captures verified bug-to-fix resolutions, `DONE.md` receipts, and `VERDICT: PATCH` outcomes, publishing them to the `bd-bus` SQLite WAL event stream and Qdrant `hivemind_episodes` (`10.0.70.125:6333`).

### Mod 5: OpenWebUI Autonomous Inlet/Outlet Filters (`:8090` & `.72:8080`)
- **Paths**: `/home/mboyle/bin/bd_openwebui_pipelines_bdkb_ext.py` & `/home/mboyle/bin/bd-openwebui-tool-gateway.py`
- **Active Global Filters**:
  1. `filter_boylenet_telemetry_injector`: Injects live Boylenet 27-VM health and `BD KB` citations into incoming chat requests.
  2. `filter_boylenet_smart_router`: Routes coding queries to `.137` RTX 2080 Ti / `.83` Heretic and architecture queries to `pipe-boylenet-bdkb-rag-citation-engine`.
  3. `filter_boylenet_token_guard`: Enforces Rule 80 blob pointer compression on large tool outputs.
