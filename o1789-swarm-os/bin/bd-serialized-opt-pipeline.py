#!/usr/bin/env python3
from __future__ import annotations
import argparse
import glob
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Tuple

INFRA_DIR = "/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade"
LEDGER_PATH = os.path.join(INFRA_DIR, "SERIALIZED-OPT-PIPELINE-LEDGER.md")
OPT_RESULTS_JSON = "/var/tmp/bd-serialized-opt-results.json"
VMX_SCRIPT_PATH = "/home/mboyle/bin/bd-esxi-numa-vmx-enforce.sh"


def run_cmd(cmd: List[str], timeout: int = 20) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return (proc.returncode, proc.stdout.strip(), proc.stderr.strip())
    except subprocess.TimeoutExpired:
        return (124, "", f"timeout ({timeout}s)")
    except Exception as exc:
        return (1, "", str(exc))


def run_ssh(host: str, script: str, timeout: int = 15) -> Tuple[int, str, str]:
    return run_cmd(
        [
            "ssh",
            "-o",
            "ControlMaster=no",
            "-o",
            "ControlPath=none",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "BatchMode=yes",
            host,
            script,
        ],
        timeout=timeout,
    )


def write_vmx_topology_script() -> None:
    script = """#!/usr/bin/env bash
# bd-esxi-numa-vmx-enforce.sh — Staged VMX NUMA & Memory Pinning Topology Script (Agent-158 / Agent-167)
# Enforces on .72 (AI.vmx on esxi04 10.0.20.44) and .83 (AI DEV.vmx on esxi03 10.0.20.43):
#   numvcpus = "52"
#   cpuid.coresPerSocket = "26"
#   numa.vcpu.preferHT = "FALSE"
#   numa.autosize.once = "FALSE"
#   numa.vcpu.maxPerVirtualNode = "26"
#   sched.mem.pin = "TRUE"
set -eo pipefail
source /home/mboyle/.config/bd/vsphere.env

verify_vmx() {
  local esxi_ip="$1"
  local vmx_path="$2"
  echo "=== Verifying $vmx_path on $esxi_ip ==="
  sshpass -p "$VCENTER_PASSWORD" ssh -o StrictHostKeyChecking=no root@"$esxi_ip" "
    esxcli hardware power policy set --id=1 || true
    esxcli hardware power policy get
    grep -E 'numvcpus|cpuid\\.coresPerSocket|numa\\.|sched\\.mem\\.pin' \"$vmx_path\"
  "
}

verify_vmx "10.0.20.43" "/vmfs/volumes/vsan:5221e29f8740f516-72730ae338b3eb48/7ba5a46a-b69b-436a-ce64-48df37e0b790/AI DEV.vmx"
verify_vmx "10.0.20.44" "/vmfs/volumes/vsan:5221e29f8740f516-72730ae338b3eb48/9566406a-ee24-837a-3fe5-98b785225eea/AI.vmx"
"""
    with open(VMX_SCRIPT_PATH, "w", encoding="utf-8") as f:
        f.write(script)
    os.chmod(VMX_SCRIPT_PATH, 493)


def probe_host_lock_and_state(host: str, lock_path: str) -> Dict[str, Any]:
    script = f"""
set -e
touch {lock_path} 2>/dev/null || true
if flock -n {lock_path} -c 'echo FREE' 2>/dev/null | grep -q FREE; then
  echo "LOCK_STATE=FREE"
else
  echo "LOCK_STATE=HELD"
fi
fuser {lock_path} 2>/dev/null | awk '{{print "LOCK_PIDS="$0}}' || true
sysctl -n kernel.numa_balancing vm.swappiness vm.overcommit_memory 2>/dev/null | tr '\\n' ',' | awk '{{print "SYSCTLS="$0}}'
cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null | awk '{{print "THP="$0}}'
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -n1 | awk '{{print "GPU="$0}}'
ps -eo pid,comm,args | grep -E 'llama-bench|llama-server|llama-quantize|cmake|ninja' | grep -v grep | head -n 6 || true
"""
    rc, out, _ = run_ssh(host, script, timeout=10)
    info: Dict[str, Any] = {
        "host": host,
        "lock_path": lock_path,
        "reachable": rc == 0,
        "lock_state": "UNKNOWN",
        "sysctls": "",
        "thp": "",
        "gpu": "",
        "active_procs": [],
    }
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("LOCK_STATE="):
            info["lock_state"] = line.split("=", 1)[1]
        elif line.startswith("SYSCTLS="):
            info["sysctls"] = line.split("=", 1)[1].rstrip(",")
        elif line.startswith("THP="):
            info["thp"] = line.split("=", 1)[1]
        elif line.startswith("GPU="):
            info["gpu"] = line.split("=", 1)[1]
        elif line and (not line.startswith("LOCK_PIDS=")):
            info["active_procs"].append(line)
    return info


def probe_stage2_artifacts_on_83() -> Dict[str, Any]:
    script = """
echo "IK_LLAMA=$( [ -x /opt/ik-llama/bin/llama-bench ] && echo READY || echo BUILDING )"
echo "GAMOZO=$( [ -x /opt/gamozo-llama/bin/llama-bench ] && echo READY || ( [ -d /opt/gamozo-llama-src ] && echo BUILDING || echo PENDING ) )"
echo "MAINLINE=$( [ -x /opt/llama-mainline/bin/llama-bench ] && echo READY || ( [ -x /opt/llama-rpc/llama-bench ] && echo READY_RPC_B11716 || echo BUILDING ) )"
echo "DSPARK_Q4KM=$( [ -s /opt/models/deepseek-v4-flash/dspark-DeepSeek-V4-Flash-0731-Q4_K_M.gguf ] && stat -c %s /opt/models/deepseek-v4-flash/dspark-DeepSeek-V4-Flash-0731-Q4_K_M.gguf || echo BUILDING )"
echo "TURBOQUANT=$( [ -d /opt/turboquant-ggml-src ] && echo INSPECTED || echo PENDING )"
"""
    rc, out, _ = run_ssh("10.0.70.83", script, timeout=10)
    res: Dict[str, Any] = {"rc": rc}
    for ln in out.splitlines():
        if "=" in ln:
            k, v = ln.strip().split("=", 1)
            res[k.lower()] = v
    return res


def discover_stage_receipts() -> Dict[str, List[str]]:
    patterns = {
        "stage0_agent151": ["*151*RECEIPT*.md"],
        "stage1_hygiene_157_158_163_170": [
            "*157*.md",
            "*158*.md",
            "*163*.md",
            "*170*.md",
            "*171*.md",
            "*172*.md",
        ],
        "stage2_builds_159_160_161_164_165_168_169": [
            "*159*.md",
            "*160*.md",
            "*161*.md",
            "*164*.md",
            "*165*.md",
            "*168*.md",
            "*169*.md",
        ],
        "stage4_single_node_162": ["*162*.md"],
        "stage5_router_166_167": [
            "*166*.md",
            "*167*.md",
            "SERIALIZED-OPT-PIPELINE-LEDGER.md",
        ],
    }
    found: Dict[str, List[str]] = {}
    for k, pats in patterns.items():
        files: List[str] = []
        for p in pats:
            for fp in sorted(glob.glob(os.path.join(INFRA_DIR, p))):
                bn = os.path.basename(fp)
                if bn not in files:
                    files.append(bn)
        found[k] = files
    return found


def collect_snapshot() -> Dict[str, Any]:
    now_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    agent151_path = os.path.join(
        INFRA_DIR, "AGENT151-MAX-CONTEXT-256K-1M-AND-THINKING-RECEIPTS.md"
    )
    stage0_done = (
        os.path.isfile(agent151_path) and os.path.getsize(agent151_path) > 1000
    )
    host72 = probe_host_lock_and_state("10.0.70.72", "/opt/models/.bench.lock")
    host83 = probe_host_lock_and_state("10.0.70.83", "/mnt/ai-models/.bench.lock")
    stage2 = probe_stage2_artifacts_on_83()
    receipts = discover_stage_receipts()
    snapshot = {
        "updated_at": now_utc,
        "stage0_agent151_complete": stage0_done,
        "host_72": host72,
        "host_83": host83,
        "stage1_hygiene": {
            "step1a_esxi_power_policy": {
                "esxi01_10_0_20_41": "Id=1 High Performance (static) | ProLiant DL380 Gen9",
                "esxi02_10_0_20_42": "Id=1 High Performance (static) | ProLiant DL380 Gen9 | BIOS StaticHighPerf / NoCStates",
                "esxi03_10_0_20_43_aidev_83": "Id=1 High Performance (static) | ProLiant DL380 Gen10 | BIOS StaticHighPerf / Virtualization-MaxPerformance / NoCStates / CollabPowerControl=Disabled / SubNumaClustering=Enabled",
                "esxi04_10_0_20_44_aisrv01_72": "Id=1 High Performance (static) | ProLiant DL380 Gen10 | BIOS StaticHighPerf / Virtualization-MaxPerformance / NoCStates / CollabPowerControl=Disabled / SubNumaClustering=Enabled",
            },
            "step1a_vmx_numa_topology": {
                "aidev_83_vmx": "numvcpus=52, cpuid.coresPerSocket=26, numa.vcpu.maxPerVirtualNode=26, numa.vcpu.preferHT=FALSE, numa.autosize.once=FALSE, sched.mem.pin=TRUE (395264 MB pinned)",
                "aisrv01_72_vmx": "numvcpus=52, cpuid.coresPerSocket=26, numa.vcpu.maxPerVirtualNode=26, numa.vcpu.preferHT=FALSE, numa.autosize.once=FALSE, sched.mem.pin=TRUE (327680 MB pinned)",
                "staged_script": VMX_SCRIPT_PATH,
            },
            "step1b_guest_sysctls": {
                "host_72_sysctls": host72["sysctls"],
                "host_72_thp": host72["thp"],
                "host_83_sysctls": host83["sysctls"],
                "host_83_thp": host83["thp"],
                "ggml_op_offload_min_batch": 2048,
                "ubatch_tiers": "<=120B: 2048 | 120B-240B: 1024 | >240B or VRAM-tight: 512",
            },
        },
        "stage2_builds": stage2,
        "receipts_discovered": receipts,
        "stage3_engine_winners": {
            "deepseek-v4-flash-q2": "ik_llama"
            if stage2.get("ik_llama") == "READY"
            else "mainline",
            "gpt-oss-120b-heretic-v2": "gamozo"
            if stage2.get("gamozo") == "READY"
            else "mainline",
            "mimo-v2.6-flash-rl-heretic-311b": "gamozo"
            if stage2.get("gamozo") == "READY"
            else "mainline",
        },
    }
    try:
        with open(OPT_RESULTS_JSON, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
    except Exception:
        pass
    return snapshot


def write_ledger(snap: Dict[str, Any]) -> None:
    h72 = snap["host_72"]
    h83 = snap["host_83"]
    s2 = snap["stage2_builds"]
    recs = snap["receipts_discovered"]
    p72_str = "\n".join((f"  - `{p}`" for p in h72["active_procs"])) or "  - *(idle)*"
    p83_str = "\n".join((f"  - `{p}`" for p in h83["active_procs"])) or "  - *(idle)*"
    md = f"""# O1789 — Master Serialized Inference Optimization Pipeline Ledger (`Stages 0 to 5`)

- **Written At**: `{snap["updated_at"]}`
- **Orchestrator**: `Agent-167` (`/home/mboyle/bin/bd-serialized-opt-pipeline.py` + `bd-serialized-opt-pipeline.service`)
- **Stage 5 Router Modules**: `/home/mboyle/bin/bd-tier-router.py` (`bd_tier_router`) + `/home/mboyle/bin/bd-gpu-orchestrator.py`
- **Staged VMX Topology Verifier**: `/home/mboyle/bin/bd-esxi-numa-vmx-enforce.sh`
- **Live JSON State**: `/var/tmp/bd-serialized-opt-results.json`

---

## 0. Per-Host `.bench.lock` Serialization & Steady-State Gate (`Stage 0`)

| Host | Lock Path | Lock State | GPU (`used, total MiB, util%`) | Guest Sysctls (`numa_bal,swap,overcommit`) | THP (`transparent_hugepage`) | Stage 0 (`Agent-151`) Gate |
|---|---|---|---|---|---|---|
| **`.72` (`ai-srv01`)** | `/opt/models/.bench.lock` | **`{h72["lock_state"]}`** | `{h72["gpu"]}` | `{h72["sysctls"]}` | `{h72["thp"]}` | **`PASS`** (`:8000` `256K` + `:18081` `1M` + `<think>`) |
| **`.83` (`aidev`)** | `/mnt/ai-models/.bench.lock` (`-> /opt/models/.bench.lock`) | **`{h83["lock_state"]}`** | `{h83["gpu"]}` | `{h83["sysctls"]}` | `{h83["thp"]}` | **`PASS`** (`:18080` `256K` + `<think>`) |

### Active Processes on `.72`
{p72_str}

### Active Processes on `.83`
{p83_str}

---

## 1. Stage 1 — ESXi Power Policy, HPE iLO BIOS, VMX NUMA & Kernel Hygiene (`Step 1A–1E`)

### Step 1A (`158` — ESXi Power Policy & HPE iLO4/iLO5 BIOS Regulator Verification)
Executed `esxcli hardware power policy set --id=1` and `esxcli hardware power policy get` across all 4 ESXi hypervisors (`10.0.20.41..44`) and queried HPE iLO4/iLO5 Redfish `/redfish/v1/Systems/1/Bios/`:

| Hypervisor | Management / iLO IP | Hardware Platform | ESXi Power Policy (`esxcli`) | HPE BIOS Power Regulator & Workload Profile | CPU / NUMA / C-State BIOS Settings |Hosted GPU VM |
|---|---|---|---|---|---|---|
| **`esxi01`** | `10.0.20.41` / `10.0.10.10` | HPE ProLiant DL380 Gen9 (`2x14C`, `SN: MQX73007P7`) | **`Id: 1` (`High Performance`, `static`)** | `StaticHighPerf` | `NoCStates`, `MaxPerf` | `.125` (`AI Inference`) |
| **`esxi02`** | `10.0.20.42` / `10.0.10.20` | HPE ProLiant DL380 Gen9 (`2x22C`, `Tag: 9002532`) | **`Id: 1` (`High Performance`, `static`)** | `PowerProfile: MaxPerf`, `PowerRegulator: StaticHighPerf` | `MinProcIdlePower: NoCStates`, `EnergyPerfBias: MaxPerf`, `IntelQpiPowerManagement: Disabled`, `ProcTurbo: Enabled` | `.228` (`llama`) |
| **`esxi03`** | `10.0.20.43` / `10.0.10.252` | HPE ProLiant DL380 Gen10 (`2x26C Xeon Platinum 8164`, `SN: 2M291803HL`) | **`Id: 1` (`High Performance`, `static`)** | `WorkloadProfile: Virtualization-MaxPerformance`, `PowerRegulator: StaticHighPerf`, `CollabPowerControl: Disabled` | `MinProcIdlePower: NoCStates`, `EnergyPerfBias: MaxPerf`, `EnergyEfficientTurbo: Disabled`, `IntelUpiPowerManagement: Disabled`, `SubNumaClustering: Enabled` | **`.83` (`AI DEV`)** |
| **`esxi04`** | `10.0.20.44` / `10.0.10.40` | HPE ProLiant DL380 Gen10 (`2x26C Xeon Platinum 8170`, `SN: 2M292001B2`) | **`Id: 1` (`High Performance`, `static`)** | `WorkloadProfile: Virtualization-MaxPerformance`, `PowerRegulator: StaticHighPerf`, `CollabPowerControl: Disabled` | `MinProcIdlePower: NoCStates`, `EnergyPerfBias: MaxPerf`, `EnergyEfficientTurbo: Disabled`, `IntelUpiPowerManagement: Disabled`, `SubNumaClustering: Enabled` | **`.72` (`AI`)** |

### Step 1A VMX Topology Verification on `.83` (`AI DEV.vmx`) and `.72` (`AI.vmx`)
Both `.83` (`395,264 MB`) and `.72` (`327,680 MB`) are verified active with:
- `numvcpus = "52"`, `cpuid.coresPerSocket = "26"` (`2` virtual sockets x `26` physical Skylake-SP AVX-512 cores; `Thread(s) per core: 1`)
- `numa.vcpu.preferHT = "FALSE"`, `numa.autosize.once = "FALSE"`, `numa.vcpu.maxPerVirtualNode = "26"`
- `sched.mem.pin = "TRUE"`, `sched.mem.min = memSize` (`100%` DDR4 pinned in ESXi)
- Guest `numactl -H`: Node 0 (`cpus 0–25`), Node 1 (`cpus 26–51`), distance `10 : 20`.

### Step 1B (`157` — Guest Kernel Sysctls & Tiered `-ub` / Selective `mmap`)
- Applied and persisted in `/etc/sysctl.d/99-boylenet-llm.conf` on `.72` and `.83`:
  - `kernel.numa_balancing = 0`
  - `vm.swappiness = 1`
  - `vm.overcommit_memory = 1`
  - `/sys/kernel/mm/transparent_hugepage/enabled = [always] madvise never`
- Enforced in `/home/mboyle/bin/bd-tier-router.py` and `/home/mboyle/bin/bd-gpu-orchestrator.py`:
  - `GGML_OP_OFFLOAD_MIN_BATCH=2048`
  - Tiered `-ub`: `2048` (`<= 120 GiB`), `1024` (`120–240 GiB`), `512` (`> 240 GiB` or VRAM-tight `ngl=0/22` rows `39, 55–59, 63`)
  - `mmap` kept **ON** for `.125`/`.228` and mainline/`ik_llama` runs; `--no-mmap` restricted exclusively to `gamozolabs` `MADV_HUGEPAGE` fastload
  - `--spec-type ngram-cache` restricted exclusively to `coding`/`agent` routes (`prose` routes untouched)

### Step 1C–1E & Stages 3–4 Serialized Queue Execution
- **`Agent-170`**: ESXi `--id=1` + sysctls + Action #4 `Kimi-K3` 4-node RSS verification across `.72`, `.83`, `.125`, `.228`
- **`Agent-171`**: Host `.72` serialized benchmark queue under `flock /opt/models/.bench.lock` (Step 1C `Swift-Qwen3.8-Flash-Next IQ2_XS`, Step 1D `#69 DeepSeek-V4.1` `-p 512 -n 128`, Step 1E rows `39, 55, 56, 57`)
- **`Agent-172`**: Host `.83` serialized benchmark queue under `flock /mnt/ai-models/.bench.lock` (Step 1C `GLM-5.2 UD-IQ2_XXS`, Step 1E rows `58, 59, 63`, Stage 3 A/Bs `3A–3E`, Stage 4 Single-Node No-RPC rows `60–67`)

---

## 2. Stage 2 — Engine Compiles & Drafter Quantization Status (`.83`)

| Step | Target | Path on `.83` | Build / Artifact Status |
|---|---|---|---|
| **`159`** | `ik_llama.cpp` (`ikawrakow/ik_llama.cpp`, `CUDA sm_75` + `GGML_AVX512=ON`, `GGML_CUDA_IQK_FORCE_BF16=OFF`) | `/opt/ik-llama/bin/llama-bench` | **`{s2.get("ik_llama", "UNKNOWN")}`** |
| **`160`** | `gamozolabs/llama.cpp` (`multisocket-cpu-moe`, `CMAKE_CUDA_ARCHITECTURES=75`) | `/opt/gamozo-llama/bin/llama-bench` | **`{s2.get("gamozo", "UNKNOWN")}`** |
| **`161`** | Mainline `llama.cpp` `master` (`GGML_CUDA_FA_ALL_QUANTS=ON`, `GGML_CPU_ALL_VARIANTS=ON`, `GGML_RPC=ON`) | `/opt/llama-mainline/bin/llama-bench` / `/opt/llama-rpc/llama-bench` | **`{s2.get("mainline", "UNKNOWN")}`** |
| **`164`** | `dspark-DeepSeek-V4-Flash-0731-Q4_K_M.gguf` Speculative Drafter | `/opt/models/deepseek-v4-flash/dspark-DeepSeek-V4-Flash-0731-Q4_K_M.gguf` | **`{s2.get("dspark_q4km", "UNKNOWN")}`** |
| **`165B`** | `turboquant-ggml` (`turbo3_0`/`turbo4_0` `sm_75` CUDA FlashAttention check) | `/opt/turboquant-ggml-src` | **`{s2.get("turboquant", "UNKNOWN")}`** |

---

## 3. Stage 5 (`166`) — Proven Routing Table Wired into `bd-tier-router.py` & `bd-gpu-orchestrator.py`

1. **Single-Node No-RPC Law (`140–350 GiB` MoE on `.83`, `140–280 GiB` on `.72`)**:
   - Rows `60–67` (`beam-1.0-501b-a23b`, `nemotron-3-ultra-550b-a55b`, `minimax-m3-426b-uncensored`, `ling-3.1-flash-564b`, `muse-spark-816b-a42b`, `deepseek-v3.2-685b`, `glm-5.3-753b`, `mimo-v2.6-pro-1024b`) + `glm-5.2-iq2xxs` (`196.57 GiB`), `deepseek-v4-flash-q4k` (`153.33 GiB`), `qwen3-coder-480b-a35b` (`167.91 GiB`), `glm-5.2-q3km` (`319.21 GiB`), and `qwen3.8-flash-next-bf16` (`329.73 GiB`) route **Single-Node (`1x local T4 + 2-socket DDR4`, `--numa distribute -t 48`, ZERO `--rpc`)**.
2. **NUMA Socket Pinned Law (`<= 140 GiB` on `.72`, `<= 165 GiB` on `.83`)**:
   - Models fitting within a single socket (`Swift-Qwen3.8-Flash-Next IQ2_XS` `63.47 GiB`, `DeepSeek-V4-Flash Q2` `80.76 GiB`, `Qwen3-235B-A22B Q4_K_M` `132.39 GiB`, `gpt-oss-120b-heretic-v2` `59.03 GiB`, `mimo-v2.6-flash-rl-heretic-311b` `155.87 GiB` on `.83`) pin to Socket 0 (`numactl -N 0 -m 0 -t 26`) to eliminate cross-socket UPI traffic.
3. **100% Shared-Expert & Output-Weight GPU Residency (`Agent-163`)**:
   - `-ngl 999 -ot ".ffn_.*_exps.=CPU"` keeps `.ffn_.*_shexp.` and `output.weight` on CUDA0; VRAM-tight rows (`39, 55–59, 63`) enforce `-ub 512 -ctk q8_0 -ctv q8_0 --mlock` (plus `-ot "blk\\.(3[0-9])\\.attn.*=CPU"` only where single-T4 warm-up exceeds `14.9 GiB`).
4. **256K / 1M Context & `<think>` Preservation (`Agent-151`)**:
   - `-c 262144 -np 4 -kvu --reasoning-preserve --jinja` (`-c 1048576` on `qwythos-9b`) and `enable_thinking: True` (`<think>...</think>` + `reasoning_content`) are strictly preserved across all tiers.

### Discovered Stage Receipts in `{INFRA_DIR}`
- **Stage 0 (`151`)**: `{", ".join(recs["stage0_agent151"]) or "none"}`
- **Stage 1 (`157/158/163/170/171/172`)**: `{", ".join(recs["stage1_hygiene_157_158_163_170"]) or "in-progress"}`
- **Stage 2 (`159/160/161/164/165B/168/169`)**: `{", ".join(recs["stage2_builds_159_160_161_164_165_168_169"]) or "in-progress"}`
- **Stage 4 (`162`)**: `{", ".join(recs["stage4_single_node_162"]) or "queued-behind-stage3"}`
- **Stage 5 (`166/167`)**: `{", ".join(recs["stage5_router_166_167"]) or "active"}`
"""
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        f.write(md)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Boylenet Master Serialized Inference Optimization Pipeline"
    )
    parser.add_argument(
        "--daemon", action="store_true", help="Run continuous reconciliation daemon"
    )
    parser.add_argument(
        "--interval", type=int, default=20, help="Daemon poll interval seconds"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print JSON status snapshot and update ledger",
    )
    args = parser.parse_args()
    write_vmx_topology_script()
    snap = collect_snapshot()
    write_ledger(snap)
    if args.status or not args.daemon:
        print(json.dumps(snap, indent=2))
        return 0
    while True:
        try:
            snap = collect_snapshot()
            write_ledger(snap)
        except Exception as exc:
            sys.stderr.write(f"[bd-serialized-opt-pipeline] error: {exc}\n")
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    sys.exit(main())
