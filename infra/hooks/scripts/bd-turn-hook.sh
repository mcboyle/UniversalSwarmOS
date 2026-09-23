#!/bin/bash
# bd-turn-hook.sh -- Claude Code Stop hook: one line per completed turn -> bd-persist/turns/<seat>.count (O860/O861).
# Seat = BD_SEAT (launcher-exported) else the tmux session of this pane. Never blocks (exit 0 always).
S=${BD_SEAT:-}; [ -n "$S" ] || { [ -n "${TMUX_PANE:-}" ] && S=$(tmux display -p -t "$TMUX_PANE" '#S' 2>/dev/null); }
[ -n "$S" ] || exit 0
printf '%s\n' "$(date -u +%FT%TZ)" >> "/home/mboyle/bd-persist/turns/$S.count" 2>/dev/null
exit 0
