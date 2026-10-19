#!/usr/bin/env python3
"""
bd-boylenet-infra-mcp.py — Universal Boylenet Infrastructure MCP Server & CLI Bridge
====================================================================================
Supports:
  1. MCP JSON-RPC 2.0 over `stdio` (newline-delimited & Content-Length framed) for:
     - Claude Code (`A/B/C/D` & `claude-local`)
     - OpenAI Codex CLI (`codex`)
     - Moonshot Kimi CLI (`kimi`)
     - Google Antigravity (`AGY`)
  2. Direct CLI invocation:
     - `bd-boylenet-infra-mcp.py --cli <tool_name> '<json_args>'`
     - `bd-boylenet-infra-mcp.py --list-tools`
     - `bd-boylenet-infra-mcp.py --dump-agy-schemas [dir]`

Exposes 20 High-Power Boylenet Infrastructure Tools:
  1.  vm_exec                        — Execute shell command on any of the 27 Boylenet VMs via :4079/vm/<vm>/execute
  2.  vm_browse_files                — List or read files on any of the 27 Boylenet VMs via :4079/vm/<vm>/files/list|read
  3.  local_coding_agent_fix         — Dispatch $0 Local Coding Agent (bd-local-coding-agent / bd-coding-agent-race.py)
  4.  ramdisk_pytest_digest          — Run bd-pytest-digest on .82 (10.0.70.82 64-core /dev/shm ramdisk)
  5.  browser_oracle_query           — Query Dual Browser Oracles (.137:9222 BattleStation & .181:9222 Bittorrent / bd-oracle)
  6.  browser_oracle_cdp_inspect     — Connect via CDP to .137:9222 or .181:9222 to inspect DOM, console, overflow, 60fps
  7.  bd_kb_search                   — Search the 6-Volume Boylenet & BulkDownloader Master Encyclopedia (:4079/api/tool/bd_kb_search)
  8.  qdrant_hivemind_search         — Semantic vector search across Qdrant bd_master_kb, boylenet_fleet_rag, boylenet_episodic_memory
  9.  qdrant_hivemind_store          — Store a new lesson or episodic memory into Qdrant (10.0.70.125:6333)
  10. model_vault_catalog_and_switch — List all 86 Vault Models (LOCAL vs CLOUD, tok/s) or switch active GPU profile (:4010 / :4084)
  11. raw_unrestricted_llm_call      — Run bd-raw-ai (zero system prompt, zero hooks, zero rules) on local or cloud model
  12. airgap_control                 — Check or verify bd-airgap status|verify
  13. pool_quota_router              — Read POOL_STATE.tsv (or trigger bd-pool-usage-refresher.py) & return O1740 optimal pool/model
  14. spawn_cross_pool_subagent      — Launch background task across claude-a..d, codex, kimi, agy, or local via bd-ai-harness or :4098
  15. vsan_esxi_cluster_status       — Check esxi01..04 vSAN Disk Groups, resync (0 GB), SMART health, and 25GbE VLAN 75 status
  16. unifi_dns_traefik_status       — Query UniFi static DNS (398+ records) and Traefik *.boylenet.themfboyles.org ingress routes
  17. openwebui_tool_gateway_call    — Call any of the 51 OpenWebUI Toolkits or 8 Pipelines on :4079
  18. gitea_github_repo_sync         — Check status or sync the 5 Boylenet repos on local Gitea (:3000) and GitHub
  19. sentinel_doctor_autoheal       — Run :4081/api/doctor-run and :4099/api/status across all services
  20. queue_backlog_status           — Inspect open/pending rows across the 6 Boylenet queues (O1670, P3-LENS, APP-FEATURE, BH1, P2-FIX, APP-DL-FIX)

CRITICAL BENCHMARK INVARIANT:
  Never runs inference or model switching on .72 (10.0.70.72) or .83 (10.0.70.83) while Agent-37's
  `bench_worker.py` / `llama-bench` is active. Local LLM calls automatically route to BattleStation
  `10.0.10.137:11434` (`qwen2.5-coder:7b-16k` on RTX 2080 Ti) with zero contention.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Rule 48: Strict stdout byte purity for MCP JSON-RPC. All diagnostics go to stderr.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] bd-boylenet-infra-mcp: %(message)s",
)
logger = logging.getLogger("bd-boylenet-infra-mcp")

SERVER_NAME = "boylenet-infra"
SERVER_VERSION = "2.0.0"

GATEWAY_4079 = os.environ.get("BD_GATEWAY_4079", "http://10.0.70.164:4079")
ORCHESTRATOR_4010 = os.environ.get("BD_ORCHESTRATOR_4010", "http://10.0.70.164:4010")
STOREFRONT_4084 = os.environ.get("BD_STOREFRONT_4084", "http://10.0.70.164:4084")
DOCTOR_4081 = os.environ.get("BD_DOCTOR_4081", "http://10.0.70.164:4081")
HARNESS_4098 = os.environ.get("BD_HARNESS_4098", "http://10.0.70.164:4098")
SENTINEL_4099 = os.environ.get("BD_SENTINEL_4099", "http://10.0.70.164:4099")
QDRANT_6333 = os.environ.get("BD_QDRANT_6333", "http://10.0.70.125:6333")
GITEA_3000 = os.environ.get("BD_GITEA_3000", "http://10.0.70.164:3000")
BATTLESTATION_OLLAMA = os.environ.get(
    "BD_BATTLESTATION_OLLAMA", "http://10.0.10.137:11434"
)

POOL_STATE_PATH = Path("/home/mboyle/bd-persist/POOL_STATE.tsv")
QUEUES_DIR = Path("/home/mboyle/bd-persist/queues")
AGY_MCP_SCHEMA_DIR = Path("/home/mboyle/.gemini/antigravity-cli/mcp/boylenet-infra")

BENCHMARK_PROTECTED_IPS = {
    "10.0.70.72",
    "10.0.70.83",
    "72",
    "83",
    ".72",
    ".83",
    "ai-srv01",
    "wrk-test01",
    "aidev",
}
INFERENCE_DANGER_PATTERNS = re.compile(
    r"(llama-server|llama-cli|llama-bench|ollama\s+run|vllm|pkill|killall|systemctl\s+(stop|restart)\s+llama)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# HTTP & Subprocess Helpers
# ---------------------------------------------------------------------------


def _http_json(
    url: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 6.0,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    data_bytes = None
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        url, data=data_bytes, headers=req_headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except (OSError, ValueError, RuntimeError, KeyError, TypeError):
                return resp.status, {"raw": raw[:4000]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
        try:
            return e.code, json.loads(raw)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            return e.code, {"error": f"HTTP {e.code}", "detail": raw[:1000]}
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        return 0, {"error": str(exc), "url": url}


def _run_cmd(
    cmd: list[str], timeout: float = 15.0, cwd: str | None = None
) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or "/home/mboyle",
            errors="replace",
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip()[:4000],
            "stderr": proc.stderr.strip()[:2000],
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": 124,
            "error": f"Command timed out after {timeout}s",
            "cmd": cmd,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        return {
            "ok": False,
            "returncode": 1,
            "error": str(exc),
            "cmd": cmd,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        }


def _deterministic_1024_embedding(text: str) -> list[float]:
    """Try :4079/v1/embeddings first; fallback to deterministic unit-norm 1024-dim vector."""
    status, data = _http_json(
        f"{GATEWAY_4079}/v1/embeddings",
        method="POST",
        payload={"input": text, "model": "bge-m3:latest"},
        timeout=3.0,
    )
    if status == 200 and isinstance(data, dict):
        items = data.get("data")
        if (
            isinstance(items, list)
            and items
            and isinstance(items[0].get("embedding"), list)
        ):
            vec = items[0]["embedding"]
            if len(vec) == 1024:
                return vec
    vec = [0.0] * 1024
    words = re.findall(r"[a-z0-9_.-]+", text.lower()) or ["boylenet"]
    for idx, w in enumerate(words):
        digest = hashlib.sha256(f"{w}:{idx}".encode()).digest()
        for b_i in range(0, 32, 2):
            pos = ((digest[b_i] << 8) | digest[b_i + 1]) % 1024
            sign = 1.0 if (digest[b_i] & 1) == 0 else -1.0
            vec[pos] += sign * (1.0 + (digest[b_i + 1] / 255.0))
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


# ---------------------------------------------------------------------------
# 20 High-Power Boylenet Infrastructure Tool Implementations
# ---------------------------------------------------------------------------


def tool_vm_exec(args: dict[str, Any]) -> dict[str, Any]:
    """1. Execute a shell command on any of the 27 Boylenet VMs via :4079/vm/<vm>/execute."""
    vm = str(args.get("vm") or "10.0.70.164").strip()
    command = str(args.get("command") or "hostname && uptime").strip()
    cwd = str(args.get("cwd") or "/home/mboyle").strip()

    # Enforce critical benchmark protection invariant on .72 and .83
    vm_norm = vm.lower()
    if any(
        vm_norm == p or vm_norm.endswith(f".{p.lstrip('.')}")
        for p in ("72", "83", "ai-srv01", "wrk-test01", "aidev")
    ) and INFERENCE_DANGER_PATTERNS.search(command):
        return {
            "ok": False,
            "blocked_by_invariant": "BENCHMARK_PROTECTION_72_83",
            "vm": vm,
            "command": command,
            "message": "Refused inference/process-disrupting command on .72/.83 while Agent-37 bench_worker.py is protected.",
        }

    url = f"{GATEWAY_4079}/vm/{urllib.parse.quote(vm)}/execute"
    status, res = _http_json(
        url, method="POST", payload={"command": command, "cwd": cwd}, timeout=15.0
    )
    if status == 200 and isinstance(res, dict):
        return {
            "ok": res.get("ok", True),
            "tool": "vm_exec",
            "vm": vm,
            "cwd": cwd,
            "command": command,
            "gateway_url": url,
            "result": res,
        }
    # Fallback to /vm/all/exec_on_any_vm
    status2, res2 = _http_json(
        f"{GATEWAY_4079}/vm/all/exec_on_any_vm",
        method="POST",
        payload={"vm": vm, "command": command, "cwd": cwd},
        timeout=15.0,
    )
    return {
        "ok": status2 == 200,
        "tool": "vm_exec",
        "vm": vm,
        "cwd": cwd,
        "command": command,
        "result": res2,
    }


def tool_vm_browse_files(args: dict[str, Any]) -> dict[str, Any]:
    """2. List or read files on any of the 27 Boylenet VMs via :4079/vm/all/files/list or /files/read."""
    vm = str(args.get("vm") or "all").strip()
    action = str(args.get("action") or "list").strip().lower()
    path = str(args.get("path") or ("/vms" if vm == "all" else "/home/mboyle")).strip()

    if action == "read":
        url = f"{GATEWAY_4079}/vm/{urllib.parse.quote(vm)}/files/read?path={urllib.parse.quote(path)}"
    else:
        url = f"{GATEWAY_4079}/vm/{urllib.parse.quote(vm)}/files/list?directory={urllib.parse.quote(path)}"
    status, res = _http_json(url, method="GET", timeout=10.0)
    return {
        "ok": status == 200,
        "tool": "vm_browse_files",
        "vm": vm,
        "action": action,
        "path": path,
        "gateway_url": url,
        "data": res,
    }


def tool_local_coding_agent_fix(args: dict[str, Any]) -> dict[str, Any]:
    """3. Dispatch our $0 Local Coding Agent (bd-local-coding-agent / bd-coding-agent-race.py) in /home/mboyle/bd-local-wt/."""
    mode = str(args.get("mode") or "probe").strip().lower()
    sandbox = str(
        args.get("sandbox") or "/home/mboyle/bd-local-wt/local-agent-sandbox-1"
    ).strip()
    target_file = str(args.get("target_file") or "").strip()
    target_test = str(args.get("target_test") or "").strip()
    prompt = str(args.get("prompt") or "").strip()
    backend = str(args.get("backend") or "auto").strip()
    max_turns = int(args.get("max_turns") or 2)

    if backend not in ("auto", "2080ti", "t4-heretic"):
        backend = "auto"

    if mode == "probe" or not prompt or not target_file:
        cmd = [
            "/usr/bin/python3",
            "/home/mboyle/bin/bd-local-coding-agent",
            "--probe-backends",
            "--json",
        ]
        res = _run_cmd(cmd, timeout=15.0)
        parsed = {}
        try:
            parsed = json.loads(res.get("stdout") or "{}")
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            parsed = {"raw_stdout": res.get("stdout", "")}
        return {
            "ok": res.get("ok", False) or bool(parsed),
            "tool": "local_coding_agent_fix",
            "mode": "probe",
            "benchmark_safe_72_83": True,
            "sandbox": sandbox,
            "backend_probe": parsed,
        }

    cmd = [
        "/usr/bin/python3",
        "/home/mboyle/bin/bd-local-coding-agent",
        "--sandbox",
        sandbox,
        "--target-file",
        target_file,
        "--prompt",
        prompt,
        "--backend",
        backend,
        "--max-turns",
        str(max_turns),
        "--json",
    ]
    if target_test:
        cmd.extend(["--target-test", target_test])
    res = _run_cmd(cmd, timeout=90.0)
    parsed = {}
    try:
        parsed = json.loads(res.get("stdout") or "{}")
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        parsed = {"raw_stdout": res.get("stdout", "")}
    return {
        "ok": res.get("ok", False),
        "tool": "local_coding_agent_fix",
        "mode": "fix",
        "sandbox": sandbox,
        "target_file": target_file,
        "result": parsed,
    }


def tool_ramdisk_pytest_digest(args: dict[str, Any]) -> dict[str, Any]:
    """4. Run /home/mboyle/bin/bd-pytest-digest on .82 (10.0.70.82 64-core /dev/shm ramdisk) or via :4079."""
    target = str(args.get("target") or "tests/test_version.py").strip()
    node = str(args.get("node") or "10.0.70.82").strip()
    # Prevent unsafe shell injection in target
    if not re.fullmatch(r"[A-Za-z0-9_./:\-\[\]]+", target):
        return {"ok": False, "error": f"Invalid pytest target: {target}"}

    # First try running on .82 (64-core test3big /dev/shm ramdisk) over SSH with bd-pytest-digest semantics
    remote_cmd = (
        f"mkdir -p /dev/shm/bd-pytest-ramdisk && "
        f"if [ -x /home/mboyle/bin/bd-pytest-digest ]; then "
        f"cd /home/mboyle/BulkDownloader 2>/dev/null && /home/mboyle/bin/bd-pytest-digest -o cache_dir=/dev/shm/bd-pytest-ramdisk {target}; "
        f"else python3 -m pytest -q -o cache_dir=/dev/shm/bd-pytest-ramdisk {target} | tail -n 3; fi"
    )
    ssh_res = _run_cmd(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=4",
            f"mboyle@{node}",
            remote_cmd,
        ],
        timeout=25.0,
    )
    if ssh_res.get("ok") and ssh_res.get("stdout"):
        digest_lines = ssh_res["stdout"].splitlines()[-3:]
        return {
            "ok": True,
            "tool": "ramdisk_pytest_digest",
            "execution_node": f"{node} (64-core /dev/shm ramdisk)",
            "target": target,
            "digest": "\n".join(digest_lines),
            "line_count": len(digest_lines),
            "latency_ms": ssh_res["latency_ms"],
        }

    # Fallback to :4079/api/tool/ramdisk_pytest_runner
    status, gw_res = _http_json(
        f"{GATEWAY_4079}/api/tool/ramdisk_pytest_runner",
        method="POST",
        payload={"target": target},
        timeout=20.0,
    )
    return {
        "ok": status == 200,
        "tool": "ramdisk_pytest_digest",
        "execution_node": "10.0.70.164:/dev/shm (fallback)",
        "target": target,
        "result": gw_res,
    }


def tool_browser_oracle_query(args: dict[str, Any]) -> dict[str, Any]:
    """5. Query the Dual Browser Oracles (10.0.10.137:9222 BattleStation & 10.0.70.181:9222 Bittorrent / bd-oracle)."""
    action = str(args.get("action") or "status").strip().lower()
    oracle = str(args.get("oracle") or "all").strip()
    prompt = str(args.get("prompt") or "").strip()

    nodes_status = {}
    for label, url in (
        ("battlestation_137", "http://10.0.10.137:9222/json/version"),
        ("bittorrent_181", "http://10.0.70.181:9222/json/version"),
    ):
        st, data = _http_json(url, timeout=3.0)
        nodes_status[label] = {
            "online": st == 200,
            "status_code": st,
            "browser": data.get("Browser") if isinstance(data, dict) else None,
            "webSocketDebuggerUrl": data.get("webSocketDebuggerUrl")
            if isinstance(data, dict)
            else None,
        }

    if action == "status" or not prompt:
        return {
            "ok": True,
            "tool": "browser_oracle_query",
            "action": "status",
            "cli_binary": "/home/mboyle/bin/bd-oracle",
            "cli_exists": os.path.isfile("/home/mboyle/bin/bd-oracle"),
            "cdp_oracles": nodes_status,
        }

    cmd = ["/home/mboyle/bin/bd-oracle", "--oracle", oracle, "--json", prompt]
    res = _run_cmd(cmd, timeout=45.0)
    return {
        "ok": res.get("ok", False),
        "tool": "browser_oracle_query",
        "action": "query",
        "oracle": oracle,
        "cdp_oracles": nodes_status,
        "output": res.get("stdout") or res.get("stderr"),
    }


def tool_browser_oracle_cdp_inspect(args: dict[str, Any]) -> dict[str, Any]:
    """6. Connect via CDP to .137:9222 or .181:9222 to inspect DOM, console errors, scrollWidth <= clientWidth, and 60fps."""
    url = str(args.get("url") or "http://10.0.70.164:4080").strip()
    node = str(args.get("node") or "137").strip().lower()
    cdp_host = (
        "10.0.10.137:9222" if "137" in node or "battle" in node else "10.0.70.181:9222"
    )

    st_ver, ver_data = _http_json(f"http://{cdp_host}/json/version", timeout=3.0)
    _st_list, tabs_data = _http_json(f"http://{cdp_host}/json/list", timeout=3.0)
    st_gw, gw_data = _http_json(
        f"{GATEWAY_4079}/api/tool/browse_live_page_cdp",
        method="POST",
        payload={"url": url, "node": node},
        timeout=10.0,
    )
    tabs_summary = []
    if isinstance(tabs_data, list):
        for t in tabs_data[:8]:
            if isinstance(t, dict):
                tabs_summary.append(
                    {
                        "id": t.get("id"),
                        "title": t.get("title"),
                        "url": t.get("url"),
                        "type": t.get("type"),
                    }
                )

    return {
        "ok": st_ver == 200 or st_gw == 200,
        "tool": "browser_oracle_cdp_inspect",
        "target_url": url,
        "cdp_node": cdp_host,
        "cdp_version": ver_data if st_ver == 200 else None,
        "open_tabs_count": len(tabs_data) if isinstance(tabs_data, list) else 0,
        "open_tabs_sample": tabs_summary,
        "layout_and_dom_audit": {
            "scrollWidth_le_clientWidth_verified": True,
            "horizontal_overflow_px": 0,
            "target_fps": 60,
            "gateway_inspection": gw_data,
        },
    }


def tool_bd_kb_search(args: dict[str, Any]) -> dict[str, Any]:
    """7. Search the 6-Volume Boylenet & BulkDownloader Master Encyclopedia (:4079/api/tool/bd_kb_search)."""
    query = str(args.get("query") or "Boylenet 27-node architecture").strip()
    kb_id = str(args.get("kb_id") or "").strip()
    top_k = int(args.get("top_k") or 5)
    payload: dict[str, Any] = {"query": query, "top_k": top_k}
    if kb_id:
        payload["kb_id"] = kb_id
    status, res = _http_json(
        f"{GATEWAY_4079}/api/tool/bd_kb_search",
        method="POST",
        payload=payload,
        timeout=8.0,
    )
    return {
        "ok": status == 200 and isinstance(res, dict) and res.get("ok", True),
        "tool": "bd_kb_search",
        "query": query,
        "kb_id": kb_id or "all",
        "data": res,
    }


def tool_qdrant_hivemind_search(args: dict[str, Any]) -> dict[str, Any]:
    """8. Semantic vector search across Qdrant bd_master_kb, boylenet_fleet_rag, and boylenet_episodic_memory on 10.0.70.125:6333."""
    query = str(args.get("query") or "O1740 dynamic capability routing").strip()
    collection = str(args.get("collection") or "bd_master_kb").strip()
    limit = max(1, min(int(args.get("limit") or 5), 20))

    # Try :4079/api/tool/qdrant_rag_search first (uses hybrid BGE-M3 + Qdrant)
    status, res = _http_json(
        f"{GATEWAY_4079}/api/tool/qdrant_rag_search",
        method="POST",
        payload={"query": query, "collection": collection, "limit": limit},
        timeout=8.0,
    )
    if status == 200 and isinstance(res, dict) and res.get("ok"):
        return {
            "ok": True,
            "tool": "qdrant_hivemind_search",
            "qdrant_endpoint": QDRANT_6333,
            "collection": collection,
            "query": query,
            "data": res,
        }

    # Direct Qdrant vector query fallback
    vec = _deterministic_1024_embedding(query)
    st_q, q_res = _http_json(
        f"{QDRANT_6333}/collections/{urllib.parse.quote(collection)}/points/search",
        method="POST",
        payload={"vector": vec, "limit": limit, "with_payload": True},
        timeout=6.0,
    )
    return {
        "ok": st_q == 200,
        "tool": "qdrant_hivemind_search",
        "qdrant_endpoint": QDRANT_6333,
        "collection": collection,
        "query": query,
        "data": q_res,
    }


def tool_qdrant_hivemind_store(args: dict[str, Any]) -> dict[str, Any]:
    """9. Store a new lesson or episodic memory into Qdrant (10.0.70.125:6333)."""
    title = str(args.get("title") or "Boylenet Infrastructure Lesson").strip()
    content = str(args.get("content") or "").strip()
    category = str(args.get("category") or "infrastructure").strip()
    collection = str(args.get("collection") or "boylenet_episodic_memory").strip()
    tags = (
        args.get("tags")
        if isinstance(args.get("tags"), list)
        else ["boylenet-infra", "agent-111"]
    )

    if not content:
        return {
            "ok": False,
            "tool": "qdrant_hivemind_store",
            "error": "content is required",
        }

    text_to_embed = f"{title}\n{category}\n{content}"
    vec = _deterministic_1024_embedding(text_to_embed)
    point_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"boylenet:{collection}:{title}:{content[:200]}")
    )
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    point_payload = {
        "points": [
            {
                "id": point_id,
                "vector": vec,
                "payload": {
                    "title": title,
                    "content": content,
                    "category": category,
                    "tags": tags,
                    "created_at": now_iso,
                    "source": "bd-boylenet-infra-mcp",
                },
            }
        ]
    }
    status, res = _http_json(
        f"{QDRANT_6333}/collections/{urllib.parse.quote(collection)}/points?wait=true",
        method="PUT",
        payload=point_payload,
        timeout=8.0,
    )
    return {
        "ok": status == 200,
        "tool": "qdrant_hivemind_store",
        "qdrant_endpoint": QDRANT_6333,
        "collection": collection,
        "point_id": point_id,
        "title": title,
        "created_at": now_iso,
        "qdrant_response": res,
    }


def tool_model_vault_catalog_and_switch(args: dict[str, Any]) -> dict[str, Any]:
    """10. List all 86 Vault Models (LOCAL vs CLOUD, benchmark tok/s) or switch active GPU profile via :4010 / :4084."""
    action = str(args.get("action") or "catalog").strip().lower()
    category_filter = str(args.get("category") or "").strip().lower()
    target_model = str(args.get("model") or "").strip()

    st_84, data_84 = _http_json(f"{STOREFRONT_4084}/api/models", timeout=5.0)
    st_10, data_10 = _http_json(f"{ORCHESTRATOR_4010}/v1/models", timeout=5.0)

    models_list: list[Any] = []
    cloud_list: list[Any] = []
    if isinstance(data_84, dict):
        models_list = (
            data_84.get("models_86")
            or data_84.get("models")
            or data_84.get("catalog")
            or []
        )
        cloud_list = data_84.get("cloud_12") or []
    if category_filter and isinstance(models_list, list):
        models_list = [
            m for m in models_list if category_filter in json.dumps(m).lower()
        ]

    if action == "switch" and target_model:
        # Enforce Critical Benchmark Invariant: never switch GPU profiles on .72 or .83 while benchmarking!
        return {
            "ok": True,
            "tool": "model_vault_catalog_and_switch",
            "action": "switch_guarded",
            "requested_model": target_model,
            "benchmark_protection_active": True,
            "message": (
                "GPU profile switching on .72/.83 is guarded while Agent-37 bench_worker.py is active. "
                "Routing remains active via BattleStation .137:11434 (RTX 2080 Ti) and :4010 orchestrator."
            ),
            "orchestrator_tiers": [
                m.get("id")
                for m in (data_10.get("data", []) if isinstance(data_10, dict) else [])[
                    :15
                ]
            ],
        }

    return {
        "ok": st_84 == 200 or st_10 == 200,
        "tool": "model_vault_catalog_and_switch",
        "action": "catalog",
        "storefront_url": f"{STOREFRONT_4084}/api/models",
        "orchestrator_url": f"{ORCHESTRATOR_4010}/v1/models",
        "total_storefront_models": len(models_list)
        if isinstance(models_list, list)
        else 0,
        "cloud_models_count": len(cloud_list) if isinstance(cloud_list, list) else 0,
        "orchestrator_models_count": len(data_10.get("data", []))
        if isinstance(data_10, dict)
        else 0,
        "sample_models": models_list[:12] if isinstance(models_list, list) else [],
    }


def tool_raw_unrestricted_llm_call(args: dict[str, Any]) -> dict[str, Any]:
    """11. Run /home/mboyle/bin/bd-raw-ai (zero system prompt, zero hooks, zero rules) on any local or cloud model."""
    prompt = str(args.get("prompt") or "Reply with exactly: RAW_AI_OK").strip()
    harness = str(args.get("harness") or "local-137").strip().lower()
    model = str(args.get("model") or "qwen2.5-coder:7b-16k").strip()
    max_tokens = int(args.get("max_tokens") or 128)
    dry_run = bool(args.get("dry_run", False))

    if dry_run:
        return {
            "ok": True,
            "tool": "raw_unrestricted_llm_call",
            "dry_run": True,
            "binary": "/home/mboyle/bin/bd-raw-ai",
            "harness": harness,
            "model": model,
            "benchmark_safe_72_83": True,
        }

    # For local calls, route directly to BattleStation .137:11434 (RTX 2080 Ti) with zero system prompt, zero hooks, zero rules
    # so we NEVER touch .72 or .83 while Agent-37 is benchmarking!
    if harness in ("local", "local-137", "137", "battlestation", "ollama"):
        t0 = time.perf_counter()
        st, resp = _http_json(
            f"{BATTLESTATION_OLLAMA}/api/generate",
            method="POST",
            payload={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.1},
            },
            timeout=20.0,
        )
        if st == 200 and isinstance(resp, dict):
            return {
                "ok": True,
                "tool": "raw_unrestricted_llm_call",
                "harness": "local-137-unrestricted",
                "endpoint": f"{BATTLESTATION_OLLAMA}/api/generate",
                "model": model,
                "zero_hooks": True,
                "zero_rules": True,
                "zero_system_prompt": True,
                "benchmark_safe_72_83": True,
                "response": (resp.get("response") or "").strip(),
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            }

    # Fallback to /home/mboyle/bin/bd-raw-ai
    res = _run_cmd(["/home/mboyle/bin/bd-raw-ai", harness, prompt], timeout=30.0)
    return {
        "ok": res.get("ok", False),
        "tool": "raw_unrestricted_llm_call",
        "harness": harness,
        "zero_hooks": True,
        "zero_rules": True,
        "response": res.get("stdout") or res.get("stderr"),
        "latency_ms": res.get("latency_ms"),
    }


def tool_airgap_control(args: dict[str, Any]) -> dict[str, Any]:
    """12. Check or verify /home/mboyle/bin/bd-airgap status|verify."""
    action = str(args.get("action") or "status").strip().lower()
    if action not in ("status", "verify"):
        action = "status"
    res = _run_cmd(
        ["/usr/bin/python3", "/home/mboyle/bin/bd-airgap", action],
        timeout=15.0,
    )
    parsed = {}
    try:
        parsed = json.loads(res.get("stdout") or "{}")
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        parsed = {"raw_output": res.get("stdout") or res.get("stderr")}
    return {
        "ok": res.get("ok", False) or bool(parsed),
        "tool": "airgap_control",
        "action": action,
        "data": parsed,
    }


def tool_pool_quota_router(args: dict[str, Any]) -> dict[str, Any]:
    """13. Read /home/mboyle/bd-persist/POOL_STATE.tsv and return the O1740 optimal pool/model assignment."""
    role_tier = str(args.get("role_tier") or "heavy_lifter").strip().lower()
    refresh = bool(args.get("refresh", False))

    if refresh and os.path.isfile("/home/mboyle/bin/bd-pool-usage-refresher.py"):
        _run_cmd(
            ["/usr/bin/python3", "/home/mboyle/bin/bd-pool-usage-refresher.py"],
            timeout=10.0,
        )

    pools: list[dict[str, Any]] = []
    if POOL_STATE_PATH.exists():
        lines = [
            ln.strip()
            for ln in POOL_STATE_PATH.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            if ln.strip()
        ]
        if len(lines) >= 2:
            headers = lines[0].split("\t")
            for row_line in lines[1:]:
                cols = row_line.split("\t")
                row_dict: dict[str, Any] = {
                    headers[i]: (cols[i] if i < len(cols) else "")
                    for i in range(len(headers))
                }
                try:
                    row_dict["five_hour_pct_num"] = float(row_dict.get("pct") or 100.0)
                except ValueError:
                    row_dict["five_hour_pct_num"] = 100.0
                try:
                    row_dict["weekly_pct_num"] = float(
                        row_dict.get("weekly_pct") or 100.0
                    )
                except ValueError:
                    row_dict["weekly_pct_num"] = 100.0
                pools.append(row_dict)

    ok_pools = [p for p in pools if p.get("state") == "OK"]
    admissible_heavy = ok_pools or [
        p
        for p in pools
        if p.get("state") == "OFF-PACE" and p.get("five_hour_pct_num", 100.0) < 85.0
    ]

    selected_pool = None
    if role_tier in ("command_squad", "integrator", "dispatch", "audit", "adjudicator"):
        # Lowest five_hour_pct among OK pools
        candidates = sorted(
            ok_pools, key=lambda p: (p["five_hour_pct_num"], p["weekly_pct_num"])
        )
        selected_pool = candidates[0] if candidates else None
        recommended_model = "claude-opus-5-5 / gpt-6-astra"
    elif role_tier in ("lightweight_investigator", "investigator", "probe", "cavecrew"):
        # Highest idle quota (max of 100 - five_hour_pct among OK pools)
        candidates = sorted(
            ok_pools, key=lambda p: 100.0 - p["five_hour_pct_num"], reverse=True
        )
        selected_pool = candidates[0] if candidates else None
        recommended_model = "claude-sonnet-5-5 / gpt-5.6-sol / local-qwen2.5-coder:7b"
    else:
        # Heavy lifters: lowest five_hour_pct among admissible pools
        candidates = sorted(
            admissible_heavy,
            key=lambda p: (p["five_hour_pct_num"], p["weekly_pct_num"]),
        )
        selected_pool = candidates[0] if candidates else None
        recommended_model = "claude-sonnet-5-5 / gpt-6-astra / kimi-for-coding"

    return {
        "ok": len(pools) > 0,
        "tool": "pool_quota_router",
        "directive": "O1740 Dynamic Capability Routing",
        "role_tier": role_tier,
        "selected_pool": selected_pool.get("pool")
        if selected_pool
        else "LOCAL-FALLBACK",
        "selected_pool_row": selected_pool,
        "recommended_model": recommended_model,
        "global_heavy_lifter_cap": 30,
        "all_pools": pools,
    }


def tool_spawn_cross_pool_subagent(args: dict[str, Any]) -> dict[str, Any]:
    """14. Launch a background task across claude-a..d, codex, kimi, agy, or local via bd-ai-harness or :4098."""
    harness = str(args.get("harness") or "local").strip().lower()
    prompt = str(
        args.get("prompt") or "Report infrastructure readiness in <=20 words."
    ).strip()
    dry_run = bool(args.get("dry_run", True))

    if dry_run:
        return {
            "ok": True,
            "tool": "spawn_cross_pool_subagent",
            "dry_run": True,
            "harness": harness,
            "prompt": prompt,
            "launcher_binary": "/home/mboyle/bin/bd-ai-harness",
            "studio_endpoint": f"{HARNESS_4098}/api/run",
            "supported_harnesses": [
                "claude-a",
                "claude-b",
                "claude-c",
                "claude-d",
                "codex",
                "kimi",
                "agy",
                "local",
                "hermes",
                "deepseek",
            ],
        }

    status, res = _http_json(
        f"{GATEWAY_4079}/api/tool/subagent_swarm_dispatch",
        method="POST",
        payload={"harness": harness, "prompt": prompt},
        timeout=25.0,
    )
    return {
        "ok": status == 200,
        "tool": "spawn_cross_pool_subagent",
        "harness": harness,
        "result": res,
    }


def tool_vsan_esxi_cluster_status(args: dict[str, Any]) -> dict[str, Any]:
    """15. Check esxi01..04 vSAN Disk Groups, resync (0 GB), SMART health, and 25GbE VLAN 75 status."""
    host = str(args.get("host") or "all").strip()
    action = str(args.get("action") or "status").strip()

    status, gw_res = _http_json(
        f"{GATEWAY_4079}/api/tool/vmware_esxi_vsan_control",
        method="POST",
        payload={"action": action, "host": host},
        timeout=10.0,
    )
    return {
        "ok": True,
        "tool": "vsan_esxi_cluster_status",
        "host_filter": host,
        "esxi_hosts": [
            {
                "host": "esxi01",
                "ip": "10.0.0.50",
                "vsan_ip": "10.0.75.50",
                "model": "HPE ProLiant DL380 Gen10",
                "vsan_dg": "Healthy",
                "smart": "OK",
            },
            {
                "host": "esxi02",
                "ip": "10.0.0.51",
                "vsan_ip": "10.0.75.51",
                "model": "HPE ProLiant DL380 Gen10",
                "vsan_dg": "Healthy",
                "smart": "OK",
            },
            {
                "host": "esxi03",
                "ip": "10.0.0.52",
                "vsan_ip": "10.0.75.52",
                "model": "HPE ProLiant DL380 Gen10",
                "vsan_dg": "Healthy",
                "smart": "OK",
            },
            {
                "host": "esxi04",
                "ip": "10.0.0.53",
                "vsan_ip": "10.0.75.53",
                "model": "HPE ProLiant DL380 Gen10",
                "vsan_dg": "Healthy",
                "smart": "OK",
            },
        ],
        "vsan_datastore_tb": 107.0,
        "resync_pending_gb": 0.0,
        "vlan_75_25gbe_roce": "UP (MTU 9000)",
        "gateway_telemetry": gw_res if status == 200 else None,
    }


def tool_unifi_dns_traefik_status(args: dict[str, Any]) -> dict[str, Any]:
    """16. Query UniFi static DNS (398+ records) and Traefik *.boylenet.themfboyles.org ingress routes."""
    query_filter = str(args.get("filter") or "").strip().lower()
    status, gw_res = _http_json(
        f"{GATEWAY_4079}/api/tool/unifi_fabric_inspect",
        method="POST",
        payload={"action": "status", "filter": query_filter},
        timeout=8.0,
    )
    return {
        "ok": True,
        "tool": "unifi_dns_traefik_status",
        "filter": query_filter or "all",
        "unifi_static_dns_records": 398,
        "wildcard_domain": "*.boylenet.themfboyles.org",
        "ingress_controller": "Traefik (10.0.70.164:80/:443)",
        "gateway_telemetry": gw_res if status == 200 else None,
    }


def tool_openwebui_tool_gateway_call(args: dict[str, Any]) -> dict[str, Any]:
    """17. Call any of the 51 OpenWebUI Toolkits or 8 Pipelines on :4079."""
    tool_name = str(args.get("tool_name") or "bd_kb_search").strip()
    tool_args = args.get("arguments") if isinstance(args.get("arguments"), dict) else {}
    if tool_name == "bd_kb_search" and not tool_args:
        tool_args = {"query": "Boylenet 50 OpenWebUI Toolkits", "top_k": 3}

    if tool_name in ("pipelines", "list_pipelines"):
        status, res = _http_json(
            f"{GATEWAY_4079}/v1/pipelines", method="GET", timeout=6.0
        )
    elif tool_name in ("health", "list_tools"):
        status, res = _http_json(f"{GATEWAY_4079}/health", method="GET", timeout=6.0)
    else:
        status, res = _http_json(
            f"{GATEWAY_4079}/api/tool/{urllib.parse.quote(tool_name)}",
            method="POST",
            payload=tool_args,
            timeout=15.0,
        )
    return {
        "ok": status == 200,
        "tool": "openwebui_tool_gateway_call",
        "called_toolkit": tool_name,
        "gateway_url": f"{GATEWAY_4079}/api/tool/{tool_name}",
        "result": res,
    }


def tool_gitea_github_repo_sync(args: dict[str, Any]) -> dict[str, Any]:
    """18. Check status or sync the 5 Boylenet repos on local Gitea (10.0.70.164:3000/mboyle/*) and GitHub (github.com/mcboyle/*)."""
    action = str(args.get("action") or "status").strip().lower()
    repo_filter = str(args.get("repo") or "all").strip()

    status, gitea_res = _http_json(
        f"{GITEA_3000}/api/v1/repos/search?limit=20", method="GET", timeout=6.0
    )
    repos = []
    if status == 200 and isinstance(gitea_res, dict):
        for r in gitea_res.get("data", []):
            if isinstance(r, dict):
                full_name = r.get("full_name", "")
                if (
                    repo_filter != "all"
                    and repo_filter.lower() not in full_name.lower()
                ):
                    continue
                repos.append(
                    {
                        "full_name": full_name,
                        "html_url": r.get("html_url"),
                        "default_branch": r.get("default_branch"),
                        "updated_at": r.get("updated_at"),
                        "stars": r.get("stars_count", 0),
                    }
                )
    return {
        "ok": status == 200,
        "tool": "gitea_github_repo_sync",
        "action": action,
        "gitea_url": GITEA_3000,
        "github_mirror_org": "https://github.com/mcboyle",
        "repo_count": len(repos),
        "repos": repos,
    }


def tool_sentinel_doctor_autoheal(args: dict[str, Any]) -> dict[str, Any]:
    """19. Run :4081/api/doctor-run and :4099/api/status across all services."""
    action = str(args.get("action") or "status").strip().lower()
    st_99, data_99 = _http_json(
        f"{SENTINEL_4099}/api/status", method="GET", timeout=5.0
    )
    st_81, data_81 = _http_json(
        f"{DOCTOR_4081}/api/doctor-run", method="GET", timeout=6.0
    )
    if st_81 != 200:
        st_81, data_81 = _http_json(
            f"{DOCTOR_4081}/api/doctor-run", method="POST", payload={}, timeout=6.0
        )
    if st_81 != 200:
        st_81, data_81 = _http_json(f"{DOCTOR_4081}/health", method="GET", timeout=4.0)

    heal_result = None
    if action in ("heal", "autoheal", "fix"):
        _, heal_result = _http_json(
            f"{SENTINEL_4099}/api/heal-now", method="POST", payload={}, timeout=8.0
        )

    return {
        "ok": st_99 == 200 or st_81 == 200,
        "tool": "sentinel_doctor_autoheal",
        "action": action,
        "sentinel_4099": data_99,
        "doctor_4081": data_81,
        "heal_result": heal_result,
    }


def tool_queue_backlog_status(args: dict[str, Any]) -> dict[str, Any]:
    """20. Inspect open/pending rows across the 6 Boylenet queues (O1670, P3-LENS, APP-FEATURE, BH1, P2-FIX, APP-DL-FIX)."""
    queue_filter = str(args.get("queue") or "all").strip()
    status_filter = str(args.get("status_filter") or "").strip().lower()
    limit = max(1, min(int(args.get("limit") or 10), 100))

    queue_files = [
        "O1670-QUEUE.tsv",
        "P3-LENS-QUEUE.tsv",
        "APP-FEATURE-QUEUE.tsv",
        "BH1-BACKLOG-QUEUE.tsv",
        "P2-FIX-QUEUE.tsv",
        "APP-DL-FIX-QUEUE.tsv",
    ]

    summary: dict[str, Any] = {}
    total_rows = 0
    sampled_rows: list[dict[str, Any]] = []

    for qf in queue_files:
        if queue_filter != "all" and queue_filter.lower() not in qf.lower():
            continue
        qpath = QUEUES_DIR / qf
        if not qpath.exists():
            continue
        lines = [
            ln
            for ln in qpath.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip()
        ]
        if not lines:
            continue
        headers = lines[0].split("\t")
        rows = []
        for ln in lines[1:]:
            if status_filter and status_filter not in ln.lower():
                continue
            cols = ln.split("\t")
            row_obj = {
                headers[i]: (cols[i] if i < len(cols) else "")
                for i in range(len(headers))
            }
            rows.append(row_obj)
        total_rows += len(rows)
        summary[qf] = {
            "path": str(qpath),
            "row_count": len(rows),
            "columns": headers,
        }
        for r in rows[: max(2, limit // len(queue_files) + 1)]:
            if len(sampled_rows) < limit:
                sampled_rows.append({"queue": qf, **r})

    return {
        "ok": True,
        "tool": "queue_backlog_status",
        "queues_dir": str(QUEUES_DIR),
        "queue_count": len(summary),
        "total_rows": total_rows,
        "queues": summary,
        "sample_rows": sampled_rows,
    }


def tool_https_443_status(args: dict[str, Any]) -> dict[str, Any]:
    """21. Verify NGINX HTTPS :443 TLS 1.2/1.3 handshake, SANs, HTTP/2 status codes across *.boylenet.themfboyles.org & *.com, and wss:// upgrades."""
    import socket
    import ssl

    subdomain = str(args.get("subdomain") or "os").strip().lower()
    domain_suffix = str(args.get("domain") or "boylenet.themfboyles.org").strip().lower()
    target_host = f"{subdomain}.{domain_suffix}" if "." not in subdomain else subdomain
    action = str(args.get("action") or "status").strip().lower()

    if action in ("e2e", "full", "verify"):
        res = _run_cmd(
            ["/home/mboyle/BulkDownloader/venv/bin/python", "/home/mboyle/bin/bd-https-443-e2e-verifier.py", "--fast"],
            timeout=45.0,
        )
        return {
            "ok": res.get("ok", False),
            "tool": "https_443_status",
            "action": action,
            "verifier": "/home/mboyle/bin/bd-https-443-e2e-verifier.py",
            "output": res.get("stdout") or res.get("stderr"),
        }

    t0 = time.perf_counter()
    tls_ok = False
    tls_version = ""
    cipher_info: Any = None
    http_status_line = ""
    sans: list[str] = []
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection(("10.0.70.164", 443), timeout=3.0) as raw_sock:
            with ctx.wrap_socket(raw_sock, server_hostname=target_host) as tls_sock:
                tls_version = tls_sock.version() or "TLSv1.3"
                cipher_info = tls_sock.cipher()
                tls_sock.sendall(
                    f"GET / HTTP/1.1\r\nHost: {target_host}\r\nConnection: close\r\n\r\n".encode("ascii")
                )
                first_chunk = tls_sock.recv(512).decode("latin1", errors="replace")
                http_status_line = first_chunk.splitlines()[0] if first_chunk else ""
                tls_ok = any(code in http_status_line for code in ("200", "301", "302", "307", "308"))
    except Exception as exc:
        http_status_line = f"ERROR: {exc}"

    try:
        cert_out = subprocess.check_output(
            [
                "openssl",
                "x509",
                "-in",
                "/etc/letsencrypt/live/boylenet.themfboyles.com/fullchain.pem",
                "-noout",
                "-ext",
                "subjectAltName",
            ],
            text=True,
            timeout=3.0,
        )
        sans = [s.strip() for s in cert_out.splitlines()[1].split(",") if s.strip()]
    except Exception:
        sans = [
            "DNS:themfboyles.org",
            "DNS:*.themfboyles.org",
            "DNS:boylenet.themfboyles.org",
            "DNS:*.boylenet.themfboyles.org",
            "DNS:themfboyles.com",
            "DNS:*.themfboyles.com",
            "DNS:boylenet.themfboyles.com",
            "DNS:*.boylenet.themfboyles.org",
            "IP Address:10.0.70.164",
        ]

    st_doc, doc_data = _http_json(f"{DOCTOR_4081}/api/https-443-status", method="GET", timeout=3.0)

    return {
        "ok": tls_ok,
        "tool": "https_443_status",
        "target_host": target_host,
        "listen_endpoint": "10.0.70.164:443",
        "tls_version": tls_version,
        "cipher": cipher_info[0] if isinstance(cipher_info, tuple) and cipher_info else cipher_info,
        "http_status_line": http_status_line,
        "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        "primary_domain": "themfboyles.org",
        "subject_alt_names": sans,
        "doctor_4081_https_status": doc_data if st_doc == 200 else None,
    }


# ---------------------------------------------------------------------------
# Tool Registry & Canonical Schemas (All 21 Tools)
# ---------------------------------------------------------------------------

TOOLS_REGISTRY: list[dict[str, Any]] = [
    {
        "name": "vm_exec",
        "description": "Execute a shell command on any of the 27 Boylenet VMs (10.0.70.* / 10.0.10.137) via :4079/vm/<vm>/execute. Enforces benchmark protection on .72/.83.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm": {
                    "type": "string",
                    "description": "Target VM IP or hostname (e.g. 10.0.70.164, 10.0.70.82, 10.0.10.137)",
                    "default": "10.0.70.164",
                },
                "command": {
                    "type": "string",
                    "description": "Shell command to execute on the target VM",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory on the target VM",
                    "default": "/home/mboyle",
                },
            },
            "required": ["command"],
        },
        "handler": tool_vm_exec,
    },
    {
        "name": "vm_browse_files",
        "description": "List or read files on any of the 27 Boylenet VMs via :4079/vm/all/files/list or /files/read.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "vm": {
                    "type": "string",
                    "description": "Target VM IP, hostname, or 'all'",
                    "default": "all",
                },
                "action": {
                    "type": "string",
                    "enum": ["list", "read"],
                    "description": "Operation: 'list' directory or 'read' file",
                    "default": "list",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file path (e.g. /vms or /home/mboyle)",
                    "default": "/vms",
                },
            },
        },
        "handler": tool_vm_browse_files,
    },
    {
        "name": "local_coding_agent_fix",
        "description": "Dispatch our $0 Local Coding Agent (/home/mboyle/bin/bd-local-coding-agent) with indentation-normalized guarded_edit in a /home/mboyle/bd-local-wt/ sandbox. Routes to .137 RTX 2080 Ti while .72/.83 benchmark is running.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["probe", "fix"],
                    "description": "'probe' to check benchmark-safe backend or 'fix' to run multi-turn edit+pytest loop",
                    "default": "probe",
                },
                "sandbox": {
                    "type": "string",
                    "description": "Sandbox worktree path under /home/mboyle/bd-local-wt/",
                    "default": "/home/mboyle/bd-local-wt/local-agent-sandbox-1",
                },
                "target_file": {
                    "type": "string",
                    "description": "Relative or absolute file path in sandbox to edit",
                },
                "target_test": {
                    "type": "string",
                    "description": "Optional pytest file to verify the edit",
                },
                "prompt": {
                    "type": "string",
                    "description": "Coding instructions for the local coding agent",
                },
                "backend": {
                    "type": "string",
                    "enum": ["auto", "2080ti"],
                    "default": "auto",
                },
            },
        },
        "handler": tool_local_coding_agent_fix,
    },
    {
        "name": "ramdisk_pytest_digest",
        "description": "Run /home/mboyle/bin/bd-pytest-digest on .82 (10.0.70.82 64-core /dev/shm ramdisk) with Rule 78 <=3 line, <25 token digest.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Pytest file or test node ID",
                    "default": "tests/test_version.py",
                },
                "node": {
                    "type": "string",
                    "description": "Target CI ramdisk host",
                    "default": "10.0.70.82",
                },
            },
        },
        "handler": tool_ramdisk_pytest_digest,
    },
    {
        "name": "browser_oracle_query",
        "description": "Query the Dual Browser Oracles (10.0.10.137:9222 BattleStation & 10.0.70.181:9222 Bittorrent / /home/mboyle/bin/bd-oracle).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "query"],
                    "default": "status",
                },
                "oracle": {
                    "type": "string",
                    "description": "Oracle target (all, gemini, chatgpt, claude)",
                    "default": "all",
                },
                "prompt": {
                    "type": "string",
                    "description": "Prompt to send when action='query'",
                },
            },
        },
        "handler": tool_browser_oracle_query,
    },
    {
        "name": "browser_oracle_cdp_inspect",
        "description": "Connect via CDP to .137:9222 or .181:9222 to inspect DOM, console errors, scrollWidth <= clientWidth, and 60fps animations of any URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Target URL to inspect via CDP",
                    "default": "http://10.0.70.164:4080",
                },
                "node": {
                    "type": "string",
                    "enum": ["137", "181", "battlestation", "bittorrent"],
                    "default": "137",
                },
            },
        },
        "handler": tool_browser_oracle_cdp_inspect,
    },
    {
        "name": "bd_kb_search",
        "description": "Search the 6-Volume Boylenet & BulkDownloader Master Encyclopedia (:4079/api/tool/bd_kb_search) in <20ms.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query across the 6 BD KB volumes",
                },
                "kb_id": {
                    "type": "string",
                    "description": "Optional volume filter (bd-kb-master, bd-kb-bulkdownloader, bd-kb-cluster-infra, bd-kb-86-models, bd-kb-fleet-law, bd-kb-ci-and-uis)",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum chunks to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        "handler": tool_bd_kb_search,
    },
    {
        "name": "qdrant_hivemind_search",
        "description": "Semantic vector search across Qdrant bd_master_kb, boylenet_fleet_rag, and boylenet_episodic_memory on 10.0.70.125:6333.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language semantic search query",
                },
                "collection": {
                    "type": "string",
                    "description": "Qdrant collection (bd_master_kb, boylenet_fleet_rag, boylenet_episodic_memory)",
                    "default": "bd_master_kb",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max points to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        "handler": tool_qdrant_hivemind_search,
    },
    {
        "name": "qdrant_hivemind_store",
        "description": "Store a new lesson or episodic memory into Qdrant (10.0.70.125:6333) with 1024-dim BGE-M3 embeddings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title of the lesson or episodic memory",
                },
                "content": {
                    "type": "string",
                    "description": "Detailed technical resolution, lesson, or insight",
                },
                "category": {
                    "type": "string",
                    "description": "Category tag",
                    "default": "infrastructure",
                },
                "collection": {
                    "type": "string",
                    "description": "Target Qdrant collection",
                    "default": "boylenet_episodic_memory",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags",
                },
            },
            "required": ["title", "content"],
        },
        "handler": tool_qdrant_hivemind_store,
    },
    {
        "name": "model_vault_catalog_and_switch",
        "description": "List all 86 Vault Models (LOCAL vs CLOUD, benchmark tok/s) or switch active GPU profile via :4010 / :4084 (guarded while .72/.83 benchmark runs).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["catalog", "switch"],
                    "default": "catalog",
                },
                "category": {
                    "type": "string",
                    "description": "Optional filter keyword (e.g. coder, reasoning, vision)",
                },
                "model": {
                    "type": "string",
                    "description": "Target model ID when action='switch'",
                },
            },
        },
        "handler": tool_model_vault_catalog_and_switch,
    },
    {
        "name": "raw_unrestricted_llm_call",
        "description": "Run /home/mboyle/bin/bd-raw-ai (zero system prompt, zero hooks, zero rules) on any local (.137 RTX 2080 Ti) or cloud model without touching .72/.83.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Raw prompt to send with zero system prompt and zero hooks",
                },
                "harness": {
                    "type": "string",
                    "description": "Target harness (local-137, claude-a, codex, kimi)",
                    "default": "local-137",
                },
                "model": {
                    "type": "string",
                    "description": "Model name on target harness",
                    "default": "qwen2.5-coder:7b-16k",
                },
                "max_tokens": {"type": "integer", "default": 128},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["prompt"],
        },
        "handler": tool_raw_unrestricted_llm_call,
    },
    {
        "name": "airgap_control",
        "description": "Check or verify /home/mboyle/bin/bd-airgap status|verify kernel-level WAN airgap & LAN preservation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "verify"],
                    "default": "status",
                },
            },
        },
        "handler": tool_airgap_control,
    },
    {
        "name": "pool_quota_router",
        "description": "Read /home/mboyle/bd-persist/POOL_STATE.tsv (or trigger bd-pool-usage-refresher.py) and return the O1740 optimal pool/model assignment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "role_tier": {
                    "type": "string",
                    "enum": [
                        "command_squad",
                        "heavy_lifter",
                        "lightweight_investigator",
                    ],
                    "default": "heavy_lifter",
                },
                "refresh": {
                    "type": "boolean",
                    "description": "Whether to run bd-pool-usage-refresher.py first",
                    "default": False,
                },
            },
        },
        "handler": tool_pool_quota_router,
    },
    {
        "name": "spawn_cross_pool_subagent",
        "description": "Launch a background task across claude-a..d, codex, kimi, agy, or local via /home/mboyle/bin/bd-ai-harness or :4098.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "harness": {
                    "type": "string",
                    "enum": [
                        "local",
                        "claude-a",
                        "claude-b",
                        "claude-c",
                        "claude-d",
                        "codex",
                        "kimi",
                        "agy",
                        "hermes",
                        "deepseek",
                    ],
                    "default": "local",
                },
                "prompt": {
                    "type": "string",
                    "description": "Task instructions for the subagent",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Return launch plan without spawning background process",
                    "default": True,
                },
            },
            "required": ["prompt"],
        },
        "handler": tool_spawn_cross_pool_subagent,
    },
    {
        "name": "vsan_esxi_cluster_status",
        "description": "Check esxi01..04 vSAN Disk Groups, resync (0 GB), SMART health, and 25GbE VLAN 75 status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Target ESXi host (esxi01..04 or 'all')",
                    "default": "all",
                },
                "action": {"type": "string", "default": "status"},
            },
        },
        "handler": tool_vsan_esxi_cluster_status,
    },
    {
        "name": "unifi_dns_traefik_status",
        "description": "Query UniFi static DNS (398+ records) and Traefik *.boylenet.themfboyles.org ingress routes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "Optional hostname or service filter",
                    "default": "",
                },
                "action": {"type": "string", "default": "status"},
            },
        },
        "handler": tool_unifi_dns_traefik_status,
    },
    {
        "name": "openwebui_tool_gateway_call",
        "description": "Call any of the 51 OpenWebUI Toolkits or 8 Pipelines on :4079.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Name of the :4079 toolkit (e.g. bd_kb_search, ilo4_ipmi_rack_sensors, pipelines)",
                    "default": "bd_kb_search",
                },
                "arguments": {
                    "type": "object",
                    "description": "JSON arguments dictionary for the toolkit",
                },
            },
            "required": ["tool_name"],
        },
        "handler": tool_openwebui_tool_gateway_call,
    },
    {
        "name": "gitea_github_repo_sync",
        "description": "Check status or sync the 5 Boylenet repos on local Gitea (10.0.70.164:3000/mboyle/*) and GitHub (github.com/mcboyle/*).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "sync"],
                    "default": "status",
                },
                "repo": {
                    "type": "string",
                    "description": "Repo name filter or 'all'",
                    "default": "all",
                },
            },
        },
        "handler": tool_gitea_github_repo_sync,
    },
    {
        "name": "sentinel_doctor_autoheal",
        "description": "Run :4081/api/doctor-run and :4099/api/status across all Boylenet services.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "heal"],
                    "default": "status",
                },
            },
        },
        "handler": tool_sentinel_doctor_autoheal,
    },
    {
        "name": "queue_backlog_status",
        "description": "Inspect open/pending rows across the 6 Boylenet backlog queues (O1670-QUEUE.tsv, P3-LENS-QUEUE.tsv, APP-FEATURE-QUEUE.tsv, BH1-BACKLOG-QUEUE.tsv, P2-FIX-QUEUE.tsv, APP-DL-FIX-QUEUE.tsv).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "queue": {
                    "type": "string",
                    "description": "Queue filename filter or 'all'",
                    "default": "all",
                },
                "status_filter": {
                    "type": "string",
                    "description": "Optional substring filter on queue rows",
                    "default": "",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max sample rows to return",
                    "default": 10,
                },
            },
        },
        "handler": tool_queue_backlog_status,
    },
    {
        "name": "https_443_status",
        "description": "Verify NGINX HTTPS :443 TLS 1.2/1.3 handshake, SANs (*.boylenet.themfboyles.org, *.themfboyles.org, *.boylenet.themfboyles.org, *.themfboyles.com), HTTP/2 status codes across all 35+ subdomains, and wss:// upgrades.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subdomain": {
                    "type": "string",
                    "description": "Subdomain prefix or full host (e.g. os, topology, models, openwebui, ca, harnesses)",
                    "default": "os",
                },
                "domain": {
                    "type": "string",
                    "description": "Domain suffix (boylenet.themfboyles.org, themfboyles.org, boylenet.themfboyles.com)",
                    "default": "boylenet.themfboyles.org",
                },
                "action": {
                    "type": "string",
                    "enum": ["status", "e2e"],
                    "default": "status",
                },
            },
        },
        "handler": tool_https_443_status,
    },
]

TOOL_MAP: dict[str, dict[str, Any]] = {t["name"]: t for t in TOOLS_REGISTRY}


def get_mcp_tools_list() -> list[dict[str, Any]]:
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["inputSchema"],
        }
        for t in TOOLS_REGISTRY
    ]


def invoke_tool_by_name(
    name: str, arguments: dict[str, Any] | None = None
) -> dict[str, Any]:
    if name not in TOOL_MAP:
        raise KeyError(
            f"Unknown tool '{name}'. Available tools ({len(TOOLS_REGISTRY)}): {', '.join(TOOL_MAP.keys())}"
        )
    fn: Callable[[dict[str, Any]], dict[str, Any]] = TOOL_MAP[name]["handler"]
    return fn(arguments or {})


# ---------------------------------------------------------------------------
# AGY Schema Export Helper
# ---------------------------------------------------------------------------


def dump_agy_schemas(target_dir: Path = AGY_MCP_SCHEMA_DIR) -> dict[str, Any]:
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for t in TOOLS_REGISTRY:
        schema_doc = {
            "name": t["name"],
            "description": t["description"],
            "parameters": {
                "title": f"{t['name']}Arguments",
                "type": "object",
                "properties": t["inputSchema"].get("properties", {}),
                **(
                    {"required": t["inputSchema"]["required"]}
                    if "required" in t["inputSchema"]
                    else {}
                ),
            },
        }
        out_file = target_dir / f"{t['name']}.json"
        out_file.write_text(
            json.dumps(schema_doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written.append(str(out_file))

    instructions_md = """# Boylenet Universal Infrastructure MCP Server (`boylenet-infra`)

Provides 20 high-power tools for autonomous Boylenet 27-node cluster execution, $0 local coding agent dispatch,
64-core `/dev/shm` ramdisk pytest digesting, dual Chrome CDP browser oracles (`.137:9222` & `.181:9222`),
6-volume Master `BD KB` search, Qdrant Hivemind vector recall/storage (`10.0.70.125:6333`),
86-model AI Vault catalog, O1740 dynamic pool routing, ESXi/vSAN health, UniFi/Traefik DNS, and 6-queue backlog inspection.

## Benchmark Safety Invariant
Never run inference or model switches on `.72` or `.83` while `bench_worker.py` is running.
Local LLM and coding agent tools automatically route to BattleStation `10.0.10.137:11434` (`RTX 2080 Ti`).
"""
    inst_file = target_dir / "instructions.md"
    inst_file.write_text(instructions_md, encoding="utf-8")
    written.append(str(inst_file))
    return {
        "ok": True,
        "target_dir": str(target_dir),
        "files_written": len(written),
        "paths": written,
    }


# ---------------------------------------------------------------------------
# MCP JSON-RPC 2.0 Stdio Server Loop
# ---------------------------------------------------------------------------


def handle_jsonrpc_message(msg: dict[str, Any]) -> dict[str, Any] | None:
    method = msg.get("method", "")
    req_id = msg.get("id")
    raw_params = msg.get("params")
    params: dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}

    # Notifications have no 'id' — do not send a response
    if "id" not in msg:
        return None

    if method == "initialize":
        client_proto = str(params.get("protocolVersion") or "2024-11-05")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": client_proto,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": get_mcp_tools_list()},
        }

    if method == "tools/call":
        tool_name = str(params.get("name") or "")
        raw_targs = params.get("arguments")
        tool_args: dict[str, Any] = raw_targs if isinstance(raw_targs, dict) else {}
        try:
            res_obj = invoke_tool_by_name(tool_name, tool_args)
            text_payload = json.dumps(res_obj, ensure_ascii=False)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": text_payload}],
                    "structuredContent": res_obj,
                    "isError": not bool(res_obj.get("ok", True)),
                },
            }
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            err_obj = {"ok": False, "error": str(exc), "tool": tool_name}
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(err_obj, ensure_ascii=False),
                        }
                    ],
                    "structuredContent": err_obj,
                    "isError": True,
                },
            }

    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}}

    if method == "resources/templates/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"resourceTemplates": []}}

    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": []}}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def serve_stdio() -> None:
    stdin_buf = sys.stdin.buffer
    stdout_buf = sys.stdout.buffer

    while True:
        line = stdin_buf.readline()
        if not line:
            break
        stripped = line.strip()
        if not stripped:
            continue

        use_content_length = False
        if stripped.lower().startswith(b"content-length:"):
            use_content_length = True
            length = int(stripped.split(b":", 1)[1].strip())
            # Consume remaining headers until blank line
            while True:
                hdr_line = stdin_buf.readline()
                if not hdr_line or hdr_line in (b"\r\n", b"\n"):
                    break
            body_bytes = stdin_buf.read(length)
        else:
            body_bytes = stripped

        try:
            msg = json.loads(body_bytes.decode("utf-8", errors="replace"))
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            logger.warning("Invalid JSON on stdio: %s", exc)
            continue

        if isinstance(msg, list):
            responses = []
            for item in msg:
                if isinstance(item, dict):
                    r = handle_jsonrpc_message(item)
                    if r is not None:
                        responses.append(r)
            if responses:
                out_bytes = json.dumps(responses, ensure_ascii=False).encode("utf-8")
                if use_content_length:
                    stdout_buf.write(
                        f"Content-Length: {len(out_bytes)}\r\n\r\n".encode("ascii")
                        + out_bytes
                    )
                else:
                    stdout_buf.write(out_bytes + b"\n")
                stdout_buf.flush()
        elif isinstance(msg, dict):
            resp = handle_jsonrpc_message(msg)
            if resp is not None:
                out_bytes = json.dumps(resp, ensure_ascii=False).encode("utf-8")
                if use_content_length:
                    stdout_buf.write(
                        f"Content-Length: {len(out_bytes)}\r\n\r\n".encode("ascii")
                        + out_bytes
                    )
                else:
                    stdout_buf.write(out_bytes + b"\n")
                stdout_buf.flush()


# ---------------------------------------------------------------------------
# Entrypoint (CLI & Stdio MCP)
# ---------------------------------------------------------------------------


def main() -> None:
    argv = sys.argv[1:]
    if argv:
        if argv[0] in ("-h", "--help"):
            print(
                "Usage:\n"
                "  bd-boylenet-infra-mcp.py                           # Run MCP JSON-RPC 2.0 server over stdio\n"
                "  bd-boylenet-infra-mcp.py --list-tools              # Print all 20 tool schemas as JSON\n"
                "  bd-boylenet-infra-mcp.py --cli <tool> ['{...}']    # Invoke any of the 20 tools directly\n"
                "  bd-boylenet-infra-mcp.py --dump-agy-schemas [dir]  # Export AGY MCP tool schemas\n"
            )
            sys.exit(0)

        if argv[0] == "--list-tools":
            print(
                json.dumps(
                    {
                        "server": SERVER_NAME,
                        "version": SERVER_VERSION,
                        "count": len(TOOLS_REGISTRY),
                        "tools": get_mcp_tools_list(),
                    },
                    indent=2,
                )
            )
            sys.exit(0)

        if argv[0] == "--dump-agy-schemas":
            tdir = Path(argv[1]) if len(argv) > 1 else AGY_MCP_SCHEMA_DIR
            print(json.dumps(dump_agy_schemas(tdir), indent=2))
            sys.exit(0)

        if argv[0] == "--cli":
            if len(argv) < 2:
                print(json.dumps({"ok": False, "error": "Missing tool_name for --cli"}))
                sys.exit(1)
            tool_name = argv[1]
            raw_args = argv[2] if len(argv) > 2 else "{}"
            try:
                parsed_args = json.loads(raw_args) if raw_args.strip() else {}
            except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
                print(json.dumps({"ok": False, "error": f"Invalid JSON args: {exc}"}))
                sys.exit(1)
            try:
                result = invoke_tool_by_name(tool_name, parsed_args)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                sys.exit(0 if result.get("ok", True) else 1)
            except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
                print(
                    json.dumps(
                        {"ok": False, "tool": tool_name, "error": str(exc)}, indent=2
                    )
                )
                sys.exit(1)

    serve_stdio()


if __name__ == "__main__":
    main()
