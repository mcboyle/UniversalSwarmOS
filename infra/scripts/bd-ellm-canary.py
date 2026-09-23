#!/usr/bin/env python3
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone

ALLOWED_SEATS = {"bd-cx-lens-1", "bd-ellm-test-scratch"}
SEAT = "bd-cx-lens-1"
LOG_FILE = "/home/mboyle/bd-persist/logs/ellm-canary.log"
VERDICTS_DIR = Path("/home/mboyle/bd-persist/verdicts")

def get_session_created(target_seat):
    res = subprocess.run(
        ["tmux", "display-message", "-p", "-t", f"={target_seat}", "#{session_created}"],
        capture_output=True, text=True
    )
    if res.returncode == 0:
        try:
            return int(res.stdout.strip())
        except ValueError:
            return 0
    return 0

def get_latest_claim_status(target_seat):
    try:
        with open("/home/mboyle/bd-persist/review-claims.tsv", "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return None, False, 0
        
    last_line = None
    for line in reversed(lines):
        if target_seat in line:
            last_line = line.strip()
            break
            
    if not last_line:
        return None, False, 0
        
    parts = last_line.split("\t")
    is_released = last_line.startswith("RELEASED")
    
    # Example format:
    # RELEASED	/home/mboyle/bd-review-wt/row709-B2-B-20260914-local	correctness	bd-cx-lens-1	2026-09-21T09:57:03Z
    if is_released and len(parts) >= 5:
        cut_path = parts[1]
        ts_str = parts[4]
    elif not is_released and len(parts) >= 4:
        cut_path = parts[0]
        ts_str = parts[3]
    else:
        return None, False, 0

    try:
        # Python 3.11+: datetime.fromisoformat parsing 'Z'
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts_str)
        claim_unix = dt.timestamp()
    except Exception:
        claim_unix = 0

    return cut_path, is_released, claim_unix

def find_verdict_for_cut(cut_path, target_seat):
    now = time.time()
    candidates = []
    
    cp = Path(cut_path)
    if cp.exists():
        candidates.extend(cp.rglob("VERDICT*.md"))
        
    if VERDICTS_DIR.exists():
        candidates.extend(VERDICTS_DIR.rglob("VERDICT*.md"))
        
    for p in sorted(candidates, key=lambda x: x.stat().st_mtime, reverse=True):
        if now - p.stat().st_mtime > 3600:
            continue
        try:
            content = p.read_text()
            if target_seat in content:
                cut_name = cp.name.replace('-local', '')
                if cut_name in str(p) or cut_name in content or "VERDICT" in p.name:
                    return str(p)
        except Exception:
            pass
    return None

def kill_tmux(target_seat, verdict_path):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG_FILE, "a") as f:
        f.write(f"{ts} | {target_seat} | Claim released, verdict found | {verdict_path}\n")
    subprocess.run(["tmux", "kill-session", "-t", f"={target_seat}"])

def main():
    global SEAT
    if os.environ.get("ELLM_EXACT_EQUALITY") != "1":
        print("Guard: ELLM_EXACT_EQUALITY != 1. Exiting.")
        time.sleep(60)
        return
        
    if "ELLM_TEST_SEAT" in os.environ:
        test_seat = os.environ["ELLM_TEST_SEAT"]
        if test_seat in ALLOWED_SEATS:
            SEAT = test_seat
        else:
            print(f"Guard: ELLM_TEST_SEAT {test_seat} not in allowlist. Exiting.")
            time.sleep(60)
            return
            
    while True:
        sess_unix = get_session_created(SEAT)
        if sess_unix > 0:
            cut_path, is_released, claim_unix = get_latest_claim_status(SEAT)
            if is_released and cut_path and claim_unix >= sess_unix:
                v_path = find_verdict_for_cut(cut_path, SEAT)
                if v_path:
                    kill_tmux(SEAT, v_path)
        time.sleep(10)

if __name__ == "__main__":
    main()
