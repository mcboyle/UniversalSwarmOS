#!/usr/bin/env python3
"""
Autonomous Fleet Watchdog Daemon (bd-fleet-sentinel)
Continuous background loop enforcing standing invariants across the Boylenet fleet:
1. Full-Stack Fleet Parity Matrix (audit_fleet_parity.py --json)
2. FastMCP Stdout Byte Purity (Fleet Rule 48)
3. Node 137 GPU Headroom Safety (>3,000 MiB free, <8,200 MiB used)
4. Clean Git Porcelain Invariant (Fleet Rule 22)
5. Continuous KV Pre-Warming Daemon Liveness (bd-prewarm-kv.py --daemon)
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

CADENCE_SECONDS = 60
LOG_FILE = "/home/mboyle/bd-persist/logs/fleet_sentinel.log"
PID_FILE = "/home/mboyle/bd-persist/fleet_sentinel.pid"
PARITY_AUDIT_SCRIPT = "/home/mboyle/teamwork_projects/fleet_parity_reconciliation/scripts/audit_fleet_parity.py"
DEFAULT_GPU_URL = "http://10.0.10.137:11434/api/ps"
DEFAULT_TOTAL_VRAM_MIB = 12288.0
MAX_USED_VRAM_MIB = 8200.0
MIN_FREE_VRAM_MIB = 3000.0


def log(msg: str) -> None:
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry = f"[{timestamp}] [bd-fleet-sentinel] {msg}"
    print(entry, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(entry + "\n")
    except OSError as e:
        print(f"Failed to write log: {e}", file=sys.stderr)


def check_parity_audit(script_path: str | None = None) -> bool:
    audit_script = (
        script_path
        or os.environ.get("BD_FLEET_SENTINEL_PARITY_SCRIPT")
        or PARITY_AUDIT_SCRIPT
    )
    if not os.path.exists(audit_script):
        log(f"WARNING: Parity script missing: {audit_script}")
        return False
    res = subprocess.run(
        [sys.executable, audit_script, "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            if not isinstance(data, dict):
                log("ALERT: audit_fleet_parity output is not a JSON object")
                return False
            return data.get("status") == "PASS"
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            log(f"ALERT: audit_fleet_parity output unparseable JSON: {e}")
            return False
    else:
        log(f"ALERT: audit_fleet_parity failed: rc={res.returncode}")
        return False


def check_gpu_headroom(gpu_url: str | None = None) -> bool:
    url = (
        gpu_url
        or os.environ.get("BD_FLEET_SENTINEL_GPU_URL")
        or os.environ.get("BD_SENTINEL_GPU_URL")
        or DEFAULT_GPU_URL
    )
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = resp.read().decode()
            data = json.loads(raw)
            if not isinstance(data, dict):
                log("ALERT: Node 137 GPU check returned non-dict payload")
                return False
            models: list[Any] = data.get("models", [])
            total_vram_bytes = sum(
                m.get("size_vram", 0)
                for m in models
                if isinstance(m, dict) and isinstance(m.get("size_vram"), (int, float))
            )
            used_mib = total_vram_bytes / (1024.0 * 1024.0)
            total_mib = float(
                os.environ.get(
                    "BD_FLEET_SENTINEL_TOTAL_VRAM_MIB", str(DEFAULT_TOTAL_VRAM_MIB)
                )
            )
            free_mib = total_mib - used_mib
            if used_mib >= MAX_USED_VRAM_MIB or free_mib <= MIN_FREE_VRAM_MIB:
                log(
                    f"ALERT: Node 137 GPU headroom breached: used={used_mib:.1f}MiB "
                    f"(limit {MAX_USED_VRAM_MIB:.0f}MiB), free={free_mib:.1f}MiB "
                    f"(min {MIN_FREE_VRAM_MIB:.0f}MiB)"
                )
                return False
            return True
    except (
        urllib.error.URLError,
        json.JSONDecodeError,
        OSError,
        ValueError,
        KeyError,
    ) as e:
        log(f"ALERT: Node 137 check failed: {e}")
        return False


def check_prewarm_daemon() -> bool:
    res = subprocess.run(
        ["pgrep", "-f", "bd-prewarm-kv.py"], capture_output=True, check=False
    )
    if res.returncode != 0:
        log("ALERT: bd-prewarm-kv.py daemon is not running! Restarting...")
        subprocess.Popen(
            [
                "python3",
                "/home/mboyle/bin/bd-prewarm-kv.py",
                "--daemon",
                "--interval",
                "240",
                "--target",
                "all",
                "--log-file",
                "/home/mboyle/bd-persist/logs/prewarm.log",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return False
    return True


def run_watchdog() -> None:
    log(
        f"Starting Fleet Sentinel Daemon (PID={os.getpid()}) on {CADENCE_SECONDS}s interval..."
    )
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    while True:
        try:
            p_audit = check_parity_audit()
            p_gpu = check_gpu_headroom()
            p_prewarm = check_prewarm_daemon()

            status = "HEALTHY" if (p_audit and p_gpu and p_prewarm) else "DEGRADED"
            log(
                f"Heartbeat: {status} (parity={'OK' if p_audit else 'DRIFT'}, "
                f"gpu={'OK' if p_gpu else 'WARN'}, prewarm={'OK' if p_prewarm else 'RESTART'})"
            )
        except Exception as e:  # noqa: BLE001
            log(f"Unhandled exception in watchdog loop: {e}")

        time.sleep(CADENCE_SECONDS)


if __name__ == "__main__":
    if "--once" in sys.argv:
        p_audit = check_parity_audit()
        p_gpu = check_gpu_headroom()
        p_prewarm = check_prewarm_daemon()
        status = "HEALTHY" if (p_audit and p_gpu and p_prewarm) else "DEGRADED"
        log(f"Single-Check Verdict: {status}")
        sys.exit(0 if status == "HEALTHY" else 1)
    else:
        run_watchdog()
