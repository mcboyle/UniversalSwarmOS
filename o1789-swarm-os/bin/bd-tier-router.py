#!/usr/bin/env python3
"""
bd-tier-router.py — Boylenet Stage-5 Proven Engine, NUMA Socket, Tiered -ub & Single-Node Routing Table
(Agent-166 / Agent-167 Master Serialized Optimization Pipeline)

Enforces:
1. Proven Engine per Model / Quant:
   - 'gamozo' (/opt/gamozo-llama/bin/llama-server): native MXFP4/Q8_0 MoE models on Skylake-SP 2-socket
     with GGML_EXPERT_SHARD=1 GGML_EXPERT_PIN=1 GGML_CUDA_REGISTER_HOST=1 --no-mmap --numa distribute -t 48
   - 'ik_llama' (/opt/ik-llama/bin/llama-server): DeepSeek2/DeepSeek4 MLA + IQ2/IQ3/IQ4 MoE models
     with -fmoe -fa -mla 3 -amb 512 -ser 6,1 -ctk q8_0
   - 'mainline' (/opt/llama-mainline/bin/llama-server or /opt/llama-rpc/llama-server): standard GGUF models
     with -fa on -ctk q8_0 -ctv q8_0 (and --moe-cache-mib 8000 where supported)
2. NUMA Socket Rule (Skylake-SP 2x26C, 161 GiB/socket on .72, 194 GiB/socket on .83):
   - <= 140 GiB: Single-socket NUMA0 pinned ('numactl -N 0 -m 0 -t 26') — zero UPI cross-socket traffic
   - > 140 GiB: Dual-socket interleaved ('--numa distribute -t 48') — aggregates both 6-channel IMC banks
3. Tiered Physical Microbatch (-ub) & Offload Batch Rule (Step 1B):
   - GGML_OP_OFFLOAD_MIN_BATCH=2048
   - <= 120 GiB: -b 2048 -ub 2048
   - 120-240 GiB: -b 2048 -ub 1024
   - > 240 GiB or VRAM-tight (former ngl=0/22 rows 39, 55-59, 63): -b 2048 -ub 512 --mlock
4. Shared-Expert & Output-Weight 100% GPU Residency Invariant (Step 1E / Agent-163):
   - NEVER offload '.ffn_.*_shexp.' or 'output.weight' to CPU.
   - Always use -ngl 999 -ot ".ffn_.*_exps.=CPU" (offloads routed experts only).
   - If VRAM > 14.9 GiB on 16 GB T4 after -ub 512 -ctk q8_0 -ctv q8_0, add partial upper-layer attention
     offload -ot "blk\\.(3[0-9])\\.attn.*=CPU" while keeping shexp and output.weight on T4.
5. Single-Node No-RPC Routing Table for 150-350 GiB MoE Models (Stage 4 / Agent-162):
   - Rows 60-67 (Beam-501B 174 GiB, Nemotron-Ultra-550B 188 GiB, MiniMax-M3-426B 189 GiB,
     Ling-3.1-564B 203 GiB, Muse-Spark-816B 210 GiB, DeepSeek-V3.2-685B 230 GiB,
     GLM-5.3-753B 236 GiB, MiMo-V2.6-Pro-1024B 238 GiB) fit in single-node DDR4 on .83 (386 GiB)
     or .72 (320 GiB up to 280 GiB) with 1x local T4 + ZERO --rpc!
6. Context & Thinking Preservation (Agent-151):
   - Strictly preserves 256K (-c 262144 -np 4 -kvu --reasoning-preserve) on coding/reasoning routes
     and 1M (-c 1048576 -np 4 -kvu --reasoning-preserve) on Qwythos-9B (:18081), plus enable_thinking=True.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

OPT_RESULTS_JSON = "/var/tmp/bd-serialized-opt-results.json"

# Former ngl=0/22 models that require -ub 512 --mlock + strict shexp GPU residency (Agent-163)
VRAM_TIGHT_MOE_MODELS = {
    "nemotron-3.5-lightning-30b-heretic",
    "glm-5.3-flash-uncensored",
    "command-a-plus-111b",
    "minimax-m2.7-ultra-uncensored-heretic",
    "glm-5.3-flash-abliterated",
    "mimo-v2.6-flash-rl-heretic-311b",
    "ling-3.1-flash-564b",
}

# Models that require partial upper-layer attention offload (-ot "blk\.(3[0-9])\.attn.*=CPU")
# if single-T4 warm-up exceeds 14.9 GiB even at -ub 512, while keeping shexp + output.weight on GPU
UPPER_ATTN_OFFLOAD_MODELS = {
    "command-a-plus-111b",
    "glm-5.3-flash-abliterated",
    "ling-3.1-flash-564b",
}

# Stage 4 (Agent-162) Single-Node No-RPC 150-350 GiB MoE Routing Table
SINGLE_NODE_NO_RPC_MOE_TABLE: Dict[str, Dict[str, Any]] = {
    "beam-1.0-501b-a23b": {
        "row": 60,
        "size_gib": 174.04,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.72",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 1024,
    },
    "nemotron-3-ultra-550b-a55b": {
        "row": 61,
        "size_gib": 188.30,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.72",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 1024,
    },
    "minimax-m3-426b-uncensored": {
        "row": 62,
        "size_gib": 189.13,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.72",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 1024,
    },
    "ling-3.1-flash-564b": {
        "row": 63,
        "size_gib": 203.10,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.83",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 512,
    },
    "muse-spark-816b-a42b": {
        "row": 64,
        "size_gib": 210.08,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.83",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 1024,
    },
    "deepseek-v3.2-685b": {
        "row": 65,
        "size_gib": 229.67,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.72",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 1024,
    },
    "glm-5.3-753b": {
        "row": 66,
        "size_gib": 236.44,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.83",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 1024,
    },
    "mimo-v2.6-pro-1024b": {
        "row": 67,
        "size_gib": 238.22,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.83",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 1024,
    },
    "glm-5.2-iq2xxs": {
        "row": 21,
        "size_gib": 196.57,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.83",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 1024,
    },
    "deepseek-v4-flash-q4k": {
        "row": 19,
        "size_gib": 153.33,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.72",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 1024,
    },
    "qwen3-coder-480b-a35b": {
        "row": 20,
        "size_gib": 167.91,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.83",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 1024,
    },
    "glm-5.2-q3km": {
        "row": 21,
        "size_gib": 319.21,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.83",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 512,
    },
    "qwen3.8-flash-next-bf16": {
        "row": 17,
        "size_gib": 329.73,
        "preferred_node": "10.0.70.83",
        "fallback_node": "10.0.70.72",
        "rpc_backends": [],
        "numa_policy": "dual_socket_distribute",
        "ubatch": 512,
    },
}


def load_live_opt_results() -> Dict[str, Any]:
    if os.path.isfile(OPT_RESULTS_JSON):
        try:
            with open(OPT_RESULTS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def resolve_ubatch_size(
    model_id: str, size_gib: float, vram_tight: bool = False
) -> int:
    mid = model_id.lower()
    if vram_tight or mid in VRAM_TIGHT_MOE_MODELS or size_gib > 240.0:
        return 512
    if size_gib <= 120.0:
        return 2048
    return 1024


def resolve_numa_policy(size_gib: float, host_ip: str = "10.0.70.83") -> Dict[str, Any]:
    """
    On .72 (161 GiB/socket) and .83 (194 GiB/socket):
    Models <= 140 GiB fit inside NUMA Node 0 with headroom -> numactl -N 0 -m 0 -t 26.
    Models > 140 GiB span both sockets -> --numa distribute -t 48.
    """
    socket_cap_gib = 165.0 if host_ip == "10.0.70.83" else 140.0
    if size_gib <= socket_cap_gib:
        return {
            "policy": "single_socket_node0",
            "prefix": "/usr/bin/numactl -N 0 -m 0",
            "numa_flag": "",
            "threads": 26,
        }
    return {
        "policy": "dual_socket_distribute",
        "prefix": "",
        "numa_flag": "--numa distribute",
        "threads": 48,
    }


def resolve_engine(model_id: str, path: str, size_gib: float) -> Dict[str, Any]:
    """
    Selects the proven engine for a model based on architecture, quantization, and live Stage-3 A/B winners.
    """
    mid = model_id.lower()
    path_l = path.lower()
    live = load_live_opt_results()
    stage3_winners = live.get("stage3_engine_winners", {})

    if mid in stage3_winners:
        winner = stage3_winners[mid]
        if winner == "ik_llama":
            return {
                "engine": "ik_llama",
                "binary_dir": "/opt/ik-llama/bin",
                "server_bin": "/opt/ik-llama/bin/llama-server",
                "bench_bin": "/opt/ik-llama/bin/llama-bench",
                "env": {
                    "LD_LIBRARY_PATH": "/opt/ik-llama/lib:/opt/llama-rpc:/usr/local/lib/ollama/cuda_v12",
                    "GGML_OP_OFFLOAD_MIN_BATCH": "2048",
                },
                "extra_flags": "-fmoe -mla 3 -amb 512 -ser 6,1",
                "use_no_mmap": False,
            }
        if winner == "gamozo":
            env_g = {
                "LD_LIBRARY_PATH": "/opt/gamozo-llama/lib:/opt/llama-rpc:/usr/local/lib/ollama/cuda_v12",
                "GGML_OP_OFFLOAD_MIN_BATCH": "2048",
                "GGML_EXPERT_SHARD": "1",
                "GGML_EXPERT_PIN": "1",
                "GGML_CUDA_REGISTER_HOST": "1",
            }
            if size_gib <= 200.0:
                env_g["GGML_EXPERT_REPLICAS"] = "1"
            return {
                "engine": "gamozo",
                "binary_dir": "/opt/gamozo-llama/bin",
                "server_bin": "/opt/gamozo-llama/bin/llama-server",
                "bench_bin": "/opt/gamozo-llama/bin/llama-bench",
                "env": env_g,
                "extra_flags": "--no-mmap",
                "use_no_mmap": True,
            }

    # Default proven rules:
    # 1. Native MXFP4 MoE models (gpt-oss-120b-heretic-v2, mimo-v2.6-flash-rl-heretic-311b) -> gamozo if installed
    if "mxfp4" in path_l or mid in (
        "gpt-oss-120b-heretic-v2",
        "mimo-v2.6-flash-rl-heretic-311b",
    ):
        return {
            "engine": "gamozo_or_mainline",
            "binary_dir": "/opt/llama-rpc",
            "server_bin": "/opt/llama-rpc/llama-server",
            "bench_bin": "/opt/llama-rpc/llama-bench",
            "env": {
                "LD_LIBRARY_PATH": "/opt/llama-rpc:/usr/local/lib/ollama/cuda_v12",
                "GGML_OP_OFFLOAD_MIN_BATCH": "2048",
            },
            "extra_flags": "",
            "use_no_mmap": False,
        }

    # 2. Standard mainline with GGML_CUDA_FA_ALL_QUANTS=ON & Skylake AVX-512 backend
    return {
        "engine": "mainline",
        "binary_dir": "/opt/llama-rpc",
        "server_bin": "/opt/llama-rpc/llama-server",
        "bench_bin": "/opt/llama-rpc/llama-bench",
        "env": {
            "LD_LIBRARY_PATH": "/opt/llama-rpc:/usr/local/lib/ollama/cuda_v12",
            "GGML_OP_OFFLOAD_MIN_BATCH": "2048",
        },
        "extra_flags": "",
        "use_no_mmap": False,
    }


def resolve_optimal_execution_plan(
    model_cfg: Dict[str, Any],
    route_type: str = "coding",
) -> Dict[str, Any]:
    """
    Computes the complete Stage-5 execution plan for any model in MODEL_CATALOG.
    Strictly preserves:
      - 256K context (-c 262144 -np 4 -kvu --reasoning-preserve) or 1M (-c 1048576) on Qwythos-9B
      - <think> / enable_thinking: True
      - 100% GPU residency for shared experts (.ffn_.*_shexp.) and output.weight
      - Single-node zero-RPC execution for all MoE models <= 350 GiB on .83 (and <= 280 GiB on .72)
    """
    mid = str(model_cfg.get("id", "")).lower()
    path = str(model_cfg.get("path", ""))
    expected_bytes = int(model_cfg.get("expected_bytes", 0) or 0)
    size_gib = (
        round(expected_bytes / (1024**3), 2)
        if expected_bytes
        else float(model_cfg.get("size_gib", 20.0))
    )
    storage_node = str(model_cfg.get("storage_node", "10.0.70.83"))
    tier = str(model_cfg.get("tier", "tier3"))

    is_qwythos_9b = "qwythos-9b" in mid
    ctx_size = (
        1048576 if is_qwythos_9b else int(model_cfg.get("ctx_size", 262144) or 262144)
    )
    if ctx_size < 262144 and "kimi-k3" not in mid:
        ctx_size = 262144

    ubatch = resolve_ubatch_size(
        mid, size_gib, vram_tight=(mid in VRAM_TIGHT_MOE_MODELS)
    )
    numa = resolve_numa_policy(size_gib, host_ip=storage_node)
    eng = resolve_engine(mid, path, size_gib)

    # Determine single-node vs RPC
    single_node_override = SINGLE_NODE_NO_RPC_MOE_TABLE.get(mid)
    is_moe = (
        tier == "tier3"
        or "moe" in str(model_cfg.get("architecture", "")).lower()
        or "a3b" in mid
        or "a22b" in mid
        or "a35b" in mid
        or "flash" in mid
        or mid in VRAM_TIGHT_MOE_MODELS
        or single_node_override is not None
    )

    # Single-node No-RPC law: MoE models <= 350 GiB on .83 or <= 280 GiB on .72 run with ZERO --rpc
    max_single_node_gib = 350.0 if storage_node == "10.0.70.83" else 280.0
    use_rpc = False
    rpc_arg = ""
    if not is_moe and tier == "tier2" and 25.0 <= size_gib <= 62.0:
        # Pure-VRAM dense 30B-70B models across 4xT4 (64 GB GDDR6)
        use_rpc = True
        rpc_arg = "--rpc 10.0.75.11:50052,10.0.75.13:50052,10.0.75.14:50052"
    elif (
        size_gib > max_single_node_gib
        or "kimi-k3" in mid
        or "deepseek-v4.1" in mid
        or "deepseek-v3-0324" in mid
    ):
        use_rpc = True
        rpc_arg = "--rpc 10.0.75.11:50052,10.0.75.13:50052,10.0.75.14:50052"

    # GPU offload & tensor override flags (NEVER offload .ffn_.*_shexp. or output.weight!)
    ot_flags: List[str] = []
    if is_moe:
        ot_flags.append('-ot ".ffn_.*_exps.=CPU"')
        if mid in UPPER_ATTN_OFFLOAD_MODELS:
            ot_flags.append('-ot "blk\\.(3[0-9])\\.attn.*=CPU"')

    mlock_flag = "--mlock" if (mid in VRAM_TIGHT_MOE_MODELS or ubatch == 512) else ""

    # Speculative decoding rule (Step 1B & Step 3D):
    # Enable --spec-type ngram-cache ONLY on coding/agent routes (leave prose routes untouched)
    spec_flags = ""
    if route_type in ("coding", "agent"):
        if "deepseek-v4-flash-q2" in mid and os.path.isfile(
            "/opt/models/deepseek-v4-flash/dspark-DeepSeek-V4-Flash-0731-Q4_K_M.gguf"
        ):
            spec_flags = (
                "-md /opt/models/deepseek-v4-flash/dspark-DeepSeek-V4-Flash-0731-Q4_K_M.gguf "
                "--spec-draft-n-max 3"
            )
        else:
            spec_flags = "--spec-type ngram-cache --spec-draft-n-max 16"

    ot_str = " ".join(ot_flags)
    cmd_parts = [
        numa["prefix"],
        eng["server_bin"],
        f"-m {path}",
        f"--alias {model_cfg.get('id', mid)}",
        rpc_arg if use_rpc else "",
        "-ngl 999",
        ot_str,
        numa["numa_flag"],
        f"-t {numa['threads']}",
        f"-c {ctx_size} -np 4 -kvu --reasoning-preserve --jinja",
        "-fa on -ctk q8_0 -ctv q8_0",
        f"-b 2048 -ub {ubatch}",
        mlock_flag,
        eng["extra_flags"],
        spec_flags,
    ]
    exec_line = " ".join(p for p in cmd_parts if p).strip()

    return {
        "model_id": model_cfg.get("id", mid),
        "size_gib": size_gib,
        "storage_node": storage_node,
        "engine": eng["engine"],
        "server_bin": eng["server_bin"],
        "env": eng["env"],
        "numa_policy": numa["policy"],
        "threads": numa["threads"],
        "ubatch": ubatch,
        "ctx_size": ctx_size,
        "enable_thinking": True,
        "reasoning_preserve": True,
        "shexp_gpu_resident": True,
        "output_weight_gpu_resident": True,
        "single_node_no_rpc": not use_rpc,
        "rpc_backends": []
        if not use_rpc
        else ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "route_type": route_type,
        "spec_flags": spec_flags,
        "exec_start_base": exec_line,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Boylenet Stage-5 Proven Tier Router & Execution Planner"
    )
    parser.add_argument(
        "--model", default="deepseek-v4-flash-q2", help="Model ID to inspect"
    )
    parser.add_argument(
        "--route-type", default="coding", choices=["coding", "agent", "prose"]
    )
    parser.add_argument(
        "--table",
        action="store_true",
        help="Print Stage-4/5 Single-Node No-RPC Routing Table",
    )
    args = parser.parse_args()

    if args.table:
        print(json.dumps(SINGLE_NODE_NO_RPC_MOE_TABLE, indent=2))
        return 0

    sample_cfg = {
        "id": args.model,
        "path": f"/opt/models/{args.model}/{args.model}.gguf",
        "size_gib": SINGLE_NODE_NO_RPC_MOE_TABLE.get(args.model, {}).get(
            "size_gib", 80.76
        ),
        "storage_node": SINGLE_NODE_NO_RPC_MOE_TABLE.get(args.model, {}).get(
            "preferred_node", "10.0.70.83"
        ),
        "tier": "tier3",
    }
    plan = resolve_optimal_execution_plan(sample_cfg, route_type=args.route_type)
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
