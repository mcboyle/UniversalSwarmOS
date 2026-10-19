# 📚 BD-KB Master: Complete BulkDownloader & Boylenet Swarm OS Encyclopedia

- **Document ID**: `bd-kb-00-master-encyclopedia`
- **Canonical Path**: `/home/mboyle/bd-persist/bd-kb/00-BD-KB-MASTER-ENCYCLOPEDIA.md`
- **Scope**: Authoritative index and executive reference across BulkDownloader (`mcboyle/BD`), the 27-node Boylenet cluster (`1.4+ TB` RAM, `656` vCPUs, `4x NVIDIA Tesla T4 64GB` + `RTX 2080 Ti 11GB`, `107 TB` All-NVMe vSAN, `25GbE` RoCE), the 86-Model AI Vault (`8.9+ TB`), Fleet Law (Rules 1–86 + O1740 Dynamic Capability Routing), CI Failure Taxonomy (`BD-CI-01`..`BD-CI-09`), 14 MCP Servers (`99` tools), 8 OpenWebUI Pipelines, and 50 Native OpenWebUI Toolkits.

---

## 1. Master Volume Index (`BD KB` Books 00–06)

| Volume | Native KB ID | Filename | Core Domain |
|---|---|---|---|
| **Vol. 00** | `bd-kb-master` | `00-BD-KB-MASTER-ENCYCLOPEDIA.md` | Master index, architecture map, quick-reference cheat sheets, IP/port directory, and top-level operating contracts |
| **Vol. 01** | `bd-kb-bulkdownloader` | `01-BULKDOWNLOADER-ARCHITECTURE-AND-CONTRACTS.md` | BulkDownloader (`bd`) Flask/Playwright/React codebase, extractors, `yt-dlp` pin invariance, CLI/toolchain (`bd-precut`, `bd-regen-order`, `bd-band-derive`, `bd-mutate`, `bd-land-trio`), and canonical 24-worker pytest contract |
| **Vol. 02** | `bd-kb-cluster-infra` | `02-BOYLENET-27NODE-CLUSTER-12U-RACK-VSAN-25GBE.md` | 27-Node Boylenet cluster topology, 12U physical rack (`79.5°F` / `26.4°C`), 4x HPE DL380 Gen10 ESXi hosts, `107 TB` NVMe vSAN, `25GbE` RoCE, and 55+ Web UIs (`165` live Cockpit views) |
| **Vol. 03** | `bd-kb-86-models` | `03-86-MODEL-VAULT-BENCHMARKS-AND-AIRGAP.md` | 86-Model Local AI Vault (`8.9+ TB` across `.72` & `.83`), real-weight `llama-bench` (`b11716`) `pp512`/`tg128` speeds, Category Winners, `bd-airgap` WAN isolation, and `bd-raw-ai` |
| **Vol. 04** | `bd-kb-fleet-law` | `04-FLEET-LAW-RULES-1-86-AND-O1740-ROUTING.md` | Fleet Law (Rules 1–86), O1740 Dynamic Capability Routing, HUB-GATE (`20%` iowait ceiling, O1741), Rule 22 Anti-Hallucination Shield, Rule 86 Mutation Coverage Severance, and Cut/Train Workflow |
| **Vol. 05** | `bd-kb-ci-and-uis` | `05-CI-TAXONOMY-RECOVERY-AND-MCP-TOOLS.md` | CI Failure Taxonomy (`BD-CI-01`..`BD-CI-09`), Gridlock Recovery playbooks, 14 Fleet MCP servers (`99` tools), 8 OpenWebUI Pipelines, and 50 Native OpenWebUI Toolkits |
| **Vol. 06** | `bd-kb-5platform-mods` | `06-5PLATFORM-MCP-MODS-HTTPS-AND-215-LEDGER.md` | 20-Tool `boylenet-infra` MCP Server across 5 platforms, Autonomous Mods 1–5 (`bd-swarm-mod`), 22 Slash Commands/Skills, `.83:18080` `Qwen3.6-Heretic` Coding Pool, NGINX/Cloudflare DNS-01 HTTPS, and `215/215` Reconciled Backlog Ledger |

---

## 2. Executive Architecture Map

### 2.1 Primary Control Plane & AI Gateway Endpoints

| Service | Node / IP | Port | URL / Endpoint | Purpose |
|---|---|---:|---|---|
| **OpenWebUI Controller** | `10.0.70.164` (`controller`) | `8090` | `http://openwebui.boylenet.themfboyles.com` (`:8090`) | Primary AI Workspace: 112 models (86 Local `[LOCAL]` + 11 Cloud `[CLOUD]` + 8 Pipelines + 11 Image/Speech models), 50 Toolkits, 128 Skills, `BD KB` |
| **OpenWebUI Vault A** | `10.0.70.72` (`ai-srv01`) | `8080` | `http://ai-webui.boylenet.themfboyles.com` (`:8080`) | Secondary AI Workspace synced 1:1 with Controller (`:8090`) |
| **LiteLLM Unified Proxy** | `10.0.70.164` (`controller`) | `4000` | `http://litellm.boylenet.themfboyles.com` (`:4000/v1`) | Unified OpenAI-compatible router for all 86 Local Vault models + 11 Cloud Frontier models (`sk-fleet-local`) |
| **OpenWebUI Tool & Pipelines Server** | `10.0.70.164` (`controller`) | `4079` | `http://10.0.70.164:4079` (`/v1` & `/openapi.json`) | Host-side OpenAPI 3.1 Tool Server + OpenWebUI Pipelines Server + Local Image/Speech/Embedding Gateway |
| **4-GPU Mode Orchestrator** | `10.0.70.164` (`controller`) | `4010` | `http://orchestrator.boylenet.themfboyles.com` (`:4010`) | Dynamic VRAM/NUMA mode switcher across 4x Tesla T4 GPUs (`.72`, `.83`, `.125`, `.228`) |
| **Boylenet Unified Portal (165 Views)** | `10.0.70.164` (`controller`) | `4080` | `http://portal.boylenet.themfboyles.com` (`:4080`) | 60fps NOC Command Wallboard & 165-View Fleet Telemetry Portal |
| **Qdrant Vector RAG Engine** | `10.0.70.125` (`ai-infer01`) | `6333` | `http://qdrant.boylenet.themfboyles.com` (`:6333`) | AVX2 SIMD Vector Search (`bd_master_kb`, `boylenet_fleet_rag`, `boylenet_codebase_ast`, `boylenet_episodic_memory`, `swarm_docs_rag`, `fleet_lessons_hivemind`) |
| **HuggingFace TEI Embeddings** | `10.0.70.164` (`controller`) | `8081` | `http://10.0.70.164:8081` | Ultra-low-latency (`<5ms`) CPU embedding server (48 tokenization workers) |
| **SearXNG Metasearch** | `10.0.70.164` (`controller`) | `8888` | `http://searxng.boylenet.themfboyles.com` (`:8888`) | Local privacy-preserving metasearch engine for live web queries |
| **Gitea Git Server** | `10.0.70.164` (`controller`) | `3000` | `http://gitea.boylenet.themfboyles.com` (`:3000`) | Self-hosted Git server & CI mirror (`mcboyle/BD`) |
| **Langfuse LLM Observability** | `10.0.70.228` (`ai-ollama01`) | `3000` | `http://langfuse.boylenet.themfboyles.com` | Token telemetry, trace spans, latency, and cost analytics |
| **BattleStation CDP Oracle & GPU** | `10.0.10.137` (`BattleStation`) | `9222` / `11434` | `http://10.0.10.137:9222` | Dual-role Chrome CDP Browser Oracle + Ryzen 9 CPU Embeddings + RTX 2080 Ti (11GB) Coder GPU |
| **Bittorrent CDP Oracle** | `10.0.70.181` (`bittorrent`) | `9222` | `http://10.0.70.181:9222` | Secondary Chrome CDP Browser Oracle node |

---

## 3. Essential Operator & Agent Quick-Reference Commands

### 3.1 BulkDownloader (`bd`) Verification & Release Commands
- **Focused Pytest (Hermetic)**:
  ```bash
  env -u BD_INSTALL_DIR bash -c 'BD_DISABLE_KEEPALIVE=1 venv/bin/python -m pytest tests/test_target.py -q'
  ```
- **Digest Pytest (Rule 78, `<=3 lines`, `<25 tokens`)**:
  ```bash
  /home/mboyle/bin/bd-pytest-digest tests/test_target.py
  ```
- **Derive Affected Test Band**:
  ```bash
  /home/mboyle/BulkDownloader/venv/bin/python /home/mboyle/BulkDownloader/toolchain/bin/bd-band-derive
  ```
- **Deterministic Artifact Regeneration**:
  ```bash
  /home/mboyle/BulkDownloader/venv/bin/python /home/mboyle/BulkDownloader/toolchain/bin/bd-regen-order --work /home/mboyle/BulkDownloader
  ```
- **Precut Gate & Freshcheck**:
  ```bash
  /home/mboyle/BulkDownloader/venv/bin/python /home/mboyle/BulkDownloader/toolchain/bin/bd-precut --gate
  /home/mboyle/BulkDownloader/venv/bin/python /home/mboyle/BulkDownloader/toolchain/bin/bd-freshcheck --repo-only
  ```
- **Canonical 24-Worker Full Test Suite**:
  ```bash
  env -u BD_INSTALL_DIR BD_DISABLE_KEEPALIVE=1 PYTHONUNBUFFERED=1 venv/bin/python -m pytest tests/ -n 24 --dist loadfile --timeout=240 --timeout-method=signal --max-worker-restart=0 -p no:randomly
  ```

### 3.2 Boylenet Swarm, Airgap & Local AI Commands
- **Check/Toggle WAN Airgap (`bd-airgap`)**:
  ```bash
  /home/mboyle/bin/bd-airgap status
  /home/mboyle/bin/bd-airgap on
  /home/mboyle/bin/bd-airgap off
  ```
- **Direct Uncensored Local AI CLI (`bd-raw-ai`)**:
  ```bash
  /home/mboyle/bin/bd-raw-ai --list
  /home/mboyle/bin/bd-raw-ai -m coder-30b "Write a fast async port scanner in Python"
  ```
- **Authoritative 27-Node Seat Census**:
  ```bash
  /home/mboyle/bd-persist/harness/bd-role-claim.sh who-all
  cat /home/mboyle/bd-persist/POOL_STATE.tsv
  ```
- **Cross-Pool Agent Messaging (`bd-say.sh`, `<=30 chars|path`)**:
  ```bash
  /home/mboyle/bd-persist/harness/bd-say.sh <tmux-session> "BOARD|path/to/VERDICT.md"
  ```

---

## 4. Golden Operating Invariants (Summary)

1. **Rule 22 (Sandbox & Worktree Immortality)**: `NO WORKTREE DELETED OR RESET, EVER.` Destructive Git commands (`git reset --hard`, `git checkout --`, `git clean -f`) are blocked outside `/home/mboyle/bd-cuts/` and `/home/mboyle/bd-local-wt/` by `~/.gemini/config/shield.py`.
2. **Rule 6 (Three Measurement Outcomes)**: `FOUND n` / `FOUND NONE` / `COULD NOT LOOK`. `UNKNOWN` is a failing third state and is **never** permission. Always prove a probe can say YES before reporting NO (Rule 7).
3. **Rule 1 & Rule 74 (HTAP-9 Zero-Prose Output Cap)**: No greetings, no filler, no narrative recaps. Execution replies `<= 50 tokens` formatted as `<STATUS> <path>`. Details live in files on disk.
4. **O1740 (Dynamic Capability Routing)**: Never hardcode pools (`A/B/C/D`). Resolve dynamically at launch from `/home/mboyle/bd-persist/POOL_STATE.tsv` across Command Squad (`OK` Opus), Heavy Lifters (`OK` or `OFF-PACE <85%`, capped at 30 per pool with hot-swap `Lenses -> Fixers -> Builders`), and Lightweight Investigators.
5. **Standing Order O1741 (HUB-GATE 20% I/O Ceiling)**: `HUB_MAX_IOWAIT_PCT = 20.0%` is never bypassed or edited. Protects Node `.164` NFSv4 exports and `flock` ledgers against multi-node lock collapse.
6. **Rule 86 (Behavioral Defect vs. Mutation Coverage Severance)**: Review lenses may `REFUTE` only for demonstrable behavioral defects, regressions, or Fleet Law violations. Surviving synthetic mutants on sound code are `BOARD-WITH-ADVISORY`.
