#!/usr/bin/env python3
"""
bd-full-suite-e2e-test.py — Master End-to-End Automated Certification Harness (O1789 Agent-105)
Supports:
  - Full 134-Assertion E2E Certification Suite (default / --full):
      * Suite A: All 28 Systemd Services & 32 Local/Remote Web Portals
      * Suite B: All 24 Traefik *.boylenet.themfboyles.com Virtual Host Ingress Routes (:80)
      * Suite C: CLI Tools, Core Subsystems & Live State Mutation -> Real-Time UI/API Update Verification
      * Suite D: Dual-Node Chrome CDP (.137:9222 & .181:9222) Full DOM, Bar/Button/Tab/Pill/Modal Click-Through & Visual Audit
  - Fast --quick mode (<1s) for bd-swarm-mod / pre-turn hooks.

CRITICAL INVARIANT:
  Never restarts, touches, or runs inference on .72 or .83 while Agent-37 llama-bench is active.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from websocket import create_connection

STREAM_LOG = "/var/tmp/bd-headless-streams/agent105-full-suite-e2e-tests.log"
JSON_REPORT = "/var/tmp/bd-full-suite-e2e-results.json"

QUICK_ENDPOINTS = [
    ("Universal-Gateway-4079", "http://10.0.70.164:4079/health"),
    ("OpenWebUI-Controller-8090", "http://10.0.70.164:8090/api/config"),
    ("OpenWebUI-VaultA-72-8080", "http://10.0.70.72:8080/api/config"),
    ("Doctor-Cockpit-4081", "http://10.0.70.164:4081/"),
    ("Multi-Harness-4098", "http://10.0.70.164:4098/"),
    ("Infra-Sentinel-4099", "http://10.0.70.164:4099/"),
    ("Qdrant-Vector-6333", "http://10.0.70.125:6333/collections"),
    ("BattleStation-Ollama-137", "http://10.0.10.137:11434/api/tags"),
]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_stream(msg: str) -> None:
    line = f"[{now_iso()}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(STREAM_LOG), exist_ok=True)
        with open(STREAM_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run_quick_mode() -> int:
    def _chk(url: str) -> dict[str, Any]:
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=2.5) as r:
                c = r.getcode()
                return {
                    "ok": 200 <= c < 400,
                    "status_code": c,
                    "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
                }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e)[:160],
                "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {n: ex.submit(_chk, u) for n, u in QUICK_ENDPOINTS}
        endpoint_results = {n: f.result() for n, f in futs.items()}
    bdkb_ok, bdkb_ms, bdkb_hits = False, 0.0, 0
    try:
        raw_kb = subprocess.check_output(
            [
                "python3",
                "/home/mboyle/bin/bd-boylenet-infra-mcp.py",
                "--cli",
                "bd_kb_search",
                json.dumps({"query": "Boylenet 27-VM topology O1740 dynamic routing", "top_k": 3}),
            ],
            text=True,
            timeout=5,
        )
        kb_data = json.loads(raw_kb).get("data", {})
        bdkb_ms = float(kb_data.get("latency_ms", 0.0))
        bdkb_hits = int(kb_data.get("result_count", 0))
        bdkb_ok = bdkb_hits > 0
    except Exception:
        pass
    mcp_tools_count = 0
    try:
        raw = subprocess.check_output(
            ["python3", "/home/mboyle/bin/bd-boylenet-infra-mcp.py", "--list-tools"],
            text=True,
            timeout=5,
        )
        parsed = json.loads(raw)
        tools_list = parsed.get("tools", parsed) if isinstance(parsed, dict) else parsed
        mcp_tools_count = len(tools_list)
    except Exception:
        pass
    summary = {
        "suite": "bd-full-suite-e2e-test",
        "status": "PASS"
        if all(v["ok"] for v in endpoint_results.values()) and bdkb_ok and mcp_tools_count >= 20
        else "PARTIAL",
        "elapsed_s": round(time.perf_counter() - t_start, 2),
        "endpoints_passed": sum(1 for v in endpoint_results.values() if v["ok"]),
        "endpoints_total": len(endpoint_results),
        "endpoints": endpoint_results,
        "bdkb_search": {"ok": bdkb_ok, "hits": bdkb_hits, "latency_ms": bdkb_ms},
        "infra_mcp_tools_count": mcp_tools_count,
    }
    print(json.dumps(summary, indent=2))
    return 0


class E2ERunner:
    def __init__(self) -> None:
        self.assertions: List[Dict[str, Any]] = []
        self.started_at = now_iso()
        self.t0 = time.monotonic()

    def record(
        self,
        suite: str,
        check_id: str,
        name: str,
        passed: bool,
        detail: str,
        latency_ms: float = 0.0,
    ) -> None:
        entry = {
            "suite": suite,
            "id": check_id,
            "name": name,
            "passed": bool(passed),
            "detail": detail,
            "latency_ms": round(latency_ms, 2),
            "timestamp": now_iso(),
        }
        self.assertions.append(entry)
        badge = "PASS" if passed else "FAIL"
        log_stream(f"[{suite}] [{badge}] {check_id}: {name} -> {detail} ({latency_ms:.1f}ms)")


def http_probe(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    method: str = "GET",
    data: Optional[bytes] = None,
    timeout: float = 6.0,
) -> Tuple[int, str, float]:
    t0 = time.monotonic()
    hdrs = {"User-Agent": "bd-full-suite-e2e-test/1.0"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body, (time.monotonic() - t0) * 1000.0
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = str(e)
        return e.code, body, (time.monotonic() - t0) * 1000.0
    except Exception as e:
        return 0, str(e), (time.monotonic() - t0) * 1000.0


def run_suite_a(runner: E2ERunner) -> None:
    log_stream("=== SUITE A: 28 Systemd Services, 32 Local Portals & Remote Endpoints ===")
    systemd_units = [
        "bd-cloud-burst-web.service",
        "bd-credentials-vault.service",
        "bd-deep-research-web.service",
        "bd-executive-briefing.service",
        "bd-gitea-prereview.service",
        "bd-gpu-orchestrator.service",
        "bd-hardware-telemetry.service",
        "bd-infra-sentinel.service",
        "bd-iptables-restore.service",
        "bd-mcp.service",
        "bd-mobile-pwa.service",
        "bd-model-storefront.service",
        "bd-multi-harness-web.service",
        "bd-multimodal-bridge.service",
        "bd-novnc.service",
        "bd-openbox.service",
        "bd-openclaw-web.service",
        "bd-opencode-web.service",
        "bd-openwebui-tool-gateway.service",
        "bd-ops-web.service",
        "bd-os-shell.service",
        "bd-pool-autobalancer.service",
        "bd-rag.service",
        "bd-topology-visualizer.service",
        "bd-trust-and-sso-portal.service",
        "bd-web-terminal-drawer.service",
        "bd-x11vnc.service",
        "bd-xvfb.service",
    ]
    for idx, unit in enumerate(systemd_units, 1):
        t0 = time.monotonic()
        r = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=5,
        )
        state = r.stdout.strip()
        lat = (time.monotonic() - t0) * 1000.0
        runner.record(
            "Suite-A",
            f"A-SYS-{idx:02d}",
            f"Systemd unit {unit}",
            state == "active",
            f"state={state}",
            lat,
        )

    local_portals = [
        ("A-WEB-3000", "Gitea (:3000)", "http://127.0.0.1:3000/", None, "Gitea"),
        ("A-WEB-3002", "Jarvis Cockpit (:3002)", "http://127.0.0.1:3002/", None, "<html"),
        ("A-WEB-4000", "LiteLLM .164 (:4000)", "http://127.0.0.1:4000/health/liveliness", None, "I'm alive"),
        ("A-WEB-4010", "GPU Mode Orchestrator (:4010)", "http://127.0.0.1:4010/v1/models", {"Authorization": "Bearer sk-local"}, "data"),
        ("A-WEB-4079", "OpenWebUI Universal Tool Gateway (:4079)", "http://127.0.0.1:4079/health", None, "bd-openwebui-tool-gateway"),
        ("A-WEB-4080", "Dashy Portal (:4080)", "http://127.0.0.1:4080/", None, "Dashy"),
        ("A-WEB-4081", "Executive Briefing, Search & Doctor (:4081)", "http://127.0.0.1:4081/", None, "Executive Briefing"),
        ("A-WEB-4082", "SSO, QR & Root CA Trust Portal (:4082)", "http://127.0.0.1:4082/", None, "Zero-Friction SSO"),
        ("A-WEB-4083", "Multi-Node Web Terminal & Agent TV Wall (:4083)", "http://127.0.0.1:4083/", None, "Agent TV Wall"),
        ("A-WEB-4084", "86-Model Vault Storefront (:4084)", "http://127.0.0.1:4084/", None, "86-Model"),
        ("A-WEB-4085", "Boylenet Unified OS Shell (:4085)", "http://127.0.0.1:4085/", None, "Unified OS"),
        ("A-WEB-4085-AG", "Boylenet Airgap API (:4085/api/airgap)", "http://127.0.0.1:4085/api/airgap", None, "airgap_enabled"),
        ("A-WEB-4086", "Mobile PWA Command Deck (:4086)", "http://127.0.0.1:4086/", None, "Mobile Command Deck"),
        ("A-WEB-4087", "Credentials & 27-Node SSH Vault (:4087)", "http://127.0.0.1:4087/", None, "Credentials"),
        ("A-WEB-4088", "165-View 60fps Topology Visualizer (:4088)", "http://127.0.0.1:4088/", None, "Topology Visualizer"),
        ("A-WEB-4088-GAL", "Topology Visualizer /gallery (:4088/gallery)", "http://127.0.0.1:4088/gallery", None, "165"),
        ("A-WEB-4088-PREF", "Topology Visualizer /api/preferred-view (:4088)", "http://127.0.0.1:4088/api/preferred-view", None, "preferred_view"),
        ("A-WEB-4089", "Natural-Language Ops Shell (:4089)", "http://127.0.0.1:4089/", None, "Ops Shell"),
        ("A-WEB-4090", "Cloud Burst Orchestrator (:4090)", "http://127.0.0.1:4090/", None, "Burst Orchestrator"),
        ("A-WEB-4091", "Physical Rack, iLO & vSAN Matrix (:4091)", "http://127.0.0.1:4091/", None, "Telemetry Matrix"),
        ("A-WEB-4092", "Gitea Pre-Review & OffSec Swarm (:4092)", "http://127.0.0.1:4092/", None, "OffSec"),
        ("A-WEB-4093", "Multimodal Voice/Vision Bridge (:4093)", "http://127.0.0.1:4093/", None, "Multimodal"),
        ("A-WEB-4094", "Deep Research & Dual-Oracle Studio (:4094)", "http://127.0.0.1:4094/", None, "Deep Research"),
        ("A-WEB-4095", "LobeChat Studio (:4095)", "http://127.0.0.1:4095/", None, "LobeChat"),
        ("A-WEB-4096", "OpenCode Web (:4096)", "http://127.0.0.1:4096/", None, "OpenCode"),
        ("A-WEB-4097", "OpenClaw Control (:4097)", "http://127.0.0.1:4097/", None, "OpenClaw"),
        ("A-WEB-4098", "Multi-Harness Studio & Arena (:4098)", "http://127.0.0.1:4098/", None, "Multi-Harness"),
        ("A-WEB-4099", "Sentinel 83-Service Self-Healer (:4099)", "http://127.0.0.1:4099/api/status", None, '"healthy_services": 83'),
        ("A-WEB-6080", "noVNC Desktop (:6080)", "http://127.0.0.1:6080/vnc.html", None, "noVNC"),
        ("A-WEB-8081", "TEI Embeddings (:8081/info)", "http://127.0.0.1:8081/info", None, "model_id"),
        ("A-WEB-8090", "OpenWebUI Controller (:8090)", "http://127.0.0.1:8090/", None, "Open WebUI"),
        ("A-WEB-8888", "SearXNG Meta-Search (:8888)", "http://127.0.0.1:8888/", None, "SearXNG"),
    ]
    for cid, name, url, hdrs, needle in local_portals:
        code, body, lat = http_probe(url, headers=hdrs)
        ok = (code == 200) and (needle.lower() in body.lower())
        runner.record(
            "Suite-A",
            cid,
            name,
            ok,
            f"HTTP {code}, matched='{needle}' ({len(body)}B)",
            lat,
        )

    remote_endpoints = [
        ("A-REM-72-8080", "OpenWebUI Vault A (.72:8080)", "http://10.0.70.72:8080/", "Open WebUI"),
        ("A-REM-125-6333", "Qdrant Vector DB (.125:6333)", "http://10.0.70.125:6333/collections", "bd_master_kb"),
        ("A-REM-228-4000", "LiteLLM Satellite (.228:4000)", "http://10.0.70.228:4000/health/liveliness", "I'm alive"),
        ("A-REM-137-11434", "BattleStation Ollama (.137:11434)", "http://10.0.10.137:11434/api/tags", "qwen2.5-coder:7b"),
        ("A-REM-137-9222", "BattleStation Chrome CDP (.137:9222)", "http://10.0.10.137:9222/json/version", "webSocketDebuggerUrl"),
        ("A-REM-181-9222", "Bittorrent Chrome CDP (.181:9222)", "http://10.0.70.181:9222/json/version", "webSocketDebuggerUrl"),
    ]
    for cid, name, url, needle in remote_endpoints:
        code, body, lat = http_probe(url)
        ok = (code == 200) and (needle.lower() in body.lower())
        runner.record(
            "Suite-A",
            cid,
            name,
            ok,
            f"HTTP {code}, matched='{needle}'",
            lat,
        )


def run_suite_b(runner: E2ERunner) -> None:
    log_stream("=== SUITE B: All 24 Traefik *.boylenet.themfboyles.com Virtual Host Routes (:80) ===")
    subdomains = [
        "os",
        "topology",
        "models",
        "terminal",
        "ca",
        "sso",
        "briefing",
        "doctor",
        "openwebui",
        "ai-webui",
        "harnesses",
        "burst",
        "sentinel",
        "research",
        "voice",
        "pwa",
        "lobechat",
        "opencode",
        "openclaw",
        "dashy",
        "gitea",
        "litellm",
        "offsec",
        "credentials",
    ]
    for sub in subdomains:
        vhost = f"{sub}.boylenet.themfboyles.com"
        code, body, lat = http_probe("http://10.0.70.164/", headers={"Host": vhost})
        ok = code in (200, 302) and len(body) > 0
        runner.record(
            "Suite-B",
            f"B-VHOST-{sub.upper()}",
            f"Traefik VHost {vhost}",
            ok,
            f"HTTP {code} ({len(body)}B)",
            lat,
        )


def run_suite_c(runner: E2ERunner) -> None:
    log_stream("=== SUITE C: CLI Tools, Core Subsystems & Live State Mutation Verification ===")

    t0 = time.monotonic()
    r = subprocess.run(
        ["/home/mboyle/bin/bd-local-triage-watch.py"],
        capture_output=True,
        text=True,
        timeout=25,
    )
    lat = (time.monotonic() - t0) * 1000.0
    fallback_exists = os.path.exists("/home/mboyle/bd-persist/state/LOCAL_LLM_FALLBACK_ACTIVE")
    try:
        watch_data = json.loads(r.stdout)
    except Exception:
        watch_data = {}
    ok_watch = (
        r.returncode == 0
        and watch_data.get("status") == "HEALTHY"
        and not fallback_exists
    )
    runner.record(
        "Suite-C",
        "C-LLM-HEALTH-01",
        "bd-local-triage-watch.py HEALTHY & LOCAL_LLM_FALLBACK_ACTIVE cleared",
        ok_watch,
        f"status={watch_data.get('status')}, fallback_flag_exists={fallback_exists}",
        lat,
    )

    with open("/home/mboyle/bd-persist/state/LOCAL_LLM_HEALTH.tsv", encoding="utf-8") as f:
        last_tsv = [ln.strip() for ln in f if ln.strip()][-1]
    runner.record(
        "Suite-C",
        "C-LLM-HEALTH-02",
        "LOCAL_LLM_HEALTH.tsv latest row records proxy=True,triv=True,ci=True",
        "HEALTHY" in last_tsv and "proxy=True,triv=True,ci=True" in last_tsv,
        last_tsv,
        1.0,
    )

    t0 = time.monotonic()
    r_ag = subprocess.run(
        ["/home/mboyle/bin/bd-airgap", "status"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    lat = (time.monotonic() - t0) * 1000.0
    ag_json = json.loads(r_ag.stdout) if r_ag.returncode == 0 else {}
    runner.record(
        "Suite-C",
        "C-AIRGAP-CLI",
        "bd-airgap status CLI across GPU nodes",
        r_ag.returncode == 0 and "airgap_enabled" in ag_json and len(ag_json.get("nodes", {})) >= 5,
        f"airgap_enabled={ag_json.get('airgap_enabled')}, nodes={len(ag_json.get('nodes', {}))}",
        lat,
    )

    code, body, lat = http_probe(
        "http://127.0.0.1:4085/api/airgap/verify",
        method="POST",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    ver_json = json.loads(body) if code == 200 else {}
    runner.record(
        "Suite-C",
        "C-AIRGAP-VERIFY",
        "Live POST :4085/api/airgap/verify real-time WAN probe & state update",
        code == 200 and bool(ver_json.get("verified_at")) and "airgap_enabled" in ver_json,
        f"HTTP {code}, verified_at={ver_json.get('verified_at')}",
        lat,
    )

    t0 = time.monotonic()
    r_list = subprocess.run(
        ["/home/mboyle/bin/bd-raw-ai", "--list"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    lat = (time.monotonic() - t0) * 1000.0
    runner.record(
        "Suite-C",
        "C-RAW-AI-LIST",
        "bd-raw-ai --list enumerates Cloud & Local Vault models",
        r_list.returncode == 0 and "qwen2.5-coder:7b" in r_list.stdout,
        f"lines={len(r_list.stdout.splitlines())}",
        lat,
    )

    t0 = time.monotonic()
    r_inf = subprocess.run(
        [
            "/home/mboyle/bin/bd-raw-ai",
            "--model",
            "qwen2.5-coder:7b",
            "Reply with strictly the word: CERT_PASS",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    lat = (time.monotonic() - t0) * 1000.0
    out_inf = r_inf.stdout.strip()
    runner.record(
        "Suite-C",
        "C-RAW-AI-INFER",
        "bd-raw-ai live inference on BattleStation .137:11434 (qwen2.5-coder:7b)",
        r_inf.returncode == 0 and "CERT_PASS" in out_inf.upper(),
        f"reply='{out_inf[:60]}'",
        lat,
    )

    t0 = time.monotonic()
    r_pool = subprocess.run(
        ["/home/mboyle/bin/bd-pool-usage-refresher.py"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    lat = (time.monotonic() - t0) * 1000.0
    with open("/home/mboyle/bd-persist/POOL_STATE.tsv", encoding="utf-8") as f:
        pool_lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith("pool\t")]
    unknown_pools = [ln.split("\t")[0] for ln in pool_lines if "\tUNKNOWN\t" in ln]
    now_str = now_iso()
    expired_pools = []
    for ln in pool_lines:
        cols = ln.split("\t")
        if len(cols) >= 6 and cols[5] and cols[5] < now_str:
            expired_pools.append(f"{cols[0]}({cols[5]})")
    runner.record(
        "Suite-C",
        "C-POOL-FRESH",
        "POOL_STATE.tsv freshness (9 pools OK, 0 UNKNOWN, 0 expired resets_at)",
        r_pool.returncode == 0 and len(pool_lines) >= 9 and len(unknown_pools) == 0 and len(expired_pools) == 0,
        f"pools={len(pool_lines)}, unknown={unknown_pools}, expired={expired_pools}",
        lat,
    )

    code_p, body_p, lat_p = http_probe("http://127.0.0.1:4098/api/pools")
    pools_api = json.loads(body_p) if code_p == 200 else {}
    runner.record(
        "Suite-C",
        "C-POOL-UI-SYNC",
        "Real-time POOL_STATE reflection in :4098/api/pools",
        code_p == 200 and len(pools_api.get("pools", [])) >= 9,
        f"HTTP {code_p}, api_pools={len(pools_api.get('pools', []))}",
        lat_p,
    )

    code_q, body_q, lat_q = http_probe("http://10.0.70.125:6333/collections/bd_master_kb")
    q_data = json.loads(body_q).get("result", {}) if code_q == 200 else {}
    pts = q_data.get("points_count", 0)
    runner.record(
        "Suite-C",
        "C-QDRANT-KB",
        "Qdrant bd_master_kb collection status green & populated",
        code_q == 200 and q_data.get("status") == "green" and pts > 0,
        f"status={q_data.get('status')}, points_count={pts}",
        lat_q,
    )

    code_s, body_s, lat_s = http_probe("http://127.0.0.1:4081/api/universal-search?q=qwen")
    s_data = json.loads(body_s) if code_s == 200 else {}
    srcs = s_data.get("sources", {})
    total_hits = sum(
        int(v.get("count", 0)) for v in srcs.values() if isinstance(v, dict)
    )
    runner.record(
        "Suite-C",
        "C-UNIV-SEARCH",
        ":4081/api/universal-search live hybrid query across Web UIs, 86 Models & Qdrant",
        code_s == 200 and s_data.get("status") == "ok" and total_hits > 0,
        f"total_hits={total_hits}, latency_ms={s_data.get('latency_ms')}",
        lat_s,
    )

    code_g, body_g, lat_g = http_probe("http://127.0.0.1:3000/api/v1/repos/search?limit=20")
    g_repos = [r["full_name"] for r in (json.loads(body_g).get("data", []) if code_g == 200 else [])]
    runner.record(
        "Suite-C",
        "C-GITEA-REPOS",
        "Gitea (:3000) hosts all core Boylenet repositories",
        code_g == 200 and "mboyle/UniversalSwarmOS" in g_repos and "mboyle/boylenet-swarm-os" in g_repos,
        f"count={len(g_repos)}, sample={g_repos[:5]}",
        lat_g,
    )

    nonce = f"E2E_LIVE_STREAM_NONCE_{int(time.time() * 1000)}"
    log_stream(f"Emit live stream mutation nonce: {nonce}")
    code_tv, body_tv, lat_tv = http_probe(
        "http://127.0.0.1:4083/api/pane?id=headless:agent105-full-suite-e2e-tests"
    )
    tv_ok = code_tv == 200 and nonce in body_tv
    runner.record(
        "Suite-C",
        "C-MUT-STREAM-4083",
        "Live stream write -> real-time reflection in :4083/api/pane",
        tv_ok,
        f"nonce={nonce} found={tv_ok}",
        lat_tv,
    )

    _, body_f0, _ = http_probe("http://127.0.0.1:4081/api/favorites")
    cnt0 = json.loads(body_f0).get("count", 0)
    fav_target = f"http://os.boylenet.themfboyles.com/#e2e-{int(time.time())}"
    fav_title = "E2E Live Favorite Toggle Probe"
    http_probe(
        "http://127.0.0.1:4081/api/favorites",
        method="POST",
        data=json.dumps({"kind": "url", "title": fav_title, "target": fav_target}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    _, body_f1, lat_f1 = http_probe("http://127.0.0.1:4081/api/favorites")
    f1_data = json.loads(body_f1)
    cnt1 = f1_data.get("count", 0)
    found_fav = any(x.get("target") == fav_target for x in f1_data.get("favorites", []))
    http_probe(
        "http://127.0.0.1:4081/api/favorites",
        method="POST",
        data=json.dumps({"action": "delete", "title": fav_title, "target": fav_target}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    _, body_f2, _ = http_probe("http://127.0.0.1:4081/api/favorites")
    cnt2 = json.loads(body_f2).get("count", 0)
    runner.record(
        "Suite-C",
        "C-MUT-FAV-4081",
        "Live :4081/api/favorites pin -> real-time count increment -> unstar restore",
        found_fav and cnt1 == cnt0 + 1 and cnt2 == cnt0,
        f"cnt0={cnt0} -> cnt1={cnt1} (found={found_fav}) -> cnt2={cnt2}",
        lat_f1,
    )

    _, body_pv0, _ = http_probe("http://127.0.0.1:4088/api/preferred-view")
    pv0 = json.loads(body_pv0).get("preferred_view", "V01")
    target_pv = "V28" if pv0 != "V28" else "V02"
    http_probe(
        "http://127.0.0.1:4088/api/preferred-view",
        method="POST",
        data=json.dumps({"preferred_view": target_pv}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    _, body_pv1, lat_pv1 = http_probe("http://127.0.0.1:4088/api/preferred-view")
    pv1 = json.loads(body_pv1).get("preferred_view")
    http_probe(
        "http://127.0.0.1:4088/api/preferred-view",
        method="POST",
        data=json.dumps({"preferred_view": pv0}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    _, body_pv2, _ = http_probe("http://127.0.0.1:4088/api/preferred-view")
    pv2 = json.loads(body_pv2).get("preferred_view")
    runner.record(
        "Suite-C",
        "C-MUT-PREFVIEW-4088",
        "Live :4088/api/preferred-view switch -> real-time readback -> restore",
        pv1 == target_pv and pv2 == pv0,
        f"{pv0} -> {pv1} -> {pv2}",
        lat_pv1,
    )

    code_dr, body_dr, lat_dr = http_probe(
        "http://127.0.0.1:4081/api/doctor-run",
        method="POST",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    dr_data = json.loads(body_dr) if code_dr == 200 else {}
    runner.record(
        "Suite-C",
        "C-MUT-DOCTOR-4081",
        "Live POST :4081/api/doctor-run executes 12/12 cluster health checks",
        code_dr == 200 and dr_data.get("status") == "ok" and dr_data.get("passed", 0) >= 12,
        f"passed={dr_data.get('passed')}",
        lat_dr,
    )


def cdp_audit_portal(cdp_host: str, port: int, path: str = "/") -> Dict[str, Any]:
    url = f"http://10.0.70.164:{port}{path}"
    req = urllib.request.Request(
        f"http://{cdp_host}:9222/json/new?{url}", method="PUT"
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        tab = json.loads(r.read().decode("utf-8"))
    tid = tab["id"]
    ws_url = tab["webSocketDebuggerUrl"]
    exceptions: List[str] = []
    try:
        ws = create_connection(ws_url, timeout=12)
        ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
        t_end = time.time() + 1.8
        while time.time() < t_end:
            ws.settimeout(0.4)
            try:
                m = json.loads(ws.recv())
                if m.get("method") == "Runtime.exceptionThrown":
                    exceptions.append(
                        m["params"]["exceptionDetails"].get("text", "uncaught")
                    )
            except Exception:
                pass

        js = """(() => {
            const sw = document.documentElement.scrollWidth;
            const cw = document.documentElement.clientWidth;
            const selector = "button, .btn, [role=button], .dock-item, .tab-btn, .tab, .pill, .filter-pill, .recipe-pill, nav a";
            const interactive = Array.from(document.querySelectorAll(selector));
            const visible = interactive.filter(el => {
                const s = window.getComputedStyle(el);
                if (s.display === "none" || s.visibility === "hidden" || parseFloat(s.opacity) === 0) return false;
                if (el.offsetParent === null && s.position !== "fixed" && s.position !== "sticky") return false;
                return true;
            });
            const zeroBox = visible.filter(el => {
                const r = el.getBoundingClientRect();
                return r.width <= 0 || r.height <= 0;
            }).map(el => el.tagName + "." + el.className);

            let clicked = 0;
            for (const el of visible.slice(0, 25)) {
                const txt = (el.innerText || "").toLowerCase();
                const oc = (el.getAttribute("onclick") || "").toLowerCase();
                if (el.tagName === "A") {
                    const href = el.getAttribute("href") || "";
                    if (href && !href.startsWith("#") && !href.startsWith("javascript:")) continue;
                }
                if (
                    oc.includes("window.open") || oc.includes("location.href") ||
                    oc.includes("heal") || oc.includes("restart") || oc.includes("retire") ||
                    oc.includes("kill") || oc.includes("airgap") || oc.includes("switchmode") ||
                    txt.includes("restart") || txt.includes("heal") || txt.includes("delete") ||
                    txt.includes("reset") || txt.includes("arm") || txt.includes("launch")
                ) continue;
                try {
                    el.click();
                    clicked++;
                } catch (e) {}
            }
            const swAfter = document.documentElement.scrollWidth;
            const cwAfter = document.documentElement.clientWidth;
            return {
                title: document.title,
                readyState: document.readyState,
                sw, cw, overflow: sw > cw,
                swAfter, cwAfter, overflowAfter: swAfter > cwAfter,
                visibleCount: visible.length,
                clickedCount: clicked,
                zeroBoxCount: zeroBox.length
            };
        })()"""
        ws.settimeout(8)
        ws.send(
            json.dumps(
                {
                    "id": 99,
                    "method": "Runtime.evaluate",
                    "params": {"expression": js, "returnByValue": True},
                }
            )
        )
        val: Dict[str, Any] = {}
        while True:
            m = json.loads(ws.recv())
            if m.get("method") == "Runtime.exceptionThrown":
                exceptions.append(
                    m["params"]["exceptionDetails"].get("text", "uncaught")
                )
            if m.get("id") == 99:
                val = m.get("result", {}).get("result", {}).get("value", {})
                break
        ws.close()
        val["exceptions"] = exceptions
        return val
    finally:
        try:
            urllib.request.urlopen(
                f"http://{cdp_host}:9222/json/close/{tid}", timeout=5
            ).read()
        except Exception:
            pass


def run_suite_d(runner: E2ERunner) -> None:
    log_stream("=== SUITE D: Playwright/CDP Browser E2E, Bar/Button/Tab Click-Through & Geometry ===")
    portals = [
        (4085, "/", "Unified OS Desktop Shell (:4085)"),
        (4088, "/", "165-View 60fps Topology Visualizer (:4088)"),
        (4088, "/gallery", "Topology Visualizer 165-View Gallery (:4088/gallery)"),
        (4084, "/", "86-Model Vault Storefront (:4084)"),
        (4083, "/", "Agent TV Wall & Multi-Node Terminal (:4083)"),
        (4082, "/", "Zero-Friction SSO, QR & Root CA Portal (:4082)"),
        (4081, "/", "Executive Briefing, Search & Doctor (:4081)"),
        (4098, "/", "Multi-Harness AI Studio & Arena (:4098)"),
        (4090, "/", "Hybrid Cloud + Local Burst Orchestrator (:4090)"),
        (4095, "/", "LobeChat AI Workspace (:4095)"),
        (4096, "/", "OpenCode Web UI (:4096)"),
        (4097, "/", "OpenClaw Control UI (:4097)"),
        (4099, "/", "Infra Sentinel 83-Service Self-Healer (:4099)"),
        (8090, "/", "OpenWebUI Controller (:8090)"),
    ]
    for port, path, label in portals:
        t0 = time.monotonic()
        res = cdp_audit_portal("10.0.10.137", port, path)
        lat = (time.monotonic() - t0) * 1000.0
        sfx = "GAL" if path == "/gallery" else str(port)
        geom_ok = (
            res.get("readyState") == "complete"
            and bool(res.get("title"))
            and not res.get("overflow")
            and not res.get("overflowAfter")
            and res.get("zeroBoxCount", 1) == 0
        )
        runner.record(
            "Suite-D",
            f"D-CDP-DOM-{sfx}",
            f"CDP Render & Responsive Geometry {label}",
            geom_ok,
            f"sw={res.get('sw')}/{res.get('cw')}, swAfter={res.get('swAfter')}/{res.get('cwAfter')}, zeroBox={res.get('zeroBoxCount')}",
            lat,
        )
        click_ok = (
            res.get("visibleCount", 0) > 0
            and len(res.get("exceptions", [])) == 0
        )
        runner.record(
            "Suite-D",
            f"D-CDP-CLICK-{sfx}",
            f"Interactive Bar/Button/Tab/Pill Click-Through {label}",
            click_ok,
            f"visible={res.get('visibleCount')}, clicked={res.get('clickedCount')}, exceptions={len(res.get('exceptions', []))}",
            lat,
        )

    t0 = time.monotonic()
    res_181 = cdp_audit_portal("10.0.70.181", 4085, "/")
    lat_181 = (time.monotonic() - t0) * 1000.0
    ok_181 = (
        res_181.get("readyState") == "complete"
        and not res_181.get("overflow")
        and len(res_181.get("exceptions", [])) == 0
    )
    runner.record(
        "Suite-D",
        "D-CDP-181-ORACLE",
        "Secondary CDP Oracle (.181:9222) Render & Click-Through (:4085)",
        ok_181,
        f"sw={res_181.get('sw')}/{res_181.get('cw')}, clicked={res_181.get('clickedCount')}, exceptions={len(res_181.get('exceptions', []))}",
        lat_181,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Boylenet Full-Suite E2E Certification Harness")
    parser.add_argument("--quick", action="store_true", help="Fast 8-endpoint + BDKB + MCP check")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()
    if args.quick:
        return run_quick_mode()

    runner = E2ERunner()
    log_stream("Starting Boylenet Full-Suite E2E Certification Harness (Agent-105)...")
    run_suite_a(runner)
    run_suite_b(runner)
    run_suite_c(runner)
    run_suite_d(runner)

    total = len(runner.assertions)
    passed = sum(1 for a in runner.assertions if a["passed"])
    failed = [a for a in runner.assertions if not a["passed"]]
    elapsed_s = round(time.monotonic() - runner.t0, 2)

    summary = {
        "started_at": runner.started_at,
        "completed_at": now_iso(),
        "elapsed_s": elapsed_s,
        "total_assertions": total,
        "passed_assertions": passed,
        "failed_assertions": len(failed),
        "pass_rate_pct": round((passed / max(1, total)) * 100.0, 2),
        "status": "PASS" if not failed else "FAIL",
        "failures": failed,
        "assertions": runner.assertions,
    }
    with open(JSON_REPORT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    log_stream(
        f"=== E2E SUMMARY: {passed}/{total} PASSED ({summary['pass_rate_pct']}%) in {elapsed_s}s -> {JSON_REPORT} ==="
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
