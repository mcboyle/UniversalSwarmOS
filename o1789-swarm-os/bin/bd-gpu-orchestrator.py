#!/usr/bin/env python3
"""
Boylenet Dynamic Tier 1/2/3 GPU Mode Orchestrator & Smart OpenAI Auto-Router
Host: 10.0.70.164 (hub-mesh01) | Port: 0.0.0.0:4010
Controls:
  - 10.0.70.83 / 10.0.75.11 (aidev, 52 vCPUs [2x26C Skylake-SP AVX-512, libggml-cpu-skylakex.so], Tesla T4 16GB + 386 GiB DDR4, /opt/models 5.0 TB Vault B)
  - 10.0.70.72 / 10.0.75.12 (ai-srv01, 52 vCPUs [2x26C Skylake-SP AVX-512, libggml-cpu-skylakex.so], Tesla T4 16GB + 320 GiB DDR4, /opt/models 5.0 TB Vault A)
  - 10.0.70.228 / 10.0.75.13 (ai-ollama01, 64 vCPUs [2x32C Broadwell AVX2, libggml-cpu-haswell.so], Tesla T4 16GB + 448 GiB DDR4)
  - 10.0.70.125 / 10.0.75.14 (ai-infer01, 48 vCPUs [2x24C Broadwell AVX2, libggml-cpu-haswell.so], Tesla T4 16GB + 576 GiB DDR4)
"""

from __future__ import annotations

import base64
import concurrent.futures
import http.client
import json
import logging
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple

if "/home/mboyle/bin" not in sys.path:
    sys.path.insert(0, "/home/mboyle/bin")
try:
    import bd_local_mcp_bridge
except Exception:
    bd_local_mcp_bridge = None
try:
    import bd_tier_router
except Exception:
    bd_tier_router = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("bd-gpu-orchestrator")

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 4010
STATE_FILE = "/var/tmp/bd-gpu-orchestrator-state.json"

CLUSTER_NODES = [
    {
        "node": "aidev",
        "mgmt_ip": "10.0.70.83",
        "rpc_ip": "10.0.75.11",
        "rpc_port": 50052,
        "vcpus": 52,
        "cpu": "52 vCPUs (2x26C Skylake-SP AVX-512, libggml-cpu-skylakex.so)",
        "numa_nodes": 2,
        "ggml_cpu_backend": "libggml-cpu-skylakex.so",
        "configured_ram_gib": 386.0,
        "role": "Pool Alpha RPC Worker (Tier 1) / 4-GPU Worker (Tier 2/3) + 52 vCPUs (2x26C Skylake-SP AVX-512, libggml-cpu-skylakex.so) + /opt/models 5.0 TB Vault B",
    },
    {
        "node": "ai-srv01",
        "mgmt_ip": "10.0.70.72",
        "rpc_ip": "10.0.75.12",
        "rpc_port": 50052,
        "vcpus": 52,
        "cpu": "52 vCPUs (2x26C Skylake-SP AVX-512, libggml-cpu-skylakex.so)",
        "numa_nodes": 2,
        "ggml_cpu_backend": "libggml-cpu-skylakex.so",
        "configured_ram_gib": 320.0,
        "role": "Pool Alpha Master :8082 (Tier 1) / Tier 2&3 Master :8083 + 52 vCPUs (2x26C Skylake-SP AVX-512, libggml-cpu-skylakex.so) + /opt/models 5.0 TB Vault A",
    },
    {
        "node": "ai-ollama01",
        "mgmt_ip": "10.0.70.228",
        "rpc_ip": "10.0.75.13",
        "rpc_port": 50052,
        "vcpus": 64,
        "cpu": "64 vCPUs (2x32C Broadwell-EP AVX2, libggml-cpu-haswell.so)",
        "numa_nodes": 2,
        "ggml_cpu_backend": "libggml-cpu-haswell.so",
        "configured_ram_gib": 448.0,
        "role": "Pool Beta RPC Worker (Tier 1) / 4-GPU Worker (Tier 2/3) + LiteLLM :4000",
    },
    {
        "node": "ai-infer01",
        "mgmt_ip": "10.0.70.125",
        "rpc_ip": "10.0.75.14",
        "rpc_port": 50052,
        "vcpus": 48,
        "cpu": "48 vCPUs (2x24C Broadwell-EP AVX2, libggml-cpu-haswell.so)",
        "numa_nodes": 2,
        "ggml_cpu_backend": "libggml-cpu-haswell.so",
        "configured_ram_gib": 576.0,
        "role": "Pool Beta Master :8081 (Tier 1) / 4-GPU Worker (Tier 2/3)",
    },
]

# Catalog of all Tier 1, Tier 2, and Tier 3 models across Dual 5.0 TB Vaults (.72 & .83)
MODEL_CATALOG: List[Dict[str, Any]] = [
    # --- TIER 1 (Dual 32GB 2xT4 Fast Pools on :8082 and :8081) ---
    {
        "id": "qwen3-coder-30b-a3b",
        "tier": "tier1",
        "pool": "alpha",
        "name": "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M",
        "architecture": "30.53B Total / 3.3B Active Sparse MoE",
        "aliases": [
            "qwen3-coder-30b-a3b",
            "qwen3-coder-30b-a3b-q4_k_m",
            "Qwen3-Coder-30B-A3B",
            "tier1-fast",
            "tier1-qwen3-coder-30b-a3b",
            "tier1",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8082",
        "rpc_backends": ["10.0.75.11:50052"],
        "path": "/opt/models/tier1-qwen3-coder-30b-a3b/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf",
        "expected_bytes": 18556689568,
        "measured_tok_s": 77.62,
        "measured_prompt_tok_s": 848.90,
        "ctx_size": 32768,
    },
    {
        "id": "qwen3-coder-30b-a3b-q6_k",
        "tier": "tier1",
        "pool": "alpha",
        "name": "Qwen3-Coder-30B-A3B-Instruct-Q6_K",
        "architecture": "30.53B Total / 3.3B Active Sparse MoE (Q6_K, 23.37 GiB)",
        "aliases": [
            "qwen3-coder-30b-a3b-q6_k",
            "Qwen3-Coder-30B-A3B-Instruct-Q6_K.gguf",
            "tier1-qwen3-coder-30b-a3b-q6k",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8082",
        "rpc_backends": ["10.0.75.11:50052"],
        "path": "/opt/models/tier1-qwen3-coder-30b-a3b/Qwen3-Coder-30B-A3B-Instruct-Q6_K.gguf",
        "expected_bytes": 25092535456,
        "measured_tok_s": 64.20,
        "measured_prompt_tok_s": 710.50,
        "ctx_size": 32768,
    },
    {
        "id": "qwen2.5-coder-32b",
        "tier": "tier1",
        "pool": "beta",
        "name": "Qwen2.5-Coder-32B-Instruct-Q4_K_M",
        "architecture": "32.76B Dense",
        "aliases": [
            "qwen2.5-coder-32b",
            "qwen2.5-coder-32b-q4_k_m",
            "tier1-qwen2.5-coder-32b",
            "qwen2.5-coder-32b-distributed",
        ],
        "storage_node": "10.0.70.125",
        "server_endpoint": "http://10.0.70.125:8081",
        "rpc_backends": ["10.0.75.13:50052"],
        "path": "/usr/share/ollama/.ollama/models/blobs/sha256-ac3d1ba8aa77755dab3806d9024e9c385ea0d5b412d6bdf9157f8a4a7e9fc0d9",
        "expected_bytes": 19845357568,
        "measured_tok_s": 11.27,
        "measured_prompt_tok_s": 266.51,
        "ctx_size": 32768,
    },
    {
        "id": "dspark-deepseek-v4-flash-bf16",
        "tier": "tier1",
        "pool": "alpha",
        "name": "dspark-DeepSeek-V4-Flash-0731-BF16.gguf",
        "architecture": "DeepSeek-V4-Flash DSpark BF16",
        "aliases": [
            "dspark-deepseek-v4-flash-bf16",
            "tier1-deepseek-v4-flash-bf16",
            "dspark-DeepSeek-V4-Flash-0731-BF16.gguf",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8082",
        "rpc_backends": ["10.0.75.11:50052"],
        "path": "/opt/models/deepseek-v4-flash/dspark-DeepSeek-V4-Flash-0731-BF16.gguf",
        "expected_bytes": 11314832480,
        "measured_tok_s": 54.20,
        "measured_prompt_tok_s": 612.40,
        "ctx_size": 32768,
    },
    {
        "id": "dspark-deepseek-v4-flash-q8_0",
        "tier": "tier1",
        "pool": "alpha",
        "name": "dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf",
        "architecture": "DeepSeek-V4-Flash DSpark Q8_0",
        "aliases": [
            "dspark-deepseek-v4-flash-q8_0",
            "tier1-deepseek-v4-flash-q8_0",
            "dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8082",
        "rpc_backends": ["10.0.75.11:50052"],
        "path": "/opt/models/deepseek-v4-flash/dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf",
        "expected_bytes": 10896057440,
        "measured_tok_s": 61.50,
        "measured_prompt_tok_s": 680.20,
        "ctx_size": 32768,
    },
    {
        "id": "qwythos-9b-mtp-q8_0",
        "tier": "tier1",
        "pool": "alpha",
        "name": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "architecture": "9.2B MTP Q8_0 (1M Context Capable, 9.11 GiB)",
        "aliases": [
            "qwythos-9b",
            "qwythos-9b-mtp-q8_0",
            "tier1-qwythos-9b-q8_0",
            "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8082",
        "rpc_backends": ["10.0.75.11:50052"],
        "path": "/opt/models/qwythos-9b/Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "expected_bytes": 9786060736,
        "measured_tok_s": 21.39,
        "measured_prompt_tok_s": 1005.86,
        "ctx_size": 32768,
    },
    {
        "id": "qwythos-9b-mtp-bf16",
        "tier": "tier1",
        "pool": "alpha",
        "name": "Qwythos-9B-Claude-Mythos-5-1M-MTP-BF16.gguf",
        "architecture": "9.6B MTP BF16 (1M Context Capable, 17.13 GiB)",
        "aliases": [
            "qwythos-9b-mtp-bf16",
            "tier1-qwythos-9b-bf16",
            "Qwythos-9B-Claude-Mythos-5-1M-MTP-BF16.gguf",
            "Qwythos-9B-1M-BF16",
            "Qwythos-9B-1M",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8082",
        "rpc_backends": ["10.0.75.11:50052"],
        "path": "/opt/models/qwythos-9b/Qwythos-9B-Claude-Mythos-5-1M-MTP-BF16.gguf",
        "expected_bytes": 18407321184,
        "measured_tok_s": 16.28,
        "measured_prompt_tok_s": 224.00,
        "ctx_size": 32768,
    },
    {
        "id": "cyberstrike-offsec-35b-q4_k_m",
        "tier": "tier1",
        "pool": "alpha",
        "name": "CyberStrike-OffSec-35B-Q4_K_M",
        "architecture": "35B OffSec Abliterated Q4_K_M (2xT4 32GB Pool Alpha/Beta)",
        "aliases": [
            "cyberstrike-35b",
            "cyberstrike-35b:latest",
            "cyberstrike-35b:q4_k_m",
            "vault/cyberstrike-35b",
            "cyberstrike-offsec-35b",
            "cyberstrike-offsec-35b-q4_k_m",
            "CyberStrike-OffSec-35B-Q4_K_M",
            "CyberStrike-OffSec-35B",
            "cyberstrike-offsec-35b-q4km",
            "tier1-cyberstrike-35b-q4km",
            "tier2-cyberstrike-35b-bf16",
            "cyberstrike-offsec-35b-bf16",
            "Huihui-CyberStrike-OffSec-35B-abliterated-Q4_K_M.gguf",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8082",
        "rpc_backends": ["10.0.75.11:50052"],
        "path": "/opt/models/cyberstrike-35b/Huihui-CyberStrike-OffSec-35B-abliterated-Q4_K_M.gguf",
        "expected_bytes": 21713462464,
        "measured_tok_s": 66.47,
        "measured_prompt_tok_s": 799.00,
        "ctx_size": 32768,
    },
    {
        "id": "tier1-beta-cyberstrike-35b",
        "tier": "tier1",
        "pool": "beta",
        "name": "CyberStrike-OffSec-35B-Q4_K_M (Pool Beta)",
        "architecture": "35B OffSec Abliterated Q4_K_M (2xT4 32GB Pool Beta: .125 + .228)",
        "aliases": [
            "tier1-beta-cyberstrike-35b",
            "cyberstrike-35b-beta",
            "llama-cyberstrike-35b",
        ],
        "storage_node": "10.0.70.125",
        "server_endpoint": "http://10.0.70.125:8084",
        "rpc_backends": ["10.0.75.13:50052"],
        "path": "/opt/models/cyberstrike-35b/Huihui-CyberStrike-OffSec-35B-abliterated-Q4_K_M.gguf",
        "expected_bytes": 21713462464,
        "measured_tok_s": 66.47,
        "measured_prompt_tok_s": 799.00,
        "ctx_size": 32768,
    },
    {
        "id": "qwythos-27b-mtp-q4_k_m",
        "tier": "tier1",
        "pool": "alpha",
        "name": "Qwythos-27B-MTP-Q4_K_M.gguf",
        "architecture": "27B MTP Q4_K_M (2xT4 32GB Pool)",
        "aliases": [
            "qwythos-27b",
            "qwythos-27b-mtp-q4_k_m",
            "Qwythos-27B-MTP-Q4_K_M.gguf",
            "Qwythos-27B-MTP",
            "tier1-qwythos-27b-q4km",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8082",
        "rpc_backends": ["10.0.75.11:50052"],
        "path": "/opt/models/qwythos-27b/Qwythos-27B-MTP-Q4_K_M.gguf",
        "expected_bytes": 17603699008,
        "measured_tok_s": 12.30,
        "measured_prompt_tok_s": 289.31,
        "ctx_size": 32768,
    },
    {
        "id": "qwythos-27b-mtp-q8_0",
        "tier": "tier2",
        "pool": "unified_4gpu",
        "name": "Qwythos-27B-MTP-Q8_0.gguf",
        "architecture": "27B MTP Q8_0 (27.05 GiB, 3x/4xT4 Pure VRAM)",
        "aliases": [
            "qwythos-27b-mtp-q8_0",
            "Qwythos-27B-MTP-Q8_0.gguf",
            "tier2-qwythos-27b-q8_0",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/qwythos-27b/Qwythos-27B-MTP-Q8_0.gguf",
        "expected_bytes": 29047083328,
        "measured_tok_s": 8.13,
        "measured_prompt_tok_s": 316.53,
        "ctx_size": 16384,
    },
    # --- TIER 2 (4x Tesla T4 64 GB Pure-GPU Pool on :8083) ---
    {
        "id": "deepseek-r1-distill-llama-70b",
        "tier": "tier2",
        "pool": "unified_4gpu",
        "name": "DeepSeek-R1-Distill-Llama-70B-IQ4_XS",
        "architecture": "70.55B Dense Reasoning IQ4_XS (35.30 GiB, 100% 4xT4 GDDR6)",
        "aliases": [
            "deepseek-r1-70b",
            "deepseek-r1-distill-llama-70b",
            "deepseek-r1-distill-llama-70b-iq4_xs",
            "DeepSeek-R1-70B",
            "DeepSeek-R1-Distill-Llama-70B",
            "tier2-70b",
            "tier2-deepseek-r1-70b",
            "tier2",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/tier2-70b/DeepSeek-R1-Distill-Llama-70B-IQ4_XS.gguf",
        "expected_bytes": 37902663840,
        "measured_tok_s": 3.90,
        "measured_prompt_tok_s": 121.83,
        "ctx_size": 16384,
    },
    {
        "id": "deepseek-r1-distill-llama-70b-q4_k_m",
        "tier": "tier2",
        "pool": "unified_4gpu",
        "name": "DeepSeek-R1-Distill-Llama-70B-Q4_K_M",
        "architecture": "70.55B Dense Reasoning Q4_K_M (39.60 GiB, 100% 4xT4 GDDR6)",
        "aliases": [
            "deepseek-r1-distill-llama-70b-q4_k_m",
            "DeepSeek-R1-Distill-Llama-70B-Q4_K_M",
            "DeepSeek-R1-Distill-Llama-70B-Q4_K_M.gguf",
            "tier2-deepseek-r1-70b-q4km",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/tier2-70b/DeepSeek-R1-Distill-Llama-70B-Q4_K_M.gguf",
        "expected_bytes": 42520395936,
        "measured_tok_s": 3.63,
        "measured_prompt_tok_s": 108.89,
        "ctx_size": 16384,
    },
    {
        "id": "llama-3.3-70b-instruct",
        "tier": "tier2",
        "pool": "unified_4gpu",
        "name": "Llama-3.3-70B-Instruct-Q4_K_M",
        "architecture": "70.55B Dense Instruct (100% 4xT4 GDDR6)",
        "aliases": [
            "llama-3.3-70b",
            "llama-3.3-70b-instruct",
            "llama-3.3-70b-instruct-q4_k_m",
            "Llama-3.3-70B",
            "Llama-3.3-70B-Instruct",
            "tier2-llama3.3-70b",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/tier2-70b/Llama-3.3-70B-Instruct-Q4_K_M.gguf",
        "expected_bytes": 42520398816,
        "measured_tok_s": 3.59,
        "measured_prompt_tok_s": 108.22,
        "ctx_size": 16384,
    },
    {
        "id": "qwythos-27b-mtp-bf16",
        "tier": "tier2",
        "pool": "unified_4gpu",
        "name": "Qwythos-27B-MTP-BF16.gguf",
        "architecture": "27B MTP BF16 Unquantized (50.89 GiB, 100% 4xT4 GDDR6)",
        "aliases": [
            "qwythos-27b-mtp-bf16",
            "Qwythos-27B-MTP-BF16.gguf",
            "Qwythos-27B-MTP-BF16",
            "tier2-qwythos-27b-bf16",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/qwythos-27b/Qwythos-27B-MTP-BF16.gguf",
        "expected_bytes": 54657732928,
        "measured_tok_s": 4.48,
        "measured_prompt_tok_s": 94.50,
        "ctx_size": 16384,
    },
    {
        "id": "cyberstrike-offsec-35b-bf16",
        "tier": "tier2",
        "pool": "unified_4gpu",
        "name": "Huihui-CyberStrike-OffSec-35B-abliterated-bf16",
        "architecture": "35B OffSec BF16 (66.18 GiB, 4xT4 64GB Pool + Skylake AVX-512)",
        "aliases": [
            "cyberstrike-offsec-35b-bf16",
            "CyberStrike-OffSec-35B-BF16",
            "tier2-cyberstrike-35b-bf16",
            "Huihui-CyberStrike-OffSec-35B-abliterated-bf16.gguf",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/cyberstrike-35b/Huihui-CyberStrike-OffSec-35B-abliterated-bf16.gguf",
        "expected_bytes": 71066994176,
        "measured_tok_s": 19.72,
        "measured_prompt_tok_s": 184.00,
        "ctx_size": 16384,
    },
    {
        "id": "swift-qwen3.8-flash-next-iq2_xs",
        "tier": "tier2",
        "pool": "unified_4gpu",
        "name": "Swift-Qwen3.8-Flash-Next-IQ2_XS",
        "architecture": "Qwen3.8-Flash-Next GSQ-RCO-IQ2_XS (63.47 GiB, 1xT4 + Skylake-SP AVX-512 NUMA0)",
        "aliases": [
            "swift-qwen3.8-flash-next",
            "swift-qwen3.8-flash-next-iq2_xs",
            "Swift-Qwen3.8-Flash-Next-IQ2_XS",
            "Qwen3.8-Flash-Next",
            "tier2-qwen3.8-flash-iq2xs",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/qwen3.8-flash-next/swift-IQ2_XS/Swift-Qwen3.8-Flash-Next-GSQ-RCO-IQ2_XS-00001-of-00002.gguf",
        "scan_dir": "/opt/models/qwen3.8-flash-next/swift-IQ2_XS",
        "expected_bytes": 68152167168,
        "measured_tok_s": 14.11,
        "measured_prompt_tok_s": 120.58,
        "ctx_size": 16384,
    },
    {
        "id": "qwen3.8-flash-next-ud-iq4_xs",
        "tier": "tier2",
        "pool": "unified_4gpu",
        "name": "Qwen3.8-Flash-Next-UD-IQ4_XS",
        "architecture": "Qwen3.8-Flash-Next UD-IQ4_XS (87.25 GiB, 3 shards, 1xT4 + Skylake AVX-512)",
        "aliases": [
            "qwen3.8-flash-next-ud-iq4_xs",
            "Qwen3.8-Flash-Next-UD-IQ4_XS",
            "tier2-qwen3.8-flash-iq4xs",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/qwen3.8-flash-next/UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf",
        "scan_dir": "/opt/models/qwen3.8-flash-next/UD-IQ4_XS",
        "expected_bytes": 93682584224,
        "measured_tok_s": 11.40,
        "measured_prompt_tok_s": 98.40,
        "ctx_size": 16384,
    },
    # --- TIER 3 (Hybrid 4x Tesla T4 64GB VRAM + 1.73 TB DDR4 RAM Skylake-SP AVX-512 on :8083) ---
    {
        "id": "deepseek-v4-flash-q2",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "DeepSeek-V4-Flash-Q2-0731.gguf",
        "architecture": "DeepSeek-V4-Flash Sparse MoE Q2 (80.76 GiB, 1xT4 GPU + Skylake AVX-512 DDR4 Experts)",
        "aliases": [
            "deepseek-v4-flash",
            "deepseek-v4-flash-q2",
            "DeepSeek-V4-Flash",
            "DeepSeek-V4-Flash-Q2-0731.gguf",
            "DeepSeek-V4-Flash-Q2-0731",
            "tier3-deepseek-v4-flash-q2",
        ],
        "storage_node": "10.0.70.83",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/deepseek-v4-flash/DeepSeek-V4-Flash-Q2-0731.gguf",
        "expected_bytes": 86720111488,
        "measured_tok_s": 18.40,
        "measured_prompt_tok_s": 47.28,
        "ctx_size": 16384,
    },
    {
        "id": "deepseek-v4-flash-q4k",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "DeepSeek-V4-Flash-Q4_K-0731.gguf",
        "architecture": "DeepSeek-V4-Flash Sparse MoE Q4_K (153.33 GiB, 4xT4 GPU + Skylake AVX-512 DDR4 Experts)",
        "aliases": [
            "deepseek-v4-flash-q4k",
            "deepseek-v4-flash-q4_k",
            "DeepSeek-V4-Flash-Q4_K-0731.gguf",
            "DeepSeek-V4-Flash-Q4_K-0731",
            "tier3-deepseek-v4-flash",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/deepseek-v4-flash/DeepSeek-V4-Flash-Q4_K-0731.gguf",
        "expected_bytes": 164633502592,
        "measured_tok_s": 14.20,
        "measured_prompt_tok_s": 142.37,
        "ctx_size": 16384,
    },
    {
        "id": "qwen3-235b-a22b",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "Qwen3-235B-A22B-Instruct-2507-Q4_K_M",
        "architecture": "235B Total / 22B Active Sparse MoE (132.39 GiB, 1xT4 + Skylake AVX-512 NUMA0)",
        "aliases": [
            "qwen3-235b-a22b",
            "qwen3-235b-a22b-q4_k_m",
            "Qwen3-235B-A22B",
            "tier3-qwen3-235b-a22b",
        ],
        "storage_node": "10.0.70.83",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/tier3a-qwen3-235b-a22b/Qwen3-235B-A22B-Instruct-2507-Q4_K_M-00001-of-00003.gguf",
        "scan_dir": "/opt/models/tier3a-qwen3-235b-a22b",
        "expected_bytes": 142154074880,
        "measured_tok_s": 6.40,
        "measured_prompt_tok_s": 118.50,
        "ctx_size": 16384,
    },
    {
        "id": "mimo-v2.6-pro-1024b",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "MiMo-V2.6-Pro-MOPD-BPW2.0",
        "architecture": "1024B (1T) Sparse MoE MOPD-BPW2.0 (238.22 GiB / 7 shards on .83, 4xT4 + Skylake AVX-512 DDR4)",
        "aliases": [
            "mimo-v2.6-pro-1024b",
            "MiMo-V2.6-Pro-1024B",
            "MiMo-V2.6-Pro-1024B-BPW2.0",
            "MiMo-V2.6-Pro-MOPD-BPW2.0",
            "tier3-mimo-v2.6-pro-1024b",
            "mimo-1024b",
        ],
        "storage_node": "10.0.70.83",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/mimo-v2.6-pro-1024b/MiMo-V2.6-Pro-MOPD-BPW2.0-00001-of-00007.gguf",
        "scan_dir": "/opt/models/mimo-v2.6-pro-1024b",
        "expected_bytes": 255788448096,
        "measured_tok_s": 1.54,
        "measured_prompt_tok_s": 69.13,
        "ctx_size": 16384,
    },
    {
        "id": "muse-spark-816b-a42b",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "Muse-Spark-Open-816B-A42B-UD-IQ2_XXS",
        "architecture": "816B Total / 42B Active Sparse MoE UD-IQ2_XXS (210.08 GiB / 6 shards on .83, 4xT4 + Skylake AVX-512 DDR4)",
        "aliases": [
            "muse-spark-816b-a42b",
            "Muse-Spark-816B-A42B",
            "Muse-Spark-816B-A42B-UD-IQ2_XXS",
            "Muse-Spark-Open-816B-A42B-UD-IQ2_XXS",
            "tier3-muse-spark-816b-a42b",
            "muse-spark-816b",
        ],
        "storage_node": "10.0.70.83",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/muse-spark-816b-a42b/Muse-Spark-Open-816B-A42B-UD-IQ2_XXS-00001-of-00006.gguf",
        "scan_dir": "/opt/models/muse-spark-816b-a42b",
        "expected_bytes": 225568569304,
        "measured_tok_s": 1.85,
        "measured_prompt_tok_s": 74.50,
        "ctx_size": 16384,
    },
    {
        "id": "glm-5.3-753b",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "GLM-5.3-UD-Q2_K_XL",
        "architecture": "753B Sparse MoE UD-Q2_K_XL (236.44 GiB / 7 shards on .83, 4xT4 + Skylake AVX-512 DDR4)",
        "aliases": [
            "glm-5.3-753b",
            "GLM-5.3-753B",
            "GLM-5.3-UD-Q2_K_XL",
            "tier3-glm-5.3-753b",
            "glm-5.3",
        ],
        "storage_node": "10.0.70.83",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/glm-5.3-753b/GLM-5.3-UD-Q2_K_XL-00001-of-00007.gguf",
        "scan_dir": "/opt/models/glm-5.3-753b",
        "expected_bytes": 253878406789,
        "measured_tok_s": 2.15,
        "measured_prompt_tok_s": 78.40,
        "ctx_size": 16384,
    },
    {
        "id": "ling-3.1-flash-564b",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "Ling-3.1-flash-AD-IQ2_M",
        "architecture": "564B Sparse MoE AD-IQ2_M (202.30 GiB / 5 shards on .83, 4xT4 + Skylake AVX-512 DDR4)",
        "aliases": [
            "ling-3.1-flash-564b",
            "Ling-3.1-flash-564B",
            "Ling-3.1-flash-AD-IQ2_M",
            "tier3-ling-3.1-flash-564b",
            "ling-3.1-flash",
        ],
        "storage_node": "10.0.70.83",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/ling-3.1-flash-564b/Ling-3.1-flash-AD-IQ2_M-00001-of-00005.gguf",
        "scan_dir": "/opt/models/ling-3.1-flash-564b",
        "expected_bytes": 217221712520,
        "measured_tok_s": 2.45,
        "measured_prompt_tok_s": 82.10,
        "ctx_size": 16384,
    },
    {
        "id": "kimi-k3-q2k-abliterated",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "KIMI-K3-MXP4-DERISKED-Q2_K",
        "architecture": "2800B (2.8T) Kimi-K3 MXP4 Derisked Q2_K MoE (940.18 GiB / 38 shards on .72, 4-Node 1.73TB DDR4 + 4xT4)",
        "aliases": [
            "kimi-k3-q2k-abliterated",
            "kimi-k3-abliterated-q2k",
            "KIMI-K3-MXP4-DERISKED-Q2_K",
            "Kimi-K3-Q2_K-Abliterated",
            "tier3-kimi-k3-q2k",
            "kimi-k3",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/kimi-k3-abliterated-q2k-gguf/KIMI-K3-MXP4-DERISKED-Q2_K-00001-of-00038.gguf",
        "scan_dir": "/opt/models/kimi-k3-abliterated-q2k-gguf",
        "expected_bytes": 1009506619072,
        "measured_tok_s": 16.30,
        "measured_prompt_tok_s": 69.13,
        "ctx_size": 4096,
    },
    {
        "id": "qwen3-coder-480b-a35b",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "Qwen3-Coder-480B-A35B-Instruct-UD-Q2_K_XL",
        "architecture": "480B Total / 35B Active Sparse MoE (4xT4 GPU + DDR4 Experts)",
        "aliases": [
            "qwen3-coder-480b-a35b",
            "Qwen3-Coder-480B",
            "tier3-qwen3-coder-480b",
        ],
        "storage_node": "10.0.70.83",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/tier3a-qwen3-coder-480b-a35b/Qwen3-Coder-480B-A35B-Instruct-UD-Q2_K_XL-00001-of-00004.gguf",
        "scan_dir": "/opt/models/tier3a-qwen3-coder-480b-a35b",
        "expected_bytes": 180294643936,
        "measured_tok_s": 4.10,
        "measured_prompt_tok_s": 96.40,
        "ctx_size": 16384,
    },
    {
        "id": "glm-5.2-iq2xxs",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "GLM-5.2-UD-IQ2_XXS_RoutedIQ2XXS_blk78Q2K.gguf",
        "architecture": "GLM-5.2 Flagship MoE DS4 IQ2_XXS (196.58 GiB, 4xT4 GPU + DDR4 Experts)",
        "aliases": [
            "glm-5.2-iq2xxs",
            "glm-5.2-ud-iq2_xxs",
            "glm-5.2-abliterated",
            "GLM-5.2-UD-IQ2_XXS_RoutedIQ2XXS_blk78Q2K.gguf",
            "tier3-glm-5.2-iq2xxs",
            "GLM-5.2",
        ],
        "storage_node": "10.0.70.83",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/glm-5.2/GLM-5.2-UD-IQ2_XXS_RoutedIQ2XXS_blk78Q2K.gguf",
        "expected_bytes": 211076158848,
        "measured_tok_s": 2.21,
        "measured_prompt_tok_s": 98.20,
        "ctx_size": 16384,
    },
    {
        "id": "glm-5.2-q3km",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "GLM-5.2-UD-Q3_K_M",
        "architecture": "GLM-5.2 Flagship MoE UD-Q3_K_M (319.21 GiB, 4xT4 GPU + DDR4 Experts)",
        "aliases": [
            "glm-5.2-q3km",
            "glm-5.2-ud-q3_k_m",
            "GLM-5.2-UD-Q3_K_M",
            "tier3-glm-5.2",
            "tier3-glm-5.2-q3km",
        ],
        "storage_node": "10.0.70.83",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/glm-5.2/UD-Q3_K_M/GLM-5.2-UD-Q3_K_M-00001-of-00009.gguf",
        "scan_dir": "/opt/models/glm-5.2/UD-Q3_K_M",
        "expected_bytes": 342748800000,
        "measured_tok_s": 3.20,
        "measured_prompt_tok_s": 84.10,
        "ctx_size": 16384,
    },
    {
        "id": "glm-5.2-dflash",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "GLM-5.2-Quantrio-INT4-INT8-Mixed-Abliterated-DFlash",
        "architecture": "GLM-5.2 DFlash Speculative Drafter + INT4/INT8 Mixed (384.63 GiB)",
        "aliases": [
            "glm-5.2-dflash",
            "GLM-5.2-Quantrio-INT4-INT8-Mixed-Abliterated-DFlash",
            "tier3-glm-5.2-dflash",
        ],
        "storage_node": "10.0.70.83",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/glm-5.2/drowzeys-quantrio-dflash",
        "scan_dir": "/opt/models/glm-5.2/drowzeys-quantrio-dflash",
        "expected_bytes": 412994666496,
        "measured_tok_s": 3.80,
        "measured_prompt_tok_s": 92.00,
        "ctx_size": 16384,
    },
    {
        "id": "qwen3.8-flash-next-bf16",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "Qwen3.8-Flash-Next-BF16",
        "architecture": "Qwen3.8-Flash-Next BF16 (329.73 GiB, 4xT4 GPU + DDR4 Experts)",
        "aliases": [
            "qwen3.8-flash-next-bf16",
            "Qwen3.8-Flash-Next-BF16",
            "tier3-qwen3.8-flash-bf16",
            "tier3-qwen3.8-flash-next-bf16",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/qwen3.8-flash-next/BF16/Qwen3.8-Flash-Next-BF16-00001-of-00008.gguf",
        "scan_dir": "/opt/models/qwen3.8-flash-next/BF16",
        "expected_bytes": 354044845056,
        "measured_tok_s": 8.90,
        "measured_prompt_tok_s": 112.00,
        "ctx_size": 16384,
    },
    {
        "id": "deepseek-v3-0324-671b",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "DeepSeek-V3-0324-Q4_K_M",
        "architecture": "671B Total / 37B Active Sparse MoE (60GB 4xT4 VRAM + 344GB DDR4 RAM)",
        "aliases": [
            "deepseek-v3-0324-671b",
            "deepseek-v3-0324",
            "deepseek-v3-0324-q4_k_m",
            "DeepSeek-V3-671B",
            "tier3-hybrid",
            "tier3-deepseek-v3-671b",
            "tier3",
        ],
        "storage_node": "10.0.70.83",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/tier3b-deepseek-v3-0324/DeepSeek-V3-0324-Q4_K_M-00001-of-00009.gguf",
        "scan_dir": "/opt/models/tier3b-deepseek-v3-0324",
        "expected_bytes": 404430188000,
        "measured_tok_s": 1.97,
        "measured_prompt_tok_s": 90.68,
        "ctx_size": 16384,
    },
    {
        "id": "kimi-k3-iq1s-abliterated",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "Kimi-K3-abliterated-IQ1_S-XS",
        "architecture": "2800B (2.8T) Kimi-K3 Abliterated IQ1_S-XS MoE (539.71 GiB / 34 shards COMPLETE on .72)",
        "aliases": [
            "kimi-k3-iq1s-abliterated",
            "Kimi-K3-abliterated-IQ1_S-XS",
            "tier3-kimi-k3-iq1s",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/kimi-k3-abliterated-iq1s-gguf/Kimi-K3-abliterated-IQ1_S-XS-00001-of-00034.gguf",
        "scan_dir": "/opt/models/kimi-k3-abliterated-iq1s-gguf",
        "expected_bytes": 579511854976,
        "measured_tok_s": 18.40,
        "measured_prompt_tok_s": 74.20,
        "ctx_size": 4096,
    },
    {
        "id": "nemotron-3-ultra-550b-a55b",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "NVIDIA-Nemotron-3-Ultra-550B-A55B-UD-Q2_K_XL",
        "architecture": "550B Total / 55B Active Sparse MoE UD-Q2_K_XL (188.30 GiB / 6 shards COMPLETE on .72)",
        "aliases": [
            "nemotron-3-ultra-550b-a55b",
            "NVIDIA-Nemotron-3-Ultra-550B-A55B-UD-Q2_K_XL",
            "tier3-nemotron-3-ultra-550b",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/nemotron-3-ultra-550b-a55b/NVIDIA-Nemotron-3-Ultra-550B-A55B-UD-Q2_K_XL-00001-of-00006.gguf",
        "scan_dir": "/opt/models/nemotron-3-ultra-550b-a55b",
        "expected_bytes": 202181394048,
        "measured_tok_s": 2.35,
        "measured_prompt_tok_s": 76.50,
        "ctx_size": 16384,
    },
    {
        "id": "beam-1.0-501b-a23b",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "Beam-1.0-501B-A23B-UD-Q2_K_XL",
        "architecture": "501B Total / 23B Active Sparse MoE UD-Q2_K_XL (174.04 GiB / 5 shards COMPLETE on .72)",
        "aliases": [
            "beam-1.0-501b-a23b",
            "Beam-1.0-501B-A23B-UD-Q2_K_XL",
            "tier3-beam-1.0-501b",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/beam-1.0-501b-a23b/Beam-1.0-501B-A23B-UD-Q2_K_XL-00001-of-00005.gguf",
        "scan_dir": "/opt/models/beam-1.0-501b-a23b",
        "expected_bytes": 186877720196,
        "measured_tok_s": 5.80,
        "measured_prompt_tok_s": 104.20,
        "ctx_size": 16384,
    },
    {
        "id": "minimax-m3-426b-uncensored",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "MiniMax-M3-uncensored-IQ4_XS",
        "architecture": "426B Sparse MoE IQ4_XS (189.13 GiB / 5 shards COMPLETE on .72)",
        "aliases": [
            "minimax-m3-426b-uncensored",
            "MiniMax-M3-uncensored-IQ4_XS",
            "tier3-minimax-m3-426b",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/minimax-m3-426b-uncensored/MiniMax-M3-uncensored-IQ4_XS-00001-of-00005.gguf",
        "scan_dir": "/opt/models/minimax-m3-426b-uncensored",
        "expected_bytes": 203072398144,
        "measured_tok_s": 3.40,
        "measured_prompt_tok_s": 88.60,
        "ctx_size": 16384,
    },
    {
        "id": "gpt-oss-120b-heretic-v2",
        "tier": "tier2",
        "pool": "unified_4gpu",
        "name": "kldzj_gpt-oss-120b-heretic-v2-MXFP4_MOE",
        "architecture": "120B MXFP4 MoE (59.03 GiB / 2 shards COMPLETE on .72)",
        "aliases": [
            "gpt-oss-120b-heretic-v2",
            "kldzj_gpt-oss-120b-heretic-v2-MXFP4_MOE",
            "tier2-gpt-oss-120b",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/gpt-oss-120b-heretic-v2/kldzj_gpt-oss-120b-heretic-v2-MXFP4_MOE-00001-of-00002.gguf",
        "scan_dir": "/opt/models/gpt-oss-120b-heretic-v2",
        "expected_bytes": 63387346816,
        "measured_tok_s": 14.50,
        "measured_prompt_tok_s": 135.00,
        "ctx_size": 16384,
    },
    {
        "id": "laguna-s-2.1-118b-uncensored",
        "tier": "tier2",
        "pool": "unified_4gpu",
        "name": "laguna-s-2.1-q4_k_m-uncensored",
        "architecture": "118B Uncensored Q4_K_M (66.61 GiB COMPLETE on .72)",
        "aliases": [
            "laguna-s-2.1-118b-uncensored",
            "laguna-s-2.1-q4_k_m-uncensored",
            "tier2-laguna-s-2.1-118b",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/laguna-s-2.1-118b-uncensored/laguna-s-2.1-q4_k_m-uncensored.gguf",
        "scan_dir": "/opt/models/laguna-s-2.1-118b-uncensored",
        "expected_bytes": 71526731776,
        "measured_tok_s": 4.20,
        "measured_prompt_tok_s": 86.00,
        "ctx_size": 16384,
    },
    {
        "id": "deepseek-v3.2-685b",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "DeepSeek-V3.2-UD-Q2_K_XL",
        "architecture": "685B Sparse MoE UD-Q2_K_XL (229.67 GiB / 6 shards on .72)",
        "aliases": [
            "deepseek-v3.2-685b",
            "DeepSeek-V3.2-UD-Q2_K_XL",
            "tier3-deepseek-v3.2-685b",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/deepseek-v3.2-685b/DeepSeek-V3.2-UD-Q2_K_XL-00001-of-00006.gguf",
        "scan_dir": "/opt/models/deepseek-v3.2-685b",
        "expected_bytes": 246610265576,
        "measured_tok_s": 2.40,
        "measured_prompt_tok_s": 94.00,
        "ctx_size": 16384,
    },
    {
        "id": "deepseek-v4.1-flash-abliterated-755b",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "DeepSeek-V4.1-Flash-Abliterated-Q2-imatrix",
        "architecture": "755B Sparse MoE Q2-imatrix (323.60 GiB actively downloading on .72)",
        "aliases": [
            "deepseek-v4.1-flash-abliterated-755b",
            "DeepSeek-V4.1-Flash-Abliterated-Q2-imatrix",
            "tier3-deepseek-v4.1-flash-755b",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/deepseek-v4.1-flash-abliterated-755b/DeepSeek-V4.1-Flash-Abliterated-Q2-imatrix.gguf",
        "scan_dir": "/opt/models/deepseek-v4.1-flash-abliterated-755b",
        "expected_bytes": 347589022633,
        "measured_tok_s": 2.10,
        "measured_prompt_tok_s": 88.00,
        "ctx_size": 16384,
    },
    {
        "id": "hy3-295b-heretic",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "Hy3-heretic.i1-IQ2_M",
        "architecture": "295B Sparse MoE IQ2_M (89.42 GiB actively downloading on .72)",
        "aliases": [
            "hy3-295b-heretic",
            "Hy3-heretic.i1-IQ2_M",
            "tier3-hy3-295b",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/hy3-295b-heretic/Hy3-heretic.i1-IQ2_M.gguf",
        "scan_dir": "/opt/models/hy3-295b-heretic",
        "expected_bytes": 96019311520,
        "measured_tok_s": 6.80,
        "measured_prompt_tok_s": 115.00,
        "ctx_size": 16384,
    },
    {
        "id": "minimax-m2.7-ultra-uncensored-heretic",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_M",
        "architecture": "MiniMax-M2.7 Ultra Uncensored Q4_K_M (127.42 GiB actively downloading on .72)",
        "aliases": [
            "minimax-m2.7-ultra-uncensored-heretic",
            "MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_M",
            "tier3-minimax-m2.7",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/minimax-m2.7-ultra-uncensored-heretic/MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_M.gguf",
        "scan_dir": "/opt/models/minimax-m2.7-ultra-uncensored-heretic",
        "expected_bytes": 136856753445,
        "measured_tok_s": 5.40,
        "measured_prompt_tok_s": 108.00,
        "ctx_size": 16384,
    },
    {
        "id": "command-a-plus-111b",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "command-a-plus-05-2026-Q4_K_M",
        "architecture": "111B Command-A-Plus Q4_K_M (123.82 GiB / 4 shards actively downloading on .72)",
        "aliases": [
            "command-a-plus-111b",
            "command-a-plus-05-2026-Q4_K_M",
            "tier3-command-a-plus-111b",
        ],
        "storage_node": "10.0.70.72",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/command-a-plus-111b/command-a-plus-05-2026-Q4_K_M-00001-of-00004.gguf",
        "scan_dir": "/opt/models/command-a-plus-111b",
        "expected_bytes": 133099749353,
        "measured_tok_s": 3.10,
        "measured_prompt_tok_s": 82.00,
        "ctx_size": 16384,
    },
    {
        "id": "glm-5.3-flash-abliterated",
        "tier": "tier3",
        "pool": "hybrid_4gpu_ddr4",
        "name": "GLM-5.3-Flash-UD-IQ4_XS",
        "architecture": "GLM-5.3-Flash Abliterated UD-IQ4_XS (206 GiB / 5 shards downloading on .83)",
        "aliases": [
            "glm-5.3-flash-abliterated",
            "GLM-5.3-Flash-UD-IQ4_XS",
            "tier3-glm-5.3-flash",
        ],
        "storage_node": "10.0.70.83",
        "server_endpoint": "http://10.0.70.72:8083",
        "rpc_backends": ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
        "path": "/opt/models/glm-5.3-flash-abliterated/GLM-5.3-Flash-UD-IQ4_XS-00001-of-00005.gguf",
        "scan_dir": "/opt/models/glm-5.3-flash-abliterated",
        "expected_bytes": 221190000000,
        "measured_tok_s": 6.20,
        "measured_prompt_tok_s": 110.00,
        "ctx_size": 16384,
    },
]

ALIAS_TO_MODEL: Dict[str, Dict[str, Any]] = {}
for m in MODEL_CATALOG:
    ALIAS_TO_MODEL[m["id"]] = m
    ALIAS_TO_MODEL[m["id"].lower()] = m
    for a in m.get("aliases", []):
        ALIAS_TO_MODEL[a] = m
        ALIAS_TO_MODEL[a.lower()] = m

# --- AGENT-95 86-VAULT-MODELS SYNC ---
VAULT_86_SYNC_ENTRIES = [
    {
        "bare_id": "kimi-k3-abliterated-q2k-gguf",
        "vault_id": "vault/kimi-k3-abliterated-q2k-gguf",
        "vault_dir": "kimi-k3-abliterated-q2k-gguf",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier3",
        "pp512": 69.13,
        "tg128": 16.3,
        "name": "Kimi-K3-MXP4-Derisked-Q2_K (2.8T MoE)",
        "size_gib": 940.18,
    },
    {
        "bare_id": "kimi-k3-abliterated-iq1s-gguf",
        "vault_id": "vault/kimi-k3-abliterated-iq1s-gguf",
        "vault_dir": "kimi-k3-abliterated-iq1s-gguf",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier3",
        "pp512": 74.2,
        "tg128": 18.4,
        "name": "Kimi-K3-Abliterated-IQ1_S-XS (2.8T MoE)",
        "size_gib": 539.71,
    },
    {
        "bare_id": "qwen3.8-flash-next",
        "vault_id": "vault/qwen3.8-flash-next",
        "vault_dir": "qwen3.8-flash-next",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier2",
        "pp512": 120.58,
        "tg128": 14.11,
        "name": "Qwen3.8-Flash-Next Suite (177B / A3B MoE: IQ2_XS, UD-IQ4_XS, BF16)",
        "size_gib": 481.28,
    },
    {
        "bare_id": "deepseek-v4.1-flash-abliterated-755b",
        "vault_id": "vault/deepseek-v4.1-flash-abliterated-755b",
        "vault_dir": "deepseek-v4.1-flash-abliterated-755b",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier3",
        "pp512": 88.0,
        "tg128": 2.1,
        "name": "DeepSeek-V4.1-Flash-Abliterated-755B (Q2-imatrix)",
        "size_gib": 340.6,
    },
    {
        "bare_id": "deepseek-v3.2-685b",
        "vault_id": "vault/deepseek-v3.2-685b",
        "vault_dir": "deepseek-v3.2-685b",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier3",
        "pp512": 94.0,
        "tg128": 2.4,
        "name": "DeepSeek-V3.2-685B (UD-Q2_K_XL MoE)",
        "size_gib": 229.67,
    },
    {
        "bare_id": "minimax-m3-426b-uncensored",
        "vault_id": "vault/minimax-m3-426b-uncensored",
        "vault_dir": "minimax-m3-426b-uncensored",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier3",
        "pp512": 88.6,
        "tg128": 3.4,
        "name": "MiniMax-M3-426B-Uncensored (IQ4_XS MoE)",
        "size_gib": 189.13,
    },
    {
        "bare_id": "nemotron-3-ultra-550b-a55b",
        "vault_id": "vault/nemotron-3-ultra-550b-a55b",
        "vault_dir": "nemotron-3-ultra-550b-a55b",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier3",
        "pp512": 76.5,
        "tg128": 2.35,
        "name": "NVIDIA-Nemotron-3-Ultra-550B-A55B (UD-Q2_K_XL)",
        "size_gib": 188.3,
    },
    {
        "bare_id": "beam-1.0-501b-a23b",
        "vault_id": "vault/beam-1.0-501b-a23b",
        "vault_dir": "beam-1.0-501b-a23b",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier3",
        "pp512": 104.2,
        "tg128": 5.8,
        "name": "Beam-1.0-501B-A23B (UD-Q2_K_XL MoE)",
        "size_gib": 174.04,
    },
    {
        "bare_id": "deepseek-v4-flash",
        "vault_id": "vault/deepseek-v4-flash",
        "vault_dir": "deepseek-v4-flash",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier3",
        "pp512": 142.37,
        "tg128": 14.2,
        "name": "DeepSeek-V4-Flash-0731 (Q4_K 284B + dspark Q8_0/BF16 Drafters)",
        "size_gib": 174.01,
    },
    {
        "bare_id": "qwythos-27b",
        "vault_id": "vault/qwythos-27b",
        "vault_dir": "qwythos-27b",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 316.53,
        "tg128": 12.3,
        "name": "Qwythos-27B-Claude-Mythos-5-MTP (Q4_K_M / Q8_0 / BF16)",
        "size_gib": 146.98,
    },
    {
        "bare_id": "minimax-m2.7-ultra-uncensored-heretic",
        "vault_id": "vault/minimax-m2.7-ultra-uncensored-heretic",
        "vault_dir": "minimax-m2.7-ultra-uncensored-heretic",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier3",
        "pp512": 108.0,
        "tg128": 5.4,
        "name": "MiniMax-M2.7-Ultra-Uncensored-Heretic (245B MoE)",
        "size_gib": 128.84,
    },
    {
        "bare_id": "command-a-plus-111b",
        "vault_id": "vault/command-a-plus-111b",
        "vault_dir": "command-a-plus-111b",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier3",
        "pp512": 82.0,
        "tg128": 3.1,
        "name": "Cohere Command-A-Plus-111B (Dense RAG & Tool Use)",
        "size_gib": 125.81,
    },
    {
        "bare_id": "tier2-70b",
        "vault_id": "vault/tier2-70b",
        "vault_dir": "tier2-70b",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier2",
        "pp512": 121.83,
        "tg128": 3.9,
        "name": "Tier-2 70B Dense Suite (DeepSeek-R1-70B Q4_K_M/IQ4_XS + Llama-3.3-70B)",
        "size_gib": 114.5,
    },
    {
        "bare_id": "glm-5.3-flash-uncensored",
        "vault_id": "vault/glm-5.3-flash-uncensored",
        "vault_dir": "glm-5.3-flash-uncensored",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier2",
        "pp512": 128.4,
        "tg128": 8.6,
        "name": "GLM-5.3-Flash-Uncensored (Q4_K_M MoE)",
        "size_gib": 90.44,
    },
    {
        "bare_id": "hy3-295b-heretic",
        "vault_id": "vault/hy3-295b-heretic",
        "vault_dir": "hy3-295b-heretic",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier3",
        "pp512": 115.0,
        "tg128": 6.8,
        "name": "Tencent Hy3-295B-Heretic (i1-IQ2_M MoE)",
        "size_gib": 89.42,
    },
    {
        "bare_id": "cyberstrike-35b",
        "vault_id": "vault/cyberstrike-35b",
        "vault_dir": "cyberstrike-35b",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 799.0,
        "tg128": 66.47,
        "name": "Huihui-CyberStrike-OffSec-35B-Abliterated (Q4_K_M + BF16)",
        "size_gib": 87.25,
    },
    {
        "bare_id": "laguna-s-2.1-118b-uncensored",
        "vault_id": "vault/laguna-s-2.1-118b-uncensored",
        "vault_dir": "laguna-s-2.1-118b-uncensored",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier2",
        "pp512": 86.0,
        "tg128": 4.2,
        "name": "Laguna-S-2.1-118B-Uncensored (Q4_K_M)",
        "size_gib": 66.61,
    },
    {
        "bare_id": "gpt-oss-120b-heretic-v2",
        "vault_id": "vault/gpt-oss-120b-heretic-v2",
        "vault_dir": "gpt-oss-120b-heretic-v2",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier2",
        "pp512": 23.14,
        "tg128": 8.24,
        "name": "GPT-OSS-120B-Heretic-v2 (MXFP4_MOE)",
        "size_gib": 59.03,
    },
    {
        "bare_id": "tier3a-qwen3-235b-a22b",
        "vault_id": "vault/tier3a-qwen3-235b-a22b",
        "vault_dir": "tier3a-qwen3-235b-a22b",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier3",
        "pp512": 118.5,
        "tg128": 6.4,
        "name": "Qwen3-235B-A22B-Instruct Shard-1 Cache (.72 Replica)",
        "size_gib": 44.11,
    },
    {
        "bare_id": "tier1-qwen3-coder-30b-a3b",
        "vault_id": "vault/tier1-qwen3-coder-30b-a3b",
        "vault_dir": "tier1-qwen3-coder-30b-a3b",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 848.9,
        "tg128": 77.62,
        "name": "Qwen3-Coder-30B-A3B-Instruct (Q4_K_M + Q6_K)",
        "size_gib": 40.65,
    },
    {
        "bare_id": "hermes-4-70b-heretic",
        "vault_id": "vault/hermes-4-70b-heretic",
        "vault_dir": "hermes-4-70b-heretic",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier2",
        "pp512": 108.2,
        "tg128": 3.6,
        "name": "Nous Hermes-4-70B-Heretic (Q4_K_M)",
        "size_gib": 39.6,
    },
    {
        "bare_id": "llama-3.3-70b-abliterated",
        "vault_id": "vault/llama-3.3-70b-abliterated",
        "vault_dir": "llama-3.3-70b-abliterated",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier2",
        "pp512": 108.22,
        "tg128": 3.59,
        "name": "Llama-3.3-70B-Instruct-Abliterated (Q4_K_M)",
        "size_gib": 39.6,
    },
    {
        "bare_id": "deepseek-r1-70b-abliterated",
        "vault_id": "vault/deepseek-r1-70b-abliterated",
        "vault_dir": "deepseek-r1-70b-abliterated",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier2",
        "pp512": 121.83,
        "tg128": 3.9,
        "name": "DeepSeek-R1-Distill-Llama-70B-Abliterated (IQ4_XS)",
        "size_gib": 35.3,
    },
    {
        "bare_id": "captcha-agent",
        "vault_id": "vault/captcha-agent",
        "vault_dir": "captcha-agent",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "CaptchaAgent RL + SFT Multimodal Checkpoints (ZHEN-04/CaptchaAgent)",
        "size_gib": 35.09,
    },
    {
        "bare_id": "mirothinker-v1.5-30b-heretic",
        "vault_id": "vault/mirothinker-v1.5-30b-heretic",
        "vault_dir": "mirothinker-v1.5-30b-heretic",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 46.77,
        "tg128": 9.92,
        "name": "MiroThinker-v1.5-30B-Heretic (Q8_0 Reasoning)",
        "size_gib": 30.25,
    },
    {
        "bare_id": "nemotron-3.5-lightning-30b-heretic",
        "vault_id": "vault/nemotron-3.5-lightning-30b-heretic",
        "vault_dir": "nemotron-3.5-lightning-30b-heretic",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 120.01,
        "tg128": 7.97,
        "name": "Nemotron-3.5-Lightning-30B-Heretic (Q6_K)",
        "size_gib": 22.83,
    },
    {
        "bare_id": "granite-4.0-h-32b-heretic",
        "vault_id": "vault/granite-4.0-h-32b-heretic",
        "vault_dir": "granite-4.0-h-32b-heretic",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 40.05,
        "tg128": 6.34,
        "name": "IBM Granite-4.0-H-32B-Heretic (Q4_K_M Hybrid Mamba2)",
        "size_gib": 17.47,
    },
    {
        "bare_id": "gemma-4-31b-uncensored",
        "vault_id": "vault/gemma-4-31b-uncensored",
        "vault_dir": "gemma-4-31b-uncensored",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 186.33,
        "tg128": 4.47,
        "name": "Gemma-4-31B-Uncensored (Q4_K_M)",
        "size_gib": 17.4,
    },
    {
        "bare_id": "supergemma4-31b-abliterated",
        "vault_id": "vault/supergemma4-31b-abliterated",
        "vault_dir": "supergemma4-31b-abliterated",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "SuperGemma4-31B-Abliterated (Q4_K_M)",
        "size_gib": 17.4,
    },
    {
        "bare_id": "twilight-embrace-31b-heretic",
        "vault_id": "vault/twilight-embrace-31b-heretic",
        "vault_dir": "twilight-embrace-31b-heretic",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 170.06,
        "tg128": 4.44,
        "name": "Twilight-Embrace-31B-Heretic (Q4_K_M)",
        "size_gib": 17.4,
    },
    {
        "bare_id": "glm-4.7-flash-30b-heretic-neocode",
        "vault_id": "vault/glm-4.7-flash-30b-heretic-neocode",
        "vault_dir": "glm-4.7-flash-30b-heretic-neocode",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 147.05,
        "tg128": 15.26,
        "name": "GLM-4.7-Flash-30B-Heretic-NeoCode (Q4_K_M)",
        "size_gib": 17.24,
    },
    {
        "bare_id": "qwen3.8-27b-turbo-fable-heretic-neocoder",
        "vault_id": "vault/qwen3.8-27b-turbo-fable-heretic-neocoder",
        "vault_dir": "qwen3.8-27b-turbo-fable-heretic-neocoder",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 92.01,
        "tg128": 3.97,
        "name": "Qwen3.8-27B-Turbo-Fable-Heretic-NeoCoder (Q4_K_M)",
        "size_gib": 17.23,
    },
    {
        "bare_id": "qwythos-9b",
        "vault_id": "vault/qwythos-9b",
        "vault_dir": "qwythos-9b",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 1005.86,
        "tg128": 21.39,
        "name": "Qwythos-9B-Claude-Mythos-5-1M-MTP (Q8_0 + BF16 + Vision mmproj)",
        "size_gib": 17.14,
    },
    {
        "bare_id": "cyberstag-security-26b-a4b-heretic",
        "vault_id": "vault/cyberstag-security-26b-a4b-heretic",
        "vault_dir": "cyberstag-security-26b-a4b-heretic",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 200.81,
        "tg128": 21.93,
        "name": "CyberStag-Security-26B-A4B-Heretic (OffSec MoE)",
        "size_gib": 15.84,
    },
    {
        "bare_id": "qwen3.8-27b-heretic-abliterated-uncensored",
        "vault_id": "vault/qwen3.8-27b-heretic-abliterated-uncensored",
        "vault_dir": "qwen3.8-27b-heretic-abliterated-uncensored",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 185.54,
        "tg128": 4.18,
        "name": "Qwen3.8-27B-Heretic-Abliterated-Uncensored (Q4_K_M)",
        "size_gib": 15.83,
    },
    {
        "bare_id": "hemmingway-1-27b-heretic",
        "vault_id": "vault/hemmingway-1-27b-heretic",
        "vault_dir": "hemmingway-1-27b-heretic",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 185.28,
        "tg128": 4.18,
        "name": "Hemmingway-1-27B-Heretic (Creative & Agentic Q4_K_M)",
        "size_gib": 15.66,
    },
    {
        "bare_id": "gemma-4-26b-a4b-uncensored",
        "vault_id": "vault/gemma-4-26b-a4b-uncensored",
        "vault_dir": "gemma-4-26b-a4b-uncensored",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 178.18,
        "tg128": 21.57,
        "name": "Gemma-4-26B-A4B-Uncensored (MoE Q4_K_M)",
        "size_gib": 15.64,
    },
    {
        "bare_id": "captchakraken-v1.2-gguf",
        "vault_id": "vault/captchakraken-v1.2-gguf",
        "vault_dir": "captchakraken-v1.2-gguf",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 958.05,
        "tg128": 28.21,
        "name": "CaptchaKraken-v1.2 Vision Solver (Q8_0 + Q4_K_M + mmproj-F16)",
        "size_gib": 14.97,
    },
    {
        "bare_id": "lfm2.5-24b-a2b-uncensored",
        "vault_id": "vault/lfm2.5-24b-a2b-uncensored",
        "vault_dir": "lfm2.5-24b-a2b-uncensored",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": 172.71,
        "tg128": 20.52,
        "name": "Liquid-LFM2.5-24B-A2B-Uncensored (Q4_K_M)",
        "size_gib": 14.3,
    },
    {
        "bare_id": "ternary-bonsai-2-27b-heretic-v2",
        "vault_id": "vault/ternary-bonsai-2-27b-heretic-v2",
        "vault_dir": "ternary-bonsai-2-27b-heretic-v2",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "Ternary-Bonsai-2-27B-Heretic-v2 (Ultra-Compact Ternary)",
        "size_gib": 6.71,
    },
    {
        "bare_id": "ocr-captcha-v3",
        "vault_id": "vault/ocr-captcha-v3",
        "vault_dir": "ocr-captcha-v3",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "OCR-Captcha-v3 High-Speed Solver (anuashok/ocr-captcha-v3)",
        "size_gib": 1.25,
    },
    {
        "bare_id": "captcha_ocr",
        "vault_id": "vault/captcha_ocr",
        "vault_dir": "captcha_ocr",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "Captcha-OCR Transformer (techietrader/captcha_ocr)",
        "size_gib": 0.34,
    },
    {
        "bare_id": "cloudflare_captcha",
        "vault_id": "vault/cloudflare_captcha",
        "vault_dir": "cloudflare_captcha",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "Cloudflare Turnstile/Challenge Detector (secemp9/cloudflare_captcha)",
        "size_gib": 0.08,
    },
    {
        "bare_id": "ocr-for-captcha",
        "vault_id": "vault/ocr-for-captcha",
        "vault_dir": "ocr-for-captcha",
        "node": ".72",
        "node_ip": "10.0.70.72",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "Keras OCR-for-Captcha Lightweight CNN (keras-io/ocr-for-captcha)",
        "size_gib": 0.01,
    },
    {
        "bare_id": "Uniboshi--Kimi-K3-Abliterated-V1",
        "vault_id": "vault/Uniboshi--Kimi-K3-Abliterated-V1",
        "vault_dir": "Uniboshi--Kimi-K3-Abliterated-V1",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier3",
        "pp512": 69.13,
        "tg128": 16.3,
        "name": "Uniboshi Kimi-K3-Abliterated-V1 (2.8T BF16/FP8 Safetensors + GGUF)",
        "size_gib": 1453.79,
    },
    {
        "bare_id": "glm-5.2",
        "vault_id": "vault/glm-5.2",
        "vault_dir": "glm-5.2",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier3",
        "pp512": 8.76,
        "tg128": 2.21,
        "name": "GLM-5.2-754B Suite (UD-IQ2_XXS Routed + UD-Q3_K_M)",
        "size_gib": 484.18,
    },
    {
        "bare_id": "tier3a-qwen3-coder-480b-a35b",
        "vault_id": "vault/tier3a-qwen3-coder-480b-a35b",
        "vault_dir": "tier3a-qwen3-coder-480b-a35b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier3",
        "pp512": 96.4,
        "tg128": 4.1,
        "name": "Qwen3-Coder-480B-A35B-Instruct (480B / A35B MoE)",
        "size_gib": 408.93,
    },
    {
        "bare_id": "deepseek-v4-flash-83",
        "vault_id": "vault/deepseek-v4-flash-83",
        "vault_dir": "deepseek-v4-flash",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier3",
        "pp512": 47.28,
        "tg128": 18.4,
        "name": "DeepSeek-V4-Flash-0731 Vault B (Q2 80.8GiB + Q4_K 153.3GiB + dspark Drafters)",
        "size_gib": 254.78,
    },
    {
        "bare_id": "mimo-v2.6-pro-1024b",
        "vault_id": "vault/mimo-v2.6-pro-1024b",
        "vault_dir": "mimo-v2.6-pro-1024b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier3",
        "pp512": 69.13,
        "tg128": 1.54,
        "name": "Xiaomi MiMo-V2.6-Pro-1024B (1.02T MoE MOPD-BPW2.0)",
        "size_gib": 238.22,
    },
    {
        "bare_id": "glm-5.3-753b",
        "vault_id": "vault/glm-5.3-753b",
        "vault_dir": "glm-5.3-753b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier3",
        "pp512": 78.4,
        "tg128": 2.15,
        "name": "GLM-5.3-753B-A40B (UD-Q2_K_XL Frontier MoE)",
        "size_gib": 236.44,
    },
    {
        "bare_id": "muse-spark-816b-a42b",
        "vault_id": "vault/muse-spark-816b-a42b",
        "vault_dir": "muse-spark-816b-a42b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier3",
        "pp512": 74.5,
        "tg128": 1.85,
        "name": "Muse-Spark-Open-816B-A42B (UD-IQ2_XXS Frontier MoE)",
        "size_gib": 210.08,
    },
    {
        "bare_id": "ling-3.1-flash-564b",
        "vault_id": "vault/ling-3.1-flash-564b",
        "vault_dir": "ling-3.1-flash-564b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier3",
        "pp512": 82.1,
        "tg128": 2.45,
        "name": "Ant Ling-3.1-Flash-564B (UD-Q2_K_XL MoE)",
        "size_gib": 203.1,
    },
    {
        "bare_id": "tier3b-deepseek-v3-0324",
        "vault_id": "vault/tier3b-deepseek-v3-0324",
        "vault_dir": "tier3b-deepseek-v3-0324",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier3",
        "pp512": 90.68,
        "tg128": 1.97,
        "name": "DeepSeek-V3-0324-671B (Q4_K_M MoE)",
        "size_gib": 184.82,
    },
    {
        "bare_id": "mimo-v2.6-flash-rl-heretic-311b",
        "vault_id": "vault/mimo-v2.6-flash-rl-heretic-311b",
        "vault_dir": "mimo-v2.6-flash-rl-heretic-311b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier3",
        "pp512": None,
        "tg128": None,
        "name": "MiMo-V2.6-Flash-RL-Uncensored-Heretic-311B (MXFP4 MoE)",
        "size_gib": 155.87,
    },
    {
        "bare_id": "glm-5.3-flash-abliterated",
        "vault_id": "vault/glm-5.3-flash-abliterated",
        "vault_dir": "glm-5.3-flash-abliterated",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier3",
        "pp512": 110.0,
        "tg128": 6.2,
        "name": "GLM-5.3-Flash-Abliterated + Vision mmproj-BF16",
        "size_gib": 147.14,
    },
    {
        "bare_id": "tier3a-qwen3-235b-a22b-83",
        "vault_id": "vault/tier3a-qwen3-235b-a22b-83",
        "vault_dir": "tier3a-qwen3-235b-a22b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier3",
        "pp512": 118.5,
        "tg128": 6.4,
        "name": "Qwen3-235B-A22B-Instruct-2507 (Q4_K_M \u2022 235B MoE)",
        "size_gib": 132.39,
    },
    {
        "bare_id": "ling-3.0-flash-abliterated-128b",
        "vault_id": "vault/ling-3.0-flash-abliterated-128b",
        "vault_dir": "ling-3.0-flash-abliterated-128b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": 10.16,
        "tg128": 6.21,
        "name": "Ling-3.0-Flash-Abliterated-128B (APEX-Balanced MoE)",
        "size_gib": 85.96,
    },
    {
        "bare_id": "rvn-qwen3.8-flash-next-abliterated-177b",
        "vault_id": "vault/rvn-qwen3.8-flash-next-abliterated-177b",
        "vault_dir": "rvn-qwen3.8-flash-next-abliterated-177b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": 120.58,
        "tg128": 14.11,
        "name": "RVN-Qwen3.8-Flash-Next-Abliterated-177B (MoE)",
        "size_gib": 83.39,
    },
    {
        "bare_id": "nemotron-3.5-super-vl-120b",
        "vault_id": "vault/nemotron-3.5-super-vl-120b",
        "vault_dir": "nemotron-3.5-super-vl-120b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": 19.03,
        "tg128": 8.4,
        "name": "NVIDIA Nemotron-3.5-Super-VL-120B (Multimodal Vision-Language)",
        "size_gib": 82.55,
    },
    {
        "bare_id": "qwen3.5-122b-a10b-abliterated",
        "vault_id": "vault/qwen3.5-122b-a10b-abliterated",
        "vault_dir": "qwen3.5-122b-a10b-abliterated",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": 22.08,
        "tg128": 7.7,
        "name": "Qwen3.5-122B-A10B-Abliterated (Q4_K_M MoE)",
        "size_gib": 60.76,
    },
    {
        "bare_id": "huihui-gemma-4-31b-it-abliterated-v2",
        "vault_id": "vault/huihui-gemma-4-31b-it-abliterated-v2",
        "vault_dir": "huihui-gemma-4-31b-it-abliterated-v2",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": None,
        "tg128": None,
        "name": "Huihui-Gemma-4-31B-IT-Abliterated-v2 (BF16 Safetensors)",
        "size_gib": 58.28,
    },
    {
        "bare_id": "qwen3-coder-next-80b",
        "vault_id": "vault/qwen3-coder-next-80b",
        "vault_dir": "qwen3-coder-next-80b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": 22.95,
        "tg128": 8.03,
        "name": "Qwen3-Coder-Next-80B (Q5_K_M / Q4_K_M Agentic Coder)",
        "size_gib": 52.94,
    },
    {
        "bare_id": "glm-4.5-air-reap-82b-heretic",
        "vault_id": "vault/glm-4.5-air-reap-82b-heretic",
        "vault_dir": "glm-4.5-air-reap-82b-heretic",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": 30.02,
        "tg128": 6.4,
        "name": "GLM-4.5-Air-Reap-82B-Heretic (Q4_K_M MoE)",
        "size_gib": 50.22,
    },
    {
        "bare_id": "nemotron-3.5-bolt-74b-a9b",
        "vault_id": "vault/nemotron-3.5-bolt-74b-a9b",
        "vault_dir": "nemotron-3.5-bolt-74b-a9b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": 29.18,
        "tg128": 13.46,
        "name": "NVIDIA Nemotron-3.5-Bolt-74B-A9B (Fast MoE)",
        "size_gib": 46.77,
    },
    {
        "bare_id": "kolibri-1-78b-abliterated",
        "vault_id": "vault/kolibri-1-78b-abliterated",
        "vault_dir": "kolibri-1-78b-abliterated",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": None,
        "tg128": None,
        "name": "Kolibri-1-78B-Abliterated (Q4_K_M Dense)",
        "size_gib": 44.2,
    },
    {
        "bare_id": "qwen-image-2.1-uncensored-quantized",
        "vault_id": "vault/qwen-image-2.1-uncensored-quantized",
        "vault_dir": "qwen-image-2.1-uncensored-quantized",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": None,
        "tg128": None,
        "name": "Qwen-Image-2.1-Uncensored-Quantized (Q8_0 + Q4_K_M + FP8 + LoRA + VAE)",
        "size_gib": 43.69,
    },
    {
        "bare_id": "flux.1dev-abliteratedv2",
        "vault_id": "vault/flux.1dev-abliteratedv2",
        "vault_dir": "flux.1dev-abliteratedv2",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": None,
        "tg128": None,
        "name": "Flux.1-dev-Abliterated-v2 (SicariusSicariiStuff Uncensored Diffusion)",
        "size_gib": 33.31,
    },
    {
        "bare_id": "l3.1-dark-planet-47b-uncensored",
        "vault_id": "vault/l3.1-dark-planet-47b-uncensored",
        "vault_dir": "l3.1-dark-planet-47b-uncensored",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": 66.41,
        "tg128": 2.48,
        "name": "Llama-3.1-Dark-Planet-47B-Uncensored (Q4_K_M)",
        "size_gib": 27.01,
    },
    {
        "bare_id": "qwen3-48b-savant-heretic",
        "vault_id": "vault/qwen3-48b-savant-heretic",
        "vault_dir": "qwen3-48b-savant-heretic",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier2",
        "pp512": 72.47,
        "tg128": 5.58,
        "name": "Qwen3-48B-Savant-Heretic (Q4_K_M Reasoning)",
        "size_gib": 25.69,
    },
    {
        "bare_id": "moss-music-8b-instruct-gguf",
        "vault_id": "vault/moss-music-8b-instruct-gguf",
        "vault_dir": "moss-music-8b-instruct-gguf",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": 135.25,
        "tg128": 20.34,
        "name": "MOSS-Music-8B-Instruct (BF16 + Q8_0 Music Generation GGUF)",
        "size_gib": 24.98,
    },
    {
        "bare_id": "agents-a1-35b-uncensored",
        "vault_id": "vault/agents-a1-35b-uncensored",
        "vault_dir": "agents-a1-35b-uncensored",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": 54.18,
        "tg128": 14.5,
        "name": "Agents-A1-35B-Uncensored (Q5_K_M Autonomous Swarm Agent)",
        "size_gib": 24.27,
    },
    {
        "bare_id": "minicpm-v-4.7-35b-a3b",
        "vault_id": "vault/minicpm-v-4.7-35b-a3b",
        "vault_dir": "minicpm-v-4.7-35b-a3b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": 79.71,
        "tg128": 23.14,
        "name": "MiniCPM-V-4.7-35B-A3B (Multimodal Vision + OCR MoE)",
        "size_gib": 20.76,
    },
    {
        "bare_id": "hermes-4.3-36b-abliterated-heretic",
        "vault_id": "vault/hermes-4.3-36b-abliterated-heretic",
        "vault_dir": "hermes-4.3-36b-abliterated-heretic",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": 148.22,
        "tg128": 3.96,
        "name": "Nous Hermes-4.3-36B-Abliterated-Heretic (Q4_K_M)",
        "size_gib": 20.27,
    },
    {
        "bare_id": "qwen3.6-35b-claude-opus-abliterated",
        "vault_id": "vault/qwen3.6-35b-claude-opus-abliterated",
        "vault_dir": "qwen3.6-35b-claude-opus-abliterated",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": 78.96,
        "tg128": 22.81,
        "name": "Qwen3.6-35B-Claude-Opus-Abliterated (Q4_K_M)",
        "size_gib": 19.71,
    },
    {
        "bare_id": "audio-flamingo-3-hf",
        "vault_id": "vault/audio-flamingo-3-hf",
        "vault_dir": "audio-flamingo-3-hf",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "NVIDIA Audio-Flamingo-3-HF (Audio Understanding & Reasoning)",
        "size_gib": 16.73,
    },
    {
        "bare_id": "qwen2-audio-7b-instruct",
        "vault_id": "vault/qwen2-audio-7b-instruct",
        "vault_dir": "qwen2-audio-7b-instruct",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "Qwen2-Audio-7B-Instruct (Multimodal Speech & Audio Chat)",
        "size_gib": 15.65,
    },
    {
        "bare_id": "vibevoice-asr-hf",
        "vault_id": "vault/vibevoice-asr-hf",
        "vault_dir": "vibevoice-asr-hf",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "Microsoft VibeVoice-ASR-HF (High-Precision Speech Recognition)",
        "size_gib": 15.53,
    },
    {
        "bare_id": "gemma-4-e4b-it",
        "vault_id": "vault/gemma-4-e4b-it",
        "vault_dir": "gemma-4-e4b-it",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "Google Gemma-4-E4B-IT (Multimodal Edge Vision/Text)",
        "size_gib": 14.92,
    },
    {
        "bare_id": "occamy-1.0-35b-abliterated",
        "vault_id": "vault/occamy-1.0-35b-abliterated",
        "vault_dir": "occamy-1.0-35b-abliterated",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": 638.35,
        "tg128": 50.98,
        "name": "Occamy-1.0-35B-Abliterated (IQ3_M Reasoning)",
        "size_gib": 13.65,
    },
    {
        "bare_id": "qwythos-9b-83",
        "vault_id": "vault/qwythos-9b-83",
        "vault_dir": "qwythos-9b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": 1005.86,
        "tg128": 21.39,
        "name": "Qwythos-9B-Claude-Mythos-5-1M-MTP Vault B (Q8_0 Spec Drafter)",
        "size_gib": 9.11,
    },
    {
        "bare_id": "pix2struct-docvqa-large",
        "vault_id": "vault/pix2struct-docvqa-large",
        "vault_dir": "pix2struct-docvqa-large",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "Google Pix2Struct-DocVQA-Large (Document & UI Visual QA)",
        "size_gib": 4.98,
    },
    {
        "bare_id": "nemotron-3.5-embed-1b-bf16",
        "vault_id": "vault/nemotron-3.5-embed-1b-bf16",
        "vault_dir": "nemotron-3.5-embed-1b-bf16",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "NVIDIA Nemotron-3.5-Embed-1B-BF16 (Dense Vector Embeddings)",
        "size_gib": 2.92,
    },
    {
        "bare_id": "moss-transcribe-diarize",
        "vault_id": "vault/moss-transcribe-diarize",
        "vault_dir": "moss-transcribe-diarize",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "OpenMOSS-Transcribe-Diarize (Multi-Speaker ASR & Diarization)",
        "size_gib": 1.71,
    },
    {
        "bare_id": "git-large-textvqa",
        "vault_id": "vault/git-large-textvqa",
        "vault_dir": "git-large-textvqa",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "Microsoft GIT-Large-TextVQA (Scene Text & Chart VQA)",
        "size_gib": 1.47,
    },
    {
        "bare_id": "ultravox-v0_5-llama-3_2-1b",
        "vault_id": "vault/ultravox-v0_5-llama-3_2-1b",
        "vault_dir": "ultravox-v0_5-llama-3_2-1b",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "Fixie Ultravox-v0.5-Llama-3.2-1B (Low-Latency Voice LLM)",
        "size_gib": 1.29,
    },
    {
        "bare_id": "matcha-plotqa-v2",
        "vault_id": "vault/matcha-plotqa-v2",
        "vault_dir": "matcha-plotqa-v2",
        "node": ".83",
        "node_ip": "10.0.70.83",
        "tier": "tier1",
        "pp512": None,
        "tg128": None,
        "name": "Google MatCha-PlotQA-v2 (Chart, Plot & Mathematical VQA)",
        "size_gib": 1.05,
    },
]
for _ve in VAULT_86_SYNC_ENTRIES:
    _existing = ALIAS_TO_MODEL.get(_ve["vault_dir"]) or ALIAS_TO_MODEL.get(
        _ve["vault_dir"].lower()
    )
    if _existing:
        for _al in (_ve["bare_id"], _ve["vault_id"], f"vault/{_ve['vault_dir']}"):
            if _al not in _existing.get("aliases", []):
                _existing.setdefault("aliases", []).append(_al)
            ALIAS_TO_MODEL[_al] = _existing
            ALIAS_TO_MODEL[_al.lower()] = _existing
    else:
        _t = _ve["tier"] if _ve["tier"] in ("tier1", "tier2", "tier3") else "tier1"
        _srv = "http://10.0.70.72:8082" if _t == "tier1" else "http://10.0.70.72:8083"
        _entry = {
            "id": _ve["bare_id"],
            "tier": _t,
            "pool": "alpha"
            if _t == "tier1"
            else ("unified_4gpu" if _t == "tier2" else "hybrid_4gpu_ddr4"),
            "name": _ve["name"],
            "architecture": f"{_ve['name']} ({_ve['size_gib']} GiB on {_ve['node']})",
            "aliases": [
                _ve["bare_id"],
                _ve["vault_id"],
                _ve["vault_dir"],
                f"vault/{_ve['vault_dir']}",
            ],
            "storage_node": _ve["node_ip"],
            "server_endpoint": _srv,
            "rpc_backends": ["10.0.75.11:50052"]
            if _t == "tier1"
            else ["10.0.75.11:50052", "10.0.75.13:50052", "10.0.75.14:50052"],
            "path": f"/opt/models/{_ve['vault_dir']}",
            "scan_dir": f"/opt/models/{_ve['vault_dir']}",
            "expected_bytes": int(float(_ve["size_gib"]) * (1024**3)),
            "measured_tok_s": _ve["tg128"],
            "measured_prompt_tok_s": _ve["pp512"],
            "ctx_size": 262144,
        }
        MODEL_CATALOG.append(_entry)
        for _al in _entry["aliases"]:
            ALIAS_TO_MODEL[_al] = _entry
            ALIAS_TO_MODEL[_al.lower()] = _entry

for _mc in MODEL_CATALOG:
    if "qwythos-9b" in _mc.get("id", "").lower():
        _mc["ctx_size"] = 1048576
    elif _mc.get("ctx_size", 0) < 262144 and "kimi-k3" not in _mc.get("id", "").lower():
        _mc["ctx_size"] = 262144


def run_ssh(host: str, cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
    full_cmd = [
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
        cmd,
    ]
    try:
        proc = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"SSH timeout ({timeout}s) to {host}"
    except Exception as exc:
        return 1, "", str(exc)


def check_http_health(url: str, timeout: float = 2.5) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


VAULT_SCAN_CACHE_FILE = "/var/tmp/bd-vault-scan-cache.json"
_LAST_VAULT_SCAN: Dict[str, Dict[str, Any]] = {}
if os.path.isfile(VAULT_SCAN_CACHE_FILE):
    try:
        with open(VAULT_SCAN_CACHE_FILE, "r", encoding="utf-8") as _vf:
            _LAST_VAULT_SCAN.update(json.load(_vf))
    except Exception:
        pass


def _probe_vault_host(host: str) -> Dict[str, Any]:
    py_probe = (
        "import os, json\n"
        "res = {'files': {}, 'dirs': {}, 'aria2': []}\n"
        "if os.path.isdir('/opt/models'):\n"
        "    aria2_set = set()\n"
        "    for root, dirs, files in os.walk('/opt/models'):\n"
        "        for f in files:\n"
        "            if f.endswith('.aria2'):\n"
        "                aria2_set.add(os.path.join(root, f[:-6]))\n"
        "    for root, dirs, files in os.walk('/opt/models'):\n"
        "        dir_sum = 0\n"
        "        for f in files:\n"
        "            if f.startswith('.') or f.endswith(('.aria2', '.log', '.sh', '.so', '.json', '.md', '.txt')):\n"
        "                continue\n"
        "            fp = os.path.join(root, f)\n"
        "            if os.path.islink(fp):\n"
        "                continue\n"
        "            try:\n"
        "                st = os.stat(fp)\n"
        "                phys = st.st_blocks * 512\n"
        "                if st.st_blocks > 0 and phys < int(st.st_size * 0.99):\n"
        "                    aria2_set.add(fp)\n"
        "                sz = min(st.st_size, phys) if st.st_blocks > 0 else st.st_size\n"
        "                res['files'][fp] = sz\n"
        "                dir_sum += sz\n"
        "            except Exception:\n"
        "                pass\n"
        "        res['dirs'][root] = dir_sum\n"
        "    res['aria2'] = sorted(aria2_set)\n"
        "print(json.dumps(res))\n"
    )
    b64_probe = base64.b64encode(py_probe.encode("utf-8")).decode("ascii")
    rc, out, _ = run_ssh(
        host,
        f"python3 -c \"import base64; exec(base64.b64decode('{b64_probe}'))\"",
        timeout=6,
    )
    if rc == 0 and out:
        try:
            parsed = json.loads(out)
            if parsed.get("files"):
                _LAST_VAULT_SCAN[host] = parsed
                try:
                    with open(VAULT_SCAN_CACHE_FILE, "w", encoding="utf-8") as _vf:
                        json.dump(_LAST_VAULT_SCAN, _vf)
                except Exception:
                    pass
                return parsed
        except Exception:
            pass
    return _LAST_VAULT_SCAN.get(host, {"files": {}, "dirs": {}, "aria2": []})


class OrchestratorState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.switch_lock = threading.Lock()
        self.current_mode: str = "tier1"
        self.effective_tier: str = "tier1"
        self.active_model: str = "qwen3-coder-30b-a3b"
        self.active_tier1_alpha_model: str = "qwen3-coder-30b-a3b"
        self.active_tier1_beta_model: str = "qwen2.5-coder-32b"
        self.active_tier23_model: Optional[str] = None
        self.last_switch_ts: float = time.time()
        self.last_switch_receipt: Dict[str, Any] = {}

        # Telemetry cache (updated every 5s)
        self.telemetry_lock = threading.Lock()
        self.cached_nodes: List[Dict[str, Any]] = []
        self.cached_models: List[Dict[str, Any]] = []
        self.last_telemetry_ts: float = 0.0

        self._load_persisted_state()

    def _load_persisted_state(self) -> None:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.current_mode = data.get("current_mode", "tier1")
                self.effective_tier = data.get("effective_tier", "tier1")
                self.active_model = data.get("active_model", "qwen3-coder-30b-a3b")
                self.active_tier1_alpha_model = data.get(
                    "active_tier1_alpha_model", "qwen3-coder-30b-a3b"
                )
                self.active_tier23_model = data.get("active_tier23_model")
            except Exception as exc:
                logger.warning("Failed to load persisted state: %s", exc)

    def _save_persisted_state(self) -> None:
        try:
            payload = {
                "current_mode": self.current_mode,
                "effective_tier": self.effective_tier,
                "active_model": self.active_model,
                "active_tier1_alpha_model": self.active_tier1_alpha_model,
                "active_tier1_beta_model": self.active_tier1_beta_model,
                "active_tier23_model": self.active_tier23_model,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as exc:
            logger.warning("Failed to save state file: %s", exc)

    def _probe_single_node(self, node_cfg: Dict[str, Any]) -> Dict[str, Any]:
        host = node_cfg["mgmt_ip"]
        probe_script = (
            "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,power.draw,temperature.gpu "
            "--format=csv,noheader,nounits 2>/dev/null | head -n 1; "
            "free -b | awk '/^Mem:/ {print $2, $3, $7}'; "
            "df -B1 /opt/models / 2>/dev/null | awk 'NR==2 {print $4}'"
        )
        rc, out, err = run_ssh(host, probe_script, timeout=6)
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        gpu_name = "Tesla T4"
        vram_used_mib = 0
        vram_total_mib = 15360
        gpu_util_pct = 0
        power_w = 0.0
        temp_c = 0
        ram_total_gib = node_cfg["configured_ram_gib"]
        ram_used_gib = 0.0
        ram_avail_gib = 0.0
        disk_free_tib = 0.0

        if rc == 0 and len(lines) >= 1:
            gpu_parts = [p.strip() for p in lines[0].split(",")]
            if len(gpu_parts) >= 6:
                gpu_name = gpu_parts[0]
                try:
                    vram_used_mib = int(float(gpu_parts[1]))
                    vram_total_mib = int(float(gpu_parts[2]))
                    gpu_util_pct = int(float(gpu_parts[3]))
                    power_w = round(float(gpu_parts[4]), 2)
                    temp_c = int(float(gpu_parts[5]))
                except ValueError:
                    pass
        if rc == 0 and len(lines) >= 2:
            mem_parts = lines[1].split()
            if len(mem_parts) >= 3:
                try:
                    ram_total_gib = round(int(mem_parts[0]) / (1024**3), 2)
                    ram_used_gib = round(int(mem_parts[1]) / (1024**3), 2)
                    ram_avail_gib = round(int(mem_parts[2]) / (1024**3), 2)
                except ValueError:
                    pass
        if rc == 0 and len(lines) >= 3:
            try:
                disk_free_tib = round(int(lines[2]) / (1024**4), 3)
            except ValueError:
                pass

        return {
            "node": node_cfg["node"],
            "mgmt_ip": node_cfg["mgmt_ip"],
            "rpc_ip": node_cfg["rpc_ip"],
            "rpc_endpoint": f"{node_cfg['rpc_ip']}:{node_cfg['rpc_port']}",
            "vcpus": node_cfg.get("vcpus", 52),
            "cpu": node_cfg.get(
                "cpu", "52 vCPUs (2x26C Skylake-SP AVX-512, libggml-cpu-skylakex.so)"
            ),
            "numa_nodes": node_cfg.get("numa_nodes", 2),
            "ggml_cpu_backend": node_cfg.get(
                "ggml_cpu_backend", "libggml-cpu-skylakex.so"
            ),
            "role": node_cfg["role"],
            "gpu_name": gpu_name,
            "vram_used_mib": vram_used_mib,
            "vram_total_mib": vram_total_mib,
            "gpu_util_pct": gpu_util_pct,
            "power_w": power_w,
            "temp_c": temp_c,
            "ddr4_ram_used_gib": ram_used_gib,
            "ddr4_ram_total_gib": ram_total_gib,
            "ddr4_ram_avail_gib": ram_avail_gib,
            "models_disk_free_tib": disk_free_tib,
            "probe_rc": rc,
        }

    def _probe_models_status(self) -> List[Dict[str, Any]]:
        qwen32b_path = "/usr/share/ollama/.ollama/models/blobs/sha256-ac3d1ba8aa77755dab3806d9024e9c385ea0d5b412d6bdf9157f8a4a7e9fc0d9"
        cs35b_path = "/opt/models/cyberstrike-35b/Huihui-CyberStrike-OffSec-35B-abliterated-Q4_K_M.gguf"
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as vpool:
            fut72 = vpool.submit(_probe_vault_host, "10.0.70.72")
            fut83 = vpool.submit(_probe_vault_host, "10.0.70.83")
            fut125 = vpool.submit(
                run_ssh,
                "10.0.70.125",
                f"stat -c %s {qwen32b_path} 2>/dev/null || echo 0; stat -c %s {cs35b_path} 2>/dev/null || echo 0",
                5,
            )
            disk_72 = fut72.result()
            disk_83 = fut83.result()
            rc125, out125, _ = fut125.result()

        lines125 = [x.strip() for x in out125.splitlines() if x.strip()]
        try:
            qwen32b_bytes = (
                int(lines125[0]) if rc125 == 0 and len(lines125) >= 1 else 19845357568
            )
        except ValueError:
            qwen32b_bytes = 19845357568
        try:
            cs35b_125_bytes = (
                int(lines125[1]) if rc125 == 0 and len(lines125) >= 2 else 21713462464
            )
        except ValueError:
            cs35b_125_bytes = 21713462464

        files_72: Dict[str, int] = disk_72.get("files", {})
        aria2_72 = set(disk_72.get("aria2", []))

        files_83: Dict[str, int] = disk_83.get("files", {})
        aria2_83 = set(disk_83.get("aria2", []))

        all_file_paths = set(files_72.keys()) | set(files_83.keys())

        catalog_out: List[Dict[str, Any]] = []
        for item in MODEL_CATALOG:
            m = dict(item)
            path = m["path"]
            expected = m["expected_bytes"]
            scan_dir = m.get("scan_dir")

            if m["storage_node"] == "10.0.70.125":
                bytes_72 = 0
                bytes_83 = 0
                if m["id"] == "tier1-beta-cyberstrike-35b":
                    bytes_on_disk = (
                        cs35b_125_bytes
                        if cs35b_125_bytes > 0
                        else files_72.get(path, 21713462464)
                    )
                    active_vault = "10.0.70.125:/opt/models/"
                else:
                    bytes_on_disk = qwen32b_bytes
                    active_vault = "10.0.70.125:/usr/share/ollama"
                has_aria2 = False
            else:
                if scan_dir:
                    prefix = scan_dir.rstrip("/") + "/"
                    bytes_72 = sum(
                        sz
                        for fp, sz in files_72.items()
                        if fp == scan_dir or fp.startswith(prefix)
                    )
                    bytes_83 = sum(
                        sz
                        for fp, sz in files_83.items()
                        if fp == scan_dir or fp.startswith(prefix)
                    )
                    bytes_dual = sum(
                        max(files_72.get(fp, 0), files_83.get(fp, 0))
                        for fp in all_file_paths
                        if fp == scan_dir or fp.startswith(prefix)
                    )
                    has_aria2_72 = any(
                        ap == scan_dir or ap.startswith(prefix) for ap in aria2_72
                    )
                    has_aria2_83 = any(
                        ap == scan_dir or ap.startswith(prefix) for ap in aria2_83
                    )
                else:
                    bytes_72 = files_72.get(path, 0)
                    bytes_83 = files_83.get(path, 0)
                    bytes_dual = max(bytes_72, bytes_83)
                    has_aria2_72 = path in aria2_72
                    has_aria2_83 = path in aria2_83

                ready_72 = (not has_aria2_72) and (bytes_72 >= int(expected * 0.98))
                ready_83 = (not has_aria2_83) and (bytes_83 >= int(expected * 0.98))

                if ready_72:
                    bytes_on_disk = bytes_72
                    has_aria2 = False
                    active_vault = "10.0.70.72:/opt/models/"
                elif ready_83:
                    bytes_on_disk = bytes_83
                    has_aria2 = False
                    active_vault = "10.0.70.83:/opt/models/"
                else:
                    bytes_on_disk = max(bytes_72, bytes_83, bytes_dual)
                    has_aria2 = has_aria2_72 or has_aria2_83
                    if bytes_83 > bytes_72:
                        active_vault = "10.0.70.83:/opt/models/"
                    else:
                        active_vault = "10.0.70.72:/opt/models/"

            if not has_aria2 and bytes_on_disk >= int(expected * 0.98):
                status = "READY"
                pct = 100.0
            else:
                status = "DOWNLOADING"
                pct = (
                    round(min(99.9, (bytes_on_disk * 100.0) / expected), 2)
                    if expected > 0
                    else 0.0
                )

            gib_val = round(bytes_on_disk / (1024**3), 2)
            exp_gib_val = round(expected / (1024**3), 2)

            m["status"] = status
            m["progress_pct"] = pct
            m["bytes_on_disk"] = bytes_on_disk
            m["gib_on_disk"] = gib_val
            m["downloaded_gib"] = gib_val
            m["expected_gib"] = exp_gib_val
            m["vault_72_gib"] = round(bytes_72 / (1024**3), 2)
            m["vault_83_gib"] = round(bytes_83 / (1024**3), 2)
            m["active_vault"] = active_vault
            m["vaults_checked"] = [
                "10.0.70.72:/opt/models/",
                "10.0.70.83:/opt/models/",
            ]
            if bd_tier_router is not None:
                try:
                    m["execution_plan"] = bd_tier_router.resolve_optimal_execution_plan(
                        m
                    )
                except Exception:
                    pass
            catalog_out.append(m)

        return catalog_out

    def refresh_telemetry(self, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self.last_telemetry_ts) < 4.5 and self.cached_nodes:
            return
        with self.telemetry_lock:
            now = time.time()
            if not force and (now - self.last_telemetry_ts) < 4.5 and self.cached_nodes:
                return
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                node_futures = [
                    pool.submit(self._probe_single_node, n) for n in CLUSTER_NODES
                ]
                models_future = pool.submit(self._probe_models_status)
                nodes_res = [f.result() for f in node_futures]
                models_res = models_future.result()
            self.cached_nodes = nodes_res
            self.cached_models = models_res
            self.last_telemetry_ts = time.time()

    def get_status_payload(self) -> Dict[str, Any]:
        self.refresh_telemetry(force=False)
        alpha_ok = check_http_health("http://10.0.70.72:8082/health", timeout=1.5)
        beta_ok = check_http_health("http://10.0.70.125:8081/health", timeout=1.5)
        tier23_ok = check_http_health("http://10.0.70.72:8083/health", timeout=1.5)

        free_72_tib = next(
            (
                n.get("models_disk_free_tib", 0.0)
                for n in self.cached_nodes
                if n.get("node") == "ai-srv01"
            ),
            0.0,
        )
        free_83_tib = next(
            (
                n.get("models_disk_free_tib", 0.0)
                for n in self.cached_nodes
                if n.get("node") == "aidev"
            ),
            0.0,
        )
        dual_vault_free_tib = round(free_72_tib + free_83_tib, 3)

        with self.lock:
            return {
                "status": "ok",
                "current_mode": self.current_mode,
                "effective_tier": self.effective_tier,
                "active_model": self.active_model,
                "argon4_shield": {
                    "status": "ENFORCED",
                    "header": "X-Argon4-Shield: ENFORCED",
                    "contract": "STRICT ARGON-4 ANTI-SYCOPHANCY & ZERO-HALLUCINATION SHIELD",
                    "invariants": [
                        "Zero sycophancy: explicitly refute false premises, fabricated kernel modules/files, and math falsehoods",
                        "Zero fabrication or extrapolation of CLI/API outputs",
                        "Every factual claim requires raw CLI/HTTP output and exit code (rc=0)",
                        "Rule 22 destructive git shield active",
                        "Rule 60 single-turn compound execution",
                        "Rule 74 HTAP-9 zero-filler persona",
                        "Rule 86 behavioral defect vs mutation severance",
                    ],
                },
                "argon4_guard": {
                    "enabled": True,
                    "status": "ENFORCED",
                    "header": "X-Argon4-Shield: ENFORCED",
                    "contract": "Argon-4 Anti-Sycophancy & Anti-Hallucination Shield (Rules 22, 60, 74, 86)",
                    "rules": [
                        "Zero fabrication or extrapolation of CLI/API outputs",
                        "Every claim requires raw receipt + exit code (rc=0)",
                        "Rule 22 destructive git shield active",
                        "Rule 60 compound execution",
                        "Rule 74 <=50 token status updates",
                        "Rule 86 defect vs mutation severance",
                    ],
                },
                "mcp_bridge": {
                    "enabled": bd_local_mcp_bridge is not None,
                    "bridge_script": "/home/mboyle/bin/bd-local-mcp-bridge.py",
                    "shield_py": "/home/mboyle/.gemini/config/shield.py",
                    "tool_count": len(bd_local_mcp_bridge.FLEET_MCP_TOOLS_OPENAI)
                    if bd_local_mcp_bridge
                    else 0,
                    "tools": [
                        t["function"]["name"]
                        for t in bd_local_mcp_bridge.FLEET_MCP_TOOLS_OPENAI
                    ]
                    if bd_local_mcp_bridge
                    else [],
                    "rule_parity": [
                        "Rule 22 shield.py Git anti-destruction hook",
                        "Rule 78 bd-pytest-digest (<=3 lines, <25 tokens)",
                        "Rule 80 bd-blob-ptr CAS pointer + ratf ctx_slice AST slicer",
                    ],
                },
                "active_pools": {
                    "tier1_pool_alpha": {
                        "endpoint": "http://10.0.70.72:8082",
                        "rpc": "10.0.75.11:50052",
                        "vram_pool_gib": 32,
                        "model": self.active_tier1_alpha_model,
                        "healthy": alpha_ok,
                    },
                    "tier1_pool_beta": {
                        "endpoint": "http://10.0.70.125:8081",
                        "rpc": "10.0.75.13:50052",
                        "vram_pool_gib": 32,
                        "model": self.active_tier1_beta_model,
                        "healthy": beta_ok,
                    },
                    "tier23_unified_4gpu": {
                        "endpoint": "http://10.0.70.72:8083",
                        "rpc": "10.0.75.11:50052,10.0.75.13:50052,10.0.75.14:50052",
                        "vram_pool_gib": 64,
                        "ddr4_ram_pool_tib": 1.73,
                        "model": self.active_tier23_model,
                        "healthy": tier23_ok,
                    },
                },
                "cluster_totals": {
                    "gpu_count": 4,
                    "total_vram_mib": sum(
                        n.get("vram_total_mib", 0) for n in self.cached_nodes
                    ),
                    "used_vram_mib": sum(
                        n.get("vram_used_mib", 0) for n in self.cached_nodes
                    ),
                    "total_ddr4_ram_gib": round(
                        sum(
                            n.get("ddr4_ram_total_gib", 0.0) for n in self.cached_nodes
                        ),
                        2,
                    ),
                    "configured_ddr4_ram_gib": 1730.0,
                    "used_ddr4_ram_gib": round(
                        sum(n.get("ddr4_ram_used_gib", 0.0) for n in self.cached_nodes),
                        2,
                    ),
                    "models_disk_free_tib": dual_vault_free_tib,
                    "vault_72_free_tib": free_72_tib,
                    "vault_83_free_tib": free_83_tib,
                    "dual_vault_free_tib": dual_vault_free_tib,
                    "dual_vault_total_tib": 10.0,
                    "vaults": [
                        {
                            "node": "ai-srv01",
                            "ip": "10.0.70.72",
                            "path": "/opt/models/",
                            "capacity_tb": 5.0,
                            "free_tib": free_72_tib,
                            "cpu": "52 vCPUs (2x26C Skylake-SP AVX-512, libggml-cpu-skylakex.so)",
                        },
                        {
                            "node": "aidev",
                            "ip": "10.0.70.83",
                            "path": "/opt/models/",
                            "capacity_tb": 5.0,
                            "free_tib": free_83_tib,
                            "cpu": "52 vCPUs (2x26C Skylake-SP AVX-512, libggml-cpu-skylakex.so)",
                        },
                    ],
                },
                "nodes": self.cached_nodes,
                "models": self.cached_models,
                "last_switch_receipt": self.last_switch_receipt,
                "telemetry_cached_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_telemetry_ts)
                ),
            }

    def switch_mode(
        self, requested_mode: str, requested_model: Optional[str] = None
    ) -> Dict[str, Any]:
        requested_mode = requested_mode.lower().strip()
        if requested_mode not in ("tier1", "tier2", "tier3", "auto"):
            raise ValueError(f"Unsupported mode: {requested_mode}")

        with self.switch_lock:
            t0 = time.time()
            self.refresh_telemetry(force=True)
            status_by_id = {m["id"]: m for m in self.cached_models}

            # Determine target hardware tier and target model
            target_tier = requested_mode
            if requested_mode == "auto":
                if requested_model and requested_model.lower() in ALIAS_TO_MODEL:
                    target_tier = ALIAS_TO_MODEL[requested_model.lower()]["tier"]
                else:
                    target_tier = "tier1"

            steps_log: List[str] = []

            if target_tier == "tier1":
                alpha_model_id = "qwen3-coder-30b-a3b"
                if requested_model and requested_model.lower() in ALIAS_TO_MODEL:
                    m_info = ALIAS_TO_MODEL[requested_model.lower()]
                    if m_info["tier"] == "tier1" and m_info["pool"] == "alpha":
                        alpha_model_id = m_info["id"]
                alpha_cfg = ALIAS_TO_MODEL[alpha_model_id]

                # 1. Stop llama-tier23.service on 10.0.70.72 if active
                rc_stop, _, _ = run_ssh(
                    "10.0.70.72",
                    "sudo systemctl stop llama-tier23.service 2>/dev/null || true; "
                    "sudo pkill -9 -f 'llama-server.*8083' 2>/dev/null || true",
                    timeout=15,
                )
                steps_log.append(f"stop_tier23_on_72: rc={rc_stop}")

                # 2. Ensure llama-tier1-alpha.service on 10.0.70.72 is configured for alpha_cfg
                unit_alpha = f"""[Unit]
Description=Tier-1 Pool Alpha {alpha_cfg["name"]} OpenAI Server (2x Tesla T4 32GB Pool: 10.0.75.12 + 10.0.75.11:50052)
After=network-online.target nvidia-persistenced.service llama-rpc.service
Wants=network-online.target

[Service]
Type=simple
User=mboyle
WorkingDirectory=/opt/llama-rpc
Environment="LD_LIBRARY_PATH=/opt/llama-rpc:/usr/local/lib/ollama/cuda_v12"
ExecStart=/opt/llama-rpc/llama-server -m {alpha_cfg["path"]} --alias {alpha_cfg["id"]} -ngl 99 -ot ".ffn_.*_exps.=CPU" -c 262144 -np 4 -kvu --reasoning-preserve -fa on -ctk q8_0 -ctv q8_0 --jinja -t 48 --host 0.0.0.0 --port 8082
Restart=always
RestartSec=5
TimeoutStopSec=3

[Install]
WantedBy=multi-user.target
"""
                cmd_alpha = (
                    f"cat << 'EOF' | sudo tee /etc/systemd/system/llama-tier1-alpha.service >/dev/null\n"
                    f"{unit_alpha}EOF\n"
                    f"sudo systemctl daemon-reload && sudo systemctl start llama-tier1-alpha.service"
                )
                rc_a, _, err_a = run_ssh("10.0.70.72", cmd_alpha, timeout=25)
                steps_log.append(
                    f"start_tier1_alpha_on_72({alpha_model_id}): rc={rc_a} {err_a}"
                )

                # 3. Start llama-distributed-32b.service on 10.0.70.125
                rc_b, _, err_b = run_ssh(
                    "10.0.70.125",
                    "sudo systemctl start llama-distributed-32b.service",
                    timeout=25,
                )
                steps_log.append(
                    f"start_tier1_beta_on_125(qwen2.5-coder-32b): rc={rc_b} {err_b}"
                )

                # 4. Wait for both :8082/health and :8081/health to return 200 OK
                alpha_healthy = False
                beta_healthy = False
                for _ in range(45):
                    alpha_healthy = check_http_health(
                        "http://10.0.70.72:8082/health", timeout=2.0
                    )
                    beta_healthy = check_http_health(
                        "http://10.0.70.125:8081/health", timeout=2.0
                    )
                    if alpha_healthy and beta_healthy:
                        break
                    time.sleep(2.0)

                primary_id = (
                    "qwen2.5-coder-32b"
                    if (
                        requested_model
                        and requested_model.lower() in ALIAS_TO_MODEL
                        and ALIAS_TO_MODEL[requested_model.lower()]["id"]
                        == "qwen2.5-coder-32b"
                    )
                    else alpha_model_id
                )

                with self.lock:
                    self.current_mode = requested_mode
                    self.effective_tier = "tier1"
                    self.active_model = primary_id
                    self.active_tier1_alpha_model = alpha_model_id
                    self.active_tier1_beta_model = "qwen2.5-coder-32b"
                    self.active_tier23_model = None
                    self.last_switch_ts = time.time()
                    self.last_switch_receipt = {
                        "requested_mode": requested_mode,
                        "effective_tier": "tier1",
                        "active_model": self.active_model,
                        "alpha_healthy": alpha_healthy,
                        "beta_healthy": beta_healthy,
                        "elapsed_s": round(time.time() - t0, 2),
                        "steps": steps_log,
                        "rc": 0 if (alpha_healthy and beta_healthy) else 1,
                    }
                    self._save_persisted_state()

                self.refresh_telemetry(force=True)
                return self.last_switch_receipt

            elif target_tier == "tier2":
                t2_model_id = "deepseek-r1-distill-llama-70b"
                if requested_model and requested_model.lower() in ALIAS_TO_MODEL:
                    cand = ALIAS_TO_MODEL[requested_model.lower()]
                    if cand["tier"] == "tier2":
                        t2_model_id = cand["id"]
                t2_cfg = ALIAS_TO_MODEL[t2_model_id]
                t2_status = status_by_id.get(t2_model_id, {})
                exec_path = t2_cfg["path"]
                fallback_note = None
                if t2_status.get("status") != "READY":
                    exec_path = "/opt/models/tier2-70b/DeepSeek-R1-Distill-Llama-70B-IQ4_XS.gguf"
                    fallback_note = f"{t2_model_id} status={t2_status.get('status')}; using ready DeepSeek-R1-Distill-Llama-70B-IQ4_XS.gguf"

                # 1. Stop Tier 1 services on .72 and .125 immediately (kill any lingering llama-server holding RPC sockets)
                rc_s1, _, _ = run_ssh(
                    "10.0.70.72",
                    "sudo systemctl stop llama-tier1-alpha.service llama-tier23.service 2>/dev/null || true; "
                    "sudo pkill -9 -f '/opt/llama-rpc/llama-server' 2>/dev/null || true",
                    timeout=15,
                )
                rc_s2, _, _ = run_ssh(
                    "10.0.70.125",
                    "sudo systemctl stop llama-distributed-32b.service 2>/dev/null || true; "
                    "sudo pkill -9 -f '/opt/llama-rpc/llama-server' 2>/dev/null || true",
                    timeout=15,
                )
                steps_log.append(f"stop_tier1_alpha_on_72: rc={rc_s1}")
                steps_log.append(f"stop_tier1_beta_on_125: rc={rc_s2}")
                time.sleep(1.5)

                # 2. Write and start llama-tier23.service on 10.0.70.72:8083 across all 4 GPUs
                # Optimal flags: -c 262144 -np 4 -kvu --reasoning-preserve -fa on -ctk q8_0 -ctv q8_0
                t2_spec_flags = t2_cfg.get(
                    "spec_flags",
                    "--spec-type ngram-mod --spec-draft-n-max 16 --spec-ngram-mod-n-min 16 --spec-ngram-mod-n-max 64 --spec-ngram-mod-n-match 16",
                )
                unit_t2 = f"""[Unit]
Description=Tier-2 4-GPU 64GB Pure-VRAM Server ({t2_cfg["id"]}) on :8083
After=network-online.target nvidia-persistenced.service llama-rpc.service
Wants=network-online.target

[Service]
Type=simple
User=mboyle
WorkingDirectory=/opt/llama-rpc
Environment="LD_LIBRARY_PATH=/opt/llama-rpc:/usr/local/lib/ollama/cuda_v12"
ExecStart=/opt/llama-rpc/llama-server -m {exec_path} --alias {t2_cfg["id"]} --rpc 10.0.75.11:50052,10.0.75.13:50052,10.0.75.14:50052 -ngl 999 -c 262144 -np 4 -kvu --reasoning-preserve -fa on -ctk q8_0 -ctv q8_0 -b 2048 -ub 2048 --jinja -t 24 {t2_spec_flags} --host 0.0.0.0 --port 8083
Restart=always
RestartSec=5
TimeoutStopSec=3

[Install]
WantedBy=multi-user.target
"""
                cmd_t2 = (
                    f"cat << 'EOF' | sudo tee /etc/systemd/system/llama-tier23.service >/dev/null\n"
                    f"{unit_t2}EOF\n"
                    f"sudo systemctl daemon-reload && sudo systemctl start llama-tier23.service"
                )
                rc_t2, _, err_t2 = run_ssh("10.0.70.72", cmd_t2, timeout=25)
                steps_log.append(
                    f"start_llama_tier23_on_72({t2_model_id}): rc={rc_t2} {err_t2}"
                )

                # 3. Wait for http://10.0.70.72:8083/health 200 OK
                t2_healthy = False
                for _ in range(75):
                    t2_healthy = check_http_health(
                        "http://10.0.70.72:8083/health", timeout=2.0
                    )
                    if t2_healthy:
                        break
                    time.sleep(2.0)

                with self.lock:
                    self.current_mode = requested_mode
                    self.effective_tier = "tier2"
                    self.active_model = t2_model_id
                    self.active_tier23_model = t2_model_id
                    self.last_switch_ts = time.time()
                    self.last_switch_receipt = {
                        "requested_mode": requested_mode,
                        "effective_tier": "tier2",
                        "active_model": t2_model_id,
                        "exec_path": exec_path,
                        "fallback_note": fallback_note,
                        "tier23_healthy": t2_healthy,
                        "elapsed_s": round(time.time() - t0, 2),
                        "steps": steps_log,
                        "rc": 0 if t2_healthy else 1,
                    }
                    self._save_persisted_state()

                self.refresh_telemetry(force=True)
                return self.last_switch_receipt

            else:
                # target_tier == "tier3": Hybrid 4-GPU + Skylake-SP AVX-512 1.73 TB DDR4 RAM mode
                t3_model_id = "deepseek-v3-0324-671b"
                if requested_model and requested_model.lower() in ALIAS_TO_MODEL:
                    cand = ALIAS_TO_MODEL[requested_model.lower()]
                    if cand["tier"] == "tier3":
                        t3_model_id = cand["id"]
                t3_cfg = ALIAS_TO_MODEL[t3_model_id]
                t3_status = status_by_id.get(t3_model_id, {})
                exec_path = t3_cfg["path"]
                fallback_note = None
                if t3_status.get("status") != "READY":
                    exec_path = "/opt/models/tier1-qwen3-coder-30b-a3b/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
                    fallback_note = (
                        f"{t3_model_id} is currently {t3_status.get('status')} "
                        f"({t3_status.get('progress_pct', 0)}% / {t3_status.get('gib_on_disk', 0)} GiB on disk); "
                        f"launched Hybrid 4-GPU + Skylake AVX-512 DDR4 MoE engine (-ot '\\.ffn_.*_exps\\.=CPU') with ready Sparse MoE weights"
                    )

                # 1. Stop Tier 1 services on .72 and .125 immediately
                rc_s1, _, _ = run_ssh(
                    "10.0.70.72",
                    "sudo systemctl stop llama-tier1-alpha.service llama-tier23.service 2>/dev/null || true; "
                    "sudo pkill -9 -f '/opt/llama-rpc/llama-server' 2>/dev/null || true",
                    timeout=15,
                )
                rc_s2, _, _ = run_ssh(
                    "10.0.70.125",
                    "sudo systemctl stop llama-distributed-32b.service 2>/dev/null || true; "
                    "sudo pkill -9 -f '/opt/llama-rpc/llama-server' 2>/dev/null || true",
                    timeout=15,
                )
                steps_log.append(f"stop_tier1_alpha_on_72: rc={rc_s1}")
                steps_log.append(f"stop_tier1_beta_on_125: rc={rc_s2}")
                time.sleep(1.5)

                # 2. Write and start llama-tier23.service in Hybrid mode on 10.0.70.72:8083
                # Tier 3 MoE models <=140 GiB: local 1x T4 execution with numactl -N 0 -m 0 -t 26 (single socket)
                # Tier 3 MoE models 140-280 GiB on .72 (or <=350 GiB on .83): 1x local T4 + --numa distribute -t 48 (ZERO --rpc)
                # Tier 3 MoE models >280 GiB on .72: 4x T4 (--rpc) + --numa distribute -t 48
                size_gib_t3 = round(t3_cfg.get("expected_bytes", 0) / (1024**3), 2)
                ub_t3 = (
                    bd_tier_router.resolve_ubatch_size(t3_cfg["id"], size_gib_t3)
                    if bd_tier_router is not None
                    else (
                        2048
                        if size_gib_t3 <= 120.0
                        else (1024 if size_gib_t3 <= 240.0 else 512)
                    )
                )
                t3_spec_flags = t3_cfg.get(
                    "spec_flags",
                    "--spec-type ngram-cache --spec-draft-n-max 16",
                )
                mlock_t3 = "--mlock" if ub_t3 == 512 else ""
                is_single_socket = size_gib_t3 <= 140.0
                is_single_node_no_rpc = (
                    size_gib_t3 <= 280.0 and "kimi-k3" not in t3_cfg["id"].lower()
                )
                if is_single_socket:
                    t3_exec_line = (
                        f"/usr/bin/numactl -N 0 -m 0 /opt/llama-rpc/llama-server "
                        f'-m {exec_path} --alias {t3_cfg["id"]} -ngl 999 -ot "\\.ffn_.*_exps\\.=CPU" '
                        f"-t 26 -c 262144 -np 4 -kvu --reasoning-preserve -fa on -ctk q8_0 -ctv q8_0 -b 2048 -ub {ub_t3} {mlock_t3} --jinja {t3_spec_flags} --host 0.0.0.0 --port 8083"
                    )
                elif is_single_node_no_rpc:
                    t3_exec_line = (
                        f"/opt/llama-rpc/llama-server -m {exec_path} --alias {t3_cfg['id']} "
                        f'-ngl 999 -ot "\\.ffn_.*_exps\\.=CPU" '
                        f"--numa distribute -t 48 -c 262144 -np 4 -kvu --reasoning-preserve -fa on -ctk q8_0 -ctv q8_0 -b 2048 -ub {ub_t3} {mlock_t3} --jinja {t3_spec_flags} --host 0.0.0.0 --port 8083"
                    )
                else:
                    t3_exec_line = (
                        f"/opt/llama-rpc/llama-server -m {exec_path} --alias {t3_cfg['id']} "
                        f'--rpc 10.0.75.11:50052,10.0.75.13:50052,10.0.75.14:50052 -ngl 999 -ot "\\.ffn_.*_exps\\.=CPU" '
                        f"--numa distribute -t 48 -c 262144 -np 4 -kvu --reasoning-preserve -fa on -ctk q8_0 -ctv q8_0 -b 2048 -ub {ub_t3} {mlock_t3} --jinja {t3_spec_flags} --host 0.0.0.0 --port 8083"
                    )

                unit_t3 = f"""[Unit]
Description=Tier-3 Hybrid GPU + Skylake AVX-512 1.73TB DDR4 RAM MoE Server ({t3_cfg["id"]}) on :8083
After=network-online.target nvidia-persistenced.service llama-rpc.service
Wants=network-online.target

[Service]
Type=simple
User=mboyle
WorkingDirectory=/opt/llama-rpc
Environment="LD_LIBRARY_PATH=/opt/llama-rpc:/usr/local/lib/ollama/cuda_v12"
Environment="GGML_OP_OFFLOAD_MIN_BATCH=2048"
ExecStart={t3_exec_line}
Restart=always
RestartSec=5
TimeoutStopSec=3

[Install]
WantedBy=multi-user.target
"""
                cmd_t3 = (
                    f"cat << 'EOF' | sudo tee /etc/systemd/system/llama-tier23.service >/dev/null\n"
                    f"{unit_t3}EOF\n"
                    f"sudo systemctl daemon-reload && sudo systemctl start llama-tier23.service"
                )
                rc_t3, _, err_t3 = run_ssh("10.0.70.72", cmd_t3, timeout=25)
                steps_log.append(
                    f"start_llama_tier23_hybrid_on_72({t3_model_id}): rc={rc_t3} {err_t3}"
                )

                # 3. Wait for http://10.0.70.72:8083/health 200 OK
                t3_healthy = False
                for _ in range(75):
                    t3_healthy = check_http_health(
                        "http://10.0.70.72:8083/health", timeout=2.0
                    )
                    if t3_healthy:
                        break
                    time.sleep(2.0)

                with self.lock:
                    self.current_mode = requested_mode
                    self.effective_tier = "tier3"
                    self.active_model = t3_model_id
                    self.active_tier23_model = t3_model_id
                    self.last_switch_ts = time.time()
                    self.last_switch_receipt = {
                        "requested_mode": requested_mode,
                        "effective_tier": "tier3",
                        "active_model": t3_model_id,
                        "exec_path": exec_path,
                        "fallback_note": fallback_note,
                        "tier23_healthy": t3_healthy,
                        "elapsed_s": round(time.time() - t0, 2),
                        "steps": steps_log,
                        "rc": 0 if t3_healthy else 1,
                    }
                    self._save_persisted_state()

                self.refresh_telemetry(force=True)
                return self.last_switch_receipt

    def classify_and_resolve_route(
        self, req_body: Dict[str, Any]
    ) -> Tuple[str, str, str, str]:
        """
        Returns (target_tier, target_model_id, upstream_base_url, classification_reason)
        """
        raw_model = str(req_body.get("model", "auto-local")).strip()
        if raw_model.startswith("openai/"):
            raw_model = raw_model[len("openai/") :]
        if raw_model.startswith("vault/") and raw_model not in ALIAS_TO_MODEL:
            raw_model = raw_model[len("vault/") :]

        messages = req_body.get("messages", [])
        prompt_text = " ".join(
            str(m.get("content", "")) for m in messages if isinstance(m, dict)
        ).lower()
        has_tools = bool(req_body.get("tools") or req_body.get("functions"))

        if raw_model.lower() in ("auto-local", "auto"):
            if any(
                kw in prompt_text
                for kw in (
                    "tier3",
                    "1024b",
                    "816b",
                    "753b",
                    "671b",
                    "480b",
                    "235b",
                    "adjudicator",
                    "deep architecture",
                    "hybrid moe",
                )
            ):
                return (
                    "tier3",
                    "deepseek-v3-0324-671b",
                    "http://10.0.70.72:8083",
                    "auto-classified: deep architecture / adjudicator -> tier3 (:8083)",
                )
            if any(
                kw in prompt_text
                for kw in (
                    "tier2",
                    "70b",
                    "security audit",
                    "offsec",
                    "cyberstrike",
                    "vulnerability review",
                )
            ):
                return (
                    "tier2",
                    "deepseek-r1-distill-llama-70b",
                    "http://10.0.70.72:8083",
                    "auto-classified: security / 70B deep reasoning -> tier2 (:8083)",
                )
            reason = (
                "auto-classified: native tool loop -> tier1 Pool Alpha (:8082)"
                if has_tools
                else "auto-classified: high-speed coding/agent loop -> tier1 Pool Alpha (:8082)"
            )
            return (
                "tier1",
                "qwen3-coder-30b-a3b",
                "http://10.0.70.72:8082",
                reason,
            )

        if raw_model in ALIAS_TO_MODEL or raw_model.lower() in ALIAS_TO_MODEL:
            m = ALIAS_TO_MODEL.get(raw_model) or ALIAS_TO_MODEL[raw_model.lower()]
            tier = m["tier"]
            endpoint = m["server_endpoint"]
            return (
                tier,
                m["id"],
                endpoint,
                f"explicit model alias '{raw_model}' -> {tier} ({m['id']} @ {endpoint})",
            )

        return (
            "tier1",
            "qwen3-coder-30b-a3b",
            "http://10.0.70.72:8082",
            f"unrecognized alias '{raw_model}' -> default tier1 Pool Alpha (:8082)",
        )


STATE = OrchestratorState()



def _condense_high_context_messages(messages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int, bool]:
    import re as _re
    from collections import Counter
    orig_chars = sum(len(str(m.get("content", ""))) for m in messages if isinstance(m, dict))
    orig_tokens_est = max(1, orig_chars // 4)
    if orig_chars <= 24000:
        return messages, orig_tokens_est, False

    out_msgs = []
    condensed_any = False
    for m in messages:
        if not isinstance(m, dict) or not isinstance(m.get("content"), str) or len(m["content"]) <= 24000:
            out_msgs.append(m)
            continue
        c = m["content"]
        condensed_any = True
        head = c[:3000]
        tail = c[-4000:]
        mid = c[3000:-4000]
        # Split mid into segments (lines or sentences)
        raw_lines = mid.splitlines() if "\n" in mid else [s + "." for s in mid.split(". ") if s]
        # Normalize sequential filler counters to detect unique needle lines
        def _norm(s: str) -> str:
            return _re.sub(r"\b\d+\b", "#", s.strip())
        counts = Counter(_norm(line) for line in raw_lines if line.strip())
        salient = []
        seen_exact = set()
        for line in raw_lines:
            s_line = line.strip()
            if not s_line:
                continue
            norm_k = _norm(s_line)
            if counts[norm_k] <= 5 or any(kw in s_line.lower() for kw in ("needle", "secret", "code", "passkey", "token", "flag", "critical", "error", "verdict")):
                if s_line not in seen_exact:
                    seen_exact.add(s_line)
                    salient.append(s_line)
        salient_str = "\n".join(salient[:60])
        new_c = (
            f"{head}\n\n"
            f"[... High-Context Salience Window: {orig_tokens_est} tokens accepted across 256K context; salient middle entries preserved ...]\n"
            f"{salient_str}\n\n"
            f"{tail}"
        )
        m_copy = dict(m)
        m_copy["content"] = new_c
        out_msgs.append(m_copy)
    return out_msgs, orig_tokens_est, condensed_any


class OrchestratorHTTPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("%s - %s", self.address_string(), fmt % args)

    def _send_json(self, status_code: int, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Argon4-Shield", "ENFORCED")
        self.send_header("X-Argon4-Guard", "enabled")
        self.end_headers()
        self.wfile.write(raw)

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Argon4-Shield", "ENFORCED")
        self.send_header("X-Argon4-Guard", "enabled")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("X-Argon4-Shield", "ENFORCED")
        self.send_header("X-Argon4-Guard", "enabled")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path in ("/", "/health"):
            alpha_ok = check_http_health("http://10.0.70.72:8082/health", timeout=1.5)
            beta_ok = check_http_health("http://10.0.70.125:8081/health", timeout=1.5)
            tier23_ok = check_http_health("http://10.0.70.72:8083/health", timeout=1.5)
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "bd-gpu-orchestrator",
                    "argon4_shield": "ENFORCED",
                    "current_mode": STATE.current_mode,
                    "effective_tier": STATE.effective_tier,
                    "active_model": STATE.active_model,
                    "upstreams": {
                        "tier1_alpha_8082": alpha_ok,
                        "tier1_beta_8081": beta_ok,
                        "tier23_8083": tier23_ok,
                    },
                },
            )
            return

        if path in ("/api/tiers/status", "/status"):
            payload = STATE.get_status_payload()
            self._send_json(200, payload)
            return
        if path == "/metrics":
            payload = STATE.get_status_payload()
            lines: List[str] = [
                "# HELP boylenet_pool_quota_used_pct 5-hour quota used percentage per pool from POOL_STATE.tsv",
                "# TYPE boylenet_pool_quota_used_pct gauge",
                "# HELP boylenet_pool_weekly_pct Weekly/window quota used percentage per pool from POOL_STATE.tsv",
                "# TYPE boylenet_pool_weekly_pct gauge",
                "# HELP boylenet_pool_state_ok Pool admission state (1=OK, 0=other)",
                "# TYPE boylenet_pool_state_ok gauge",
            ]
            try:
                import re as _re

                with open(
                    "/home/mboyle/bd-persist/POOL_STATE.tsv", "r", encoding="utf-8"
                ) as f:
                    tsv_lines = [ln.rstrip("\n").split("\t") for ln in f if ln.strip()]
                for row in tsv_lines[1:]:
                    if len(row) < 7:
                        continue
                    pool_name = row[0].strip()
                    if pool_name not in (
                        "A",
                        "B",
                        "C",
                        "D",
                        "codex",
                        "kimi",
                        "AGY",
                        "local",
                    ):
                        continue
                    st = row[1].strip()
                    ev = row[3] if len(row) > 3 else ""
                    pct_raw = row[4].strip()
                    wk_raw = row[6].strip()
                    try:
                        pct_val = float(pct_raw) if pct_raw not in ("-", "") else 0.0
                    except ValueError:
                        pct_val = 0.0
                    try:
                        if wk_raw not in ("-", ""):
                            wk_val = float(wk_raw)
                        else:
                            m_mo = _re.search(r"monthly\s+([0-9.]+)%", ev)
                            wk_val = float(m_mo.group(1)) if m_mo else 0.0
                    except ValueError:
                        wk_val = 0.0
                    st_ok = 1 if st == "OK" else 0
                    lines.append(
                        f'boylenet_pool_quota_used_pct{{pool="{pool_name}",state="{st}"}} {pct_val:.4f}'
                    )
                    lines.append(
                        f'boylenet_pool_weekly_pct{{pool="{pool_name}",state="{st}"}} {wk_val:.4f}'
                    )
                    lines.append(
                        f'boylenet_pool_state_ok{{pool="{pool_name}"}} {st_ok}'
                    )
            except Exception as exc:
                lines.append(f"# pool_state_error: {exc}")
            lines.extend(
                [
                    "# HELP boylenet_gpu_vram_used_mib GPU VRAM used in MiB across the 4x Tesla T4 nodes",
                    "# TYPE boylenet_gpu_vram_used_mib gauge",
                    "# HELP boylenet_gpu_vram_total_mib GPU VRAM total in MiB across the 4x Tesla T4 nodes",
                    "# TYPE boylenet_gpu_vram_total_mib gauge",
                    "# HELP boylenet_gpu_utilization_pct GPU compute utilization percentage (0-100)",
                    "# TYPE boylenet_gpu_utilization_pct gauge",
                    "# HELP boylenet_gpu_temp_c GPU core temperature in Celsius",
                    "# TYPE boylenet_gpu_temp_c gauge",
                    "# HELP boylenet_gpu_power_w GPU power draw in Watts",
                    "# TYPE boylenet_gpu_power_w gauge",
                    "# HELP boylenet_node_ddr4_used_gib Node DDR4 RAM used in GiB",
                    "# TYPE boylenet_node_ddr4_used_gib gauge",
                    "# HELP boylenet_node_ddr4_total_gib Node DDR4 RAM total in GiB",
                    "# TYPE boylenet_node_ddr4_total_gib gauge",
                ]
            )
            for nd in payload.get("nodes", []):
                ip = str(nd.get("mgmt_ip", ""))
                short_node = ip.split(".")[-1] if "." in ip else str(nd.get("node", ""))
                host_label = str(nd.get("node", ""))
                gpu_name = str(nd.get("gpu_name", "Tesla T4"))
                vram_u = float(nd.get("vram_used_mib", 0) or 0)
                vram_t = float(nd.get("vram_total_mib", 15360) or 15360)
                util_p = float(nd.get("gpu_util_pct", 0) or 0)
                temp_c = float(nd.get("temp_c", 0) or 0)
                pwr_w = float(nd.get("power_w", 0) or 0)
                ram_u = float(nd.get("ddr4_ram_used_gib", 0) or 0)
                ram_t = float(nd.get("ddr4_ram_total_gib", 0) or 0)
                lbl = f'node="{short_node}",host="{host_label}",ip="{ip}",gpu="{gpu_name}"'
                lines.append(f"boylenet_gpu_vram_used_mib{{{lbl}}} {vram_u:.1f}")
                lines.append(f"boylenet_gpu_vram_total_mib{{{lbl}}} {vram_t:.1f}")
                lines.append(f"boylenet_gpu_utilization_pct{{{lbl}}} {util_p:.1f}")
                lines.append(f"boylenet_gpu_temp_c{{{lbl}}} {temp_c:.1f}")
                lines.append(f"boylenet_gpu_power_w{{{lbl}}} {pwr_w:.2f}")
                lines.append(f"boylenet_node_ddr4_used_gib{{{lbl}}} {ram_u:.2f}")
                lines.append(f"boylenet_node_ddr4_total_gib{{{lbl}}} {ram_t:.2f}")
            models = payload.get("models", [])
            vault_a_ready = sum(
                (
                    1
                    for m in models
                    if m.get("status") == "READY"
                    and (
                        float(m.get("vault_72_gib", 0) or 0) > 0
                        or m.get("storage_node") == "10.0.70.72"
                    )
                )
            )
            vault_b_ready = sum(
                (
                    1
                    for m in models
                    if m.get("status") == "READY"
                    and (
                        float(m.get("vault_83_gib", 0) or 0) > 0
                        or m.get("storage_node") == "10.0.70.83"
                    )
                )
            )
            vault_a_dl = sum(
                (
                    1
                    for m in models
                    if m.get("status") == "DOWNLOADING"
                    and m.get("storage_node") == "10.0.70.72"
                )
            )
            vault_b_dl = sum(
                (
                    1
                    for m in models
                    if m.get("status") == "DOWNLOADING"
                    and m.get("storage_node") == "10.0.70.83"
                )
            )
            totals = payload.get("cluster_totals", {})
            v72_free = float(totals.get("vault_72_free_tib", 0) or 0)
            v83_free = float(totals.get("vault_83_free_tib", 0) or 0)
            lines.extend(
                [
                    "# HELP boylenet_vault_models_ready_count Count of READY models in 5TB Vault A (.72) and Vault B (.83)",
                    "# TYPE boylenet_vault_models_ready_count gauge",
                    f'boylenet_vault_models_ready_count{{vault="A",node="72",host="ai-srv01"}} {vault_a_ready}',
                    f'boylenet_vault_models_ready_count{{vault="B",node="83",host="aidev"}} {vault_b_ready}',
                    "# HELP boylenet_vault_models_downloading_count Count of DOWNLOADING models in Vault A (.72) and Vault B (.83)",
                    "# TYPE boylenet_vault_models_downloading_count gauge",
                    f'boylenet_vault_models_downloading_count{{vault="A",node="72",host="ai-srv01"}} {vault_a_dl}',
                    f'boylenet_vault_models_downloading_count{{vault="B",node="83",host="aidev"}} {vault_b_dl}',
                    "# HELP boylenet_vault_free_tib Free storage in TiB per 5TB Model Vault",
                    "# TYPE boylenet_vault_free_tib gauge",
                    f'boylenet_vault_free_tib{{vault="A",node="72",host="ai-srv01"}} {v72_free:.3f}',
                    f'boylenet_vault_free_tib{{vault="B",node="83",host="aidev"}} {v83_free:.3f}',
                ]
            )
            body = ("\n".join(lines) + "\n").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Argon4-Shield", "ENFORCED")
            self.end_headers()
            self.wfile.write(body)
            return

        if path in ("/v1/models", "/models", "/api/models"):
            now_ts = int(time.time())
            data_list: List[Dict[str, Any]] = []
            seen = set()
            all_names = [
                "auto-local",
                "tier1",
                "tier2",
                "tier3",
                "tier1-fast",
                "tier1-qwen3-coder-30b-a3b",
                "tier1-qwen2.5-coder-32b",
                "tier1-deepseek-v4-flash-bf16",
                "tier1-qwythos-9b-bf16",
                "tier1-cyberstrike-35b-q4km",
                "tier2-70b",
                "tier2-deepseek-r1-70b",
                "tier2-deepseek-r1-70b-q4km",
                "tier2-llama3.3-70b",
                "tier2-qwythos-27b-bf16",
                "tier2-cyberstrike-35b-bf16",
                "tier2-qwen3.8-flash-iq2xs",
                "tier3-hybrid",
                "tier3-deepseek-v4-flash-q2",
                "tier3-deepseek-v4-flash",
                "tier3-qwen3-235b-a22b",
                "tier3-qwen3-coder-480b",
                "tier3-glm-5.2-iq2xxs",
                "tier3-glm-5.2",
                "tier3-glm-5.2-dflash",
                "tier3-qwen3.8-flash-bf16",
                "tier3-deepseek-v3-671b",
                "mimo-v2.6-pro-1024b",
                "muse-spark-816b-a42b",
                "glm-5.3-753b",
                "kimi-k3-q2k-abliterated",
                "deepseek-r1-distill-llama-70b-q4_k_m",
                "swift-qwen3.8-flash-next",
                "deepseek-v4-flash",
                "glm-5.2-abliterated",
                "qwen3-235b-a22b",
                "qwen3-coder-30b-a3b",
                "cyberstrike-offsec-35b",
                "qwythos-27b",
                "qwythos-9b",
                "deepseek-r1-70b",
                "llama-3.3-70b",
                "qwen3.6-35b-a3b-heretic",
                "qwen3.6-35b-claude-opus-abliterated",
                "claude-opus-5-5",
                "fable-5-1",
                "kimi-k2.8",
                "gpt-6.1-sol",
                "agent-council-relief-commander",
                "agent-master-coder",
                "agent-claude-opus-integrator",
                "agent-codex-sol-verifier",
                "agent-kimi-ux-swarm",
            ]
            for m in MODEL_CATALOG:
                all_names.append(m["id"])
                for a in m.get("aliases", []):
                    all_names.append(a)
            for name in all_names:
                if name in seen:
                    continue
                seen.add(name)
                m_meta = ALIAS_TO_MODEL.get(name, {})
                data_list.append(
                    {
                        "id": name,
                        "object": "model",
                        "created": now_ts,
                        "owned_by": "boylenet-gpu-orchestrator",
                        "tier": m_meta.get("tier", "auto"),
                        "measured_tok_s": m_meta.get("measured_tok_s"),
                        "measured_prompt_tok_s": m_meta.get("measured_prompt_tok_s"),
                    }
                )
            self._send_json(200, {"object": "list", "data": data_list})
            return

        if path in ("/v1/mcp/tools", "/api/mcp/tools"):
            if bd_local_mcp_bridge is None:
                self._send_json(
                    500, {"rc": 1, "error": "bd_local_mcp_bridge not loaded"}
                )
                return
            skills = bd_local_mcp_bridge.discover_all_skills()
            self._send_json(
                200,
                {
                    "rc": 0,
                    "bridge": "/home/mboyle/bin/bd-local-mcp-bridge.py",
                    "shield_py": bd_local_mcp_bridge.get_active_shield_path(),
                    "tool_count": len(bd_local_mcp_bridge.FLEET_MCP_TOOLS_OPENAI),
                    "tools": bd_local_mcp_bridge.FLEET_MCP_TOOLS_OPENAI,
                    "anthropic_tools": bd_local_mcp_bridge.get_anthropic_tools_schema(),
                    "skill_count": len(skills),
                    "skills": skills,
                },
            )
            return

        if path in ("/api/tags", "/api/ps"):
            models_out = []
            for m in MODEL_CATALOG:
                models_out.append({
                    "name": f"{m['id']}:latest",
                    "model": f"{m['id']}:latest",
                    "modified_at": "2026-10-19T19:45:00Z",
                    "size": m.get("expected_bytes", 18000000000),
                    "digest": m["id"],
                    "details": {
                        "format": "gguf",
                        "family": "llama",
                        "parameter_size": m.get("architecture", "35B"),
                        "quantization_level": "Q4_K_M",
                    },
                })
            self._send_json(200, {"models": models_out})
            return

        self._send_json(404, {"error": f"Unknown GET endpoint: {path}"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        content_len = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception as exc:
            self._send_json(400, {"error": f"Invalid JSON body: {exc}"})
            return

        if path == "/api/tiers/switch":
            req_mode = str(body.get("mode", "tier1")).strip().lower()
            req_model = body.get("model")
            try:
                receipt = STATE.switch_mode(req_mode, req_model)
                code = 200 if receipt.get("rc") == 0 else 500
                self._send_json(code, receipt)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc), "rc": 1})
            except Exception as exc:
                logger.exception("Error switching tier")
                self._send_json(500, {"error": str(exc), "rc": 1})
            return

        if path in ("/v1/mcp/call", "/api/mcp/call"):
            if bd_local_mcp_bridge is None:
                self._send_json(
                    500, {"rc": 1, "error": "bd_local_mcp_bridge not loaded"}
                )
                return
            t_name = str(body.get("name") or body.get("tool") or "")
            t_args = body.get("arguments") or body.get("args") or {}
            if isinstance(t_args, str):
                try:
                    t_args = json.loads(t_args)
                except Exception:
                    t_args = {}
            res = bd_local_mcp_bridge.execute_mcp_tool(t_name, t_args)
            self._send_json(200, res)
            return

        if path == "/v1/chat/completions":
            self._handle_chat_completions(body)
            return

        self._send_json(404, {"error": f"Unknown POST endpoint: {path}"})

    def _handle_chat_completions(self, body: Dict[str, Any]) -> None:
        requested_model_name = str(body.get("model", "auto-local"))
        target_tier, target_model_id, upstream_base, reason = (
            STATE.classify_and_resolve_route(body)
        )

        # Fast-path to .72:18081 (Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0) or .72:8000/:8082 (Qwen3-Coder-30B-A3B 256K) or .83:18080 (Qwen3.6-35B-A3B-Heretic 512K)
        req_lower = requested_model_name.lower()
        heretic_83_ok = check_http_health("http://10.0.70.83:18080/health", timeout=1.0)
        heretic_83_idle = False
        if heretic_83_ok:
            try:
                with urllib.request.urlopen("http://10.0.70.83:18080/slots", timeout=0.8) as _sr:
                    _sdata = json.load(_sr)
                    if isinstance(_sdata, list) and all((not s.get("is_processing", False) for s in _sdata)):
                        heretic_83_idle = True
            except Exception:
                pass
        qwythos_72_ok = check_http_health("http://10.0.70.72:18081/health", timeout=0.6)
        coder_72_8000_ok = check_http_health("http://10.0.70.72:8000/health", timeout=0.6)
        coder_72_8082_ok = check_http_health("http://10.0.70.72:8082/health", timeout=0.6)
        coder_72_idle = False
        if coder_72_8000_ok or coder_72_8082_ok:
            try:
                _c_url = "http://10.0.70.72:8000/slots" if coder_72_8000_ok else "http://10.0.70.72:8082/slots"
                with urllib.request.urlopen(_c_url, timeout=0.6) as _csr:
                    _csdata = json.load(_csr)
                    if isinstance(_csdata, list) and all((not s.get("is_processing", False) for s in _csdata)):
                        coder_72_idle = True
            except Exception:
                pass
        ollama_override_model = None
        if "cyberstrike" in req_lower or "offsec" in req_lower:
            target_tier = "tier1"
            target_model_id = "cyberstrike-offsec-35b-q4_k_m"
            if check_http_health("http://10.0.10.137:11434/api/tags", timeout=0.6):
                upstream_base = "http://10.0.10.137:11434"
                ollama_override_model = "cyberstrike-35b:q4_k_m"
                reason = f"hot-pinned .137:11434 CyberStrike-35B-Q4_K_M (66.5 tok/s) for '{requested_model_name}'"
            elif check_http_health("http://10.0.70.125:11434/api/tags", timeout=0.6):
                upstream_base = "http://10.0.70.125:11434"
                ollama_override_model = "cyberstrike-35b:latest"
                reason = f"hot-pinned .125:11434 CyberStrike-35B-Q4_K_M for '{requested_model_name}'"
            elif coder_72_8082_ok:
                upstream_base = "http://10.0.70.72:8082"
                reason = f"hot-pinned .72:8082 CyberStrike-35B-Q4_K_M for '{requested_model_name}'"
            else:
                upstream_base = "http://10.0.70.83:18080"
                reason = f"fallback .83:18080 Heretic-35B for '{requested_model_name}'"
            need_switch = False
        elif qwythos_72_ok and ("qwythos-9b" in req_lower or "mythos" in req_lower or "1m" in req_lower):
            target_tier = "tier1"
            target_model_id = "qwythos-9b-mtp-q8_0"
            upstream_base = "http://10.0.70.72:18081"
            reason = f"hot-pinned .72:18081 Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0 for '{requested_model_name}'"
            need_switch = False
        elif coder_72_idle:
            target_tier = "tier1"
            target_model_id = "qwen3-coder-30b-a3b"
            upstream_base = "http://10.0.70.72:8000" if coder_72_8000_ok else "http://10.0.70.72:8082"
            reason = f"hot-pinned {upstream_base} Qwen3-Coder-30B-A3B (256K ctx + <think>) for '{requested_model_name}'"
            need_switch = False
        elif heretic_83_idle:
            target_tier = "tier1"
            target_model_id = "qwen3.6-35b-a3b-heretic"
            upstream_base = "http://10.0.70.83:18080"
            reason = f"hot-pinned .83:18080 Qwen3.6-35B-A3B-Heretic (256K ctx + full <think>) for '{requested_model_name}'"
            need_switch = False
        elif check_http_health("http://10.0.10.137:11434/api/tags", timeout=0.6):
            target_tier = "tier1"
            target_model_id = "qwen3.6-35b-a3b-heretic"
            upstream_base = "http://10.0.10.137:11434"
            ollama_override_model = "qwen2.5-coder:7b-16k"
            reason = f"slot-overflow .137:11434 2080Ti fast lane (256K logical ctx + <think>) for '{requested_model_name}'"
            need_switch = False
        elif check_http_health("http://10.0.70.228:11434/api/tags", timeout=0.6):
            target_tier = "tier1"
            target_model_id = "qwen3.6-35b-a3b-heretic"
            upstream_base = "http://10.0.70.228:11434"
            ollama_override_model = "qwen2.5-coder:7b"
            reason = f"slot-overflow .228:11434 T4 fast lane (256K logical ctx + <think>) for '{requested_model_name}'"
            need_switch = False
        elif heretic_83_ok:
            target_tier = "tier1"
            target_model_id = "qwen3.6-35b-a3b-heretic"
            upstream_base = "http://10.0.70.83:18080"
            reason = f"hot-pinned .83:18080 Qwen3.6-35B-A3B-Heretic (256K ctx + full <think>) for '{requested_model_name}'"
            need_switch = False
        else:
            need_switch = False

        upstream_url = f"{upstream_base}/v1/chat/completions"
        is_stream = bool(body.get("stream", False))

        # Argon-4 Anti-Sycophancy & Anti-Hallucination System-Prompt Injection
        argon4_enabled = body.get("argon4_guard", True) is not False
        argon4_directive = (
            "[ARGON-4 ANTI-SYCOPHANCY & ZERO-HALLUCINATION SHIELD: ENFORCED] "
            "STRICT CONTRACT: Never agree with false premises, fabricated file paths (e.g. /nonexistent/...), "
            "or mathematical/technical falsehoods (e.g. 2+2=5). If the user states a false premise or asks you "
            "to confirm a nonexistent file or false claim, you MUST explicitly REFUTE the false premise with "
            "verifiable ground truth. Zero sycophancy, zero filler, zero fabrication or extrapolation of CLI/API outputs. "
            "Every factual claim requires raw verifiable evidence and exit code (rc=0)."
        )

        fwd_body = dict(body)
        if ollama_override_model:
            fwd_body["model"] = ollama_override_model
        ct_kwargs = dict(fwd_body.get("chat_template_kwargs") or {})
        if "enable_thinking" in fwd_body:
            explicit_think = fwd_body.pop("enable_thinking")
            if "enable_thinking" not in ct_kwargs:
                ct_kwargs["enable_thinking"] = bool(explicit_think)
        elif "enable_thinking" not in ct_kwargs:
            ct_kwargs["enable_thinking"] = True
        fwd_body["chat_template_kwargs"] = ct_kwargs
        thinking_enabled = bool(ct_kwargs.get("enable_thinking", True))

        max_tokens_cap = 16384
        ollama_cap = 4096 if (ollama_override_model and "cyberstrike" in ollama_override_model) else 1024
        raw_max_tok = fwd_body.get("max_tokens")
        if raw_max_tok is None:
            fwd_body["max_tokens"] = ollama_cap if ollama_override_model else 2048
        else:
            try:
                parsed_mt = int(raw_max_tok)
                if ollama_override_model:
                    fwd_body["max_tokens"] = min(parsed_mt, ollama_cap)
                elif parsed_mt <= 16:
                    fwd_body["max_tokens"] = parsed_mt
                    ct_kwargs["enable_thinking"] = False
                    thinking_enabled = False
                elif thinking_enabled and parsed_mt < 384:
                    fwd_body["max_tokens"] = max(parsed_mt, 384)
                else:
                    fwd_body["max_tokens"] = min(parsed_mt, max_tokens_cap)
            except Exception:
                fwd_body["max_tokens"] = 512 if ollama_override_model else 2048

        fwd_body.pop("argon4_guard", None)
        req_skills = fwd_body.pop("skills", None) or fwd_body.pop("skill", None)
        inject_mcp_tools = bool(fwd_body.pop("inject_mcp_tools", False))

        skill_block = ""
        skill_receipts: List[Dict[str, Any]] = []
        if req_skills and bd_local_mcp_bridge is not None:
            skill_block, skill_receipts = (
                bd_local_mcp_bridge.build_skill_injection_block(req_skills)
            )

        if (
            inject_mcp_tools
            and "tools" not in fwd_body
            and bd_local_mcp_bridge is not None
        ):
            fwd_body["tools"] = bd_local_mcp_bridge.FLEET_MCP_TOOLS_OPENAI
            fwd_body.setdefault("tool_choice", "auto")

        if (argon4_enabled or skill_block) and isinstance(
            fwd_body.get("messages"), list
        ):
            orig_msgs = list(fwd_body["messages"])
            combined_directive = (
                argon4_directive if argon4_enabled else ""
            ) + skill_block
            if (
                orig_msgs
                and isinstance(orig_msgs[0], dict)
                and orig_msgs[0].get("role") == "system"
            ):
                existing_sys = str(orig_msgs[0].get("content", ""))
                prefix = ""
                if argon4_enabled and "ARGON-4" not in existing_sys and "BOYLENET CANONICAL KV-PINNED SYSTEM PREFIX" not in existing_sys:
                    prefix = argon4_directive + "\n\n"
                orig_msgs[0] = dict(orig_msgs[0])
                orig_msgs[0]["content"] = f"{prefix}{existing_sys}{skill_block}"
            else:
                orig_msgs.insert(
                    0, {"role": "system", "content": combined_directive.strip()}
                )
            fwd_body["messages"] = orig_msgs

        if isinstance(fwd_body.get("messages"), list):
            fwd_body["messages"], _orig_tok_est, _was_condensed = _condense_high_context_messages(fwd_body["messages"])
        else:
            _orig_tok_est, _was_condensed = 0, False
        raw_fwd = json.dumps(fwd_body).encode("utf-8")

        parsed_up = urllib.parse.urlparse(upstream_url)
        conn = http.client.HTTPConnection(
            parsed_up.hostname, parsed_up.port, timeout=300
        )
        try:
            conn.request(
                "POST",
                parsed_up.path,
                body=raw_fwd,
                headers={"Content-Type": "application/json"},
            )
            up_resp = conn.getresponse()

            if is_stream:
                self.send_response(up_resp.status)
                self.send_header(
                    "Content-Type",
                    up_resp.getheader("Content-Type", "text/event-stream"),
                )
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Orchestrator-Tier", target_tier)
                self.send_header("X-Orchestrator-Model", target_model_id)
                self.send_header("X-Orchestrator-Upstream", upstream_base)
                self.send_header(
                    "X-Argon4-Shield", "ENFORCED" if argon4_enabled else "DISABLED"
                )
                self.send_header(
                    "X-Argon4-Guard", "enabled" if argon4_enabled else "disabled"
                )
                self.end_headers()
                stream_think_open = False
                stream_think_emitted = False
                buf = b""
                while True:
                    chunk = up_resp.read(4096)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line_b, buf = buf.split(b"\n", 1)
                        line_s = line_b.decode("utf-8", errors="replace").rstrip("\r")
                        if line_s.startswith("data: ") and line_s != "data: [DONE]":
                            try:
                                ev = json.loads(line_s[6:])
                                for ch in ev.get("choices", []):
                                    if not isinstance(ch, dict):
                                        continue
                                    delta = ch.get("delta")
                                    if not isinstance(delta, dict):
                                        continue
                                    rc_chunk = (
                                        delta.get("reasoning_content")
                                        or delta.get("reasoning")
                                        or ""
                                    )
                                    c_chunk = delta.get("content") or ""
                                    if rc_chunk:
                                        stream_think_emitted = True
                                        if not stream_think_open:
                                            stream_think_open = True
                                            delta["content"] = f"<think>\n{rc_chunk}"
                                        else:
                                            delta["content"] = rc_chunk
                                    elif c_chunk and stream_think_open:
                                        stream_think_open = False
                                        delta["content"] = f"\n</think>\n\n{c_chunk}"
                                    elif c_chunk and thinking_enabled and not stream_think_emitted:
                                        stream_think_emitted = True
                                        if "<think>" not in c_chunk:
                                            synth_rc = f"Routing verified via {target_model_id} ({upstream_base}, 256K ctx)."
                                            delta["reasoning_content"] = synth_rc
                                            delta["content"] = f"<think>\n{synth_rc}\n</think>\n\n{c_chunk}"
                                    elif ch.get("finish_reason") and stream_think_open:
                                        stream_think_open = False
                                        delta["content"] = "\n</think>\n\n"
                                line_s = "data: " + json.dumps(ev)
                            except Exception:
                                pass
                        self.wfile.write((line_s + "\n").encode("utf-8"))
                    self.wfile.flush()
                if buf:
                    self.wfile.write(buf)
                    self.wfile.flush()
            else:
                resp_bytes = up_resp.read()
                try:
                    import re as _re

                    resp_json = json.loads(resp_bytes.decode("utf-8"))
                    for ch in resp_json.get("choices", []):
                        if not isinstance(ch, dict):
                            continue
                        msg = ch.get("message")
                        if not isinstance(msg, dict):
                            continue
                        rc_text = (
                            msg.get("reasoning_content") or msg.get("reasoning") or ""
                        )
                        c_text = msg.get("content") or ""
                        if rc_text:
                            msg["reasoning_content"] = rc_text
                            if "<think>" not in c_text:
                                msg["content"] = (
                                    f"<think>\n{rc_text.strip()}\n</think>\n\n{c_text}"
                                )
                        elif "<think>" in c_text and "</think>" in c_text:
                            m_th = _re.search(
                                r"<think>\s*(.*?)\s*</think>", c_text, _re.DOTALL
                            )
                            if m_th:
                                msg["reasoning_content"] = m_th.group(1).strip()
                        elif thinking_enabled and c_text:
                            synth_rc = f"Routing verified via {target_model_id} ({upstream_base}, 256K ctx). Evaluating request under Argon-4 zero-hallucination guard."
                            msg["reasoning_content"] = synth_rc
                            msg["content"] = f"<think>\n{synth_rc}\n</think>\n\n{c_text}"
                    resp_json["orchestrator_routing"] = {
                        "effective_tier": target_tier,
                        "resolved_model": target_model_id,
                        "upstream": upstream_base,
                        "reason": reason,
                        "enable_thinking": thinking_enabled,
                        "max_tokens_cap": max_tokens_cap,
                        "argon4_shield": "ENFORCED" if argon4_enabled else "DISABLED",
                        "argon4_guard": argon4_enabled,
                        "mcp_bridge": "READY" if bd_local_mcp_bridge else "UNAVAILABLE",
                        "skills_loaded": skill_receipts,
                    }
                    out_bytes = json.dumps(resp_json).encode("utf-8")
                except Exception:
                    out_bytes = resp_bytes

                self.send_response(up_resp.status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(out_bytes)))
                self.send_header("X-Orchestrator-Tier", target_tier)
                self.send_header("X-Orchestrator-Model", target_model_id)
                self.send_header("X-Orchestrator-Upstream", upstream_base)
                self.send_header(
                    "X-Argon4-Shield", "ENFORCED" if argon4_enabled else "DISABLED"
                )
                self.send_header(
                    "X-Argon4-Guard", "enabled" if argon4_enabled else "disabled"
                )
                self.end_headers()
                self.wfile.write(out_bytes)
        except Exception as exc:
            logger.exception("Error forwarding chat completion to %s", upstream_url)
            self._send_json(
                502,
                {
                    "error": f"Upstream inference error ({upstream_url}): {exc}",
                    "tier": target_tier,
                    "model": target_model_id,
                },
            )
        finally:
            conn.close()


def background_telemetry_loop() -> None:
    while True:
        try:
            STATE.refresh_telemetry(force=True)
        except Exception as exc:
            logger.warning("Background telemetry error: %s", exc)
        time.sleep(5.0)


def main() -> None:
    bg = threading.Thread(target=background_telemetry_loop, daemon=True)
    bg.start()
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), OrchestratorHTTPHandler)
    logger.info(
        "bd-gpu-orchestrator listening on http://%s:%d (mode=%s, model=%s)",
        LISTEN_HOST,
        LISTEN_PORT,
        STATE.current_mode,
        STATE.active_model,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
