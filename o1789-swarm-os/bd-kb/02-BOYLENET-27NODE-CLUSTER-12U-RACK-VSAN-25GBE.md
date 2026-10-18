# 🖥️ BD-KB 2: Boylenet 27-Node Cluster, 12U Physical Rack (`79.5°F`), 107TB vSAN, 25GbE RoCE & 55+ Web UIs

- **Document ID**: `bd-kb-02-cluster-infra`
- **Canonical Path**: `/home/mboyle/bd-persist/bd-kb/02-BOYLENET-27NODE-CLUSTER-12U-RACK-VSAN-25GBE.md`
- **Scope**: Complete hardware, network, storage, hypervisor, and web service encyclopedia for the 27-node Boylenet cluster (`boylenet.themfboyles.com`).

---

## 1. Physical 12U Rack & Bare-Metal Hypervisor Topology

- **Physical Enclosure**: **Startech 12U Open-Frame Server Rack** (`4x HPE ProLiant DL380 Gen10` 2U servers = `8U` compute + `4U` switching/UPS/PDU headroom).
- **Ambient Intake Temperature**: **`79.5°F` (`26.4°C`)** measured via HPE iLO 4 sensor `01-Inlet Ambient` across all 4 hosts (`10.0.10.200`–`10.0.10.203`).
- **Total Cluster Capacity**: **27 Nodes**, **`656` vCPUs**, **`1.4+ TB` DDR4 ECC RAM** (`1.73 TB` physical across 4 DL380 Gen10 hosts + BattleStation), **`107.0 TB` All-NVMe vSAN**, **`25GbE` Dual-Port SFP28 RoCE v2** mesh (`MTU 9000`).

### 1.1 The 4 Bare-Metal HPE ProLiant DL380 Gen10 ESXi 8.0U3 Hosts + BattleStation

| Host | ESXi Management IP | iLO 4 IPMI IP | CPU Architecture | Physical RAM | GPU Accelerator | Primary Hosted VMs |
|---|---|---|---|---:|---|---|
| **ESXi Host 01** | `10.0.70.1` (`esxi01`) | `10.0.10.200` | Dual Intel Xeon Gold/Platinum Skylake-X (AVX-512, 48 threads) | `562 GiB` | **NVIDIA Tesla T4 (`16 GB` VRAM)** | `ai-srv01` (`.72`), `controller` (`.164`) |
| **ESXi Host 02** | `10.0.70.2` (`esxi02`) | `10.0.10.201` | Dual Intel Xeon Skylake-X (AVX-512, 48 threads) | `562 GiB` | **NVIDIA Tesla T4 (`16 GB` VRAM)** | `ai-srv02` (`.83`), `wrk-test04` (`.82`) |
| **ESXi Host 03** | `10.0.70.3` (`esxi03`) | `10.0.10.202` | Dual Intel Xeon Skylake-X (AVX-512, 48 threads) | `384 GiB` | **NVIDIA Tesla T4 (`16 GB` VRAM)** | `ai-infer01` (`.125`), `spr-pool` VMs |
| **ESXi Host 04** | `10.0.70.4` (`esxi04`) | `10.0.10.203` | Dual Intel Xeon Skylake-X (AVX-512, 48 threads) | `384 GiB` | **NVIDIA Tesla T4 (`16 GB` VRAM)** | `ai-ollama01` (`.228`), `bittorrent` (`.181`) |
| **BattleStation** | `10.0.10.137` (Bare-Metal Win/WSL2) | N/A | AMD Ryzen 9 (CPU Embedding Pin, Rule 84) | `64 GiB` | **NVIDIA RTX 2080 Ti (`11 GB` VRAM)** | Chrome CDP Oracle (`:9222`), Ollama (`:11434`) |

---

## 2. 27-Node VM & Host Directory

| Node Group | IP Address(es) | Hostname(s) | Role & Workload Assignment |
|---|---|---|---|
| **Hub Controller** | `10.0.70.164` | `controller` (`test5`) | NFSv4 Hub, OpenWebUI (`:8090`), LiteLLM (`:4000`), Tool/Pipelines Gateway (`:4079`), GPU Orchestrator (`:4010`), Gitea (`:3000`), SearXNG (`:8888`), TEI (`:8081`), PostgreSQL (`:5432`), Redis (`:6379`), MinIO (`:9000`), Prometheus (`:9090`), Grafana (`:3001`), 30+ Dashboards (`:4070`–`:4099`) |
| **AI Vault Node A** | `10.0.70.72` | `ai-srv01` | `562 GiB` DDR4 + Tesla T4 (`16 GB`), `/mnt/models_hot` (`5.1 TB`), `llama-server` (`:11434`), RPC Worker (`:50052`), OpenWebUI Vault A (`:8080`) |
| **AI Vault Node B** | `10.0.70.83` | `ai-srv02` | `562 GiB` DDR4 + Tesla T4 (`16 GB`), `/mnt/models_hot` (`5.4 TB`), `llama-server` (`:11434`), RPC Worker (`:50052`) |
| **AI Inference & Qdrant** | `10.0.70.125` | `ai-infer01` | Tesla T4 (`16 GB`), Qdrant AVX2 Vector DB (`:6333`), Ollama (`:11434`), RPC Worker (`:50052`) |
| **AI Satellite & Langfuse** | `10.0.70.228` | `ai-ollama01` | Tesla T4 (`16 GB`), Primary Ollama (`:11434`), Langfuse (`:3000`), LiteLLM Satellite, RPC Worker (`:50052`) |
| **64-Core Ramdisk Runner** | `10.0.70.82` | `wrk-test04` | 64-vCPU High-Speed Pytest Ramdisk Offload (`bd-remote-pytest-82`) & RAG Indexing |
| **Worker & Lens Nodes** | `.52`, `.80`, `.183`, `.195`, `.120`, `.149`, `.185` | `wrk-*` / `spr-*` | Distributed Claude/Codex/AGY Worker & Review Lens Execution Seats |
| **Cold Spare Pool (Rule 61)** | DHCP via vSphere | `spare1`–`spare2` (Hot), `spare3`–`spare12` (Cold) | Elastic VMware Cold Spares (`448 GB` RAM, `176` vCPUs conserved when `spare3`–`spare12` powered off) |
| **Dual CDP Browser Oracles** | `10.0.10.137`, `10.0.70.181` | `BattleStation`, `bittorrent` | Live Chrome DevTools Protocol (`:9222`) Oracles for `bd-oracle` ($0 marginal cost) & JS rendering |

---

## 3. Complete Boylenet Web UI & Port Directory (`.164` & Cluster)

| Port | Service Name | DNS / URL | Description |
|---:|---|---|---|
| `8090` | **OpenWebUI Controller** | `http://openwebui.boylenet.themfboyles.com` | Primary AI Workspace (112 Models, 50 Toolkits, 8 Pipelines, BD KB) |
| `8080` | **OpenWebUI Vault A (`.72`)** | `http://ai-webui.boylenet.themfboyles.com` | Vault A AI Workspace synced with Controller |
| `4000` | **LiteLLM Proxy** | `http://litellm.boylenet.themfboyles.com` | Unified OpenAI API Gateway (`86` Local + `11` Cloud Models) |
| `4010` | **4-GPU Mode Orchestrator** | `http://orchestrator.boylenet.themfboyles.com` | 1-Click GPU Pool Mode Switcher (`fast_parallel`, `unified_4gpu_70b`, `moe_235b_hybrid`, `kimi_k3_cluster`) |
| `4070` | **Swarm Cost & Savings Analyzer** | `http://10.0.70.164:4070` | Token economics, local vs. cloud ROI, and cache hit telemetry |
| `4071` | **Git Train & Patch Explorer** | `http://10.0.70.164:4071` | Live train integration status, patch SHA256 verification, and worktree census |
| `4072` | **Pytest & CI Shard Matrix** | `http://10.0.70.164:4072` | `.82` Ramdisk pytest runner telemetry and CI shard health |
| `4073` | **PostgreSQL & pgvector Studio** | `http://10.0.70.164:4073` | `ai_mesh` PostgreSQL schema, table explorer, and episodic memory inspector |
| `4074` | **vSAN & NVMe IOPS Telemetry** | `http://10.0.70.164:4074` | `107 TB` vSAN datastore capacity, NFSv4 latency, and `HUB-GATE` iowait monitor |
| `4075` | **25GbE RoCE & DNS Matrix** | `http://10.0.70.164:4075` | 25GbE SFP28 throughput, MTU 9000 jumbo frame status, and 398-record DNS matrix |
| `4076` | **86-Model Vault & GGUF Explorer** | `http://10.0.70.164:4076` | Complete `.72` & `.83` model inventory, shard sizes, and `llama-bench` leaderboard |
| `4077` | **Chrome CDP Browser Oracle HUD** | `http://10.0.70.164:4077` | Live `.137:9222` & `.181:9222` browser tabs and oracle fanout status |
| `4078` | **Airgap & Firewall Command Center** | `http://10.0.70.164:4078` | `bd-airgap` WAN kill-switch status, iptables rules, and local-only verification |
| `4079` | **Universal Tool, Pipeline & KB Gateway** | `http://10.0.70.164:4079` | OpenAPI 3.1 Tool Server + OpenWebUI `/v1` Pipelines, Image/Speech Gen & `BD KB` Search |
| `4080` | **Boylenet Unified Portal (165 Views)** | `http://portal.boylenet.themfboyles.com` | Master 60fps NOC Wallboard with all 165 operational views |
| `4081` | **Boylenet Doctor & Self-Healer** | `http://10.0.70.164:4081` | 31-Service health matrix and 1-click auto-remediation engine |
| `4083` | **Live Agent Stream Multiplexer** | `http://10.0.70.164:4083` | Real-time SSE log streamer for `/var/tmp/bd-headless-streams/*.log` |
| `4091` | **12U Rack & iLO 4 Thermal HUD** | `http://10.0.70.164:4091` | Live HPE DL380 Gen10 iLO 4 inlet temps (`79.5°F`), fan speeds, and PSU wattage |
| `4095` | **4-Model Consensus Arena** | `http://10.0.70.164:4095` | Parallel side-by-side LLM battleground & automated judge |
| `4099` | **Sentinel Auto-Healer Daemon** | `http://10.0.70.164:4099` | Continuous background watchdog for all Boylenet ports |

---

## 4. Certified Post-Drain `esxi01..04` vSAN Disk Group, HBA Queue-Depth, 25GbE RoCE & 12U Rack E2E Scorecard (`Agent-109`, `2026-10-18T23:22:48Z`)

### 4.1 Cluster-Wide vSAN Health, Resync & Disk Group Homogeneity Summary (`vsanDatastore`: `328.45 TiB` Raw / `194.75 TiB` Free)
- **ClusterUUID / SubClusterUUID**: `5221e29f-8740-f516-7273-0ae338b3eb48` (`4/4` hosts `HEALTHY`, `MaintenanceModeState: OFF`, `UnicastModeEnabled: true`, `Ondiskformatversion: 20`).
- **Global vSAN Resync Status (`esxcli vsan debug resync summary get`)**: `TotalBytesLeftToResync: 0` (`0.00 GB`), `TotalNumberOfResyncingObjects: 0` across all 4 hosts (`esxi01..04`).
- **Global vSAN Disk & Congestion Health (`esxcli vsan debug disk summary get`)**: `OverallHealth: green`, `ComponentMetadataHealth: green`, `MemoryPoolsheaps: green`, `MemoryPoolsslabs: green` (`0` congestion / `0` operational issues across all `75` vSAN disks in `11` Disk Groups).
- **`esxi01` (`10.0.20.41`) Surgical Per-Disk Re-Grouping Certified (`5/5` moves complete)**:
  - **DG 1 (`52e69070-da86-8f9f-27b2-679f255787a8`)**: Cache = `mpx.vmhba0:C2:T0:L0` (`1TB Samsung SSD 870`, `Wear=50/raw=899`, `Health=OK`) + **Pure `4×24TB Seagate Exos` Capacity Tier** (`mpx.vmhba0:C2:T3:L0`, `T4:L0`, `T5:L0`, `T13:L0` — `22,889,472 MB` each).
  - **DG 2 (`520e7405-7951-d36b-972f-44fa76ee518e`)**: Cache = `mpx.vmhba0:C2:T1:L0` (`1TB Samsung SSD 870`, `Wear=33/raw=1210`, `Health=OK`) + **Consolidated `7×3TB SAS` Capacity Tier** (`naa.5000cca01aa9a96c` `T6`, `naa.5000cca01ab112cc` `T7`, `naa.5000cca01aa7e5ec` `T8`, `naa.5000cca01ad7dc48` `T9`, `naa.5000cca01aa800e0` `T10`, `naa.50000c0f012d3630` `T11`, `naa.50000c0f01e0c290` `T12` — `2,861,588 MB` each).
- **`esxi02` (`10.0.20.42`)**: `2` Disk Groups (`13` vSAN disks total):
  - **DG 1 (`5240e70d-e734-a316-5a99-987272e3bd8a`)**: Cache = `mpx.vmhba0:C2:T8:L0` (`1TB Samsung SSD 870`, `Wear=24/raw=1375`, `Health=OK`) + `5` Capacity Disks (`T1`, `T3`, `T5`, `T7`, `T12`).
  - **DG 2 (`522f2b56-0852-910b-878c-d54289f87c32`)**: Cache = `mpx.vmhba0:C2:T9:L0` (`1TB Samsung SSD 860`, `Wear=9/raw=1641`, `Health=OK`) + `6` Capacity Disks (`T0`, `T2`, `T4`, `T6`, `T10`, `T11`).
- **`esxi03` (`10.0.20.43`)**: `4` Disk Groups (`25` vSAN disks total; all SSDs including `t10.ATA_____LITEON_CV32D8D5122D41_SATA_512GB_SED______TW0MN0K7LOH0075G01ZI` verified untouched in `DG 528858fc-593c-7675-862f-0da87d31e53c`).
- **`esxi04` (`10.0.20.44`)**: `3` Disk Groups (`24` vSAN disks total: `3` Cache SSDs + `21` Capacity Disks, `7` per DG).

### 4.2 25GbE SFP28 RoCE Fabric (`VLAN 75`, `10.0.75.11..14`) & UniFi Switch Port Matrix
| Node | Mgmt IP | RoCE IP (`VLAN 75`) | ESXi Host & Physical NIC | UniFi USW-Pro-Aggregation Port | Guest NIC / MTU | Link Speed (Host / Guest) | Full-Mesh Ping Loss | Inter-Node RTT (avg) |
|---|---|---|---|---|---|---|---|---|
| **`aidev` (`ai-srv02`)** | `10.0.70.83` | `10.0.75.11/24` | `esxi03` (`vmnic10` ConnectX-4 Lx) | **Port 30 (`25GbE SFP28`)** | `ens33` (`vmxnet3`, `MTU 9000`) | `25000Mb/s` Full / `10000Mb/s` | `0%` (`20/20` pkts) | `0.173ms`–`0.244ms` (`0.017ms` self) |
| **`ai-srv01`** | `10.0.70.72` | `10.0.75.12/24` | `esxi01` (`vmnic7` ConnectX-4 Lx) | **Port 29 (`25GbE SFP28`)** | `ens33` (`vmxnet3`, `MTU 9000`) | `25000Mb/s` Full / `10000Mb/s` | `0%` (`20/20` pkts) | `0.190ms`–`0.237ms` (`0.027ms` self) |
| **`ai-ollama01`** | `10.0.70.228` | `10.0.75.13/24` | `esxi02` (`vmnic6` ConnectX-4 Lx) | **Port 31 (`25GbE SFP28`)** | `ens33` (`vmxnet3`, `MTU 9000`) | `25000Mb/s` Full / `10000Mb/s` | `0%` (`20/20` pkts) | `0.141ms`–`0.217ms` (`0.020ms` self) |
| **`ai-infer01`** | `10.0.70.125` | `10.0.75.14/24` | `esxi04` (`vmnic6` ConnectX-5) | **Port 32 (`25GbE SFP28`)** | `ens33` (`vmxnet3`, `MTU 9000`) | `25000Mb/s` Full / `10000Mb/s` | `0%` (`20/20` pkts) | `0.145ms`–`0.235ms` (`0.019ms` self) |

### 4.3 12U Physical Rack iLO 4 / iLO 5 Thermal, Fan & PSU Telemetry (`:4091/api/hardware`)
| Host | Rack Position | ESXi IP | iLO IP & Generation | Inlet Temp | CPU1 / CPU2 Temp | Power Draw (Now / Avg / Max) | PSUs | Fans (Count / Health / Avg %) |
|---|---|---|---|---|---|---|---|---|
| **`esxi01`** (`DL380 Gen9`) | `U11–U12` | `10.0.20.41` | `10.0.10.10` (`iLO 4 v2.82`) | `44.0°C` (Sensor) / `26.4°C` (`79.5°F` Rack Ambient) | `40.0°C` / `40.0°C` | `480W` / `483W` / `609W` | `2/2 OK` | `6` / `OK` / `55.7%` |
| **`esxi02`** (`DL380 Gen9`) | `U09–U10` | `10.0.20.42` | `10.0.10.20` (`iLO 4 v2.82`) | `23.0°C` (`73.4°F`) | `40.0°C` / `48.0°C` | `459W` / `462W` / `514W` | `2/2 OK` | `6` / `OK` / `49.2%` |
| **`esxi03`** (`DL380 Gen10`) | `U07–U08` | `10.0.20.43` | `10.0.10.30` / `.252` (`iLO 5`) | `25.0°C` (`77.0°F`) | `40.0°C` / `41.0°C` | `574W` / `573W` / `680W` | `2/2 OK` | `6` / `OK` / `73.3%` |
| **`esxi04`** (`DL380 Gen10`) | `U05–U06` | `10.0.20.44` | `10.0.10.40` (`iLO 5`) | `26.0°C` (`78.8°F`) | `40.0°C` / `40.0°C` | `584W` / `591W` / `792W` | `2/2 OK` | `6` / `OK` / `47.2%` |
