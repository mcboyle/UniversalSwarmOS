#!/usr/bin/env python3
"""
bd-telemetry-daemon.py -- Autonomous Deterministic Fleet Telemetry & Heartbeat Daemon.
Replaces generative LLM polling loops (Haiku / Terra status & triage seats) with
pure 0-token deterministic measurement. Writes live state to disk and alerts on anomalies.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

STATUS_TXT = Path("/home/mboyle/bd-persist/STATUS.txt")
LIVE_JSON = Path("/home/mboyle/bd-persist/accounting/fleet_telemetry_live.json")
ALERTS_LOG = Path("/home/mboyle/bd-persist/accounting/alerts.log")
USAGE_DB = Path("/home/mboyle/bd-persist/accounting/usage.sqlite")
BULK_DOWNLOADER = Path("/home/mboyle/BulkDownloader")
SWARM_OS = Path("/home/mboyle/UniversalSwarmOS")


def get_git_state(repo_path: Path) -> Dict[str, Any]:
    """Inspect repository status without modifying working trees."""
    if not (repo_path / ".git").exists():
        return {"exists": False, "clean": True, "head": "N/A", "branch": "N/A"}
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=repo_path, stderr=subprocess.DEVNULL, text=True
        ).strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path, stderr=subprocess.DEVNULL, text=True
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo_path, stderr=subprocess.DEVNULL, text=True
        ).strip()
        return {
            "exists": True,
            "head": head,
            "branch": branch,
            "clean": len(status) == 0,
            "dirty_count": len(status.splitlines()) if status else 0,
        }
    except Exception as e:
        return {"exists": True, "error": str(e), "clean": False}


def get_system_metrics() -> Dict[str, Any]:
    """Gather host CPU, RAM, and Disk metrics."""
    # Load avg
    load1, load5, load15 = os.getloadavg()
    # Memory
    mem_total = 0
    mem_avail = 0
    if os.path.exists("/proc/meminfo"):
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1]) // 1024
                elif line.startswith("MemAvailable:"):
                    mem_avail = int(line.split()[1]) // 1024
    mem_used = mem_total - mem_avail
    mem_pct = round(100.0 * mem_used / max(mem_total, 1), 1)

    # Disk
    du_home = shutil.disk_usage("/home/mboyle")
    disk_pct = round(100.0 * du_home.used / max(du_home.total, 1), 1)

    return {
        "load_1m": round(load1, 2),
        "load_5m": round(load5, 2),
        "load_15m": round(load15, 2),
        "ram_total_mb": mem_total,
        "ram_used_mb": mem_used,
        "ram_avail_mb": mem_avail,
        "ram_pct": mem_pct,
        "disk_total_gb": round(du_home.total / (1024**3), 1),
        "disk_used_gb": round(du_home.used / (1024**3), 1),
        "disk_free_gb": round(du_home.free / (1024**3), 1),
        "disk_pct": disk_pct,
    }


def get_swarm_state() -> Dict[str, Any]:
    """Inspect active tmux sessions and claims. A probe that fails reports None plus its error, never 0 (rule 6)."""
    # Active tmux sessions
    sessions: list[str] | None = None
    tmux_error = None
    try:
        probe = subprocess.run(["tmux", "ls"], capture_output=True, text=True, timeout=10, check=False)
        if probe.returncode == 0:
            sessions = [line.split(":", 1)[0].strip() for line in probe.stdout.splitlines() if ":" in line]
        else:
            tmux_error = (probe.stderr.strip() or f"tmux ls rc={probe.returncode}")[:200]
    except (OSError, subprocess.SubprocessError) as e:
        tmux_error = f"{type(e).__name__}: {e}"[:200]

    # Active claims
    pool_file = Path("/home/mboyle/bd-persist/POOL_STATE.tsv")
    claimed_roles: list[str] | None = None
    claims_error = None
    try:
        with open(pool_file) as f:
            claimed_roles = []
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2 and parts[1] != "FREE":
                    claimed_roles.append(parts[0])
    except (OSError, UnicodeDecodeError) as e:
        claimed_roles = None
        claims_error = f"{pool_file}: {type(e).__name__}"

    return {
        "active_tmux_sessions": sessions,
        "session_count": None if sessions is None else len(sessions),
        "tmux_error": tmux_error,
        "claimed_roles": claimed_roles,
        "claim_count": None if claimed_roles is None else len(claimed_roles),
        "claims_error": claims_error,
    }


def get_telemetry_accounting() -> Dict[str, Any]:
    """Query usage.sqlite for real-time token statistics."""
    if not USAGE_DB.exists():
        return {"available": False, "error": f"{USAGE_DB} absent"}
    try:
        conn = sqlite3.connect(USAGE_DB, timeout=2.0)
        cursor = conn.cursor()
        total_responses = cursor.execute("SELECT count(*) FROM usage_responses").fetchone()[0]
        
        # 1-hour consumption and wire prefix cache efficiency
        one_hour_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
        h_data = cursor.execute(
            """
            SELECT 
                count(*),
                coalesce(sum(json_extract(usage, '$.input_tokens')), 0),
                coalesce(sum(json_extract(usage, '$.output_tokens')), 0),
                coalesce(sum(coalesce(json_extract(usage, '$.cache_read_input_tokens'), json_extract(usage, '$.cached_input_tokens'), 0)), 0),
                coalesce(sum(coalesce(json_extract(usage, '$.cache_creation_input_tokens'), json_extract(usage, '$.cache_write_input_tokens'), 0)), 0)
            FROM usage_responses 
            WHERE timestamp >= ?
            """,
            (one_hour_ago,),
        ).fetchone()
        conn.close()
        in_tok = h_data[1]
        out_tok = h_data[2]
        cache_read = h_data[3]
        cache_write = h_data[4]
        cache_pct = round((cache_read / in_tok) * 100, 2) if in_tok > 0 else 0.0

        return {
            "available": True,
            "total_responses": total_responses,
            "last_1h_turns": h_data[0],
            "last_1h_in_tokens": in_tok,
            "last_1h_out_tokens": out_tok,
            "last_1h_cache_read_tokens": cache_read,
            "last_1h_cache_creation_tokens": cache_write,
            "last_1h_cache_hit_pct": cache_pct,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


def collect_and_sync() -> Dict[str, Any]:
    """Run single telemetry collection cycle, update disk state, and flag anomalies."""
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sys_metrics = get_system_metrics()
    bd_git = get_git_state(BULK_DOWNLOADER)
    swarm_git = get_git_state(SWARM_OS)
    swarm = get_swarm_state()
    acct = get_telemetry_accounting()

    anomalies = []
    if sys_metrics["disk_pct"] > 90.0:
        anomalies.append(f"CRIT: Disk usage at {sys_metrics['disk_pct']}%")
    if not bd_git.get("clean", True):
        anomalies.append(f"WARN: BulkDownloader working tree dirty ({bd_git.get('dirty_count', 0)} files)")
    if sys_metrics["ram_pct"] > 95.0:
        anomalies.append(f"WARN: RAM exhaustion ({sys_metrics['ram_pct']}%)")
    if swarm["tmux_error"]:
        anomalies.append(f"WARN: telemetry sensor failure: tmux ({swarm['tmux_error']})")
    if swarm["claims_error"]:
        anomalies.append(f"WARN: telemetry sensor failure: claims ({swarm['claims_error']})")
    if not acct.get("available"):
        anomalies.append(f"WARN: telemetry sensor failure: accounting ({acct.get('error', 'unavailable')})")

    payload = {
        "written_at": now_utc,
        "system": sys_metrics,
        "repositories": {
            "BulkDownloader": bd_git,
            "UniversalSwarmOS": swarm_git,
        },
        "swarm": swarm,
        "accounting": acct,
        "anomalies": anomalies,
    }

    LIVE_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp_json = LIVE_JSON.with_suffix(".tmp")
    with open(tmp_json, "w") as f:
        json.dump(payload, f, indent=2)
    tmp_json.replace(LIVE_JSON)
    local_telem_bin = Path("/home/mboyle/bin/bd-local-pool-telemetry.py")
    if local_telem_bin.exists():
        try:
            subprocess.run([sys.executable, str(local_telem_bin), "--sync"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8, check=False)
            payload = json.loads(LIVE_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Write lean human/agent readable status text; an unavailable sensor prints UNKNOWN/UNAVAILABLE, never 0.
    seats = "UNKNOWN (tmux probe failed)" if swarm["session_count"] is None else str(swarm["session_count"])
    claims = "UNKNOWN (claims unreadable)" if swarm["claim_count"] is None else str(swarm["claim_count"])
    if acct.get("available"):
        accounting = (f"{acct['total_responses']} total turns | Last 1h: {acct['last_1h_turns']} turns "
                      f"({round(acct['last_1h_in_tokens']/1000, 1)}k in)")
    else:
        accounting = f"UNAVAILABLE ({acct.get('error', 'unknown error')})"
    status_summary = (
        f"TIMESTAMP: {now_utc}\n"
        f"STATUS: {'WARN' if anomalies else 'GREEN'}\n"
        f"LOAD: {sys_metrics['load_1m']} {sys_metrics['load_5m']} {sys_metrics['load_15m']} | RAM: {sys_metrics['ram_pct']}% | DISK: {sys_metrics['disk_pct']}%\n"
        f"GIT: BD={bd_git.get('head')} ({'clean' if bd_git.get('clean') else 'DIRTY'}) | SWARM={swarm_git.get('head')} ({'clean' if swarm_git.get('clean') else 'DIRTY'})\n"
        f"SWARM: {seats} active tmux seats | {claims} active role claims\n"
        f"ACCOUNTING: {accounting}\n"
    )
    if anomalies:
        status_summary += f"ANOMALIES: {'; '.join(anomalies)}\n"

    tmp_txt = STATUS_TXT.with_suffix(".tmp")
    with open(tmp_txt, "w") as f:
        f.write(status_summary)
    tmp_txt.replace(STATUS_TXT)

    # Log anomalies if any
    if anomalies:
        with open(ALERTS_LOG, "a") as f:
            f.write(f"{now_utc} {' | '.join(anomalies)}\n")

    return payload


def main():
    parser = argparse.ArgumentParser(description="Deterministic Fleet Telemetry Daemon")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for cron or manual checks)")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval in seconds (default 60)")
    args = parser.parse_args()

    if args.once:
        _data = collect_and_sync()
        print(f"TELEMETRY SYNCED: {STATUS_TXT}")
        return

    print(f"Starting bd-telemetry-daemon (interval={args.interval}s, target={STATUS_TXT})...")
    while True:
        try:
            collect_and_sync()
        except Exception as e:
            print(f"Error in telemetry loop: {e}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
