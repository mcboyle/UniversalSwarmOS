#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone

EXCLUDE_SEATS = {"bd-capture-test2", "antigravity", "relay-test"}

def get_live_seats():
    res = subprocess.run(["tmux", "ls", "-F", "#{session_name}"], capture_output=True, text=True)
    if res.returncode != 0: return []
    return [s.strip() for s in res.stdout.strip().split("\n") if s.strip()]

def is_idle(seat):
    # Using the exact bash idle_pane logic
    bash_code = f"""
_o945_strip_ghost() {{
  sed -E 's/\x1b\\[(2|2;[0-9;]+|[0-9;]+;2)m(\x1b\\[([1-9]|1[0-9]|2[013-9]|[3-9][0-9]|38;[0-9;]+|48;[0-9;]+)m|[^\\x1b])*\\x1b\\[(0|22)(;[0-9;]+)?m//g; s/\\x1b\\[[0-9;?]*[A-Za-z]//g; s/\\xc2\\xa0/ /g'
}}
cap=$(tmux capture-pane -e -pt "{seat}:" -S -40 2>/dev/null | _o945_strip_ghost) || exit 1
printf '%s\\n' "$cap" | grep -qiE "esc to cancel|\\(y/n\\)|Yes, |No, |Allow|Deny|Do you trust|Press Enter|Select" && exit 1
printf '%s\\n' "$cap" | grep -qE 'esc to interrupt|\\([0-9]+m [0-9]+s|\\([0-9]+s ·' && exit 1
last=$(printf '%s\\n' "$cap" | grep '^❯' | tail -1)
[ -n "$last" ] || exit 1
if printf '%s' "$last" | grep -qE '^❯ +$|^❯$'; then exit 0; fi
if printf '%s' "$last" | grep -qE '^❯ +Try "[^"]*"$'; then exit 0; fi
exit 1
"""
    res = subprocess.run(["bash", "-c", bash_code])
    return res.returncode == 0

def flush_relay(seat):
    env = os.environ.copy()
    env["PYTHONPATH"] = "/home/mboyle/teamwork_projects/lifecycle_optimizer"
    subprocess.run(["/home/mboyle/bin/bd-batch-relay", "flush", "--target", seat], env=env, capture_output=True)

def drain_inbox(seat):
    inbox_dir = Path(f"/home/mboyle/bd-persist/inbox/{seat}")
    if not inbox_dir.exists(): return
    
    drained_file = inbox_dir / ".drained"
    last_drained = drained_file.stat().st_mtime if drained_file.exists() else 0
    
    md_files = [f for f in inbox_dir.glob("*.md") if f.name != "BATCH.md"]
    new_files = [f for f in md_files if f.stat().st_mtime > last_drained and not f.name.startswith("IDLE-BATCH-")]
    
    if not new_files: return
    
    # Sort files by modification time
    new_files.sort(key=lambda x: x.stat().st_mtime)
    
    ts_compact = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_file = inbox_dir / f"IDLE-BATCH-{ts_compact}.md"
    
    content = f"# TERSE: {len(new_files)} messages drained by bd-idle-flush at {ts_compact}\\n\\n"
    for nf in new_files:
        content += f"--- {nf.name}\\n"
        content += nf.read_text() + "\\n\\n"
        
    batch_file.write_text(content)
    drained_file.touch()
    
    # Push immediately
    env = os.environ.copy()
    env["BD_SAY_BATCH"] = "0"
    subprocess.run(["/home/mboyle/bd-say.sh", seat, f"[from cron:bd-idle-flush] INBOX {len(new_files)} new: {batch_file}"], env=env)

def main():
    seats = get_live_seats()
    for seat in seats:
        if seat in EXCLUDE_SEATS:
            continue
        if is_idle(seat):
            flush_relay(seat)
            drain_inbox(seat)

if __name__ == "__main__":
    main()
