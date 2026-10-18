---
name: boylenet-infra-commander
description: Boylenet 27-VM Infrastructure Commander skill for Kimi K2.8, Claude Code, Codex, and AGY. Execute commands across all 27 VMs, inspect Sovereign Local Gateway (:4010) & LiteLLM (:4000), and toggle bd-airgap.
---

# Boylenet 27-VM Infrastructure Commander (`boylenet-infra-commander`)

Provides unified infrastructure command and telemetry across all 27 Boylenet cluster nodes (`1,472 GB RAM`, `656 vCPUs`, `3x GPU nodes`), the Universal Tool Gateway (`:4079`), Sovereign Local AI Gateway (`:4010`), LiteLLM Mesh (`:4000`), and `bd-airgap` sovereignty controls.

## 1. Critical Operating Invariants
- **Benchmark Contention Lock (`.72` & `.83`)**: Always check if `bench_worker.py` is running on Vault A (`10.0.70.72`) or Vault B (`10.0.70.83`) before dispatching heavy workloads to those two nodes.
- **Hardware Segregation (Rule 84)**:
  - `10.0.70.82` (`wrk-test04`, 64-core `/dev/shm` ramdisk): Dedicated pytest, AST indexing, and CI verification node.
  - `10.0.10.137` (`BattleStation`, Ryzen 9 + 11GB RTX 2080 Ti): Fast `$0` local coding (`qwen2.5-coder:14b`/`7b` on `:11434`) + embedding models (`bge-m3` on `:8091`) + Chrome CDP Oracle (`:9222`).
  - `10.0.70.125` (`ai-infer01`): Qdrant vector engine (`:6333`, `bd_master_kb`, `hivemind_episodes`) + TEI embeddings.

## 2. Core CLI & MCP Commands

### Inspect 27-VM Cluster Telemetry & Pool Quotas
```bash
python3 /home/mboyle/bin/bd-boylenet-infra-mcp.py --status
```

### Execute Command Across Any of the 27 VMs
```bash
python3 /home/mboyle/bin/bd-boylenet-infra-mcp.py --vm 10.0.70.82 --cmd "df -h /dev/shm && uptime"
```

### Check or Toggle Sovereign Airgap Mode (`bd-airgap`)
```bash
/home/mboyle/bin/bd-airgap status
# Toggle strict local-only airgap or hybrid cloud+local mode:
/home/mboyle/bin/bd-airgap off
```

### Query Universal Tool Gateway (`:4079`) Directly
```bash
curl -fsS -X POST http://10.0.70.164:4079/api/tool/boylenet_fleet_telemetry \
  -H "Content-Type: application/json" \
  -d '{"query":"summary"}'
```
