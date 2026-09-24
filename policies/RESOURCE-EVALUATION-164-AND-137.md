# Host Evaluation & Ingestion Status

## 1. Controller 10.0.70.164 (`Test5`) Resource Evaluation

### Current Provisioning & Utilization
- **vCPU**: 48 vCPUs allocated. Current load: `1.33, 1.96, 2.00` (<4% load).
- **RAM**: 350 GB allocated (`344Gi`). Current usage: `62Gi used` / `281Gi available` (~18% usage, 82% idle headroom).
- **Storage**: Root LV is 2.0 TB, with `1.8 TB used` and `209 GB available` (**90% full**).

### Verdict on 164
- **CPU & RAM**: **DO NOT INCREASE**. 48 vCPUs and 350 GB RAM already provide massive headroom. Heavy compute (RAG indexing, compilation) is routed to 64-core `wrk-test04` (`10.0.70.82`) per fleet architecture.
- **Storage**: **EXPANSION RECOMMENDED IF >=95%**. Storage is at 90%. Expanding the root VMDK/vSAN volume by +500GB-1TB or running cleanup on old docker/build caches will prevent disk exhaustion.

---

## 2. Ingestion Status: 10.0.10.137 (Physical GPU Node)
- **Network**: Ping responding (TTL=127). Ports 445 (SMB) and 3389 (RDP) are open.
- **SSH Daemon**: OpenSSH installation is in progress.
- **Listener Daemon**: Actively polling port 22. As soon as `sshd` starts, controller will connect to probe GPU specs (`nvidia-smi`) and setup Chrome/CDP oracle bridge.
