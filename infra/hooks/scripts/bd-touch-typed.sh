#!/usr/bin/env bash
# UserPromptSubmit hook (H543/H518): refresh OPERATOR-LAST-TYPED (epoch) when the OPERATOR types in a PM pane.
# Fleet messages arrive as prompts too; they start with "[from " (bd-say) -- those never count. Non-PM sessions never count.
P=/home/mboyle/bd-persist
sess=${BD_SEAT:-}
[ -n "$sess" ] || { [ -n "${TMUX_PANE:-}" ] && sess=$(tmux display -p -t "$TMUX_PANE" '#S' 2>/dev/null || true); }
[ -n "$sess" ] || sess=$(tmux display-message -p '#S' 2>/dev/null || true)
case "$sess" in bd-pm-*|*pm*) ;; *) exit 0;; esac

prompt=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("prompt",""))' 2>/dev/null | head -c 20 || true)
case "$prompt" in "[from "*|"PM SELF-DRIVING"*|"") exit 0;; esac

date -u +%s > $P/OPERATOR-LAST-TYPED.tmp && mv $P/OPERATOR-LAST-TYPED.tmp $P/OPERATOR-LAST-TYPED
[ "$(head -1 $P/OPERATOR-PRESENCE.md 2>/dev/null)" = PRESENT ] || { { echo PRESENT; tail -n +2 $P/OPERATOR-PRESENCE.md; echo "# $(date -u +%FT%TZ)  PRESENT   -- operator typed in $sess (bd-touch-typed.sh hook, H543/H518)."; } > $P/OPERATOR-PRESENCE.md.tmp && mv $P/OPERATOR-PRESENCE.md.tmp $P/OPERATOR-PRESENCE.md; }
exit 0
