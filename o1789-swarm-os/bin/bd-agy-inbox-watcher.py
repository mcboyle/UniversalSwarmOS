import datetime as dt
import json
import re
import subprocess
import time
from pathlib import Path
INBOX_DIR = Path("/home/mboyle/bd-persist/inbox/agy")
STATE_DIR = Path("/home/mboyle/bd-persist/state")
ALERTS_MD = STATE_DIR / "AGY-LIVE-ALERTS.md"
UNREAD_JSON = Path("/var/tmp/agy-inbox-unread.json")
SEEN_FILE = Path("/var/tmp/agy-inbox-seen.json")

def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load_seen() -> set:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text()))
        except Exception:
            pass
    return set()

def save_seen(seen: set) -> None:
    try:
        SEEN_FILE.write_text(json.dumps(sorted(list(seen))[-1000:]))
    except Exception:
        pass

def emit_alert(source: str, msg: str, path_ref: str="") -> None:
    if "cron:bd-inbox-drain" in msg:
        return
    ts = now_iso()
    clean_msg = " ".join(msg.strip().split())[:220]
    line = f"- **{ts}** | `[{source}]` {clean_msg}" + (f" (`{path_ref}`)" if path_ref else "") + "\n"
    if not ALERTS_MD.exists():
        ALERTS_MD.write_text("# AGY Live Inbox Alerts (<1s Real-Time Mirror)\n\n")
    with ALERTS_MD.open("a", encoding="utf-8") as f:
        f.write(line)
    unread = []
    if UNREAD_JSON.exists():
        try:
            unread = json.loads(UNREAD_JSON.read_text()).get("alerts", [])
        except Exception:
            unread = []
    unread.append({"ts": ts, "source": source, "message": clean_msg, "path": path_ref})
    UNREAD_JSON.write_text(json.dumps({"updated_at": ts, "unread_count": len(unread), "alerts": unread[-30:]}, indent=2))

def step(seen: set) -> None:
    try:
        subprocess.run(["/home/mboyle/bin/bd-batch-relay", "flush", "--target", "agy"], capture_output=True, timeout=3)
    except Exception:
        pass
    try:
        res = subprocess.run(["tmux", "capture-pane", "-p", "-t", "agy", "-S", "-60"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            for raw in res.stdout.splitlines():
                m = re.search(r"(\[from [^\]]+\]\s+.+)", raw.strip())
                if m:
                    msg = re.sub(r"\s*\(alt\+m to send immediately\)\s*$", "", m.group(1).strip())
                    if "cron:bd-inbox-drain" in msg:
                        continue
                    key = f"tmux:{msg[:120]}"
                    if key not in seen:
                        seen.add(key)
                        emit_alert("tmux:agy", msg)
    except Exception:
        pass
    if INBOX_DIR.exists():
        for p in sorted(INBOX_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime):
            key = f"inbox:{p.name}:{int(p.stat().st_mtime)}"
            if key not in seen:
                seen.add(key)
                try:
                    txt = p.read_text(encoding="utf-8", errors="replace").strip()
                    lines = [l.strip() for l in txt.splitlines() if l.strip() and (not l.startswith("#")) and ("cron:bd-inbox-drain" not in l)]
                    if lines:
                        emit_alert("inbox/agy", lines[-1][:180], str(p))
                except Exception:
                    pass
    if STATE_DIR.exists():
        for p in sorted(STATE_DIR.glob("ORDER-pm-B-*"), key=lambda x: x.stat().st_mtime):
            key = f"state:{p.name}:{int(p.stat().st_mtime)}"
            if key not in seen:
                seen.add(key)
                try:
                    first = p.read_text(encoding="utf-8", errors="replace").splitlines()[0][:160]
                    emit_alert("state:pm-B", first, str(p))
                except Exception:
                    pass

def main() -> None:
    seen = load_seen()
    while True:
        try:
            step(seen)
            save_seen(seen)
        except Exception:
            pass
        time.sleep(3)
if __name__ == "__main__":
    main()
