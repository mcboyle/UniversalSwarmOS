# 🌐 BD-KB 06: 5-Platform `boylenet-infra` MCP, Mods 1–5 (`bd-swarm-mod`), NGINX/Cloudflare HTTPS & 215/215 Backlog Ledger

- **Document ID**: `bd-kb-06-5platform-mcp-mods-https-215-ledger`
- **Native KB ID**: `bd-kb-5platform-mods`
- **Canonical Path**: `/home/mboyle/bd-persist/bd-kb/06-5PLATFORM-MCP-MODS-HTTPS-AND-215-LEDGER.md`
- **Campaign**: `O1789` ("Double It and the 115 Approved" — 30-Swarm Full-Cluster & 5-Platform Architecture)
- **Scope**: Authoritative reference for the 20-tool `boylenet-infra` MCP server (`/home/mboyle/bin/bd-boylenet-infra-mcp.py`), Autonomous Swarm Mods 1–5 (`/home/mboyle/bin/bd-swarm-mod`), 22 Cross-Platform Slash Commands & Skills across Claude Code, OpenAI Codex CLI, Kimi K2.8 CLI, Antigravity (AGY), and OpenWebUI (`:8090` / `:8080`), `.83:18080` `Qwen3.6-35B-A3B-Heretic` + `.137:11434` `RTX 2080 Ti` $0 Local Coding Pool, NGINX `:443` + Let's Encrypt Cloudflare DNS-01 HTTPS Termination, and the `215/215` (`100%`) Reconciled Backlog Ledger.

---

## 1. Universal 20-Tool `boylenet-infra` MCP Server (`/home/mboyle/bin/bd-boylenet-infra-mcp.py`)

The `boylenet-infra` MCP server exposes all 27 Boylenet cluster nodes, local GPU coding pools, 64-core ramdisk test execution, dual Chrome CDP browser oracles, Qdrant vector RAG, and 6-queue backlog orchestration through a single zero-dependency JSON-RPC 2.0 stdio + CLI bridge (`/home/mboyle/bin/bd-boylenet-infra-mcp.py`).

### 1.1 5-Platform Registration Matrix

| Platform | Configuration Path | Invocation Mechanism | Status |
|---|---|---|---|
| **Claude Code (Pools A & B)** | `/home/mboyle/.claude.json` (`mcpServers.boylenet-infra`) | Native MCP stdio + `~/.claude/commands/*.md` | `ACTIVE` |
| **OpenAI Codex CLI (Pool C)** | `/home/mboyle/.codex/config.toml` (`[mcp_servers.boylenet-infra]`) | Native MCP stdio + `~/.codex/prompts/*.md` | `ACTIVE` |
| **Kimi K2.8 CLI (Pool E)** | `/home/mboyle/.kimi/mcp.json` (`mcpServers.boylenet-infra`) | `kimi --mcp-config-file ~/.kimi/mcp.json` + `~/.kimi/skills/` | `ACTIVE` |
| **Google Antigravity (Pool D)** | `/home/mboyle/.gemini/antigravity-cli/mcp/boylenet-infra/*.json` | `call_mcp_tool(ServerName="boylenet-infra", ...)` + 20 JSON schemas | `ACTIVE` |
| **OpenWebUI (`:8090` & `:8080`)** | `/home/mboyle/bin/bd-openwebui-tool-gateway.py` (`:4079`) | OpenAPI 3.1 Tool Server (`/openapi/infra.json` & `/tools/{tool}/call`) | `ACTIVE` |

### 1.2 Complete 20-Tool Catalog (`boylenet-infra`)

| # | Tool Name | Primary Backend / Target | Purpose & Safety Invariants |
|---:|---|---|---|
| 1 | `vm_exec` | `:4079/vm/<vm>/execute` (27 VMs) | Execute shell commands across any of the 27 Boylenet VMs; enforces `.72`/`.83` benchmark protection guard (`INFERENCE_DANGER_PATTERNS`). |
| 2 | `vm_browse_files` | `:4079/vm/<vm>/files/list|read` | Non-destructive directory listing and file reading across all 27 VMs (`/vms` NFS mesh or per-node paths). |
| 3 | `local_coding_agent_fix` | `/home/mboyle/bin/bd-local-coding-agent.py` | Dispatch $0 Local GPU Coding Agent (`--backend auto|t4-heretic|2080ti`) in `/home/mboyle/bd-local-wt/` with `apply_guarded_edit` and multi-turn `ruff` + `mypy` + `bd-pytest-digest` self-healing. |
| 4 | `ramdisk_pytest_digest` | `10.0.70.82` (`/dev/shm/bd-ramdisk-pytest`) | Run `bd-pytest-digest` on `.82` (`wrk-test04`, 64 vCPUs, 96 GB RAM) in `/dev/shm` tmpfs (`0.0%` iowait on `.164`) with automatic local fallback. |
| 5 | `browser_oracle_query` | `/home/mboyle/bin/bd-oracle` (`.137` & `.181`) | Fan out prompts to Gemini, ChatGPT, Claude A, and Claude B via Windows Chrome CDP (`10.0.10.137:9222` & `10.0.70.181:9222`) at `$0` marginal API cost (Rule 79). |
| 6 | `browser_oracle_cdp_inspect` | `.137:9222` & `.181:9222` + `:4080`–`:4099` | Live Chrome CDP tab census + E2E portal health and latency probe across all Boylenet web portals. |
| 7 | `bd_kb_search` | `/home/mboyle/bd-persist/bd-kb/*.md` + `:6333` | Sub-20ms hybrid vector (`1024-d` Cosine in Qdrant `bd_master_kb`) + lexical search across all Volumes (`00`–`06`) of the Boylenet Master Knowledge Base. |
| 8 | `qdrant_hivemind_search` | `http://10.0.70.125:6333` (Qdrant) | Semantic vector search across `bd_master_kb`, `boylenet_episodic_memory`, `fleet_lessons_hivemind`, `boylenet_fleet_rag`, `boylenet_codebase_ast`, and `swarm_docs_rag`. |
| 9 | `qdrant_hivemind_store` | `http://10.0.70.125:6333` (Qdrant) | Store verified engineering lessons and debugging episodes into Qdrant (`fleet_lessons_hivemind` / `boylenet_episodic_memory`) per Rule 25. |
| 10 | `model_vault_catalog_and_switch` | `:4084/api/models` & `:4010/v1/models` | Query all 86 Local Vault models (`8.9+ TB` GGUFs) + 12 Cloud models and benchmark `tok/s`; guards GPU profile switching when `bench_worker.py` is active. |
| 11 | `raw_unrestricted_llm_call` | `/home/mboyle/bin/bd-raw-ai` | Zero-system-prompt, zero-hook raw LLM execution across `.83:18080` (`Qwen3.6-35B-A3B-Heretic`), `.137:11434` (`RTX 2080 Ti`), `:4000` (`LiteLLM`), or cloud harnesses. |
| 12 | `airgap_control` | `/home/mboyle/bin/bd-airgap` + `:4095` | Inspect or toggle `bd-airgap` (`status|on|off`) and verify sovereign local-only operational readiness. |
| 13 | `pool_quota_router` | `/home/mboyle/bd-persist/POOL_STATE.tsv` | Resolve dynamic pool assignment (`command_squad`, `heavy_lifter`, `lightweight_investigator`) per Operator Directive O1740 and Rule 6. |
| 14 | `spawn_cross_pool_subagent` | `/home/mboyle/bin/bd-subagent-router.sh` | Launch or dry-run a cross-pool subagent across Claude, Codex, Kimi, AGY, or Local GPU (`t4-heretic` / `2080ti`) with O1740 ledger logging. |
| 15 | `vsan_esxi_cluster_status` | `:4080/api/hardware` & `:4088/api/vsan-storage` | Inspect 4x HPE DL380 Gen10 ESXi hosts (`.121`, `.122`, `.140`, `.143`), `107 TB` All-NVMe vSAN, `25GbE` RoCE vmk1/vmk2, and `12U` rack thermals (`79.5°F`). |
| 16 | `unifi_dns_traefik_status` | `:4089` + `10.0.0.1` + `:443` | Audit `.boylenet.themfboyles.com` DNS resolution, NGINX/Traefik `:443` TLS termination, and UniFi UDM Pro gateway telemetry. |
| 17 | `openwebui_tool_gateway_call` | `http://10.0.70.164:4079/tools/{name}/call` | Proxy any of the 50 native OpenWebUI toolkits hosted on `:4079` (`core`, `infra`, `rag`, `coding`, `fleet`). |
| 18 | `gitea_github_repo_sync` | `:4090/api/git-repos` & `:3000` | Audit synchronization status across all 8 Git repositories in `/home/mboyle/git-repos/*`, local Gitea (`:3000`), and GitHub (`mcboyle/*`). |
| 19 | `sentinel_doctor_autoheal` | `:4094/api/sentinel-healer` & `bd-doctor` | Inspect autonomous self-healing watchdog events, HUB-GATE (`<20%` iowait), and systemd service health. |
| 20 | `queue_backlog_status` | `/home/mboyle/bd-persist/*.tsv` | Live census and reconciliation across all 6 Boylenet queues (`215/215` total rows: `P3-LENS`, `BH1`, `BH2`, `P2-FIX`, `APP-DL-FIX`, `O1670`). |

---

## 2. Autonomous Swarm Mods 1–5 (`/home/mboyle/bin/bd-swarm-mod`)

`bd-swarm-mod` (`/home/mboyle/bin/bd-swarm-mod.py`, symlinked at `/home/mboyle/bin/bd-swarm-mod`) unifies five autonomous productivity and token-saving mods across Claude Code, Codex, Kimi, Antigravity, and OpenWebUI:

### 2.1 Mod Architecture & Measured Benchmarks

| Mod | Command / Hook Entrypoint | Target Budget / SLA | Measured Performance | Core Behavior |
|---|---|---|---|---|
| **Mod 1: Pre-Turn Context Injector** | `bd-swarm-mod pre-turn --compact` | `<100 tokens` (`<25ms`) | **`42 tokens`** (`168 chars`, `~11ms`) | Injects live O1740 `POOL_STATE.tsv`, `.164` load/iowait (`HUB-GATE`), active local GPU coder endpoint (`.83:18080` `Qwen3.6-Heretic` + `.137:11434` `2080 Ti`), and `215/215` queue status. |
| **Mod 2: Post-Edit Ramdisk Gate** | `bd-swarm-mod post-edit --file <py>` | `<4.0s` (`<=3 lines`, `<25 tok`) | **`0.48s–1.85s`** (`1 line`, `9 tokens`) | Runs `ruff check` + `mypy` + `.82` 64-core `/dev/shm` ramdisk `bd-pytest-digest` automatically on edited `.py` files inside `/home/mboyle/bd-local-wt/` or `/home/mboyle/bd-cuts/`. |
| **Mod 3: Rule 25 HiveMind Auto-Publisher** | `bd-swarm-mod publish-lesson --title ...` | `<250ms` dual-index | **`38ms`** (`1024-d` Cosine upsert) | Automatically embeds (`hybrid-bge-m3-384d-plus-lexical-640d`) and upserts verified lessons into Qdrant `fleet_lessons_hivemind` + `bd_master_kb` + `/home/mboyle/bd-persist/hivemind-lessons.jsonl`. |
| **Mod 4: OpenWebUI Inlet & 1-Click Actions** | `bd-swarm-mod owui-inlet` / `owui-action` | `<30ms` RAG injection | **`14ms`** (`top-3` chunks injected) | Automatically enriches technical OpenWebUI prompts on `:8090` / `:8080` with top-3 `BD KB` + HiveMind chunks and provides 3 one-click action buttons (` Verify on .82 Ramdisk`, `🤖 Fix with Local GPU`, `📚 Save to HiveMind`). |
| **Mod 5: Unified Swarm Mod CLI** | `bd-swarm-mod status` / `--all-checks` | `<3.0s` full self-test | **`1.42s`** (`all_mods_passed: true`) | Single CLI & JSON diagnostic verifier across all 5 platforms (`Claude`, `Codex`, `Kimi`, `AGY`, `OpenWebUI`). |

---

## 3. 22 Cross-Platform Slash Commands, Prompts & Skills + `.83:18080` `Qwen3.6-Heretic` Wire-Up

### 3.1 Live `.83:18080` `Qwen3.6-35B-A3B-Heretic` Coding Pool (Swarm `#022`)
- **Node `.83` (`10.0.70.83`, Dual NVIDIA Tesla T4 32GB GDDR6)** completed `37/37` GGUF benchmarks (`100%`) and hosts `Qwen3.6-35B-A3B-Heretic-Q4_K_M.gguf` Always-Warm on `http://10.0.70.83:18080/v1/chat/completions` (`--chat-template-kwargs '{"enable_thinking":false}'`).
- **Smart Backend Selector (`/home/mboyle/bin/bd-local-coding-agent.py`)**:
  - Probes `.83` (`10.0.70.83`) first via SSH process table.
  - When `.83` has `0` `bench_worker.py` / `llama-bench` processes and `http://10.0.70.83:18080/v1/chat/completions` is online, both `--backend t4-heretic` and `--backend auto` route directly to **`.83:18080` (`Qwen3.6-35B-A3B-Heretic`)** with **zero SSH or HTTP touch on `.72`** while `.72` finishes `kimi-k3-abliterated-iq1s-gguf`.
  - BattleStation `.137:11434` (`qwen2.5-coder:7b-16k` on RTX 2080 Ti 11GB) remains hot-standby via `--backend 2080ti` (`~95 tok/s`).

### 3.2 Cross-Platform Slash Command & Skill Inventory (22 Entrypoints)

1. **Claude Code Slash Commands (`/home/mboyle/.claude/commands/*.md`)**:
   - `/boylenet-infra` — Execute any of the 20 `boylenet-infra` MCP tools or cluster diagnostics
   - `/local-code-fix` — Dispatch `bd-local-coding-agent` (`t4-heretic` on `.83:18080` or `2080ti` on `.137:11434`)
   - `/ramdisk-pytest` — Run `<4s` 64-core `.82` `/dev/shm` ramdisk pytest digest
   - `/bdkb` — Query Volumes `00`–`06` of the Master `BD KB` and Qdrant `bd_master_kb`
   - `/oracle-e2e` — Run Dual Chrome CDP Browser Oracle (`.137:9222` & `.181:9222`) E2E verification
   - `/swarm-mod` — Run `bd-swarm-mod` (`pre-turn`, `post-edit`, `publish-lesson`, `status`)
2. **OpenAI Codex CLI Prompts (`/home/mboyle/.codex/prompts/*.md`)**:
   - `boylenet-infra.md`, `local-code-fix.md`, `ramdisk-pytest.md`, `bdkb.md`, `oracle-e2e.md`, `swarm-mod.md`
3. **Kimi K2.8 CLI Skills (`/home/mboyle/.kimi/skills/*/SKILL.md`)**:
   - `boylenet-autonomous-infra`, `boylenet-4platform-bridge`, `boylenet-bdkb-hivemind`, `boylenet-dual-oracle-e2e`, `boylenet-infra-commander`, `boylenet-local-coding-agent`, `bd-swarm-mod`, `bd-o1670-backlog-burndown`, `bd-p2-appdl-verifier`, `bd-backlog-reconciler`
4. **Google Antigravity (AGY) Skills (`/home/mboyle/.agents/skills/*/SKILL.md`)**:
   - Mirrors all 10 Boylenet autonomous skills above plus `bd-oracle-suite-e2e`, `boylenet-autonomous-mods`, `boylenet-architect`, `fleet-satellite-orchestration`, and `fleet-gridlock-recovery`.

---

## 4. NGINX `:443` + Let's Encrypt Cloudflare DNS-01 HTTPS & Traefik Routing Architecture

### 4.1 Wildcard TLS Certificate & Renewal Pipeline
- **Domain Namespace**: `*.boylenet.themfboyles.com` + `boylenet.themfboyles.com`
- **ACME Challenge Method**: Let's Encrypt **Cloudflare DNS-01** (`certbot` / `acme.sh` with `dns_cloudflare` plugin) so internal RFC1918 endpoints (`10.0.70.0/24` and `10.0.10.0/24`) receive browser-trusted TLS certificates without exposing ports `:80`/`:443` to the public WAN.
- **Certificate Storage on `.164` (`controller`)**:
  - Staging / Self-Signed Fallback & Live Cert Symlinks: `/etc/nginx/ssl/boylenet/` (`fullchain.pem`, `privkey.pem`) and `/etc/letsencrypt/live/boylenet.themfboyles.com/`
  - Reverse Proxy Configs: `/etc/nginx/sites-available/boylenet-https.conf` (NGINX `:443` HTTP/2 + WebSocket upgrade `Upgrade`/`Connection` headers for all `:4080`–`:4099`, `:8090`, `:8080`, `:3000`, `:4000`, `:4010`, `:6333` backends).

### 4.2 Canonical `*.boylenet.themfboyles.com` HTTPS Virtual Host Map

| FQDN | Backend Target | Protocol / Features |
|---|---|---|
| `https://portal.boylenet.themfboyles.com` | `http://10.0.70.164:4080` | 165-View Unified NOC Portal (SSE + WebSocket + 60fps canvas) |
| `https://openwebui.boylenet.themfboyles.com` | `http://10.0.70.164:8090` | Primary OpenWebUI Controller (`112` models, `50` toolkits, `BD KB`) |
| `https://ai-webui.boylenet.themfboyles.com` | `http://10.0.70.72:8080` | Secondary OpenWebUI Vault A (`1:1` synced with `:8090`) |
| `https://litellm.boylenet.themfboyles.com` | `http://10.0.70.164:4000` | LiteLLM Unified OpenAI/Anthropic Router (`sk-fleet-local`) |
| `https://orchestrator.boylenet.themfboyles.com` | `http://10.0.70.164:4010` | Sovereign Local AI Gateway & 4-GPU Orchestrator |
| `https://storefront.boylenet.themfboyles.com` | `http://10.0.70.164:4084` | 86-Model AI Vault Storefront & Benchmark Explorer |
| `https://qdrant.boylenet.themfboyles.com` | `http://10.0.70.125:6333` | Qdrant Vector RAG Engine (`bd_master_kb` + 5 collections) |
| `https://gitea.boylenet.themfboyles.com` | `http://10.0.70.164:3000` | Local Gitea Git Server (`mcboyle/BD`) |
| `https://langfuse.boylenet.themfboyles.com` | `http://10.0.70.228:3000` | Langfuse LLM Trace & Spend Observability |

---

## 5. Complete `215/215` (`100.0%`) Reconciled Backlog Ledger

All **215** backlog rows across the 6 authoritative Boylenet TSV queues have been audited, verified against live Git commit/blob SHAs and `.82` 64-core `/dev/shm` ramdisk pytest gates, and reconciled to `100.0%` completion:

| # | Queue File | Total Rows | Terminal / Verified (`LANDED` / `MERGED` / `VERIFIED`) | Open / Unverified | Verification Runner & Receipt |
|---:|---|---:|---:|---:|---|
| 1 | `/home/mboyle/bd-persist/P3-LENS-QUEUE.tsv` | `80` | **`80` (`100.0%`)** | `0` | `bd-backlog-reconciler` (`AGENT109` / `AGENT114`) |
| 2 | `/home/mboyle/bd-persist/BH1-BACKLOG-QUEUE.tsv` | `15` | **`15` (`100.0%`)** | `0` | `bd-backlog-reconciler` (`15/15` `MERGED`) |
| 3 | `/home/mboyle/bd-persist/BH2-BUILD-QUEUE.tsv` | `22` | **`22` (`100.0%`)** | `0` | `bd-backlog-reconciler` (`22/22` `LANDED`) |
| 4 | `/home/mboyle/bd-persist/P2-FIX-QUEUE.tsv` | `20` | **`20` (`100.0%`)** | `0` | `bd-p2-appdl-verifier` (`20/20` `LANDED` + `PATCH-SHA256`) |
| 5 | `/home/mboyle/bd-persist/APP-DL-FIX-QUEUE.tsv` | `9` | **`9` (`100.0%`)** | `0` | `bd-p2-appdl-verifier` (`9/9` `LANDED`/`VERIFIED_NO_OP`) |
| 6 | `/home/mboyle/bd-persist/O1670-QUEUE.tsv` | `69` | **`69` (`100.0%`)** | `0` | `/home/mboyle/bin/bd-o1670-backlog-runner.py` (`69/69` `VERIFIED`) |
| **Total** | **6 Authoritative Fleet Queues** | **`215`** | **`215` (`100.0%`)** | **`0`** | **100% Zero-Backlog Certification (`O1789`)** |
