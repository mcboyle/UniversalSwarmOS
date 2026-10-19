#!/usr/bin/env python3
"""
Boylenet Natural-Language Ops Shell (bd-ops-web.py / bd-ops)
Port: 4089 (http://ops.boylenet.themfboyles.org)
Swarms #17 & #C9: Translates natural-language infrastructure requests into structured,
pre-vetted read/ops commands across:
  - bd-pool-autobalancer
  - bd-gpu-orchestrator (bd-tier-switch / :4010)
  - bd-infra-sentinel (:4099)
  - bd-remote-pytest-turbo
  - bd-vault-curator
  - bd-semantic-search
  - bd-hardware-telemetry (:4091)
  - bd-cloud-burst (:4090)

Supports:
  - Kimi Code CLI (/home/mboyle/.local/bin/kimi -p "..." with stdin=subprocess.DEVNULL)
  - Local 4xT4 GPU Models (http://10.0.70.164:4000/v1/chat/completions)
  - Deterministic Fast-Path Intent Classifier + Parameter Extractor
  - Dry-Run Preview Mode (READ-ONLY vs STATE-CHANGE safety classification)
  - 1-Click Verified Playbook Execution & Audit Trail (/var/tmp/bd-ops-history.jsonl)
"""

from __future__ import annotations

import argparse
import datetime
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

PORT = int(os.environ.get("BD_OPS_PORT", "4089"))
KIMI_BIN = "/home/mboyle/.local/bin/kimi"
LITELLM_URL = os.environ.get("BD_LITELLM_URL", "http://10.0.70.164:4000").rstrip("/")
LITELLM_KEY = os.environ.get("BD_LITELLM_KEY", "sk-fleet-local")
HISTORY_PATH = "/var/tmp/bd-ops-history.jsonl"
HISTORY_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get_json(url: str, timeout: float = 8.0) -> Dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_json(
    url: str,
    payload: Dict[str, Any],
    timeout: float = 20.0,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=hdrs,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Pre-Vetted Playbook Catalog
# ---------------------------------------------------------------------------
PLAYBOOKS: List[Dict[str, Any]] = [
    {
        "id": "gpu_temps_all",
        "title": "Check GPU Temps, VRAM & Power Across All 4 T4 Nodes",
        "sample_query": "check GPU temps across all 4 T4 nodes",
        "tool": "bd-gpu-orchestrator",
        "binary": "/home/mboyle/bin/bd-tier-switch",
        "safety_class": "READ-ONLY",
        "risk_level": "LOW (Zero State Mutation)",
        "target_node": "ai-srv01 (.72), ai-srv02 (.73), ai-ollama01 (.228), ai-infer01 (.125)",
        "command_preview": "/home/mboyle/bin/bd-tier-switch status",
        "description": "Queries :4010 GPU Orchestrator for live nvidia-smi temperatures, VRAM usage, power draw, DDR4 RAM, and active llama.cpp RPC slots across all 4 Tesla T4 nodes.",
        "keywords": [
            "gpu",
            "temp",
            "temps",
            "temperature",
            "t4",
            "vram",
            "4xt4",
            "nvidia",
            "watts",
            "power",
        ],
    },
    {
        "id": "vsan_disk_groups_esxi",
        "title": "Show vSAN Disk Groups, Cache SSDs & Capacity Disks on ESXi Host",
        "sample_query": "show vSAN disk groups on esxi01",
        "tool": "bd-infra-sentinel / bd-hardware-telemetry",
        "binary": "/home/mboyle/bin/bd-hardware-telemetry.py",
        "safety_class": "READ-ONLY",
        "risk_level": "LOW (Zero State Mutation)",
        "target_node": "esxi01 (10.0.20.41) / vSAN Cluster (vc04 10.0.20.70)",
        "command_preview": "bd-ops --playbook vsan_disk_groups_esxi --host esxi01 (via http://10.0.70.164:4091/api/hardware)",
        "description": "Inspects vSAN datastore capacity (328.45 TiB total), cache tier SSDs, and backing NAA capacity disks on the requested ESXi host (esxi01..esxi04 or all).",
        "keywords": [
            "vsan",
            "disk group",
            "disk groups",
            "esxi01",
            "esxi02",
            "esxi03",
            "esxi04",
            "esxi",
            "ssd",
            "datastore",
            "ilo",
        ],
    },
    {
        "id": "switch_tier1_cyberstrike",
        "title": "Switch Tier 1 Alpha/Beta GPU Pool to CyberStrike 35B",
        "sample_query": "switch Tier 1 Alpha to CyberStrike 35B",
        "tool": "bd-gpu-orchestrator",
        "binary": "/home/mboyle/bin/bd-tier-switch",
        "safety_class": "STATE-CHANGE",
        "risk_level": "MEDIUM (Hot-Swaps Active GPU Tier 1 Model)",
        "target_node": "10.0.70.164:4010 -> ai-srv01 (.72) & ai-srv02 (.73)",
        "command_preview": "/home/mboyle/bin/bd-tier-switch tier1 cyberstrike-offsec-35b",
        "description": "Hot-swaps the 4xT4 GPU cluster into Tier 1 with cyberstrike-offsec-35b active and verifies Argon-4 shield compliance.",
        "keywords": ["cyberstrike", "35b", "offsec", "tier 1 alpha", "switch tier 1"],
    },
    {
        "id": "switch_tier1_qwen3",
        "title": "Switch Tier 1 GPU Pool to Qwen3-Coder-30B-A3B (Default Fast Coding)",
        "sample_query": "switch Tier 1 to Qwen3 Coder 30B",
        "tool": "bd-gpu-orchestrator",
        "binary": "/home/mboyle/bin/bd-tier-switch",
        "safety_class": "STATE-CHANGE",
        "risk_level": "MEDIUM (Hot-Swaps Active GPU Tier 1 Model)",
        "target_node": "10.0.70.164:4010 -> ai-srv01 (.72), ai-srv02 (.73), ai-ollama01 (.228), ai-infer01 (.125)",
        "command_preview": "/home/mboyle/bin/bd-tier-switch tier1 qwen3-coder-30b-a3b",
        "description": "Hot-swaps the 4xT4 GPU cluster into dual-pool Tier 1 with qwen3-coder-30b-a3b (77.6 tok/s).",
        "keywords": [
            "qwen3",
            "qwen3-coder",
            "30b",
            "a3b",
            "restore tier 1",
            "default model",
        ],
    },
    {
        "id": "switch_tier2_deepseek70b",
        "title": "Switch 4xT4 Cluster to Tier 2 DeepSeek-R1-Distill-Llama-70B",
        "sample_query": "switch GPU cluster to Tier 2 DeepSeek 70B",
        "tool": "bd-gpu-orchestrator",
        "binary": "/home/mboyle/bin/bd-tier-switch",
        "safety_class": "STATE-CHANGE",
        "risk_level": "MEDIUM (Re-allocates All 4 T4 GPUs to 70B RPC Pool)",
        "target_node": "10.0.70.164:4010 -> All 4 T4 Nodes (60GB GDDR6)",
        "command_preview": "/home/mboyle/bin/bd-tier-switch tier2 deepseek-r1-distill-llama-70b",
        "description": "Switches all 4 Tesla T4 GPUs across RoCE 10.0.75.0/24 into unified Tier 2 70B reasoning mode.",
        "keywords": ["tier 2", "tier2", "deepseek 70b", "70b", "r1-distill"],
    },
    {
        "id": "warm_ci_ramdisk",
        "title": "Warm CI /dev/shm Ramdisk & Bytecode on test3big (.82)",
        "sample_query": "warm CI ramdisk on test3big",
        "tool": "bd-remote-pytest-turbo",
        "binary": "/home/mboyle/bin/bd-remote-pytest-turbo",
        "safety_class": "STATE-CHANGE",
        "risk_level": "LOW-MEDIUM (Rsyncs /dev/shm/bd-ci-ramdisk on Worker Pool)",
        "target_node": "test3big (10.0.70.82, 64-vCPU) + wrk-test01..07",
        "command_preview": "/home/mboyle/bin/bd-remote-pytest-turbo --warm",
        "description": "Pre-stages BulkDownloader worktree into /dev/shm/bd-ci-ramdisk on test3big (10.0.70.82) and precompiles Python bytecode for zero-I/O test execution.",
        "keywords": [
            "warm",
            "ramdisk",
            "test3big",
            "ci ramdisk",
            "/dev/shm",
            "pytest turbo warm",
        ],
    },
    {
        "id": "audit_ci_ramdisk",
        "title": "Audit CI /dev/shm Ramdisk Capacity & CPU Load Across Worker Pool",
        "sample_query": "audit CI ramdisk status on test3big and worker pool",
        "tool": "bd-remote-pytest-turbo",
        "binary": "/home/mboyle/bin/bd-remote-pytest-turbo",
        "safety_class": "READ-ONLY",
        "risk_level": "LOW (Zero State Mutation)",
        "target_node": "test3big (10.0.70.82) + wrk-test01..07",
        "command_preview": "/home/mboyle/bin/bd-remote-pytest-turbo --audit",
        "description": "Audits /dev/shm free space, nproc core counts, load averages, and virtualenv readiness across test workers.",
        "keywords": [
            "audit ramdisk",
            "check ramdisk",
            "pytest audit",
            "worker pool status",
            "test3big status",
        ],
    },
    {
        "id": "lowest_5h_quota_pool",
        "title": "Check Which Pool Has Lowest 5h Quota & O1740 Routing Table",
        "sample_query": "check which pool has the lowest 5h quota",
        "tool": "bd-pool-autobalancer",
        "binary": "/home/mboyle/bin/bd-pool-autobalancer",
        "safety_class": "READ-ONLY",
        "risk_level": "LOW (Zero State Mutation)",
        "target_node": "controller (10.0.70.164)",
        "command_preview": "/home/mboyle/bin/bd-pool-autobalancer --status --no-color",
        "description": "Evaluates live POOL_STATE.tsv and /var/tmp/bd-pool-autobalancer.json to rank all pools (Claude A/B/C/D, Codex, Kimi, AGY, Local 4xT4) by lowest 5-hour quota utilization.",
        "keywords": [
            "lowest",
            "5h",
            "quota",
            "pool",
            "autobalancer",
            "five_hour",
            "which pool",
            "o1740",
            "remaining quota",
        ],
    },
    {
        "id": "sentinel_health_matrix",
        "title": "Check 83-Service Infra Sentinel Health Matrix & Degraded Endpoints",
        "sample_query": "check sentinel health matrix and show any degraded services",
        "tool": "bd-infra-sentinel",
        "binary": "/home/mboyle/bin/bd-infra-sentinel.py",
        "safety_class": "READ-ONLY",
        "risk_level": "LOW (Zero State Mutation)",
        "target_node": "controller (10.0.70.164:4099) -> 27-Node Boylenet Swarm",
        "command_preview": "curl -s http://127.0.0.1:4099/api/status (bd-infra-sentinel)",
        "description": "Queries the :4099 Infra Sentinel daemon for the live 83-service health matrix, uptime %, latency, and recent self-healing actions.",
        "keywords": [
            "sentinel",
            "health",
            "unhealthy",
            "degraded",
            "83",
            "services",
            "uptime",
        ],
    },
    {
        "id": "sentinel_heal_all",
        "title": "Trigger Immediate Infra Sentinel Self-Heal Sweep Across All Services",
        "sample_query": "run sentinel self-heal across all unhealthy services now",
        "tool": "bd-infra-sentinel",
        "binary": "/home/mboyle/bin/bd-infra-sentinel.py",
        "safety_class": "STATE-CHANGE",
        "risk_level": "MEDIUM (Restarts Unhealthy Systemd/Docker Services)",
        "target_node": "controller (10.0.70.164:4099) -> 27-Node Boylenet Swarm",
        "command_preview": "POST http://127.0.0.1:4099/api/heal-now {}",
        "description": "Triggers an immediate full-fleet sweep and automatic self-heal remediation on :4099 Infra Sentinel.",
        "keywords": [
            "heal",
            "self-heal",
            "fix services",
            "restart unhealthy",
            "heal all",
        ],
    },
    {
        "id": "vault_curator_pairs",
        "title": "Audit GGUF Model Vault Integrity & Speculative Draft-Model Pairings",
        "sample_query": "show GGUF model vault speculative draft pairings and integrity",
        "tool": "bd-vault-curator",
        "binary": "/home/mboyle/bin/bd-vault-curator",
        "safety_class": "READ-ONLY",
        "risk_level": "LOW (Zero State Mutation)",
        "target_node": "controller (.164) + /models/gguf Vault",
        "command_preview": "/home/mboyle/bin/bd-vault-curator --pairs",
        "description": "Inspects the GGUF model vault manifest and displays verified target + draft speculative decoding pairs.",
        "keywords": [
            "vault",
            "curator",
            "gguf",
            "draft",
            "speculative",
            "pairs",
            "orphans",
        ],
    },
    {
        "id": "semantic_search_fleet",
        "title": "Run Fleet-Wide Hybrid RAG + AST Semantic Codebase Search",
        "sample_query": "semantic search for O1740 dynamic capability routing",
        "tool": "bd-semantic-search",
        "binary": "/home/mboyle/bin/bd-semantic-search",
        "safety_class": "READ-ONLY",
        "risk_level": "LOW (Zero State Mutation)",
        "target_node": "ai-infer01 (10.0.70.125:6333 Qdrant + TEI :8081/:8082)",
        "command_preview": '/home/mboyle/bin/bd-semantic-search "<search_term>" --top-k 5',
        "description": "Executes hybrid vector + cross-encoder reranked semantic search against Qdrant (.125:6333) and TEI (.125:8081/:8082).",
        "keywords": [
            "search",
            "semantic",
            "qdrant",
            "rag",
            "find code",
            "where is",
            "ast",
        ],
    },
]

PLAYBOOK_BY_ID: Dict[str, Dict[str, Any]] = {p["id"]: p for p in PLAYBOOKS}


def extract_parameters(query: str, playbook_id: str) -> Dict[str, str]:
    q_low = query.lower()
    params: Dict[str, str] = {}
    if playbook_id == "vsan_disk_groups_esxi":
        m = re.search(r"\b(esxi0[1-4])\b", q_low)
        params["host"] = m.group(1) if m else "esxi01"
    elif playbook_id == "semantic_search_fleet":
        cleaned = re.sub(
            r"^(run\s+|perform\s+|execute\s+)?(semantic\s+search|search\s+codebase|search\s+fleet|search|find)\s+(for\s+|about\s+|on\s+)?",
            "",
            query.strip(),
            flags=re.IGNORECASE,
        ).strip("\"' ")
        params["search_term"] = cleaned or "O1740 dynamic capability routing"
    elif playbook_id == "warm_ci_ramdisk":
        if "test3big" in q_low or "10.0.70.82" in q_low or ".82" in q_low:
            params["node"] = "10.0.70.82"
    return params


def deterministic_classify(query: str) -> Tuple[str, float, str]:
    q_low = query.lower().strip()
    if not q_low:
        return "lowest_5h_quota_pool", 1.0, "Default playbook: lowest 5h quota check"

    # Direct high-precision intent patterns
    if (
        ("gpu" in q_low or "t4" in q_low or "vram" in q_low)
        and any(
            w in q_low
            for w in (
                "temp",
                "temps",
                "temperature",
                "check",
                "status",
                "show",
                "power",
                "vram",
                "nodes",
            )
        )
        and "switch" not in q_low
    ):
        return (
            "gpu_temps_all",
            0.99,
            "Matched GPU temperature / VRAM telemetry across 4xT4 nodes",
        )

    if "vsan" in q_low or "disk group" in q_low or re.search(r"\besxi0[1-4]\b", q_low):
        return (
            "vsan_disk_groups_esxi",
            0.99,
            "Matched vSAN disk group / ESXi host storage query",
        )

    if "cyberstrike" in q_low or ("tier 1" in q_low and "35b" in q_low):
        return (
            "switch_tier1_cyberstrike",
            0.99,
            "Matched Tier 1 switch to cyberstrike-offsec-35b",
        )

    if ("switch" in q_low or "load" in q_low or "restore" in q_low) and (
        "qwen3" in q_low or "30b" in q_low
    ):
        return (
            "switch_tier1_qwen3",
            0.98,
            "Matched Tier 1 switch to qwen3-coder-30b-a3b",
        )

    if ("switch" in q_low or "load" in q_low) and (
        "tier 2" in q_low or "tier2" in q_low or "70b" in q_low
    ):
        return (
            "switch_tier2_deepseek70b",
            0.98,
            "Matched Tier 2 switch to deepseek-r1-distill-llama-70b",
        )

    if ("warm" in q_low or "pre-sync" in q_low or "presync" in q_low) and (
        "ramdisk" in q_low or "test3big" in q_low or "ci" in q_low or "pytest" in q_low
    ):
        return "warm_ci_ramdisk", 0.99, "Matched CI ramdisk warm-up on test3big (.82)"

    if ("audit" in q_low or "status" in q_low or "check" in q_low) and (
        "ramdisk" in q_low or "test3big" in q_low or "pytest turbo" in q_low
    ):
        return "audit_ci_ramdisk", 0.96, "Matched CI ramdisk audit across worker pool"

    if any(
        w in q_low
        for w in (
            "5h",
            "quota",
            "lowest",
            "which pool",
            "autobalancer",
            "pool state",
            "pools",
        )
    ):
        return (
            "lowest_5h_quota_pool",
            0.99,
            "Matched cross-pool 5h quota & O1740 autobalancer inspection",
        )

    if re.search(r"\b(heal|self-heal|fix|remediate)\b", q_low) and (
        "sentinel" in q_low
        or "service" in q_low
        or "unhealthy" in q_low
        or "all" in q_low
    ):
        return "sentinel_heal_all", 0.97, "Matched Infra Sentinel self-heal execution"

    if (
        "sentinel" in q_low
        or "unhealthy" in q_low
        or "83" in q_low
        or "service health" in q_low
    ):
        return (
            "sentinel_health_matrix",
            0.95,
            "Matched Infra Sentinel 83-service health matrix",
        )

    if "vault" in q_low or "gguf" in q_low or "draft" in q_low or "curator" in q_low:
        return (
            "vault_curator_pairs",
            0.96,
            "Matched GGUF Model Vault curator & draft pairs check",
        )

    if (
        "semantic" in q_low
        or "qdrant" in q_low
        or q_low.startswith("search ")
        or q_low.startswith("find ")
    ):
        return "semantic_search_fleet", 0.95, "Matched Hybrid RAG + AST semantic search"

    # Fallback keyword scoring
    best_id = "lowest_5h_quota_pool"
    best_score = 0.0
    for pb in PLAYBOOKS:
        score = sum(1.0 for kw in pb["keywords"] if kw in q_low)
        if score > best_score:
            best_score = score
            best_id = pb["id"]
    return best_id, min(0.90, 0.55 + best_score * 0.12), "Keyword similarity match"


def call_kimi_classifier(query: str, timeout: float = 22.0) -> Dict[str, Any]:
    """Invoke Kimi Code CLI (/home/mboyle/.local/bin/kimi -p ... with stdin=subprocess.DEVNULL)."""
    if not os.path.isfile(KIMI_BIN):
        return {"ok": False, "error": f"{KIMI_BIN} not found"}
    ids_desc = ", ".join(
        f"{p['id']} ({p['safety_class']}: {p['title']})" for p in PLAYBOOKS
    )
    prompt = (
        "You are the Boylenet Natural-Language Ops Shell classifier. "
        f"Map the operator query to ONE playbook_id from: [{ids_desc}]. "
        "Reply with ONLY a single-line JSON object: "
        '{"playbook_id":"<id>","confidence":0.99,"rationale":"<concise 12-word reason>"}. '
        f"Operator query: {query!r}"
    )
    t0 = time.monotonic()
    try:
        p = subprocess.run(
            [KIMI_BIN, "-p", prompt],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        elapsed = round(time.monotonic() - t0, 2)
        raw = (p.stdout or "").strip()
        m = re.search(r"\{[^{}]*\"playbook_id\"[^{}]*\}", raw, flags=re.DOTALL)
        if m:
            parsed = json.loads(m.group(0))
            pb_id = str(parsed.get("playbook_id", "")).strip()
            if pb_id in PLAYBOOK_BY_ID:
                return {
                    "ok": True,
                    "engine": "kimi-code-cli",
                    "elapsed_s": elapsed,
                    "playbook_id": pb_id,
                    "confidence": float(parsed.get("confidence", 0.95)),
                    "rationale": str(
                        parsed.get("rationale", "Classified by Kimi Code CLI")
                    ),
                    "raw_excerpt": raw[:300],
                }
        return {
            "ok": False,
            "engine": "kimi-code-cli",
            "elapsed_s": elapsed,
            "raw_excerpt": raw[:300],
        }
    except Exception as exc:
        return {"ok": False, "engine": "kimi-code-cli", "error": str(exc)}


def call_local_llm_classifier(query: str, timeout: float = 8.0) -> Dict[str, Any]:
    """Invoke Local 4xT4 LiteLLM (:4000) to classify natural-language ops intent."""
    ids_desc = ", ".join(f"{p['id']} ({p['safety_class']})" for p in PLAYBOOKS)
    prompt = (
        f"Classify this Boylenet infrastructure request into one playbook_id from [{ids_desc}]. "
        'Return ONLY JSON: {"playbook_id":"...","rationale":"..."}.\n'
        f"Request: {query}"
    )
    t0 = time.monotonic()
    try:
        resp = http_post_json(
            f"{LITELLM_URL}/v1/chat/completions",
            {
                "model": "qwen3-coder-30b-a3b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 120,
            },
            timeout=timeout,
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
        )
        elapsed = round(time.monotonic() - t0, 2)
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        m = re.search(r"\{[^{}]*\"playbook_id\"[^{}]*\}", content, flags=re.DOTALL)
        if m:
            parsed = json.loads(m.group(0))
            pb_id = str(parsed.get("playbook_id", "")).strip()
            if pb_id in PLAYBOOK_BY_ID:
                return {
                    "ok": True,
                    "engine": "local-4xt4-qwen3-coder-30b-a3b",
                    "elapsed_s": elapsed,
                    "playbook_id": pb_id,
                    "rationale": str(
                        parsed.get("rationale", "Classified by Local 4xT4 GPU")
                    ),
                }
        return {
            "ok": False,
            "engine": "local-4xt4",
            "elapsed_s": elapsed,
            "raw_excerpt": content[:240],
        }
    except Exception as exc:
        return {"ok": False, "engine": "local-4xt4", "error": str(exc)}


def translate_nl_query(query: str, engine_pref: str = "auto") -> Dict[str, Any]:
    """
    Translate a natural-language query into a structured Dry-Run Preview payload.
    Supports engine_pref: 'auto' (deterministic + local/kimi), 'kimi', 'local', 'deterministic'.
    """
    t0 = time.monotonic()
    det_id, det_conf, det_reason = deterministic_classify(query)
    chosen_id = det_id
    engine_used = "deterministic-fast-path"
    ai_trace: Dict[str, Any] = {
        "deterministic": {
            "playbook_id": det_id,
            "confidence": det_conf,
            "rationale": det_reason,
        }
    }

    if engine_pref == "kimi":
        kimi_res = call_kimi_classifier(query, timeout=25.0)
        ai_trace["kimi"] = kimi_res
        if kimi_res.get("ok"):
            chosen_id = kimi_res["playbook_id"]
            engine_used = "kimi-code-cli (/home/mboyle/.local/bin/kimi)"
    elif engine_pref == "local":
        loc_res = call_local_llm_classifier(query, timeout=10.0)
        ai_trace["local_4xt4"] = loc_res
        if loc_res.get("ok"):
            chosen_id = loc_res["playbook_id"]
            engine_used = "local-4xt4 (qwen3-coder-30b-a3b)"
    elif engine_pref == "auto":
        # If deterministic confidence < 0.95, consult Local 4xT4 then Kimi CLI
        if det_conf < 0.95:
            loc_res = call_local_llm_classifier(query, timeout=6.0)
            ai_trace["local_4xt4"] = loc_res
            if loc_res.get("ok"):
                chosen_id = loc_res["playbook_id"]
                engine_used = "local-4xt4 + deterministic-guard"
            else:
                kimi_res = call_kimi_classifier(query, timeout=18.0)
                ai_trace["kimi"] = kimi_res
                if kimi_res.get("ok"):
                    chosen_id = kimi_res["playbook_id"]
                    engine_used = "kimi-code-cli + deterministic-guard"

    pb = PLAYBOOK_BY_ID.get(chosen_id, PLAYBOOK_BY_ID["lowest_5h_quota_pool"])
    params = extract_parameters(query, pb["id"])

    # Build concrete preview command string and target node
    cmd_str = pb["command_preview"]
    target_node = pb["target_node"]
    if pb["id"] == "vsan_disk_groups_esxi":
        host = params.get("host", "esxi01")
        host_ips = {
            "esxi01": "10.0.20.41",
            "esxi02": "10.0.20.42",
            "esxi03": "10.0.20.43",
            "esxi04": "10.0.20.44",
        }
        target_node = f"{host}.boylenet.themfboyles.org ({host_ips.get(host, '10.0.20.41')}) via :4091 Hardware Telemetry"
        cmd_str = f"bd-ops --execute --playbook vsan_disk_groups_esxi --host {host}"
    elif pb["id"] == "semantic_search_fleet":
        term = params.get("search_term", "O1740 dynamic capability routing")
        cmd_str = f"/home/mboyle/bin/bd-semantic-search {json.dumps(term)} --top-k 5"

    elapsed_ms = round((time.monotonic() - t0) * 1000.0, 1)
    return {
        "rc": 0,
        "mode": "DRY-RUN PREVIEW",
        "timestamp": utc_now(),
        "query": query,
        "playbook_id": pb["id"],
        "title": pb["title"],
        "tool": pb["tool"],
        "binary": pb["binary"],
        "safety_class": pb["safety_class"],
        "risk_level": pb["risk_level"],
        "target_node": target_node,
        "command": cmd_str,
        "params": params,
        "description": pb["description"],
        "engine_used": engine_used,
        "translation_ms": elapsed_ms,
        "ai_trace": ai_trace,
    }


def record_ops_history(entry: Dict[str, Any]) -> None:
    try:
        with HISTORY_LOCK:
            with open(HISTORY_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def load_ops_history(limit: int = 20) -> List[Dict[str, Any]]:
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        out: List[Dict[str, Any]] = []
        for ln in reversed(lines[-limit:]):
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []


def execute_verified_playbook(
    playbook_id: str, params: Optional[Dict[str, str]] = None, query: str = ""
) -> Dict[str, Any]:
    """
    Strictly executes ONLY pre-vetted playbooks in PLAYBOOK_BY_ID.
    Never executes arbitrary shell strings.
    """
    params = params or {}
    if playbook_id not in PLAYBOOK_BY_ID:
        return {"rc": 1, "error": f"Unknown or unverified playbook_id: {playbook_id}"}

    pb = PLAYBOOK_BY_ID[playbook_id]
    t0 = time.monotonic()
    stdout_str = ""
    stderr_str = ""
    rc = 0
    structured_data: Any = None

    try:
        if playbook_id == "gpu_temps_all":
            # Fetch live JSON from :4010/status + format crisp table
            data = http_get_json("http://127.0.0.1:4010/status", timeout=10.0)
            nodes = data.get("nodes", [])
            lines = [
                "==========================================================================================",
                f" BOYLENET 4x TESLA T4 GPU CLUSTER TELEMETRY (active_model={data.get('active_model')} | tier={data.get('effective_tier')})",
                "==========================================================================================",
                f" {'NODE':<14} {'MGMT IP':<13} {'ROCE IP':<13} {'TEMP':<8} {'VRAM MiB':<15} {'POWER':<9} {'DDR4 RAM GiB':<16} {'STATUS'}",
                "-" * 90,
            ]
            for n in nodes:
                name = n.get("node", "?")
                mip = n.get("mgmt_ip", "?")
                rip = n.get("rpc_ip", "?")
                temp = f"{n.get('temp_c', 0)}°C"
                vram = f"{n.get('vram_used_mib', 0)}/{n.get('vram_total_mib', 15360)}"
                pwr = f"{n.get('power_w', 0):.1f}W"
                ram = f"{n.get('ddr4_ram_used_gib', 0):.1f}/{n.get('ddr4_ram_total_gib', 0):.1f}"
                st = (
                    "ONLINE (rc=0)"
                    if n.get("probe_rc") == 0
                    else f"DEGRADED (rc={n.get('probe_rc')})"
                )
                lines.append(
                    f" {name:<14} {mip:<13} {rip:<13} {temp:<8} {vram:<15} {pwr:<9} {ram:<16} {st}"
                )
            lines.append("=" * 90)
            stdout_str = "\n".join(lines)
            structured_data = {
                "active_model": data.get("active_model"),
                "effective_tier": data.get("effective_tier"),
                "nodes": nodes,
            }

        elif playbook_id == "vsan_disk_groups_esxi":
            host_filter = str(params.get("host", "esxi01")).lower().strip()
            hw = http_get_json("http://127.0.0.1:4091/api/hardware", timeout=12.0)
            vsan = hw.get("vsan", {})
            hosts = hw.get("esxi_hosts", [])
            lines = [
                "==========================================================================================",
                f" BOYLENET vSAN DATASTORE & DISK GROUP INSPECTOR (Filter: {host_filter})",
                "==========================================================================================",
                f" Datastore : {vsan.get('name', 'vsanDatastore')} | Accessible: {vsan.get('accessible')}",
                f" Capacity  : {vsan.get('used_tib', 0):.2f} TiB used / {vsan.get('capacity_tib', 0):.2f} TiB total ({vsan.get('used_pct', 0)}% used, {vsan.get('free_tib', 0):.2f} TiB free)",
                f" Totals    : {vsan.get('total_disk_groups', 0)} Disk Groups | {vsan.get('total_cache_ssds', 0)} Cache SSDs | {vsan.get('total_capacity_disks', 0)} Capacity Disks",
                "-" * 90,
            ]
            matched_hosts = []
            for h in hosts:
                short = str(h.get("short", "")).lower()
                if host_filter not in ("all", "") and short != host_filter:
                    continue
                matched_hosts.append(h)
                lines.append(
                    f" Host: {h.get('name')} ({h.get('ip')}) | vSAN IP: {h.get('vsan_ip')} | iLO: {h.get('ilo_ip')} | Rack: {h.get('rack_u')}"
                )
                lines.append(
                    f"   Hardware : {h.get('vendor')} {h.get('model')} | CPU: {h.get('cpu_pct')}% | RAM: {h.get('memory_gib_used')}/{h.get('memory_gib_total')} GiB ({h.get('memory_pct')}%)"
                )
                lines.append(
                    f"   vSAN DGs : {h.get('vsan_dg_count')} Disk Groups | {h.get('vsan_ssd_count')} Cache SSDs | {h.get('vsan_cap_disk_count')} Capacity Disks"
                )
                for idx, dg in enumerate(h.get("vsan_disk_groups", []), 1):
                    lines.append(
                        f"     [Disk Group #{idx}] Cache SSD: {dg.get('ssd')} -> {dg.get('capacity_disk_count')} Capacity Disks:"
                    )
                    for cd in dg.get("capacity_disks", []):
                        lines.append(f"        - {cd}")
            lines.append("=" * 90)
            stdout_str = "\n".join(lines)
            structured_data = {"vsan": vsan, "hosts": matched_hosts}

        elif playbook_id in (
            "switch_tier1_cyberstrike",
            "switch_tier1_qwen3",
            "switch_tier2_deepseek70b",
        ):
            if playbook_id == "switch_tier1_cyberstrike":
                cmd = [
                    "/home/mboyle/bin/bd-tier-switch",
                    "tier1",
                    "cyberstrike-offsec-35b",
                ]
            elif playbook_id == "switch_tier1_qwen3":
                cmd = [
                    "/home/mboyle/bin/bd-tier-switch",
                    "tier1",
                    "qwen3-coder-30b-a3b",
                ]
            else:
                cmd = [
                    "/home/mboyle/bin/bd-tier-switch",
                    "tier2",
                    "deepseek-r1-distill-llama-70b",
                ]
            p = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            rc = p.returncode
            stdout_str = p.stdout.strip()
            stderr_str = p.stderr.strip()

        elif playbook_id == "warm_ci_ramdisk":
            cmd = ["/home/mboyle/bin/bd-remote-pytest-turbo", "--warm"]
            if params.get("node"):
                cmd.extend(["--node", params["node"]])
            p = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            rc = p.returncode
            stdout_str = p.stdout.strip()
            stderr_str = p.stderr.strip()

        elif playbook_id == "audit_ci_ramdisk":
            cmd = ["/home/mboyle/bin/bd-remote-pytest-turbo", "--audit"]
            p = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            rc = p.returncode
            stdout_str = p.stdout.strip()
            stderr_str = p.stderr.strip()

        elif playbook_id == "lowest_5h_quota_pool":
            cmd = ["/home/mboyle/bin/bd-pool-autobalancer", "--status", "--no-color"]
            p = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            rc = p.returncode
            stdout_str = p.stdout.strip()
            stderr_str = p.stderr.strip()
            try:
                with open(
                    "/var/tmp/bd-pool-autobalancer.json", "r", encoding="utf-8"
                ) as f:
                    structured_data = json.load(f)
            except Exception:
                pass

        elif playbook_id == "sentinel_health_matrix":
            st = http_get_json("http://127.0.0.1:4099/api/status", timeout=10.0)
            unhealthy = [
                s for s in st.get("services", []) if not s.get("healthy", True)
            ]
            lines = [
                "==========================================================================================",
                f" BOYLENET INFRA SENTINEL (:4099) — {st.get('healthy_services')}/{st.get('total_services')} HEALTHY ({st.get('uptime_pct')}% Uptime)",
                "==========================================================================================",
                f" Status: {st.get('status', 'ok').upper()} | Sweep Latency: {st.get('last_sweep_duration_ms')}ms | Total Self-Heals: {st.get('total_self_heals')}",
            ]
            if unhealthy:
                lines.append(" Unhealthy / Degraded Services:")
                for u in unhealthy:
                    lines.append(
                        f"   - [{u.get('category')}] {u.get('name')} ({u.get('id')}): {u.get('detail')}"
                    )
            else:
                lines.append(" All 83 monitored services are HEALTHY (0 unhealthy).")
            lines.append("=" * 90)
            stdout_str = "\n".join(lines)
            structured_data = st

        elif playbook_id == "sentinel_heal_all":
            res = http_post_json("http://127.0.0.1:4099/api/heal-now", {}, timeout=35.0)
            stdout_str = json.dumps(res, indent=2)
            structured_data = res

        elif playbook_id == "vault_curator_pairs":
            cmd = ["/home/mboyle/bin/bd-vault-curator", "--pairs"]
            p = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            rc = p.returncode
            stdout_str = p.stdout.strip()
            stderr_str = p.stderr.strip()

        elif playbook_id == "semantic_search_fleet":
            term = str(
                params.get("search_term") or query or "O1740 dynamic capability routing"
            )
            cmd = ["/home/mboyle/bin/bd-semantic-search", term, "--top-k", "5"]
            p = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            rc = p.returncode
            stdout_str = p.stdout.strip()
            stderr_str = p.stderr.strip()

    except Exception as exc:
        rc = 1
        stderr_str = str(exc)

    elapsed_s = round(time.monotonic() - t0, 2)
    result = {
        "rc": rc,
        "mode": "EXECUTED",
        "timestamp": utc_now(),
        "playbook_id": playbook_id,
        "title": pb["title"],
        "tool": pb["tool"],
        "safety_class": pb["safety_class"],
        "target_node": pb["target_node"],
        "params": params,
        "query": query or pb["sample_query"],
        "elapsed_s": elapsed_s,
        "stdout": stdout_str,
        "stderr": stderr_str,
        "structured": structured_data,
    }
    record_ops_history(
        {
            "timestamp": result["timestamp"],
            "playbook_id": playbook_id,
            "title": pb["title"],
            "safety_class": pb["safety_class"],
            "query": result["query"],
            "rc": rc,
            "elapsed_s": elapsed_s,
        }
    )
    return result


# ---------------------------------------------------------------------------
# Sleek Glassmorphic HTML UI for Natural-Language Ops Shell (:4089)
# ---------------------------------------------------------------------------
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Boylenet Natural-Language Ops Shell (:4089)</title>
<style>
  :root {
    --bg: #050811;
    --panel: rgba(13, 19, 34, 0.88);
    --card: rgba(19, 28, 49, 0.78);
    --border: rgba(56, 189, 248, 0.22);
    --cyan: #00e5ff;
    --emerald: #10b981;
    --amber: #f59e0b;
    --rose: #f43f5e;
    --purple: #a855f7;
    --text: #f1f5f9;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: radial-gradient(circle at 15% 10%, #0f172a 0%, #050811 65%);
    color: var(--text);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    min-height: 100vh;
  }
  header {
    padding: 18px 28px;
    border-bottom: 1px solid var(--border);
    background: rgba(8, 13, 24, 0.92);
    backdrop-filter: blur(14px);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .brand-badge {
    background: linear-gradient(135deg, #00e5ff, #3b82f6);
    color: #040814;
    font-weight: 800;
    padding: 8px 12px;
    border-radius: 10px;
    letter-spacing: 0.6px;
    font-size: 0.85rem;
  }
  .brand h1 {
    margin: 0;
    font-size: 1.25rem;
    letter-spacing: -0.3px;
  }
  .brand p {
    margin: 2px 0 0;
    font-size: 0.82rem;
    color: var(--muted);
  }
  .nav-pills {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .nav-pills a {
    color: var(--cyan);
    text-decoration: none;
    font-size: 0.8rem;
    padding: 6px 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.7);
  }
  .nav-pills a:hover {
    border-color: var(--cyan);
    background: rgba(0, 229, 255, 0.12);
  }
  main {
    max-width: 1440px;
    margin: 0 auto;
    padding: 24px;
    display: grid;
    grid-template-columns: 1.35fr 0.95fr;
    gap: 22px;
  }
  @media (max-width: 1024px) {
    main { grid-template-columns: 1fr; }
  }
  .panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px;
    box-shadow: 0 12px 34px rgba(0, 0, 0, 0.45);
  }
  .panel h2 {
    margin: 0 0 14px;
    font-size: 1.02rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: #e2e8f0;
  }
  .nl-box {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }
  .nl-input {
    flex: 1;
    min-width: 260px;
    background: #080d1a;
    border: 1px solid rgba(56, 189, 248, 0.35);
    color: var(--text);
    padding: 13px 16px;
    border-radius: 10px;
    font-size: 0.96rem;
    outline: none;
  }
  .nl-input:focus {
    border-color: var(--cyan);
    box-shadow: 0 0 16px rgba(0, 229, 255, 0.22);
  }
  select.engine-select {
    background: #080d1a;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0 12px;
    font-size: 0.85rem;
  }
  .btn {
    border: none;
    border-radius: 10px;
    padding: 12px 18px;
    font-weight: 700;
    cursor: pointer;
    font-size: 0.88rem;
    transition: all 0.16s ease;
  }
  .btn-preview {
    background: linear-gradient(135deg, #00e5ff, #0284c7);
    color: #020617;
  }
  .btn-exec {
    background: linear-gradient(135deg, #10b981, #059669);
    color: #022c22;
  }
  .btn:hover { transform: translateY(-1px); filter: brightness(1.08); }
  .presets-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 10px;
    margin-top: 16px;
  }
  .preset-chip {
    background: var(--card);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 10px;
    padding: 10px 12px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .preset-chip:hover {
    border-color: var(--cyan);
    background: rgba(0, 229, 255, 0.08);
  }
  .preset-chip .q {
    font-size: 0.85rem;
    font-weight: 600;
    color: #f8fafc;
    margin-bottom: 5px;
  }
  .preset-chip .meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.73rem;
    color: var(--muted);
  }
  .badge {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.4px;
  }
  .badge-ro {
    background: rgba(16, 185, 129, 0.16);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.4);
  }
  .badge-rw {
    background: rgba(245, 158, 11, 0.18);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.45);
  }
  .preview-card {
    margin-top: 18px;
    background: rgba(9, 14, 26, 0.92);
    border: 1px solid rgba(0, 229, 255, 0.35);
    border-radius: 12px;
    padding: 16px;
  }
  .kv-row {
    display: grid;
    grid-template-columns: 150px 1fr;
    padding: 6px 0;
    border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    font-size: 0.86rem;
  }
  .kv-row .k { color: var(--muted); font-weight: 600; }
  .kv-row .v { color: var(--text); font-family: 'JetBrains Mono', monospace; word-break: break-all; }
  pre.terminal {
    background: #03060c;
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-radius: 10px;
    padding: 14px;
    color: #a7f3d0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    overflow-x: auto;
    max-height: 440px;
    white-space: pre-wrap;
  }
  .history-item {
    padding: 10px 12px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.12);
    font-size: 0.82rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }
</style>
</head>
<body>
<header>
  <div class="brand">
    <span class="brand-badge">OPS SHELL :4089</span>
    <div>
      <h1>Boylenet Natural-Language Ops Shell</h1>
      <p>Kimi Code CLI + Local 4xT4 GPU Intent Translator • Dry-Run Safety Classification • Verified Playbook Runner</p>
    </div>
  </div>
  <div class="nav-pills">
    <a href="http://dashy.boylenet.themfboyles.org">Dashy :4080</a>
    <a href="http://mobile.boylenet.themfboyles.org">Mobile PWA :4086</a>
    <a href="http://cloud.boylenet.themfboyles.org">Cloud Burst :4090</a>
    <a href="http://hardware.boylenet.themfboyles.org">Hardware :4091</a>
    <a href="http://sentinel.boylenet.themfboyles.org">Sentinel :4099</a>
    <a href="/health">Health JSON</a>
  </div>
</header>

<main>
  <section class="panel">
    <h2>
      <span>1. Natural-Language Infrastructure Command Translator</span>
      <span id="status-indicator" style="font-size:0.78rem;color:var(--cyan);">Ready • Argon-4 Shield Active</span>
    </h2>
    <div class="nl-box">
      <input id="nl-query" class="nl-input" type="text"
        value="check GPU temps across all 4 T4 nodes"
        placeholder="e.g., check GPU temps across all 4 T4 nodes, show vSAN disk groups on esxi01, switch Tier 1 Alpha to CyberStrike 35B..." />
      <select id="nl-engine" class="engine-select">
        <option value="auto">Engine: Auto (Fast-Path + Local 4xT4 + Kimi)</option>
        <option value="kimi">Engine: Kimi Code CLI (kimi -p)</option>
        <option value="local">Engine: Local 4xT4 (Qwen3-Coder-30B)</option>
        <option value="deterministic">Engine: Deterministic Guard Only</option>
      </select>
      <button class="btn btn-preview" onclick="runPreview()">Dry-Run Preview</button>
    </div>

    <div class="preview-card" id="preview-card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <strong id="pv-title" style="color:var(--cyan);font-size:0.98rem;">Dry-Run Preview Ready</strong>
        <span id="pv-badge" class="badge badge-ro">READ-ONLY</span>
      </div>
      <div class="kv-row"><div class="k">Playbook ID</div><div class="v" id="pv-id">-</div></div>
      <div class="kv-row"><div class="k">Target Tool</div><div class="v" id="pv-tool">-</div></div>
      <div class="kv-row"><div class="k">Target Node(s)</div><div class="v" id="pv-node">-</div></div>
      <div class="kv-row"><div class="k">Safety / Risk</div><div class="v" id="pv-risk">-</div></div>
      <div class="kv-row"><div class="k">Exact Command</div><div class="v" id="pv-cmd" style="color:#38bdf8;">-</div></div>
      <div class="kv-row"><div class="k">Translator Engine</div><div class="v" id="pv-engine">-</div></div>
      <div style="margin-top:14px;display:flex;gap:12px;align-items:center;justify-content:space-between;">
        <span id="pv-desc" style="font-size:0.8rem;color:var(--muted);">Click "Execute Verified Playbook" to run this pre-vetted operation.</span>
        <button class="btn btn-exec" id="btn-execute" onclick="executeCurrentPlaybook()">Execute Verified Playbook</button>
      </div>
    </div>

    <h2 style="margin-top:22px;">
      <span>2. Live Execution Output & Telemetry Receipt</span>
      <span id="exec-meta" style="font-size:0.78rem;color:var(--emerald);"></span>
    </h2>
    <pre class="terminal" id="exec-output">Select a preset or click "Dry-Run Preview" -> "Execute Verified Playbook" to view live output.</pre>
  </section>

  <section class="panel">
    <h2><span>Pre-Vetted Playbook Presets Library (<span id="preset-count">0</span>)</span><span style="font-size:0.76rem;color:var(--muted);">1-Click Load & Preview</span></h2>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;" id="ops-filter-bar">
      <button class="btn ops-filter-btn" data-filter="ALL" style="padding:6px 12px;font-size:0.76rem;background:rgba(0,229,255,0.18);color:var(--cyan);border:1px solid var(--cyan);" onclick="setOpsFilter('ALL', this)">ALL</button>
      <button class="btn ops-filter-btn" data-filter="READ-ONLY" style="padding:6px 12px;font-size:0.76rem;background:rgba(15,23,42,0.8);color:var(--text);border:1px solid var(--border);" onclick="setOpsFilter('READ-ONLY', this)">🟢 READ-ONLY</button>
      <button class="btn ops-filter-btn" data-filter="STATE-CHANGE" style="padding:6px 12px;font-size:0.76rem;background:rgba(15,23,42,0.8);color:var(--text);border:1px solid var(--border);" onclick="setOpsFilter('STATE-CHANGE', this)">🟠 STATE-CHANGE</button>
    </div>
    <input id="preset-search" class="nl-input" type="text" placeholder="Search playbooks by tool, safety class, or keyword..." oninput="renderPlaybookGrid()" style="width:100%;padding:9px 12px;font-size:0.84rem;margin-bottom:8px;" />
    <div class="presets-grid" id="presets-grid"></div>

    <h2 style="margin-top:24px;"><span>Recent Verified Ops Audit Trail</span><span style="font-size:0.76rem;color:var(--muted);">/var/tmp/bd-ops-history.jsonl</span></h2>
    <div id="history-list" style="max-height:290px;overflow-y:auto;"></div>
  </section>
</main>

<script>
let currentPreview = null;
let allPlaybooks = [];
let activeOpsFilter = 'ALL';

function setOpsFilter(f, btn) {
  activeOpsFilter = f;
  document.querySelectorAll('.ops-filter-btn').forEach(b => {
    b.style.background = 'rgba(15,23,42,0.8)';
    b.style.color = 'var(--text)';
    b.style.borderColor = 'var(--border)';
  });
  if (btn) {
    btn.style.background = 'rgba(0,229,255,0.18)';
    btn.style.color = 'var(--cyan)';
    btn.style.borderColor = 'var(--cyan)';
  }
  renderPlaybookGrid();
}

function renderPlaybookGrid() {
  const grid = document.getElementById('presets-grid');
  grid.innerHTML = '';
  const q = ((document.getElementById('preset-search') && document.getElementById('preset-search').value) || '').toLowerCase().trim();
  const filtered = allPlaybooks.filter(pb => {
    if (activeOpsFilter !== 'ALL' && pb.safety_class !== activeOpsFilter) return false;
    if (!q) return true;
    const hay = [pb.id, pb.title, pb.tool, pb.sample_query, pb.safety_class, pb.description].join(' ').toLowerCase();
    return hay.includes(q);
  });
  const cnt = document.getElementById('preset-count');
  if (cnt) cnt.textContent = `${filtered.length}/${allPlaybooks.length}`;
  filtered.forEach(pb => {
    const div = document.createElement('div');
    div.className = 'preset-chip';
    const badgeCls = pb.safety_class === 'READ-ONLY' ? 'badge-ro' : 'badge-rw';
    div.innerHTML = `
      <div class="q">"${pb.sample_query}"</div>
      <div class="meta">
        <span>${pb.tool}</span>
        <span class="badge ${badgeCls}">${pb.safety_class}</span>
      </div>
    `;
    div.onclick = () => {
      document.getElementById('nl-query').value = pb.sample_query;
      runPreview();
    };
    grid.appendChild(div);
  });
}

async function loadPlaybooks() {
  const r = await fetch('/api/status');
  const d = await r.json();
  allPlaybooks = d.playbooks || [];
  renderPlaybookGrid();
  renderHistory(d.history || []);
}

function renderHistory(items) {
  const box = document.getElementById('history-list');
  if (!items.length) {
    box.innerHTML = '<div style="color:var(--muted);font-size:0.82rem;padding:8px;">No operations executed yet in this session.</div>';
    return;
  }
  box.innerHTML = items.map(it => {
    const cls = it.safety_class === 'READ-ONLY' ? 'badge-ro' : 'badge-rw';
    return `<div class="history-item">
      <div>
        <div style="font-weight:600;color:#e2e8f0;">${it.title || it.playbook_id}</div>
        <div style="color:var(--muted);font-size:0.75rem;">"${it.query}" • ${it.timestamp}</div>
      </div>
      <div style="text-align:right;">
        <span class="badge ${cls}">${it.safety_class}</span>
        <div style="font-size:0.74rem;color:#34d399;margin-top:3px;">rc=${it.rc} (${it.elapsed_s}s)</div>
      </div>
    </div>`;
  }).join('');
}

async function runPreview() {
  const q = document.getElementById('nl-query').value.trim();
  const eng = document.getElementById('nl-engine').value;
  document.getElementById('status-indicator').textContent = 'Translating via ' + eng + '...';
  const r = await fetch('/api/translate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({query: q, engine: eng})
  });
  const d = await r.json();
  currentPreview = d;
  document.getElementById('pv-title').textContent = d.title || 'Dry-Run Preview';
  const badge = document.getElementById('pv-badge');
  badge.textContent = d.safety_class;
  badge.className = 'badge ' + (d.safety_class === 'READ-ONLY' ? 'badge-ro' : 'badge-rw');
  document.getElementById('pv-id').textContent = d.playbook_id;
  document.getElementById('pv-tool').textContent = d.tool + ' (' + d.binary + ')';
  document.getElementById('pv-node').textContent = d.target_node;
  document.getElementById('pv-risk').textContent = d.safety_class + ' • ' + d.risk_level;
  document.getElementById('pv-cmd').textContent = d.command;
  document.getElementById('pv-engine').textContent = `${d.engine_used} (${d.translation_ms}ms)`;
  document.getElementById('pv-desc').textContent = d.description;
  document.getElementById('status-indicator').textContent = 'Dry-Run Preview Verified';
}

async function executeCurrentPlaybook() {
  if (!currentPreview) {
    await runPreview();
  }
  const out = document.getElementById('exec-output');
  out.textContent = `[Executing Verified Playbook: ${currentPreview.playbook_id}]\\nCommand: ${currentPreview.command}\\nTarget: ${currentPreview.target_node}\\nPlease wait...`;
  const r = await fetch('/api/execute', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      playbook_id: currentPreview.playbook_id,
      params: currentPreview.params || {},
      query: currentPreview.query
    })
  });
  const d = await r.json();
  document.getElementById('exec-meta').textContent = `rc=${d.rc} • ${d.elapsed_s}s • ${d.timestamp}`;
  out.textContent = (d.stdout || '') + (d.stderr ? '\\n[STDERR]\\n' + d.stderr : '');
  loadPlaybooks();
}

window.addEventListener('DOMContentLoaded', async () => {
  await loadPlaybooks();
  await runPreview();
});
</script>
</body>
</html>
"""


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class OpsRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send_json(self, code: int, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Argon4-Shield", "ENFORCED")
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, code: int, html: str) -> None:
        raw = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Argon4-Shield", "ENFORCED")
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
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "bd-ops-web",
                    "port": PORT,
                    "url": "http://ops.boylenet.themfboyles.org",
                    "playbooks_count": len(PLAYBOOKS),
                    "kimi_cli_present": os.path.isfile(KIMI_BIN),
                    "litellm_gateway": LITELLM_URL,
                    "safety_modes": ["READ-ONLY", "STATE-CHANGE"],
                    "timestamp": utc_now(),
                },
            )
            return
        if path in ("/api/status", "/api/playbooks"):
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "bd-ops-web",
                    "port": PORT,
                    "timestamp": utc_now(),
                    "playbooks": PLAYBOOKS,
                    "history": load_ops_history(20),
                },
            )
            return
        self._send_html(200, HTML_PAGE)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        length = int(self.headers.get("Content-Length", "0"))
        body_raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(body_raw.decode("utf-8")) if body_raw else {}
        except Exception as exc:
            self._send_json(400, {"rc": 1, "error": f"Invalid JSON: {exc}"})
            return

        if path == "/api/translate":
            query = str(body.get("query", "")).strip()
            engine = str(body.get("engine", "auto")).strip().lower()
            res = translate_nl_query(query, engine_pref=engine)
            self._send_json(200, res)
            return

        if path == "/api/execute":
            playbook_id = str(body.get("playbook_id", "")).strip()
            params = body.get("params") or {}
            query = str(body.get("query", "")).strip()
            if not playbook_id and query:
                tr = translate_nl_query(
                    query, engine_pref=str(body.get("engine", "auto"))
                )
                playbook_id = tr["playbook_id"]
                params = tr.get("params", {})
            res = execute_verified_playbook(playbook_id, params=params, query=query)
            self._send_json(200 if res.get("rc") == 0 else 500, res)
            return

        self._send_json(404, {"rc": 1, "error": f"Unknown endpoint {path}"})


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Boylenet Natural-Language Ops Shell (CLI + Web Server :4089)"
    )
    ap.add_argument("query", nargs="*", help="Natural-language infrastructure request")
    ap.add_argument("--serve", action="store_true", help="Run HTTP server on :4089")
    ap.add_argument("--port", type=int, default=PORT, help="HTTP port (default 4089)")
    ap.add_argument(
        "--dry-run", action="store_true", help="Show Dry-Run Preview without executing"
    )
    ap.add_argument(
        "--execute",
        "-x",
        action="store_true",
        help="Execute the matched verified playbook",
    )
    ap.add_argument(
        "--playbook", default="", help="Directly specify verified playbook_id"
    )
    ap.add_argument(
        "--host", default="", help="Optional ESXi host parameter (e.g. esxi01)"
    )
    ap.add_argument(
        "--engine", default="auto", choices=["auto", "kimi", "local", "deterministic"]
    )
    ap.add_argument(
        "--list-playbooks", action="store_true", help="List all pre-vetted playbooks"
    )
    ap.add_argument("--json", action="store_true", help="Output JSON")
    args = ap.parse_args()

    if args.list_playbooks:
        if args.json:
            print(json.dumps(PLAYBOOKS, indent=2))
        else:
            print(
                "=========================================================================================="
            )
            print(" BOYLENET NATURAL-LANGUAGE OPS SHELL — PRE-VETTED PLAYBOOKS (:4089)")
            print(
                "=========================================================================================="
            )
            for pb in PLAYBOOKS:
                print(
                    f' [{pb["safety_class"]:<12}] {pb["id"]:<26} | {pb["tool"]:<22} | "{pb["sample_query"]}"'
                )
            print(
                "=========================================================================================="
            )
        return 0

    query_str = " ".join(args.query).strip()
    if args.serve or (
        not query_str
        and not args.playbook
        and os.path.basename(sys.argv[0]) == "bd-ops-web.py"
    ):
        srv = ThreadedHTTPServer(("0.0.0.0", args.port), OpsRequestHandler)
        print(
            f"[bd-ops-web] Listening on http://0.0.0.0:{args.port} (http://ops.boylenet.themfboyles.org)",
            flush=True,
        )
        srv.serve_forever()
        return 0

    if not query_str and not args.playbook:
        ap.print_help()
        return 0

    preview = translate_nl_query(query_str or args.playbook, engine_pref=args.engine)
    if args.playbook and args.playbook in PLAYBOOK_BY_ID:
        pb = PLAYBOOK_BY_ID[args.playbook]
        preview["playbook_id"] = pb["id"]
        preview["title"] = pb["title"]
        preview["safety_class"] = pb["safety_class"]
    if args.host:
        preview.setdefault("params", {})["host"] = args.host

    if not args.execute:
        if args.json:
            print(json.dumps(preview, indent=2))
        else:
            print(
                "=========================================================================================="
            )
            print(f" DRY-RUN PREVIEW — {preview['title']}")
            print(
                "=========================================================================================="
            )
            print(f" Query          : {preview['query']}")
            print(f" Playbook ID    : {preview['playbook_id']}")
            print(
                f" Safety Class   : {preview['safety_class']} ({preview['risk_level']})"
            )
            print(f" Target Tool    : {preview['tool']} ({preview['binary']})")
            print(f" Target Node(s) : {preview['target_node']}")
            print(f" Exact Command  : {preview['command']}")
            print(
                f" Translator     : {preview['engine_used']} ({preview['translation_ms']}ms)"
            )
            print(
                "------------------------------------------------------------------------------------------"
            )
            print(" Tip: Re-run with --execute (-x) to run this verified playbook.")
            print(
                "=========================================================================================="
            )
        return 0

    exec_res = execute_verified_playbook(
        preview["playbook_id"],
        params=preview.get("params", {}),
        query=query_str,
    )
    if args.json:
        print(json.dumps(exec_res, indent=2))
    else:
        print(exec_res.get("stdout", ""))
        if exec_res.get("stderr"):
            print(exec_res["stderr"], file=sys.stderr)
    return int(exec_res.get("rc", 0))


if __name__ == "__main__":
    sys.exit(main())
