---
name: boylenet-4platform-bridge
description: Unified 4-Platform Autonomous Integration Bridge across Antigravity (AGY), Claude Code, OpenAI Codex CLI, Kimi K2.8 CLI, and Local GPU (:4010 / .137 / .83). Documents how all platforms seamlessly invoke bd-boylenet-infra-mcp.py, bd-swarm-mod, bd-local-coding-agent, and bd-cross-platform-swarm-assist.py.
---

# Boylenet 4-Platform + Local GPU Autonomous Bridge (`boylenet-4platform-bridge`)

Every agent running on **Antigravity (AGY)**, **Claude Code**, **OpenAI Codex CLI**, **Kimi K2.8 CLI**, or **Boylenet Local GPU (`:4010` / `.137` / `.83`)** shares 100% unified access to Boylenet's 27-VM cluster, 88-tool Universal Gateway (`:4079`), 6-Volume `BD KB`, Dual Browser Oracles (`.137:9222` & `.181:9222`), and cross-platform swarm fanout.

---

## 1. Cross-Platform Component Matrix

| Capability | Canonical Binary / MCP | Claude Code Slash Command | Codex Agent Profile | Kimi K2.8 Skill |
|---|---|---|---|---|
| **27-VM Infra & Airgap** | `/home/mboyle/bin/bd-boylenet-infra-mcp.py` | `/boylenet-infra` | `boylenet-xplat-commander` | `boylenet-infra-commander` |
| **Dual Browser Oracle** | `/home/mboyle/bin/bd-oracle` & `bd-oracle-suite-verifier.py` | `/boylenet-oracle` | `boylenet-oracle-tester` | `boylenet-dual-oracle-e2e` |
| **`$0` Local Coding Agent** | `/home/mboyle/bin/bd-local-coding-agent` | `/boylenet-local-coder` | `boylenet-local-coder` | `boylenet-local-coding-agent` |
| **6-Volume `BD KB` (`<20ms`)** | `bd_openwebui_pipelines_bdkb_ext.py` | `/boylenet-bdkb` | `boylenet-xplat-commander` | `boylenet-bdkb-hivemind` |
| **Full Suite E2E Trilogy** | `bd-full-suite-e2e-test.py` + `bd-openwebui-e2e-test.py` | `/boylenet-e2e` | `boylenet-e2e-verifier` | `boylenet-dual-oracle-e2e` |
| **Cross-Platform Swarm** | `/home/mboyle/bin/bd-cross-platform-swarm-assist.py` | `/boylenet-xplat-swarm` | `boylenet-xplat-commander` | `boylenet-infra-commander` |
| **Autonomous Mods/Hooks** | `/home/mboyle/bin/bd-swarm-mod` | *(Auto-active via hooks)* | *(Auto-active via wrappers)* | *(Auto-active via hooks)* |

---

## 2. Seamless Invocation Patterns Across All 4 Platforms

### A. `bd-boylenet-infra-mcp.py` (27-VM Cluster, `:4010` GPU Gateway, `bd-airgap`)
- **MCP Tool Call**: registered as `boylenet-infra` MCP server across Claude Code (`~/.claude.json`), Codex (`~/.codex/config.toml`), Kimi (`~/.kimi/mcp.json`), and AGY (`~/.gemini/antigravity-cli/mcp/boylenet-infra/`).
- **Direct CLI**:
  ```bash
  python3 /home/mboyle/bin/bd-boylenet-infra-mcp.py --status
  python3 /home/mboyle/bin/bd-boylenet-infra-mcp.py --vm 10.0.70.82 --cmd "uptime"
  ```

### B. `bd-swarm-mod` (Autonomous Hooks, `.82` Ramdisk Pytest, HiveMind Auto-Publisher)
- Inspect or toggle autonomous platform mods:
  ```bash
  /home/mboyle/bin/bd-swarm-mod status
  /home/mboyle/bin/bd-swarm-mod test
  ```

### C. `bd-local-coding-agent` (`$0` Local GPU Coding + `.82` 64-Core Ramdisk Self-Healing)
- Automatically checks `.72`/`.83` for `bench_worker.py` contention and routes to `.137:11434` (`qwen2.5-coder:14b`/`7b` on RTX 2080 Ti) or `.83:8081` (`Qwen3.6-35B-A3B-Heretic`):
  ```bash
  /home/mboyle/bin/bd-local-coding-agent --probe-backends
  /home/mboyle/bin/bd-local-coding-agent --sandbox /home/mboyle/bd-local-wt/sb-race-local \
    --target-file bulk_downloader/utils.py --target-test tests/test_utils.py \
    --prompt "Add helper or fix defect" --json
  ```

### D. `bd-cross-platform-swarm-assist.py` (Parallel Multi-Platform Fanout)
- Consults `/home/mboyle/bd-persist/POOL_STATE.tsv` (O1740 Dynamic Capability Routing) and launches parallel sub-tasks across Claude Code, Codex CLI, Kimi K2.8 CLI, Local GPU (`:4099`/`bd-local-coding-agent`), and AGY:
  ```bash
  python3 /home/mboyle/bin/bd-cross-platform-swarm-assist.py \
    --task "Audit and verify module invariants" \
    --platforms claude,codex,kimi,local \
    --json
  ```
