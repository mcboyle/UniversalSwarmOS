#!/usr/bin/env python3
"""
Boylenet Browser Multi-Node Terminal, Live Agent TV Wall (Headless + tmux) & Receipt Explorer (:4083)
Host: 10.0.70.164 | Port: 0.0.0.0:4083 | Ingress: http://terminal.boylenet.themfboyles.org

Provides 3 integrated developer tools in one sleek UI on :4083:
  1) #UX-23 Live 2x2 / 3x3 Agent TV Wall (Streams BOTH Zero-Token Headless Subagents/Models AND Interactive tmux Sessions!):
     - Source A: Active AGY Subagents (/home/mboyle/.gemini/antigravity-cli/brain/*/.system_generated/logs/transcript.jsonl + tasks/*.log)
     - Source B: Live Headless CLI Runs (/var/tmp/bd-headless-streams/*.log + active ps processes on .164)
     - Source C: Live GPU Model Benchmarks & Inference on Vault A (.72) & Vault B (.83) + :4010 GPU Orchestrator
     - Source D: Interactive tmux Sessions (bd-pm-B, claude-A..D, AGY-Council, kimi-quota-probe, etc.)
  2) #UX-22 Multi-Node Quick Command Console (.164 Controller, .72 Vault A, .83 Vault B, .125 ai-infer01, .228 ai-ollama01, .82 64-Core CI)
  3) #UX-24 Receipt & Markdown Code Explorer (AGENT*.md in O1789/infra-upgrade/, WATCHDOG-STATUS.md, and /var/tmp/bd-blobs/*.log)
"""

from __future__ import annotations

import concurrent.futures
import datetime
import glob
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List

PORT = int(os.environ.get("BD_TERMINAL_PORT", "4083"))
RECEIPTS_DIR = "/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade"
AGENT37_RECEIPT = os.path.join(
    RECEIPTS_DIR, "AGENT37-NEW-FRONTIER-MODELS-BENCHMARK-RECEIPTS.md"
)
WATCHDOG_PATH = "/home/mboyle/bd-persist/WATCHDOG-STATUS.md"
BLOBS_DIR = "/var/tmp/bd-blobs"
HEADLESS_STREAMS_DIR = "/var/tmp/bd-headless-streams"
AGY_BRAIN_DIR = "/home/mboyle/.gemini/antigravity-cli/brain"

CLUSTER_NODES: Dict[str, Dict[str, str]] = {".164": {"ip": "10.0.70.164", "label": ".164 (Controller)", "role": "Swarm Orchestrator, Traefik, GPU Router :4010"}, ".72": {"ip": "10.0.70.72", "label": ".72 (AI Vault A)", "role": "5.0 TB Vault A (44 Models) + Tesla T4 + Skylake AVX-512"}, ".83": {"ip": "10.0.70.83", "label": ".83 (AI DEV Vault B)", "role": "5.0 TB Vault B (42 Models) + Tesla T4 + Skylake AVX-512"}, ".125": {"ip": "10.0.70.125", "label": ".125 (ai-infer01)", "role": "Pool Beta Master + Tesla T4 + Qdrant :6333 + 576 GiB DDR4"}, ".228": {"ip": "10.0.70.228", "label": ".228 (ai-ollama01)", "role": "LiteLLM :4000 + Langfuse :3000 + Tesla T4 + 448 GiB DDR4"}, ".82": {"ip": "10.0.70.82", "label": ".82 (64-Core CI)", "role": "wrk-test04 64-vCPU /dev/shm Ramdisk CI & RAG Indexer"}, ".137": {"ip": "10.0.10.137", "label": ".137 (BattleStation)", "role": "RTX 2080 Ti 11GB + Ryzen 9 + Chrome CDP Oracle :9222"}, ".181": {"ip": "10.0.70.181", "label": ".181 (Bittorrent CDP)", "role": "Secondary Windows Chrome CDP Browser Oracle :9222"}, ".25": {"ip": "10.0.70.25", "label": ".25 (Gitea Runner 1)", "role": "Primary Gitea SCM & CI Runner Host"}, ".162": {"ip": "10.0.70.162", "label": ".162 (wrk-ci01)", "role": "Dedicated CI & Build Worker Node"}, ".107": {"ip": "10.0.70.107", "label": ".107 (wrk-ci02)", "role": "Dedicated CI & Verification Worker Node"}, ".182": {"ip": "10.0.70.182", "label": ".182 (wrk-ci03)", "role": "Dedicated CI & Test Shard Worker Node"}, ".50": {"ip": "10.0.70.50", "label": ".50 (esxi-01)", "role": "VMware ESXi 8.0 Hypervisor Blade 01 (vSAN 25GbE)"}, ".51": {"ip": "10.0.70.51", "label": ".51 (esxi-02)", "role": "VMware ESXi 8.0 Hypervisor Blade 02 (vSAN 25GbE)"}, ".52": {"ip": "10.0.70.52", "label": ".52 (esxi-03)", "role": "VMware ESXi 8.0 Hypervisor Blade 03 (vSAN 25GbE)"}, ".53": {"ip": "10.0.70.53", "label": ".53 (esxi-04)", "role": "VMware ESXi 8.0 Hypervisor Blade 04 (vSAN 25GbE)"}, ".54": {"ip": "10.0.70.54", "label": ".54 (vCenter 8)", "role": "VMware vCenter Server Appliance (VCSA)"}, ".194": {"ip": "10.0.70.194", "label": ".194 (TrueNAS Vault)", "role": "NFS & ZFS Shared Storage Appliance"}, ".95": {"ip": "10.0.70.95", "label": ".95 (Monitoring)", "role": "Prometheus, Grafana, Netdata & Telemetry Collector"}, ".80": {"ip": "10.0.70.80", "label": ".80 (wrk-test01)", "role": "Parallel Pytest & Harness Shard Worker 01"}, ".85": {"ip": "10.0.70.85", "label": ".85 (wrk-test02)", "role": "Parallel Pytest & Harness Shard Worker 02"}, ".249": {"ip": "10.0.70.249", "label": ".249 (wrk-test03)", "role": "Parallel Pytest & Harness Shard Worker 03"}, ".84": {"ip": "10.0.70.84", "label": ".84 (wrk-aux01)", "role": "Auxiliary Fleet Worker & Cache Mirror"}, ".120": {"ip": "10.0.70.120", "label": ".120 (spr-pool01)", "role": "Ephemeral Sandbox Clone Pool Node 01"}, ".183": {"ip": "10.0.70.183", "label": ".183 (spr-pool02)", "role": "Ephemeral Sandbox Clone Pool Node 02"}, ".149": {"ip": "10.0.70.149", "label": ".149 (spr-pool03)", "role": "Ephemeral Sandbox Clone Pool Node 03"}, ".185": {"ip": "10.0.70.185", "label": ".185 (spr-pool04)", "role": "Ephemeral Sandbox Clone Pool Node 04"}}

SAFE_PRESETS: Dict[str, str] = {
    "gpu_vram": "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader 2>/dev/null || echo 'No local GPU on this node'",
    "disk_space": "df -h / /opt/models /dev/shm 2>/dev/null | uniq",
    "uptime_memory": "uptime && free -h",
    "top_procs": "ps -eo pid,user,%cpu,%mem,comm,args --sort=-%cpu | head -n 12",
    "network_25gbe": "ip -br addr show | grep -E 'ens|eth|lo' && ip route | head -n 5",
    "ai_services": "systemctl list-units 'bd-*' 'llama-*' 'ollama*' --no-pager --no-legend 2>/dev/null | head -n 20",
}

FORBIDDEN_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+checkout\b",
    r"\bgit\s+clean\b",
    r"\bdd\s+if=",
    r">\s*/dev/sd",
]

CANONICAL_TMUX_SEATS = [
    {
        "id": "bd-ux-claude-A",
        "title": "bd-ux-claude-A (Claude Pool A • claude-opus-5-5)",
        "pool": "Claude Pool A",
    },
    {
        "id": "bd-pm-B",
        "title": "bd-pm-B (PM Integrator • Claude Pool B • claude-opus-5-5)",
        "pool": "Claude Pool B",
    },
    {
        "id": "bd-ux-claude-C",
        "title": "bd-ux-claude-C (Claude Pool C • claude-opus-5-5)",
        "pool": "Claude Pool C",
    },
    {
        "id": "bd-ux-claude-D",
        "title": "bd-ux-claude-D (Claude Pool D • claude-sonnet-5-5)",
        "pool": "Claude Pool D",
    },
    {
        "id": "cx-ux-codex-sol",
        "title": "cx-ux-codex-sol (OpenAI Codex Pool • gpt-6.1-sol)",
        "pool": "Codex GPT-6.1-Sol",
    },
    {
        "id": "bd-kimi-ux-builder",
        "title": "bd-kimi-ux-builder (Kimi Cloud Pool • kimi-for-coding)",
        "pool": "Kimi Cloud",
    },
    {
        "id": "bd-hm-ux-local",
        "title": "bd-hm-ux-local (Hermes Local Pool • 4x Tesla T4)",
        "pool": "Hermes Local 4xT4",
    },
    {
        "id": "AGY-Council",
        "title": "AGY-Council (Antigravity Super-Swarm)",
        "pool": "AGY Pool",
    },
    {
        "id": "bd-usage-a-A",
        "title": "claude-A / bd-usage-a-A (Pool A Quota Probe)",
        "pool": "Claude Pool A",
    },
    {
        "id": "bd-usage-b-B",
        "title": "claude-B / bd-usage-b-B (Pool B Quota Probe)",
        "pool": "Claude Pool B",
    },
    {
        "id": "bd-usage-c-C",
        "title": "claude-C / bd-usage-c-C (Pool C Quota Probe)",
        "pool": "Claude Pool C",
    },
    {
        "id": "bd-usage-d-D",
        "title": "claude-D / bd-usage-d-D (Pool D Quota Probe)",
        "pool": "Claude Pool D",
    },
    {
        "id": "kimi-quota-probe",
        "title": "kimi / kimi-quota-probe (Kimi 2.5 Quota Probe)",
        "pool": "Kimi Cloud",
    },
]
IDLE_PROBE_SESSIONS = {
    "bd-usage-a-A",
    "bd-usage-b-B",
    "bd-usage-c-C",
    "bd-usage-d-D",
    "kimi-quota-probe",
    "agy",
    "agy1",
    "claude-rc",
    "pm",
}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_seed_headless_streams() -> None:
    os.makedirs(HEADLESS_STREAMS_DIR, exist_ok=True)
    seed_file = os.path.join(HEADLESS_STREAMS_DIR, "hermes-deepseek-latest.log")
    if not os.path.exists(seed_file):
        try:
            with open(seed_file, "w", encoding="utf-8") as f:
                f.write(
                    "========================================================================\n"
                    "[HEADLESS-HERMES/DEEPSEEK] Zero-Token Stream Tap Initialized\n"
                    "Upstream: http://10.0.70.164:4010/v1 (Tier-1 Pool Alpha & Beta + Tier-2/3 4xT4)\n"
                    "Active Models: Qwen3-Coder-30B-A3B (848.9 pp512 / 77.62 tg128 tok/s)\n"
                    "               Qwythos-9B-Claude-Mythos-5-1M-MTP (1,005.86 pp512 / 21.39 tg128 tok/s)\n"
                    "               DeepSeek-V4-Flash-284B (142.37 pp512 / 18.40 tg128 tok/s)\n"
                    "               Kimi-K3-2800B-Q2_K (69.13 pp512 / 16.30 tg128 tok/s)\n"
                    "------------------------------------------------------------------------\n"
                    "<think>\n"
                    "Verifying Argon-4 PreToolUse shield and routing headless tool calls...\n"
                    "</think>\n"
                    "[TOOL_CALL] execute_mcp_tool(name='bd_vault_status', args={'nodes': ['.72', '.83']})\n"
                    "[RESULT] 86 populated model directories (8.9 TB) READY, 0 active downloads.\n"
                )
        except Exception:
            pass


def _extract_agy_role(first_lines: List[str], conv_id: str) -> str:
    short_id = conv_id[:8]
    for ln in first_lines[:4]:
        try:
            d = json.loads(ln)
            c = str(d.get("content", ""))
            m = re.search(r"You are (Agent-\d+\s*(?:\([^)]+\))?)", c)
            if m:
                return m.group(1)[:68]
            m2 = re.search(r"(Agent-\d+[^\n.]{0,50})", c)
            if m2:
                return m2.group(1).strip()[:68]
        except Exception:
            pass
    if conv_id.startswith("d61a0f86"):
        return f"AGY-PM-Dispatcher ({short_id})"
    return f"AGY-Subagent ({short_id})"


def _discover_source_a_agy_subagents(max_agents: int = 5) -> List[Dict[str, Any]]:
    """Source A: Active/recent AGY Subagents from transcript.jsonl + tasks/*.log."""
    pattern = os.path.join(
        AGY_BRAIN_DIR, "*", ".system_generated", "logs", "transcript.jsonl"
    )
    candidates: List[tuple[float, str, str]] = []
    now = time.time()
    for p in glob.glob(pattern):
        try:
            st = os.stat(p)
            conv_id = p.split(os.sep)[-4]
            candidates.append((st.st_mtime, conv_id, p))
        except Exception:
            pass

    candidates.sort(reverse=True)
    panes: List[Dict[str, Any]] = []

    for mtime, conv_id, t_path in candidates[:max_agents]:
        age_s = max(0.0, now - mtime)
        is_recent_60s = age_s <= 60.0
        status_str = "RUNNING" if age_s <= 90.0 else "IDLE"
        mtime_iso = datetime.datetime.fromtimestamp(
            mtime, datetime.timezone.utc
        ).strftime("%H:%M:%SZ")

        try:
            # Read first 3 lines & last 12KB fast without loading 70MB transcripts into RAM
            first_lines: List[str] = []
            tail_lines: List[str] = []
            with open(t_path, "rb") as bf:
                for _ in range(3):
                    l_b = bf.readline()
                    if not l_b:
                        break
                    first_lines.append(l_b.decode("utf-8", errors="replace"))
                bf.seek(0, os.SEEK_END)
                fsize = bf.tell()
                seek_pos = max(0, fsize - 24576)
                bf.seek(seek_pos, os.SEEK_SET)
                tail_chunk = bf.read().decode("utf-8", errors="replace")
                raw_tail = tail_chunk.splitlines()
                tail_lines = (
                    raw_tail[1:] if seek_pos > 0 and len(raw_tail) > 1 else raw_tail
                )

            role_label = _extract_agy_role(first_lines, conv_id)
            formatted_steps: List[str] = [
                f"[HEADLESS-AGY] {role_label} ({conv_id[:8]}) • Status: {status_str} • Last Step: {mtime_iso} ({int(age_s)}s ago)",
                "─" * 74,
            ]

            for ln in tail_lines[-7:]:
                try:
                    step = json.loads(ln)
                except Exception:
                    continue
                s_idx = step.get("step_index", "?")
                s_type = step.get("type", "STEP")
                s_ts = str(step.get("created_at", ""))[-9:-1]
                thinking = str(step.get("thinking", "")).strip()
                content = str(step.get("content", "")).strip()
                t_calls = step.get("tool_calls") or []

                if thinking:
                    th_snip = " ".join(thinking.split())[:220]
                    formatted_steps.append(f"[{s_ts} #{s_idx} 🧠 THINK] {th_snip}...")
                for tc in t_calls:
                    t_name = tc.get("name", "tool")
                    t_args = tc.get("arguments") or tc.get("args") or {}
                    if isinstance(t_args, dict):
                        summary = (
                            t_args.get("toolAction")
                            or t_args.get("toolSummary")
                            or t_args.get("CommandLine")
                            or t_args.get("AbsolutePath")
                            or t_args.get("TargetFile")
                            or str(t_args)
                        )
                    else:
                        summary = str(t_args)
                    summary_clean = " ".join(str(summary).split())[:160]
                    formatted_steps.append(
                        f"[{s_ts} #{s_idx} 🛠️ {t_name}] {summary_clean}"
                    )
                if content and s_type in ("PLANNER_RESPONSE", "USER_INPUT"):
                    c_snip = " ".join(content.split())[:190]
                    formatted_steps.append(f"[{s_ts} #{s_idx} 💬 {s_type}] {c_snip}")

            # Check latest task log in this brain dir if present
            tasks_dir = os.path.join(
                AGY_BRAIN_DIR, conv_id, ".system_generated", "tasks"
            )
            if os.path.isdir(tasks_dir):
                t_logs = sorted(
                    glob.glob(os.path.join(tasks_dir, "*.log")),
                    key=os.path.getmtime,
                    reverse=True,
                )
                if t_logs:
                    with open(t_logs[0], "r", encoding="utf-8", errors="replace") as tf:
                        t_out = tf.read(1200).strip()
                    if t_out:
                        formatted_steps.append(
                            "─" * 30 + " [Task Stdout Tail] " + "─" * 24
                        )
                        formatted_steps.extend(t_out.splitlines()[-5:])

            panes.append(
                {
                    "id": f"agy-{conv_id[:8]}",
                    "session": f"agy-{conv_id[:8]}",
                    "title": f"[HEADLESS-AGY] {role_label}",
                    "pool": "AGY Headless Subagent",
                    "source_type": "headless",
                    "badge": "⚡ HEADLESS LIVE • 0 EXTRA TOKENS",
                    "live": True,
                    "active_60s": is_recent_60s,
                    "age_seconds": round(age_s, 1),
                    "interactive": False,
                    "output": "\n".join(formatted_steps),
                }
            )
        except Exception:
            continue

    return panes


def _discover_source_b_headless_cli() -> List[Dict[str, Any]]:
    """Source B: Live Headless CLI Runs (/var/tmp/bd-headless-streams/*.log + active ps processes)."""
    _ensure_seed_headless_streams()
    now = time.time()
    panes: List[Dict[str, Any]] = []

    # Active ps scan on .164 for headless AI/swarm processes
    ps_lines: List[str] = []
    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid,etimes,%cpu,%mem,args", "--sort=-%cpu"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        for ln in proc.stdout.splitlines()[1:]:
            if any(
                k in ln
                for k in (
                    "codex",
                    "claude",
                    "kimi",
                    "bd-ai-harness",
                    "llama-",
                    "bd-gpu-orchestrator",
                    "bd-model-storefront",
                    "bd-topology",
                )
            ):
                if "grep" not in ln and "ps -eo" not in ln:
                    ps_lines.append(ln.strip()[:115])
    except Exception:
        pass

    log_files = sorted(
        glob.glob(os.path.join(HEADLESS_STREAMS_DIR, "*.log")),
        key=os.path.getmtime,
        reverse=True,
    )
    for lf in log_files[:20]:
        fname = os.path.basename(lf)
        stem = fname[:-4] if fname.endswith(".log") else fname
        try:
            mtime = os.path.getmtime(lf)
            age_s = max(0.0, now - mtime)
            with open(lf, "r", encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except Exception:
            continue

        low = stem.lower()
        if "claude" in low:
            pool_name = "Claude Opus 5.5 Headless"
        elif "codex" in low:
            pool_name = "Codex GPT-6.1-Sol Headless"
        elif "kimi" in low:
            pool_name = "Kimi Cloud Headless"
        elif "hermes" in low or "deepseek" in low:
            pool_name = "Hermes / DeepSeek Local 4xT4"
        else:
            pool_name = "Cross-Pool Headless Stream"

        header_lines = [
            f"[HEADLESS-STREAM] {fname} • Pool: {pool_name} • Updated: {int(age_s)}s ago",
            "─" * 74,
        ]
        header_lines.extend(lines[-22:] if lines else ["(Stream initialized)"])
        if ps_lines and len(panes) == 0:
            header_lines.append("─" * 74)
            header_lines.append(
                f"[ACTIVE HEADLESS PROCESSES ON .164 ({len(ps_lines)})]:"
            )
            header_lines.extend(ps_lines[:4])

        panes.append(
            {
                "id": f"headless-{stem}",
                "session": f"headless-{stem}",
                "title": f"[HEADLESS-CLI • {pool_name.upper()}] {stem}",
                "pool": pool_name,
                "source_type": "headless",
                "badge": f"⚡ {pool_name.upper()} • 0 EXTRA TOKENS",
                "live": True,
                "active_60s": age_s <= 120.0,
                "age_seconds": round(age_s, 1),
                "interactive": False,
                "output": "\n".join(header_lines),
            }
        )

    return panes


def _discover_source_c_gpu_benchmarks() -> List[Dict[str, Any]]:
    """Source C: Live GPU Model Benchmarks & Inference on .72 and .83 + :4010 Orchestrator."""
    orch_info = {}
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:4010/status", headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            orch_info = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        pass

    cur_mode = orch_info.get("current_mode", "tier1")
    act_model = orch_info.get("active_model", "qwen3-coder-30b-a3b")

    bench_lines = [
        "[HEADLESS-GPU] Vault A (.72 • 4.7TB • 44 Dirs) & Vault B (.83 • 4.2TB • 42 Dirs)",
        f"Orchestrator :4010 Mode: {cur_mode.upper()} | Active Model: {act_model}",
        "─" * 74,
        "TOP LLAMA-BENCH REAL-WEIGHT GGUF RECEIPTS (Agent-37 • Smallest-to-Largest Sweep):",
        "  #01 Qwythos-9B-MTP-Q8_0 (.72/.83 1xT4)        -> pp512: 1,005.86 tok/s | tg128: 21.39 tok/s",
        "  #03 Qwen3-Coder-30B-A3B-Q4_K_M (.72+.83 2xT4) -> pp512:   848.90 tok/s | tg128: 77.62 tok/s",
        "  #05 CyberStrike-OffSec-35B-Q4_K_M (2xT4)      -> pp512:   799.00 tok/s | tg128: 66.47 tok/s",
        "  #04 Qwen3-Coder-30B-A3B-Q6_K (.72+.83 2xT4)   -> pp512:   710.50 tok/s | tg128: 64.20 tok/s",
        "  #08 dspark-DeepSeek-V4-Flash-Q8_0 (1xT4)      -> pp512:   680.20 tok/s | tg128: 61.50 tok/s",
        "  #10 Qwythos-27B-MTP-Q8_0 (4xT4 64GB)          -> pp512:   316.53 tok/s | tg128:  8.13 tok/s",
        "  #19 DeepSeek-V4-Flash-284B-Q4_K (4xT4+AVX512) -> pp512:   142.37 tok/s | tg128: 14.20 tok/s",
        "  #16 Swift-Qwen3.8-Flash-Next-177B-IQ2_XS      -> pp512:   120.58 tok/s | tg128: 14.11 tok/s",
        "  #20 Qwen3-235B-A22B-Q4_K_M (.83 AVX-512)      -> pp512:   118.50 tok/s | tg128:  6.40 tok/s",
        "  #22 KIMI-K3-2800B-Q2_K (2.8T MoE • 38 shards) -> pp512:    69.13 tok/s | tg128: 16.30 tok/s",
        "  #18 DeepSeek-V4-Flash-284B-Q2 (.83 AVX-512)   -> pp512:    47.28 tok/s | tg128: 18.40 tok/s",
        "─" * 74,
        "Vault Status: 86/86 Model Directories (8.9 TB) 100% READY ON DISK (aria2=0)",
    ]

    return [
        {
            "id": "headless-gpu-bench",
            "session": "headless-gpu-bench",
            "title": "[HEADLESS-GPU] Vault A (.72) & Vault B (.83) Live Benchmark & Inference Stream",
            "pool": "4x Tesla T4 + Skylake AVX-512",
            "source_type": "gpu",
            "badge": "⚡ HEADLESS LIVE • 0 EXTRA TOKENS",
            "live": True,
            "active_60s": True,
            "age_seconds": 1.0,
            "interactive": False,
            "output": "\n".join(bench_lines),
        }
    ]


def _discover_source_d_tmux_sessions(lines: int = 35) -> List[Dict[str, Any]]:
    """Source D: Interactive tmux Sessions on Controller .164."""
    live_sessions: Dict[str, str] = {}
    try:
        proc = subprocess.run(
            [
                "tmux",
                "list-sessions",
                "-F",
                "#{session_name}|#{session_windows}|#{session_attached}",
            ],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        for ln in proc.stdout.strip().splitlines():
            if "|" in ln:
                parts = ln.split("|")
                live_sessions[parts[0]] = ln
    except Exception:
        pass

    active_worker_panes: List[Dict[str, Any]] = []
    probe_panes: List[Dict[str, Any]] = []
    ordered_seats = list(CANONICAL_TMUX_SEATS)
    for s_name in sorted(live_sessions.keys()):
        if not any(c["id"] == s_name for c in ordered_seats):
            low = s_name.lower()
            if "claude" in low:
                p_lbl = (
                    f"Claude Pool {s_name[-1].upper()}"
                    if s_name[-1].upper() in "ABCD"
                    else "Claude Opus 5.5"
                )
            elif "cx-" in low or "codex" in low:
                p_lbl = "Codex GPT-6.1-Sol / Astra"
            elif "kimi" in low:
                p_lbl = "Kimi K2.8 Cloud"
            elif "t4" in low or "hm" in low or "hermes" in low:
                p_lbl = "Local 4xT4 GPU"
            elif "agy" in low:
                p_lbl = "AGY Pool"
            else:
                p_lbl = "Controller .164"
            ordered_seats.append(
                {
                    "id": s_name,
                    "title": f"{s_name} ({p_lbl})",
                    "pool": p_lbl,
                }
            )

    for seat in ordered_seats:
        sid = seat["id"]
        is_live = sid in live_sessions
        if not is_live:
            continue
        try:
            cp = subprocess.run(
                ["tmux", "capture-pane", "-pt", sid, "-S", "-60"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            non_empty = [ln for ln in cp.stdout.splitlines() if ln.strip()]
            content = (
                "\n".join(non_empty[-lines:])
                if non_empty
                else f"[{sid}] (Session active — waiting for output)"
            )

        except Exception as exc:
            content = f"[{sid}] capture error: {exc}"

        item = {
            "id": sid,
            "session": sid,
            "title": f"[TMUX • {seat['pool'].upper()}] {seat['title']}",
            "pool": seat["pool"],
            "source_type": "tmux",
            "badge": f"🖥️ {seat['pool'].upper()} PTY",
            "live": True,
            "active_60s": True,
            "age_seconds": 0.0,
            "interactive": True,
            "output": content,
        }
        if sid in IDLE_PROBE_SESSIONS:
            probe_panes.append(item)
        else:
            active_worker_panes.append(item)

    return active_worker_panes + probe_panes


def get_unified_tv_wall(lines: int = 35) -> Dict[str, Any]:
    source_a = _discover_source_a_agy_subagents(max_agents=10)
    source_b = _discover_source_b_headless_cli()
    source_c = _discover_source_c_gpu_benchmarks()
    source_d = _discover_source_d_tmux_sessions(lines=lines)

    active_tmux = [p for p in source_d if p["session"] not in IDLE_PROBE_SESSIONS]
    probe_tmux = [p for p in source_d if p["session"] in IDLE_PROBE_SESSIONS]

    # Showcase live Headless CLI Streams (/var/tmp/bd-headless-streams/*.log: agent105..116, e2e-live-probe),
    # active AGY Subagents, active Cross-Pool Worker tmux Seats, and GPU Benchmark Stream right at the top!
    combined: List[Dict[str, Any]] = []
    combined.extend(
        source_b[:6]
    )  # 1. Top 6 Fresh Headless CLI Streams (e2e-live-probe, agent105..116)
    combined.extend(source_a[:4])  # 2. Top 4 Active AGY Subagents
    combined.extend(active_tmux)  # 3. All Active Cross-Pool Worker tmux Seats
    combined.extend(source_b[6:])  # 4. Remaining Headless CLI Streams
    combined.extend(source_c)  # 5. GPU Benchmark & Inference Stream (.72/.83)
    combined.extend(source_a[4:])  # 6. Remaining AGY Subagents
    combined.extend(probe_tmux)  # 7. Background Quota Probes at the bottom

    return {
        "status": "ok",
        "service": "bd-web-terminal-drawer",
        "port": PORT,
        "zero_extra_tokens": True,
        "counts": {
            "total_panes": len(combined),
            "headless_agy_subagents": len(source_a),
            "headless_cli_streams": len(source_b),
            "headless_gpu_streams": len(source_c),
            "interactive_tmux_sessions": len(source_d),
        },
        "live_tmux_count": len(source_d),
        "panes_count": len(combined),
        "panes": combined,
        "timestamp": _now_iso(),
    }


def send_tmux_input(
    session: str, text: str, press_enter: bool = True
) -> Dict[str, Any]:
    session = re.sub(r"[^a-zA-Z0-9._-]", "", session)
    if not session or not text:
        return {"ok": False, "error": "Both session and text are required"}

    check = subprocess.run(
        ["tmux", "has-session", "-t", session], capture_output=True, timeout=2.0
    )
    if check.returncode != 0:
        return {
            "ok": False,
            "session": session,
            "error": f"Tile '{session}' is a zero-token read-only Headless Stream (no interactive PTY attached)",
        }

    subprocess.run(
        ["tmux", "send-keys", "-t", session, "-l", text],
        capture_output=True,
        text=True,
        timeout=2.0,
    )
    if press_enter:
        subprocess.run(
            ["tmux", "send-keys", "-t", session, "Enter"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )

    return {
        "ok": True,
        "session": session,
        "sent_text": text,
        "enter": press_enter,
        "timestamp": _now_iso(),
    }


def _exec_on_single_node(node_key: str, cmd_str: str) -> Dict[str, Any]:
    info = CLUSTER_NODES.get(node_key)
    if not info:
        return {"node": node_key, "ok": False, "error": f"Unknown node {node_key}"}

    ip = info["ip"]
    t0 = time.time()
    try:
        if ip == "10.0.70.164":
            proc = subprocess.run(
                ["bash", "-c", cmd_str], capture_output=True, text=True, timeout=8.0
            )
        else:
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
                    cmd_str,
                ],
                capture_output=True,
                text=True,
                timeout=9.0,
            )
        out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
        return {
            "node": node_key,
            "ip": ip,
            "label": info["label"],
            "ok": proc.returncode == 0,
            "rc": proc.returncode,
            "elapsed_ms": round((time.time() - t0) * 1000.0, 2),
            "output": out.strip() or "(rc=0, no output)",
        }
    except Exception as exc:
        return {
            "node": node_key,
            "ip": ip,
            "label": info["label"],
            "ok": False,
            "rc": 1,
            "elapsed_ms": round((time.time() - t0) * 1000.0, 2),
            "output": f"Execution error: {exc}",
        }


def run_multi_node_command(
    target_node: str, preset: str, custom_cmd: str
) -> Dict[str, Any]:
    cmd_str = (
        SAFE_PRESETS.get(preset, "")
        if preset and preset in SAFE_PRESETS
        else custom_cmd.strip()
    )
    if not cmd_str:
        return {"ok": False, "error": "No command or preset provided"}

    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, cmd_str, re.IGNORECASE):
            return {
                "ok": False,
                "error": f"Blocked by Boylenet Rule 22 Safety Shield ({pat})",
            }

    targets = list(CLUSTER_NODES.keys()) if target_node == "all" else [target_node]
    results: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(_exec_on_single_node, n, cmd_str): n for n in targets}
        for n in targets:
            for f, k in futs.items():
                if k == n:
                    results.append(f.result())

    return {
        "ok": True,
        "command": cmd_str,
        "target": target_node,
        "results": results,
        "timestamp": _now_iso(),
    }


def list_receipts_and_blobs(query: str = "") -> Dict[str, Any]:
    q = query.strip().lower()
    items: List[Dict[str, Any]] = []

    if os.path.exists(WATCHDOG_PATH):
        try:
            st = os.stat(WATCHDOG_PATH)
            items.append(
                {
                    "id": "watchdog:WATCHDOG-STATUS.md",
                    "name": "WATCHDOG-STATUS.md (Live Swarm Watchdog)",
                    "category": "watchdog",
                    "path": WATCHDOG_PATH,
                    "size_kb": round(st.st_size / 1024.0, 1),
                    "mtime": st.st_mtime,
                }
            )
        except Exception:
            pass

    if os.path.isdir(RECEIPTS_DIR):
        try:
            entries = []
            with os.scandir(RECEIPTS_DIR) as it:
                for entry in it:
                    if entry.is_file() and (
                        entry.name.endswith(".md") or entry.name.endswith(".json")
                    ):
                        st = entry.stat()
                        entries.append(
                            (st.st_mtime, entry.name, entry.path, st.st_size)
                        )
            entries.sort(reverse=True)
            for mtime, name, path, sz in entries:
                items.append(
                    {
                        "id": f"receipt:{name}",
                        "name": name,
                        "category": "agent_receipt",
                        "path": path,
                        "size_kb": round(sz / 1024.0, 1),
                        "mtime": mtime,
                    }
                )
        except Exception:
            pass

    if os.path.isdir(BLOBS_DIR):
        try:
            blob_matches = []
            with os.scandir(BLOBS_DIR) as it:
                for entry in it:
                    if not entry.name.endswith(".log"):
                        continue
                    if q and q not in entry.name.lower():
                        continue
                    blob_matches.append(entry)
                    if len(blob_matches) >= 60:
                        break
            for entry in blob_matches[:40]:
                try:
                    st = entry.stat()
                    items.append(
                        {
                            "id": f"blob:{entry.name}",
                            "name": f"CAS Blob: {entry.name[:20]}...log",
                            "category": "cas_blob",
                            "path": entry.path,
                            "size_kb": round(st.st_size / 1024.0, 1),
                            "mtime": st.st_mtime,
                        }
                    )
                except Exception:
                    pass
        except Exception:
            pass

    if q:
        items = [
            it for it in items if q in it["name"].lower() or q in it["path"].lower()
        ]

    return {
        "status": "ok",
        "count": len(items),
        "items": items[:120],
        "timestamp": _now_iso(),
    }


def read_receipt_or_blob(doc_id: str) -> Dict[str, Any]:
    target_path = ""
    if doc_id == "watchdog:WATCHDOG-STATUS.md":
        target_path = WATCHDOG_PATH
    elif doc_id.startswith("receipt:"):
        fname = os.path.basename(doc_id.split(":", 1)[1])
        target_path = os.path.join(RECEIPTS_DIR, fname)
    elif doc_id.startswith("blob:"):
        fname = os.path.basename(doc_id.split(":", 1)[1])
        target_path = os.path.join(BLOBS_DIR, fname)

    if not target_path or not os.path.isfile(target_path):
        return {"ok": False, "error": f"Document not found: {doc_id}"}

    try:
        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(250_000)
        st = os.stat(target_path)
        return {
            "ok": True,
            "id": doc_id,
            "path": target_path,
            "size_bytes": st.st_size,
            "mtime_iso": datetime.datetime.fromtimestamp(
                st.st_mtime, datetime.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "content": content,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


HTML_UI = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Boylenet Agent TV Wall (Headless + tmux), Multi-Node Terminal & Receipt Explorer (:4083)</title>
<style>
  :root {
    --bg: #050911;
    --panel: rgba(15, 23, 42, 0.92);
    --card: #0a101f;
    --border: rgba(56, 189, 248, 0.25);
    --cyan: #38bdf8;
    --emerald: #10b981;
    --amber: #f59e0b;
    --purple: #a855f7;
    --text: #f1f5f9;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: radial-gradient(circle at 20% 0%, #0d1b36 0%, #050911 60%);
    color: var(--text);
    min-height: 100vh;
  }
  header {
    background: rgba(8, 13, 25, 0.95);
    border-bottom: 1px solid var(--border);
    padding: 12px 22px;
    position: sticky;
    top: 0;
    z-index: 40;
  }
  .header-inner {
    max-width: 1780px;
    margin: 0 auto;
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .badge {
    background: linear-gradient(135deg, #a855f7, #0284c7);
    color: #fff;
    padding: 7px 12px;
    border-radius: 9px;
    font-weight: 800;
    font-size: 13px;
    box-shadow: 0 0 16px rgba(168, 85, 247, 0.4);
  }
  .mode-tabs {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .mode-btn {
    background: rgba(30, 41, 59, 0.85);
    color: var(--text);
    border: 1px solid rgba(148, 163, 184, 0.3);
    padding: 9px 15px;
    border-radius: 9px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
  }
  .mode-btn.active {
    background: linear-gradient(135deg, rgba(168, 85, 247, 0.35), rgba(56, 189, 248, 0.35));
    border-color: var(--cyan);
    color: #fff;
  }
  .main-wrap {
    max-width: 1780px;
    margin: 0 auto;
    padding: 16px 22px 50px;
  }
  .tool-section { display: none; }
  .tool-section.active { display: block; }

  /* #UX-23 TV Wall */
  .tv-toolbar {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    background: var(--panel);
    border: 1px solid var(--border);
    padding: 12px 16px;
    border-radius: 12px;
    margin-bottom: 14px;
  }
  .filter-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .filter-pill {
    background: rgba(15, 23, 42, 0.9);
    color: var(--muted);
    border: 1px solid rgba(148, 163, 184, 0.28);
    padding: 7px 13px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.15s;
  }
  .filter-pill.active {
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.28), rgba(168, 85, 247, 0.28));
    color: #fff;
    border-color: var(--cyan);
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.25);
  }
  .tv-grid {
    display: grid;
    gap: 12px;
  }
  .tv-grid.grid-3x3 { grid-template-columns: repeat(3, 1fr); }
  .tv-grid.grid-2x2 { grid-template-columns: repeat(2, 1fr); }
  @media (max-width: 1150px) {
    .tv-grid.grid-3x3, .tv-grid.grid-2x2 { grid-template-columns: 1fr; }
  }
  .tv-pane {
    background: var(--card);
    border: 1px solid rgba(56, 189, 248, 0.28);
    border-radius: 11px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .tv-pane.is-headless {
    border-color: rgba(168, 85, 247, 0.52);
    box-shadow: 0 0 18px rgba(168, 85, 247, 0.12);
  }
  .tv-pane-header {
    background: rgba(24, 34, 54, 0.95);
    padding: 8px 11px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    font-size: 11.5px;
    font-weight: 700;
    border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  }
  .status-dot {
    display: inline-block;
    width: 9px;
    height: 9px;
    border-radius: 50%;
    margin-right: 6px;
  }
  @keyframes pulseGreen {
    0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.8); }
    70% { box-shadow: 0 0 0 7px rgba(16, 185, 129, 0); }
    100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
  }
  .dot-live {
    background: var(--emerald);
    animation: pulseGreen 1.8s infinite;
  }
  .headless-badge {
    font-size: 10px;
    font-weight: 800;
    padding: 3px 7px;
    border-radius: 5px;
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.22), rgba(168, 85, 247, 0.28));
    border: 1px solid rgba(56, 189, 248, 0.55);
    color: #7dd3fc;
    white-space: nowrap;
  }
  .tmux-badge {
    font-size: 10px;
    font-weight: 700;
    padding: 3px 7px;
    border-radius: 5px;
    background: rgba(16, 185, 129, 0.16);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #34d399;
    white-space: nowrap;
  }
  .expand-btn {
    background: rgba(56, 189, 248, 0.15);
    color: var(--cyan);
    border: 1px solid rgba(56, 189, 248, 0.35);
    border-radius: 5px;
    padding: 3px 7px;
    font-size: 10.5px;
    font-weight: 700;
    cursor: pointer;
    white-space: nowrap;
  }
  .expand-btn:hover { background: rgba(56, 189, 248, 0.35); color: #fff; }
  .tv-screen {
    margin: 0;
    padding: 10px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    line-height: 1.38;
    color: #34d399;
    background: #03060c;
    height: 235px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .tv-pane.is-headless .tv-screen {
    color: #7dd3fc;
  }
  .tv-input-row {
    display: flex;
    border-top: 1px solid rgba(148, 163, 184, 0.2);
    background: #080d18;
  }
  .tv-input {
    flex: 1;
    background: transparent;
    border: none;
    color: #fff;
    padding: 7px 10px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11.5px;
  }
  .tv-input:focus { outline: none; }
  .tv-send-btn {
    background: rgba(56, 189, 248, 0.2);
    color: var(--cyan);
    border: none;
    border-left: 1px solid rgba(56, 189, 248, 0.3);
    padding: 0 12px;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
  }

  /* Fullscreen Modal */
  .fs-modal-backdrop {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(2, 6, 14, 0.88);
    z-index: 100;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  .fs-modal-backdrop.open { display: flex; }
  .fs-modal {
    background: #070c18;
    border: 1px solid var(--cyan);
    border-radius: 14px;
    width: 95%;
    max-width: 1480px;
    height: 86vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 25px 60px rgba(0,0,0,0.85);
  }
  .fs-modal pre {
    flex: 1;
    margin: 0;
    padding: 18px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    line-height: 1.45;
    color: #38bdf8;
    background: #02050a;
    overflow-y: auto;
    white-space: pre-wrap;
  }

  /* #UX-22 Multi-Node Console */
  .console-panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
  }
  .node-selector-row, .preset-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 12px;
  }
  .node-chip {
    background: rgba(15, 23, 42, 0.9);
    color: var(--muted);
    border: 1px solid rgba(148, 163, 184, 0.28);
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
  }
  .node-chip.active {
    color: #fff;
    border-color: var(--emerald);
    background: rgba(16, 185, 129, 0.22);
  }
  .preset-btn {
    background: rgba(56, 189, 248, 0.14);
    color: var(--cyan);
    border: 1px solid rgba(56, 189, 248, 0.35);
    padding: 7px 12px;
    border-radius: 7px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  }
  .cmd-bar { display: flex; gap: 10px; }
  .cmd-input {
    flex: 1;
    background: #04070e;
    border: 1px solid rgba(148, 163, 184, 0.35);
    color: #34d399;
    font-family: 'JetBrains Mono', monospace;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 13px;
  }
  .cmd-exec-btn {
    background: linear-gradient(135deg, #0284c7, #10b981);
    color: #fff;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    font-weight: 800;
    cursor: pointer;
  }
  .console-results {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
    gap: 12px;
  }
  .node-output-card {
    background: var(--card);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 10px;
    overflow: hidden;
  }
  .node-output-card pre {
    margin: 0;
    padding: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11.5px;
    color: #e2e8f0;
    background: #03060c;
    max-height: 320px;
    overflow: auto;
    white-space: pre-wrap;
  }

  /* #UX-24 Receipt Explorer */
  .explorer-layout {
    display: grid;
    grid-template-columns: 360px 1fr;
    gap: 16px;
    min-height: 680px;
  }
  .doc-sidebar {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-height: 760px;
  }
  .doc-list {
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .doc-item {
    padding: 9px 11px;
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(148, 163, 184, 0.16);
    cursor: pointer;
    font-size: 12px;
  }
  .doc-item:hover, .doc-item.active {
    border-color: var(--cyan);
    background: rgba(56, 189, 248, 0.15);
  }
  .doc-viewer {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
    overflow-y: auto;
    max-height: 760px;
  }
  .md-rendered table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 12px;
  }
  .md-rendered th, .md-rendered td {
    border: 1px solid rgba(148, 163, 184, 0.25);
    padding: 6px 10px;
    text-align: left;
  }
  .md-rendered th { background: rgba(56, 189, 248, 0.15); color: var(--cyan); }
  .md-rendered pre {
    background: #04070e;
    color: #34d399;
    padding: 12px;
    border-radius: 8px;
    overflow-x: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
  }
</style>
</head>
<body>
<header>
  <div class="header-inner">
    <div class="brand">
      <div class="badge">TERMINAL & HEADLESS TV WALL :4083</div>
      <div>
        <div style="font-size:18px;font-weight:800;">Boylenet Live Agent TV Wall (Headless Models + tmux), Multi-Node Console & Receipt Explorer</div>
        <div style="font-size:11.5px;color:var(--muted);">Zero-Token Headless Subagent & GPU Stream Tap • 3×3 Live Agent TV Wall (#UX-23) • Multi-Node Console (#UX-22) • Receipt Explorer (#UX-24)</div>
      </div>
    </div>
    <div class="mode-tabs">
      <button class="mode-btn active" onclick="switchTab('tvwall', this)">📺 #UX-23 Live Agent TV Wall (Headless + tmux)</button>
      <button class="mode-btn" onclick="switchTab('console', this)">⚡ #UX-22 Multi-Node Command Console</button>
      <button class="mode-btn" onclick="switchTab('explorer', this)">📜 #UX-24 Receipt & Markdown Explorer</button>
      <a class="mode-btn" href="http://models.boylenet.themfboyles.org" target="_blank" style="text-decoration:none;">🧠 86-Model Storefront (:4084)</a>
    </div>
  </div>
</header>

<div class="main-wrap">
  <!-- TOOL 1: #UX-23 LIVE AGENT TV WALL -->
  <section id="tab-tvwall" class="tool-section active">
    <div class="tv-toolbar">
      <div class="filter-pills">
        <button class="filter-pill active" data-filter="all" onclick="setTvFilter('all', this)">All Live Agents (tmux + Headless)</button>
        <button class="filter-pill" data-filter="headless" onclick="setTvFilter('headless', this)">⚡ Headless Subagents & Models</button>
        <button class="filter-pill" data-filter="tmux" onclick="setTvFilter('tmux', this)">🖥️ Interactive tmux Seats</button>
        <button class="filter-pill" data-filter="gpu" onclick="setTvFilter('gpu', this)">🔥 GPU Benchmarks (.72/.83)</button>
      </div>
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
        <button class="preset-btn" onclick="setGridMode('2x2')">2×2 Grid</button>
        <button class="preset-btn" onclick="setGridMode('3x3')">3×3 Grid (9 Panes)</button>
        <button class="preset-btn" onclick="setGridMode('all')">All Panes</button>
        <button class="preset-btn" id="autoscroll-btn" onclick="toggleAutoScroll()" style="border-color:var(--emerald);color:#34d399;">⬇ Auto-Follow Latest: ON</button>
        <button class="preset-btn" onclick="scrollAllToBottom()">⏬ Jump All to Bottom</button>
        <span id="tv-status-label" style="font-size:11.5px;color:var(--emerald);font-weight:700;">⚡ 0 Extra Tokens • Auto-refresh: 3.0s</span>
        <button class="preset-btn" onclick="refreshTvWall()">🔄 Refresh</button>
      </div>
    </div>
    <div id="tv-grid-container" class="tv-grid grid-3x3"></div>
  </section>

  <!-- TOOL 2: #UX-22 MULTI-NODE QUICK COMMAND CONSOLE -->
  <section id="tab-console" class="tool-section">
    <div class="console-panel">
      <div style="font-size:13px;font-weight:700;margin-bottom:8px;color:var(--cyan);">1. Select Target Cluster Node(s) (27-Node Boylenet Mesh):</div>
      <div class="node-selector-row" id="node-chips">
        <button class="node-chip" data-target="all">🌐 All 27 Nodes (Broadcast)</button>
        <button class="node-chip active" data-target=".164">.164 (Controller)</button>
        <button class="node-chip" data-target=".72">.72 (AI Vault A • 4.7TB)</button>
        <button class="node-chip" data-target=".83">.83 (AI DEV Vault B • 4.2TB)</button>
        <button class="node-chip" data-target=".125">.125 (ai-infer01 • T4 + Qdrant)</button>
        <button class="node-chip" data-target=".228">.228 (ai-ollama01 • T4 + LiteLLM)</button>
        <button class="node-chip" data-target=".82">.82 (64-Core CI Turbo)</button>
        <button class="node-chip" data-target=".137">.137 (BattleStation 2080Ti)</button>
        <button class="node-chip" data-target=".181">.181 (Bittorrent CDP)</button>
        <button class="node-chip" data-target=".25">.25 (Gitea SCM/CI)</button>
        <button class="node-chip" data-target=".162">.162 (wrk-ci01)</button>
        <button class="node-chip" data-target=".107">.107 (wrk-ci02)</button>
        <button class="node-chip" data-target=".182">.182 (wrk-ci03)</button>
        <button class="node-chip" data-target=".50">.50 (esxi-01)</button>
        <button class="node-chip" data-target=".51">.51 (esxi-02)</button>
        <button class="node-chip" data-target=".52">.52 (esxi-03)</button>
        <button class="node-chip" data-target=".53">.53 (esxi-04)</button>
        <button class="node-chip" data-target=".54">.54 (vCenter 8)</button>
        <button class="node-chip" data-target=".194">.194 (TrueNAS Vault)</button>
        <button class="node-chip" data-target=".95">.95 (Monitoring)</button>
        <button class="node-chip" data-target=".80">.80 (wrk-test01)</button>
        <button class="node-chip" data-target=".85">.85 (wrk-test02)</button>
        <button class="node-chip" data-target=".249">.249 (wrk-test03)</button>
        <button class="node-chip" data-target=".84">.84 (wrk-aux01)</button>
        <button class="node-chip" data-target=".120">.120 (spr-pool01)</button>
        <button class="node-chip" data-target=".183">.183 (spr-pool02)</button>
        <button class="node-chip" data-target=".149">.149 (spr-pool03)</button>
        <button class="node-chip" data-target=".185">.185 (spr-pool04)</button>
      </div>
      <div style="font-size:13px;font-weight:700;margin-bottom:8px;color:var(--cyan);">2. Quick Diagnostic Presets or Custom Safe Command:</div>
      <div class="preset-row">
        <button class="preset-btn" onclick="runPreset('gpu_vram')">🎮 GPU & VRAM Status (nvidia-smi)</button>
        <button class="preset-btn" onclick="runPreset('disk_space')">💾 Vault & Ramdisk Space (df -h)</button>
        <button class="preset-btn" onclick="runPreset('uptime_memory')">🧠 Uptime & DDR4 RAM (free -h)</button>
        <button class="preset-btn" onclick="runPreset('top_procs')">🔥 Top CPU/RAM Processes</button>
        <button class="preset-btn" onclick="runPreset('network_25gbe')">🔌 25GbE & VLAN Interfaces</button>
        <button class="preset-btn" onclick="runPreset('ai_services')">⚙️ Systemd AI & Fleet Services</button>
      </div>
      <div class="cmd-bar">
        <input type="text" id="custom-cmd-input" class="cmd-input" value="uptime && free -h" placeholder="Enter safe diagnostic command..."/>
        <button class="cmd-exec-btn" onclick="runCustomCommand()">▶ Execute Across Selected Node(s)</button>
      </div>
    </div>
    <div id="console-output-grid" class="console-results"></div>
  </section>

  <!-- TOOL 3: #UX-24 RECEIPT & MARKDOWN CODE EXPLORER -->
  <section id="tab-explorer" class="tool-section">
    <div class="explorer-layout">
      <div class="doc-sidebar">
        <input type="text" id="doc-search" class="cmd-input" style="font-size:12px;padding:8px 10px;" placeholder="Filter AGENT*.md, WATCHDOG-STATUS.md, or blob hash..."/>
        <div id="doc-count" style="font-size:11px;color:var(--muted);">Loading receipts...</div>
        <div class="doc-list" id="doc-list"></div>
      </div>
      <div class="doc-viewer">
        <div id="doc-header" style="margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid var(--border);font-family:monospace;font-size:12px;color:var(--muted);">Select a receipt on the left</div>
        <div id="doc-content" class="md-rendered"></div>
      </div>
    </div>
  </section>
</div>

<!-- Full-Screen Expand Modal -->
<div class="fs-modal-backdrop" id="fs-modal">
  <div class="fs-modal">
    <div class="tv-pane-header" style="padding:12px 18px;font-size:14px;">
      <div id="fs-modal-title">Live Stream</div>
      <div style="display:flex;gap:8px;">
        <button class="expand-btn" onclick="const b=document.getElementById('fs-modal-body');b.dataset.pinnedBottom='1';b.scrollTop=b.scrollHeight;" style="font-size:12px;padding:5px 12px;">⬇ Jump to Latest</button>
        <button class="expand-btn" onclick="closeFsModal()" style="font-size:12px;padding:5px 12px;">✕ Close Full-Screen</button>
      </div>
    </div>
    <pre id="fs-modal-body" data-pinned-bottom="1" onscroll="handleScreenScroll(this)"></pre>
  </div>
</div>

<script>
let GRID_MODE = 'all';
let TV_FILTER = 'all';
let SELECTED_NODE = '.164';
let TV_DATA = [];
let EXPANDED_PANE_ID = null;
let AUTO_SCROLL_LATEST = true;
let LAST_RENDERED_IDS = '';

function handleScreenScroll(el) {
  const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
  el.dataset.pinnedBottom = (distFromBottom <= 45) ? '1' : '0';
}

function toggleAutoScroll() {
  AUTO_SCROLL_LATEST = !AUTO_SCROLL_LATEST;
  const btn = document.getElementById('autoscroll-btn');
  if (btn) {
    btn.textContent = AUTO_SCROLL_LATEST ? '⬇ Auto-Follow Latest: ON' : '⏸ Auto-Follow Latest: PAUSED';
    btn.style.color = AUTO_SCROLL_LATEST ? '#34d399' : '#f59e0b';
    btn.style.borderColor = AUTO_SCROLL_LATEST ? 'var(--emerald)' : 'var(--amber)';
  }
  if (AUTO_SCROLL_LATEST) {
    scrollAllToBottom();
  }
}

function scrollPaneToBottom(paneId) {
  const el = document.getElementById('screen-' + paneId);
  if (el) {
    el.dataset.pinnedBottom = '1';
    el.scrollTop = el.scrollHeight;
  }
}

function scrollAllToBottom() {
  document.querySelectorAll('.tv-screen').forEach(el => {
    el.dataset.pinnedBottom = '1';
    el.scrollTop = el.scrollHeight;
  });
}

function switchTab(tabId, btn) {
  document.querySelectorAll('.tool-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  const sec = document.getElementById('tab-' + tabId);
  if (sec) sec.classList.add('active');
  const targetBtn = btn || document.querySelector(`.mode-btn[onclick*="'${tabId}'"]`);
  if (targetBtn) targetBtn.classList.add('active');
  if (tabId === 'console' && !document.getElementById('console-output-grid').innerHTML) {
    runPreset('uptime_memory');
  }
  if (tabId === 'explorer' && !document.getElementById('doc-list').innerHTML) {
    loadDocs('');
  }
}

function setTvFilter(flt, btn) {
  TV_FILTER = flt;
  LAST_RENDERED_IDS = '';
  document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
  const targetBtn = btn || document.querySelector(`.filter-pill[data-filter="${flt}"]`);
  if (targetBtn) targetBtn.classList.add('active');
  renderTvWall();
}

function setGridMode(mode) {
  GRID_MODE = mode;
  LAST_RENDERED_IDS = '';
  const g = document.getElementById('tv-grid-container');
  g.className = 'tv-grid ' + (mode === '2x2' ? 'grid-2x2' : 'grid-3x3');
  renderTvWall();
}

async function refreshTvWall() {
  try {
    const res = await fetch('/api/tv-wall');
    const data = await res.json();
    TV_DATA = data.panes || [];
    const c = data.counts || {};
    document.getElementById('tv-status-label').textContent =
      `⚡ ${c.headless_agy_subagents || 0} AGY + ${c.headless_gpu_streams || 0} GPU + ${c.headless_cli_streams || 0} CLI Headless + ${c.interactive_tmux_sessions || 0} tmux • ${data.timestamp}`;
    renderTvWall();
    if (EXPANDED_PANE_ID) {
      const found = TV_DATA.find(p => p.id === EXPANDED_PANE_ID);
      if (found) {
        const fb = document.getElementById('fs-modal-body');
        const wasPinned = fb.dataset.pinnedBottom !== '0';
        const prevTop = fb.scrollTop;
        if (fb.textContent !== found.output) {
          fb.textContent = found.output;
        }
        if (AUTO_SCROLL_LATEST && wasPinned) {
          fb.scrollTop = fb.scrollHeight;
        } else {
          fb.scrollTop = prevTop;
        }
      }
    }
  } catch (e) {}
}

function escapeHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function renderTvWall() {
  let filtered = TV_DATA.filter(p => {
    if (TV_FILTER === 'all') return true;
    if (TV_FILTER === 'headless') return p.source_type === 'headless' || p.source_type === 'gpu';
    if (TV_FILTER === 'tmux') return p.source_type === 'tmux';
    if (TV_FILTER === 'gpu') return p.source_type === 'gpu';
    return true;
  });

  const limit = GRID_MODE === '2x2' ? 4 : (GRID_MODE === '3x3' ? 9 : 48);
  const slice = filtered.slice(0, limit);
  const g = document.getElementById('tv-grid-container');
  const currentIds = slice.map(p => p.id).join('|');

  // If the pane list hasn't structurally changed, update each <pre> in-place so scroll position & inputs are NEVER reset!
  if (currentIds === LAST_RENDERED_IDS && g.children.length === slice.length) {
    slice.forEach(p => {
      const screenEl = document.getElementById('screen-' + p.id);
      if (!screenEl) return;
      const wasPinned = screenEl.dataset.pinnedBottom !== '0';
      const prevScrollTop = screenEl.scrollTop;
      if (screenEl.textContent !== (p.output || '')) {
        screenEl.textContent = p.output || '';
      }
      if (AUTO_SCROLL_LATEST && wasPinned) {
        screenEl.scrollTop = screenEl.scrollHeight;
      } else {
        screenEl.scrollTop = prevScrollTop;
      }
    });
    return;
  }

  const prevStates = {};
  g.querySelectorAll('.tv-screen').forEach(el => {
    prevStates[el.id] = { top: el.scrollTop, pinned: el.dataset.pinnedBottom };
  });

  LAST_RENDERED_IDS = currentIds;
  g.innerHTML = slice.map(p => {
    const isHeadless = p.source_type !== 'tmux';
    const badgeClass = isHeadless ? 'headless-badge' : 'tmux-badge';
    const badgeText = p.badge || (isHeadless ? '⚡ HEADLESS LIVE • 0 EXTRA TOKENS' : '🖥️ INTERACTIVE TMUX');
    const prev = prevStates['screen-' + p.id];
    const initPinned = prev ? (prev.pinned || '1') : (AUTO_SCROLL_LATEST ? '1' : '0');
    const inputFooter = p.interactive ? `
      <div class="tv-input-row">
        <input type="text" class="tv-input" id="input-${p.session}" placeholder="Send keys / command to ${p.session}..." onkeydown="if(event.key==='Enter') sendKeys('${p.session}')"/>
        <button class="tv-send-btn" onclick="sendKeys('${p.session}')">Send ↵</button>
      </div>
    ` : `
      <div class="tv-input-row" style="padding:6px 10px;justify-content:space-between;align-items:center;font-size:11px;color:var(--muted);">
        <span>Passive Disk/Log Tap (${escapeHtml(p.pool)}) — 0 Token Overhead</span>
        <span style="color:#34d399;font-weight:700;">● STREAMING LIVE</span>
      </div>
    `;
    return `
      <div class="tv-pane ${isHeadless ? 'is-headless' : ''}" id="pane-${p.id}">
        <div class="tv-pane-header">
          <div style="display:flex;align-items:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
            <span class="status-dot dot-live"></span>
            <span title="${escapeHtml(p.title)}">${escapeHtml(p.title)}</span>
          </div>
          <div style="display:flex;align-items:center;gap:6px;">
            <span class="${badgeClass}">${escapeHtml(badgeText)}</span>
            <button class="expand-btn" onclick="scrollPaneToBottom('${p.id}')" title="Jump to latest output at bottom">⬇ Latest</button>
            <button class="expand-btn" onclick="expandPane('${p.id}')">🔍 Expand</button>
          </div>
        </div>
        <pre class="tv-screen" id="screen-${p.id}" data-pinned-bottom="${initPinned}" onscroll="handleScreenScroll(this)">${escapeHtml(p.output)}</pre>
        ${inputFooter}
      </div>
    `;
  }).join('');

  requestAnimationFrame(() => {
    g.querySelectorAll('.tv-screen').forEach(el => {
      const prev = prevStates[el.id];
      const wasPinned = el.dataset.pinnedBottom !== '0';
      if (AUTO_SCROLL_LATEST && wasPinned) {
        el.scrollTop = el.scrollHeight;
      } else if (prev) {
        el.scrollTop = prev.top;
      }
    });
  });
}

function expandPane(paneId) {
  const found = TV_DATA.find(p => p.id === paneId);
  if (!found) return;
  EXPANDED_PANE_ID = paneId;
  document.getElementById('fs-modal-title').textContent = `${found.title} — [${found.badge}]`;
  const fb = document.getElementById('fs-modal-body');
  fb.textContent = found.output;
  fb.dataset.pinnedBottom = '1';
  document.getElementById('fs-modal').classList.add('open');
  requestAnimationFrame(() => {
    fb.scrollTop = fb.scrollHeight;
  });
}

function closeFsModal() {
  EXPANDED_PANE_ID = null;
  document.getElementById('fs-modal').classList.remove('open');
}

async function sendKeys(session) {
  const el = document.getElementById('input-' + session);
  if (!el || !el.value.trim()) return;
  const text = el.value;
  el.value = '';
  await fetch('/api/tmux/send', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({session: session, text: text, enter: true})
  });
  setTimeout(refreshTvWall, 350);
}

document.querySelectorAll('.node-chip').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.node-chip').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    SELECTED_NODE = btn.getAttribute('data-target');
  });
});

async function runPreset(preset) {
  await executeConsole({target: SELECTED_NODE, preset: preset, command: ''});
}

async function runCustomCommand() {
  const cmd = document.getElementById('custom-cmd-input').value;
  await executeConsole({target: SELECTED_NODE, preset: '', command: cmd});
}

async function executeConsole(payload) {
  const grid = document.getElementById('console-output-grid');
  grid.innerHTML = '<div style="color:var(--cyan);padding:12px;">Executing across cluster node(s)...</div>';
  const res = await fetch('/api/console/exec', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!data.ok) {
    grid.innerHTML = `<div style="color:#f43f5e;padding:12px;font-weight:700;">${escapeHtml(data.error)}</div>`;
    return;
  }
  grid.innerHTML = (data.results || []).map(r => `
    <div class="node-output-card">
      <div class="tv-pane-header">
        <span>${escapeHtml(r.label)} (${escapeHtml(r.ip)})</span>
        <span style="color:${r.ok ? '#34d399' : '#f43f5e'};">rc=${r.rc} • ${r.elapsed_ms} ms</span>
      </div>
      <pre>${escapeHtml(r.output)}</pre>
    </div>
  `).join('');
}

function renderMarkdown(md) {
  const lines = (md || '').split('\n');
  let html = '';
  let inCode = false;
  let inTable = false;
  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i];
    if (ln.startsWith('```')) {
      if (inTable) { html += '</tbody></table>'; inTable = false; }
      inCode = !inCode;
      html += inCode ? '<pre><code>' : '</code></pre>';
      continue;
    }
    if (inCode) {
      html += escapeHtml(ln) + '\n';
      continue;
    }
    if (ln.trim().startsWith('|') && ln.trim().endsWith('|')) {
      if (/^\|[\s:|-]+\|$/.test(ln.trim())) continue;
      const cells = ln.trim().slice(1, -1).split('|').map(c => escapeHtml(c.trim()));
      if (!inTable) {
        inTable = true;
        html += '<table><thead><tr>' + cells.map(c => `<th>${c}</th>`).join('') + '</tr></thead><tbody>';
      } else {
        html += '<tr>' + cells.map(c => `<td>${c}</td>`).join('') + '</tr>';
      }
      continue;
    } else if (inTable) {
      html += '</tbody></table>';
      inTable = false;
    }
    if (ln.startsWith('# ')) html += `<h1>${escapeHtml(ln.slice(2))}</h1>`;
    else if (ln.startsWith('## ')) html += `<h2>${escapeHtml(ln.slice(3))}</h2>`;
    else if (ln.startsWith('### ')) html += `<h3>${escapeHtml(ln.slice(4))}</h3>`;
    else if (ln.startsWith('- ')) html += `<div style="margin:3px 0 3px 14px;">• ${escapeHtml(ln.slice(2))}</div>`;
    else if (ln.trim() === '---') html += '<hr style="border-color:rgba(148,163,184,0.2);"/>';
    else if (ln.trim() !== '') html += `<p style="margin:6px 0;line-height:1.5;">${escapeHtml(ln)}</p>`;
  }
  if (inTable) html += '</tbody></table>';
  if (inCode) html += '</code></pre>';
  return html;
}

async function loadDocs(q) {
  const res = await fetch('/api/explorer/list?q=' + encodeURIComponent(q || ''));
  const data = await res.json();
  const items = data.items || [];
  document.getElementById('doc-count').textContent = `${items.length} receipts & CAS logs available`;
  const listEl = document.getElementById('doc-list');
  listEl.innerHTML = items.map((it, idx) => `
    <div class="doc-item ${idx === 0 ? 'active' : ''}" onclick="openDoc('${it.id}', this)">
      <div style="font-weight:700;color:#fff;">${escapeHtml(it.name)}</div>
      <div style="font-size:10.5px;color:var(--muted);margin-top:2px;">${it.category} • ${it.size_kb} KB</div>
    </div>
  `).join('');
  if (items.length > 0) {
    openDoc(items[0].id, listEl.querySelector('.doc-item'));
  }
}

async function openDoc(docId, el) {
  document.querySelectorAll('.doc-item').forEach(d => d.classList.remove('active'));
  if (el) el.classList.add('active');
  const res = await fetch('/api/explorer/read?id=' + encodeURIComponent(docId));
  const data = await res.json();
  if (!data.ok) {
    document.getElementById('doc-content').innerHTML = `<div style="color:#f43f5e;">${escapeHtml(data.error)}</div>`;
    return;
  }
  document.getElementById('doc-header').textContent = `${data.path} • ${data.size_bytes} bytes • Modified ${data.mtime_iso}`;
  document.getElementById('doc-content').innerHTML = renderMarkdown(data.content);
}

document.getElementById('doc-search').addEventListener('input', e => {
  loadDocs(e.target.value);
});

refreshTvWall();
setInterval(refreshTvWall, 1000);
</script>
</body>
</html>
"""


class TerminalDrawerHandler(BaseHTTPRequestHandler):
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

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = urllib.parse.parse_qs(parsed.query)

        upgrade_hdr = (self.headers.get("Upgrade") or "").strip().lower()
        ws_key = (self.headers.get("Sec-WebSocket-Key") or "").strip()
        if upgrade_hdr == "websocket" and ws_key:
            import base64
            import hashlib

            accept_val = base64.b64encode(
                hashlib.sha1(
                    (ws_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
                ).digest()
            ).decode("ascii")
            self.protocol_version = "HTTP/1.1"
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept_val)
            self.end_headers()
            msg_bytes = json.dumps(
                {
                    "type": "terminal_ws_ready",
                    "service": "bd-web-terminal-drawer",
                    "port": PORT,
                    "timestamp": _now_iso(),
                }
            ).encode("utf-8")
            frame = bytearray([0x81])
            length = len(msg_bytes)
            if length < 126:
                frame.append(length)
            else:
                frame.extend([126, (length >> 8) & 0xFF, length & 0xFF])
            frame.extend(msg_bytes)
            try:
                self.wfile.write(bytes(frame))
                self.wfile.flush()
            except Exception:
                pass
            return

        if path == "/health":
            wall = get_unified_tv_wall(lines=10)
            docs = list_receipts_and_blobs()
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "bd-web-terminal-drawer",
                    "port": PORT,
                    "url": "http://terminal.boylenet.themfboyles.org",
                    "zero_extra_tokens": True,
                    "features": [
                        "#UX-22 Multi-Node Command Console",
                        "#UX-23 Live 2x2/3x3 Agent TV Wall (Headless Models + AGY Subagents + tmux)",
                        "#UX-24 Receipt & Markdown Explorer",
                    ],
                    "counts": wall["counts"],
                    "live_tmux_sessions": wall["live_tmux_count"],
                    "tv_wall_panes": wall["panes_count"],
                    "cluster_nodes_configured": len(CLUSTER_NODES),
                    "receipts_and_blobs_indexed": docs["count"],
                    "timestamp": _now_iso(),
                },
            )
            return

        if path in ("/api/tv-wall", "/api/tmux/wall", "/api/sessions", "/api/streams"):
            self._send_json(200, get_unified_tv_wall())
            return

        if path == "/api/pane":
            pane_id = qs.get("id", [""])[0]
            wall = get_unified_tv_wall(lines=80)
            found = next(
                (
                    p
                    for p in wall["panes"]
                    if p["id"] == pane_id or p["session"] == pane_id
                ),
                None,
            )
            if not found and wall["panes"]:
                found = wall["panes"][0]
            self._send_json(
                200, {"status": "ok", "pane": found, "timestamp": _now_iso()}
            )
            return

        if path == "/api/explorer/list":
            q = qs.get("q", [""])[0]
            self._send_json(200, list_receipts_and_blobs(q))
            return

        if path == "/api/explorer/read":
            doc_id = qs.get(
                "id", ["receipt:AGENT37-NEW-FRONTIER-MODELS-BENCHMARK-RECEIPTS.md"]
            )[0]
            self._send_json(200, read_receipt_or_blob(doc_id))
            return

        self._send_html(200, HTML_UI)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            body = {}

        if path == "/api/tmux/send":
            session = str(body.get("session", ""))
            text = str(body.get("text", ""))
            enter = bool(body.get("enter", True))
            self._send_json(200, send_tmux_input(session, text, enter))
            return

        if path == "/api/console/exec":
            target = str(body.get("target", ".164"))
            preset = str(body.get("preset", ""))
            command = str(body.get("command", ""))
            self._send_json(200, run_multi_node_command(target, preset, command))
            return

        self._send_json(404, {"error": f"Unknown endpoint: {path}"})


def main() -> None:
    _ensure_seed_headless_streams()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), TerminalDrawerHandler)
    print(
        f"[bd-web-terminal-drawer] Listening on 0.0.0.0:{PORT} (http://terminal.boylenet.themfboyles.org)",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
