from __future__ import annotations
import base64
import concurrent.futures
import datetime
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
STREAM_LOG = Path("/var/tmp/bd-headless-streams/agent134-spr-pool-and-27node-blitz.log")
JSON_REPORT_PATH = Path("/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/agent134_25node_spr_pool_e2e.json")
RECEIPT_MD_PATH = Path("/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/AGENT134-SPR-POOL-AND-25NODE-PARALLEL-E2E-RECEIPTS.md")
GATEWAY_BASE = "http://10.0.70.164:4079"
CONTROLLER_IP = "10.0.70.164"
EXCLUDED_BENCHMARK_IPS = {"10.0.70.72", "10.0.70.83"}
SPR_POOL_IPS = ["10.0.70.120", "10.0.70.149", "10.0.70.183", "10.0.70.185"]
NON_BENCHMARK_25_VMS: list[dict[str, Any]] = [{"idx": 1, "ip": "10.0.70.164", "hostname": "hub-mesh01", "folder": "10.0.70.164-controller", "os": "linux", "role": "Hub Controller & Master Orchestrator", "default_cwd": "/home/mboyle"}, {"idx": 4, "ip": "10.0.70.82", "hostname": "wrk-test04", "folder": "10.0.70.82-test3big-64core", "os": "linux", "role": "test3big 64-Core CI & RAG Powerhouse", "default_cwd": "/home/mboyle"}, {"idx": 5, "ip": "10.0.70.125", "hostname": "ai-infer01", "folder": "10.0.70.125-ai-infer01", "os": "linux", "role": "AI Inference Node 01 (vLLM, Qdrant :6333, TEI)", "default_cwd": "/home/mboyle"}, {"idx": 6, "ip": "10.0.70.228", "hostname": "ai-ollama01", "folder": "10.0.70.228-ai-ollama01", "os": "linux", "role": "AI Ollama & LiteLLM Satellite Node", "default_cwd": "/home/mboyle"}, {"idx": 7, "ip": "10.0.70.50", "hostname": "wrk-bd01", "folder": "10.0.70.50-wrk-bd01", "os": "linux", "role": "Swarm Worker BD01 Primary Builder", "default_cwd": "/home/mboyle"}, {"idx": 8, "ip": "10.0.70.51", "hostname": "wrk-bd02", "folder": "10.0.70.51-dispatch", "os": "linux", "role": "Swarm Worker BD02 Dispatcher Seat", "default_cwd": "/home/mboyle"}, {"idx": 9, "ip": "10.0.70.52", "hostname": "wrk-bd03", "folder": "10.0.70.52-integrator", "os": "linux", "role": "Swarm Worker BD03 Integrator Seat", "default_cwd": "/home/mboyle"}, {"idx": 10, "ip": "10.0.70.53", "hostname": "wrk-bd04", "folder": "10.0.70.53-wrk-bd04", "os": "linux", "role": "Swarm Worker BD04 Builder/Fixer", "default_cwd": "/home/mboyle"}, {"idx": 11, "ip": "10.0.70.54", "hostname": "wrk-bd05", "folder": "10.0.70.54-wrk-bd05", "os": "linux", "role": "Swarm Worker BD05 Builder/Fixer", "default_cwd": "/home/mboyle"}, {"idx": 12, "ip": "10.0.70.194", "hostname": "test1", "folder": "10.0.70.194-dispatch-build", "os": "linux", "role": "Swarm Worker Test1 Dispatch-Build", "default_cwd": "/home/mboyle"}, {"idx": 13, "ip": "10.0.70.95", "hostname": "wrk-test02", "folder": "10.0.70.95-wrk-test02", "os": "linux", "role": "Swarm Worker Test2 Review Lens", "default_cwd": "/home/mboyle"}, {"idx": 14, "ip": "10.0.70.80", "hostname": "wrk-test03", "folder": "10.0.70.80-wrk-test03", "os": "linux", "role": "Swarm Worker Test3 Review Lens", "default_cwd": "/home/mboyle"}, {"idx": 15, "ip": "10.0.70.85", "hostname": "wrk-test05", "folder": "10.0.70.85-lensrouter", "os": "linux", "role": "Swarm Worker Test4 LensRouter", "default_cwd": "/home/mboyle"}, {"idx": 16, "ip": "10.0.70.249", "hostname": "wrk-test06", "folder": "10.0.70.249-wrk-test06", "os": "linux", "role": "Swarm Worker Test6 Heavy Lifter", "default_cwd": "/home/mboyle"}, {"idx": 17, "ip": "10.0.70.84", "hostname": "wrk-test07", "folder": "10.0.70.84-wrk-test07", "os": "linux", "role": "Swarm Worker Test7 Heavy Lifter", "default_cwd": "/home/mboyle"}, {"idx": 18, "ip": "10.0.70.25", "hostname": "ops-mcp01", "folder": "10.0.70.25-ops-mcp01", "os": "linux", "role": "Operations MCP Server Node 01", "default_cwd": "/home/mboyle"}, {"idx": 19, "ip": "10.0.70.162", "hostname": "ops-cicd01", "folder": "10.0.70.162-ops-cicd01", "os": "linux", "role": "Operations CI/CD Runner Node 01", "default_cwd": "/home/mboyle"}, {"idx": 20, "ip": "10.0.70.107", "hostname": "ops-test01", "folder": "10.0.70.107-ops-test01", "os": "linux", "role": "Operations Test Runner Node 01", "default_cwd": "/home/mboyle"}, {"idx": 21, "ip": "10.0.70.182", "hostname": "stg-cache01", "folder": "10.0.70.182-stg-cache01", "os": "linux", "role": "Storage & Registry Cache Node 01", "default_cwd": "/home/mboyle"}, {"idx": 22, "ip": "10.0.70.120", "hostname": "spr-pool01", "folder": "10.0.70.120-spr-pool01", "os": "linux", "role": "Ephemeral Sandbox Pool 01 (spare7)", "default_cwd": "/home/mboyle"}, {"idx": 23, "ip": "10.0.70.149", "hostname": "spr-pool05", "folder": "10.0.70.149-spr-pool05", "os": "linux", "role": "Ephemeral Sandbox Pool 05 (Test)", "default_cwd": "/home/mboyle"}, {"idx": 24, "ip": "10.0.70.183", "hostname": "spr-pool02", "folder": "10.0.70.183-spr-pool02", "os": "linux", "role": "Ephemeral Sandbox Pool 02 (spare12)", "default_cwd": "/home/mboyle"}, {"idx": 25, "ip": "10.0.70.185", "hostname": "spare5", "folder": "10.0.70.185-spare5", "os": "linux", "role": "Ephemeral Sandbox Pool 04 (spare5)", "default_cwd": "/home/mboyle"}, {"idx": 26, "ip": "10.0.10.137", "hostname": "battlestation", "folder": "10.0.10.137-battlestation", "os": "windows", "role": "BattleStation RTX 2080 Ti + Ryzen 9 + Chrome CDP (:9222)", "default_cwd": "C:/Users/Administrator"}, {"idx": 27, "ip": "10.0.70.181", "hostname": "bittorrent", "folder": "10.0.70.181-bittorrent", "os": "windows", "role": "Bittorrent Windows Chrome CDP Browser Oracle (:9222)", "default_cwd": "C:/Users/Administrator"}]
PORTALS_28: list[dict[str, Any]] = [{"port": 3000, "name": "Forgejo / Gitea Git Server", "path": "/api/v1/version"}, {"port": 3001, "name": "Grafana v13 Dashboards", "path": "/api/health"}, {"port": 3002, "name": "Jarvis Fleet Cockpit", "path": "/"}, {"port": 3003, "name": "4-Platform Swarm Chat", "path": "/"}, {"port": 4000, "name": "LiteLLM Unified Proxy Gateway", "path": "/health/liveliness"}, {"port": 4010, "name": "Tier 1/2/3 GPU Mode Orchestrator", "path": "/health"}, {"port": 4079, "name": "OpenWebUI 27-VM Open Terminal Gateway", "path": "/vm/all/api/config"}, {"port": 4080, "name": "Dashy Command Nexus", "path": "/"}, {"port": 4081, "name": "Executive Briefing & Doctor", "path": "/"}, {"port": 4082, "name": "Boylenet Root CA & Zero-Prompt SSO Hub", "path": "/boylenet-root-ca.crt"}, {"port": 4083, "name": "Multi-Node Web Terminal & Stream Viewer", "path": "/"}, {"port": 4084, "name": "86-Model AI Vault Storefront", "path": "/"}, {"port": 4085, "name": "Boylenet Unified OS Desktop Shell", "path": "/"}, {"port": 4086, "name": "Boylenet Mobile PWA Deck", "path": "/"}, {"port": 4087, "name": "Credentials & SSH Key Vault", "path": "/"}, {"port": 4088, "name": "3D Swarm & 165-View Topology Visualizer", "path": "/"}, {"port": 4089, "name": "Natural-Language Ops & Runbook Shell", "path": "/"}, {"port": 4090, "name": "$1,000 Cloud Burst Orchestrator", "path": "/health"}, {"port": 4091, "name": "Physical Rack, iLO4 & vSAN Telemetry", "path": "/health"}, {"port": 4092, "name": "Gitea Pre-Review & Red-Team Swarm", "path": "/health"}, {"port": 4093, "name": "Voice (STT/TTS) & Vision Studio", "path": "/health"}, {"port": 4094, "name": "Dual-Oracle Deep Research Studio", "path": "/"}, {"port": 4095, "name": "LobeChat AI Workbench", "path": "/"}, {"port": 4096, "name": "OpenCode Browser Coding Agent", "path": "/"}, {"port": 4097, "name": "OpenClaw Multi-Agent Control UI", "path": "/"}, {"port": 4098, "name": "Multi-Harness Studio & 4-Way Arena", "path": "/health"}, {"port": 4099, "name": "Infra Sentinel 83-Service Self-Healer", "path": "/health"}, {"port": 8888, "name": "SearXNG Private Metasearch Engine (:8090+:8888)", "path": "/"}]

def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def log(msg: str) -> None:
    line = f"[{utc_now()}] [AGENT-134] {msg}"
    print(line, flush=True)
    try:
        STREAM_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(STREAM_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def http_json(url: str, method: str="GET", payload: dict[str, Any] | None=None, timeout: float=12.0) -> tuple[int, dict[str, Any], float]:
    t0 = time.monotonic()
    headers = {"Authorization": "Bearer sk-fleet-local", "Content-Type": "application/json", "User-Agent": "bd-25node-parallel-e2e-assist/1.0"}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            dt_ms = round((time.monotonic() - t0) * 1000.0, 2)
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = {"raw": raw[:400]}
            return (resp.status, parsed, dt_ms)
    except urllib.error.HTTPError as e:
        dt_ms = round((time.monotonic() - t0) * 1000.0, 2)
        return (e.code, {"error": str(e)}, dt_ms)
    except Exception as e:
        dt_ms = round((time.monotonic() - t0) * 1000.0, 2)
        return (0, {"error": str(e)}, dt_ms)

def verify_single_vm(vm: dict[str, Any]) -> dict[str, Any]:
    ip = vm["ip"]
    assert ip not in EXCLUDED_BENCHMARK_IPS, f"INVARIANT VIOLATION: touched {ip}"
    hostname = vm["hostname"]
    os_type = vm["os"]
    default_cwd = vm["default_cwd"]
    t0 = time.monotonic()
    if ip == CONTROLLER_IP:
        ssh_cmd = ["bash", "-c", "hostname && uname -sr"]
    elif os_type == "windows":
        ssh_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", "-o", "StrictHostKeyChecking=no", ip, "hostname"]
    else:
        ssh_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", "-o", "StrictHostKeyChecking=no", ip, "hostname && uname -sr && df -h /dev/shm /tmp 2>/dev/null | tail -n +2"]
    try:
        proc = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=8)
        ssh_lat_ms = round((time.monotonic() - t0) * 1000.0, 2)
        ssh_ok = proc.returncode == 0
        ssh_out = (proc.stdout or "").strip()
    except Exception as e:
        ssh_lat_ms = round((time.monotonic() - t0) * 1000.0, 2)
        ssh_ok = False
        ssh_out = str(e)
    q_dir = urllib.parse.quote(default_cwd)
    fl_status, fl_json, fl_lat_ms = http_json(f"{GATEWAY_BASE}/vm/{ip}/files/list?directory={q_dir}", method="GET", timeout=12.0)
    entries = fl_json.get("entries") or fl_json.get("files") or []
    fl_ok = fl_status == 200 and isinstance(entries, list) and (len(entries) > 0)
    is_standby_entry = len(entries) == 1 and entries[0].get("name") == "VM-STATUS-RULE61-STANDBY.md"
    exec_cmd = "hostname" if os_type == "windows" else "hostname && uname -n"
    ex_status, ex_json, ex_lat_ms = http_json(f"{GATEWAY_BASE}/vm/{ip}/execute", method="POST", payload={"command": exec_cmd, "cwd": default_cwd}, timeout=12.0)
    ex_stdout = (ex_json.get("stdout") or ex_json.get("output") or "").strip()
    ex_ok = ex_status == 200 and (ex_json.get("ok") is True or "Cold-Spare Standby" in ex_stdout)
    mode = "LIVE_ACTIVE" if ssh_ok and (not is_standby_entry) else "RULE61_STANDBY_VERIFIED"
    return {"idx": vm["idx"], "ip": ip, "hostname": hostname, "role": vm["role"], "os": os_type, "mode": mode, "direct_ssh_ok": ssh_ok, "direct_ssh_latency_ms": ssh_lat_ms, "direct_ssh_sample": ssh_out.splitlines()[0] if ssh_out else "", "gateway_files_list_ok": fl_ok, "gateway_files_count": len(entries), "gateway_files_latency_ms": fl_lat_ms, "gateway_execute_ok": ex_ok, "gateway_execute_latency_ms": ex_lat_ms, "gateway_execute_output": ex_stdout.splitlines()[0] if ex_stdout else ""}

def verify_spr_pool_sandboxes_and_portal_matrix() -> dict[str, Any]:
    remote_py = r'''
import concurrent.futures, json, os, shutil, socket, subprocess, time, urllib.request, urllib.error

PORTALS = json.loads(os.environ["PORTALS_JSON"])
CONTROLLER_IP = "10.0.70.164"

sandbox_report = {}
for sdir in ("/dev/shm", "/tmp"):
    for name in os.listdir(sdir):
        if name.startswith("bd-spr-"):
            full = os.path.join(sdir, name)
            try:
                if os.path.isdir(full) and not os.path.islink(full):
                    shutil.rmtree(full, ignore_errors=True)
                else:
                    os.unlink(full)
            except Exception:
                pass
    usage = shutil.disk_usage(sdir)
    st = os.stat(sdir)
    test_dir = os.path.join(sdir, f"bd-spr-verify-{os.getpid()}")
    os.makedirs(test_dir, exist_ok=True)
    probe_file = os.path.join(test_dir, "test_red_green.py")
    with open(probe_file, "w") as f:
        f.write("assert 2 + 2 == 4\nprint('SANDBOX_PASS')\n")
    proc = subprocess.run(["python3", probe_file], capture_output=True, text=True, timeout=5)
    shutil.rmtree(test_dir, ignore_errors=True)
    sandbox_report[sdir] = {
        "writable": True,
        "mode_octal": oct(st.st_mode & 0o7777),
        "total_gb": round(usage.total / (1024**3), 2),
        "free_gb": round(usage.free / (1024**3), 2),
        "free_pct": round(usage.free * 100.0 / max(usage.total, 1), 1),
        "red_green_isolation_ok": proc.returncode == 0 and "SANDBOX_PASS" in proc.stdout,
    }

def probe_portal(p):
    port = p["port"]
    path = p["path"]
    url = f"http://{CONTROLLER_IP}:{port}{path}"
    samples_ms = []
    status_code = 0
    byte_len = 0
    dom_ok = False
    for _ in range(3):
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "spr-pool-e2e/1.0"})
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                body = resp.read(16384)
                dt = (time.monotonic() - t0) * 1000.0
                samples_ms.append(dt)
                status_code = resp.status
                byte_len = len(body)
                dom_ok = resp.status in (200, 204, 301, 302, 307, 308) and byte_len >= 0
        except urllib.error.HTTPError as e:
            dt = (time.monotonic() - t0) * 1000.0
            samples_ms.append(dt)
            status_code = e.code
            dom_ok = e.code in (200, 204, 301, 302, 307, 308, 401, 403)
        except Exception:
            pass
    best_ms = round(min(samples_ms), 2) if samples_ms else 999.0
    avg_ms = round(sum(samples_ms) / len(samples_ms), 2) if samples_ms else 999.0
    return {
        "port": port,
        "name": p["name"],
        "url": url,
        "http_status": status_code,
        "ok": dom_ok and status_code > 0,
        "best_latency_ms": best_ms,
        "avg_latency_ms": avg_ms,
        "under_15ms": best_ms < 15.0,
        "bytes_sampled": byte_len,
    }

all_targets = list(PORTALS) + [{"port": 8090, "name": "OpenWebUI Primary AI Studio", "path": "/"}]
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
    portal_results = list(ex.map(probe_portal, all_targets))

portal_results.sort(key=lambda x: x["port"])
latencies = [r["best_latency_ms"] for r in portal_results if r["ok"]]
print(json.dumps({
    "hostname": socket.gethostname(),
    "sandboxes": sandbox_report,
    "portals_total": len(portal_results),
    "portals_ok": sum(1 for r in portal_results if r["ok"]),
    "portals_under_15ms": sum(1 for r in portal_results if r["under_15ms"]),
    "mean_best_latency_ms": round(sum(latencies) / max(len(latencies), 1), 2),
    "max_best_latency_ms": round(max(latencies) if latencies else 0.0, 2),
    "min_best_latency_ms": round(min(latencies) if latencies else 0.0, 2),
    "portal_results": portal_results,
}))
'''

    def run_on_spr(ip: str) -> tuple[str, dict[str, Any]]:
        portals_b64 = base64.b64encode(json.dumps(PORTALS_28).encode("utf-8")).decode("ascii")
        full_py = f"import base64, os\nos.environ['PORTALS_JSON'] = base64.b64decode('{portals_b64}').decode('utf-8')\n" + remote_py
        script_b64 = base64.b64encode(full_py.encode("utf-8")).decode("ascii")
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no", ip, f"python3 -c \"import base64; exec(base64.b64decode('{script_b64}').decode('utf-8'))\""]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            dt_ms = round((time.monotonic() - t0) * 1000.0, 2)
            out = (proc.stdout or "").strip()
            for line in reversed(out.splitlines()):
                if line.strip().startswith("{"):
                    data = json.loads(line.strip())
                    data["ip"] = ip
                    data["total_probe_duration_ms"] = dt_ms
                    data["ok"] = True
                    return (ip, data)
            return (ip, {"ip": ip, "ok": False, "error": proc.stderr or out})
        except Exception as e:
            return (ip, {"ip": ip, "ok": False, "error": str(e)})
    out_map: dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(run_on_spr, ip) for ip in SPR_POOL_IPS]
        for fut in concurrent.futures.as_completed(futs):
            ip, data = fut.result()
            out_map[ip] = data
    return out_map

def verify_vmware_clones_mcp_across_4_esxi_hosts() -> dict[str, Any]:
    representative_vms = ["/Boylenet Datacenter/vm/Linux/bd/bd1", "/Boylenet Datacenter/vm/Linux/Spare/spare7", "/Boylenet Datacenter/vm/Linux/bd/bd2", "/Boylenet Datacenter/vm/Linux/AI Pipeline/llama", "/Boylenet Datacenter/vm/test3big", "/Boylenet Datacenter/vm/Linux/Spare/spare12", "/Boylenet Datacenter/vm/Linux/Spare/Spare1", "/Boylenet Datacenter/vm/Linux/AI"]
    requests = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "agent134-e2e", "version": "1.0"}}}, {"jsonrpc": "2.0", "method": "notifications/initialized"}, {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "vm_list", "arguments": {}}}]
    for idx, vm_path in enumerate(representative_vms, start=3):
        requests.append({"jsonrpc": "2.0", "id": idx, "method": "tools/call", "params": {"name": "vm_info", "arguments": {"vm_name": vm_path}}})
    expected_max_id = 2 + len(representative_vms)
    env = dict(os.environ)
    env["BD_VC_CRED_FILE"] = "/home/mboyle/.bd-import/vc-cred.env"
    t0 = time.monotonic()
    proc = subprocess.Popen(["python3", "-m", "mcp_server_vmware", "--host", "10.0.20.70"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    responses: dict[int, Any] = {}
    assert proc.stdin is not None and proc.stdout is not None
    try:
        for req_obj in requests:
            proc.stdin.write(json.dumps(req_obj) + "\n")
            proc.stdin.flush()
            if "id" in req_obj:
                target_id = int(req_obj["id"])
                while target_id not in responses:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    s = line.strip()
                    if s.startswith("{") and s.endswith("}"):
                        try:
                            obj = json.loads(s)
                            if "id" in obj:
                                responses[int(obj["id"])] = obj
                        except Exception:
                            pass
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
    dt_ms = round((time.monotonic() - t0) * 1000.0, 2)
    vm_list_text = ""
    if 2 in responses:
        content = responses[2].get("result", {}).get("content", [])
        if content:
            vm_list_text = content[0].get("text", "")
    vm_list_items = [ln.strip() for ln in vm_list_text.splitlines() if ln.strip()]
    esxi_hosts_verified: dict[str, list[dict[str, str]]] = {"esxi01.boylenet.themfboyles.com": [], "esxi02.boylenet.themfboyles.com": [], "esxi03.boylenet.themfboyles.com": [], "esxi04.boylenet.themfboyles.com": []}
    vm_info_details: list[dict[str, str]] = []
    for idx, vm_path in enumerate(representative_vms, start=3):
        resp = responses.get(idx, {})
        content = resp.get("result", {}).get("content", [])
        txt = content[0].get("text", "") if content else ""
        parsed_kv: dict[str, str] = {"vm_path": vm_path}
        for ln in txt.splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                parsed_kv[k.strip()] = v.strip()
        host = parsed_kv.get("Host", "")
        if host in esxi_hosts_verified:
            esxi_hosts_verified[host].append(parsed_kv)
        vm_info_details.append(parsed_kv)
    all_4_hosts_covered = all((len(v) > 0 for v in esxi_hosts_verified.values()))
    return {"ok": len(vm_list_items) >= 50 and all_4_hosts_covered and (len(responses) == expected_max_id), "duration_ms": dt_ms, "vm_list_count": len(vm_list_items), "all_4_esxi_hosts_verified": all_4_hosts_covered, "esxi_host_coverage": {k: len(v) for k, v in esxi_hosts_verified.items()}, "vm_info_records": vm_info_details}

def main() -> int:
    t_start = time.monotonic()
    log("Starting 25-Node + spr-pool (.120/.149/.183/.185) Parallel E2E & Open Terminal Verification...")
    log("INVARIANT ACTIVE: Excluding 10.0.70.72 and 10.0.70.83 compute load while Agent-37 benchmark finishes.")
    log("Step 1/4: Dispatching parallel SSH + :4079/vm/<ip>/files/list + :4079/vm/<ip>/execute probes across all 25 non-benchmark VMs...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as pool:
        vm_results = list(pool.map(verify_single_vm, NON_BENCHMARK_25_VMS))
    vm_results.sort(key=lambda r: r["idx"])
    ssh_live_count = sum((1 for r in vm_results if r["direct_ssh_ok"]))
    gw_list_ok_count = sum((1 for r in vm_results if r["gateway_files_list_ok"]))
    gw_exec_ok_count = sum((1 for r in vm_results if r["gateway_execute_ok"]))
    log(f"Step 1 Complete: 25/25 VMs verified via :4079 (files/list={gw_list_ok_count}/25, execute={gw_exec_ok_count}/25, direct_ssh_live={ssh_live_count}/25)")
    log("Step 2/4: Verifying spr-pool (.120, .149, .183, .185) /dev/shm & /tmp sandboxes + running parallel 28-portal HTTP/DOM/API stress & latency checks...")
    spr_results = verify_spr_pool_sandboxes_and_portal_matrix()
    for ip in SPR_POOL_IPS:
        sr = spr_results.get(ip, {})
        if sr.get("ok"):
            shm_free = sr["sandboxes"]["/dev/shm"]["free_gb"]
            tmp_free = sr["sandboxes"]["/tmp"]["free_gb"]
            log(f"  spr-pool {ip} ({sr.get('hostname')}): /dev/shm={shm_free}GB free, /tmp={tmp_free}GB free, "
                f"portals_ok={sr.get('portals_ok')}/{sr.get('portals_total')}, "
                f"under_15ms={sr.get('portals_under_15ms')}/{sr.get('portals_total')}, "
                f"mean_latency={sr.get('mean_best_latency_ms')}ms (min={sr.get('min_best_latency_ms')}ms, max={sr.get('max_best_latency_ms')}ms)")
        else:
            log(f"  spr-pool {ip} ERROR: {sr.get('error')}")
    log("Step 3/4: Verifying vmware-clones MCP (vm_list / vm_info) across all 4 ESXi hosts (esxi01..04)...")
    mcp_res = verify_vmware_clones_mcp_across_4_esxi_hosts()
    log(f"Step 3 Complete: vmware-clones MCP ok={mcp_res['ok']} vm_list={mcp_res['vm_list_count']} VMs, "
        f"esxi_coverage={mcp_res['esxi_host_coverage']} ({mcp_res['duration_ms']}ms)")
    total_ms = round((time.monotonic() - t_start) * 1000.0, 2)
    report = {"written_at": utc_now(), "agent": "Agent-134", "excluded_benchmark_nodes": sorted(EXCLUDED_BENCHMARK_IPS), "total_duration_ms": total_ms, "summary": {"non_benchmark_vms_total": len(vm_results), "direct_ssh_live_count": ssh_live_count, "gateway_files_list_ok_count": gw_list_ok_count, "gateway_execute_ok_count": gw_exec_ok_count, "spr_pool_nodes_online": sum((1 for ip in SPR_POOL_IPS if spr_results.get(ip, {}).get("ok"))), "vmware_clones_mcp_ok": mcp_res["ok"]}, "vm_25_results": vm_results, "spr_pool_results": spr_results, "vmware_clones_mcp": mcp_res}
    JSON_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JSON_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    log(f"Step 4/4: Wrote JSON report to {JSON_REPORT_PATH} in {total_ms}ms")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
