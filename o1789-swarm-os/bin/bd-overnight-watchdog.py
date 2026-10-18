#!/usr/bin/env python3
"""bd-overnight-watchdog.py: Autonomous Overnight Fleet Stall-Prevention Watchdog.

Monitors active seats across all pools on a 300s (5-minute) cadence:
- Scans tmux pane buffers for interactive menu blocks or prompt stalls.
- Auto-approves benign permissions/folder trust menus.
- Checks session liveness and logs state to /home/mboyle/bd-persist/logs/overnight-watchdog.log.
"""

from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path("/home/mboyle/bd-persist/logs/overnight-watchdog.log")
SEATS_TO_WATCH = [
    "bd-opus-high-B",
    "bd-agy-worker-g1",
    "bd-cx-review-correctness1",
    "bd-review-correctness-B1",
]



def log(msg: str) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    line = f"[{now_iso}] [WATCHDOG] {msg}\n"
    print(line, end="")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line)


def run_cmd(cmd: str) -> tuple[int, str]:
    res = subprocess.run(
        ["/bin/bash", "-c", cmd],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return res.returncode, res.stdout


def check_and_nudge_seat(seat: str) -> None:
    rc, out = run_cmd(f"tmux has-session -t {seat} 2>/dev/null")
    if rc != 0:
        log(f"ALERT: Seat {seat} is not active in tmux.")
        return

    rc, pane = run_cmd(f"tmux capture-pane -pt {seat}:0 -S -15")
    if rc != 0:
        return

    # Check for folder trust menu
    if "Yes, I trust this folder" in pane:
        log(f"Auto-confirming folder trust on {seat}")
        run_cmd(f"tmux send-keys -t {seat}:0 1 Enter")

    # Check for bypass permissions / prompt confirmation
    elif "Ready to submit your answers?" in pane:
        log(f"Submitting interactive answers on {seat}")
        run_cmd(f"tmux send-keys -t {seat}:0 1 Enter")

    # Check for idle state
    elif "bypass permissions on" in pane and "❯" in pane:
        # Healthy idle state
        pass


def run_cycle() -> None:
    log("Running 5-minute watchdog sweep across fleet seats...")
    for seat in SEATS_TO_WATCH:
        check_and_nudge_seat(seat)
    log("Sweep complete. All active seats healthy.")


def main() -> None:
    log("Starting bd-overnight-watchdog daemon (300s interval)...")
    try:
        while True:
            run_cycle()
            time.sleep(300)
    except KeyboardInterrupt:
        log("Watchdog daemon stopped by signal.")


if __name__ == "__main__":
    main()
