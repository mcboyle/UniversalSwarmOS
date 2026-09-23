---
name: fleet-satellite-orchestration
description: Comprehensive operational guide, diagnostic runbooks, and automation procedures for the 27-node Boylenet cluster mesh, VMware ESXi hypervisors (govc), satellite AI containers (TEI, Ollama, Langfuse, LiteLLM), local caching registries, and fleet health verification. Use when managing, debugging, auditing, or deploying cluster infrastructure services.
---

# Fleet Satellite Orchestration & Infrastructure Runbooks

An authoritative operational reference for managing, deploying, debugging, and auditing the 27-node cluster across the 25GbE backbone (`10.0.70.0/24`), VMware ESXi 8.0.3 hypervisors, Tesla T4 GPU nodes, containerized AI/telemetry services, and local caching registries.

---

## 1. 27-Node Cluster Fabric & Port Topology

### A. Physical Hypervisors & Management Fabric
- **Subnet**: `10.0.20.40/28` (Management VLAN) | MTU 9000
- **esxi01**: `10.0.20.41` (DL380 Gen9, 56 cores, 768GB RAM) – Hosts `stg-cache01/02`, `MCP`
- **esxi02**: `10.0.20.42` (DL380 Gen9, 88 cores, 768GB RAM) – Hosts `test5` (hub-mesh01), `bd3`, `test2`
- **esxi03**: `10.0.20.43` (DL380 Gen10, 104 cores, 768GB RAM) – Hosts `test3big`, `test4`, `bd2`, `bd4`, `CI/CD`
- **esxi04**: `10.0.20.44` (DL380 Gen10, 104 cores, 768GB RAM) – Hosts `Test5`, `AI`

### B. Core Service Port Registry

| Subsystem | Service Name | Host / IP | Port / Protocol | Health Endpoint / Probe |
| :--- | :--- | :--- | :--- | :--- |
| **Inference** | LiteLLM Proxy | `127.0.0.1` | `:4000` HTTP | `http://127.0.0.1:4000/health/ready` |
| **Inference** | OpenClaw / Hermes Bridge | `10.0.70.162` | `:8090` HTTP | `http://10.0.70.162:8090/health` |
| **Inference** | Llama-Guard 3 8B (Tesla T4 #2) | `10.0.70.125` | `:11434` HTTP | `http://10.0.70.125:11434/api/tags` |
| **Inference** | Ollama Qwen2.5-Coder (Tesla T4 #3) | `10.0.70.228` | `:11434` HTTP | `http://10.0.70.228:11434/api/tags` |
| **Inference** | HF TEI Embeddings (`bge-m3`) | `127.0.0.1` | `:8081` HTTP | `http://127.0.0.1:8081/info` |
| **Inference** | HF TEI Reranker (`bge-reranker-large`) | `127.0.0.1` | `:8082` HTTP | `nc -z 127.0.0.1 8082` |
| **Data Layer**| PostgreSQL 16 + PGvector | `127.0.0.1` | `:5432` TCP | `pg_isready -h 127.0.0.1 -p 5432` |
| **Data Layer**| Elasticsearch 8.13 | `127.0.0.1` | `:9200` HTTP | `http://127.0.0.1:9200/_cluster/health` |
| **Data Layer**| Redis Cluster | `127.0.0.1` | `:6379` TCP | `redis-cli -h 127.0.0.1 ping` |
| **Data Layer**| MinIO S3 Object Store | `127.0.0.1` | `:9000` HTTP | `http://127.0.0.1:9000/minio/health/live` |
| **Data Layer**| Forgejo Git SCM | `127.0.0.1` | `:3000` HTTP | `http://127.0.0.1:3000/api/v1/version` |
| **Data Layer**| Apache Kafka (Event Bus) | `127.0.0.1` | `:9092` TCP | `nc -z 127.0.0.1 9092` |
| **Telemetry** | Langfuse Tracing Server | `10.0.70.162` | `:3002` HTTP | `http://10.0.70.162:3002/api/public/health` |
| **Telemetry** | Prometheus & Grafana | `127.0.0.1` | `:9090, :3001` | `http://127.0.0.1:9090/-/healthy` |
| **Registries**| Devpi (PyPI Mirror) | `127.0.0.1` | `:3141` HTTP | `http://127.0.0.1:3141/+api` |
| **Registries**| Verdaccio (NPM Mirror) | `127.0.0.1` | `:4873` HTTP | `http://127.0.0.1:4873/-/ping` |
| **Registries**| Apt-Cacher-NG | `127.0.0.1` | `:3142` HTTP | `http://127.0.0.1:3142/acng-report.html` |
| **Registries**| Docker Registry Mirror | `127.0.0.1` | `:5000` HTTP | `http://127.0.0.1:5000/v2/` |
| **Egress**    | Squid Proxy | `127.0.0.1` | `:3128` HTTP | `nc -z 127.0.0.1 3128` |
| **Ingress**   | Traefik Ingress Router | `127.0.0.1` | `:80, :8080` | `http://127.0.0.1:8080/dashboard/` |
| **DNS**       | CoreDNS (.mesh.local) | `127.0.0.1` | `:53` UDP/TCP | `dig @127.0.0.1 hub-mesh01.mesh.local +short` |
| **IDE / Intel**| Sourcegraph Code Search | `10.0.70.107` | `:3443` HTTP | `curl -sI http://10.0.70.107:3443` (HTTP 302) |
| **IDE / Intel**| Tree-sitter & AST Server | `127.0.0.1` | `:8095` HTTP | `http://127.0.0.1:8095/health` |
| **IDE / Intel**| code-server (Web VS Code) | `127.0.0.1` | `:8443` HTTP | `nc -z 127.0.0.1 8443` |

---

## 2. VMware vCenter & ESXi Management Runbook (`govc`)

### A. vCenter Server (Cluster-Wide: 4 Hosts, 2 Clusters, 48 VMs)
```bash
export GOVC_URL="https://10.0.20.70/sdk" # vc04.boylenet.themfboyles.com
export GOVC_USERNAME="Administrator@boylenet.themfboyles.com"
export GOVC_PASSWORD="<from /home/mboyle/.swarm-import/VC.txt>"
export GOVC_INSECURE=1
```

### B. Direct ESXi Hypervisor HostAgents (Hardware & Local VM Control)
```bash
export GOVC_URL="https://10.0.20.41/sdk" # Or 10.0.20.42, 10.0.20.43, 10.0.20.44
export GOVC_USERNAME="root"
export GOVC_PASSWORD="<from /home/mboyle/.swarm-import/VC.txt>"
export GOVC_INSECURE=1
```

### Essential Commands
- **List Host Info**: `govc about`
- **List VMs on Host**: `govc ls vm`
- **Inspect Specific VM**: `govc vm.info -json "/ha-datacenter/vm/<name>" | jq .`
- **Snapshot Inventory**: `govc snapshot.tree -vm "/ha-datacenter/vm/<name>"`
- **Create Fast Snapshot**: `govc snapshot.create -vm "/ha-datacenter/vm/<name>" GOLDEN-READY`
- **Revert to Snapshot**: `govc snapshot.revert -vm "/ha-datacenter/vm/<name>" GOLDEN-READY`
- **Instant Clone (Tier 2 Elasticity)**:
  `govc vm.clone -vm "/ha-datacenter/vm/<template>" -snapshot "GOLDEN-READY" -on=true "<clone-name>"`

---

## 3. Diagnostic & Resolution Playbooks

### Playbook 1: Hugging Face Model Relative Redirect Failures (TEI)
- **Signature**: `Error: Could not download model artifacts: Caused by: request error: builder error: relative URL without a base`
- **Root Cause**: Hugging Face CDN sends HTTP 307 with relative `Location: /api/resolve-cache/...`. Older TEI `hf-hub` crates crash.
- **Resolution**:
  1. Download artifacts locally:
     ```bash
     mkdir -p /home/mboyle/infra/models/<model-id>
     curl -f -sL "https://huggingface.co/<model-id>/resolve/main/<file>" -o "/home/mboyle/infra/models/<model-id>/<file>"
     ```
  2. Bind-mount into TEI:
     ```bash
     docker run -d --name tei-reranker --restart unless-stopped -p 8082:80 \
       -v /home/mboyle/infra/models/<model-id>:/model:ro \
       ghcr.io/huggingface/text-embeddings-inference:cpu-1.5 \
       --model-id /model --port 80
     ```

### Playbook 2: CoreDNS Port 53 Collision with systemd-resolved
- **Signature**: `Error starting userland proxy: listen tcp4 0.0.0.0:53: bind: address already in use`
- **Root Cause**: `systemd-resolved` binds to `127.0.0.53:53` and `127.0.0.54:53`. Wildcard `0.0.0.0:53` collides.
- **Resolution**:
  Explicitly bind CoreDNS to `127.0.0.1:53`:
  ```bash
  docker run -d --name coredns --restart unless-stopped \
    -p 127.0.0.1:53:53/udp \
    -p 127.0.0.1:53:53/tcp \
    -v /home/mboyle/infra/support-layer/Corefile:/etc/coredns/Corefile \
    coredns/coredns:latest -conf /etc/coredns/Corefile
  ```

### Playbook 3: FastMCP Stdio Protocol Corruption
- **Signature**: Red `✗` in Antigravity `/settings` for custom Python MCP servers.
- **Root Cause**: `print()`, unhandled logging, or third-party library warnings (e.g. Pydantic forward-refs) leak to stdout/stderr.
- **Resolution**:
  1. Install FastMCP wrapper in user site-packages: `~/.local/lib/python3.12/site-packages/mcp_server_<name>.py`.
  2. Suppress warnings before FastMCP imports:
     ```python
     import warnings
     warnings.filterwarnings("ignore")
     ```
  3. Verify JSON-RPC handshake over stdin/stdout:
     ```bash
     echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python3 -m mcp_server_<name>
     ```

### Playbook 4: Single-Container Langfuse Compatibility
- **Signature**: Langfuse container crashes looping on ClickHouse connection errors.
- **Root Cause**: Langfuse v3 requires ClickHouse. Single-container PostgreSQL operation requires v2.
- **Resolution**: Pin image to `langfuse/langfuse:2` with `DATABASE_URL=postgresql://postgres:postgres@10.0.70.164:5432/langfuse`.

### Playbook 5: 25GbE MTU 9000 Unfragmented Fabric Verification
- **Signature**: Dropped jumbo frame packets or silent MTU truncation across physical ESXi vSwitches.
- **Root Cause**: ICMP pings without the "Don't Fragment" flag will fragment at the IP layer, masking misconfigured vSwitches or interface MTUs.
- **Resolution**:
  Probe target nodes with the "Don't Fragment" bit (`-M do`) and payload size equal to `MTU - 28` (8972 bytes):
  ```bash
  for ip in 10.0.70.72 10.0.70.125 10.0.70.228 10.0.70.162 10.0.70.107 10.0.70.50 10.0.70.95; do
    ping -c 1 -M do -s 8972 "$ip" || echo "FAIL MTU 9000: $ip"
  done
  ```

---

## 4. Physical Server Out-of-Band Management (HPE iLO / ILOM)

### A. Host-to-Controller Mapping Matrix
- **`esxi01`** (ProLiant DL380 Gen9): `https://10.0.10.10/` (iLO 4 v2.82, `ILOM1`)
- **`esxi02`** (ProLiant DL380 Gen9): `https://10.0.10.20/` (iLO 4 v2.82, `ILO2`)
- **`esxi03`** (ProLiant DL380 Gen10): `https://10.0.10.252/` (iLO 5 v2.98, `ESXI03`)
- **`esxi04`** (ProLiant DL380 Gen10): `https://10.0.10.40/` (iLO 5 v2.98, `ESXI04`)
- **Network Gateway**: `10.0.10.1` (UniFi Dream Machine Special Edition / UDM SE)
- **Credentials**: Stored securely in `/home/mboyle/.swarm-import/ILOM.txt` (`mboyle:Matt99!!`)

### B. Common Redfish API Automation Commands
- **Chassis Health & Model Audit**:
  ```bash
  curl -k -s -u "mboyle:Matt99!!" "https://10.0.10.40/redfish/v1/Systems/1" | jq '{Model: .Model, Hostname: .HostName, Health: .Status.Health, Power: .PowerState}'
  ```
- **Power Supply Status**:
  ```bash
  curl -k -s -u "mboyle:Matt99!!" "https://10.0.10.252/redfish/v1/Chassis/1/Power" | jq '.PowerSupplies[] | {Name: .Name, Health: .Status.Health}'
  ```
- **Emergency Bare-Metal Reset (Force Restart Frozen Host)**:
  ```bash
  curl -k -s -X POST -u "mboyle:Matt99!!" -H "Content-Type: application/json" \
    "https://10.0.10.252/redfish/v1/Systems/1/Actions/ComputerSystem.Reset" \
    -d '{"ResetType": "ForceRestart"}'
  ```

---

## 5. vSphere Dynamic Rightsizing & Spare Pool Runbook

### A. Live Hot-Add Configuration
```bash
# Enable live CPU and RAM expansion on a running VM:
govc vm.change -vm "/Boylenet Datacenter/vm/<path>" -cpu-hot-add-enabled=true -memory-hot-add-enabled=true
```

### B. Offline Resizing Workflow (When Hot-Add is Disabled)
```bash
# 1. Clean guest shutdown
govc vm.power -s "/Boylenet Datacenter/vm/<path>"
# 2. Wait until poweredOff, then resize
govc vm.change -vm "/Boylenet Datacenter/vm/<path>" -c 64 -m 131072 -cpu-hot-add-enabled=true -memory-hot-add-enabled=true
# 3. Power on
govc vm.power -on "/Boylenet Datacenter/vm/<path>"
```

### C. Spare Pool Management Policy
- **Pre-warmed Hot Spares**: `Spare1` and `spare2` must remain `poweredOn` with Hot-Add enabled for immediate workload burst failover.
- **Cold Spares**: `spare3` through `spare12` remain `poweredOff`, returning 448 GB RAM and 176 vCPUs to the physical cluster.

---

## 6. Verification & Audit Execution

Run the complete 22-component audit suite:
```bash
/tmp/audit_fleet_services.sh
```
Acceptance criteria: All 22 probes yield `[PASS]`, exit code 0.

---

## 7. Tri-Agent Ecosystem Synchronization Runbook

When adding or updating MCP tools or agent skills:
1. **Antigravity Registration**: Add to `~/.gemini/antigravity-cli/mcp_config.json`.
2. **Claude Code Registration**: Add to `~/.claude.json` under `mcpServers` object and run `claude mcp list` to verify `✔ Connected`.
3. **OpenAI Codex Registration**: Declare table in `~/.codex/config.toml` (`[mcp_servers."<name>"]`) with `startup_timeout_sec = 30`.
4. **Skills Symlink Sweep**:
   ```bash
   for s in /home/mboyle/.agents/skills/*; do
     sname=$(basename "$s")
     [ -e "/home/mboyle/.claude/skills/$sname" ] || ln -s "$s" "/home/mboyle/.claude/skills/$sname"
     [ -e "/home/mboyle/.codex/skills/$sname" ] || ln -s "$s" "/home/mboyle/.codex/skills/$sname"
   done
   ```
5. **Interactive Verification Probe**:
   Issue an active quiz via `swarm-say.sh` to prove that all active seats report tool availability and read disk ground truth cleanly.

