#!/usr/bin/env bash
# bd-fleet-quota-probe.sh -- O1157: Global Sentinel for API Quota Exhaustion
set -uo pipefail

P=${BD_QUOTA_P:-/home/mboyle/bd-persist}
LEDGER=${BD_QUOTA_LEDGER:-$P/DISPATCH-LEDGER.tsv}
BRIEFQ=${BD_QUOTA_BRIEFQ:-$P/harness/bd-briefq-add}

# Look for standard quota error signatures across AGY, Codex, and Claude.
ERROR_REGEX='RESOURCE_EXHAUSTED|usage limit exceeded|quota exceeded|429 Too Many Requests|usage limits|rate limit exceeded'

# H607: derive identity from the live pane's process tree, not its seat name.
# Missing/ambiguous process metadata is UNKNOWN and cannot authorize an alert.
route_identity() {
  python3 - "$1" "${BD_QUOTA_PROC_ROOT:-/proc}" <<'PY_ROUTE'
import pathlib, re, sys
root = pathlib.Path(sys.argv[2])
try:
    pane_pid = int(sys.argv[1])
    parents = {}
    for entry in root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / "status").read_text()
            parents[int(entry.name)] = int(re.search(r"^PPid:\s+(\d+)", status, re.M)[1])
        except (OSError, TypeError, ValueError):
            continue
    if pane_pid not in parents:
        sys.exit(1)
    descendants = {pane_pid}
    while True:
        more = {pid for pid, parent in parents.items() if parent in descendants}
        if more <= descendants:
            break
        descendants |= more
    identities = []
    for pid in descendants:
        try:
            argv = (root / str(pid) / "cmdline").read_bytes().decode().rstrip("\0").split("\0")
        except (OSError, UnicodeError):
            continue
        exe = pathlib.Path(argv[0]).name
        if exe in ("node", "nodejs", "python", "python3") and len(argv) > 1:
            script = pathlib.Path(argv[1])
            exe = "agy" if "agy" in script.parts else script.name
        if exe not in ("codex", "claude", "agy"):
            continue
        model = None
        for i, arg in enumerate(argv):
            if arg in ("--model", "-m") and i + 1 < len(argv):
                model = argv[i + 1]
            elif arg.startswith("--model="):
                model = arg.split("=", 1)[1]
        if model and not re.fullmatch(r"[A-Za-z0-9_.:/-]+", model):
            sys.exit(1)
        # A MODEL IS REQUIRED ONLY WHERE IT DECIDES THE ROUTE. Measured on the live
        # fleet: 4 of the 5 codex seats run `codex --profile <p>` with NO --model on
        # argv (bd-cx-worker-1/-3, bd-cx-lens-1/-2), so demanding one silences the
        # sentinel for exactly the seats this row exists to rescue. codex's bucket
        # follows from the exe and claude's from CLAUDE_CONFIG_DIR, neither of which
        # needs the model; only AGY's route is chosen BY the model, so only AGY still
        # refuses without one. An unread model is reported as unverified, never guessed.
        if exe == "agy" and not model:
            sys.exit(1)
        model = model or "unverified"
        if exe == "codex":
            route, bucket = "native-codex", "CODEX"
        elif exe == "agy":
            if model.startswith("gemini"):
                route = "agy-gemini"
            elif model.startswith(("claude", "gpt")):
                route = "agy-claude"
            else:
                sys.exit(1)
            bucket = "AGY"
        else:
            try:
                env = (root / str(pid) / "environ").read_bytes().split(b"\0")
                config = next((v.split(b"=", 1)[1].decode() for v in env if v.startswith(b"CLAUDE_CONFIG_DIR=")), "")
            except (OSError, UnicodeError):
                sys.exit(1)
            if config == "/home/mboyle/.claude-b":
                bucket = "POOL-B"
            elif config in ("/home/mboyle/.claude-c", "/home/mboyle/.claude-d"):
                bucket = "POOL-" + config[-1].upper()   # accounts C/D (2026-09-30)
            elif config in ("", "/home/mboyle/.claude"):
                bucket = "POOL-A"
            else:
                sys.exit(1)
            route = "native-claude"
        identities.append((route, model, bucket))
    # Launch wrappers may retain the identical route/model of their child.
    identities = set(identities)
    # Different identities cannot attribute the pane error to one model.
    if len(identities) != 1:
        sys.exit(1)
    print("\t".join(next(iter(identities))))
except (OSError, ValueError):
    sys.exit(1)
PY_ROUTE
}

live_seats=$(tmux ls -F '#S' 2>/dev/null || true)

for seat in $live_seats; do
  # Ignore purely administrative/local panes and command-squad / PM seats
  if [[ "$seat" == "relay-test" || "$seat" == "antigravity" || "$seat" == bd-pm-* || "$seat" == bd-usage-* || "$seat" == bd-integrator-* || "$seat" == bd-dispatch-* || "$seat" == bd-lensrouter-* ]]; then continue; fi

  # tmux ls can race session teardown; exact targets also avoid prefix matches.
  tmux has-session -t "=$seat" 2>/dev/null || continue
  target=$(tmux display-message -p -t "=$seat:" '#{session_id} #{pane_id} #{pane_pid}' 2>/dev/null) || continue
  read -r session_id pane_id pane_pid <<< "$target"
  [[ "$session_id" =~ ^\$[0-9]+$ && "$pane_id" =~ ^%[0-9]+$ && "$pane_pid" =~ ^[0-9]+$ ]] || continue
  pane=$(tmux capture-pane -p -t "$pane_id" 2>/dev/null) || continue

  if echo "$pane" | grep -iqE "$ERROR_REGEX"; then
    identity=$(route_identity "$pane_pid") || continue
    IFS=$'\t' read -r route model bucket <<< "$identity"
    tmux has-session -t "=$seat" 2>/dev/null || continue
    current=$(tmux display-message -p -t "=$seat:" '#{session_id} #{pane_id} #{pane_pid}' 2>/dev/null) || continue
    [ "$current" = "$target" ] || continue
    [ "$(route_identity "$pane_pid")" = "$identity" ] || continue
    marker="$P/QUOTA-EXHAUSTED-$seat"
    [ -e "$marker" ] && continue # Already handled
    
    echo "$(date -u +%FT%TZ) QUOTA EXHAUSTED: $seat route=$route model=$model bucket=$bucket session=$session_id" >> "$P/logs/quota-probe.log"
    : > "$marker"
    
    # Tell the PM
    /home/mboyle/bd-say.sh pm "QUOTA-EXHAUSTED: Seat $seat hit API limits (Bucket: $bucket; route=$route model=$model). Confirmed seat/model limit; apply scoped failover policy." >/dev/null 2>&1
    
    # Requeue the brief if it was working on one
    open=$(awk -F '\t' -v s="$seat" '$2==s && $4=="dispatched"{r=$3; b=$5} $2==s && $4~/done|aborted/{r="";b=""} END{if(r) print r "\t" b}' "$LEDGER" 2>/dev/null || true)
    if [ -n "$open" ]; then
      slug=${open%%$'\t'*}
      brief=${open#*$'\t'}
      grep -qE "^${slug}[[:space:]]" "$P/brief-queue.txt" 2>/dev/null || "$BRIEFQ" "$slug" "$brief" T2 >/dev/null
    fi
    
    # Kill the dead seat so it doesn't spin
    tmux kill-session -t "$session_id" 2>/dev/null || true
    /home/mboyle/bd-role-claim.sh reap >/dev/null 2>&1
  fi
done
