#!/usr/bin/env bash
set -uo pipefail

SEAT="${BD_SEAT:-}"
if [ -z "$SEAT" ] && [ -n "${TMUX_PANE:-}" ]; then
  SEAT=$(tmux display -p -t "$TMUX_PANE" '#S' 2>/dev/null || true)
fi
[ -n "$SEAT" ] || SEAT=$(tmux display-message -p '#S' 2>/dev/null || true)
[ -n "$SEAT" ] || SEAT="unknown"

exec /usr/bin/env python3 -c '
import sys, os, json, datetime

seat = sys.argv[1] if len(sys.argv) > 1 else "unknown"
target_file = None

if len(sys.argv) > 2 and os.path.isfile(sys.argv[2]):
    target_file = sys.argv[2]
else:
    try:
        raw_in = sys.stdin.read()
    except Exception:
        sys.exit(0)
    
    if not raw_in.strip():
        sys.exit(0)
        
    try:
        ev = json.loads(raw_in)
        if isinstance(ev, dict) and "transcript_path" in ev:
            target_file = ev["transcript_path"]
        elif isinstance(ev, dict) and "message" in ev:
            ev_list = [ev]
            target_file = None
        else:
            ev_list = [ev]
            target_file = None
    except Exception:
        target_file = None
        ev_list = []
        for line in raw_in.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev_list.append(json.loads(line))
            except Exception:
                pass

last_assistant = None

if target_file and os.path.isfile(target_file):
    try:
        with open(target_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("type") == "assistant" or (isinstance(obj.get("message"), dict) and obj.get("message", {}).get("role") == "assistant"):
                        last_assistant = obj
                except Exception:
                    continue
    except Exception:
        sys.exit(0)
elif "ev_list" in locals() and ev_list:
    for obj in ev_list:
        if obj.get("type") == "assistant" or (isinstance(obj.get("message"), dict) and obj.get("message", {}).get("role") == "assistant"):
            last_assistant = obj

if not last_assistant:
    sys.exit(0)

msg = last_assistant.get("message")
if isinstance(msg, dict):
    content = msg.get("content", [])
else:
    content = last_assistant.get("content", [])

text_pieces = []
if isinstance(content, str):
    text_pieces.append(content)
elif isinstance(content, list):
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text_pieces.append(item.get("text", ""))
        elif isinstance(item, str):
            text_pieces.append(item)

full_text = "\n".join(text_pieces).strip()
lines = len(full_text.splitlines()) if full_text else 0
chars = len(full_text)

if lines > 12 or chars > 900:
    log_dir = "/home/mboyle/bd-persist/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "narrative.log")
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"{now_iso} {seat} lines={lines} chars={chars}\n")
    except Exception:
        pass
    
    print(json.dumps({
        "systemMessage": "FLEET_RULE 1/33c: cut narration; detail -> file, send the path"
    }))
else:
    print("{}")

sys.exit(0)
' "$SEAT" "$@"
