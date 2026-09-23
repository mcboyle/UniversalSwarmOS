#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1

PYTHON_BIN="${BD_FLEET_PYTHON:-$(command -v python3 || echo "python3")}"

# Check for full plugin cli.py in standard locations
CLI_CANDIDATES=(
    "${BD_FLEET_DIR:-}/cli.py"
    "$DIR/cli.py"
    "$DIR/../cli.py"
    "${SWARM_ROOT:-/opt/swarm_os}/persist/plugins/bd-fleet-mcp/cli.py"
    "/home/mboyle/bd-persist/plugins/bd-fleet-mcp/cli.py"
)

CLI_PATH=""
for cand in "${CLI_CANDIDATES[@]}"; do
    if [ -n "$cand" ] && [ -f "$cand" ]; then
        CLI_PATH="$cand"
        break
    fi
done

# Delegate to cli.py if present and mcp runtime is available
if [ -n "$CLI_PATH" ] && "$PYTHON_BIN" -c "import mcp" 2>/dev/null; then
    exec "$PYTHON_BIN" "$CLI_PATH" hook "$@"
fi

# Fallback: Robust self-contained pure-Python validator (Zero external dependencies)
exec "$PYTHON_BIN" - "$@" << 'EOF'
import sys, os, json, re, time

def validate_say(target, message):
    if not target or not isinstance(target, str):
        return False, "invalid_target"
    if target == "bd-capture-test2":
        return False, "operator-owned target: Rule 21"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", target):
        return False, "invalid_target_name"
    if not message or not isinstance(message, str) or not message.strip():
        return False, "empty_message"
    has_path = bool(re.search(r"(?:^|\s)(?:/[^\s]+|https?://\S+|[\w./-]+\.(?:md|log|txt|json|tsv))(?=\s|$)", message))
    if len(message) > 30 and not has_path:
        return False, "length_exceeded: >30 chars without path"
    return True, "ALLOW"

raw = ""
if len(sys.argv) > 2 and sys.argv[1] == "hook":
    raw = sys.argv[2]
else:
    raw = sys.stdin.read()

if not raw.strip():
    sys.exit(0)

# Check JSON tool input
if raw.lstrip().startswith(("{", "[")):
    try:
        obj = json.loads(raw)
        tool = obj.get("toolCall", obj)
        name = tool.get("name", tool.get("tool_name", ""))
        inp = tool.get("args", tool.get("tool_input", {}))
        
        if name in ("say", "mcp__bd__say"):
            target = inp.get("target", inp.get("recipient", ""))
            message = inp.get("text", inp.get("message", ""))
            ok, reason = validate_say(target, message)
            if not ok:
                print(f"REFUSED: {reason}", file=sys.stderr)
                sys.exit(2)
            sys.exit(0)
            
        cmd = inp.get("command", inp.get("CommandLine", inp.get("cmd", "")))
        if cmd:
            raw = cmd
    except Exception:
        sys.exit(0)

# Check CLI bd-say commands
if "bd-say" in raw:
    for line in raw.split("\n"):
        parts = line.strip().split()
        for idx, part in enumerate(parts):
            if part in ("bd-say", "bd-say.sh") and idx + 2 < len(parts):
                target = parts[idx + 1]
                message = " ".join(parts[idx + 2:]).strip("\"'")
                if any(c in line for c in ("$", "`")):
                    print("REFUSED: dynamic argument in say", file=sys.stderr)
                    sys.exit(2)
                ok, reason = validate_say(target, message)
                if not ok:
                    print(f"REFUSED: {reason}", file=sys.stderr)
                    sys.exit(2)

sys.exit(0)
EOF
