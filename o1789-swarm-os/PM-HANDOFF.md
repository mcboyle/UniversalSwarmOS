# MASTER PM HANDOFF (`O1789`) — AGY-Council (`Agent-101`) -> `bd-pm-B` (Remote-Control PM) & Command Squad

- **WRITTEN-AT**: `2026-10-18T20:52:00Z`
- **CAMPAIGN**: `O1789` (Boylenet 27-Node Hardware/vSAN/25GbE Upgrade, 86-Model Dual-Vault, 165-View 60fps Swarm OS, OpenWebUI 50-Toolkit Super-Suite & Dual-Platform Git Publication)
- **ACTIVE PM SEAT**: `bd-pm-B` (`--remote-control`, Pool B `OK` `0%` 5h / `19%` wk)
- **COMMAND SQUAD NODES**: `.51` (`wrk-test01` / Integrator), `.194` (`wrk-test05` / Dispatcher & LensRouter), `.85` (`wrk-test06` / Audit & Adjudicator), `.52` (`wrk-test02` / Trainer & Usage Sentinel)
- **CRITICAL HARDWARE INVARIANT**: **DO NOT INTERRUPT, RESTART, OR CONTEND WITH `Agent-37`'S ACTIVE `llama-bench` / `ggml-rpc-server` BENCHMARK SWEEP ON `.72`, `.83`, `.125`, OR `.228`!** (`77/87` models completed; final `10` heavyweight models actively running on `.72+.228` and `.83+.125`).

---

## 1. Published GitHub & Local Gitea Multi-Repository Matrix (`O1789` Secret-Sanitized)

All Boylenet Swarm OS code, systemd units, OpenWebUI Super-Suite gateways/pipelines/exports, the 6-Volume Master `BD KB`, `157+` O1789 verification receipts, and sanitized infrastructure configurations are committed and pushed to **both** GitHub (`mcboyle`) and Local Gitea (`10.0.70.164:3000/mboyle`) with `BOYLENET_SECRET_GUARD` pre-commit scrubbing:

| Repository | GitHub URL (`mcboyle`) | Local Gitea URL (`10.0.70.164:3000/mboyle`) | Local Staging Path | Tracked Files | Head Commit SHA (`main`) |
|---|---|---|---|---:|---|
| **`boylenet-swarm-os`** | `https://github.com/mcboyle/boylenet-swarm-os` | `http://10.0.70.164:3000/mboyle/boylenet-swarm-os` | `/home/mboyle/git-repos/boylenet-swarm-os` | `200` | `8c28f72cc2f8` |
| **`boylenet-openwebui-supersuite`** | `https://github.com/mcboyle/boylenet-openwebui-supersuite` | `http://10.0.70.164:3000/mboyle/boylenet-openwebui-supersuite` | `/home/mboyle/git-repos/boylenet-openwebui-supersuite` | `15` | `e8d2758b7c22` |
| **`boylenet-bd-kb-and-receipts`** | `https://github.com/mcboyle/boylenet-bd-kb-and-receipts` | `http://10.0.70.164:3000/mboyle/boylenet-bd-kb-and-receipts` | `/home/mboyle/git-repos/boylenet-bd-kb-and-receipts` | `170` | `340d8f3249cd` |
| **`boylenet-infra-configs`** | `https://github.com/mcboyle/boylenet-infra-configs` | `http://10.0.70.164:3000/mboyle/boylenet-infra-configs` | `/home/mboyle/git-repos/boylenet-infra-configs` | `18` | `00f546673ef1` |
| **`UniversalSwarmOS`** | `https://github.com/mcboyle/UniversalSwarmOS` | `http://10.0.70.164:3000/mboyle/UniversalSwarmOS` | `/home/mboyle/git-repos/UniversalSwarmOS` | `922` | `e426727077bb` |

---

## 2. 86-Model Dual-Vault (`8.9 TB` on `.72` & `.83`), Category Champions & `Agent-37` Sweep Status

1. **Dual-Vault Inventory (`100%` Mirrored Across AI Vault A `.72` & AI Vault B `.83`)**:
   - **Total Model Directories**: **`86 / 86`** (`8.9 TB` total weights on NVMe/vSAN)
   - **LiteLLM Router (`.164:4000` & `.228:4000`)**: **`228`** live routed model aliases (`/home/mboyle/infra/support-layer/litellm/config.yaml`)
   - **OpenWebUI Catalog (`.164:8090` & `.72:8080`)**: **`260`** models with explicit **`🟢 LOCAL [FREE • AIRGAP]`** (`198`) vs **`☁️ CLOUD [PAID WAN]`** (`62`) badges
2. **Measured `llama-bench` (`b11716`) Category Champions**:
   - **Flagship Uncensored Coding & Reasoning (35B MoE)**: **`Qwen3.6-35B-A3B-Heretic`** (`qwen3.6-35b-a3b-heretic`) — **`103.59 tok/s` prefill (`pp512`) / `24.16 tok/s` decode (`tg128`)** on 1x T4 + Skylake AVX-512 (`795.0 tok/s` pp / `65.8 tok/s` tg on 2x T4)
   - **High-Throughput Local Coding (30B MoE)**: **`Qwen3-Coder-30B-A3B-Instruct-Q4_K_M`** (`tier1-qwen3-coder-30b-a3b`) — **`848.90 tok/s` prefill / `77.62 tok/s` decode** on 2x T4 Pool Alpha
   - **Offensive Security & Binary/Packet Analysis (35B MoE)**: **`Huihui-CyberStrike-OffSec-35B-abliterated-Q4_K_M`** (`cyberstrike-35b`) — **`799.00 tok/s` prefill / `66.47 tok/s` decode** on 2x T4
   - **100B+ Frontier Hybrid MoE**: **`GLM-4.5-Air-REAP-82B-A12B-Heretic-Q4_K_M`** (`106B.A12B`) — **`30.02 tok/s` prefill / `6.40 tok/s` decode** on 1x T4 + Skylake AVX-512 (`-ot exps=CPU, ngl=99`); **`NVIDIA-Nemotron-3.5-Bolt-74B-A9B`** — **`29.18 tok/s` pp / `13.46 tok/s` tg**
   - **Speculative Drafter & Ultra-Fast 9B/10B**: **`Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0`** (`1,005.86 tok/s` pp / `21.39 tok/s` tg) & **`DeepSeek-V4-Flash-0731-Q8_0`** (`680.20 tok/s` pp / `61.50 tok/s` tg)
   - **1-Trillion Parameter Frontier**: **`KIMI-K3-MXP4-DERISKED-Q2_K`** (`940.18 GiB`, 38 shards) — **`69.13 tok/s` pp / `16.30 tok/s` tg** across 4-Node `1.73 TB` DDR4 + 4x T4 Hybrid
3. **`Agent-37` Benchmark Sweep Status (DO NOT INTERRUPT)**:
   - **Progress**: **`77 / 87` (`88.5%`) completed** (`60` real-weight GGUF `llama-bench` configurations `rc=0` + `17` non-GGUF Safetensors/ONNX/Diffusers models validated).
   - **Remaining**: **`10` ultra-heavyweight models** (`5` on `.72` + `5` on `.83`), currently benchmarking `nemotron-3-ultra-550b-a55b` (`188.3 GiB`) on `.72+.228` and `ling-3.1-flash-564b` (`203.1 GiB`) on `.83+.125`.
   - **Receipt**: `/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/AGENT37-NEW-FRONTIER-MODELS-BENCHMARK-RECEIPTS.md`.

---

## 3. Raw Unrestricted AI CLI (`/home/mboyle/bin/bd-raw-ai`) & 100% Kernel WAN Airgap (`/home/mboyle/bin/bd-airgap`)

1. **`/home/mboyle/bin/bd-raw-ai` (Zero-Guardrail Direct Heretic/Abliterated Launcher)**:
   - Connects directly to local `ik_llama.cpp` (`b11716`) endpoints on `.72`, `.83`, and `.125` with zero system-prompt filtering, zero proxy inspection, and zero cloud egress.
   - Commands: `bd-raw-ai "<prompt>"`, `bd-raw-ai --cyber "<prompt>"`, `bd-raw-ai --reason "<prompt>"`, `bd-raw-ai --list`.
2. **`/home/mboyle/bin/bd-airgap` + `:4085` Top-Bar Toggle (3-Layer Hardware/Kernel WAN Lock)**:
   - **Layer 1**: Kernel `iptables OUTPUT` & `DOCKER-USER` chains blocking all non-RFC1918 WAN traffic (`10.0.0.0/8`, `127.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` whitelisted).
   - **Layer 2**: LiteLLM (`:4000`) routing lock (`🟢 LOCAL [FREE • AIRGAP]` models only).
   - **Layer 3**: Cloud Burst Orchestrator (`:4090`) budget lock (`AIRGAP-LOCKED`).
   - Commands: `bd-airgap status`, `bd-airgap on`, `bd-airgap off`, or click the **`🛡️ WAN AIRGAP`** pill in the Unified OS Shell (`http://10.0.70.164:4085`).

---

## 4. OpenWebUI Maximum-Power Super-Suite (`:8090` / `.72:8080` + `:4079` Universal Gateway)

Deployed in 100% parity on Controller (`http://10.0.70.164:8090` / `http://openwebui.boylenet.themfboyles.com`) and AI Vault A (`http://10.0.70.72:8080` / `http://ai-webui.boylenet.themfboyles.com`):

1. **`260` Explicitly Labeled Models**: `198` `🟢 LOCAL [FREE • AIRGAP]` + `62` `☁️ CLOUD [PAID WAN]`.
2. **`50` Native Python Toolkits (`tk_01`..`tk_50`) + `5` OpenAPI 3.1 Tool Servers (`39` REST Endpoints)**:
   - Covers file/AST/git, Gitea/GitHub PRs, SearXNG/ArXiv/Wiki, Chrome CDP Oracles (`.137:9222` & `.181:9222`), 14 MCP servers, VMware ESXi/vSAN, UniFi 25GbE, `/dev/shm` Ramdisk Pytest, Z3 SMT prover, eBPF profiler, and `BD KB` search.
3. **`128` Agent Skills + `128` Slash Command Prompts**: Full fleet skill catalog accessible via `/` commands in chat.
4. **`8` Valve-Configurable Pipelines + `12` Active Global Functions (`20` Total)**:
   - Includes `bd_smart_o1740_intent_router_pipeline`, `bd_kb_auto_grounding_pipeline`, `bd_rule22_airgap_dlp_shield_pipeline`, `bd_multi_agent_council_consensus_pipeline`, `bd_autonomous_code_and_pytest_pipeline`, `bd_deep_research_multi_engine_pipeline`, `bd_multimodal_flux_vision_voice_pipeline`, and `bd_langfuse_caveman_telemetry_filter`.
5. **`11` Dedicated Local Multimodal Image & Speech Models**:
   - `6` Local Image/Vision generators (`/static/generated/<id>.png` 1080p studio) + `5` Local Neural Speech TTS/STT models (`Kokoro-82M`, `Piper`, `Faster-Whisper-Large-v3`).
6. **`6-Volume Master BD KB` + `5` Qdrant 1024-Dim Vector Collections (`11` Knowledge Bases)**:
   - Authored in `/home/mboyle/bd-persist/bd-kb/00..05-*.md` + `manifest.json`, indexed in Qdrant (`http://10.0.70.125:6333/collections/bd_master_kb`, 28 chunks, 1024-d BGE-M3 hybrid vectors), and attached natively to OpenWebUI models.
7. **`28` Interactive Open Terminal VM Connections (`/vm/<hostname>`)**:
   - Live interactive shell + file browser inside OpenWebUI for all `27` Boylenet VMs (`hub-mesh01`, `ai-srv01`, `aidev`, `ai-infer01`, `ai-ollama01`, `wrk-test01..07`, `spr-pool01..12`, etc.) plus the `64-Core CI Ramdisk` (`/dev/shm/bd-openwebui-ci-ramdisk`).

---

## 5. Live 60fps 165-View HiveMind/CoT/Rack/Military Visualizer (`:4088`) & Unified OS Shell (`:4085`)

1. **Unified Boylenet OS Shell (`http://10.0.70.164:4085` / `http://os.boylenet.themfboyles.com`)**:
   - Single-pane top navigation bar across all Boylenet apps, `Ctrl+K` global command omnibar, `~` slide-down Quake Web Terminal drawer (`:4083`), and 1-click WAN Airgap toggle.
2. **165-View Live 60fps Visualizer (`http://10.0.70.164:4088` / `http://topology.boylenet.themfboyles.com`)**:
   - **`V01`–`V100`**: 100 live 60fps HiveMind Chain-of-Thought (CoT) agent movement & reasoning views.
   - **`T01`–`T65`**: 65 live 60fps 3D Topology, 12U 36-inch Physical Rack Digital Twins, vSAN NVMe, 25GbE SFP28, and Military/Sci-Fi Mission Control views.
   - **Wallboard & Gallery**: `/wallboard` (`2x2` / `3x2` auto-cycling NOC display) and `/gallery` (`179` rendered previews with 1-click `🚀 Launch Live 60fps` and `⭐ Set Preferred` persistence).

---

## 6. Immediate Operational Orders for Incoming PM (`bd-pm-B`) & Command Squad (`.51`, `.194`, `.85`, `.52`)

### Order 1: Refresh Stale Platform Usage Across All Pools (FIRST ACTION)
Before dispatching heavy lifters, Command Squad usage/telemetry agents on `.51`, `.194`, `.85`, and `.52` MUST refresh stale quota observations in `/home/mboyle/bd-persist/POOL_STATE.tsv`:
1. Refresh **AGY** (`gemini 5h/wk`, `claude+gpt 5h/wk`), **Claude Pools A/B/C/D** (`bd-usage-a-A`, `bd-usage-b-B`, `bd-usage-c-C`, `bd-usage-d-D`), **Codex** (`codex rate_limits`), **Kimi** (`/usage`), and **Local GPU/MoE** (`local`) rows in `/home/mboyle/bd-persist/POOL_STATE.tsv`.
2. Verify `/home/mboyle/bd-persist/POOL_STATE.tsv` timestamps are `< 120s` old before resolving pools under **Directive O1740** (Rule 6: `UNKNOWN` is never permission).

### Order 2: Start Remaining Queue & Launch Task Rows (`O1740` Dynamic Capability Routing)
1. **Command Squad (`.51` Integrator, `.194` Dispatcher/LensRouter, `.85` Audit/Adjudicator, `.52` Trainer)**:
   - Bind to `OK` high-context pools (lowest `five_hour_pct` tie-break: currently Pool B `0%` and Pool D `0%`, followed by Pool A `2%` and Pool C `3%`).
2. **Heavy Lifters (`review-*` Lenses -> Fixers -> Builders)**:
   - Resume the remaining `BulkDownloader` queue (`60` tagged candidates / staged briefs in `/home/mboyle/bd-persist/harness-work/O1789/staged_briefs/`).
   - Enforce the **Global 30 Heavy-Lifter Seat Cap** across all pools (`30s` launch spacing, `HUB-GATE` O1741 load guard, `retire-seat` hot-swap on verdict completion).
   - Enforce **Rule 86 (Protocol F)**: surviving synthetic test mutants on sound candidate code are `BOARD-WITH-ADVISORY` and never block train integration.

### Order 3: Execute Local vs. Cloud Coding Agent A/B Sandbox Benchmark (OPERATOR MANDATE)
To measure the real-world speed, token throughput, and pytest reliability of our best local coding model against a frontier cloud agent on an identical production task:
1. **Select a Queued Task Row / Fix**: Pick the first ready builder/fixer task row from the active queue.
2. **Create Two Isolated Sandboxes in `/home/mboyle/bd-local-wt/` (or `/home/mboyle/bd-cuts/`)**:
   - **Cloud Sandbox**: `/home/mboyle/bd-local-wt/<row>-cloud-ab` — dispatched via standard cloud builder (`Claude Sonnet/Opus` or `Codex gpt-6-astra`).
   - **Local Sandbox**: `/home/mboyle/bd-local-wt/<row>-local-ab` — dispatched to a **Local Coding Agent** backed by the Category Champion local coding model (`Qwen3.6-35B-A3B-Heretic` or `Qwen3-Coder-30B-A3B-Instruct` via LiteLLM `:4000` / local OpenCode/Aider/Codex harness).
3. **CRITICALBENCHMARK GUARD**:
   - While `Agent-37`'s final 10 models are finishing `llama-bench` on `.72+.228` and `.83+.125`, route the Local Coding Agent's immediate inference to **`.137` (`BattleStation` RTX 2080 Ti `94 tok/s`)** or wait for `.72`/`.83` `llama-bench` completion before binding 2xT4 `.72+.83` so `Agent-37`'s active benchmark run is **never interrupted or contended with**!
4. **Record Comparative Metrics**:
   - Write `/home/mboyle/bd-persist/harness-work/O1789/LOCAL-VS-CLOUD-AB-SANDBOX-BENCHMARK.md` comparing:
     - Wall-clock time to patch (`seconds`)
     - Prompt & completion token speeds (`tok/s`)
     - `ruff_check` + `mypy_check` + `bd-pytest-digest` pass rate on first attempt (`PASS`/`FAIL`)
     - Marginal API cost (`$0.00` local vs `$X.XX` cloud).

---

## 7. Preserved Historical Baseline (`2026-10-16` Waves 5–8 & Infrastructure Proofs)

1. **Waves 5, 6, 7 & 8 (16 Cuts, `268/268` Tests PASS) & Z3 SMT Consensus**:
   - Proof Artifact: `/home/mboyle/bd-persist/WAVE_5_8_SMT_CONSENSUS_PROOF.md` (`UNSAT_PROVEN` unanimous 4-pool quorum).
   - Rebase Train Audit: `/home/mboyle/.gemini/antigravity-cli/brain/62d3879a-675a-4913-93d4-3017d3a70ccf/REBASE_TRAIN_STACKING_AUDIT.md`.
   - 24-Dimension Swarm Synthesis: `/home/mboyle/.gemini/antigravity-cli/brain/d61a0f86-9a87-4a9f-8b2c-ea5791e23bc8/BOYLENET_24_DIMENSION_SWARM_SYNTHESIS_REPORT.md`.
2. **Active Cluster Services & Endpoints**:
   - Unified Boylenet OS Shell: `http://10.0.70.164:4085` (`http://os.boylenet.themfboyles.com`)
   - 165-View 60fps Topology & HiveMind CoT Visualizer: `http://10.0.70.164:4088` (`http://topology.boylenet.themfboyles.com`)
   - 86-Model App Storefront: `http://10.0.70.164:4084` (`http://models.boylenet.themfboyles.com`)
   - OpenWebUI Super-Suite: `http://10.0.70.164:8090` & `http://10.0.70.72:8080`
   - OpenWebUI Universal Gateway (`50` Toolkits, `8` Pipelines, `28` VM Terminals): `http://10.0.70.164:4079`
   - Guided Swarm Studio: `http://10.0.70.164:4098`
   - Cloud Burst & WAN Airgap Orchestrator: `http://10.0.70.164:4090`
   - 83-Service Autonomous Sentinel: `http://10.0.70.164:4099`
   - Jarvis Cockpit: `http://10.0.70.164:3002`
   - Universal Fleet Chat: `http://10.0.70.164:3003/fleet-chats`
   - LiteLLM Proxy (`228` Models): `http://10.0.70.164:4000` & `http://10.0.70.228:4000`
   - Local Gitea Server: `http://10.0.70.164:3000`
   - Qdrant Vector Engine (`bd_master_kb` + 5 Fleet RAG Collections): `http://10.0.70.125:6333`
   - Dual Chrome CDP Oracles: `10.0.10.137:9222` & `10.0.70.181:9222`
