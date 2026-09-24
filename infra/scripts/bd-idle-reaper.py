#!/usr/bin/env python3
"""
bd-idle-reaper.py -- Automated Idle Seat Retirement & Compaction Daemon
Monitors active swarm seats. If a non-protected seat has been idle for > 30 minutes
and its active context exceeds 150,000 tokens, automatically retires or compacts it.

Authority: Operator Optimization Mandate 2026-09-23
"""

import argparse
import glob
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

LOG_FILE = Path("/home/mboyle/bd-persist/logs/idle-reaper.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [idle-reaper] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("idle-reaper")

PROTECTED_SEATS = {
    "agy-recovery",
    "auto-approver",
    "bd-amnesia-daemon",
    "bd-idle-reaper",
    "cockpit-9999",
    "dashboard",
    "hf-telemetry-guard",
    "opus-handoff-B",
    "bd-pm-B",
    "cx-test-long",
    "cx-astra-test",
}

DEFAULT_IDLE_MINUTES = 30.0
DEFAULT_TOKEN_THRESHOLD = 150_000
CHARS_PER_TOKEN = 3.5


def get_live_tmux_sessions() -> list[str]:
    try:
        out = subprocess.check_output(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return [s.strip() for s in out.splitlines() if s.strip()]
    except Exception:
        return []


def get_session_transcript_info(session_name: str) -> tuple[float, int, str | None]:
    """Returns (idle_minutes, est_tokens, transcript_path) for a tmux session."""
    try:
        pids = subprocess.check_output(
            ["tmux", "list-panes", "-t", session_name, "-F", "#{pane_pid}"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).splitlines()
        if not pids:
            return 0.0, 0, None
        
        pane_pid = int(pids[0].strip())
        
        # Check processes running under this pane
        child_pids = [pane_pid]
        try:
            children = subprocess.check_output(
                ["pgrep", "-P", str(pane_pid)],
                text=True,
                stderr=subprocess.DEVNULL,
            ).splitlines()
            child_pids.extend(int(c.strip()) for c in children if c.strip())
        except Exception:
            pass

        now = time.time()
        newest_file: Path | None = None
        newest_mtime = 0.0

        for p in child_pids:
            fd_dir = Path(f"/proc/{p}/fd")
            if not fd_dir.exists():
                continue
            for fd in fd_dir.glob("*"):
                try:
                    target = Path(os.readlink(fd))
                    if target.suffix == ".jsonl" and ("projects" in str(target) or "sessions" in str(target)):
                        st = target.stat()
                        if st.st_mtime > newest_mtime:
                            newest_mtime = st.st_mtime
                            newest_file = target
                except Exception:
                    continue

        if newest_file and newest_mtime > 0:
            idle_min = (now - newest_mtime) / 60.0
            est_tokens = int(newest_file.stat().st_size / CHARS_PER_TOKEN)
            return idle_min, est_tokens, str(newest_file)

    except Exception as e:
        logger.debug(f"Error inspecting {session_name}: {e}")

    return 0.0, 0, None


def retire_or_compact_seat(session_name: str, idle_min: float, est_tokens: int, dry_run: bool = False) -> None:
    logger.info(
        f"BREACH: {session_name} idle {idle_min:.1f}m (> {DEFAULT_IDLE_MINUTES}m) with ~{est_tokens:,} tokens (> {DEFAULT_TOKEN_THRESHOLD:,})"
    )
    if dry_run:
        logger.info(f"[DRY-RUN] Would retire/compact {session_name}")
        return

    # 1. Order retirement via bd-say.sh
    msg = f"STOP: RETIRED (O1348 idle {idle_min:.0f}m, {est_tokens//1000}k tok). Write handoff-{session_name}.md NOW, then idle."
    try:
        subprocess.run(
            ["/home/mboyle/bd-say.sh", session_name, msg],
            timeout=10,
            capture_output=True,
        )
        logger.info(f"Dispatched retirement order to {session_name}")
    except Exception as e:
        logger.warning(f"Failed to send retirement order to {session_name}: {e}")

    # 2. Release role claim if held
    try:
        role_out = subprocess.check_output(
            ["/home/mboyle/bd-role-claim.sh", "--mine", session_name],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        for line in role_out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                role = parts[0].strip()
                logger.info(f"Releasing role {role} for {session_name}")
                subprocess.run(
                    ["/home/mboyle/bd-role-claim.sh", "release", role, session_name],
                    timeout=5,
                    capture_output=True,
                )
    except Exception:
        pass


def run_sweep(dry_run: bool = False) -> int:
    sessions = get_live_tmux_sessions()
    retired_count = 0
    for s in sessions:
        if s in PROTECTED_SEATS:
            continue
        idle_min, est_tokens, transcript = get_session_transcript_info(s)
        if idle_min >= DEFAULT_IDLE_MINUTES and est_tokens >= DEFAULT_TOKEN_THRESHOLD:
            retire_or_compact_seat(s, idle_min, est_tokens, dry_run=dry_run)
            retired_count += 1
    return retired_count


def main():
    parser = argparse.ArgumentParser(description="bd-idle-reaper daemon")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in background")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without retiring")
    args = parser.parse_args()

    logger.info(f"bd-idle-reaper starting (daemon={args.daemon}, idle_threshold={DEFAULT_IDLE_MINUTES}m, token_threshold={DEFAULT_TOKEN_THRESHOLD})")

    if not args.daemon:
        count = run_sweep(dry_run=args.dry_run)
        logger.info(f"One-shot sweep complete. Retired {count} seats.")
        return

    while True:
        try:
            run_sweep(dry_run=args.dry_run)
        except Exception as e:
            logger.error(f"Error in sweep iteration: {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
