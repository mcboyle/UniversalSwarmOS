#!/bin/bash
# bd-codex-tender.sh -- Deterministic helper for the Codex Tender role
# Inspects codex tmux sessions, auto-answers trust/overload, logs states.
set -uo pipefail

LOG_FILE="/home/mboyle/bd-persist/logs/codex-tender.log"
mkdir -p "$(dirname "$LOG_FILE")"

TS=$(date -u +%FT%TZ)
echo "[$TS] Starting codex-tender pass" >> "$LOG_FILE"

# Collect active codex sessions
SESSIONS=$(tmux list-sessions -F '#S' 2>/dev/null | grep -E '^(rc|cx|as|as-int)' || true)

for s in $SESSIONS; do
  PANE_TAIL=$(tmux capture-pane -p -t "$s" 2>/dev/null | tail -12 || true)
  STATE="IDLE"

  if echo "$PANE_TAIL" | grep -qE "Working \(|Waiting for background"; then
    STATE="WORKING"
  elif echo "$PANE_TAIL" | grep -qF "Yes, continue"; then
    STATE="TRUST"
    tmux send-keys -t "$s" Enter 2>/dev/null || true
    echo "[$TS] $s: Sent Enter for TRUST" >> "$LOG_FILE"
  elif echo "$PANE_TAIL" | grep -qE "Failed to start turn|Server overloaded"; then
    STATE="OVERLOADED"
    tmux send-keys -t "$s" Enter 2>/dev/null || true
    echo "[$TS] $s: Resubmitted for OVERLOADED" >> "$LOG_FILE"
  elif echo "$PANE_TAIL" | grep -qE "› 1\."; then
    # Human-only response required
    STATE="QUESTION"
  elif echo "$PANE_TAIL" | grep -qE "Worked for|Awaiting NEXT"; then
    STATE="IDLE"
  fi

  echo "[$TS] Seat $s: state=$STATE" >> "$LOG_FILE"
done

echo "[$TS] Pass completed" >> "$LOG_FILE"
echo "STATUS: GREEN $LOG_FILE"
