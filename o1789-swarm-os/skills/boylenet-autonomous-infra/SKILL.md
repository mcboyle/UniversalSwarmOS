---
name: boylenet-autonomous-infra
description: Autonomous Boylenet 27-node cluster infrastructure execution, $0 local coding agent dispatch, 64-core /dev/shm ramdisk pytest digesting, dual Chrome CDP browser oracles (.137 & .181), 6-volume Master BD KB search, Qdrant Hivemind vector memory, 86-model AI Vault catalog, O1740 dynamic pool routing, ESXi/vSAN health, UniFi/Traefik DNS, and 6-queue backlog orchestration via the universal boylenet-infra MCP server (/home/mboyle/bin/bd-boylenet-infra-mcp.py).
---

# Boylenet Autonomous Infrastructure Skill (`boylenet-autonomous-infra`)

Use this skill whenever an agent on **Claude Code (`A/B/C/D` & `claude-local`)**, **OpenAI Codex (`codex`)**, **Moonshot Kimi (`kimi`)**, **Google Antigravity (`AGY`)**, or the **Local GPU Coding Agent (`bd-local-coding-agent`)** needs to autonomously inspect, command, test, or heal any component of the 27-node Boylenet cluster.

## Critical Benchmark Protection Invariant
- **NEVER** run inference, load weights, or restart `llama-server` on `.72` (`10.0.70.72`) or `.83` (`10.0.70.83`) while `Agent-37`'s `bench_worker.py` / `llama-bench` is running.
- All local coding turns and raw LLM calls automatically route to BattleStation `10.0.10.137:11434` (`qwen2.5-coder:7b-16k` on RTX 2080 Ti at ~95 tok/s) with zero contention.

## Universal MCP Server & CLI Invocation
Every tool is available both via native MCP (`boylenet-infra` / `boylenet_infra`) and via direct CLI:
```bash
/home/mboyle/bin/bd-boylenet-infra-mcp.py --cli <tool_name> '<json_args>'
```

## The 20 Autonomous Infrastructure Tools
1. `vm_exec` — Execute shell command on any of the 27 Boylenet VMs (`10.0.70.*` / `10.0.10.137`) via `:4079/vm/<vm>/execute`.
2. `vm_browse_files` — List or read files across all 27 VMs via `:4079/vm/all/files/list` or `/files/read`.
3. `local_coding_agent_fix` — Dispatch `$0` Local Coding Agent (`/home/mboyle/bin/bd-local-coding-agent`) with indentation-normalized `guarded_edit` + multi-turn `ruff`/`mypy`/`bd-pytest-digest` self-healing in `/home/mboyle/bd-local-wt/`.
4. `ramdisk_pytest_digest` — Run `/home/mboyle/bin/bd-pytest-digest` on `.82` (`10.0.70.82` 64-core `/dev/shm` ramdisk, Rule 78 `<=3 lines, <25 tokens`).
5. `browser_oracle_query` — Query Dual Browser Oracles (`10.0.10.137:9222` BattleStation & `10.0.70.181:9222` Bittorrent / `/home/mboyle/bin/bd-oracle`).
6. `browser_oracle_cdp_inspect` — Connect via CDP to `.137:9222` or `.181:9222` to verify DOM, console errors, `scrollWidth <= clientWidth`, and 60fps animations.
7. `bd_kb_search` — Search the 6-Volume Boylenet & BulkDownloader Master Encyclopedia (`:4079/api/tool/bd_kb_search`) in `<20ms`.
8. `qdrant_hivemind_search` — Semantic vector search across Qdrant `bd_master_kb`, `boylenet_fleet_rag`, and `boylenet_episodic_memory` on `10.0.70.125:6333`.
9. `qdrant_hivemind_store` — Store a verified lesson or episodic memory into Qdrant (`10.0.70.125:6333`) with 1024-dim BGE-M3 embeddings.
10. `model_vault_catalog_and_switch` — List all 86 Vault Models (`🟢 LOCAL` vs `☁️ CLOUD`, `tok/s`) or switch GPU profiles via `:4010` / `:4084`.
11. `raw_unrestricted_llm_call` — Run `/home/mboyle/bin/bd-raw-ai` (zero system prompt, zero hooks, zero rules) on BattleStation `.137:11434` or cloud harnesses.
12. `airgap_control` — Check or verify `/home/mboyle/bin/bd-airgap status|verify` (WAN airgap with RFC1918 LAN preservation).
13. `pool_quota_router` — Read `/home/mboyle/bd-persist/POOL_STATE.tsv` and resolve O1740 optimal pool/model (`command_squad`, `heavy_lifter`, `lightweight_investigator`).
14. `spawn_cross_pool_subagent` — Launch background task across `claude-a..d`, `codex`, `kimi`, `agy`, or `local` via `/home/mboyle/bin/bd-ai-harness` or `:4098`.
15. `vsan_esxi_cluster_status` — Inspect `esxi01..04` vSAN Disk Groups (`107 TB`), resync (`0 GB`), SMART health, and 25GbE VLAN 75 status.
16. `unifi_dns_traefik_status` — Query UniFi static DNS (`398+` records) and Traefik `*.boylenet.themfboyles.com` ingress routes.
17. `openwebui_tool_gateway_call` — Call any of the 51 OpenWebUI Toolkits or 8 Pipelines on `:4079`.
18. `gitea_github_repo_sync` — Check status or sync the 5 Boylenet repos on local Gitea (`10.0.70.164:3000/mboyle/*`) and GitHub (`github.com/mcboyle/*`).
19. `sentinel_doctor_autoheal` — Run `:4081/api/doctor-run` and `:4099/api/status` across all Boylenet services.
20. `queue_backlog_status` — Inspect open/pending rows across all 6 Boylenet backlog queues (`O1670`, `P3-LENS`, `APP-FEATURE`, `BH1`, `P2-FIX`, `APP-DL-FIX`).
