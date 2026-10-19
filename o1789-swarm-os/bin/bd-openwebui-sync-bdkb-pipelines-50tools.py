#!/usr/bin/env python3
"""
Boylenet OpenWebUI Master Synchronizer:
1. Embeds all 6 BD KB volumes (1024-d) into Qdrant collection `bd_master_kb` on 10.0.70.125:6333.
2. Synchronizes all 6 Native BD KB Knowledge Bases (`bd-kb-*`) + files + public access grants
   across BOTH .164:8090 (Controller) and .72:8080 (Vault A).
3. Registers Qdrant `bd_master_kb` in OpenWebUI External Knowledge connections & sources.
4. Connects OpenWebUI Admin -> Tools -> Pipelines (`http://10.0.70.164:4079/v1`) and registers
   all 8 Pipelines, 6 Local Image/Vision Generator Models, and 5 Local Speech/Audio Models.
5. Registers Toolkits #31 through #50 (expanding native `tool` table to 50 High-ROI Toolkits #01-#50)
   and attaches them + BD KB to workspace models on both OpenWebUI instances.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

if "/home/mboyle/bin" not in sys.path:
    sys.path.insert(0, "/home/mboyle/bin")

import bd_openwebui_pipelines_bdkb_ext as bdkb_ext

# Import 1024-d embedding generator from bd-openwebui-tool-gateway.py
import importlib.util

_gw_spec = importlib.util.spec_from_file_location(
    "bd_openwebui_tool_gateway", "/home/mboyle/bin/bd-openwebui-tool-gateway.py"
)
_gw_mod = importlib.util.module_from_spec(_gw_spec)  # type: ignore[arg-type]
assert _gw_spec and _gw_spec.loader
_gw_spec.loader.exec_module(_gw_mod)
compute_hybrid_1024_embedding = _gw_mod.compute_hybrid_1024_embedding

QDRANT_URL = "http://10.0.70.125:6333"
QDRANT_COLLECTION = "bd_master_kb"
GATEWAY_URL = "http://10.0.70.164:4079"
STREAM_LOG = Path("/var/tmp/bd-headless-streams/agent99-pipelines-bdkb-50tools.log")

INSTANCES = [
    {
        "name": "OpenWebUI-Controller-164:8090",
        "base_url": "http://127.0.0.1:8090",
        "public_url": "http://openwebui.boylenet.themfboyles.org",
        "admin_id": "a12463df-370f-4948-b488-9437da254b15",
        "secret": "<REDACTED_BY_BOYLENET_SECRET_GUARD>",
        "ssh_host": None,
    },
    {
        "name": "OpenWebUI-VaultA-72:8080",
        "base_url": "http://10.0.70.72:8080",
        "public_url": "http://ai-webui.boylenet.themfboyles.org",
        "admin_id": "c1658bb0-ad7c-48c2-a18a-7c000dd6a04e",
        "secret": "<REDACTED_BY_BOYLENET_SECRET_GUARD>",
        "ssh_host": "10.0.70.72",
    },
]

BD_KB_DEFINITIONS = [
    {
        "id": "bd-kb-master",
        "name": "📚 [BD KB #00] Master Encyclopedia (BulkDownloader + 27-Node Boylenet + 86 Models + Rules 1-86)",
        "description": "Single-pane-of-glass Master Encyclopedia covering BulkDownloader, 27-node Boylenet cluster, 86-model vault, Fleet Rules 1-86, O1740 routing, and 50 toolkits.",
        "files": [
            "00-BD-KB-MASTER-ENCYCLOPEDIA.md",
            "01-BULKDOWNLOADER-ARCHITECTURE-AND-CONTRACTS.md",
            "02-BOYLENET-27NODE-CLUSTER-12U-RACK-VSAN-25GBE.md",
            "03-86-MODEL-VAULT-BENCHMARKS-AND-AIRGAP.md",
            "04-FLEET-LAW-RULES-1-86-AND-O1740-ROUTING.md",
            "05-CI-TAXONOMY-RECOVERY-AND-MCP-TOOLS.md",
        ],
    },
    {
        "id": "bd-kb-bulkdownloader",
        "name": "📦 [BD KB #01] BulkDownloader Architecture, Contracts, Cut Workflow & Ramdisk Pytest",
        "description": "BulkDownloader repository layout, yt-dlp pin invariant, Rule 22 sandbox paths, Cut Workflow, and /dev/shm ramdisk pytest execution.",
        "files": ["01-BULKDOWNLOADER-ARCHITECTURE-AND-CONTRACTS.md"],
    },
    {
        "id": "bd-kb-cluster-infra",
        "name": "🖧 [BD KB #02] Boylenet 27-Node Cluster, 12U Rack, VMware ESXi/vSAN & 25GbE Fabric",
        "description": "Full 27-node Boylenet hardware/IP/role table, 12U 36-inch rack physical layout, VMware ESXi 8.0 / vSAN 18TB NVMe, and UniFi 25GbE SFP28 fabric.",
        "files": ["02-BOYLENET-27NODE-CLUSTER-12U-RACK-VSAN-25GBE.md"],
    },
    {
        "id": "bd-kb-86-models",
        "name": "🧠 [BD KB #03] 86-Model Vault Catalog, SWE-bench / LiveCodeBench & Dual-Speed Airgap",
        "description": "Complete 86-model catalog across Vault A (.72), Vault B (.83), GPU Inference (.125), BattleStation (.137), and $1,000 Cloud Burst with dual-speed WAN airgap.",
        "files": ["03-86-MODEL-VAULT-BENCHMARKS-AND-AIRGAP.md"],
    },
    {
        "id": "bd-kb-fleet-law",
        "name": "⚖️ [BD KB #04] Fleet Law (Rules 1-86), O1740 Dynamic Routing & HUB-GATE",
        "description": "Authoritative Fleet Law Rules 1-86, Protocols A-F, O1740 Dynamic Capability Routing (POOL_STATE.tsv), HUB-GATE, and Rule 22 Anti-Hallucination Shield.",
        "files": ["04-FLEET-LAW-RULES-1-86-AND-O1740-ROUTING.md"],
    },
    {
        "id": "bd-kb-ci-and-uis",
        "name": "🛠️ [BD KB #05] CI Taxonomy, Great Train Recovery, 14 MCP Servers & 50 OpenWebUI Toolkits",
        "description": "BulkDownloader CI failure taxonomy (C1-C6), Great Train Recovery playbooks, 14 MCP servers, 128 skills, and 50 OpenWebUI toolkits.",
        "files": ["05-CI-TAXONOMY-RECOVERY-AND-MCP-TOOLS.md"],
    },
]


def log_stream(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"[{ts}] Agent-99: {msg}\n"
    STREAM_LOG.parent.mkdir(parents=True, exist_ok=True)
    with STREAM_LOG.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line.strip(), flush=True)


def make_jwt(user_id: str, secret: str) -> str:
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"id": user_id, "exp": int(time.time()) + 86400 * 7}).encode()
    ).rstrip(b"=")
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), header + b"." + payload, hashlib.sha256).digest()
    ).rstrip(b"=")
    return (header + b"." + payload + b"." + sig).decode()


def api_call(
    base_url: str,
    token: str,
    method: str,
    path: str,
    body: Any = None,
    timeout: int = 20,
) -> tuple[int, Any]:
    url = f"{base_url}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    data_bytes = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as exc:
        return 599, {"error": str(exc)}


def sync_qdrant_bd_master_kb() -> dict[str, Any]:
    chunks = bdkb_ext.load_bd_kb_chunks()
    # 1. Ensure collection exists
    req_create = urllib.request.Request(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}",
        data=json.dumps({"vectors": {"size": 1024, "distance": "Cosine"}}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req_create, timeout=10) as r:
        create_res = json.loads(r.read().decode())

    # 2. Build points with 1024-d embeddings
    points = []
    for idx, ch in enumerate(chunks, start=1):
        vec = compute_hybrid_1024_embedding(f"{ch['section_title']}\n{ch['content']}")
        points.append(
            {
                "id": idx,
                "vector": vec,
                "payload": {
                    "chunk_id": ch.get("chunk_id", f"chunk-{idx}"),
                    "book_id": ch.get("book_id", ""),
                    "book_name": ch["book_name"],
                    "section_title": ch["section_title"],
                    "text": ch["content"],
                    "content": ch["content"],
                    "source": f"/home/mboyle/bd-persist/bd-kb/{ch['book_name']}",
                    "metadata": {
                        "source": ch["book_name"],
                        "book_id": ch.get("book_id", ""),
                        "section": ch["section_title"],
                    },
                },
            }
        )

    req_upsert = urllib.request.Request(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points?wait=true",
        data=json.dumps({"points": points}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req_upsert, timeout=20) as r:
        upsert_res = json.loads(r.read().decode())

    # 3. Verify search
    qvec = compute_hybrid_1024_embedding("O1740 dynamic capability routing 27 nodes")
    req_search = urllib.request.Request(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/search",
        data=json.dumps({"vector": qvec, "limit": 3, "with_payload": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_search, timeout=10) as r:
        search_res = json.loads(r.read().decode())

    return {
        "collection": QDRANT_COLLECTION,
        "points_upserted": len(points),
        "create_status": create_res.get("status"),
        "upsert_status": upsert_res.get("status"),
        "verify_hits": len(search_res.get("result", [])),
        "top_hit_section": (
            search_res.get("result", [{}])[0].get("payload", {}).get("section_title")
            if search_res.get("result")
            else None
        ),
    }


def build_toolkit_source(
    tk_id: str,
    title: str,
    description: str,
    method_name: str,
    action_name: str,
    params_sig: str,
    payload_expr: str,
    docstring: str,
) -> str:
    return f'''"""
title: {title}
author: Boylenet Sovereign AI Architecture (Agent-99)
version: 2.5.0
description: {description}
"""

import json
import urllib.request
from typing import Any, Optional
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        gateway_url: str = Field(
            default="{GATEWAY_URL}",
            description="Boylenet Universal Tool & BD KB Gateway (:4079) base URL.",
        )
        timeout_seconds: int = Field(
            default=25,
            description="HTTP request timeout in seconds.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.citation = True

    def _call_gateway(self, action: str, payload: dict) -> str:
        url = f"{{self.valves.gateway_url.rstrip('/')}}/api/tool/{{action}}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={{"Content-Type": "application/json"}},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.valves.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception as exc:
            return json.dumps({{"ok": False, "toolkit": "{tk_id}", "action": action, "error": str(exc)}}, indent=2)

    def {method_name}(self, {params_sig}) -> str:
        """
        {docstring}
        """
        return self._call_gateway("{action_name}", {payload_expr})
'''


TOOLKITS_31_TO_50: list[dict[str, Any]] = [
    {
        "id": "tk_31_bd_knowledge_base_oracle",
        "name": "31_bd_knowledge_base_oracle — Master BD KB Instant Search & Fact Verifier",
        "description": "Search the authoritative 6-volume BD KB (BulkDownloader, 27-Node Boylenet Cluster, 86-Model Vault, Rules 1-86, O1740, CI Taxonomy & 50 Toolkits).",
        "method": "bd_kb_search",
        "action": "bd_kb_search",
        "params": 'query: str, book: str = "all", top_k: int = 5',
        "payload": '{"query": query, "book": book, "top_k": top_k}',
        "doc": "Query the Master BD KB across all 6 reference volumes and return ranked citations.",
    },
    {
        "id": "tk_32_fleet_law_and_rule_auditor",
        "name": "32_fleet_law_and_rule_auditor — Fleet Rules 1-86 Lookup & Compliance Verifier",
        "description": "Inspect Fleet Rules 1-86, Protocols A-F, Rule 22 sandbox paths, and verify rule compliance.",
        "method": "audit_fleet_rule",
        "action": "fleet_law_and_rule_auditor",
        "params": 'rule_number: str = "", query: str = ""',
        "payload": '{"rule_number": rule_number, "query": query}',
        "doc": "Look up exact Fleet Law rules (1-86) and verify compliance invariants.",
    },
    {
        "id": "tk_33_o1740_pool_and_seat_router",
        "name": "33_o1740_pool_and_seat_router — Live POOL_STATE.tsv & O1740 Dynamic Capability Router",
        "description": "Inspect live POOL_STATE.tsv and resolve optimal O1740 pool binding for Command Squad, Heavy Lifters, or Lightweight Investigators.",
        "method": "resolve_o1740_pool",
        "action": "o1740_pool_and_seat_router",
        "params": 'role_tier: str = "heavy_lifter"',
        "payload": '{"role_tier": role_tier}',
        "doc": "Resolve dynamic pool assignment from /home/mboyle/bd-persist/POOL_STATE.tsv per O1740.",
    },
    {
        "id": "tk_34_hivemind_persistent_memory_bank",
        "name": "34_hivemind_persistent_memory_bank — Cross-Session Fact & Lesson Memory Store/Recall",
        "description": "Recall or store persistent engineering facts, lessons, and architectural decisions in the Boylenet Hivemind Memory Bank.",
        "method": "hivemind_memory",
        "action": "hivemind_persistent_memory_bank",
        "params": 'action: str = "recall", query: str = "", content: str = "", tags: str = "boylenet,bdkb"',
        "payload": '{"action": action, "query": query, "content": content, "tags": tags}',
        "doc": "Recall, store, or check status of persistent Hivemind cross-session memory.",
    },
    {
        "id": "tk_35_caveman_token_compressor",
        "name": "35_caveman_token_compressor — Ultra-Dense Prompt/Context Compression & TOON Codec",
        "description": "Compress long prompts, logs, or markdown docs into high-density Caveman/TOON format while preserving all technical coordinates.",
        "method": "compress_context",
        "action": "caveman_token_compressor",
        "params": 'text: str, mode: str = "compress"',
        "payload": '{"text": text, "mode": mode}',
        "doc": "Compress text into Caveman ultra-dense representation and report token savings.",
    },
    {
        "id": "tk_36_bd_bus_wal_and_smt_consensus",
        "name": "36_bd_bus_wal_and_smt_consensus — Cross-Pool Event Bus WAL & JSON Consensus Evaluator",
        "description": "Read/publish cross-pool bd-bus WAL events and evaluate Rule 76 Protocol B BOARD/REFUTE JSON consensus.",
        "method": "bus_and_consensus",
        "action": "bd_bus_wal_and_smt_consensus",
        "params": 'action: str = "read", topic: str = "fleet-status", message: str = ""',
        "payload": '{"action": action, "topic": topic, "message": message}',
        "doc": "Read/publish bd-bus WAL messages or evaluate SMT consensus invariants.",
    },
    {
        "id": "tk_37_cut_train_and_worktree_inspector",
        "name": "37_cut_train_and_worktree_inspector — Cut Train Status, Scratchpad Worktrees & Gate Auditor",
        "description": "Inspect BulkDownloader cut train status, Rule 83 persistent worktrees in bd-local-wt and bd-cuts, and gate receipts.",
        "method": "inspect_worktrees_and_cuts",
        "action": "cut_train_and_worktree_inspector",
        "params": 'target: str = "all"',
        "payload": '{"target": target}',
        "doc": "List active Git worktrees in bd-local-wt / bd-cuts and verify Rule 22/83 hygiene.",
    },
    {
        "id": "tk_38_langfuse_and_litellm_telemetry",
        "name": "38_langfuse_and_litellm_telemetry — LiteLLM :4000 Spend, Latency & Langfuse Trace Inspector",
        "description": "Inspect live LiteLLM (:4000) model catalog, health, spend/latency metrics, and Langfuse (:3091) telemetry status.",
        "method": "inspect_llm_telemetry",
        "action": "langfuse_and_litellm_telemetry",
        "params": 'view: str = "summary"',
        "payload": '{"view": view}',
        "doc": "Query LiteLLM (:4000) and Langfuse (:3091) live health and model routing telemetry.",
    },
    {
        "id": "tk_39_prometheus_grafana_loki_observability",
        "name": "39_prometheus_grafana_loki_observability — Cluster Metrics (PromQL) & Log Query Engine",
        "description": "Execute live PromQL queries against Prometheus (10.0.70.168:9090) and inspect Grafana/Loki observability across 27 nodes.",
        "method": "query_prometheus_metrics",
        "action": "prometheus_grafana_loki_observability",
        "params": 'promql: str = "up"',
        "payload": '{"promql": promql}',
        "doc": "Run a PromQL query against Prometheus on mon-core01 (10.0.70.168:9090).",
    },
    {
        "id": "tk_40_nfs_storage_and_blob_cas_manager",
        "name": "40_nfs_storage_and_blob_cas_manager — NFS Storage, /var/tmp/bd-blobs CAS & Disk Analyzer",
        "description": "Inspect Rule 80 /var/tmp/bd-blobs/<sha256>.log CAS pointers, store/dereference blobs, and check NVMe/NFS/ramdisk capacity.",
        "method": "manage_blob_cas_and_storage",
        "action": "nfs_storage_and_blob_cas_manager",
        "params": 'action: str = "status", sha256: str = "", content: str = ""',
        "payload": '{"action": action, "sha256": sha256, "content": content}',
        "doc": "Inspect disk mounts or read/write Rule 80 /var/tmp/bd-blobs CAS objects.",
    },
    {
        "id": "tk_41_redis_state_and_cache_inspector",
        "name": "41_redis_state_and_cache_inspector — Redis Cache & Queue Health Inspector",
        "description": "Inspect Redis cache endpoints on .164 and db-redis01 (.172) for queue depth, key patterns, and latency.",
        "method": "inspect_redis_cache",
        "action": "redis_state_and_cache_inspector",
        "params": 'host: str = "127.0.0.1", port: int = 6379, pattern: str = "*"',
        "payload": '{"host": host, "port": port, "pattern": pattern}',
        "doc": "Check Redis PING and sample keys on Controller or db-redis01.",
    },
    {
        "id": "tk_42_ssh_27node_parallel_fabric_runner",
        "name": "42_ssh_27node_parallel_fabric_runner — Safe Read-Only Parallel Command Runner Across 27 Nodes",
        "description": "Run read-only diagnostic commands (uptime, free -h, df -h, nvidia-smi, hostname) across Boylenet cluster nodes.",
        "method": "run_cluster_readonly_probe",
        "action": "ssh_27node_parallel_fabric_runner",
        "params": 'nodes: str = "10.0.70.164,10.0.70.72,10.0.70.83,10.0.70.125", command: str = "uptime"',
        "payload": '{"nodes": nodes, "command": command}',
        "doc": "Execute a safe read-only probe across selected Boylenet cluster nodes.",
    },
    {
        "id": "tk_43_systemd_and_daemon_healer",
        "name": "43_systemd_and_daemon_healer — Fleet Daemon Health & Service Inspector",
        "description": "Check systemd status and recent journal logs for critical Boylenet services (litellm, qdrant-portal, docker, open-webui).",
        "method": "inspect_systemd_daemons",
        "action": "systemd_and_daemon_healer",
        "params": 'service: str = "all"',
        "payload": '{"service": service}',
        "doc": "Inspect status of Boylenet systemd units and daemons.",
    },
    {
        "id": "tk_44_git_log_blame_and_diff_detective",
        "name": "44_git_log_blame_and_diff_detective — Deep Git History, Pickaxe Search & Blame Inspector",
        "description": "Perform read-only Git log, pickaxe (-S) search, show, or diff against declared base in BulkDownloader.",
        "method": "git_detective",
        "action": "git_log_blame_and_diff_detective",
        "params": 'repo_path: str = "/home/mboyle/BulkDownloader", mode: str = "log", target: str = "HEAD", limit: int = 10',
        "payload": '{"repo_path": repo_path, "mode": mode, "target": target, "limit": limit}',
        "doc": "Run read-only git log, pickaxe, show, or diff inspection.",
    },
    {
        "id": "tk_45_json_yaml_toml_schema_validator",
        "name": "45_json_yaml_toml_schema_validator — Config Syntax, JSON Schema & OpenAPI 3.1 Validator",
        "description": "Validate JSON, YAML, or TOML payloads and verify OpenAPI 3.1 structural compliance.",
        "method": "validate_config_payload",
        "action": "json_yaml_toml_schema_validator",
        "params": 'content: str, format: str = "json"',
        "payload": '{"content": content, "format": format}',
        "doc": "Parse and validate JSON, YAML, or TOML configuration content.",
    },
    {
        "id": "tk_46_regex_and_jq_data_transformer",
        "name": "46_regex_and_jq_data_transformer — High-Speed Regex Extraction & JSON/JQ Transformer",
        "description": "Run Python regex extraction or jq transformation over structured or unstructured text.",
        "method": "transform_text_or_json",
        "action": "regex_and_jq_data_transformer",
        "params": 'text: str, pattern: str = "", jq_expr: str = ""',
        "payload": '{"text": text, "pattern": pattern, "jq_expr": jq_expr}',
        "doc": "Apply regex or jq expressions to extract structured fields.",
    },
    {
        "id": "tk_47_cryptography_hash_jwt_and_tls_inspector",
        "name": "47_cryptography_hash_jwt_and_tls_inspector — SHA256/HMAC/Base64, JWT Decoder & TLS Inspector",
        "description": "Compute SHA-256/SHA-512 hashes, decode JWT headers/claims, or inspect TLS certificates.",
        "method": "crypto_jwt_tls_inspect",
        "action": "cryptography_hash_jwt_and_tls_inspector",
        "params": 'mode: str = "sha256", data: str = "", host: str = ""',
        "payload": '{"mode": mode, "data": data, "host": host}',
        "doc": "Compute cryptographic digests, decode JWTs, or inspect TLS handshakes.",
    },
    {
        "id": "tk_48_model_arena_and_speed_benchmarker",
        "name": "48_model_arena_and_speed_benchmarker — Side-by-Side Local Model Latency & Tok/s Benchmarker",
        "description": "Benchmark latency and tokens/sec across local and cloud models on LiteLLM (:4000).",
        "method": "benchmark_models",
        "action": "model_arena_and_speed_benchmarker",
        "params": 'prompt: str = "Reply in one sentence confirming your model identity and node.", models: str = "local-164-32b-coder,vault-qwen3-coder-30b-a3b"',
        "payload": '{"prompt": prompt, "models": models}',
        "doc": "Run a side-by-side latency and throughput benchmark across LiteLLM models.",
    },
    {
        "id": "tk_49_prompt_architect_and_skill_synthesizer",
        "name": "49_prompt_architect_and_skill_synthesizer — System Prompt & SKILL.md Generator",
        "description": "Synthesize structured Boylenet SKILL.md files and high-precision system prompts grounded in BD KB.",
        "method": "synthesize_skill_or_prompt",
        "action": "prompt_architect_and_skill_synthesizer",
        "params": 'task_name: str, domain: str = "boylenet-engineering"',
        "payload": '{"task_name": task_name, "domain": domain}',
        "doc": "Generate a ready-to-use SKILL.md template and system prompt grounded in BD KB.",
    },
    {
        "id": "tk_50_boylenet_doctor_and_self_healer",
        "name": "50_boylenet_doctor_and_self_healer — One-Click End-to-End Cluster, Airgap, RAG, Pipelines & UI Doctor",
        "description": "Run a comprehensive end-to-end diagnostic across LiteLLM (:4000), Gateway/Pipelines (:4079), Qdrant (:6333), SearXNG (:8888), Voice (:4093), and both OpenWebUI nodes.",
        "method": "run_boylenet_doctor",
        "action": "boylenet_doctor_and_self_healer",
        "params": 'deep: bool = True',
        "payload": '{"deep": deep}',
        "doc": "Verify end-to-end health of all Boylenet AI endpoints, BD KB, Qdrant, Pipelines, and UIs.",
    },
]


def sync_instance(inst: dict[str, Any]) -> dict[str, Any]:
    name = inst["name"]
    base_url = inst["base_url"]
    token = make_jwt(inst["admin_id"], inst["secret"])
    ssh_host = inst["ssh_host"]

    # 1. Update Retrieval Embedding config -> http://10.0.70.164:4079 (1024-dim fast hybrid BGE-M3)
    emb_status, _ = api_call(
        base_url,
        token,
        "POST",
        "/api/v1/retrieval/embedding/update",
        {
            "RAG_EMBEDDING_ENGINE": "ollama",
            "RAG_EMBEDDING_MODEL": "bge-m3:latest",
            "RAG_EMBEDDING_BATCH_SIZE": 16,
            "ENABLE_ASYNC_EMBEDDING": True,
            "ollama_config": {"url": GATEWAY_URL, "key": "sk-fleet-local"},
            "openai_config": {"url": f"{GATEWAY_URL}/v1", "key": "sk-fleet-local"},
        },
    )

    # 2. Update OpenAI Config to include BOTH LiteLLM (:4000/v1) and Pipelines Server (:4079/v1)
    openai_cfg_body = {
        "ENABLE_OPENAI_API": True,
        "OPENAI_API_BASE_URLS": [
            "http://10.0.70.164:4000/v1",
            "http://10.0.70.164:4079/v1",
        ],
        "OPENAI_API_KEYS": [
            "sk-fleet-local",
            "sk-fleet-local",
        ],
        "OPENAI_API_CONFIGS": {
            "0": {
                "enable": True,
                "tags": [{"name": "LiteLLM-86-Models"}],
                "prefix_id": "",
                "model_ids": [],
                "connection_type": "external",
            },
            "1": {
                "enable": True,
                "tags": [{"name": "Boylenet-Pipelines-Image-Speech"}],
                "prefix_id": "",
                "model_ids": [],
                "connection_type": "local",
            },
        },
    }
    openai_status, _ = api_call(
        base_url, token, "POST", "/openai/config/update", openai_cfg_body
    )

    # 3. Ensure 6 OpenAPI Tool Server Suites are registered (including bdkb-50tools)
    _, cur_tool_servers = api_call(base_url, token, "GET", "/api/v1/configs/tool_servers")
    connections = (
        cur_tool_servers.get("TOOL_SERVER_CONNECTIONS", [])
        if isinstance(cur_tool_servers, dict)
        else []
    )
    bdkb_srv_id = "boylenet-bdkb-50tools-suite"
    if not any(isinstance(c, dict) and c.get("info", {}).get("id") == bdkb_srv_id for c in connections):
        connections.append(
            {
                "type": "openapi",
                "url": f"{GATEWAY_URL}/bdkb-50tools",
                "spec_type": "url",
                "spec": "",
                "path": "openapi.json",
                "auth_type": "none",
                "key": "",
                "config": {"enable": True, "access_control": None},
                "info": {
                    "id": bdkb_srv_id,
                    "name": "Boylenet BD KB Oracle & Toolkits #31-#50 Extended Power Suite (:4079)",
                    "description": "Master BD KB Search + Fleet Law 1-86, O1740 Pool Router, Hivemind, Caveman, Bus/SMT, Git Worktrees, Langfuse, Prometheus, NFS, Redis, SSH Mesh, Model Benchmarker, and Boylenet Doctor.",
                },
            }
        )
        api_call(
            base_url,
            token,
            "POST",
            "/api/v1/configs/tool_servers",
            {"TOOL_SERVER_CONNECTIONS": connections},
        )

    # 4. Register / Update Toolkits #31 through #50 via OpenWebUI /api/v1/tools/
    _, existing_tools_resp = api_call(base_url, token, "GET", "/api/v1/tools/")
    existing_ids = {
        t["id"] for t in (existing_tools_resp if isinstance(existing_tools_resp, list) else [])
    }

    registered_31_50 = 0
    for tk in TOOLKITS_31_TO_50:
        code = build_toolkit_source(
            tk_id=tk["id"],
            title=tk["name"],
            description=tk["description"],
            method_name=tk["method"],
            action_name=tk["action"],
            params_sig=tk["params"],
            payload_expr=tk["payload"],
            docstring=tk["doc"],
        )
        payload = {
            "id": tk["id"],
            "name": tk["name"],
            "content": code,
            "meta": {
                "description": tk["description"],
                "manifest": {
                    "title": tk["name"],
                    "author": "Boylenet Sovereign AI Architecture (Agent-99)",
                    "version": "2.5.0",
                },
            },
            "access_control": None,
        }
        if tk["id"] in existing_ids:
            st, _ = api_call(
                base_url, token, "POST", f"/api/v1/tools/id/{tk['id']}/update", payload
            )
        else:
            st, _ = api_call(base_url, token, "POST", "/api/v1/tools/create", payload)
        if st in (200, 201):
            registered_31_50 += 1

    # 5. Synchronize all 6 BD KB Knowledge Bases + Files + External Knowledge + Workspace Models in SQLite DB
    # We pass the 6 Markdown books and definitions to a container-side Python script so `knowledge`, `file`,
    # `knowledge_file`, `access_grant`, `config` (external_knowledge), and `model` tables are 100% populated.
    books_payload = {}
    for fname in BD_KB_DEFINITIONS[0]["files"]:
        fpath = bdkb_ext.BD_KB_DIR / fname
        books_payload[fname] = fpath.read_text(encoding="utf-8")

    db_sync_input = {
        "admin_id": inst["admin_id"],
        "kb_defs": BD_KB_DEFINITIONS,
        "books": books_payload,
        "pipelines": bdkb_ext.PIPELINES_CATALOG,
        "image_models": bdkb_ext.IMAGE_GENERATOR_MODELS,
        "speech_models": bdkb_ext.SPEECH_AUDIO_MODELS,
        "qdrant_url": QDRANT_URL,
        "qdrant_collection": QDRANT_COLLECTION,
    }

    container_script = r"""
import hashlib, json, os, sqlite3, sys, time, uuid
from pathlib import Path

data = json.loads(sys.stdin.read())
admin_id = data["admin_id"]
kb_defs = data["kb_defs"]
books = data["books"]
now = int(time.time())

uploads_dir = Path("/app/backend/data/uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)

con = sqlite3.connect("/app/backend/data/webui.db")
cur = con.cursor()

# 1. Write the 6 BD KB markdown files into /app/backend/data/uploads and upsert into `file` table
file_ids_by_name = {}
for fname, content in books.items():
    fid = "bdkb-file-" + fname.lower().replace(".md", "").replace("_", "-")
    dest = uploads_dir / f"{fid}_{fname}"
    dest.write_text(content, encoding="utf-8")
    fhash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    fmeta = {
        "name": fname,
        "content_type": "text/markdown",
        "size": len(content.encode("utf-8")),
        "source": "bd-kb",
    }
    fdata = {
        "status": "processed",
        "content": content,
    }
    cur.execute(
        "INSERT OR REPLACE INTO file (id, user_id, filename, meta, created_at, hash, data, updated_at, path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (fid, admin_id, fname, json.dumps(fmeta), now, fhash, json.dumps(fdata), now, str(dest)),
    )
    file_ids_by_name[fname] = fid

# 2. Upsert the 6 Native Knowledge Bases into `knowledge`, `knowledge_file`, and `access_grant`
for kb in kb_defs:
    kbid = kb["id"]
    kb_file_ids = [file_ids_by_name[fn] for fn in kb["files"] if fn in file_ids_by_name]
    kb_meta = {
        "source": "bd-kb",
        "file_ids": kb_file_ids,
        "qdrant_collection": data["qdrant_collection"],
        "embedding_dim": 1024,
    }
    kb_data = {"file_ids": kb_file_ids}
    cur.execute(
        "INSERT OR REPLACE INTO knowledge (id, user_id, name, description, data, meta, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (kbid, admin_id, kb["name"], kb["description"], json.dumps(kb_data), json.dumps(kb_meta), now, now),
    )
    for fid in kb_file_ids:
        kfid = f"kf-{kbid}-{fid}"
        cur.execute(
            "INSERT OR REPLACE INTO knowledge_file (id, knowledge_id, file_id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (kfid, kbid, fid, admin_id, now, now),
        )
    # Public read grant
    cur.execute("DELETE FROM access_grant WHERE resource_type='knowledge' AND resource_id=?", (kbid,))
    cur.execute(
        "INSERT INTO access_grant (id, resource_type, resource_id, principal_type, principal_id, permission, created_at) VALUES (?, 'knowledge', ?, 'user', '*', 'read', ?)",
        (str(uuid.uuid4()), kbid, now),
    )

# 3. Ensure all 50 native tools in tool table have public read access_grant
cur.execute("SELECT id FROM tool")
all_tool_ids = [r[0] for r in cur.fetchall()]
for tid in all_tool_ids:
    cur.execute("SELECT COUNT(*) FROM access_grant WHERE resource_type='tool' AND resource_id=? AND principal_id='*'", (tid,))
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO access_grant (id, resource_type, resource_id, principal_type, principal_id, permission, created_at) VALUES (?, 'tool', ?, 'user', '*', 'read', ?)",
            (str(uuid.uuid4()), tid, now),
        )

# 4. Attach all 50 toolkits + 6 BD KB knowledge bases to workspace models AND register Pipeline/Image/Speech workspace models
kb_items = [
    {"id": kb["id"], "name": kb["name"], "description": kb["description"], "type": "collection"}
    for kb in kb_defs
]

cur.execute("SELECT id, meta, params FROM model")
existing_models = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

# Update existing workspace models to include all 50 toolIds and the Master BD KB
for mid, (m_meta_s, m_params_s) in existing_models.items():
    try:
        m_meta = json.loads(m_meta_s) if m_meta_s else {}
    except Exception:
        m_meta = {}
    m_meta["toolIds"] = sorted(all_tool_ids)
    cur_kbs = m_meta.get("knowledge") or []
    existing_kb_ids = {k.get("id") for k in cur_kbs if isinstance(k, dict)}
    for kbi in kb_items:
        if kbi["id"] not in existing_kb_ids:
            cur_kbs.append(kbi)
    m_meta["knowledge"] = cur_kbs
    cur.execute("UPDATE model SET meta=?, updated_at=? WHERE id=?", (json.dumps(m_meta), now, mid))

new_entries = []
for p in data["pipelines"]:
    new_entries.append((p["id"], p["name"], p.get("description") or p["name"], "local-164-32b-coder"))
for im in data["image_models"]:
    new_entries.append((im["id"], im["name"], im.get("description") or im["name"], None))
for sp in data["speech_models"]:
    new_entries.append((sp["id"], sp["name"], sp.get("description") or sp["name"], None))

for mid, mname, mdesc, base_mid in new_entries:
    m_meta = {
        "profile_image_url": "/static/favicon.png",
        "description": mdesc,
        "capabilities": {
            "vision": True,
            "file_upload": True,
            "web_search": True,
            "image_generation": True,
            "code_interpreter": True,
            "citations": True,
            "status_updates": True,
        },
        "toolIds": sorted(all_tool_ids),
        "knowledge": kb_items,
    }
    m_params = {
        "system": "You are a Boylenet Sovereign AI model grounded in the official 6-volume BD KB, 27-node Boylenet cluster, and 50 High-ROI Toolkits.",
        "function_calling": "native",
    }
    cur.execute(
        "INSERT OR REPLACE INTO model (id, user_id, base_model_id, name, meta, params, created_at, updated_at, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (mid, admin_id, base_mid, mname, json.dumps(m_meta), json.dumps(m_params), now, now),
    )
    cur.execute("DELETE FROM access_grant WHERE resource_type='model' AND resource_id=?", (mid,))
    cur.execute(
        "INSERT INTO access_grant (id, resource_type, resource_id, principal_type, principal_id, permission, created_at) VALUES (?, 'model', ?, 'user', '*', 'read', ?)",
        (str(uuid.uuid4()), mid, now),
    )

con.commit()
print(json.dumps({
    "files_upserted": len(file_ids_by_name),
    "kbs_upserted": len(kb_defs),
    "native_tools_total": len(all_tool_ids),
    "pipeline_image_speech_models_upserted": len(new_entries),
}))
"""

    b64_script = base64.b64encode(container_script.encode("utf-8")).decode("ascii")
    runner_one_liner = f"import base64; exec(base64.b64decode('{b64_script}').decode('utf-8'))"
    cmd = ["docker", "exec", "-i", "open-webui", "python3", "-c", runner_one_liner]
    if ssh_host:
        cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            ssh_host,
            f'sudo -n docker exec -i open-webui python3 -c "{runner_one_liner}"',
        ]

    proc = subprocess.run(
        cmd,
        input=json.dumps(db_sync_input),
        text=True,
        capture_output=True,
        timeout=45,
    )
    db_res = (
        json.loads(proc.stdout.strip().splitlines()[-1])
        if proc.returncode == 0 and proc.stdout.strip()
        else {"error": proc.stderr}
    )

    # Also register Qdrant bd_master_kb in external_knowledge.connections via /api/v1/configs/export + import
    st_exp, exp_cfg = api_call(base_url, token, "GET", "/api/v1/configs/export")
    if st_exp == 200 and isinstance(exp_cfg, dict):
        ext_kb = exp_cfg.setdefault("external_knowledge", {})
        conns = ext_kb.setdefault("connections", [])
        if not any(
            isinstance(c, dict) and c.get("collection_name") == "bd_master_kb"
            for c in conns
        ):
            conns.append(
                {
                    "id": "qdrant-bd-master-kb",
                    "name": "Boylenet Master BD KB (Qdrant 1024-d Vector Collection)",
                    "type": "qdrant",
                    "url": QDRANT_URL,
                    "collection_name": "bd_master_kb",
                    "embedding_model": "bge-m3:latest",
                    "dimensions": 1024,
                    "enable": True,
                }
            )
            api_call(base_url, token, "POST", "/api/v1/configs/import", {"config": exp_cfg})

    # 6. Live Verification via OpenWebUI REST APIs
    _, pl_list = api_call(base_url, token, "GET", "/api/v1/pipelines/list")
    pl_urls = pl_list.get("data", []) if isinstance(pl_list, dict) else []
    pipeline_idx = next(
        (item["idx"] for item in pl_urls if "4079" in str(item.get("url", ""))),
        1,
    )
    _, pl_items = api_call(base_url, token, "GET", f"/api/v1/pipelines/?urlIdx={pipeline_idx}")
    _, kb_list = api_call(base_url, token, "GET", "/api/v1/knowledge/")
    _, tools_list = api_call(base_url, token, "GET", "/api/v1/tools/")

    native_toolkits = [
        t for t in (tools_list if isinstance(tools_list, list) else [])
        if not str(t.get("id", "")).startswith("server:")
    ]
    openapi_tool_servers = [
        t for t in (tools_list if isinstance(tools_list, list) else [])
        if str(t.get("id", "")).startswith("server:")
    ]
    kb_items_resp = kb_list.get("items", kb_list) if isinstance(kb_list, dict) else kb_list
    bd_kb_ids = sorted(
        [
            k["id"]
            for k in (kb_items_resp if isinstance(kb_items_resp, list) else [])
            if str(k.get("id", "")).startswith("bd-kb-")
        ]
    )

    return {
        "instance": name,
        "base_url": base_url,
        "public_url": inst["public_url"],
        "embedding_update_status": emb_status,
        "openai_config_status": openai_status,
        "toolkits_31_50_registered": registered_31_50,
        "db_sync": db_res,
        "verified_pipelines_servers": pl_urls,
        "verified_pipelines_count": len(pl_items.get("data", [])) if isinstance(pl_items, dict) else 0,
        "verified_bd_kb_count": len(bd_kb_ids),
        "verified_bd_kb_ids": bd_kb_ids,
        "verified_native_toolkits_count": len(native_toolkits),
        "verified_openapi_tool_servers_count": len(openapi_tool_servers),
        "verified_total_tools_entries": len(tools_list) if isinstance(tools_list, list) else 0,
    }


def main() -> None:
    t0 = time.time()
    log_stream("Starting BD KB Qdrant 1024-d indexing + Dual-Node OpenWebUI Pipelines, Image/Speech Models & 50-Toolkit Synchronization")
    qdrant_res = sync_qdrant_bd_master_kb()
    log_stream(f"Qdrant bd_master_kb indexed: {qdrant_res['points_upserted']} chunks (verify_hits={qdrant_res['verify_hits']})")

    instance_results = []
    for inst in INSTANCES:
        res = sync_instance(inst)
        instance_results.append(res)
        log_stream(
            f"Synced {inst['name']}: pipelines={res['verified_pipelines_count']}, bd_kb={res['verified_bd_kb_count']}, native_toolkits={res['verified_native_toolkits_count']}, openapi_servers={res['verified_openapi_tool_servers_count']}"
        )

    summary = {
        "ok": True,
        "elapsed_s": round(time.time() - t0, 2),
        "qdrant_bd_master_kb": qdrant_res,
        "instances": instance_results,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
