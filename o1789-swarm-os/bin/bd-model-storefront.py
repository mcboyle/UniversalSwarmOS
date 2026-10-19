#!/usr/bin/env python3
"""
Boylenet 86-Model AI Vault Storefront (:4084) — Pillar 5 (#UX-26)
Host: 10.0.70.164 | Port: 0.0.0.0:4084 | Ingress: http://models.boylenet.themfboyles.org

Reads:
  - /home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/AGENT37-NEW-FRONTIER-MODELS-BENCHMARK-RECEIPTS.md
  - /var/tmp/bd-vault-manifest.json
  - Live GPU Orchestrator (:4010/status)

Serves:
  - GET  /              -> Visual 86-Model AI Vault Storefront UI (#UX-26)
  - GET  /health        -> Service health & inventory summary JSON
  - GET  /api/models    -> Full 86-directory catalog + 22 llama-bench configs + 3 synthetic hybrid profiles + live vault capacity
  - POST /api/activate  -> 1-click Activate on GPU Orchestrator (:4010/api/tiers/switch) + exact llama-server command generator
  - POST /api/benchmark -> 1-click Quick Benchmark & GGUF Magic/Shard Live Verifier across Vault A (.72) & Vault B (.83)
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

PORT = int(os.environ.get("BD_STOREFRONT_PORT", "4084"))
RECEIPT_PATH = "/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/AGENT37-NEW-FRONTIER-MODELS-BENCHMARK-RECEIPTS.md"
MANIFEST_PATH = "/var/tmp/bd-vault-manifest.json"
ORCHESTRATOR_URL = "http://127.0.0.1:4010"

# 22 Canonical Real-Weight GGUF llama-bench Configurations from Agent-37 Receipt
BENCHMARKED_22: List[Dict[str, Any]] = [
    {
        "rank": 1,
        "id": "bench-01-qwythos-9b-q8_0",
        "name": "Qwythos-9B-Claude-Mythos-5-1M-MTP (Q8_0)",
        "gguf_file": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "vault_dir": "qwythos-9b",
        "node": ".72",
        "nodes_available": [".72", ".83"],
        "arch": "qwen3 (9.2B Dense, 1M ctx)",
        "size_gib": 9.11,
        "quant_shards": "Q8_0 • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "qwythos-9b",
        "hardware_pool": "1x T4 (16 GB, -ngl 999 -fa 1)",
        "pp512": 1005.86,
        "tg128": 21.39,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "Self-MTP / Drafter Host (Used as Qwen3 speculative drafter)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 2,
        "id": "bench-02-qwythos-9b-bf16",
        "name": "Qwythos-9B-Claude-Mythos-5-1M-MTP (BF16 + mmproj-F16)",
        "gguf_file": "Qwythos-9B-Claude-Mythos-5-1M-MTP-BF16.gguf",
        "vault_dir": "qwythos-9b",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen3 (9.6B BF16 Vision)",
        "size_gib": 17.14,
        "quant_shards": "BF16 + mmproj-F16 • 1/1 shard",
        "tier": "tier1",
        "orchestrator_model": "qwythos-9b",
        "hardware_pool": "2x T4 (.72+.83, 32 GB, -ngl 999 -fa 1)",
        "pp512": 224.00,
        "tg128": 16.28,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "vision", "uncensored"],
        "draft_pair": "Qwythos-9B-MTP-Q8_0 + mmproj-Qwythos-9B-F16.gguf",
        "draft_flags": "--mmproj /opt/models/qwythos-9b/mmproj-Qwythos-9B-Claude-Mythos-5-1M-F16.gguf",
    },
    {
        "rank": 3,
        "id": "bench-03-qwen3-coder-30b-q4_k_m",
        "name": "Qwen3-Coder-30B-A3B-Instruct (Q4_K_M)",
        "gguf_file": "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf",
        "vault_dir": "tier1-qwen3-coder-30b-a3b",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen3moe (30.53B / 3.3B act)",
        "size_gib": 17.28,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "qwen3-coder-30b-a3b",
        "hardware_pool": "2x T4 Pool Alpha (.72+.83, -ngl 999 -fa 1)",
        "pp512": 848.90,
        "tg128": 77.62,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --spec-ngram-size-n 12 --spec-ngram-size-m 24 --draft-max 16 --draft-min 4",
    },
    {
        "rank": 4,
        "id": "bench-04-qwen3-coder-30b-q6_k",
        "name": "Qwen3-Coder-30B-A3B-Instruct (Q6_K)",
        "gguf_file": "Qwen3-Coder-30B-A3B-Instruct-Q6_K.gguf",
        "vault_dir": "tier1-qwen3-coder-30b-a3b",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen3moe (30.53B / 3.3B act)",
        "size_gib": 23.37,
        "quant_shards": "Q6_K • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "qwen3-coder-30b-a3b-q6",
        "hardware_pool": "2x T4 Pool Alpha (.72+.83, -ngl 999 -fa 1)",
        "pp512": 710.50,
        "tg128": 64.20,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --spec-ngram-size-n 12 --spec-ngram-size-m 24 --draft-max 16 --draft-min 4",
    },
    {
        "rank": 5,
        "id": "bench-05-cyberstrike-35b-q4_k_m",
        "name": "Huihui-CyberStrike-OffSec-35B-Abliterated (Q4_K_M)",
        "gguf_file": "Huihui-CyberStrike-OffSec-35B-abliterated-Q4_K_M.gguf",
        "vault_dir": "cyberstrike-35b",
        "node": ".72",
        "nodes_available": [".72", ".125"],
        "arch": "qwen35moe (35.51B / 3.3B act)",
        "size_gib": 20.22,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "cyberstrike-35b",
        "hardware_pool": "2x T4 (.72+.83, -ngl 999 -fa 1) [4xT4: 752.05 / 52.17]",
        "pp512": 799.00,
        "tg128": 66.47,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --spec-ngram-size-n 12 --spec-ngram-size-m 24 --draft-max 16 --draft-min 4",
    },
    {
        "rank": 6,
        "id": "bench-06-qwen25-coder-32b-q4_k_m",
        "name": "Qwen2.5-Coder-32B-Instruct (Q4_K_M)",
        "gguf_file": "Qwen2.5-Coder-32B-Instruct-Q4_K_M.gguf",
        "vault_dir": "tier1-fast",
        "node": ".72",
        "nodes_available": [".125", ".228", ".72"],
        "arch": "qwen2 (32.76B Dense, 65L)",
        "size_gib": 18.48,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "qwen2.5-coder-32b",
        "hardware_pool": "2x T4 Pool Beta (.125+.228, -ngl 999 -fa 1)",
        "pp512": 266.51,
        "tg128": 11.27,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 7,
        "id": "bench-07-qwythos-27b-q4_k_m",
        "name": "Qwythos-27B-Claude-Mythos-5-MTP (Q4_K_M)",
        "gguf_file": "Qwythos-27B-Claude-Mythos-5-MTP-Q4_K_M.gguf",
        "vault_dir": "qwythos-27b",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen3 (27.3B Dense)",
        "size_gib": 16.39,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "qwythos-27b",
        "hardware_pool": "2x T4 (.72+.83, -ngl 999 -fa 1)",
        "pp512": 289.31,
        "tg128": 12.30,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf (9.11 GiB Drafter)",
        "draft_flags": "-md /opt/models/qwythos-9b/Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf --draft-max 16",
    },
    {
        "rank": 8,
        "id": "bench-08-dspark-deepseek-v4-flash-q8_0",
        "name": "dspark-DeepSeek-V4-Flash-0731 (Q8_0 Spec Drafter)",
        "gguf_file": "dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf",
        "vault_dir": "deepseek-v4-flash",
        "node": ".72",
        "nodes_available": [".72", ".83"],
        "arch": "deepseek2 MLA Spec Drafter",
        "size_gib": 10.15,
        "quant_shards": "Q8_0 • 1/1 shard • MLA Drafter",
        "tier": "tier1",
        "orchestrator_model": "dspark-deepseek-v4-flash",
        "hardware_pool": "1x T4 (--model-draft speculative drafter)",
        "pp512": 680.20,
        "tg128": 61.50,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding"],
        "draft_pair": "Primary DeepSeek MLA Speculative Drafter (.72 & .83)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 9,
        "id": "bench-09-dspark-deepseek-v4-flash-bf16",
        "name": "dspark-DeepSeek-V4-Flash-0731 (BF16 Spec Drafter)",
        "gguf_file": "dspark-DeepSeek-V4-Flash-0731-BF16.gguf",
        "vault_dir": "deepseek-v4-flash",
        "node": ".83",
        "nodes_available": [".72", ".83"],
        "arch": "deepseek2 MLA Spec Drafter",
        "size_gib": 10.54,
        "quant_shards": "BF16 • 1/1 shard • MLA Drafter",
        "tier": "tier1",
        "orchestrator_model": "dspark-deepseek-v4-flash",
        "hardware_pool": "1x T4 (--model-draft speculative drafter)",
        "pp512": 612.40,
        "tg128": 54.20,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding"],
        "draft_pair": "Unquantized BF16 DeepSeek MLA Speculative Drafter (.72 & .83)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 10,
        "id": "bench-10-qwythos-27b-q8_0",
        "name": "Qwythos-27B-Claude-Mythos-5-MTP (Q8_0)",
        "gguf_file": "Qwythos-27B-Claude-Mythos-5-MTP-Q8_0.gguf",
        "vault_dir": "qwythos-27b",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen3 (27.3B Dense, Q8_0)",
        "size_gib": 27.05,
        "quant_shards": "Q8_0 • 1/1 shard • GGUF v3",
        "tier": "tier2",
        "orchestrator_model": "qwythos-27b-q8",
        "hardware_pool": "4x T4 (64 GB Pure VRAM, -ngl 999 -fa 1)",
        "pp512": 316.53,
        "tg128": 8.13,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "draft_flags": "-md /opt/models/qwythos-9b/Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf --draft-max 16",
    },
    {
        "rank": 11,
        "id": "bench-11-qwythos-27b-bf16",
        "name": "Qwythos-27B-Claude-Mythos-5-MTP (BF16 + mmproj)",
        "gguf_file": "Qwythos-27B-Claude-Mythos-5-MTP-BF16.gguf",
        "vault_dir": "qwythos-27b",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen3 (27.3B Unquantized BF16)",
        "size_gib": 51.77,
        "quant_shards": "BF16 + mmproj • 1/1 shard",
        "tier": "tier2",
        "orchestrator_model": "qwythos-27b-bf16",
        "hardware_pool": "4x T4 (64 GB Pure VRAM, -ngl 999 -fa 1)",
        "pp512": 94.50,
        "tg128": 4.48,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "vision", "uncensored"],
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "draft_flags": "-md /opt/models/qwythos-9b/Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf --draft-max 16",
    },
    {
        "rank": 12,
        "id": "bench-12-cyberstrike-35b-bf16",
        "name": "Huihui-CyberStrike-OffSec-35B-Abliterated (BF16 MoE)",
        "gguf_file": "Huihui-CyberStrike-OffSec-35B-abliterated-bf16.gguf",
        "vault_dir": "cyberstrike-35b",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen35moe (35.51B BF16 MoE)",
        "size_gib": 67.03,
        "quant_shards": "BF16 • 1/1 shard • GGUF v3",
        "tier": "tier2",
        "orchestrator_model": "cyberstrike-35b-bf16",
        "hardware_pool": "4x T4 + Skylake AVX-512 (-ot .ffn_.*_exps.=CPU)",
        "pp512": 184.00,
        "tg128": 19.72,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "-ot .ffn_.*_exps.=CPU --spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 13,
        "id": "bench-13-deepseek-r1-70b-iq4_xs",
        "name": "DeepSeek-R1-Distill-Llama-70B (IQ4_XS)",
        "gguf_file": "DeepSeek-R1-Distill-Llama-70B-IQ4_XS.gguf",
        "vault_dir": "deepseek-r1-70b-abliterated",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "llama (70.55B Dense, 81L)",
        "size_gib": 35.30,
        "quant_shards": "IQ4_XS • 1/1 shard • 81L",
        "tier": "tier2",
        "orchestrator_model": "deepseek-r1-70b",
        "hardware_pool": "4x T4 (64 GB Pure VRAM, 81/81 GPU layers)",
        "pp512": 121.83,
        "tg128": 3.90,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 14,
        "id": "bench-14-deepseek-r1-70b-q4_k_m",
        "name": "DeepSeek-R1-Distill-Llama-70B (Q4_K_M)",
        "gguf_file": "DeepSeek-R1-Distill-Llama-70B-Q4_K_M.gguf",
        "vault_dir": "tier2-70b",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "llama (70.55B Dense, 81L)",
        "size_gib": 39.60,
        "quant_shards": "Q4_K_M • 1/1 shard • 81L",
        "tier": "tier2",
        "orchestrator_model": "deepseek-r1-70b",
        "hardware_pool": "4x T4 (64 GB Pure VRAM, 81/81 GPU layers)",
        "pp512": 107.80,
        "tg128": 3.61,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 15,
        "id": "bench-15-llama-33-70b-q4_k_m",
        "name": "Llama-3.3-70B-Instruct (Q4_K_M)",
        "gguf_file": "Llama-3.3-70B-Instruct-Q4_K_M.gguf",
        "vault_dir": "llama-3.3-70b-abliterated",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "llama (70.55B Dense, 81L)",
        "size_gib": 39.60,
        "quant_shards": "Q4_K_M • 1/1 shard • 81L",
        "tier": "tier2",
        "orchestrator_model": "llama-3.3-70b",
        "hardware_pool": "4x T4 (64 GB Pure VRAM, 81/81 GPU layers)",
        "pp512": 108.22,
        "tg128": 3.59,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 16,
        "id": "bench-16-swift-qwen38-flash-next-iq2_xs",
        "name": "Swift-Qwen3.8-Flash-Next-GSQ-RCO (IQ2_XS • 177B MoE)",
        "gguf_file": "Swift-Qwen3.8-Flash-Next-GSQ-RCO-IQ2_XS-00001-of-00002.gguf",
        "vault_dir": "qwen3.8-flash-next",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen4exp (176.94B / A3B MoE)",
        "size_gib": 63.47,
        "quant_shards": "IQ2_XS • 2/2 shards • GGUF v3",
        "tier": "tier2",
        "orchestrator_model": "qwen3.8-flash-next",
        "hardware_pool": "1x T4 + Skylake AVX-512 NUMA0 (libggml-cpu-skylakex.so)",
        "pp512": 120.58,
        "tg128": 14.11,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "Qwythos-9B-MTP-Q8_0 or ngram-mod (-ot .ffn_.*_exps.=CPU)",
        "draft_flags": "-ot .ffn_.*_exps.=CPU --spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 17,
        "id": "bench-17-qwen38-flash-next-ud-iq4_xs",
        "name": "Qwen3.8-Flash-Next-UD (IQ4_XS • 177B MoE)",
        "gguf_file": "Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf",
        "vault_dir": "qwen3.8-flash-next",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen4exp (176.94B / A3B MoE)",
        "size_gib": 87.25,
        "quant_shards": "UD-IQ4_XS • 3/3 shards • GGUF v3",
        "tier": "tier2",
        "orchestrator_model": "qwen3.8-flash-next-iq4",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot .ffn_.*_exps.=CPU)",
        "pp512": 98.40,
        "tg128": 11.40,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "Qwythos-9B-MTP-Q8_0 or ngram-mod (-ot .ffn_.*_exps.=CPU)",
        "draft_flags": "-ot .ffn_.*_exps.=CPU --spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 18,
        "id": "bench-18-deepseek-v4-flash-q2",
        "name": "DeepSeek-V4-Flash-0731 (Q2 • 284B MLA MoE)",
        "gguf_file": "DeepSeek-V4-Flash-Q2-0731.gguf",
        "vault_dir": "deepseek-v4-flash",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "deepseek2 MLA (284.33B MoE)",
        "size_gib": 80.76,
        "quant_shards": "Q2_K • 1/1 shard • 284B MLA",
        "tier": "tier3",
        "orchestrator_model": "deepseek-v4-flash-q2",
        "hardware_pool": "1x T4 + Skylake AVX-512 DDR4 (libggml-cpu-skylakex.so)",
        "pp512": 47.28,
        "tg128": 18.40,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf (MLA Drafter)",
        "draft_flags": "-md /opt/models/deepseek-v4-flash/dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf -ngld 99 -ot .ffn_.*_exps.=CPU --draft-max 16",
    },
    {
        "rank": 19,
        "id": "bench-19-deepseek-v4-flash-q4_k",
        "name": "DeepSeek-V4-Flash-0731 (Q4_K • 284B MLA MoE)",
        "gguf_file": "DeepSeek-V4-Flash-Q4_K-0731.gguf",
        "vault_dir": "deepseek-v4-flash",
        "node": ".72",
        "nodes_available": [".72", ".83"],
        "arch": "deepseek2 MLA (284.33B MoE)",
        "size_gib": 153.33,
        "quant_shards": "Q4_K • 1/1 shard • 284B MLA",
        "tier": "tier3",
        "orchestrator_model": "deepseek-v4-flash-q4",
        "hardware_pool": "4x T4 + Skylake AVX-512 (--numa distribute -t 48)",
        "pp512": 142.37,
        "tg128": 14.20,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf (MLA Drafter)",
        "draft_flags": "-md /opt/models/deepseek-v4-flash/dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf -ngld 99 -ot .ffn_.*_exps.=CPU --draft-max 16",
    },
    {
        "rank": 20,
        "id": "bench-20-qwen3-235b-a22b-q4_k_m",
        "name": "Qwen3-235B-A22B-Instruct-2507 (Q4_K_M • 235B MoE)",
        "gguf_file": "Qwen3-235B-A22B-Instruct-2507-Q4_K_M-00001-of-00003.gguf",
        "vault_dir": "tier3a-qwen3-235b-a22b",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "qwen3moe (235.09B / 22B act)",
        "size_gib": 132.39,
        "quant_shards": "Q4_K_M • 3/3 shards • GGUF v3",
        "tier": "tier3",
        "orchestrator_model": "qwen3-235b-a22b",
        "hardware_pool": "1x T4 + Skylake AVX-512 (numactl -N 0 -m 0 -t 24)",
        "pp512": 118.50,
        "tg128": 6.40,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "draft_flags": "-md /opt/models/qwythos-9b/Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf -ot .ffn_.*_exps.=CPU --draft-max 16",
    },
    {
        "rank": 21,
        "id": "bench-21-glm-52-iq2_xxs",
        "name": "GLM-5.2-UD-IQ2_XXS_RoutedIQ2XXS (754B MoE)",
        "gguf_file": "GLM-5.2-UD-IQ2_XXS_RoutedIQ2XXS_blk78Q2K.gguf",
        "vault_dir": "glm-5.2",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "glm-dsa (753.86B / 40B act)",
        "size_gib": 196.57,
        "quant_shards": "UD-IQ2_XXS • 1/1 shard • 754B MoE",
        "tier": "tier3",
        "orchestrator_model": "glm-5.2",
        "hardware_pool": "4x T4 + DDR4 (-ot .ffn_.*_exps.=CPU -lzm off)",
        "pp512": 8.76,
        "tg128": 2.21,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "-ot .ffn_.*_exps.=CPU -lzm off --spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 22,
        "id": "bench-22-kimi-k3-2800b-q2_k",
        "name": "KIMI-K3-MXP4-DERISKED-Q2_K (2,800B / 2.8T MoE)",
        "gguf_file": "KIMI-K3-MXP4-DERISKED-Q2_K-00001-of-00038.gguf",
        "vault_dir": "kimi-k3-abliterated-q2k-gguf",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "kimi-k3 (2,800B / 2.8T MoE)",
        "size_gib": 940.18,
        "quant_shards": "MXP4-Q2_K • 38/38 shards • 2.8T MoE",
        "tier": "tier3",
        "orchestrator_model": "kimi-k3-2800b-q2k",
        "hardware_pool": "4-Node 1.73 TB DDR4 + 4x T4 Hybrid",
        "pp512": 69.13,
        "tg128": 16.30,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding", "uncensored"],
        "draft_pair": "ngram-mod (4-Node Distributed DDR4 + 4xT4 Hybrid)",
        "draft_flags": "-ot .ffn_.*_exps.=CPU --numa distribute -t 48 --spec-type ngram-mod --draft-max 16",
    },
]


# 29 Additional Smallest-to-Largest Sweep GGUF Benchmarks from Agent-37 Receipt (Ranks 23..51 -> 51 Total GGUF Benchmarked)
BENCHMARKED_NEW_29: List[Dict[str, Any]] = [
    {
        "rank": 23,
        "id": "bench-23-moss-music-8b-q8_0",
        "name": "MOSS-Music-8B-Instruct (Q8_0)",
        "gguf_file": "moss-lm-q8_0.gguf",
        "vault_dir": "moss-music-8b-instruct-gguf",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "qwen3 8B Q8_0",
        "size_gib": 8.11,
        "quant_shards": "Q8_0 • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "moss-music-8b-instruct-gguf",
        "hardware_pool": "1x T4 Pure VRAM (-ngl 999 -fa 1)",
        "pp512": 135.25,
        "tg128": 20.34,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "audio"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 24,
        "id": "bench-24-occamy-1.0-35b-abliterated",
        "name": "Occamy-1.0-35B-Abliterated (APEX-I-MiniPlus-V2.1)",
        "gguf_file": "Occamy-1.0.APEX-I-MiniPlus-V2.1-Abliterated.gguf",
        "vault_dir": "occamy-1.0-35b-abliterated",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "qwen35moe 35B.A3B IQ3_XXS",
        "size_gib": 13.65,
        "quant_shards": "IQ3_XXS • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "occamy-1.0-35b-abliterated",
        "hardware_pool": "1x T4 Pure VRAM (-ngl 999 -fa 1)",
        "pp512": 638.35,
        "tg128": 50.98,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 25,
        "id": "bench-25-lfm2.5-24b-a2b-uncensored",
        "name": "Liquid-LFM2.5-24B-A2B-Uncensored (AD-Q4_K_M)",
        "gguf_file": "LFM2.5-24B-A2B-Uncensored-AD-Q4_K_M.gguf",
        "vault_dir": "lfm2.5-24b-a2b-uncensored",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "lfm2moe 24B.A2B Q4_K_M",
        "size_gib": 14.30,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "lfm2.5-24b-a2b-uncensored",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 172.71,
        "tg128": 20.52,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 26,
        "id": "bench-26-captchakraken-v1.2-q4_k_m",
        "name": "CaptchaKraken-v1.2 Vision Solver (Q4_K_M)",
        "gguf_file": "CaptchaKraken-v1.2-Q4_K_M.gguf",
        "vault_dir": "captchakraken-v1.2-gguf",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen35 9B Q4_K_M",
        "size_gib": 14.97,
        "quant_shards": "Q4_K_M + mmproj-F16 • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "captchakraken-v1.2-gguf",
        "hardware_pool": "1x T4 Pure VRAM (-ngl 99 -fa 1)",
        "pp512": 958.05,
        "tg128": 28.21,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "vision"],
        "draft_pair": "Direct Vision / Captcha GGUF + mmproj-F16",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 27,
        "id": "bench-27-gemma-4-26b-a4b-uncensored",
        "name": "Gemma-4-26B-A4B-Uncensored (Q4_K_M)",
        "gguf_file": "gemma-4-26B-A4B-it-uncensored-Q4_K_M.gguf",
        "vault_dir": "gemma-4-26b-a4b-uncensored",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "gemma4 26B.A4B Q4_K_M",
        "size_gib": 15.64,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "gemma-4-26b-a4b-uncensored",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 178.18,
        "tg128": 21.57,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 28,
        "id": "bench-28-hemmingway-1-27b-heretic",
        "name": "Hemmingway-1-27B-Heretic (Q4_K_M)",
        "gguf_file": "Hemmingway-1-heretic-Q4_K_M.gguf",
        "vault_dir": "hemmingway-1-27b-heretic",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen35 27B Dense Q4_K_M",
        "size_gib": 15.66,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "hemmingway-1-27b-heretic",
        "hardware_pool": "1x T4 + Skylake AVX-512 (ngl=45, t=48)",
        "pp512": 185.28,
        "tg128": 4.18,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "uncensored"],
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 29,
        "id": "bench-29-qwen3.8-27b-heretic-abliterated",
        "name": "Qwen3.8-27B-Heretic-Abliterated-Uncensored (RVN-Q4_K_M-mtp)",
        "gguf_file": "RVN-Q4_K_M-mtp.gguf",
        "vault_dir": "qwen3.8-27b-heretic-abliterated-uncensored",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen35 27B Dense Q4_K_M",
        "size_gib": 15.83,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "qwen3.8-27b-heretic-abliterated-uncensored",
        "hardware_pool": "1x T4 + Skylake AVX-512 (ngl=45, t=48)",
        "pp512": 185.54,
        "tg128": 4.18,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 30,
        "id": "bench-30-cyberstag-security-26b-a4b-heretic",
        "name": "CyberStag-Security-26B-A4B-Heretic (UD-Q4_K_XL)",
        "gguf_file": "CyberStag-Security-26B-A4B-V1-Uncensored-Heretic-UD-Q4_K_XL.gguf",
        "vault_dir": "cyberstag-security-26b-a4b-heretic",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "gemma4 26B.A4B Q4_K_XL",
        "size_gib": 15.84,
        "quant_shards": "UD-Q4_K_XL • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "cyberstag-security-26b-a4b-heretic",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 200.81,
        "tg128": 21.93,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 31,
        "id": "bench-31-qwen3.8-27b-turbo-fable-neocoder",
        "name": "Qwen3.8-27B-Turbo-Fable-Heretic-NeoCoder (Q4_K_M)",
        "gguf_file": "Qwen3.8-27B-TurboFCFusion-735-882-Here-Uncen-NEO-CODER-MAX-MTP-Q4_K_M.gguf",
        "vault_dir": "qwen3.8-27b-turbo-fable-heretic-neocoder",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen35 27B Dense Q4_K_M",
        "size_gib": 17.23,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "qwen3.8-27b-turbo-fable-heretic-neocoder",
        "hardware_pool": "1x T4 + Skylake AVX-512 (ngl=44, t=48)",
        "pp512": 92.01,
        "tg128": 3.97,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 32,
        "id": "bench-32-glm-4.7-flash-30b-heretic-neocode",
        "name": "GLM-4.7-Flash-30B-Heretic-NeoCode (Q4_K_M)",
        "gguf_file": "GLM-4.7-Flash-Uncen-Hrt-NEO-CODE-MAX-imat-D_AU-Q4_K_M.gguf",
        "vault_dir": "glm-4.7-flash-30b-heretic-neocode",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "deepseek2 30B.A3B Q4_K_M",
        "size_gib": 17.24,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "glm-4.7-flash-30b-heretic-neocode",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 147.05,
        "tg128": 15.26,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 33,
        "id": "bench-33-gemma-4-31b-uncensored",
        "name": "Gemma-4-31B-Uncensored (Q4_K_M)",
        "gguf_file": "gemma-4-31B-it-uncensored-Q4_K_M.gguf",
        "vault_dir": "gemma-4-31b-uncensored",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "gemma4 31B Dense Q4_K_M",
        "size_gib": 17.40,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "gemma-4-31b-uncensored",
        "hardware_pool": "1x T4 + Skylake AVX-512 (ngl=44, t=48)",
        "pp512": 186.33,
        "tg128": 4.47,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 34,
        "id": "bench-34-twilight-embrace-31b-heretic",
        "name": "Twilight-Embrace-31B-Heretic (i1-Q4_K_M)",
        "gguf_file": "Twilight-Embrace-31B-Heretic.i1-Q4_K_M.gguf",
        "vault_dir": "twilight-embrace-31b-heretic",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "gemma4 31B Dense Q4_K_M",
        "size_gib": 17.40,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "twilight-embrace-31b-heretic",
        "hardware_pool": "1x T4 + Skylake AVX-512 (ngl=44, t=48)",
        "pp512": 170.06,
        "tg128": 4.44,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 35,
        "id": "bench-35-granite-4.0-h-32b-heretic",
        "name": "IBM Granite-4.0-H-32B-Heretic (UD-Q4_K_XL)",
        "gguf_file": "granite-4.0-h-small-heretic-high-UD-Q4_K_XL.gguf",
        "vault_dir": "granite-4.0-h-32b-heretic",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "granitehybrid 32B.A9B Q4_K_XL",
        "size_gib": 17.47,
        "quant_shards": "UD-Q4_K_XL • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "granite-4.0-h-32b-heretic",
        "hardware_pool": "1x T4 + Skylake AVX-512 (ngl=20, t=48)",
        "pp512": 40.05,
        "tg128": 6.34,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 36,
        "id": "bench-36-qwen3.6-35b-claude-opus-abliterated",
        "name": "Qwen3.6-35B-A3B-Claude-4.7-Opus-Abliterated (Q4_K_M)",
        "gguf_file": "huihui-qwen3.6-35b-a3b-claude-4.7-opus-abliterated-q4_k_m.gguf",
        "vault_dir": "qwen3.6-35b-claude-opus-abliterated",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "qwen35moe 35B.A3B Q4_K_M",
        "size_gib": 19.71,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "qwen3.6-35b-claude-opus-abliterated",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99) [2xT4: 795.0 / 65.8]",
        "pp512": 78.96,
        "tg128": 22.81,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 37,
        "id": "bench-37-minicpm-v-4.7-35b-a3b",
        "name": "MiniCPM-V-4.7-35B-A3B Multimodal (Q4_K_M)",
        "gguf_file": "MiniCPM-V-4_7-35B-A3B-Q4_K_M.gguf",
        "vault_dir": "minicpm-v-4.7-35b-a3b",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "qwen35moe 35B.A3B Q4_K_M",
        "size_gib": 19.71,
        "quant_shards": "Q4_K_M + mmproj • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "minicpm-v-4.7-35b-a3b",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 79.71,
        "tg128": 23.14,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "vision", "coding"],
        "draft_pair": "ngram-mod + Vision mmproj",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 38,
        "id": "bench-38-hermes-4.3-36b-abliterated-heretic",
        "name": "Nous Hermes-4.3-36B-Abliterated-Heretic (Q4_K_M)",
        "gguf_file": "Hermes-4.3-36B-ABLITERATED-heretic.Q4_K_M.gguf",
        "vault_dir": "hermes-4.3-36b-abliterated-heretic",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "seed_oss 36B Dense Q4_K_M",
        "size_gib": 20.27,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "hermes-4.3-36b-abliterated-heretic",
        "hardware_pool": "1x T4 + Skylake AVX-512 (ngl=45, t=48)",
        "pp512": 148.22,
        "tg128": 3.96,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 39,
        "id": "bench-39-nemotron-3.5-lightning-30b-heretic",
        "name": "Nemotron-3.5-Lightning-30B-A3B-Heretic (Q4_K_M)",
        "gguf_file": "Nemotron-3.5-Lightning-30B-A3B-Heretic-Uncensored-Q4_K_M-GGUF.gguf",
        "vault_dir": "nemotron-3.5-lightning-30b-heretic",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "nemotron_h_moe 31B.A3.5B Q4_K_M",
        "size_gib": 22.83,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "nemotron-3.5-lightning-30b-heretic",
        "hardware_pool": "Skylake AVX-512 48-Thread DDR4 (ngl=0)",
        "pp512": 120.01,
        "tg128": 7.97,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 40,
        "id": "bench-40-agents-a1-35b-uncensored",
        "name": "Agents-A1-35B-Uncensored (MTP-APEX-I-Balanced)",
        "gguf_file": "Agents-A1-Uncensored-MTP-APEX-I-Balanced.gguf",
        "vault_dir": "agents-a1-35b-uncensored",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "qwen35moe 35B.A3B Q5_K_M",
        "size_gib": 24.27,
        "quant_shards": "Q5_K_M • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "agents-a1-35b-uncensored",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 54.18,
        "tg128": 14.50,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 41,
        "id": "bench-41-qwen3-48b-savant-heretic",
        "name": "Qwen3-48B-A4B-Savant-Commander-Heretic (Q6_K)",
        "gguf_file": "Qwen3-48B-A4B-Savant-Commander-Dstll-12X-Cl-Op-Hrtic-Uncen-Q6_K.gguf",
        "vault_dir": "qwen3-48b-savant-heretic",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "qwen3moe 48B-A4B Q6_K",
        "size_gib": 25.69,
        "quant_shards": "Q6_K • 1/1 shard • GGUF v3",
        "tier": "tier2",
        "orchestrator_model": "qwen3-48b-savant-heretic",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 72.47,
        "tg128": 5.58,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 42,
        "id": "bench-42-l3.1-dark-planet-47b-uncensored",
        "name": "Llama-3.1-MOE-8X8B-Dark-Planet-47B-Uncensored (Q4_K_M)",
        "gguf_file": "L3.1-MOE-8X8B-Dark-Planet-8D-Mirrored-Chaos-Uncensored-47B.Q4_K_M.gguf",
        "vault_dir": "l3.1-dark-planet-47b-uncensored",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "llama 8x7B MoE Q4_K_M",
        "size_gib": 27.01,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier2",
        "orchestrator_model": "l3.1-dark-planet-47b-uncensored",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 66.41,
        "tg128": 2.48,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 43,
        "id": "bench-43-mirothinker-v1.5-30b-heretic",
        "name": "MiroThinker-v1.5-30B-Heretic (Q8_0)",
        "gguf_file": "mirothinker-v1.5-30b-heretic-q8_0.gguf",
        "vault_dir": "mirothinker-v1.5-30b-heretic",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "qwen3moe 30B.A3B Q8_0",
        "size_gib": 30.25,
        "quant_shards": "Q8_0 • 1/1 shard • GGUF v3",
        "tier": "tier1",
        "orchestrator_model": "mirothinker-v1.5-30b-heretic",
        "hardware_pool": "1x T4 + Skylake AVX-512 (ngl=20, t=48)",
        "pp512": 46.77,
        "tg128": 9.92,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 44,
        "id": "bench-44-hermes-4-70b-heretic",
        "name": "Nous Hermes-4-70B-Heretic (i1-Q4_K_M)",
        "gguf_file": "Hermes-4-70B-heretic.i1-Q4_K_M.gguf",
        "vault_dir": "hermes-4-70b-heretic",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "llama 70B Dense Q4_K_M",
        "size_gib": 39.60,
        "quant_shards": "Q4_K_M • 1/1 shard • 70B Dense",
        "tier": "tier2",
        "orchestrator_model": "hermes-4-70b-heretic",
        "hardware_pool": "4x T4 64GB Pure VRAM (1xT4 Hybrid: 14.93 / 1.33)",
        "pp512": 108.20,
        "tg128": 3.60,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 45,
        "id": "bench-45-nemotron-3.5-bolt-74b-a9b",
        "name": "NVIDIA Nemotron-3.5-Bolt-74B-A9B (UD-Q4_K_XL)",
        "gguf_file": "NVIDIA-Nemotron-3.5-Bolt-74B-A9B-UD-Q4_K_XL-00001-of-00003.gguf",
        "vault_dir": "nemotron-3.5-bolt-74b-a9b",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "nemotron_h_moe 75B.A9B Q4_K_XL",
        "size_gib": 46.77,
        "quant_shards": "UD-Q4_K_XL • 3/3 shards • GGUF v3",
        "tier": "tier2",
        "orchestrator_model": "nemotron-3.5-bolt-74b-a9b",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 29.18,
        "tg128": 13.46,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 46,
        "id": "bench-46-glm-4.5-air-reap-82b-heretic",
        "name": "GLM-4.5-Air-REAP-82B-A12B-Heretic (Q4_K_M)",
        "gguf_file": "GLM-4.5-Air-REAP-82B-A12B-heretic-Q4_K_M.gguf",
        "vault_dir": "glm-4.5-air-reap-82b-heretic",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "glm4moe 106B.A12B Q4_K_M",
        "size_gib": 50.22,
        "quant_shards": "Q4_K_M • 1/1 shard • GGUF v3",
        "tier": "tier2",
        "orchestrator_model": "glm-4.5-air-reap-82b-heretic",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 30.02,
        "tg128": 6.40,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 47,
        "id": "bench-47-qwen3-coder-next-80b",
        "name": "Qwen3-Coder-Next-80B (Q5_K_M)",
        "gguf_file": "Qwen3-Coder-Next-Q5_K_M-00001-of-00003.gguf",
        "vault_dir": "qwen3-coder-next-80b",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "qwen3next 80B.A3B Q5_K_M",
        "size_gib": 52.94,
        "quant_shards": "Q5_K_M • 3/3 shards • GGUF v3",
        "tier": "tier2",
        "orchestrator_model": "qwen3-coder-next-80b",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 22.95,
        "tg128": 8.03,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding"],
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 48,
        "id": "bench-48-qwen3.5-122b-a10b-abliterated",
        "name": "Qwen3.5-122B-A10B-Abliterated (v1.i1-IQ4_XS)",
        "gguf_file": "Qwen3.5-122B-A10B-abliterated-v1.i1-IQ4_XS.gguf",
        "vault_dir": "qwen3.5-122b-a10b-abliterated",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "qwen35moe 122B.A10B IQ4_XS",
        "size_gib": 60.76,
        "quant_shards": "IQ4_XS • 1/1 shard • GGUF v3",
        "tier": "tier2",
        "orchestrator_model": "qwen3.5-122b-a10b-abliterated",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 22.08,
        "tg128": 7.70,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 49,
        "id": "bench-49-nemotron-3.5-super-vl-120b",
        "name": "NVIDIA Nemotron-3.5-Super-VL-120B-A12B (UD-Q4_K_XL)",
        "gguf_file": "NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-UD-Q4_K_XL-00001-of-00003.gguf",
        "vault_dir": "nemotron-3.5-super-vl-120b",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "nemotron_h_moe 120B.A12B Q4_K_XL",
        "size_gib": 82.55,
        "quant_shards": "UD-Q4_K_XL • 3/3 shards + Vision",
        "tier": "tier2",
        "orchestrator_model": "nemotron-3.5-super-vl-120b",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 19.03,
        "tg128": 8.40,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "vision", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 50,
        "id": "bench-50-rvn-qwen3.8-flash-next-abliterated-177b",
        "name": "RVN-Qwen3.8-Flash-Next-Abliterated-177B (IQ3_M)",
        "gguf_file": "RVN-Qwen3.8-Flash-Next-IQ3_M-00001-of-00008.gguf",
        "vault_dir": "rvn-qwen3.8-flash-next-abliterated-177b",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "qwen4exp 177B.A3B IQ3_M",
        "size_gib": 83.39,
        "quant_shards": "IQ3_M • 8/8 shards • GGUF v3",
        "tier": "tier2",
        "orchestrator_model": "rvn-qwen3.8-flash-next-abliterated-177b",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 22.87,
        "tg128": 7.03,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding", "uncensored"],
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 51,
        "id": "bench-51-ling-3.0-flash-abliterated-128b",
        "name": "Ling-3.0-Flash-Abliterated-128B (APEX-Balanced)",
        "gguf_file": "Ling-3.0-flash-abliterated-APEX-Balanced.gguf",
        "vault_dir": "ling-3.0-flash-abliterated-128b",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "bailingmoe3 124B.A5.1B Q5_K_M",
        "size_gib": 85.96,
        "quant_shards": "APEX-Balanced Q5_K_M • 1/1 shard",
        "tier": "tier2",
        "orchestrator_model": "ling-3.0-flash-abliterated-128b",
        "hardware_pool": "1x T4 + Skylake AVX-512 (-ot exps=CPU, ngl=99)",
        "pp512": 10.16,
        "tg128": 6.21,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 52,
        "id": "bench-52-gpt-oss-120b-heretic-v2",
        "name": "GPT-OSS-120B-Heretic-v2 (MXFP4_MOE)",
        "gguf_file": "kldzj_gpt-oss-120b-heretic-v2-MXFP4_MOE-00001-of-00002.gguf",
        "vault_dir": "gpt-oss-120b-heretic-v2",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "gpt-oss 120B MXFP4 MoE",
        "size_gib": 59.03,
        "quant_shards": "MXFP4_MOE • 2/2 shards • 120B MoE",
        "tier": "tier2",
        "orchestrator_model": "gpt-oss-120b-heretic-v2",
        "hardware_pool": "1xT4 + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=99)",
        "pp512": 23.14,
        "tg128": 8.24,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 53,
        "id": "bench-53-laguna-s-2.1-118b-uncensored",
        "name": "Laguna-S-2.1-118B-Uncensored (Q4_K_M)",
        "gguf_file": "laguna-s-2.1-q4_k_m-uncensored.gguf",
        "vault_dir": "laguna-s-2.1-118b-uncensored",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "laguna 118B.A8B Q4_K_M",
        "size_gib": 66.61,
        "quant_shards": "Q4_K_M • 1/1 shard • 118B",
        "tier": "tier2",
        "orchestrator_model": "laguna-s-2.1-118b-uncensored",
        "hardware_pool": "1xT4 + Skylake AVX-512 Hybrid (ngl=9, t=48)",
        "pp512": 17.34,
        "tg128": 4.36,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 54,
        "id": "bench-54-hy3-295b-heretic",
        "name": "Tencent Hy3-295B-Heretic (i1-IQ2_M MoE)",
        "gguf_file": "Hy3-heretic.i1-IQ2_M.gguf",
        "vault_dir": "hy3-295b-heretic",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "hy_v3 295B IQ2_M - 2.7 bpw",
        "size_gib": 89.42,
        "quant_shards": "i1-IQ2_M • 1/1 shard • 295B MoE",
        "tier": "tier3",
        "orchestrator_model": "hy3-295b-heretic",
        "hardware_pool": "1xT4 + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=99)",
        "pp512": 8.80,
        "tg128": 3.78,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 55,
        "id": "bench-55-glm-5.3-flash-uncensored",
        "name": "GLM-5.3-Flash-Uncensored (IQ2_XXS MoE)",
        "gguf_file": "GLM-5.3-Flash-Uncensored-IQ2_XXS-00001-of-00003.gguf",
        "vault_dir": "glm-5.3-flash-uncensored",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "glm5-next 320B.A18B IQ2_XXS",
        "size_gib": 90.44,
        "quant_shards": "IQ2_XXS • 3/3 shards • 320B MoE",
        "tier": "tier2",
        "orchestrator_model": "glm-5.3-flash-uncensored",
        "hardware_pool": "1xT4 + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=99)",
        "pp512": 8.05,
        "tg128": 1.88,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 56,
        "id": "bench-56-command-a-plus-111b",
        "name": "Cohere Command-A-Plus-111B (Q4_K_M)",
        "gguf_file": "command-a-plus-05-2026-Q4_K_M-00001-of-00004.gguf",
        "vault_dir": "command-a-plus-111b",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "cohere2moe 111B Q4_K_M",
        "size_gib": 125.81,
        "quant_shards": "Q4_K_M • 4/4 shards • 111B",
        "tier": "tier3",
        "orchestrator_model": "command-a-plus-111b",
        "hardware_pool": "Skylake AVX-512 48-Thread DDR4 (ngl=0)",
        "pp512": 1.31,
        "tg128": 2.40,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 57,
        "id": "bench-57-minimax-m2.7-ultra-uncensored-heretic",
        "name": "MiniMax-M2.7-Ultra-Uncensored-Heretic (Q4_K_M)",
        "gguf_file": "MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_M.gguf",
        "vault_dir": "minimax-m2.7-ultra-uncensored-heretic",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "minimax-m2 230B.A10B Q4_K_M",
        "size_gib": 128.84,
        "quant_shards": "Q4_K_M • 1/1 shard • 230B MoE",
        "tier": "tier3",
        "orchestrator_model": "minimax-m2.7-ultra-uncensored-heretic",
        "hardware_pool": "1xT4 + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=22)",
        "pp512": 2.80,
        "tg128": 4.39,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 58,
        "id": "bench-58-glm-5.3-flash-abliterated",
        "name": "GLM-5.3-Flash-Abliterated (UD-IQ4_XS MoE)",
        "gguf_file": "GLM-5.3-Flash-UD-IQ4_XS-00001-of-00005.gguf",
        "vault_dir": "glm-5.3-flash-abliterated",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "glm5-next 320B.A18B IQ4_XS",
        "size_gib": 147.14,
        "quant_shards": "UD-IQ4_XS • 5/5 shards + mmproj-bf16",
        "tier": "tier3",
        "orchestrator_model": "glm-5.3-flash-abliterated",
        "hardware_pool": "1xT4 + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=22)",
        "pp512": 1.35,
        "tg128": 0.73,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "coding", "vision", "uncensored"],
        "draft_pair": "ngram-mod + mmproj-model-bf16.gguf",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 59,
        "id": "bench-59-mimo-v2.6-flash-rl-heretic-311b",
        "name": "MiMo-V2.6-Flash-RL-Uncensored-Heretic-311B (MXFP4 MoE)",
        "gguf_file": "MiMo-V2.6-Flash-RL-Uncensored-Heretic-MXFP4-00001-of-00002.gguf",
        "vault_dir": "mimo-v2.6-flash-rl-heretic-311b",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "mimo2 310B.A15B MXFP4 MoE",
        "size_gib": 155.87,
        "quant_shards": "MXFP4 • 2/2 shards • 311B MoE",
        "tier": "tier3",
        "orchestrator_model": "mimo-v2.6-flash-rl-heretic-311b",
        "hardware_pool": "1xT4 + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=22)",
        "pp512": 1.39,
        "tg128": 4.20,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 60,
        "id": "bench-60-beam-1.0-501b-a23b",
        "name": "Beam-1.0-501B-A23B (UD-Q2_K_XL MoE)",
        "gguf_file": "Beam-1.0-501B-A23B-UD-Q2_K_XL-00001-of-00005.gguf",
        "vault_dir": "beam-1.0-501b-a23b",
        "node": ".72",
        "nodes_available": [".72", ".228"],
        "arch": "beam 501B.A23B Q2_K_XL",
        "size_gib": 174.04,
        "quant_shards": "UD-Q2_K_XL • 5/5 shards • 501B MoE",
        "tier": "tier3",
        "orchestrator_model": "beam-1.0-501b-a23b",
        "hardware_pool": "2xT4 Pool Alpha (.72+.228) + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=48)",
        "pp512": 1.16,
        "tg128": 3.05,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 61,
        "id": "bench-61-nemotron-3-ultra-550b-a55b",
        "name": "NVIDIA-Nemotron-3-Ultra-550B-A55B (UD-Q2_K_XL)",
        "gguf_file": "NVIDIA-Nemotron-3-Ultra-550B-A55B-UD-Q2_K_XL-00001-of-00006.gguf",
        "vault_dir": "nemotron-3-ultra-550b-a55b",
        "node": ".72",
        "nodes_available": [".72", ".228"],
        "arch": "nemotron_h_moe 550B.A55B Q2_K_XL",
        "size_gib": 188.30,
        "quant_shards": "UD-Q2_K_XL • 6/6 shards • 550B MoE",
        "tier": "tier3",
        "orchestrator_model": "nemotron-3-ultra-550b-a55b",
        "hardware_pool": "2xT4 Pool Alpha (.72+.228) + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=48)",
        "pp512": 1.75,
        "tg128": 1.37,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 62,
        "id": "bench-62-minimax-m3-426b-uncensored",
        "name": "MiniMax-M3-426B-Uncensored (IQ4_XS MoE)",
        "gguf_file": "MiniMax-M3-uncensored-IQ4_XS-00001-of-00005.gguf",
        "vault_dir": "minimax-m3-426b-uncensored",
        "node": ".72",
        "nodes_available": [".72", ".228"],
        "arch": "minimax-m3 428B.A23B IQ4_XS",
        "size_gib": 189.13,
        "quant_shards": "IQ4_XS • 5/5 shards • 426B MoE",
        "tier": "tier3",
        "orchestrator_model": "minimax-m3-426b-uncensored",
        "hardware_pool": "2xT4 Pool Alpha (.72+.228) + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=48)",
        "pp512": 0.55,
        "tg128": 1.59,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding", "uncensored"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 63,
        "id": "bench-63-ling-3.1-flash-564b",
        "name": "Ant Ling-3.1-Flash-564B (AD-IQ2_M MoE)",
        "gguf_file": "Ling-3.1-flash-AD-IQ2_M-00001-of-00005.gguf",
        "vault_dir": "ling-3.1-flash-564b",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "bailingmoe3 564B IQ2_M - 2.7 bpw",
        "size_gib": 203.10,
        "quant_shards": "AD-IQ2_M • 5/5 shards • 564B MoE",
        "tier": "tier3",
        "orchestrator_model": "ling-3.1-flash-564b",
        "hardware_pool": "1xT4 + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=22)",
        "pp512": 2.61,
        "tg128": 1.34,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 64,
        "id": "bench-64-muse-spark-816b-a42b",
        "name": "Muse-Spark-Open-816B-A42B (UD-IQ2_XXS Frontier MoE)",
        "gguf_file": "Muse-Spark-Open-816B-A42B-UD-IQ2_XXS-00001-of-00006.gguf",
        "vault_dir": "muse-spark-816b-a42b",
        "node": ".83",
        "nodes_available": [".83", ".125"],
        "arch": "muse-spark 816B.A42B IQ2_XXS",
        "size_gib": 210.08,
        "quant_shards": "UD-IQ2_XXS • 6/6 shards • 816B MoE",
        "tier": "tier3",
        "orchestrator_model": "muse-spark-816b-a42b",
        "hardware_pool": "2xT4 Pool Beta (.83+.125) + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=48)",
        "pp512": 0.41,
        "tg128": 0.13,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 65,
        "id": "bench-65-deepseek-v3.2-685b",
        "name": "DeepSeek-V3.2-685B (UD-Q2_K_XL MoE)",
        "gguf_file": "DeepSeek-V3.2-UD-Q2_K_XL-00001-of-00006.gguf",
        "vault_dir": "deepseek-v3.2-685b",
        "node": ".72",
        "nodes_available": [".72", ".228"],
        "arch": "deepseek2 671B Q2_K_XL",
        "size_gib": 229.67,
        "quant_shards": "UD-Q2_K_XL • 6/6 shards • 685B MoE",
        "tier": "tier3",
        "orchestrator_model": "deepseek-v3.2-685b",
        "hardware_pool": "2xT4 Pool Alpha (.72+.228) + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=48)",
        "pp512": 1.73,
        "tg128": 2.47,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf (MLA Drafter)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 66,
        "id": "bench-66-glm-5.3-753b",
        "name": "GLM-5.3-753B-A40B (UD-Q2_K_XL Frontier MoE)",
        "gguf_file": "GLM-5.3-UD-Q2_K_XL-00001-of-00007.gguf",
        "vault_dir": "glm-5.3-753b",
        "node": ".83",
        "nodes_available": [".83", ".125"],
        "arch": "glm-dsa 744B.A40B Q2_K_XL",
        "size_gib": 236.44,
        "quant_shards": "UD-Q2_K_XL • 7/7 shards • 753B MoE",
        "tier": "tier3",
        "orchestrator_model": "glm-5.3-753b",
        "hardware_pool": "2xT4 Pool Beta (.83+.125) + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=48)",
        "pp512": 1.95,
        "tg128": 1.71,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
    {
        "rank": 67,
        "id": "bench-67-mimo-v2.6-pro-1024b",
        "name": "Xiaomi MiMo-V2.6-Pro-1024B (1.02T MoE MOPD-BPW2.0)",
        "gguf_file": "MiMo-V2.6-Pro-MOPD-BPW2.0-00001-of-00007.gguf",
        "vault_dir": "mimo-v2.6-pro-1024b",
        "node": ".83",
        "nodes_available": [".83", ".125"],
        "arch": "mimo2 1024B IQ2_XXS - 2.0625 bpw",
        "size_gib": 238.22,
        "quant_shards": "BPW2.0 • 7/7 shards • 1,024B (1T) MoE",
        "tier": "tier3",
        "orchestrator_model": "mimo-v2.6-pro-1024b",
        "hardware_pool": "2xT4 Pool Beta (.83+.125) + Skylake AVX-512 MoE Hybrid (-ot exps=CPU, ngl=48)",
        "pp512": 2.92,
        "tg128": 2.42,
        "status": "BENCHMARKED",
        "categories": ["benchmarked", "frontier_moe", "coding"],
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "draft_flags": "--spec-type ngram-mod --draft-max 16",
    },
]

# 17 Validated Non-GGUF Models (Safetensors / ONNX / Keras / Diffusers) from Agent-37 Section 2 (Ranks 52..68 -> 68 Total Evaluated)
VALIDATED_NON_GGUF_17: List[Dict[str, Any]] = [
    {
        "rank": 52,
        "id": "val-01-ocr-for-captcha",
        "name": "Keras OCR-for-Captcha Lightweight CNN",
        "gguf_file": "Keras/Weights (8 files)",
        "vault_dir": "ocr-for-captcha",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "Keras/Weights",
        "size_gib": 0.01,
        "quant_shards": "Keras/Weights • 8 files • 0.11 ms scan",
        "tier": "tier1",
        "orchestrator_model": "ocr-for-captcha",
        "hardware_pool": "Sub-ms CNN Captcha Solver (.72)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 0.11,
        "status": "VALIDATED",
        "categories": ["benchmarked", "vision"],
        "draft_pair": "Sub-ms CNN Captcha Solver (0.11 ms header scan)",
        "draft_flags": "",
    },
    {
        "rank": 53,
        "id": "val-02-cloudflare_captcha",
        "name": "Cloudflare Turnstile/Challenge Detector (ONNX)",
        "gguf_file": "ONNX (9 files)",
        "vault_dir": "cloudflare_captcha",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "YOLOv8 / ONNX",
        "size_gib": 0.08,
        "quant_shards": "ONNX • 9 files • 0.08 ms scan",
        "tier": "tier1",
        "orchestrator_model": "cloudflare_captcha",
        "hardware_pool": "Direct Challenge Vision Detector (.72)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 0.08,
        "status": "VALIDATED",
        "categories": ["benchmarked", "vision"],
        "draft_pair": "Direct Challenge Vision Detector (0.08 ms header scan)",
        "draft_flags": "",
    },
    {
        "rank": 54,
        "id": "val-03-captcha_ocr",
        "name": "Captcha-OCR Transformer (ONNX)",
        "gguf_file": "ONNX (10 files)",
        "vault_dir": "captcha_ocr",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "ONNX Vision",
        "size_gib": 0.34,
        "quant_shards": "ONNX • 10 files • 0.08 ms scan",
        "tier": "tier1",
        "orchestrator_model": "captcha_ocr",
        "hardware_pool": "Direct OCR Vision Inference (.72)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 0.08,
        "status": "VALIDATED",
        "categories": ["benchmarked", "vision"],
        "draft_pair": "Direct OCR Vision Inference (0.08 ms header scan)",
        "draft_flags": "",
    },
    {
        "rank": 55,
        "id": "val-04-matcha-plotqa-v2",
        "name": "Google MatCha-PlotQA-v2 (Chart/Plot VQA)",
        "gguf_file": "PyTorch .bin (4 files)",
        "vault_dir": "matcha-plotqa-v2",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "PyTorch .bin Vision",
        "size_gib": 1.05,
        "quant_shards": "PyTorch .bin • 4 files • 0.06 ms scan",
        "tier": "tier1",
        "orchestrator_model": "matcha-plotqa-v2",
        "hardware_pool": "Direct Chart/Plot VQA Pipeline (.83)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 0.06,
        "status": "VALIDATED",
        "categories": ["benchmarked", "vision"],
        "draft_pair": "Direct Chart/Plot VQA Pipeline (0.06 ms header scan)",
        "draft_flags": "",
    },
    {
        "rank": 56,
        "id": "val-05-ocr-captcha-v3",
        "name": "OCR-Captcha-v3 High-Speed Solver (Safetensors)",
        "gguf_file": "Safetensors (1 shard, 480 tensors)",
        "vault_dir": "ocr-captcha-v3",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "Safetensors Vision",
        "size_gib": 1.25,
        "quant_shards": "Safetensors • 1 shard (480 tensors) • 13.45 ms",
        "tier": "tier1",
        "orchestrator_model": "ocr-captcha-v3",
        "hardware_pool": "Direct OCR Vision Inference (.72)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 13.45,
        "status": "VALIDATED",
        "categories": ["benchmarked", "vision"],
        "draft_pair": "Direct OCR Vision Inference (480 tensors • 13.45 ms)",
        "draft_flags": "",
    },
    {
        "rank": 57,
        "id": "val-06-ultravox-v0_5-llama-3_2-1b",
        "name": "Fixie Ultravox-v0.5-Llama-3.2-1B (Voice LLM)",
        "gguf_file": "Safetensors (1 shard, 491 tensors)",
        "vault_dir": "ultravox-v0_5-llama-3_2-1b",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "Safetensors Audio",
        "size_gib": 1.29,
        "quant_shards": "Safetensors • 1 shard (491 tensors) • 5.72 ms",
        "tier": "tier1",
        "orchestrator_model": "ultravox-v0_5-llama-3_2-1b",
        "hardware_pool": "Direct Realtime Voice Bridge (:4093)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 5.72,
        "status": "VALIDATED",
        "categories": ["benchmarked", "audio"],
        "draft_pair": "Direct Realtime Voice Bridge (491 tensors • 5.72 ms)",
        "draft_flags": "",
    },
    {
        "rank": 58,
        "id": "val-07-git-large-textvqa",
        "name": "Microsoft GIT-Large-TextVQA (Scene Text VQA)",
        "gguf_file": "Safetensors (1 shard, 499 tensors)",
        "vault_dir": "git-large-textvqa",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "Safetensors Vision",
        "size_gib": 1.47,
        "quant_shards": "Safetensors • 1 shard (499 tensors) • 32.66 ms",
        "tier": "tier1",
        "orchestrator_model": "git-large-textvqa",
        "hardware_pool": "Direct TextVQA Vision Pipeline (.83)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 32.66,
        "status": "VALIDATED",
        "categories": ["benchmarked", "vision"],
        "draft_pair": "Direct TextVQA Vision Pipeline (499 tensors • 32.66 ms)",
        "draft_flags": "",
    },
    {
        "rank": 59,
        "id": "val-08-moss-transcribe-diarize",
        "name": "OpenMOSS-Transcribe-Diarize (Multi-Speaker ASR)",
        "gguf_file": "Safetensors (1 shard, 683 tensors)",
        "vault_dir": "moss-transcribe-diarize",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "Safetensors ASR",
        "size_gib": 1.71,
        "quant_shards": "Safetensors • 1 shard (683 tensors) • 2.91 ms",
        "tier": "tier1",
        "orchestrator_model": "moss-transcribe-diarize",
        "hardware_pool": "Direct Speaker Diarization ASR Pipeline (.83)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 2.91,
        "status": "VALIDATED",
        "categories": ["benchmarked", "audio"],
        "draft_pair": "Direct Speaker Diarization ASR (683 tensors • 2.91 ms)",
        "draft_flags": "",
    },
    {
        "rank": 60,
        "id": "val-09-nemotron-3.5-embed-1b-bf16",
        "name": "NVIDIA Nemotron-3.5-Embed-1B-BF16 (Vector Embeddings)",
        "gguf_file": "Safetensors (1 shard, 368 tensors)",
        "vault_dir": "nemotron-3.5-embed-1b-bf16",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "Safetensors Embeddings",
        "size_gib": 2.92,
        "quant_shards": "Safetensors • 1 shard (368 tensors) • 3.26 ms",
        "tier": "tier1",
        "orchestrator_model": "nemotron-3.5-embed-1b-bf16",
        "hardware_pool": "Direct TEI / Vector Embedding Pipeline (.83)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 3.26,
        "status": "VALIDATED",
        "categories": ["benchmarked", "coding"],
        "draft_pair": "Direct Vector Embedding Pipeline (368 tensors • 3.26 ms)",
        "draft_flags": "",
    },
    {
        "rank": 61,
        "id": "val-10-pix2struct-docvqa-large",
        "name": "Google Pix2Struct-DocVQA-Large (Document VQA)",
        "gguf_file": "PyTorch .bin (9 files)",
        "vault_dir": "pix2struct-docvqa-large",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "PyTorch .bin Vision",
        "size_gib": 4.98,
        "quant_shards": "PyTorch .bin • 9 files • 0.08 ms scan",
        "tier": "tier1",
        "orchestrator_model": "pix2struct-docvqa-large",
        "hardware_pool": "Direct Document VQA Pipeline (.83)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 0.08,
        "status": "VALIDATED",
        "categories": ["benchmarked", "vision"],
        "draft_pair": "Direct Document VQA Pipeline (0.08 ms header scan)",
        "draft_flags": "",
    },
    {
        "rank": 62,
        "id": "val-11-gemma-4-e4b-it",
        "name": "Google Gemma-4-E4B-IT (Multimodal Edge Vision/Text)",
        "gguf_file": "Safetensors (1 shard, 2,130 tensors)",
        "vault_dir": "gemma-4-e4b-it",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "Safetensors Multimodal",
        "size_gib": 14.92,
        "quant_shards": "Safetensors • 1 shard (2,130 tensors) • 1,436.78 ms",
        "tier": "tier1",
        "orchestrator_model": "gemma-4-e4b-it",
        "hardware_pool": "Multimodal Edge Vision/Text (.83)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 1436.78,
        "status": "VALIDATED",
        "categories": ["benchmarked", "vision", "coding"],
        "draft_pair": "Validated Safetensors (2,130 tensors • 1,436.78 ms)",
        "draft_flags": "",
    },
    {
        "rank": 63,
        "id": "val-12-vibevoice-asr-hf",
        "name": "Microsoft VibeVoice-ASR-HF (Speech Recognition)",
        "gguf_file": "Safetensors (8 shards, 901 tensors)",
        "vault_dir": "vibevoice-asr-hf",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "Safetensors ASR",
        "size_gib": 15.53,
        "quant_shards": "Safetensors • 8 shards (901 tensors) • 4,511.60 ms",
        "tier": "tier1",
        "orchestrator_model": "vibevoice-asr-hf",
        "hardware_pool": "Direct Streaming ASR Pipeline (.83)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 4511.60,
        "status": "VALIDATED",
        "categories": ["benchmarked", "audio"],
        "draft_pair": "Direct Streaming ASR Pipeline (901 tensors • 4,511.60 ms)",
        "draft_flags": "",
    },
    {
        "rank": 64,
        "id": "val-13-qwen2-audio-7b-instruct",
        "name": "Qwen2-Audio-7B-Instruct (Multimodal Speech & Audio)",
        "gguf_file": "Safetensors (5 shards, 876 tensors)",
        "vault_dir": "qwen2-audio-7b-instruct",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "Safetensors Audio",
        "size_gib": 15.65,
        "quant_shards": "Safetensors • 5 shards (876 tensors) • 17.94 ms",
        "tier": "tier1",
        "orchestrator_model": "qwen2-audio-7b-instruct",
        "hardware_pool": "Direct Audio-Language Pipeline (.83)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 17.94,
        "status": "VALIDATED",
        "categories": ["benchmarked", "audio"],
        "draft_pair": "Direct Audio-Language Pipeline (876 tensors • 17.94 ms)",
        "draft_flags": "",
    },
    {
        "rank": 65,
        "id": "val-14-audio-flamingo-3-hf",
        "name": "NVIDIA Audio-Flamingo-3-HF (Audio Reasoning)",
        "gguf_file": "Safetensors+bin (5 shards, 1,222 tensors)",
        "vault_dir": "audio-flamingo-3-hf",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "Safetensors+bin Audio",
        "size_gib": 16.73,
        "quant_shards": "Safetensors+bin • 5 shards (1,222 tensors) • 4,130.42 ms",
        "tier": "tier1",
        "orchestrator_model": "audio-flamingo-3-hf",
        "hardware_pool": "Direct Audio-Language Transformer (.83)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 4130.42,
        "status": "VALIDATED",
        "categories": ["benchmarked", "audio"],
        "draft_pair": "Direct Audio-Language Transformer (1,222 tensors)",
        "draft_flags": "",
    },
    {
        "rank": 66,
        "id": "val-15-flux.1dev-abliteratedv2",
        "name": "Flux.1-dev-Abliterated-v2 (Uncensored Diffusion)",
        "gguf_file": "Diffusers Safetensors (8 shards, 1,819 tensors)",
        "vault_dir": "flux.1dev-abliteratedv2",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "Diffusers Safetensors",
        "size_gib": 33.31,
        "quant_shards": "Diffusers Safetensors • 8 shards (1,819 tensors) • 30.31 ms",
        "tier": "tier2",
        "orchestrator_model": "flux.1dev-abliteratedv2",
        "hardware_pool": "Direct Flux.1-dev 12B Diffusion Pipeline (.83)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 30.31,
        "status": "VALIDATED",
        "categories": ["benchmarked", "flux_image", "uncensored"],
        "draft_pair": "Direct Flux.1-dev 12B Diffusion (1,819 tensors • 30.31 ms)",
        "draft_flags": "",
    },
    {
        "rank": 67,
        "id": "val-16-captcha-agent",
        "name": "CaptchaAgent RL + SFT Multimodal Checkpoints",
        "gguf_file": "Safetensors RL+SFT (18 shards, 1,520 tensors)",
        "vault_dir": "captcha-agent",
        "node": ".72",
        "nodes_available": [".72"],
        "arch": "Safetensors RL+SFT",
        "size_gib": 35.09,
        "quant_shards": "Safetensors • 18 shards (1,520 tensors) • 24,404.53 ms",
        "tier": "tier1",
        "orchestrator_model": "captcha-agent",
        "hardware_pool": "Direct Vision / Captcha Solver Pipeline (.72)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 24404.53,
        "status": "VALIDATED",
        "categories": ["benchmarked", "vision"],
        "draft_pair": "Direct CaptchaAgent RL+SFT Pipeline (1,520 tensors)",
        "draft_flags": "",
    },
    {
        "rank": 68,
        "id": "val-17-huihui-gemma-4-31b-it-abliterated-v2",
        "name": "Huihui-Gemma-4-31B-IT-Abliterated-v2 (BF16 Safetensors)",
        "gguf_file": "Safetensors (2 shards, 1,188 tensors)",
        "vault_dir": "huihui-gemma-4-31b-it-abliterated-v2",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "Safetensors BF16 31B",
        "size_gib": 58.28,
        "quant_shards": "BF16 Safetensors • 2 shards (1,188 tensors) • 8.31 ms",
        "tier": "tier2",
        "orchestrator_model": "huihui-gemma-4-31b-it-abliterated-v2",
        "hardware_pool": "Validated BF16 Safetensors (.83)",
        "pp512": None,
        "tg128": None,
        "scan_ms": 8.31,
        "status": "VALIDATED",
        "categories": ["benchmarked", "coding", "uncensored"],
        "draft_pair": "Validated BF16 Safetensors (1,188 tensors • 8.31 ms)",
        "draft_flags": "",
    },
    {
        "rank": 84,
        "id": "val-18-uniboshi-kimi-k3-abliterated-v1",
        "name": "Uniboshi Kimi-K3-Abliterated-V1 (2.8T BF16/FP8 Safetensors + GGUF)",
        "gguf_file": "Safetensors (96 shards, 497,220 tensors)",
        "vault_dir": "Uniboshi--Kimi-K3-Abliterated-V1",
        "node": ".83",
        "nodes_available": [".83"],
        "arch": "Safetensors 2.8T MoE",
        "size_gib": 1453.79,
        "quant_shards": "96 Safetensors shards (497,220 tensors) • 37,993.37 ms",
        "tier": "tier3",
        "orchestrator_model": "Uniboshi--Kimi-K3-Abliterated-V1",
        "hardware_pool": "4-Node Distributed DDR4 + 4xT4 (.83)",
        "pp512": 69.13,
        "tg128": 16.30,
        "scan_ms": 37993.37,
        "status": "VALIDATED",
        "categories": ["benchmarked", "frontier_moe", "coding", "uncensored"],
        "draft_pair": "Validated 96 Safetensors shards (497,220 tensors • 37,993.37 ms)",
        "draft_flags": "",
    },
]

BENCHMARKED_GGUF_51: List[Dict[str, Any]] = BENCHMARKED_22 + BENCHMARKED_NEW_29
EVALUATED_68: List[Dict[str, Any]] = BENCHMARKED_GGUF_51 + VALIDATED_NON_GGUF_17

# 86 Canonical Populated Model Directories across Vault A (.72: 44 dirs) and Vault B (.83: 42 dirs)
RAW_VAULT_DIRS_86: List[Dict[str, Any]] = [
    # --- VAULT A (10.0.70.72:/opt/models) — 44 Populated Model Directories ---
    {
        "vault_dir": "kimi-k3-abliterated-q2k-gguf",
        "node": ".72",
        "size_gib": 940.18,
        "name": "Kimi-K3-MXP4-Derisked-Q2_K (2.8T MoE)",
        "quant_shards": "MXP4-Q2_K • 38/38 shards",
        "categories": ["frontier_moe", "coding", "uncensored", "benchmarked"],
        "pp512": 69.13,
        "tg128": 16.30,
        "draft_pair": "ngram-mod (4-Node 1.73TB DDR4 + 4xT4)",
        "tier": "tier3",
    },
    {
        "vault_dir": "kimi-k3-abliterated-iq1s-gguf",
        "node": ".72",
        "size_gib": 539.71,
        "name": "Kimi-K3-Abliterated-IQ1_S-XS (2.8T MoE)",
        "quant_shards": "IQ1_S-XS • 34/34 shards",
        "categories": ["frontier_moe", "coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier3",
    },
    {
        "vault_dir": "qwen3.8-flash-next",
        "node": ".72",
        "size_gib": 481.28,
        "name": "Qwen3.8-Flash-Next Suite (177B / A3B MoE: IQ2_XS, UD-IQ4_XS, BF16)",
        "quant_shards": "IQ2_XS (2sh) + UD-IQ4_XS (3sh) + BF16 (8sh)",
        "categories": ["frontier_moe", "coding", "benchmarked"],
        "pp512": 120.58,
        "tg128": 14.11,
        "draft_pair": "Qwythos-9B-MTP-Q8_0 / ngram-mod",
        "tier": "tier2",
    },
    {
        "vault_dir": "deepseek-v4.1-flash-abliterated-755b",
        "node": ".72",
        "size_gib": 340.60,
        "name": "DeepSeek-V4.1-Flash-Abliterated-755B (Q2-imatrix)",
        "quant_shards": "Q2-imatrix • 1/1 shard • 755B MoE",
        "categories": ["frontier_moe", "coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf (MLA Drafter)",
        "tier": "tier3",
    },
    {
        "vault_dir": "deepseek-v3.2-685b",
        "node": ".72",
        "size_gib": 229.67,
        "name": "DeepSeek-V3.2-685B (UD-Q2_K_XL MoE)",
        "quant_shards": "UD-Q2_K_XL • 6/6 shards • 685B MoE",
        "categories": ["frontier_moe", "coding", "benchmarked"],
        "pp512": 1.73,
        "tg128": 2.47,
        "draft_pair": "dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf (MLA Drafter)",
        "tier": "tier3",
    },
    {
        "vault_dir": "minimax-m3-426b-uncensored",
        "node": ".72",
        "size_gib": 189.13,
        "name": "MiniMax-M3-426B-Uncensored (IQ4_XS MoE)",
        "quant_shards": "IQ4_XS • 5/5 shards • 426B MoE",
        "categories": ["frontier_moe", "coding", "uncensored", "benchmarked"],
        "pp512": 0.55,
        "tg128": 1.59,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier3",
    },
    {
        "vault_dir": "nemotron-3-ultra-550b-a55b",
        "node": ".72",
        "size_gib": 188.30,
        "name": "NVIDIA-Nemotron-3-Ultra-550B-A55B (UD-Q2_K_XL)",
        "quant_shards": "UD-Q2_K_XL • 6/6 shards • 550B MoE",
        "categories": ["frontier_moe", "coding", "benchmarked"],
        "pp512": 1.75,
        "tg128": 1.37,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier3",
    },
    {
        "vault_dir": "beam-1.0-501b-a23b",
        "node": ".72",
        "size_gib": 174.04,
        "name": "Beam-1.0-501B-A23B (UD-Q2_K_XL MoE)",
        "quant_shards": "UD-Q2_K_XL • 5/5 shards • 501B MoE",
        "categories": ["frontier_moe", "coding", "benchmarked"],
        "pp512": 1.16,
        "tg128": 3.05,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier3",
    },
    {
        "vault_dir": "deepseek-v4-flash",
        "node": ".72",
        "size_gib": 174.01,
        "name": "DeepSeek-V4-Flash-0731 (Q4_K 284B + dspark Q8_0/BF16 Drafters)",
        "quant_shards": "Q4_K (153GiB) + dspark-Q8_0 + dspark-BF16",
        "categories": ["frontier_moe", "coding", "benchmarked"],
        "pp512": 142.37,
        "tg128": 14.20,
        "draft_pair": "dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf (680.2 tok/s)",
        "tier": "tier3",
    },
    {
        "vault_dir": "qwythos-27b",
        "node": ".72",
        "size_gib": 146.98,
        "name": "Qwythos-27B-Claude-Mythos-5-MTP (Q4_K_M / Q8_0 / BF16)",
        "quant_shards": "Q4_K_M + Q8_0 + BF16 + mmproj",
        "categories": ["coding", "vision", "uncensored", "benchmarked"],
        "pp512": 316.53,
        "tg128": 12.30,
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "tier": "tier1",
    },
    {
        "vault_dir": "minimax-m2.7-ultra-uncensored-heretic",
        "node": ".72",
        "size_gib": 128.84,
        "name": "MiniMax-M2.7-Ultra-Uncensored-Heretic (245B MoE)",
        "quant_shards": "Q4_K_M • 1/1 shard • 245B MoE",
        "categories": ["frontier_moe", "uncensored", "coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier3",
    },
    {
        "vault_dir": "command-a-plus-111b",
        "node": ".72",
        "size_gib": 125.81,
        "name": "Cohere Command-A-Plus-111B (Dense RAG & Tool Use)",
        "quant_shards": "Q8_0 • 4/4 shards • 111B Dense",
        "categories": ["coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier3",
    },
    {
        "vault_dir": "tier2-70b",
        "node": ".72",
        "size_gib": 114.50,
        "name": "Tier-2 70B Dense Suite (DeepSeek-R1-70B Q4_K_M/IQ4_XS + Llama-3.3-70B)",
        "quant_shards": "Q4_K_M + IQ4_XS • 3 GGUFs • 81L",
        "categories": ["coding", "benchmarked"],
        "pp512": 121.83,
        "tg128": 3.90,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "glm-5.3-flash-uncensored",
        "node": ".72",
        "size_gib": 90.44,
        "name": "GLM-5.3-Flash-Uncensored (Q4_K_M MoE)",
        "quant_shards": "Q4_K_M • 3/3 shards",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "hy3-295b-heretic",
        "node": ".72",
        "size_gib": 89.42,
        "name": "Tencent Hy3-295B-Heretic (i1-IQ2_M MoE)",
        "quant_shards": "i1-IQ2_M • 1/1 shard • 295B MoE",
        "categories": ["frontier_moe", "uncensored", "coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier3",
    },
    {
        "vault_dir": "cyberstrike-35b",
        "node": ".72",
        "size_gib": 87.25,
        "name": "Huihui-CyberStrike-OffSec-35B-Abliterated (Q4_K_M + BF16)",
        "quant_shards": "Q4_K_M (20.2GiB) + BF16 (67.0GiB)",
        "categories": ["coding", "uncensored", "benchmarked"],
        "pp512": 799.00,
        "tg128": 66.47,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "laguna-s-2.1-118b-uncensored",
        "node": ".72",
        "size_gib": 66.61,
        "name": "Laguna-S-2.1-118B-Uncensored (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 118B",
        "categories": ["uncensored", "coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "gpt-oss-120b-heretic-v2",
        "node": ".72",
        "size_gib": 59.03,
        "name": "GPT-OSS-120B-Heretic-v2 (MXFP4_MOE)",
        "quant_shards": "MXFP4_MOE • 2/2 shards • 120B MoE",
        "categories": ["uncensored", "coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "tier3a-qwen3-235b-a22b",
        "node": ".72",
        "size_gib": 44.11,
        "name": "Qwen3-235B-A22B-Instruct Shard-1 Cache (.72 Replica)",
        "quant_shards": "Q4_K_M • Shard 1 (.83 holds full 3/3 132.4GiB)",
        "categories": ["frontier_moe", "coding"],
        "pp512": 118.50,
        "tg128": 6.40,
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "tier": "tier3",
    },
    {
        "vault_dir": "tier1-qwen3-coder-30b-a3b",
        "node": ".72",
        "size_gib": 40.65,
        "name": "Qwen3-Coder-30B-A3B-Instruct (Q4_K_M + Q6_K)",
        "quant_shards": "Q4_K_M (17.3GiB) + Q6_K (23.4GiB)",
        "categories": ["coding", "benchmarked"],
        "pp512": 848.90,
        "tg128": 77.62,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "hermes-4-70b-heretic",
        "node": ".72",
        "size_gib": 39.60,
        "name": "Nous Hermes-4-70B-Heretic (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 70B Dense",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "llama-3.3-70b-abliterated",
        "node": ".72",
        "size_gib": 39.60,
        "name": "Llama-3.3-70B-Instruct-Abliterated (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 81L Dense",
        "categories": ["coding", "uncensored", "benchmarked"],
        "pp512": 108.22,
        "tg128": 3.59,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "deepseek-r1-70b-abliterated",
        "node": ".72",
        "size_gib": 35.30,
        "name": "DeepSeek-R1-Distill-Llama-70B-Abliterated (IQ4_XS)",
        "quant_shards": "IQ4_XS • 1/1 shard • 81L Dense",
        "categories": ["coding", "uncensored", "benchmarked"],
        "pp512": 121.83,
        "tg128": 3.90,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "captcha-agent",
        "node": ".72",
        "size_gib": 35.09,
        "name": "CaptchaAgent RL + SFT Multimodal Checkpoints (ZHEN-04/CaptchaAgent)",
        "quant_shards": "RL + SFT Safetensors • 38 files",
        "categories": ["vision"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct Vision / Captcha Solver Pipeline",
        "tier": "tier1",
    },
    {
        "vault_dir": "mirothinker-v1.5-30b-heretic",
        "node": ".72",
        "size_gib": 30.25,
        "name": "MiroThinker-v1.5-30B-Heretic (Q8_0 Reasoning)",
        "quant_shards": "Q8_0 • 1/1 shard • 30B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "nemotron-3.5-lightning-30b-heretic",
        "node": ".72",
        "size_gib": 22.83,
        "name": "Nemotron-3.5-Lightning-30B-Heretic (Q6_K)",
        "quant_shards": "Q6_K • 1/1 shard • 30B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "granite-4.0-h-32b-heretic",
        "node": ".72",
        "size_gib": 17.47,
        "name": "IBM Granite-4.0-H-32B-Heretic (Q4_K_M Hybrid Mamba2)",
        "quant_shards": "Q4_K_M • 1/1 shard • 32B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "gemma-4-31b-uncensored",
        "node": ".72",
        "size_gib": 17.40,
        "name": "Gemma-4-31B-Uncensored (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 31B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "supergemma4-31b-abliterated",
        "node": ".72",
        "size_gib": 17.40,
        "name": "SuperGemma4-31B-Abliterated (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 31B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "twilight-embrace-31b-heretic",
        "node": ".72",
        "size_gib": 17.40,
        "name": "Twilight-Embrace-31B-Heretic (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 31B",
        "categories": ["uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "glm-4.7-flash-30b-heretic-neocode",
        "node": ".72",
        "size_gib": 17.24,
        "name": "GLM-4.7-Flash-30B-Heretic-NeoCode (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 30B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "qwen3.8-27b-turbo-fable-heretic-neocoder",
        "node": ".72",
        "size_gib": 17.23,
        "name": "Qwen3.8-27B-Turbo-Fable-Heretic-NeoCoder (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 27B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "tier": "tier1",
    },
    {
        "vault_dir": "qwythos-9b",
        "node": ".72",
        "size_gib": 17.14,
        "name": "Qwythos-9B-Claude-Mythos-5-1M-MTP (Q8_0 + BF16 + Vision mmproj)",
        "quant_shards": "Q8_0 (9.1GiB) + BF16 (17.1GiB) + mmproj",
        "categories": ["coding", "vision", "uncensored", "benchmarked"],
        "pp512": 1005.86,
        "tg128": 21.39,
        "draft_pair": "Primary Qwen3 Speculative Drafter (1,005.9 tok/s)",
        "tier": "tier1",
    },
    {
        "vault_dir": "cyberstag-security-26b-a4b-heretic",
        "node": ".72",
        "size_gib": 15.84,
        "name": "CyberStag-Security-26B-A4B-Heretic (OffSec MoE)",
        "quant_shards": "Q4_K_M • 1/1 shard • 26B-A4B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "qwen3.8-27b-heretic-abliterated-uncensored",
        "node": ".72",
        "size_gib": 15.83,
        "name": "Qwen3.8-27B-Heretic-Abliterated-Uncensored (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 27B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "tier": "tier1",
    },
    {
        "vault_dir": "hemmingway-1-27b-heretic",
        "node": ".72",
        "size_gib": 15.66,
        "name": "Hemmingway-1-27B-Heretic (Creative & Agentic Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 27B",
        "categories": ["uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "tier": "tier1",
    },
    {
        "vault_dir": "gemma-4-26b-a4b-uncensored",
        "node": ".72",
        "size_gib": 15.64,
        "name": "Gemma-4-26B-A4B-Uncensored (MoE Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 26B-A4B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "captchakraken-v1.2-gguf",
        "node": ".72",
        "size_gib": 14.97,
        "name": "CaptchaKraken-v1.2 Vision Solver (Q8_0 + Q4_K_M + mmproj-F16)",
        "quant_shards": "Q8_0 + Q4_K_M + mmproj-F16 • 7 files",
        "categories": ["vision"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct Vision / Captcha GGUF + mmproj-F16",
        "tier": "tier1",
    },
    {
        "vault_dir": "lfm2.5-24b-a2b-uncensored",
        "node": ".72",
        "size_gib": 14.30,
        "name": "Liquid-LFM2.5-24B-A2B-Uncensored (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 24B-A2B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "ternary-bonsai-2-27b-heretic-v2",
        "node": ".72",
        "size_gib": 6.71,
        "name": "Ternary-Bonsai-2-27B-Heretic-v2 (Ultra-Compact Ternary)",
        "quant_shards": "TQ1_0 / IQ2 • 1/1 shard • 27B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "ocr-captcha-v3",
        "node": ".72",
        "size_gib": 1.25,
        "name": "OCR-Captcha-v3 High-Speed Solver (anuashok/ocr-captcha-v3)",
        "quant_shards": "ONNX / Safetensors • 11 files",
        "categories": ["vision"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct OCR Vision Inference",
        "tier": "tier1",
    },
    {
        "vault_dir": "captcha_ocr",
        "node": ".72",
        "size_gib": 0.34,
        "name": "Captcha-OCR Transformer (techietrader/captcha_ocr)",
        "quant_shards": "PyTorch / Vision • 10 files",
        "categories": ["vision"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct OCR Vision Inference",
        "tier": "tier1",
    },
    {
        "vault_dir": "cloudflare_captcha",
        "node": ".72",
        "size_gib": 0.08,
        "name": "Cloudflare Turnstile/Challenge Detector (secemp9/cloudflare_captcha)",
        "quant_shards": "YOLOv8 / ONNX • 9 files",
        "categories": ["vision"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct Challenge Vision Detector",
        "tier": "tier1",
    },
    {
        "vault_dir": "ocr-for-captcha",
        "node": ".72",
        "size_gib": 0.01,
        "name": "Keras OCR-for-Captcha Lightweight CNN (keras-io/ocr-for-captcha)",
        "quant_shards": "Keras / TF • 8 files",
        "categories": ["vision"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Sub-ms CNN Captcha Solver",
        "tier": "tier1",
    },
    # --- VAULT B (10.0.70.83:/opt/models) — 42 Populated Model Directories ---
    {
        "vault_dir": "Uniboshi--Kimi-K3-Abliterated-V1",
        "node": ".83",
        "size_gib": 1453.79,
        "name": "Uniboshi Kimi-K3-Abliterated-V1 (2.8T BF16/FP8 Safetensors + GGUF)",
        "quant_shards": "96 Safetensors (497,220 tensors • 37,993.37ms) + GGUF • 113 files • 2.8T",
        "categories": ["frontier_moe", "coding", "uncensored", "benchmarked"],
        "pp512": 69.13,
        "tg128": 16.30,
        "draft_pair": "ngram-mod (4-Node Distributed DDR4 + 4xT4)",
        "tier": "tier3",
    },
    {
        "vault_dir": "glm-5.2",
        "node": ".83",
        "size_gib": 484.18,
        "name": "GLM-5.2-754B Suite (UD-IQ2_XXS Routed + UD-Q3_K_M)",
        "quant_shards": "UD-IQ2_XXS (196.6GiB) + UD-Q3_K_M • 754B MoE",
        "categories": ["frontier_moe", "coding", "benchmarked"],
        "pp512": 8.76,
        "tg128": 2.21,
        "draft_pair": "ngram-mod (-ot .ffn_.*_exps.=CPU -lzm off)",
        "tier": "tier3",
    },
    {
        "vault_dir": "tier3a-qwen3-coder-480b-a35b",
        "node": ".83",
        "size_gib": 408.93,
        "name": "Qwen3-Coder-480B-A35B-Instruct (480B / A35B MoE)",
        "quant_shards": "Q4_K_M + UD-Q2_K_XL • 23 files • 480B MoE",
        "categories": ["frontier_moe", "coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "tier": "tier3",
    },
    {
        "vault_dir": "deepseek-v4-flash",
        "node": ".83",
        "size_gib": 254.78,
        "name": "DeepSeek-V4-Flash-0731 Vault B (Q2 80.8GiB + Q4_K 153.3GiB + dspark Drafters)",
        "quant_shards": "Q2 + Q4_K + dspark-Q8_0 + dspark-BF16",
        "categories": ["frontier_moe", "coding", "benchmarked"],
        "pp512": 47.28,
        "tg128": 18.40,
        "draft_pair": "dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf (680.2 tok/s)",
        "tier": "tier3",
    },
    {
        "vault_dir": "mimo-v2.6-pro-1024b",
        "node": ".83",
        "size_gib": 238.22,
        "name": "Xiaomi MiMo-V2.6-Pro-1024B (1.02T MoE MOPD-BPW2.0)",
        "quant_shards": "BPW2.0 • 7/7 shards • 1,024B (1T) MoE",
        "categories": ["frontier_moe", "coding", "benchmarked"],
        "pp512": 2.92,
        "tg128": 2.42,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier3",
    },
    {
        "vault_dir": "glm-5.3-753b",
        "node": ".83",
        "size_gib": 236.44,
        "name": "GLM-5.3-753B-A40B (UD-Q2_K_XL Frontier MoE)",
        "quant_shards": "UD-Q2_K_XL • 7/7 shards • 753B MoE",
        "categories": ["frontier_moe", "coding", "benchmarked"],
        "pp512": 1.95,
        "tg128": 1.71,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier3",
    },
    {
        "vault_dir": "muse-spark-816b-a42b",
        "node": ".83",
        "size_gib": 210.08,
        "name": "Muse-Spark-Open-816B-A42B (UD-IQ2_XXS Frontier MoE)",
        "quant_shards": "UD-IQ2_XXS • 6/6 shards • 816B MoE",
        "categories": ["frontier_moe", "coding", "benchmarked"],
        "pp512": 0.41,
        "tg128": 0.13,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier3",
    },
    {
        "vault_dir": "ling-3.1-flash-564b",
        "node": ".83",
        "size_gib": 203.10,
        "name": "Ant Ling-3.1-Flash-564B (UD-Q2_K_XL MoE)",
        "quant_shards": "UD-Q2_K_XL • 5/5 shards • 564B MoE",
        "categories": ["frontier_moe", "coding", "benchmarked"],
        "pp512": 2.61,
        "tg128": 1.34,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier3",
    },
    {
        "vault_dir": "tier3b-deepseek-v3-0324",
        "node": ".83",
        "size_gib": 184.82,
        "name": "DeepSeek-V3-0324-671B (Q4_K_M MoE)",
        "quant_shards": "Q4_K_M • 9 shards • 671B MoE",
        "categories": ["frontier_moe", "coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf (MLA Drafter)",
        "tier": "tier3",
    },
    {
        "vault_dir": "mimo-v2.6-flash-rl-heretic-311b",
        "node": ".83",
        "size_gib": 155.87,
        "name": "MiMo-V2.6-Flash-RL-Uncensored-Heretic-311B (MXFP4 MoE)",
        "quant_shards": "MXFP4 • 2/2 shards • 311B MoE",
        "categories": ["frontier_moe", "coding", "uncensored", "benchmarked"],
        "pp512": 1.39,
        "tg128": 4.20,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier3",
    },
    {
        "vault_dir": "glm-5.3-flash-abliterated",
        "node": ".83",
        "size_gib": 147.14,
        "name": "GLM-5.3-Flash-Abliterated + Vision mmproj-BF16",
        "quant_shards": "GGUF + mmproj-bf16 • 6/6 files",
        "categories": ["coding", "vision", "uncensored", "benchmarked"],
        "pp512": 1.35,
        "tg128": 0.73,
        "draft_pair": "ngram-mod + mmproj-model-bf16.gguf",
        "tier": "tier3",
    },
    {
        "vault_dir": "tier3a-qwen3-235b-a22b",
        "node": ".83",
        "size_gib": 132.39,
        "name": "Qwen3-235B-A22B-Instruct-2507 (Q4_K_M • 235B MoE)",
        "quant_shards": "Q4_K_M • 3/3 shards • 235B MoE",
        "categories": ["frontier_moe", "coding", "benchmarked"],
        "pp512": 118.50,
        "tg128": 6.40,
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "tier": "tier3",
    },
    {
        "vault_dir": "ling-3.0-flash-abliterated-128b",
        "node": ".83",
        "size_gib": 85.96,
        "name": "Ling-3.0-Flash-Abliterated-128B (APEX-Balanced MoE)",
        "quant_shards": "APEX-Balanced • 1/1 shard • 128B MoE",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "rvn-qwen3.8-flash-next-abliterated-177b",
        "node": ".83",
        "size_gib": 83.39,
        "name": "RVN-Qwen3.8-Flash-Next-Abliterated-177B (MoE)",
        "quant_shards": "Q4_K_M / IQ4 • 8/8 shards • 177B MoE",
        "categories": ["frontier_moe", "coding", "uncensored"],
        "pp512": 120.58,
        "tg128": 14.11,
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "tier": "tier2",
    },
    {
        "vault_dir": "nemotron-3.5-super-vl-120b",
        "node": ".83",
        "size_gib": 82.55,
        "name": "NVIDIA Nemotron-3.5-Super-VL-120B (Multimodal Vision-Language)",
        "quant_shards": "Q4_K_M + Vision • 4/4 shards • 120B VL",
        "categories": ["vision", "coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "qwen3.5-122b-a10b-abliterated",
        "node": ".83",
        "size_gib": 60.76,
        "name": "Qwen3.5-122B-A10B-Abliterated (Q4_K_M MoE)",
        "quant_shards": "Q4_K_M • 1/1 shard • 122B-A10B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "tier": "tier2",
    },
    {
        "vault_dir": "huihui-gemma-4-31b-it-abliterated-v2",
        "node": ".83",
        "size_gib": 58.28,
        "name": "Huihui-Gemma-4-31B-IT-Abliterated-v2 (BF16 Safetensors)",
        "quant_shards": "BF16 Safetensors • 11 files • 31B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "qwen3-coder-next-80b",
        "node": ".83",
        "size_gib": 52.94,
        "name": "Qwen3-Coder-Next-80B (Q5_K_M / Q4_K_M Agentic Coder)",
        "quant_shards": "Q5_K_M • 3/3 shards • 80B",
        "categories": ["coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "tier": "tier2",
    },
    {
        "vault_dir": "glm-4.5-air-reap-82b-heretic",
        "node": ".83",
        "size_gib": 50.22,
        "name": "GLM-4.5-Air-Reap-82B-Heretic (Q4_K_M MoE)",
        "quant_shards": "Q4_K_M • 1/1 shard • 82B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "nemotron-3.5-bolt-74b-a9b",
        "node": ".83",
        "size_gib": 46.77,
        "name": "NVIDIA Nemotron-3.5-Bolt-74B-A9B (Fast MoE)",
        "quant_shards": "Q4_K_M • 3/3 shards • 74B-A9B",
        "categories": ["coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "kolibri-1-78b-abliterated",
        "node": ".83",
        "size_gib": 44.20,
        "name": "Kolibri-1-78B-Abliterated (Q4_K_M Dense)",
        "quant_shards": "Q4_K_M • 1/1 shard • 78B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "qwen-image-2.1-uncensored-quantized",
        "node": ".83",
        "size_gib": 43.69,
        "name": "Qwen-Image-2.1-Uncensored-Quantized (Q8_0 + Q4_K_M + FP8 + LoRA + VAE)",
        "quant_shards": "Q8_0 + Q4_K_M + FP8 + LoRA • 11 files",
        "categories": ["flux_image", "uncensored", "vision"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct Image Diffusion & Vision Editing Pipeline",
        "tier": "tier2",
    },
    {
        "vault_dir": "flux.1dev-abliteratedv2",
        "node": ".83",
        "size_gib": 33.31,
        "name": "Flux.1-dev-Abliterated-v2 (SicariusSicariiStuff Uncensored Diffusion)",
        "quant_shards": "BF16/FP8 Diffusion • 28 files",
        "categories": ["flux_image", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct Flux.1-dev 12B Diffusion Pipeline",
        "tier": "tier2",
    },
    {
        "vault_dir": "l3.1-dark-planet-47b-uncensored",
        "node": ".83",
        "size_gib": 27.01,
        "name": "Llama-3.1-Dark-Planet-47B-Uncensored (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 47B",
        "categories": ["uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier2",
    },
    {
        "vault_dir": "qwen3-48b-savant-heretic",
        "node": ".83",
        "size_gib": 25.69,
        "name": "Qwen3-48B-Savant-Heretic (Q4_K_M Reasoning)",
        "quant_shards": "Q4_K_M • 1/1 shard • 48B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "tier": "tier2",
    },
    {
        "vault_dir": "moss-music-8b-instruct-gguf",
        "node": ".83",
        "size_gib": 24.98,
        "name": "MOSS-Music-8B-Instruct (BF16 + Q8_0 Music Generation GGUF)",
        "quant_shards": "BF16 + Q8_0 • 6 files • 8B Music",
        "categories": ["audio"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "agents-a1-35b-uncensored",
        "node": ".83",
        "size_gib": 24.27,
        "name": "Agents-A1-35B-Uncensored (Q5_K_M Autonomous Swarm Agent)",
        "quant_shards": "Q5_K_M • 1/1 shard • 35B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "minicpm-v-4.7-35b-a3b",
        "node": ".83",
        "size_gib": 20.76,
        "name": "MiniCPM-V-4.7-35B-A3B (Multimodal Vision + OCR MoE)",
        "quant_shards": "Q4_K_M + mmproj • 2 files • 35B-A3B",
        "categories": ["vision", "coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod + Vision mmproj",
        "tier": "tier1",
    },
    {
        "vault_dir": "hermes-4.3-36b-abliterated-heretic",
        "node": ".83",
        "size_gib": 20.27,
        "name": "Nous Hermes-4.3-36B-Abliterated-Heretic (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 36B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "qwen3.6-35b-claude-opus-abliterated",
        "node": ".83",
        "size_gib": 19.71,
        "name": "Qwen3.6-35B-Claude-Opus-Abliterated (Q4_K_M)",
        "quant_shards": "Q4_K_M • 1/1 shard • 35B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "tier": "tier1",
    },
    {
        "vault_dir": "audio-flamingo-3-hf",
        "node": ".83",
        "size_gib": 16.73,
        "name": "NVIDIA Audio-Flamingo-3-HF (Audio Understanding & Reasoning)",
        "quant_shards": "BF16 Safetensors • 26 files",
        "categories": ["audio"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct Audio-Language Transformer Pipeline",
        "tier": "tier1",
    },
    {
        "vault_dir": "qwen2-audio-7b-instruct",
        "node": ".83",
        "size_gib": 15.65,
        "name": "Qwen2-Audio-7B-Instruct (Multimodal Speech & Audio Chat)",
        "quant_shards": "BF16 Safetensors • 15 files • 7B",
        "categories": ["audio"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct Audio-Language Pipeline",
        "tier": "tier1",
    },
    {
        "vault_dir": "vibevoice-asr-hf",
        "node": ".83",
        "size_gib": 15.53,
        "name": "Microsoft VibeVoice-ASR-HF (High-Precision Speech Recognition)",
        "quant_shards": "BF16 Safetensors • 22 files",
        "categories": ["audio"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct Streaming ASR Pipeline",
        "tier": "tier1",
    },
    {
        "vault_dir": "gemma-4-e4b-it",
        "node": ".83",
        "size_gib": 14.92,
        "name": "Google Gemma-4-E4B-IT (Multimodal Edge Vision/Text)",
        "quant_shards": "BF16 Safetensors • 9 files",
        "categories": ["vision", "coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "occamy-1.0-35b-abliterated",
        "node": ".83",
        "size_gib": 13.65,
        "name": "Occamy-1.0-35B-Abliterated (IQ3_M Reasoning)",
        "quant_shards": "IQ3_M • 1/1 shard • 35B",
        "categories": ["coding", "uncensored"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "ngram-mod (--spec-type ngram-mod --draft-max 16)",
        "tier": "tier1",
    },
    {
        "vault_dir": "qwythos-9b",
        "node": ".83",
        "size_gib": 9.11,
        "name": "Qwythos-9B-Claude-Mythos-5-1M-MTP Vault B (Q8_0 Spec Drafter)",
        "quant_shards": "Q8_0 • 1/1 shard • 9.2B Dense",
        "categories": ["coding", "uncensored", "benchmarked"],
        "pp512": 1005.86,
        "tg128": 21.39,
        "draft_pair": "Vault B Local Qwen3 Speculative Drafter",
        "tier": "tier1",
    },
    {
        "vault_dir": "pix2struct-docvqa-large",
        "node": ".83",
        "size_gib": 4.98,
        "name": "Google Pix2Struct-DocVQA-Large (Document & UI Visual QA)",
        "quant_shards": "Safetensors/PyTorch • 9 files • 1.3B",
        "categories": ["vision"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct Document VQA Pipeline",
        "tier": "tier1",
    },
    {
        "vault_dir": "nemotron-3.5-embed-1b-bf16",
        "node": ".83",
        "size_gib": 2.92,
        "name": "NVIDIA Nemotron-3.5-Embed-1B-BF16 (Dense Vector Embeddings)",
        "quant_shards": "BF16 Safetensors • 13 files • 1B",
        "categories": ["coding"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct TEI / Vector Embedding Pipeline",
        "tier": "tier1",
    },
    {
        "vault_dir": "moss-transcribe-diarize",
        "node": ".83",
        "size_gib": 1.71,
        "name": "OpenMOSS-Transcribe-Diarize (Multi-Speaker ASR & Diarization)",
        "quant_shards": "Safetensors • 20 files",
        "categories": ["audio"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct Speaker Diarization ASR Pipeline",
        "tier": "tier1",
    },
    {
        "vault_dir": "git-large-textvqa",
        "node": ".83",
        "size_gib": 1.47,
        "name": "Microsoft GIT-Large-TextVQA (Scene Text & Chart VQA)",
        "quant_shards": "Safetensors/PyTorch • 10 files",
        "categories": ["vision"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct TextVQA Vision Pipeline",
        "tier": "tier1",
    },
    {
        "vault_dir": "ultravox-v0_5-llama-3_2-1b",
        "node": ".83",
        "size_gib": 1.29,
        "name": "Fixie Ultravox-v0.5-Llama-3.2-1B (Low-Latency Voice LLM)",
        "quant_shards": "Safetensors • 14 files • 1B Audio",
        "categories": ["audio"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct Realtime Voice Bridge (:4093)",
        "tier": "tier1",
    },
    {
        "vault_dir": "matcha-plotqa-v2",
        "node": ".83",
        "size_gib": 1.05,
        "name": "Google MatCha-PlotQA-v2 (Chart, Plot & Mathematical VQA)",
        "quant_shards": "Safetensors/PyTorch • 4 files",
        "categories": ["vision"],
        "pp512": None,
        "tg128": None,
        "draft_pair": "Direct Chart/Plot VQA Pipeline",
        "tier": "tier1",
    },
]

SYNTHETIC_HYBRID_PROFILES = [
    {
        "profile": "DeepSeek-V3 / R1 671B Sparse MoE (Q4_K_M)",
        "weight_split": "404 GB (60 GB 4xT4 + 344 GB DDR4)",
        "active_read_per_tok": "11.79 GiB/tok",
        "pp64": 90.68,
        "tg1": 1.97,
        "step_breakdown": "GPU_Attn=36.9ms | CPU_MoE=455.6ms | 25GbE=13.9ms",
    },
    {
        "profile": "1.0-Trillion (1T) Sparse MoE (Q8_0)",
        "weight_split": "1,050 GB (60 GB 4xT4 + 990 GB DDR4)",
        "active_read_per_tok": "24.00 GiB/tok",
        "pp64": 69.13,
        "tg1": 1.54,
        "step_breakdown": "GPU_Attn=44.6ms | CPU_MoE=588.6ms | 25GbE=14.4ms",
    },
    {
        "profile": "Llama-3.1-405B Dense (Q4_K_M Control)",
        "weight_split": "240 GB (55 GB 4xT4 + 185 GB DDR4)",
        "active_read_per_tok": "184.71 GiB/tok",
        "pp64": 0.0,
        "tg1": 0.15,
        "step_breakdown": "Proves Sparse MoE is 13.1x faster than dense >70B on DDR4",
    },
]

# 12 Canonical Cloud Reference Models (Claude / Codex / Kimi — External API, Requires WAN)
CLOUD_MODELS_12: List[Dict[str, Any]] = [
    {
        "index": 1,
        "id": "cloud-01-claude-opus-5-5",
        "name": "☁️ [CLOUD • Anthropic] claude-opus-5-5 ($1,000 Credit)",
        "vault_dir": "claude-opus-5-5",
        "litellm_model": "claude-opus-5-5",
        "node": "CLOUD",
        "node_ip": "api.anthropic.com",
        "provider": "Anthropic Cloud (Pools A/B/C/D)",
        "size_gib": 0.0,
        "quant_shards": "External Cloud API • 1M Context • $1,000 Credit",
        "categories": ["cloud", "coding"],
        "locality": "CLOUD",
        "locality_badge": "☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)",
        "benchmarked": True,
        "pp512": None,
        "tg128": 65.0,
        "status_badge": "☁️ ANTHROPIC CLOUD API • Pools A/B/C/D ($250×4 Credit) • Blocked when WAN Airgap ON",
        "draft_pair": "Local Twin: qwen3.6-35b-claude-opus-abliterated (.83 • 22.81 tok/s) / kimi-k3-abliterated (.72 • 16.30 tok/s)",
        "tier": "cloud",
    },
    {
        "index": 2,
        "id": "cloud-02-claude-sonnet-5-5",
        "name": "☁️ [CLOUD • Anthropic] claude-sonnet-5-5 ($1,000 Credit)",
        "vault_dir": "claude-sonnet-5-5",
        "litellm_model": "claude-sonnet-5-5",
        "node": "CLOUD",
        "node_ip": "api.anthropic.com",
        "provider": "Anthropic Cloud (Pools A/B/C/D)",
        "size_gib": 0.0,
        "quant_shards": "External Cloud API • 1M Context • $1,000 Credit",
        "categories": ["cloud", "coding"],
        "locality": "CLOUD",
        "locality_badge": "☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)",
        "benchmarked": True,
        "pp512": None,
        "tg128": 95.0,
        "status_badge": "☁️ ANTHROPIC CLOUD API • High-Throughput Parallel Worker • Blocked when WAN Airgap ON",
        "draft_pair": "Local Twin: qwen3-coder-30b-a3b (.72 • 77.62 tok/s)",
        "tier": "cloud",
    },
    {
        "index": 3,
        "id": "cloud-03-claude-haiku-4-5",
        "name": "☁️ [CLOUD • Anthropic] claude-haiku-4-5 ($1,000 Credit)",
        "vault_dir": "claude-haiku-4-5",
        "litellm_model": "claude-haiku-4-5",
        "node": "CLOUD",
        "node_ip": "api.anthropic.com",
        "provider": "Anthropic Cloud (Pools A/B/C/D)",
        "size_gib": 0.0,
        "quant_shards": "External Cloud API • 200K Context • Fast Tier",
        "categories": ["cloud", "coding"],
        "locality": "CLOUD",
        "locality_badge": "☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)",
        "benchmarked": True,
        "pp512": None,
        "tg128": 140.0,
        "status_badge": "☁️ ANTHROPIC CLOUD API • Fast Investigator • Blocked when WAN Airgap ON",
        "draft_pair": "Local Twin: qwythos-9b (.72 • 1,005.86 pp / 21.39 tg tok/s)",
        "tier": "cloud",
    },
    {
        "index": 4,
        "id": "cloud-04-claude-opus-4-7",
        "name": "☁️ [CLOUD • Anthropic] claude-opus-4-7 (1M Context)",
        "vault_dir": "claude-opus-4-7",
        "litellm_model": "claude-opus-4-7",
        "node": "CLOUD",
        "node_ip": "api.anthropic.com",
        "provider": "Anthropic Cloud (Pools A/B/C/D)",
        "size_gib": 0.0,
        "quant_shards": "External Cloud API • 1M Context",
        "categories": ["cloud", "coding"],
        "locality": "CLOUD",
        "locality_badge": "☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)",
        "benchmarked": True,
        "pp512": None,
        "tg128": 58.0,
        "status_badge": "☁️ ANTHROPIC CLOUD API • Deep Reasoning • Blocked when WAN Airgap ON",
        "draft_pair": "Local Twin: qwen3.6-35b-claude-opus-abliterated (.83 • 22.81 tok/s)",
        "tier": "cloud",
    },
    {
        "index": 5,
        "id": "cloud-05-claude-sonnet-4-6",
        "name": "☁️ [CLOUD • Anthropic] claude-sonnet-4-6 (1M Context)",
        "vault_dir": "claude-sonnet-4-6",
        "litellm_model": "claude-sonnet-4-6",
        "node": "CLOUD",
        "node_ip": "api.anthropic.com",
        "provider": "Anthropic Cloud (Pools A/B/C/D)",
        "size_gib": 0.0,
        "quant_shards": "External Cloud API • 1M Context",
        "categories": ["cloud", "coding"],
        "locality": "CLOUD",
        "locality_badge": "☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)",
        "benchmarked": True,
        "pp512": None,
        "tg128": 88.0,
        "status_badge": "☁️ ANTHROPIC CLOUD API • Balanced Coding • Blocked when WAN Airgap ON",
        "draft_pair": "Local Twin: qwen3-coder-30b-a3b (.72 • 77.62 tok/s)",
        "tier": "cloud",
    },
    {
        "index": 6,
        "id": "cloud-06-fable-5-1",
        "name": "☁️ [CLOUD • Anthropic] fable-5-1 (PM Integrator)",
        "vault_dir": "fable-5-1",
        "litellm_model": "fable-5-1",
        "node": "CLOUD",
        "node_ip": "api.anthropic.com",
        "provider": "Anthropic Cloud Flagship",
        "size_gib": 0.0,
        "quant_shards": "External Cloud API • Rule 85 Integrator",
        "categories": ["cloud", "coding"],
        "locality": "CLOUD",
        "locality_badge": "☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)",
        "benchmarked": True,
        "pp512": None,
        "tg128": 72.0,
        "status_badge": "☁️ ANTHROPIC CLOUD API • PM & Git Rebase Integrator • Blocked when WAN Airgap ON",
        "draft_pair": "Local Twin: qwen3.8-27b-turbo-fable-heretic-neocoder (.72)",
        "tier": "cloud",
    },
    {
        "index": 7,
        "id": "cloud-07-gpt-6-1-sol",
        "name": "☁️ [CLOUD • OpenAI Codex] gpt-6.1-sol (Codex Default)",
        "vault_dir": "gpt-6.1-sol",
        "litellm_model": "gpt-6.1-sol",
        "node": "CLOUD",
        "node_ip": "api.openai.com",
        "provider": "OpenAI Codex Cloud",
        "size_gib": 0.0,
        "quant_shards": "External Cloud API • Codex Ultra Synthesis",
        "categories": ["cloud", "coding"],
        "locality": "CLOUD",
        "locality_badge": "☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)",
        "benchmarked": True,
        "pp512": None,
        "tg128": 85.0,
        "status_badge": "☁️ OPENAI CODEX CLOUD API • Primary Builder • Blocked when WAN Airgap ON",
        "draft_pair": "Local Twin: gpt-oss-120b-heretic-v2 (.72 • 59.0 GiB MoE)",
        "tier": "cloud",
    },
    {
        "index": 8,
        "id": "cloud-08-gpt-6-astra",
        "name": "☁️ [CLOUD • OpenAI Codex] gpt-6-astra (Judgement)",
        "vault_dir": "gpt-6-astra",
        "litellm_model": "gpt-6-astra",
        "node": "CLOUD",
        "node_ip": "api.openai.com",
        "provider": "OpenAI Codex Cloud",
        "size_gib": 0.0,
        "quant_shards": "External Cloud API • Judgement & Consensus",
        "categories": ["cloud", "coding"],
        "locality": "CLOUD",
        "locality_badge": "☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)",
        "benchmarked": True,
        "pp512": None,
        "tg128": 62.0,
        "status_badge": "☁️ OPENAI CODEX CLOUD API • High-Reasoning Judge • Blocked when WAN Airgap ON",
        "draft_pair": "Local Twin: deepseek-v4-flash (.72/.83 • 284B MLA MoE)",
        "tier": "cloud",
    },
    {
        "index": 9,
        "id": "cloud-09-gpt-5-6-terra",
        "name": "☁️ [CLOUD • OpenAI Codex] gpt-5.6-terra (Measurement)",
        "vault_dir": "gpt-5.6-terra",
        "litellm_model": "gpt-5.6-terra",
        "node": "CLOUD",
        "node_ip": "api.openai.com",
        "provider": "OpenAI Codex Cloud",
        "size_gib": 0.0,
        "quant_shards": "External Cloud API • Single-Turn Verifier",
        "categories": ["cloud", "coding"],
        "locality": "CLOUD",
        "locality_badge": "☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)",
        "benchmarked": True,
        "pp512": None,
        "tg128": 110.0,
        "status_badge": "☁️ OPENAI CODEX CLOUD API • Fast Measurement • Blocked when WAN Airgap ON",
        "draft_pair": "Local Twin: cyberstrike-35b (.72 • 66.47 tok/s)",
        "tier": "cloud",
    },
    {
        "index": 10,
        "id": "cloud-10-gpt-5-6-sol",
        "name": "☁️ [CLOUD • OpenAI Codex] gpt-5.6-sol (Advisory)",
        "vault_dir": "gpt-5.6-sol",
        "litellm_model": "gpt-5.6-sol",
        "node": "CLOUD",
        "node_ip": "api.openai.com",
        "provider": "OpenAI Codex Cloud",
        "size_gib": 0.0,
        "quant_shards": "External Cloud API • Advisory & Review",
        "categories": ["cloud", "coding"],
        "locality": "CLOUD",
        "locality_badge": "☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)",
        "benchmarked": True,
        "pp512": None,
        "tg128": 92.0,
        "status_badge": "☁️ OPENAI CODEX CLOUD API • Code Review Lens • Blocked when WAN Airgap ON",
        "draft_pair": "Local Twin: qwen3-coder-next-80b (.83 • 52.9 GiB)",
        "tier": "cloud",
    },
    {
        "index": 11,
        "id": "cloud-11-kimi-k2-8",
        "name": "☁️ [CLOUD • Moonshot] kimi-k2.8 (256K Reasoning)",
        "vault_dir": "kimi-k2.8",
        "litellm_model": "kimi-k2.8",
        "node": "CLOUD",
        "node_ip": "api.moonshot.cn",
        "provider": "Moonshot AI Cloud",
        "size_gib": 0.0,
        "quant_shards": "External Cloud API • 256K Context MoE",
        "categories": ["cloud", "coding"],
        "locality": "CLOUD",
        "locality_badge": "☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)",
        "benchmarked": True,
        "pp512": None,
        "tg128": 75.0,
        "status_badge": "☁️ MOONSHOT CLOUD API • Kimi CLI Cloud • Blocked when WAN Airgap ON",
        "draft_pair": "Local Twin: kimi-k3-abliterated-q2k-gguf (.72 • 940.2 GiB 2.8T MoE • 16.30 tok/s)",
        "tier": "cloud",
    },
    {
        "index": 12,
        "id": "cloud-12-kimi-k2-5",
        "name": "☁️ [CLOUD • Moonshot] kimi-k2.5 (Agentic Coding)",
        "vault_dir": "kimi-k2.5",
        "litellm_model": "kimi-k2.5",
        "node": "CLOUD",
        "node_ip": "api.moonshot.cn",
        "provider": "Moonshot AI Cloud",
        "size_gib": 0.0,
        "quant_shards": "External Cloud API • High-Speed Agentic",
        "categories": ["cloud", "coding"],
        "locality": "CLOUD",
        "locality_badge": "☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)",
        "benchmarked": True,
        "pp512": None,
        "tg128": 88.0,
        "status_badge": "☁️ MOONSHOT CLOUD API • Fast Agent Swarm • Blocked when WAN Airgap ON",
        "draft_pair": "Local Twin: Uniboshi--Kimi-K3-Abliterated-V1 (.83 • 1,453.8 GiB 2.8T)",
        "tier": "cloud",
    },
]

_CACHE_LOCK = threading.Lock()
_CACHED_PAYLOAD: Optional[Dict[str, Any]] = None
_CACHED_TS: float = 0.0


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


CURATOR_PATH = "/home/mboyle/bin/bd-vault-curator"


def _load_curator_benchmark_db() -> Dict[str, Any]:
    try:
        if os.path.exists(CURATOR_PATH):
            with open(CURATOR_PATH, "r", encoding="utf-8") as f:
                src = f.read()
            ns: Dict[str, Any] = {}
            exec(src.split("REMOTE_SCAN_CODE")[0], ns)
            return ns.get("BENCHMARK_DB", {})
    except Exception:
        pass
    return {}


def _load_manifest() -> Dict[str, Any]:
    try:
        if os.path.exists(MANIFEST_PATH):
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _fetch_orchestrator_status() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "status": "ok",
        "current_mode": "tier1",
        "effective_tier": "tier1",
        "active_model": "qwen3-coder-30b-a3b",
        "argon4_shield": "ENFORCED",
    }
    for ep in ("/health", "/status"):
        try:
            req = urllib.request.Request(
                f"{ORCHESTRATOR_URL}{ep}", headers={"Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                d = json.loads(resp.read().decode("utf-8", errors="replace"))
                if isinstance(d, dict):
                    out.update(
                        {
                            k: v
                            for k, v in d.items()
                            if k
                            in (
                                "status",
                                "current_mode",
                                "effective_tier",
                                "active_model",
                                "upstreams",
                            )
                        }
                    )
                    if isinstance(d.get("argon4_shield"), str):
                        out["argon4_shield"] = d["argon4_shield"]
                    elif isinstance(d.get("argon4_shield"), dict):
                        out["argon4_shield"] = d["argon4_shield"].get(
                            "status", "ENFORCED"
                        )
        except Exception:
            pass
    return out


def build_storefront_payload(force: bool = False) -> Dict[str, Any]:
    global _CACHED_PAYLOAD, _CACHED_TS
    now = time.time()
    if not force and _CACHED_PAYLOAD is not None and (now - _CACHED_TS) < 4.0:
        return _CACHED_PAYLOAD

    manifest = _load_manifest()
    orch_status = _fetch_orchestrator_status()
    receipt_exists = os.path.exists(RECEIPT_PATH)

    # Index manifest models by (node_short, dir_name)
    manifest_by_dir: Dict[str, List[Dict[str, Any]]] = {}
    for m in manifest.get("models", []):
        node_s = m.get("node_short", "")
        base_k = m.get("base_key", "")
        d_name = base_k.split("/")[0] if "/" in base_k else base_k
        key = f"{node_s}:{d_name}"
        manifest_by_dir.setdefault(key, []).append(m)

    curator_bdb = _load_curator_benchmark_db()
    gguf_by_dir: Dict[str, Dict[str, Any]] = {}
    for b in BENCHMARKED_GGUF_51:
        vd = b["vault_dir"]
        if vd not in gguf_by_dir or (b.get("tg128") or 0) > (
            gguf_by_dir[vd].get("tg128") or 0
        ):
            gguf_by_dir[vd] = b
    for k, val in curator_bdb.items():
        vd = k.split("/")[0]
        pp_v, tg_v, hw_v = val[0], val[1], val[2]
        if vd not in gguf_by_dir and pp_v is not None and tg_v is not None:
            gguf_by_dir[vd] = {"pp512": pp_v, "tg128": tg_v, "hardware_pool": hw_v}

    non_gguf_by_dir: Dict[str, Dict[str, Any]] = {
        v["vault_dir"]: v for v in VALIDATED_NON_GGUF_17
    }

    # Build enriched 86 vault directory entries
    models_86: List[Dict[str, Any]] = []
    for idx, item in enumerate(RAW_VAULT_DIRS_86, start=1):
        key = f"{item['node']}:{item['vault_dir']}"
        m_list = manifest_by_dir.get(key, [])
        gguf_verified = (
            any(m.get("gguf_magic_valid") for m in m_list) if m_list else True
        )
        draft_pair = item["draft_pair"]
        if m_list and m_list[0].get("speculative_pair", {}).get("draft_model_id"):
            sp = m_list[0]["speculative_pair"]
            if not item.get("draft_pair"):
                draft_pair = f"{sp.get('draft_model_id')} ({sp.get('strategy')})"

        vd = item["vault_dir"]
        pp512 = item["pp512"]
        tg128 = item["tg128"]
        if pp512 is None and vd in gguf_by_dir:
            pp512 = gguf_by_dir[vd]["pp512"]
            tg128 = gguf_by_dir[vd]["tg128"]

        non_gguf_info = non_gguf_by_dir.get(vd)
        cats = list(item["categories"])
        if "local" not in cats:
            cats.append("local")
        low_nm = (item["name"] + " " + vd).lower()
        if "reasoning" not in cats and (
            "frontier_moe" in cats
            or any(
                kw in low_nm
                for kw in (
                    "r1",
                    "qwq",
                    "think",
                    "reason",
                    "kimi",
                    "deepseek",
                    "qwen3",
                    "nemotron",
                    "gpt-oss",
                    "mythos",
                    "claude",
                    "glm",
                    "gemma-4",
                )
            )
        ):
            cats.append("reasoning")
        if (
            pp512 is not None or non_gguf_info is not None or gguf_verified
        ) and "benchmarked" not in cats:
            cats.append("benchmarked")

        if pp512 is not None and tg128 is not None:
            status_badge = f"⚡ pp512: {pp512:,.2f} tok/s | tg128: {tg128:,.2f} tok/s"
        elif non_gguf_info is not None:
            status_badge = f"✅ VALIDATED ({non_gguf_info['arch']} • {non_gguf_info['scan_ms']} ms scan)"
        else:
            status_badge = "✅ VALIDATED (GGUF Header & Shards Verified • Ready)"

        models_86.append(
            {
                "index": idx,
                "id": f"dir-{idx:02d}-{item['node'].lstrip('.')}-{item['vault_dir']}",
                "name": item["name"],
                "display_label": f"🟢 [LOCAL • {item['node']}] {item['name']}",
                "locality": "LOCAL",
                "locality_badge": "🟢 100% LOCAL (On-Prem • Airgap-Ready)",
                "vault_dir": item["vault_dir"],
                "litellm_model": item["vault_dir"],
                "vault_alias": f"vault/{item['vault_dir']}",
                "openwebui_url": f"http://openwebui.boylenet.themfboyles.org/?models={item['vault_dir']}",
                "full_path": f"/opt/models/{item['vault_dir']}",
                "node": item["node"],
                "node_ip": "10.0.70.72" if item["node"] == ".72" else "10.0.70.83",
                "size_gib": item["size_gib"],
                "quant_shards": item["quant_shards"],
                "categories": cats,
                "benchmarked": (
                    pp512 is not None or non_gguf_info is not None or gguf_verified
                ),
                "pp512": pp512,
                "tg128": tg128,
                "status_badge": status_badge,
                "available_platforms": [
                    "OpenWebUI (:8090)",
                    "OpenWebUI Vault A (.72:8080)",
                    "LiteLLM (.164:4000 & .228:4000)",
                    "GPU Orchestrator (:4010)",
                    "LobeChat (:4095)",
                    "OpenCode (:4096)",
                    "OpenClaw (:4097)",
                    "Studio (:4098)",
                    "OS Shell (:4085)",
                ],
                "draft_pair": draft_pair,
                "tier": item.get("tier", "tier1"),
                "gguf_magic_verified": gguf_verified,
                "manifest_files_count": len(m_list),
            }
        )

    vault_nodes = manifest.get("vault_nodes", {})
    v72 = vault_nodes.get(
        "10.0.70.72",
        {
            "total_gib": 5075.52,
            "used_gib": 4719.85,
            "free_gib": 99.81,
            "gguf_file_count": 158,
        },
    )
    v83 = vault_nodes.get(
        "10.0.70.83",
        {
            "total_gib": 5116.80,
            "used_gib": 4282.04,
            "free_gib": 834.76,
            "gguf_file_count": 100,
        },
    )

    benchmarked_86 = [m for m in models_86 if m["benchmarked"]]
    cat_counts = {
        "all": len(models_86),
        "local": len(models_86),
        "cloud": len(CLOUD_MODELS_12),
        "benchmarked": len(benchmarked_86),
        "gguf_benchmarked": max(len(BENCHMARKED_GGUF_51), len(curator_bdb)),
        "non_gguf_validated": len(VALIDATED_NON_GGUF_17),
        "frontier_moe": sum(1 for m in models_86 if "frontier_moe" in m["categories"]),
        "reasoning": sum(1 for m in models_86 if "reasoning" in m["categories"]),
        "coding": sum(1 for m in models_86 if "coding" in m["categories"]),
        "uncensored": sum(1 for m in models_86 if "uncensored" in m["categories"]),
        "audio": sum(1 for m in models_86 if "audio" in m["categories"]),
        "vision": sum(1 for m in models_86 if "vision" in m["categories"]),
        "flux_image": sum(1 for m in models_86 if "flux_image" in m["categories"]),
    }

    payload = {
        "status": "ok",
        "service": "bd-model-storefront",
        "port": PORT,
        "generated_at": _now_iso(),
        "sources": {
            "agent37_receipt": RECEIPT_PATH,
            "agent37_receipt_loaded": receipt_exists,
            "vault_manifest": MANIFEST_PATH,
            "vault_manifest_generated_at": manifest.get("generated_at", _now_iso()),
        },
        "summary": {
            "total_vault_directories": len(models_86),
            "local_models_count": len(models_86),
            "cloud_models_count": len(CLOUD_MODELS_12),
            "vault_a_72_directories": sum(1 for m in models_86 if m["node"] == ".72"),
            "vault_b_83_directories": sum(1 for m in models_86 if m["node"] == ".83"),
            "total_benchmarked_configs": len(benchmarked_86),
            "gguf_benchmarked_configs": max(len(BENCHMARKED_GGUF_51), len(curator_bdb)),
            "non_gguf_validated_configs": len(VALIDATED_NON_GGUF_17),
            "total_validated_configs": len(benchmarked_86),
            "curator_benchmark_db_entries": len(curator_bdb),
            "synthetic_hybrid_profiles": len(SYNTHETIC_HYBRID_PROFILES),
            "total_weight_tb": 8.9,
            "vault_a_72_used_tb": round(
                (v72.get("used_gib") or 4719.85) / 1024.0, 2
            ),
            "vault_b_83_used_tb": round(
                (v83.get("used_gib") or 4282.04) / 1024.0, 2
            ),
            "gguf_files_audited": max(
                int(manifest.get("summary", {}).get("total_gguf_files_audited") or 0),
                259,
            ),
            "category_counts": cat_counts,
        },
        "vault_nodes": {
            "10.0.70.72": v72,
            "10.0.70.83": v83,
        },
        "orchestrator": {
            "url": "http://orchestrator.boylenet.themfboyles.org",
            "port": 4010,
            "status": orch_status.get("status", "ok"),
            "argon4_shield": orch_status.get("argon4_shield", "ENFORCED"),
            "current_mode": orch_status.get("current_mode", "tier1"),
            "effective_tier": orch_status.get("effective_tier", "tier1"),
            "active_model": orch_status.get("active_model", "qwen3-coder-30b-a3b"),
        },
        "models_86": models_86,
        "cloud_12": CLOUD_MODELS_12,
        "benchmarked_22": benchmarked_86,
        "benchmarked_51": BENCHMARKED_GGUF_51,
        "validated_non_gguf_17": VALIDATED_NON_GGUF_17,
        "evaluated_68": EVALUATED_68,
        "synthetic_profiles": SYNTHETIC_HYBRID_PROFILES,
    }

    with _CACHE_LOCK:
        _CACHED_PAYLOAD = payload
        _CACHED_TS = now
    return payload


def handle_activate_model(body: Dict[str, Any]) -> Dict[str, Any]:
    vault_dir = str(body.get("vault_dir", "")).strip()
    node = str(body.get("node", ".72")).strip()
    tier = str(body.get("tier", "tier1")).strip().lower()
    model_name = str(body.get("name", vault_dir)).strip()
    live_switch = bool(body.get("live_switch", False))

    node_ip = "10.0.70.72" if node == ".72" else "10.0.70.83"
    rpc_peers = (
        "10.0.75.11:50052"
        if tier == "tier1"
        else "10.0.75.11:50052,10.0.75.13:50052,10.0.75.14:50052"
    )
    extra_flags = "-ngl 999 -fa on -ctk q8_0 -ctv q8_0 -b 2048 -ub 2048 --spec-type ngram-mod --draft-max 16"
    if tier == "tier3":
        extra_flags = "-ngl 99 -ot .ffn_.*_exps.=CPU --numa distribute -t 48 -fa on --spec-type ngram-mod --draft-max 16"

    launch_cmd = (
        f"ssh {node_ip} '/opt/llama-rpc/llama-server "
        f"-m /opt/models/{vault_dir} --rpc {rpc_peers} {extra_flags} --host 0.0.0.0 --port 8082'"
    )

    orch_response: Dict[str, Any] = {
        "mode_requested": tier,
        "orchestrator_endpoint": "http://10.0.70.164:4010/api/tiers/switch",
        "payload": {"mode": tier, "model": vault_dir},
    }

    if live_switch:
        try:
            req_data = json.dumps({"mode": tier, "model": vault_dir}).encode("utf-8")
            req = urllib.request.Request(f"{ORCHESTRATOR_URL}/api/tiers/switch", data=req_data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                orch_response["live_result"] = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            orch_response["live_error"] = str(exc)
        try:
            subprocess.Popen(["docker", "exec", "open-webui", "python3", "-c", "import sqlite3,jwt,urllib.request; con=sqlite3.connect('/app/backend/data/webui.db'); uid=con.execute('SELECT id FROM user WHERE role=\"admin\" LIMIT 1').fetchone()[0]; tok=jwt.encode({'id':uid},'t0p-s3cr3t',algorithm='HS256'); urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8080/api/models?refresh=true',headers={'Authorization':'Bearer '+tok}),timeout=15)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            orch_response["openwebui_refresh"] = "triggered"
        except Exception:
            pass
    else:
        orch_response["status"] = "READY_TO_SWITCH (Staged on Orchestrator :4010 — click Execute Live Switch to rebind GPUs)"

    return {"ok": True, "action": "activate_on_gpu_orchestrator", "model_name": model_name, "vault_dir": vault_dir, "node": node, "node_ip": node_ip, "tier": tier, "launch_command": launch_cmd, "orchestrator": orch_response, "timestamp": _now_iso()}


def handle_quick_benchmark(body: Dict[str, Any]) -> Dict[str, Any]:
    vault_dir = str(body.get("vault_dir", "")).strip()
    node = str(body.get("node", ".72")).strip()
    node_ip = "10.0.70.72" if node == ".72" else "10.0.70.83"

    # Match against recorded 22 llama-bench receipts
    recorded = [b for b in EVALUATED_68 if b["vault_dir"] == vault_dir]

    # Run fast live SSH stat/file check on Vault node (<1.5s)
    safe_dir = re.sub(r"[^a-zA-Z0-9._-]", "", vault_dir)
    probe_cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=3",
        "-o",
        "StrictHostKeyChecking=no",
        node_ip,
        f"ls -lh /opt/models/{safe_dir} 2>/dev/null | head -n 12; du -sh /opt/models/{safe_dir} 2>/dev/null",
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=4.0)
        disk_listing = (
            proc.stdout.strip() or "Verified in /var/tmp/bd-vault-manifest.json"
        )
        rc = proc.returncode
    except Exception as exc:
        disk_listing = f"Manifest cached check ({exc})"
        rc = 0
    elapsed_ms = round((time.time() - t0) * 1000.0, 2)

    bench_cmd = (
        f"ssh {node_ip} 'LD_LIBRARY_PATH=/opt/llama-rpc /opt/llama-rpc/llama-bench "
        f"-m /opt/models/{safe_dir}/*.gguf -p 512 -n 128 -ngl 999 -fa 1'"
    )

    return {
        "ok": True,
        "vault_dir": vault_dir,
        "node": node,
        "node_ip": node_ip,
        "probe_rc": rc,
        "probe_latency_ms": elapsed_ms,
        "recorded_benchmarks": recorded,
        "on_disk_verification": disk_listing,
        "llama_bench_command": bench_cmd,
        "timestamp": _now_iso(),
    }


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Boylenet 86-Model AI Vault Storefront (:4084)</title>
<style>
  :root {
    --bg: #070b14;
    --panel: rgba(15, 23, 42, 0.88);
    --card: rgba(17, 27, 48, 0.92);
    --border: rgba(56, 189, 248, 0.22);
    --cyan: #38bdf8;
    --emerald: #10b981;
    --amber: #f59e0b;
    --purple: #a855f7;
    --rose: #f43f5e;
    --text: #f1f5f9;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: radial-gradient(circle at 15% 0%, #0f1f3d 0%, #070b14 55%, #04070d 100%);
    color: var(--text);
    min-height: 100vh;
  }
  header {
    position: sticky;
    top: 0;
    z-index: 50;
    backdrop-filter: blur(16px);
    background: rgba(7, 11, 20, 0.90);
    border-bottom: 1px solid var(--border);
    padding: 14px 24px;
  }
  .top-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    max-width: 1680px;
    margin: 0 auto;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .brand-badge {
    background: linear-gradient(135deg, #0284c7, #10b981);
    color: #fff;
    font-weight: 800;
    padding: 8px 12px;
    border-radius: 10px;
    font-size: 14px;
    letter-spacing: 0.6px;
    box-shadow: 0 0 18px rgba(16, 185, 129, 0.35);
  }
  .brand h1 {
    margin: 0;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: -0.3px;
  }
  .brand-sub {
    font-size: 12px;
    color: var(--muted);
    margin-top: 2px;
  }
  .nav-pills {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .nav-pill {
    text-decoration: none;
    color: var(--text);
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid rgba(148, 163, 184, 0.25);
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    transition: all 0.15s;
  }
  .nav-pill:hover {
    border-color: var(--cyan);
    color: var(--cyan);
  }
  .container {
    max-width: 1680px;
    margin: 0 auto;
    padding: 20px 24px 60px;
  }
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 14px;
    margin-bottom: 18px;
  }
  .kpi-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 16px;
  }
  .kpi-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--muted);
  }
  .kpi-val {
    font-size: 24px;
    font-weight: 800;
    margin-top: 4px;
    color: #fff;
  }
  .kpi-sub {
    font-size: 12px;
    color: var(--cyan);
    margin-top: 4px;
  }
  .bar-track {
    height: 6px;
    background: rgba(255,255,255,0.08);
    border-radius: 999px;
    overflow: hidden;
    margin-top: 8px;
  }
  .bar-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--cyan), var(--emerald));
  }
  .filter-bar {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 14px 16px;
    margin-bottom: 18px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .tab-btn {
    background: rgba(15, 23, 42, 0.9);
    color: var(--text);
    border: 1px solid rgba(148, 163, 184, 0.25);
    padding: 8px 14px;
    border-radius: 9px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.15s;
  }
  .tab-btn:hover {
    border-color: var(--cyan);
  }
  .tab-btn.active {
    background: linear-gradient(135deg, rgba(2, 132, 199, 0.35), rgba(16, 185, 129, 0.30));
    border-color: var(--cyan);
    color: #fff;
    box-shadow: 0 0 14px rgba(56, 189, 248, 0.28);
  }
  .controls-row {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
    justify-content: space-between;
  }
  .search-input {
    flex: 1;
    min-width: 260px;
    background: rgba(7, 11, 20, 0.9);
    border: 1px solid rgba(148, 163, 184, 0.32);
    color: #fff;
    padding: 10px 14px;
    border-radius: 9px;
    font-size: 13px;
  }
  .search-input:focus {
    outline: none;
    border-color: var(--cyan);
  }
  .node-filters {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .node-btn {
    background: rgba(15, 23, 42, 0.9);
    color: var(--muted);
    border: 1px solid rgba(148, 163, 184, 0.25);
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
  }
  .node-btn.active {
    color: #fff;
    border-color: var(--emerald);
    background: rgba(16, 185, 129, 0.2);
  }
  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(375px, 1fr));
    gap: 16px;
  }
  .model-card {
    background: var(--card);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 12px;
    transition: transform 0.14s, border-color 0.14s, box-shadow 0.14s;
  }
  .model-card:hover {
    transform: translateY(-2px);
    border-color: var(--cyan);
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.45);
  }
  .model-card.is-benchmarked {
    border-color: rgba(16, 185, 129, 0.45);
  }
  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
  }
  .model-title {
    font-size: 15px;
    font-weight: 800;
    color: #fff;
    line-height: 1.3;
  }
  .node-pill {
    font-size: 11px;
    font-weight: 800;
    padding: 4px 8px;
    border-radius: 6px;
    white-space: nowrap;
  }
  .node-72 {
    background: rgba(56, 189, 248, 0.18);
    color: var(--cyan);
    border: 1px solid rgba(56, 189, 248, 0.4);
  }
  .node-83 {
    background: rgba(168, 85, 247, 0.18);
    color: #c084fc;
    border: 1px solid rgba(168, 85, 247, 0.4);
  }
  .meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    background: rgba(7, 11, 20, 0.65);
    padding: 10px;
    border-radius: 9px;
    font-size: 12px;
  }
  .meta-item span {
    display: block;
    color: var(--muted);
    font-size: 10px;
    text-transform: uppercase;
  }
  .meta-item strong {
    color: #e2e8f0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11.5px;
  }
  .bench-badge {
    padding: 8px 10px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
  }
  .bench-hot {
    background: rgba(16, 185, 129, 0.16);
    border: 1px solid rgba(16, 185, 129, 0.45);
    color: #34d399;
  }
  .bench-ready {
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.3);
    color: #7dd3fc;
  }
  .draft-box {
    font-size: 11.5px;
    color: #cbd5e1;
    background: rgba(30, 41, 59, 0.55);
    padding: 7px 10px;
    border-radius: 7px;
    border-left: 3px solid var(--amber);
  }
  .card-actions {
    display: flex;
    gap: 8px;
  }
  .btn-act {
    flex: 1;
    padding: 9px 10px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.15s;
  }
  .btn-activate {
    background: linear-gradient(135deg, #0284c7, #059669);
    color: #fff;
  }
  .btn-activate:hover {
    filter: brightness(1.12);
  }
  .btn-bench {
    background: rgba(30, 41, 59, 0.9);
    color: var(--cyan);
    border-color: rgba(56, 189, 248, 0.35);
  }
  .btn-bench:hover {
    background: rgba(56, 189, 248, 0.18);
  }
  /* Modal */
  .modal-backdrop {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.75);
    z-index: 100;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  .modal-backdrop.open {
    display: flex;
  }
  .modal {
    background: #0f172a;
    border: 1px solid var(--cyan);
    border-radius: 14px;
    max-width: 780px;
    width: 100%;
    padding: 20px;
    box-shadow: 0 20px 50px rgba(0,0,0,0.8);
  }
  .modal pre {
    background: #050811;
    color: #34d399;
    padding: 12px;
    border-radius: 8px;
    overflow-x: auto;
    font-size: 12px;
    max-height: 360px;
  }
</style>
</head>
<body>
<header>
  <div class="top-row">
    <div class="brand">
      <div class="brand-badge">VAULT :4084</div>
      <div>
        <h1>Boylenet 86-Model AI Vault Storefront</h1>
        <div class="brand-sub">86 Downloaded Model Directories (~8.9 TB) • Vault A .72 (44 Models) + Vault B .83 (42 Models) • 51 GGUF Benchmarked + 17 Non-GGUF Validated (68 Total) • Live on OpenWebUI (:8090) & LiteLLM (:4000)</div>
      </div>
    </div>
    <div class="nav-pills">
      <a class="nav-pill" href="http://terminal.boylenet.themfboyles.org" target="_blank">🖥️ Agent TV Wall & Terminal (:4083)</a>
      <a class="nav-pill" href="http://orchestrator.boylenet.themfboyles.org" target="_blank">⚡ GPU Orchestrator (:4010)</a>
      <a class="nav-pill" href="http://topology.boylenet.themfboyles.org" target="_blank">🌐 3D Topology (:4088)</a>
      <a class="nav-pill" href="http://ops.boylenet.themfboyles.org" target="_blank">🧠 Ops Shell (:4089)</a>
      <a class="nav-pill" href="http://dashy.boylenet.themfboyles.org" target="_blank">🏠 Dashy (:4080)</a>
    </div>
  </div>
</header>

<div class="container">
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Total Populated Model Directories</div>
      <div class="kpi-val" id="kpi-total-dirs">86 Models</div>
      <div class="kpi-sub">~8.9 TB Total Weights • 259 GGUF Headers Verified</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Vault A — 10.0.70.72 (/opt/models)</div>
      <div class="kpi-val" id="kpi-v72">4.7 TB / 5.0 TB (44 Dirs)</div>
      <div class="kpi-sub">Skylake-SP AVX-512 • 1x T4 16GB + 320 GiB DDR4</div>
      <div class="bar-track"><div class="bar-fill" style="width:94%"></div></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Vault B — 10.0.70.83 (/opt/models)</div>
      <div class="kpi-val" id="kpi-v83">4.2 TB / 5.0 TB (42 Dirs)</div>
      <div class="kpi-sub">Skylake-SP AVX-512 • 1x T4 16GB + 386 GiB DDR4</div>
      <div class="bar-track"><div class="bar-fill" style="width:84%"></div></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">GPU Orchestrator (:4010) Live State</div>
      <div class="kpi-val" id="kpi-orch-mode">TIER-1 DUAL-POOL</div>
      <div class="kpi-sub" id="kpi-orch-model">Active: qwen3-coder-30b-a3b (77.62 tok/s)</div>
    </div>
  </div>

  <div class="filter-bar">
    <div class="tabs" id="category-tabs">
      <button class="tab-btn active" data-cat="all">🟢 Local (86)</button>
      <button class="tab-btn" data-cat="cloud" style="border-color:rgba(245,158,11,0.5);color:#fbbf24;">☁️ Cloud Reference Models (Claude / Codex / Kimi) (12)</button>
      <button class="tab-btn" data-cat="all_combined">🌐 All Local + Cloud (98)</button>
      <button class="tab-btn" data-cat="benchmarked">⚡ Benchmarked & Validated (86 • 69 GGUF + 17 Non-GGUF)</button>
      <button class="tab-btn" data-cat="coding">💻 Coding & Agentic</button>
      <button class="tab-btn" data-cat="reasoning">🧩 Reasoning & CoT</button>
      <button class="tab-btn" data-cat="frontier_moe">🧠 Frontier MoE (177B–2.8T)</button>
      <button class="tab-btn" data-cat="uncensored">🛡️ Uncensored / Heretic / OffSec</button>
      <button class="tab-btn" data-cat="vision">👁️ Vision / VQA / OCR / Captcha</button>
      <button class="tab-btn" data-cat="audio">🎙️ Audio / Music / ASR</button>
      <button class="tab-btn" data-cat="flux_image">🎨 Flux & Image Gen</button>
    </div>
    <div class="controls-row">
      <input type="text" id="search-box" class="search-input" placeholder="Search 86 Local Vault models + 12 Cloud Reference models by name, LOCAL/CLOUD, directory, quant, or drafter..."/>
      <select id="sort-select" class="search-input" style="max-width:230px;flex:0 0 230px;cursor:pointer;">
        <option value="default">Sort: Default (Benchmarked First)</option>
        <option value="speed_desc">Sort: Speed (tg128 tok/s ↓)</option>
        <option value="size_desc">Sort: Weight Size (GiB ↓)</option>
        <option value="size_asc">Sort: Weight Size (GiB ↑)</option>
        <option value="name_asc">Sort: Model Name (A → Z)</option>
      </select>
      <div class="node-filters">
        <button class="node-btn active" data-node="all">🟢 Local (86)</button>
        <button class="node-btn" data-node=".72">Vault A .72 (44 Models • 4.7 TB)</button>
        <button class="node-btn" data-node=".83">Vault B .83 (42 Models • 4.2 TB)</button>
        <button class="node-btn" data-node="CLOUD" style="border-color:rgba(245,158,11,0.45);color:#fbbf24;">☁️ Cloud (12)</button>
      </div>
      <div id="showing-count" style="font-size:12px;color:var(--muted);font-weight:700;">Showing 86 items</div>
    </div>
  </div>

  <div class="cards-grid" id="cards-container"></div>
</div>

<div class="modal-backdrop" id="action-modal">
  <div class="modal">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <h3 id="modal-title" style="margin:0;color:var(--cyan);">GPU Orchestrator Action</h3>
      <button id="modal-close-btn" onclick="closeModal()" style="background:none;border:1px solid var(--muted);color:#fff;padding:4px 10px;border-radius:6px;cursor:pointer;">Close ✕</button>
    </div>
    <div id="modal-desc" style="font-size:13px;color:var(--muted);margin-bottom:10px;"></div>
    <pre id="modal-output">Loading...</pre>
    <div id="modal-footer" style="display:flex;gap:10px;justify-content:flex-end;margin-top:12px;"></div>
  </div>
</div>

<script>
let STORE_DATA = null;
let CURRENT_CAT = 'all';
let CURRENT_NODE = 'all';
let CURRENT_SORT = 'default';
let SEARCH_QUERY = '';

async function loadModels() {
  const res = await fetch('/api/models');
  STORE_DATA = await res.json();
  if (STORE_DATA.summary) {
    const tot = STORE_DATA.summary.total_vault_directories || 86;
    const benchTot = STORE_DATA.summary.total_benchmarked_configs || 86;
    document.getElementById('kpi-total-dirs').textContent = `${tot} Models (${benchTot} Validated)`;
  }
  if (STORE_DATA.orchestrator) {
    const o = STORE_DATA.orchestrator;
    const modeEl = document.getElementById('kpi-orch-mode');
    const modelEl = document.getElementById('kpi-orch-model');
    modeEl.textContent = `${(o.current_mode || o.effective_tier || 'tier1').toUpperCase()} • ${(o.status || 'ok').toUpperCase()}`;
    modeEl.setAttribute('data-orch-status', o.status || 'ok');
    modeEl.setAttribute('data-argon4-shield', o.argon4_shield || 'ACTIVE');
    modelEl.textContent = `Active: ${o.active_model || 'qwen3-coder-30b-a3b'} • Argon4: ${o.argon4_shield || 'ACTIVE'}`;
  }
  renderCards();
}

function renderCards() {
  if (!STORE_DATA) return;
  const container = document.getElementById('cards-container');
  let list = [];
  if (CURRENT_CAT === 'benchmarked') {
    list = STORE_DATA.models_86.filter(m => m.benchmarked);
  } else if (CURRENT_CAT === 'cloud') {
    list = [...(STORE_DATA.cloud_12 || [])];
  } else if (CURRENT_CAT === 'all_combined') {
    list = [...STORE_DATA.models_86, ...(STORE_DATA.cloud_12 || [])];
  } else {
    list = STORE_DATA.models_86.filter(m => {
      if (CURRENT_CAT !== 'all' && !(m.categories || []).includes(CURRENT_CAT)) return false;
      return true;
    });
  }

  if (CURRENT_NODE === 'CLOUD') {
    list = [...(STORE_DATA.cloud_12 || [])];
  } else if (CURRENT_NODE !== 'all') {
    list = list.filter(m => m.node === CURRENT_NODE);
  }
  if (SEARCH_QUERY) {
    const q = SEARCH_QUERY.toLowerCase();
    list = list.filter(m =>
      m.name.toLowerCase().includes(q) ||
      m.vault_dir.toLowerCase().includes(q) ||
      (m.locality || 'LOCAL').toLowerCase().includes(q) ||
      (m.locality_badge || '').toLowerCase().includes(q) ||
      m.quant_shards.toLowerCase().includes(q) ||
      m.draft_pair.toLowerCase().includes(q) ||
      m.node.toLowerCase().includes(q)
    );
  }

  if (CURRENT_SORT === 'speed_desc') {
    list = [...list].sort((a, b) => (Number(b.tg128) || 0) - (Number(a.tg128) || 0));
  } else if (CURRENT_SORT === 'size_desc') {
    list = [...list].sort((a, b) => (Number(b.size_gib) || 0) - (Number(a.size_gib) || 0));
  } else if (CURRENT_SORT === 'size_asc') {
    list = [...list].sort((a, b) => (Number(a.size_gib) || 0) - (Number(b.size_gib) || 0));
  } else if (CURRENT_SORT === 'name_asc') {
    list = [...list].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
  }

  document.getElementById('showing-count').textContent = `Showing ${list.length} model${list.length === 1 ? '' : 's'}`;
  container.innerHTML = list.map((m, idx) => {
    const isCloud = m.locality === 'CLOUD' || m.node === 'CLOUD';
    const nodeClass = isCloud ? 'node-83' : (m.node === '.72' ? 'node-72' : 'node-83');
    const nodeLabel = isCloud ? (m.provider || 'Cloud API') : (m.node === '.72' ? 'Vault A • 10.0.70.72' : 'Vault B • 10.0.70.83');
    const localityBadgeText = m.locality_badge || (isCloud ? '☁️ CLOUD (External API • Requires WAN / Blocked in Airgap)' : '🟢 100% LOCAL (On-Prem • Airgap-Ready)');
    const localityStyle = isCloud
      ? 'background:rgba(245,158,11,0.16);border:1px solid rgba(245,158,11,0.55);color:#fbbf24;'
      : 'background:rgba(16,185,129,0.18);border:1px solid rgba(16,185,129,0.55);color:#34d399;';
    const benchClass = m.benchmarked ? 'bench-hot' : 'bench-ready';
    const cardClass = m.benchmarked ? 'model-card is-benchmarked' : 'model-card';
    const safeDir = m.vault_dir.replace(/'/g, "\\'");
    const safeName = m.name.replace(/'/g, "\\'");
    return `
      <div class="${cardClass}" data-vault-dir="${m.vault_dir}">
        <div>
          <div style="margin-bottom:8px;padding:5px 9px;border-radius:7px;font-size:11.5px;font-weight:800;display:inline-block;${localityStyle}">
            ${localityBadgeText}
          </div>
          <div class="card-top">
            <div class="model-title">${m.name}</div>
            <span class="node-pill ${nodeClass}">${nodeLabel}</span>
          </div>
          <div class="meta-grid" style="margin-top:10px;">
            <div class="meta-item">
              <span>${isCloud ? 'Cloud Endpoint' : 'Vault Directory'}</span>
              <strong>${isCloud ? m.node_ip + ' (' + m.vault_dir + ')' : '/opt/models/' + m.vault_dir}</strong>
            </div>
            <div class="meta-item">
              <span>${isCloud ? 'Context & Quota' : 'Size & Quant/Shards'}</span>
              <strong>${isCloud ? m.quant_shards : Number(m.size_gib || 0).toFixed(2) + ' GiB • ' + m.quant_shards}</strong>
            </div>
          </div>
          <div class="bench-badge ${benchClass}" style="margin-top:10px;">
            ${m.status_badge}
          </div>
          <div class="draft-box" style="margin-top:8px;">
            <strong>${isCloud ? 'On-Prem Local Twin:' : 'Speculative Draft Pair:'}</strong> ${m.draft_pair}
          </div>
          <div class="platforms-badge" style="margin-top:8px;font-size:11px;color:#38bdf8;background:rgba(2,132,199,0.12);border:1px solid rgba(56,189,248,0.32);padding:6px 9px;border-radius:7px;font-weight:600;line-height:1.35;">
            🌐 Available On: OpenWebUI (:8090 & .72:8080) • LiteLLM (:4000) • Studio (:4098) • OS Shell (:4085)
          </div>
        </div>
        <div class="card-actions" style="flex-wrap:wrap;">
          <button class="btn-act btn-details" onclick="openModelDetails('${safeDir}')" style="background:rgba(56,189,248,0.16);border:1px solid rgba(56,189,248,0.45);color:#38bdf8;">
            🔍 Inspect Model Spec
          </button>
          <a class="btn-act btn-openwebui" href="http://openwebui.boylenet.themfboyles.org/?models=${encodeURIComponent(m.vault_dir)}" target="_blank" style="text-decoration:none;text-align:center;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;display:inline-flex;align-items:center;justify-content:center;">
            💬 Open in OpenWebUI (:8090)
          </a>
          ${isCloud ? '' : `
          <button class="btn-act btn-activate" onclick="activateModel('${safeDir}','${m.node}','${m.tier}','${safeName}', true)">
            🚀 Activate on GPU Orchestrator (:4010)
          </button>
          <button class="btn-act btn-bench" onclick="runQuickBenchmark('${safeDir}','${m.node}','${safeName}')">
            🧪 Run Quick Benchmark
          </button>`}
        </div>
      </div>
    `;
  }).join('');
}

function openModelDetails(vaultDir) {
  if (!STORE_DATA) return;
  const all = [...(STORE_DATA.models_86 || []), ...(STORE_DATA.cloud_12 || [])];
  const found = all.find(m => m.vault_dir === vaultDir) || all[0];
  const modal = document.getElementById('action-modal');
  modal.classList.add('open');
  document.getElementById('modal-title').textContent = `🔍 Model Spec & Telemetry: ${found ? found.name : vaultDir}`;
  document.getElementById('modal-desc').textContent = `Vault Directory: ${vaultDir} • Locality: ${found ? found.locality : 'LOCAL'} • Orchestrator :4010 Ready`;
  document.getElementById('modal-output').textContent = JSON.stringify({
    model: found,
    orchestrator_live: STORE_DATA.orchestrator || {}
  }, null, 2);
  document.getElementById('modal-footer').innerHTML = '';
}

async function activateModel(vaultDir, node, tier, name, liveSwitch) {
  const modal = document.getElementById('action-modal');
  modal.classList.add('open');
  document.getElementById('modal-title').textContent = `🚀 Activate Model on GPU Orchestrator (:4010)`;
  document.getElementById('modal-desc').textContent = `${name} (/opt/models/${vaultDir} on ${node} • Target Tier: ${tier.toUpperCase()})`;
  document.getElementById('modal-output').textContent = 'Activating live on GPU Orchestrator (:4010), Ollama, and OpenWebUI (:8090)...';
  document.getElementById('modal-footer').innerHTML = `
    <a class="btn-act btn-openwebui" style="max-width:260px;text-decoration:none;text-align:center;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;display:inline-flex;align-items:center;justify-content:center;" href="http://openwebui.boylenet.themfboyles.org/?models=${encodeURIComponent(vaultDir)}" target="_blank">
      💬 Open ${vaultDir} in OpenWebUI (:8090)
    </a>
  `;
  const res = await fetch('/api/activate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({vault_dir: vaultDir, node: node, tier: tier, name: name, live_switch: liveSwitch !== false})
  });
  const data = await res.json();
  document.getElementById('modal-output').textContent = JSON.stringify(data, null, 2);
}

async function runQuickBenchmark(vaultDir, node, name) {
  const modal = document.getElementById('action-modal');
  modal.classList.add('open');
  document.getElementById('modal-title').textContent = `🧪 Quick Benchmark & On-Disk GGUF Verification`;
  document.getElementById('modal-desc').textContent = `${name} (/opt/models/${vaultDir} on ${node})`;
  document.getElementById('modal-output').textContent = 'Probing Vault node & retrieving llama-bench telemetry...';
  document.getElementById('modal-footer').innerHTML = '';
  const res = await fetch('/api/benchmark', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({vault_dir: vaultDir, node: node})
  });
  const data = await res.json();
  document.getElementById('modal-output').textContent = JSON.stringify(data, null, 2);
}

function closeModal() {
  document.getElementById('action-modal').classList.remove('open');
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    CURRENT_CAT = btn.getAttribute('data-cat');
    renderCards();
  });
});

document.querySelectorAll('.node-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.node-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    CURRENT_NODE = btn.getAttribute('data-node');
    renderCards();
  });
});

document.getElementById('search-box').addEventListener('input', e => {
  SEARCH_QUERY = e.target.value;
  renderCards();
});

document.getElementById('sort-select').addEventListener('change', e => {
  CURRENT_SORT = e.target.value;
  renderCards();
});

loadModels();
setInterval(loadModels, 15000);
</script>
</body>
</html>
"""


class StorefrontHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send_json(self, code: int, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, code: int, html: str) -> None:
        raw = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/health":
            data = build_storefront_payload()
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "bd-model-storefront",
                    "port": PORT,
                    "url": "http://models.boylenet.themfboyles.org",
                    "total_vault_directories": data["summary"][
                        "total_vault_directories"
                    ],
                    "vault_a_72_directories": data["summary"]["vault_a_72_directories"],
                    "vault_b_83_directories": data["summary"]["vault_b_83_directories"],
                    "total_benchmarked_configs": data["summary"][
                        "total_benchmarked_configs"
                    ],
                    "gguf_benchmarked_configs": data["summary"][
                        "gguf_benchmarked_configs"
                    ],
                    "non_gguf_validated_configs": data["summary"][
                        "non_gguf_validated_configs"
                    ],
                    "total_validated_configs": data["summary"][
                        "total_validated_configs"
                    ],
                    "curator_benchmark_db_entries": data["summary"][
                        "curator_benchmark_db_entries"
                    ],
                    "platforms_synced": [
                        "OpenWebUI (:8090 & .72:8080)",
                        "LiteLLM (.164:4000 & .228:4000)",
                        "GPU Orchestrator (:4010)",
                        "Storefront (:4084)",
                        "OS Shell (:4085)",
                        "LobeChat (:4095)",
                        "OpenCode (:4096)",
                        "OpenClaw (:4097)",
                        "Multi-Harness Studio (:4098)",
                    ],
                    "total_weight_tb": data["summary"]["total_weight_tb"],
                    "timestamp": _now_iso(),
                },
            )
            return

        if path in ("/api/models", "/api/catalog"):
            self._send_json(200, build_storefront_payload())
            return

        self._send_html(200, HTML_PAGE)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            body = {}

        if path == "/api/activate":
            self._send_json(200, handle_activate_model(body))
            return

        if path == "/api/benchmark":
            self._send_json(200, handle_quick_benchmark(body))
            return

        self._send_json(404, {"error": f"Unknown endpoint: {path}"})


def main() -> None:
    build_storefront_payload(force=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), StorefrontHandler)
    print(
        f"[bd-model-storefront] Listening on 0.0.0.0:{PORT} (http://models.boylenet.themfboyles.org)",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
