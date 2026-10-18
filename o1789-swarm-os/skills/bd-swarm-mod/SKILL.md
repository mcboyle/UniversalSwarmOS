---
name: bd-swarm-mod
description: Unified Autonomous Swarm Mod & Plugin Pack across Claude, Codex, Kimi, AGY, and OpenWebUI (.164:8090 / .72:8080). Provides <100-token pre-turn infrastructure & quota context injection (Mod 1), <4s post-edit Ruff + Mypy + .82 /dev/shm ramdisk pytest verification (Mod 2), autonomous Rule 25 Qdrant HiveMind & BD KB lesson publishing (Mod 3), OpenWebUI autonomous inlet BD KB context filter + 1-click actions (Mod 4), and the unified `bd-swarm-mod` CLI (Mod 5).
---

# `bd-swarm-mod` — Autonomous Swarm Mod & Plugin Pack (Mods 1–5)

## Quick Commands (`bd-swarm-mod`)
```bash
# 1. Inspect live status of all 5 Autonomous Mods, Qdrant vectors, .82 ramdisk, and OpenWebUI functions
/home/mboyle/bin/bd-swarm-mod status [--json]

# 2. Emit <100-token live infrastructure, O1740 pool quota, GPU benchmark-guard & :4079 gateway header
/home/mboyle/bin/bd-swarm-mod context [--json] [--hook] [--platform claude|codex|kimi|agy]

# 3. Run <4s post-edit Ruff (F,E9) + Mypy + .82 /dev/shm ramdisk pytest digest on any worktree or file
/home/mboyle/bin/bd-swarm-mod verify-edit /home/mboyle/bd-local-wt/<wt>/<file.py> [--test tests/test_*.py] [--json]

# 4. Autonomously scan AGENT*.md + RESULT.md, upsert 1024-d vectors to Qdrant (fleet_lessons_hivemind & bd_master_kb), and update 05-SWARM-OPERATIONS-RECEIPTS-AND-PLAYBOOKS.md
/home/mboyle/bin/bd-swarm-mod sync-lessons [--json]

# 5. Run full 5-Mod + 28-VM Open Terminal E2E verification suite
/home/mboyle/bin/bd-swarm-mod e2e-quick [--json]
```

## The 5 Autonomous Mods
1. **Mod 1 (`/home/mboyle/bin/bd-auto-infra-context-hook.py`)**: `<100`-token pre-turn infrastructure & O1740 quota context injector hook (`POOL_STATE.tsv`, `.137`/`.83`/`.72` benchmark-safe GPU state, `:4079` 27-VM Open Terminal & 51-Toolkit gateway, `bd-airgap`, `bd-local-coding-agent`, `bd-boylenet-infra-mcp`).
2. **Mod 2 (`/home/mboyle/bin/bd-auto-pytest-ramdisk-mod.py`)**: `<4s` post-edit `ruff check --select F,E9` + `mypy` + `.82` `/dev/shm/bd-ci-ramdisk` pytest runner with `bd-pytest-digest`.
3. **Mod 3 (`/home/mboyle/bin/bd-auto-hivemind-lesson-publisher.py`)**: Rule 25 autonomous scanner for `AGENT*.md` and `RESULT.md` that upserts 1024-d vectors into Qdrant `fleet_lessons_hivemind` & `bd_master_kb` (`10.0.70.125:6333`) and updates `05-SWARM-OPERATIONS-RECEIPTS-AND-PLAYBOOKS.md`.
4. **Mod 4 (`/home/mboyle/bin/bd-openwebui-autonomous-mods-installer.py`)**: OpenWebUI global active (`is_active=1`, `is_global=1`) filter & action mods on `.164:8090` and `.72:8080`:
   - `boylenet_autonomous_context_and_bdkb_mod` (`type="filter"`, `is_global=1`)
   - `action_commit_and_push_gitea_github` (`type="action"`, `is_global=1`)
   - `action_dispatch_local_coding_agent` (`type="action"`, `is_global=1`)
5. **Mod 5 (`/home/mboyle/bin/bd-swarm-mod`)**: Unified CLI manager across Claude, Codex, Kimi, AGY, and all 28 Open Terminal VM connections.
