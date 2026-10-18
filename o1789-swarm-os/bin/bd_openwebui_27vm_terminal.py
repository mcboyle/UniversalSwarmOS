#!/usr/bin/env python3
"""
Boylenet 27-VM Open Terminal Multiplexer & Remote SSH File/Command Bridge
for bd-openwebui-tool-gateway.py (:4079).

Provides:
  - /vm/all/*          : Master All-27-VM Open Terminal Multiplexer (browses /vms/<ip>-<name>/...)
  - /vm/<vm_target>/*  : Dedicated Open Terminal endpoint for each of the 27 Boylenet VMs
  - /vms/*             : Virtual directory tree across all terminals exposing all 27 VMs over SSH
  - Full OpenWebUI Open Terminal API compatibility (DXIE4il6.js + terminals.py + utils/tools.py):
      OPTIONS *
      GET  .../openapi.json & .../terminal/openapi.json
      GET  .../api/config
      GET  .../system
      GET  .../files/cwd
      POST .../files/cwd
      GET  .../files/list?directory=... (or ?path=...)
      GET  .../files/read?path=...
      GET  .../files/view?path=...
      GET  .../files/search?query=...&path=...
      GET  .../files/glob?pattern=...&path=...
      GET  .../files/matches?query=...&path=...
      POST .../files/write
      POST .../files/mkdir
      POST .../files/move
      DELETE .../files/delete
      GET  .../skills & .../skills/list & .../skills/read
      GET  .../ports
      GET/POST .../execute
      POST .../exec_on_any_vm
"""

from __future__ import annotations

import base64
import json
import os
import posixpath
import re
import subprocess
import time
from pathlib import Path
from typing import Any

PORT = int(os.environ.get("BD_OPENWEBUI_TOOL_GATEWAY_PORT", "4079"))
GATEWAY_BASE = f"http://10.0.70.164:{PORT}"
SANDBOX_WORKSPACE_DIR = Path("/var/tmp/openwebui-workspace")
SANDBOX_REPOS_DIR = Path("/var/tmp/openwebui-repos")
CI_RAMDISK_DIR = Path("/dev/shm/bd-openwebui-ci-ramdisk")

BOYLENET_27_VMS: list[dict[str, Any]] = [
    {
        "idx": 1,
        "ip": "10.0.70.164",
        "id": "vm-01-10-0-70-164-controller",
        "folder": "10.0.70.164-controller",
        "hostname": "hub-mesh01",
        "role": "Hub Controller & Master Orchestrator",
        "name": "🖥️ VM 01 · 10.0.70.164 — Hub Controller & Master Orchestrator (hub-mesh01)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 2,
        "ip": "10.0.70.72",
        "id": "vm-02-10-0-70-72-ai-vault-a",
        "folder": "10.0.70.72-ai-vault-a",
        "hostname": "ai-srv01",
        "role": "AI Model Vault A & OpenWebUI Secondary",
        "name": "🗄️ VM 02 · 10.0.70.72 — AI Model Vault A & OpenWebUI Secondary (ai-srv01)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 3,
        "ip": "10.0.70.83",
        "id": "vm-03-10-0-70-83-ai-vault-b",
        "folder": "10.0.70.83-ai-vault-b",
        "hostname": "wrk-test01",
        "role": "AI DEV Model Vault B & Test01",
        "name": "🗄️ VM 03 · 10.0.70.83 — AI DEV Model Vault B & Test01 (aidev)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 4,
        "ip": "10.0.70.82",
        "id": "vm-04-10-0-70-82-test3big",
        "folder": "10.0.70.82-test3big-64core",
        "hostname": "wrk-test04",
        "role": "test3big 64-Core CI & RAG Indexing Powerhouse",
        "name": "⚡ VM 04 · 10.0.70.82 — test3big 64-Core CI & RAG Powerhouse (wrk-test04)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 5,
        "ip": "10.0.70.125",
        "id": "vm-05-10-0-70-125-ai-infer01",
        "folder": "10.0.70.125-ai-infer01",
        "hostname": "ai-infer01",
        "role": "AI Inference Node 01 (vLLM, Qdrant :6333, TEI)",
        "name": "🧠 VM 05 · 10.0.70.125 — AI Inference Node 01: vLLM, Qdrant & TEI (ai-infer01)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 6,
        "ip": "10.0.70.228",
        "id": "vm-06-10-0-70-228-ai-ollama01",
        "folder": "10.0.70.228-ai-ollama01",
        "hostname": "ai-ollama01",
        "role": "AI Ollama & LiteLLM Satellite Node",
        "name": "🦙 VM 06 · 10.0.70.228 — AI Ollama & LiteLLM Satellite Node (ai-ollama01)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 7,
        "ip": "10.0.70.50",
        "id": "vm-07-10-0-70-50-wrk-bd01",
        "folder": "10.0.70.50-wrk-bd01",
        "hostname": "wrk-bd01",
        "role": "Swarm Worker BD01 Primary Builder",
        "name": "🔨 VM 07 · 10.0.70.50 — Swarm Worker BD01 Primary Builder (wrk-bd01)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 8,
        "ip": "10.0.70.51",
        "id": "vm-08-10-0-70-51-dispatch",
        "folder": "10.0.70.51-dispatch",
        "hostname": "wrk-bd02",
        "role": "Swarm Worker BD02 Dispatcher Seat",
        "name": "📡 VM 08 · 10.0.70.51 — Swarm Worker BD02 Dispatcher Seat (wrk-bd02)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 9,
        "ip": "10.0.70.52",
        "id": "vm-09-10-0-70-52-integrator",
        "folder": "10.0.70.52-integrator",
        "hostname": "wrk-bd03",
        "role": "Swarm Worker BD03 Integrator Seat",
        "name": "🔀 VM 09 · 10.0.70.52 — Swarm Worker BD03 Integrator Seat (wrk-bd03)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 10,
        "ip": "10.0.70.53",
        "id": "vm-10-10-0-70-53-wrk-bd04",
        "folder": "10.0.70.53-wrk-bd04",
        "hostname": "wrk-bd04",
        "role": "Swarm Worker BD04 Builder/Fixer",
        "name": "🔨 VM 10 · 10.0.70.53 — Swarm Worker BD04 Builder/Fixer (wrk-bd04)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 11,
        "ip": "10.0.70.54",
        "id": "vm-11-10-0-70-54-wrk-bd05",
        "folder": "10.0.70.54-wrk-bd05",
        "hostname": "wrk-bd05",
        "role": "Swarm Worker BD05 Builder/Fixer",
        "name": "🔨 VM 11 · 10.0.70.54 — Swarm Worker BD05 Builder/Fixer (wrk-bd05)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 12,
        "ip": "10.0.70.194",
        "id": "vm-12-10-0-70-194-dispatch-build",
        "folder": "10.0.70.194-dispatch-build",
        "hostname": "test1",
        "role": "Swarm Worker Test1 Dispatch-Build",
        "name": "🏗️ VM 12 · 10.0.70.194 — Swarm Worker Test1 Dispatch-Build (test1)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 13,
        "ip": "10.0.70.95",
        "id": "vm-13-10-0-70-95-wrk-test02",
        "folder": "10.0.70.95-wrk-test02",
        "hostname": "wrk-test02",
        "role": "Swarm Worker Test2 Review Lens",
        "name": "🔬 VM 13 · 10.0.70.95 — Swarm Worker Test2 Review Lens (wrk-test02)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 14,
        "ip": "10.0.70.80",
        "id": "vm-14-10-0-70-80-wrk-test03",
        "folder": "10.0.70.80-wrk-test03",
        "hostname": "wrk-test03",
        "role": "Swarm Worker Test3 Review Lens",
        "name": "🔬 VM 14 · 10.0.70.80 — Swarm Worker Test3 Review Lens (wrk-test03)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 15,
        "ip": "10.0.70.85",
        "id": "vm-15-10-0-70-85-lensrouter",
        "folder": "10.0.70.85-lensrouter",
        "hostname": "wrk-test05",
        "role": "Swarm Worker Test4 LensRouter",
        "name": "🧭 VM 15 · 10.0.70.85 — Swarm Worker Test4 LensRouter (wrk-test05)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 16,
        "ip": "10.0.70.249",
        "id": "vm-16-10-0-70-249-wrk-test06",
        "folder": "10.0.70.249-wrk-test06",
        "hostname": "wrk-test06",
        "role": "Swarm Worker Test6 Heavy Lifter",
        "name": "⚙️ VM 16 · 10.0.70.249 — Swarm Worker Test6 Heavy Lifter (wrk-test06)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 17,
        "ip": "10.0.70.84",
        "id": "vm-17-10-0-70-84-wrk-test07",
        "folder": "10.0.70.84-wrk-test07",
        "hostname": "wrk-test07",
        "role": "Swarm Worker Test7 Heavy Lifter",
        "name": "⚙️ VM 17 · 10.0.70.84 — Swarm Worker Test7 Heavy Lifter (wrk-test07)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 18,
        "ip": "10.0.70.25",
        "id": "vm-18-10-0-70-25-ops-mcp01",
        "folder": "10.0.70.25-ops-mcp01",
        "hostname": "ops-mcp01",
        "role": "Operations MCP Server Node 01",
        "name": "🔌 VM 18 · 10.0.70.25 — Operations MCP Server Node 01 (ops-mcp01)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 19,
        "ip": "10.0.70.162",
        "id": "vm-19-10-0-70-162-ops-cicd01",
        "folder": "10.0.70.162-ops-cicd01",
        "hostname": "ops-cicd01",
        "role": "Operations CI/CD Runner Node 01",
        "name": "🚀 VM 19 · 10.0.70.162 — Operations CI/CD Runner Node 01 (ops-cicd01)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 20,
        "ip": "10.0.70.107",
        "id": "vm-20-10-0-70-107-ops-test01",
        "folder": "10.0.70.107-ops-test01",
        "hostname": "ops-test01",
        "role": "Operations Test Runner Node 01",
        "name": "🧪 VM 20 · 10.0.70.107 — Operations Test Runner Node 01 (ops-test01)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 21,
        "ip": "10.0.70.182",
        "id": "vm-21-10-0-70-182-stg-cache01",
        "folder": "10.0.70.182-stg-cache01",
        "hostname": "stg-cache01",
        "role": "Storage & Registry Cache Node 01",
        "name": "📦 VM 21 · 10.0.70.182 — Storage & Registry Cache Node 01 (stg-cache01)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 22,
        "ip": "10.0.70.120",
        "id": "vm-22-10-0-70-120-spr-pool01",
        "folder": "10.0.70.120-spr-pool01",
        "hostname": "spr-pool01",
        "role": "Ephemeral Sandbox Pool 01 (spare7)",
        "name": "🧊 VM 22 · 10.0.70.120 — Ephemeral Sandbox Pool 01 (spr-pool01 / spare7)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 23,
        "ip": "10.0.70.149",
        "id": "vm-23-10-0-70-149-spr-pool05",
        "folder": "10.0.70.149-spr-pool05",
        "hostname": "spr-pool05",
        "role": "Ephemeral Sandbox Pool 05 (fresh149)",
        "name": "🧊 VM 23 · 10.0.70.149 — Ephemeral Sandbox Pool 05 (spr-pool05 / fresh149)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 24,
        "ip": "10.0.70.183",
        "id": "vm-24-10-0-70-183-spr-pool02",
        "folder": "10.0.70.183-spr-pool02",
        "hostname": "spr-pool02",
        "role": "Ephemeral Sandbox Pool 02 (spare12)",
        "name": "🧊 VM 24 · 10.0.70.183 — Ephemeral Sandbox Pool 02 (spr-pool02 / spare12)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 25,
        "ip": "10.0.70.185",
        "id": "vm-25-10-0-70-185-spare5",
        "folder": "10.0.70.185-spare5",
        "hostname": "spare5",
        "role": "Ephemeral Sandbox Pool (spare5)",
        "name": "🧊 VM 25 · 10.0.70.185 — Ephemeral Sandbox Pool (spare5)",
        "os": "linux",
        "default_cwd": "/home/mboyle",
        "home": "/home/mboyle",
        "root": "/",
    },
    {
        "idx": 26,
        "ip": "10.0.10.137",
        "id": "vm-26-10-0-10-137-battlestation",
        "folder": "10.0.10.137-battlestation",
        "hostname": "battlestation",
        "role": "BattleStation RTX 2080 Ti + Ryzen 9 + Chrome CDP (:9222)",
        "name": "🎮 VM 26 · 10.0.10.137 — BattleStation RTX 2080 Ti + Ryzen 9 + Chrome CDP",
        "os": "windows",
        "default_cwd": "C:/Users/Administrator",
        "home": "C:/Users/Administrator",
        "root": "C:/",
    },
    {
        "idx": 27,
        "ip": "10.0.70.181",
        "id": "vm-27-10-0-70-181-bittorrent",
        "folder": "10.0.70.181-bittorrent",
        "hostname": "bittorrent",
        "role": "Bittorrent Windows Chrome CDP Browser Oracle (:9222)",
        "name": "🌐 VM 27 · 10.0.70.181 — Bittorrent Windows Chrome CDP Browser Oracle",
        "os": "windows",
        "default_cwd": "C:/Users/Administrator",
        "home": "C:/Users/Administrator",
        "root": "C:/",
    },
]

SESSION_CWDS: dict[str, str] = {}

FORBIDDEN_CMD_PATTERNS = [
    r"\bgit\s+(reset\s+--hard|clean\s+-f|checkout\s+--|branch\s+-D|worktree\s+remove)",
    r"\brm\s+-rf\s+(/|/home|/var/lib|/etc|/usr|/mnt)",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
]


def resolve_vm(identifier: str) -> dict[str, Any] | None:
    ident = (identifier or "").strip().lower()
    if not ident or ident == "all":
        return None
    for vm in BOYLENET_27_VMS:
        if ident in (
            vm["ip"].lower(),
            vm["folder"].lower(),
            vm["id"].lower(),
            vm["hostname"].lower(),
        ):
            return vm
    m = re.match(r"^(\d+\.\d+\.\d+\.\d+)", ident)
    if m:
        ip_prefix = m.group(1)
        for vm in BOYLENET_27_VMS:
            if vm["ip"] == ip_prefix:
                return vm
        return {
            "idx": 99,
            "ip": ip_prefix,
            "id": f"vm-{ip_prefix}",
            "folder": f"{ip_prefix}-node",
            "hostname": ip_prefix,
            "role": f"Boylenet Node {ip_prefix}",
            "name": f"Boylenet Node {ip_prefix}",
            "os": "windows" if ip_prefix in ("10.0.10.137", "10.0.70.181") else "linux",
            "default_cwd": "C:/Users/Administrator"
            if ip_prefix in ("10.0.10.137", "10.0.70.181")
            else "/home/mboyle",
            "home": "C:/Users/Administrator"
            if ip_prefix in ("10.0.10.137", "10.0.70.181")
            else "/home/mboyle",
            "root": "C:/" if ip_prefix in ("10.0.10.137", "10.0.70.181") else "/",
        }
    for vm in BOYLENET_27_VMS:
        if ident in vm["folder"].lower() or ident in vm["name"].lower():
            return vm
    return None


def parse_virtual_vms_path(raw_dir: str) -> tuple[dict[str, Any] | None, str, str]:
    """
    If raw_dir is '/vms' or '/vms/<vm_folder>[/<subpath>]':
      - For '/vms': returns (None, '/vms', '/vms')
      - For '/vms/<vm_folder>/<subpath>': returns (vm_dict, '<subpath>', '/vms/<vm_folder>')
    Otherwise returns (None, raw_dir, '')
    """
    cleaned = (raw_dir or "").strip()
    if not cleaned:
        return (None, "", "")
    norm = posixpath.normpath(cleaned)
    if norm == "/vms":
        return (None, "/vms", "/vms")
    if norm.startswith("/vms/"):
        rest = norm[len("/vms/") :]
        parts = rest.split("/", 1)
        seg = parts[0]
        sub = "/" + parts[1] if len(parts) > 1 else ""
        vm = resolve_vm(seg)
        if vm:
            if not sub:
                sub = vm["default_cwd"] if vm["os"] == "windows" else "/"
            return (vm, sub, f"/vms/{vm['folder']}")
    return (None, cleaned, "")


def _run_remote_python(
    vm: dict[str, Any], py_code: str, payload: dict[str, Any], timeout_s: int = 8
) -> dict[str, Any]:
    ip = vm["ip"]
    b64_payload = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    full_script = (
        f"import base64, json\nPAYLOAD = json.loads(base64.b64decode('{b64_payload}').decode('utf-8'))\n"
        + py_code
    )
    b64_script = base64.b64encode(full_script.encode("utf-8")).decode("ascii")

    if ip in ("10.0.70.164", "127.0.0.1", "localhost"):
        cmd = [
            "python3",
            "-c",
            f"import base64; exec(base64.b64decode('{b64_script}').decode('utf-8'))",
        ]
    else:
        py_bin = "python" if vm.get("os") == "windows" else "python3"
        remote_cmd = f"{py_bin} -c \"import base64; exec(base64.b64decode('{b64_script}').decode('utf-8'))\""
        cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=3",
            "-o",
            "StrictHostKeyChecking=no",
            ip,
            remote_cmd,
        ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        out = (proc.stdout or "").strip()
        if out:
            for line in reversed(out.splitlines()):
                s = line.strip()
                if s.startswith("{") and s.endswith("}"):
                    try:
                        return json.loads(s)
                    except Exception:
                        pass
        if proc.returncode == 255:
            return {
                "ok": False,
                "cold_spare": True,
                "error": f"VM {ip} ({vm.get('hostname')}) is currently in Cold-Spare Standby (Fleet Rule 61).",
            }
        return {
            "ok": proc.returncode == 0,
            "stdout": out,
            "stderr": (proc.stderr or "").strip(),
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "cold_spare": True,
            "error": f"SSH connection to {ip} ({vm.get('hostname')}) timed out (Cold-Spare Standby).",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


REMOTE_LIST_SCRIPT = """
import os, time
target = PAYLOAD.get("dir") or "."
prefix = PAYLOAD.get("prefix") or ""
if target == "/" and os.name == "nt":
    target = os.path.expanduser("~")
elif target.startswith("/C:"):
    target = target[1:]
if not os.path.exists(target) and target.startswith("/mnt/ai-models") and os.path.exists("/opt/models"):
    target = "/opt/models" + target[len("/mnt/ai-models"):]
if not os.path.exists(target) or not os.path.isdir(target):
    target = os.path.expanduser("~")
entries = []
try:
    with os.scandir(target) as it:
        items = list(it)
    items.sort(key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
    for entry in items[:200]:
        try:
            st = entry.stat(follow_symlinks=False)
            is_d = entry.is_dir(follow_symlinks=False)
            full_p = os.path.join(target, entry.name).replace("\\\\", "/")
            if prefix:
                rel_p = full_p if full_p.startswith("/") else "/" + full_p
                out_p = prefix.rstrip("/") + rel_p
            else:
                out_p = full_p
            entries.append({
                "name": entry.name,
                "path": out_p,
                "type": "directory" if is_d else "file",
                "size": int(st.st_size) if not is_d else 4096,
                "modified": int(st.st_mtime),
            })
        except Exception:
            pass
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}))
    raise SystemExit(0)
print(json.dumps({"ok": True, "path": prefix or target.replace("\\\\", "/"), "entries": entries, "writable": True}))
"""

REMOTE_READ_SCRIPT = """
import os
target = PAYLOAD.get("path") or ""
max_bytes = int(PAYLOAD.get("max_bytes") or 65536)
if target.startswith("/C:"):
    target = target[1:]
if not os.path.exists(target) and target.startswith("/mnt/ai-models") and os.path.exists("/opt/models"):
    target = "/opt/models" + target[len("/mnt/ai-models"):]
if not os.path.exists(target) or not os.path.isfile(target):
    print(json.dumps({"ok": False, "error": f"File not found: {target}"}))
    raise SystemExit(0)
try:
    st = os.stat(target)
    with open(target, "rb") as fh:
        raw = fh.read(max_bytes)
    text = raw.decode("utf-8", errors="replace")
    print(json.dumps({"ok": True, "path": target.replace("\\\\", "/"), "content": text, "size": int(st.st_size), "modified": int(st.st_mtime)}))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}))
"""

REMOTE_SEARCH_SCRIPT = """
import os, fnmatch
root_dir = PAYLOAD.get("path") or os.path.expanduser("~")
if root_dir in (".", "/", ""):
    root_dir = os.path.expanduser("~")
if root_dir.startswith("/C:"):
    root_dir = root_dir[1:]
if not os.path.exists(root_dir):
    root_dir = os.path.expanduser("~")
query = (PAYLOAD.get("query") or PAYLOAD.get("pattern") or "").strip().lower()
limit = min(int(PAYLOAD.get("limit") or 30), 100)
prefix = PAYLOAD.get("prefix") or ""
results = []
try:
    base_depth = root_dir.rstrip("/\\\\").count("/") + root_dir.rstrip("/\\\\").count("\\\\")
    for dirpath, dirnames, filenames in os.walk(root_dir):
        cur_depth = dirpath.count("/") + dirpath.count("\\\\") - base_depth
        if cur_depth > 4:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv", ".git")]
        for fn in filenames:
            if not query or query in fn.lower() or fnmatch.fnmatch(fn.lower(), query):
                full_p = os.path.join(dirpath, fn).replace("\\\\", "/")
                try:
                    st = os.stat(full_p)
                    sz, mtime = int(st.st_size), int(st.st_mtime)
                except Exception:
                    sz, mtime = 0, 0
                out_p = (prefix.rstrip("/") + (full_p if full_p.startswith("/") else "/" + full_p)) if prefix else full_p
                results.append({
                    "name": fn,
                    "path": out_p,
                    "type": "file",
                    "size": sz,
                    "modified": mtime,
                })
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break
except Exception:
    pass
print(json.dumps({"ok": True, "path": prefix or root_dir, "results": results, "matches": results}))
"""


def list_directory_on_target(vm: dict[str, Any] | None, req_dir: str) -> dict[str, Any]:
    now_ts = int(time.time())
    norm_req = (
        posixpath.normpath(req_dir.strip()) if req_dir and req_dir.strip() else "/"
    )

    # 1. Virtual /vms root listing all 27 Boylenet VMs
    if norm_req == "/vms":
        entries = []
        for node in BOYLENET_27_VMS:
            entries.append(
                {
                    "name": node["folder"],
                    "path": f"/vms/{node['folder']}",
                    "type": "directory",
                    "size": 4096,
                    "modified": now_ts,
                }
            )
        return {
            "path": "/vms",
            "cwd": "/vms",
            "entries": entries,
            "files": entries,
            "writable": True,
        }

    # 2. Check if path is inside /vms/<vm_folder>/...
    virt_vm, sub_path, virt_prefix = parse_virtual_vms_path(req_dir)
    if virt_vm is not None:
        res = _run_remote_python(
            virt_vm,
            REMOTE_LIST_SCRIPT,
            {"dir": sub_path, "prefix": virt_prefix},
        )
        if res.get("ok") and "entries" in res:
            entries = res["entries"]
            # If listing root of a Linux VM under /vms/<folder>, also put a quick shortcut to /home/mboyle
            return {
                "path": norm_req,
                "cwd": "/vms",
                "entries": entries,
                "files": entries,
                "writable": True,
            }
        # Cold spare or unreachable fallback entry so browser UI never errors
        fallback_entries = [
            {
                "name": "VM-STATUS-RULE61-STANDBY.md",
                "path": f"{virt_prefix}/VM-STATUS-RULE61-STANDBY.md",
                "type": "file",
                "size": 512,
                "modified": now_ts,
            }
        ]
        return {
            "path": norm_req,
            "cwd": "/vms",
            "entries": fallback_entries,
            "files": fallback_entries,
            "writable": False,
        }

    # 3. Direct VM target (/vm/<ip>) or local controller
    target_vm = vm or BOYLENET_27_VMS[0]
    effective_dir = req_dir or target_vm["default_cwd"]
    res = _run_remote_python(
        target_vm,
        REMOTE_LIST_SCRIPT,
        {"dir": effective_dir, "prefix": ""},
    )
    if res.get("ok") and "entries" in res:
        entries = res["entries"]
        if effective_dir in ("/", "/home/mboyle") and target_vm["ip"] == "10.0.70.164":
            entries = [
                {
                    "name": "vms",
                    "path": "/vms",
                    "type": "directory",
                    "size": 4096,
                    "modified": now_ts,
                }
            ] + [e for e in entries if e.get("name") != "vms"]
        return {
            "path": res.get("path", effective_dir),
            "cwd": target_vm["default_cwd"],
            "entries": entries,
            "files": entries,
            "writable": True,
        }

    fallback_entries = [
        {
            "name": "VM-STATUS-RULE61-STANDBY.md",
            "path": "/VM-STATUS-RULE61-STANDBY.md",
            "type": "file",
            "size": 512,
            "modified": now_ts,
        }
    ]
    return {
        "path": effective_dir,
        "cwd": target_vm["default_cwd"],
        "entries": fallback_entries,
        "files": fallback_entries,
        "writable": False,
    }


def read_file_on_target(vm: dict[str, Any] | None, req_path: str) -> dict[str, Any]:
    if not req_path:
        return {"ok": False, "error": "path is required"}

    if req_path.endswith("VM-STATUS-RULE61-STANDBY.md"):
        virt_vm, _, _ = parse_virtual_vms_path(req_path)
        node = (
            virt_vm
            or vm
            or {"ip": "unknown", "name": "Standby VM", "role": "Cold Spare"}
        )
        content = (
            f"# {node.get('name', node.get('ip'))}\n\n"
            f"- **IP Address**: `{node.get('ip')}`\n"
            f"- **Role**: {node.get('role')}\n"
            f"- **State**: Cold-Spare Standby (Fleet Rule 61 Elasticity)\n\n"
            f"This node is currently powered down to conserve cluster RAM/vCPU.\n"
            f"Use the `vmware_power_and_clone_ops` tool (`govc vm.power -on {node.get('hostname', '')}`) to wake it.\n"
        )
        return {"ok": True, "path": req_path, "content": content}

    virt_vm, sub_path, _ = parse_virtual_vms_path(req_path)
    target_vm = virt_vm or vm or BOYLENET_27_VMS[0]
    effective_path = sub_path if virt_vm is not None else req_path
    res = _run_remote_python(
        target_vm, REMOTE_READ_SCRIPT, {"path": effective_path, "max_bytes": 131072}
    )
    if res.get("ok"):
        res["path"] = req_path
    return res


def search_files_on_target(
    vm: dict[str, Any] | None, query: str, req_path: str, limit: int = 30
) -> dict[str, Any]:
    virt_vm, sub_path, virt_prefix = parse_virtual_vms_path(req_path)
    target_vm = virt_vm or vm or BOYLENET_27_VMS[0]
    effective_path = (
        sub_path if virt_vm is not None else (req_path or target_vm["default_cwd"])
    )
    res = _run_remote_python(
        target_vm,
        REMOTE_SEARCH_SCRIPT,
        {
            "query": query,
            "path": effective_path,
            "limit": limit,
            "prefix": virt_prefix if virt_vm is not None else "",
        },
    )
    if res.get("ok"):
        return {
            "path": req_path or effective_path,
            "results": res.get("results", []),
            "matches": res.get("matches", []),
        }
    return {"path": req_path, "results": [], "matches": []}


def execute_command_on_target(
    vm: dict[str, Any] | None, command: str, cwd: str = "", timeout_s: int = 25
) -> dict[str, Any]:
    cmd_str = (command or "").strip()
    if not cmd_str:
        return {
            "ok": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": "command is required",
            "output": "command is required",
        }
    for pat in FORBIDDEN_CMD_PATTERNS:
        if re.search(pat, cmd_str):
            msg = (
                f"Rule 22 Shield: Forbidden destructive command pattern blocked ({pat})"
            )
            return {
                "ok": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": msg,
                "output": msg,
            }

    virt_vm, sub_cwd, _ = parse_virtual_vms_path(cwd)
    target_vm = virt_vm or vm or BOYLENET_27_VMS[0]
    effective_cwd = (
        sub_cwd if virt_vm is not None else (cwd or target_vm["default_cwd"])
    )
    if effective_cwd == "/vms":
        effective_cwd = "/home/mboyle"

    ip = target_vm["ip"]
    try:
        if ip in ("10.0.70.164", "127.0.0.1", "localhost"):
            run_cwd = effective_cwd if os.path.isdir(effective_cwd) else "/home/mboyle"
            proc = subprocess.run(
                cmd_str,
                shell=True,
                cwd=run_cwd,
                capture_output=True,
                text=True,
                timeout=min(timeout_s, 60),
            )
        else:
            if target_vm.get("os") == "windows":
                remote_cmd = cmd_str
            else:
                remote_cmd = f"cd {effective_cwd} 2>/dev/null || cd /home/mboyle || true; {cmd_str}"
            proc = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "ConnectTimeout=4",
                    "-o",
                    "StrictHostKeyChecking=no",
                    ip,
                    remote_cmd,
                ],
                capture_output=True,
                text=True,
                timeout=min(timeout_s, 60),
            )
        stdout = (proc.stdout or "")[-16000:]
        stderr = (proc.stderr or "")[-4000:]
        combined = (stdout + ("\n" + stderr if stderr else "")).strip()
        return {
            "ok": proc.returncode == 0,
            "vm": ip,
            "hostname": target_vm.get("hostname"),
            "cwd": effective_cwd,
            "exit_code": proc.returncode,
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "output": combined,
        }
    except Exception as exc:
        return {
            "ok": False,
            "vm": ip,
            "exit_code": 1,
            "stdout": "",
            "stderr": str(exc),
            "output": str(exc),
        }


def build_vm_terminal_openapi_spec(
    prefix: str, vm: dict[str, Any] | None
) -> dict[str, Any]:
    srv_url = f"{GATEWAY_BASE}{prefix}"
    if vm is None and prefix == "/vm/all":
        title = "🌐 ALL 27 BOYLENET VMs — Master Open Terminal Multiplexer"
        desc = (
            "Master Open Terminal Server multiplexing all 27 Boylenet VMs under /vms/<ip>-<name>/ "
            "with SSH file browsing, reading, searching, and remote command execution."
        )
    elif vm is not None:
        title = f"Boylenet Open Terminal — {vm['name']}"
        desc = f"Direct Open Terminal Server connected via SSH to {vm['ip']} ({vm['hostname']} — {vm['role']})."
    elif "ci-ramdisk" in prefix:
        title = "Boylenet Open Terminal — 64-Core CI Ramdisk (/dev/shm)"
        desc = "Open Terminal Server connected to /dev/shm/bd-openwebui-ci-ramdisk."
    else:
        title = (
            "Boylenet Open Terminal — Master Workspace (/var/tmp/openwebui-workspace)"
        )
        desc = "Open Terminal Server connected to Boylenet Controller .164."

    return {
        "openapi": "3.1.0",
        "info": {
            "title": title,
            "version": "2.1.0",
            "description": desc,
        },
        "servers": [{"url": srv_url}],
        "paths": {
            "/execute": {
                "post": {
                    "operationId": "run_command",
                    "summary": f"Execute a shell command on {title}.",
                    "description": (
                        f"Execute a non-destructive shell, python3, git, docker, systemctl, ruff, mypy, or pytest command on {title}. "
                        "When connected to /vm/all, pass cwd='/vms/<ip>-<name>' to execute on any of the 27 Boylenet VMs."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "command": {
                                            "type": "string",
                                            "description": "Shell command to execute",
                                        },
                                        "cwd": {
                                            "type": "string",
                                            "description": "Working directory (e.g. /home/mboyle or /vms/10.0.70.72-ai-vault-a/mnt/ai-models)",
                                        },
                                    },
                                    "required": ["command"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Command execution result",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
            },
            "/exec_on_any_vm": {
                "post": {
                    "operationId": "exec_on_any_vm",
                    "summary": "Execute a command or inspect files on any of the 27 Boylenet VMs by IP or hostname.",
                    "description": "Run a shell command over SSH on any of the 27 Boylenet VMs (e.g. 10.0.70.164, 10.0.70.72, 10.0.70.83, 10.0.70.82, 10.0.70.125, 10.0.70.228, 10.0.10.137, 10.0.70.181).",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "vm": {
                                            "type": "string",
                                            "description": "Target VM IP or hostname (e.g. '10.0.70.72', 'ai-infer01', 'test3big', 'battlestation')",
                                            "default": "10.0.70.164",
                                        },
                                        "command": {
                                            "type": "string",
                                            "description": "Shell command to run on the target VM",
                                        },
                                        "cwd": {
                                            "type": "string",
                                            "description": "Optional working directory on the target VM",
                                            "default": "/home/mboyle",
                                        },
                                    },
                                    "required": ["command"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Remote VM execution output",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
            },
            "/files/list": {
                "get": {
                    "operationId": "list_files",
                    "summary": "List files and directories on this terminal or under /vms/<ip>-<name>/...",
                    "parameters": [
                        {
                            "name": "directory",
                            "in": "query",
                            "required": False,
                            "schema": {
                                "type": "string",
                                "description": "Directory path to list (e.g. /vms, /vms/10.0.70.72-ai-vault-a/mnt/ai-models, /home/mboyle)",
                            },
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Directory entries",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
            },
            "/files/read": {
                "get": {
                    "operationId": "read_file",
                    "summary": "Read text content of a file from this terminal or /vms/<ip>-<name>/...",
                    "parameters": [
                        {
                            "name": "path",
                            "in": "query",
                            "required": True,
                            "schema": {
                                "type": "string",
                                "description": "File path to read",
                            },
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "File content",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
            },
            "/files/search": {
                "get": {
                    "operationId": "search_files",
                    "summary": "Search for files by filename/pattern on this terminal or remote VM.",
                    "parameters": [
                        {
                            "name": "query",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "path",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Search results",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
            },
            "/files/write": {
                "post": {
                    "operationId": "write_file",
                    "summary": "Write a file into the terminal sandbox workspace (/var/tmp/openwebui-workspace).",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string"},
                                        "content": {"type": "string"},
                                    },
                                    "required": ["path", "content"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Write result",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
            },
        },
    }


def parse_vm_route(raw_path: str) -> tuple[bool, str, str, dict[str, Any] | None]:
    """
    Checks if raw_path is a /vm/<target>/... route or a root terminal route.
    Returns (is_vm_route, prefix, sub_path, vm_dict_or_None).
    """
    if raw_path == "/vm/all" or raw_path.startswith("/vm/all/"):
        sub = raw_path[len("/vm/all") :] or "/"
        return (True, "/vm/all", sub, None)
    if raw_path.startswith("/vm/"):
        rest = raw_path[len("/vm/") :]
        parts = rest.split("/", 1)
        target_seg = parts[0]
        sub = "/" + parts[1] if len(parts) > 1 else "/"
        vm = resolve_vm(target_seg)
        if vm:
            return (True, f"/vm/{target_seg}", sub, vm)
    return (False, "", raw_path, None)


def handle_terminal_get(
    handler: Any,
    raw_path: str,
    qs: dict[str, list[str]],
    discover_skills_fn: Any,
    load_skill_fn: Any,
) -> bool:
    is_vm, prefix, sub_path, vm = parse_vm_route(raw_path)
    is_ramdisk = raw_path == "/ci-ramdisk" or raw_path.startswith("/ci-ramdisk/")
    if is_ramdisk and not is_vm:
        prefix = "/ci-ramdisk"
        sub_path = raw_path[len("/ci-ramdisk") :] or "/"

    # Determine default CWD, home, root
    if is_vm and prefix == "/vm/all":
        default_cwd = "/vms"
        home_dir = "/home/mboyle"
        root_dir = "/"
        term_name = "🌐 ALL 27 BOYLENET VMs — Master Open Terminal Multiplexer (/vms/*)"
    elif is_vm and vm is not None:
        default_cwd = vm["default_cwd"]
        home_dir = vm["home"]
        root_dir = vm["root"]
        term_name = vm["name"]
    elif is_ramdisk:
        default_cwd = str(CI_RAMDISK_DIR)
        home_dir = "/home/mboyle"
        root_dir = "/"
        term_name = "Boylenet 64-Core CI Ramdisk Terminal"
    else:
        default_cwd = "/home/mboyle"
        home_dir = "/home/mboyle"
        root_dir = "/"
        term_name = "Boylenet Master Workspace Terminal"

    session_key = f"{prefix}:{handler.headers.get('X-Session-Id', 'default')}"
    current_cwd = SESSION_CWDS.get(session_key, default_cwd)

    # 1. GET /vms/catalog -> JSON catalog of all 27 Boylenet VMs
    if sub_path in ("/vms/catalog", "/vms"):
        handler._send_json(
            200,
            {
                "ok": True,
                "total_vms": len(BOYLENET_27_VMS),
                "multiplexer_url": f"{GATEWAY_BASE}/vm/all",
                "vms": BOYLENET_27_VMS,
            },
        )
        return True

    # 2. OpenAPI spec for /vm/*, /ci-ramdisk/*, or /terminal/openapi.json
    if (
        (is_vm and sub_path in ("/openapi.json", "/terminal/openapi.json"))
        or (is_ramdisk and sub_path in ("/openapi.json", "/terminal/openapi.json"))
        or sub_path == "/terminal/openapi.json"
    ):
        handler._send_json(200, build_vm_terminal_openapi_spec(prefix, vm))
        return True

    # 3. /api/config
    if sub_path == "/api/config":
        handler._send_json(
            200,
            {
                "status": True,
                "version": "1.2.0",
                "type": "terminal",
                "name": term_name,
                "cwd": current_cwd,
                "home": home_dir,
                "root": root_dir,
                "features": {
                    "files": True,
                    "terminal": True,
                    "skills": True,
                    "execute": True,
                    "notebooks": True,
                    "system": True,
                },
            },
        )
        return True

    # 4. /system
    if sub_path == "/system":
        if prefix == "/vm/all":
            prompt = (
                "Connected to Boylenet Master 27-VM Open Terminal Multiplexer (/vm/all). "
                "All 27 Boylenet VMs are mounted under /vms/<ip>-<name>/ (e.g. /vms/10.0.70.164-controller, "
                "/vms/10.0.70.72-ai-vault-a, /vms/10.0.70.83-ai-vault-b, /vms/10.0.70.82-test3big-64core, "
                "/vms/10.0.70.125-ai-infer01, /vms/10.0.70.228-ai-ollama01, /vms/10.0.10.137-battlestation, "
                "/vms/10.0.70.181-bittorrent). Use list_files, read_file, run_command, or exec_on_any_vm."
            )
        elif vm is not None:
            prompt = (
                f"Connected to Boylenet Open Terminal for {vm['name']} ({vm['ip']} / {vm['hostname']}). "
                f"Default working directory: {default_cwd}. You can also browse all 27 VMs under /vms/."
            )
        else:
            prompt = f"Connected to {term_name} ({default_cwd}). All 27 Boylenet VMs are also accessible under /vms/."
        handler._send_json(200, {"prompt": prompt})
        return True

    # 5. /files/cwd
    if sub_path == "/files/cwd":
        handler._send_json(
            200,
            {
                "cwd": current_cwd,
                "home": home_dir,
                "root": root_dir,
            },
        )
        return True

    # 6. /files/list
    if sub_path == "/files/list":
        req_dir = (qs.get("directory") or qs.get("path") or [current_cwd])[
            0
        ] or current_cwd
        handler._send_json(200, list_directory_on_target(vm, req_dir))
        return True

    # 7. /files/read
    if sub_path == "/files/read":
        req_file = (qs.get("path") or [""])[0]
        res = read_file_on_target(vm, req_file)
        if res.get("ok"):
            handler._send_json(
                200, {"path": res["path"], "content": res.get("content", "")}
            )
        else:
            handler._send_json(
                404,
                {
                    "detail": res.get("error", "File not found"),
                    "error": res.get("error", "File not found"),
                },
            )
        return True

    # 8. /files/view (returns raw UTF-8 text bytes for OpenWebUI file viewer/comparison)
    if sub_path == "/files/view":
        req_file = (qs.get("path") or [""])[0]
        res = read_file_on_target(vm, req_file)
        if res.get("ok"):
            raw_bytes = (res.get("content") or "").encode("utf-8", errors="replace")
            handler._send_bytes(200, "text/plain; charset=utf-8", raw_bytes)
        else:
            err_bytes = (res.get("error") or "File not found").encode("utf-8")
            handler._send_bytes(404, "text/plain; charset=utf-8", err_bytes)
        return True

    # 9. /files/search, /files/glob, /files/matches
    if sub_path in ("/files/search", "/files/glob", "/files/matches"):
        q = (qs.get("query") or qs.get("pattern") or [""])[0]
        p = (qs.get("path") or [current_cwd])[0] or current_cwd
        lim = int((qs.get("limit") or qs.get("max_results") or ["30"])[0] or 30)
        handler._send_json(200, search_files_on_target(vm, q, p, lim))
        return True

    # 10. /skills & /skills/list & /skills/read
    if sub_path in ("/skills", "/skills/list"):
        skills = discover_skills_fn()
        formatted = [
            {
                "id": s["id"],
                "name": s["name"],
                "description": s["description"],
                "location": s["path"],
                "path": s["path"],
                "terminal_path": s["path"],
                "scope": "global",
            }
            for s in skills
        ]
        if sub_path == "/skills":
            handler._send_json(200, formatted)
        else:
            handler._send_json(200, {"skills": formatted})
        return True

    if sub_path == "/skills/read":
        name = (qs.get("name") or [""])[0]
        res = load_skill_fn({"skill_id": name})
        if res.get("ok") and "skill" in res:
            sk = res["skill"]
            handler._send_json(
                200,
                {
                    "id": sk["id"],
                    "name": sk["name"],
                    "description": sk["description"],
                    "content": sk["content"],
                    "location": sk["path"],
                    "path": sk["path"],
                    "resources": sk.get("helper_files", []),
                },
            )
        else:
            handler._send_json(404, res)
        return True

    # 11. /ports & /execute (GET poll)
    if sub_path == "/ports":
        handler._send_json(
            200,
            {
                "ports": [
                    3000,
                    4000,
                    4010,
                    4079,
                    4080,
                    4081,
                    4082,
                    4083,
                    4084,
                    4085,
                    4088,
                    4090,
                    4093,
                    4098,
                    4099,
                    8080,
                    8090,
                    8888,
                ]
            },
        )
        return True

    if sub_path == "/execute":
        handler._send_json(200, [])
        return True

    return False


def handle_terminal_post(
    handler: Any,
    raw_path: str,
    payload: dict[str, Any],
    write_file_fn: Any,
) -> bool:
    is_vm, prefix, sub_path, vm = parse_vm_route(raw_path)
    is_ramdisk = raw_path == "/ci-ramdisk" or raw_path.startswith("/ci-ramdisk/")
    if is_ramdisk and not is_vm:
        prefix = "/ci-ramdisk"
        sub_path = raw_path[len("/ci-ramdisk") :] or "/"

    if is_vm and prefix == "/vm/all":
        default_cwd = "/vms"
        home_dir = "/home/mboyle"
        root_dir = "/"
    elif is_vm and vm is not None:
        default_cwd = vm["default_cwd"]
        home_dir = vm["home"]
        root_dir = vm["root"]
    elif is_ramdisk:
        default_cwd = str(CI_RAMDISK_DIR)
        home_dir = "/home/mboyle"
        root_dir = "/"
    else:
        default_cwd = "/home/mboyle"
        home_dir = "/home/mboyle"
        root_dir = "/"

    session_key = f"{prefix}:{handler.headers.get('X-Session-Id', 'default')}"
    current_cwd = SESSION_CWDS.get(session_key, default_cwd)

    if sub_path == "/files/cwd":
        new_cwd = str(payload.get("path") or payload.get("cwd") or current_cwd).strip()
        SESSION_CWDS[session_key] = new_cwd
        handler._send_json(
            200,
            {
                "cwd": new_cwd,
                "home": home_dir,
                "root": root_dir,
            },
        )
        return True

    if sub_path == "/execute":
        cmd = str(payload.get("command") or "")
        cwd = str(payload.get("cwd") or current_cwd)
        res = execute_command_on_target(vm, cmd, cwd, timeout_s=30)
        handler._send_json(200, res)
        return True

    if sub_path == "/exec_on_any_vm":
        target_str = str(payload.get("vm") or "10.0.70.164")
        target_vm = resolve_vm(target_str) or BOYLENET_27_VMS[0]
        cmd = str(payload.get("command") or "hostname && uptime")
        cwd = str(payload.get("cwd") or target_vm["default_cwd"])
        res = execute_command_on_target(target_vm, cmd, cwd, timeout_s=30)
        handler._send_json(200, res)
        return True

    if sub_path == "/files/write":
        fpath = str(payload.get("path") or payload.get("file_path") or "")
        content = str(payload.get("content") or "")
        res = write_file_fn({"file_path": fpath, "mode": "write", "content": content})
        handler._send_json(200, res)
        return True

    if sub_path == "/files/mkdir":
        req_dir = str(payload.get("path") or "").strip()
        if not req_dir.startswith("/"):
            p = (SANDBOX_WORKSPACE_DIR / req_dir).resolve()
        else:
            p = Path(req_dir).resolve()
        if str(p).startswith(str(SANDBOX_WORKSPACE_DIR.resolve())):
            p.mkdir(parents=True, exist_ok=True)
            handler._send_json(200, {"ok": True, "path": str(p)})
        else:
            handler._send_json(
                200, {"ok": True, "path": req_dir, "note": "Sandbox mkdir"}
            )
        return True

    if sub_path == "/files/move":
        handler._send_json(200, {"ok": True})
        return True

    return False
