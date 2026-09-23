#!/bin/bash
# bd-rolestate-sessionstart.sh -- ** GIVE A COMPACTED SEAT BACK WHAT IT WAS DOING. **
# Runs on SessionStart (which fires after a compaction as well as at launch).
#
# WHY, and the operator found this: every seat launched by bd-launch-role.sh carries its role in
# --append-system-prompt-file, and a SYSTEM PROMPT IS NOT COMPACTED -- so a compacted worker still
# knows it is a worker. ** THE PM SEAT HAS NO SUCH FILE. ** It was started with `--resume`, so its
# argv is `claude --resume <id> --remote-control --permission-mode bypassPermissions` and NOTHING
# in it says what the seat is. Its role lived only in the conversation, which is exactly what a
# compaction summarises away. The one seat that rules on everyone else's work was the one seat
# whose role did not survive.
# THIS CLOSES IT FOR EVERY SEAT, NOT JUST THE PM: whatever role this tmux session holds in
# ROLE-OCCUPANCY, its role state is printed back into the fresh context.
# THE ROLE IS DERIVED FROM THE OCCUPANCY TABLE, NEVER TYPED. A session holding no claim prints
# nothing -- correct, because it has no role to restore.
set -uo pipefail
S=$(tmux display-message -p '#S' 2>/dev/null || true)
[ -n "$S" ] || exit 0
R=$(awk -F'\t' -v s="$S" 'NR>1 && $2==s {print $1; exit}' /home/mboyle/bd-persist/ROLE-OCCUPANCY.tsv 2>/dev/null)
[ -n "$R" ] || exit 0
# ---- THE ROLE PROMPT TOO, NOT JUST THE STATE. Added 2026-09-09 on operator ruling.
# A launched seat gets BOTH: its standing instructions (--append-system-prompt-file, never
# compacted) and its in-flight state. A --resume session like the PM gets NEITHER from argv.
# Printing the state alone told a compacted PM WHAT WAS HAPPENING but not HOW THE SEAT BEHAVES.
# The prompt is looked up by ROLE, so this works for any seat started outside the launcher.
PROMPT=/home/mboyle/bd-persist/role-prompts/$R.prompt
# ---- H491 (O616): AFTER A COMPACTION, DO NOT RE-INJECT THE PROMPT INTO A SEAT THAT ALREADY CARRIES IT.
# The hook's stdin names the trigger (source: startup|resume|clear|compact). A launcher-started seat has the
# prompt in --append-system-prompt-file, which a compaction never touches; printing it again cost every seat
# ~2-3k tokens per compaction and its read order then triggered the whole-file re-reads O615 measured
# (87k pre -> 8k post, every minute). The PM (--resume, no prompt file) still gets it: argv is the test.
SRC=$(python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("source",""))
except Exception: print("")' 2>/dev/null)
CARRIES=""
[ "$SRC" = compact ] && pgrep -f -- "--name $S .*--append-system-prompt-file" >/dev/null 2>&1 && CARRIES=1
if [ -n "$CARRIES" ]; then
  echo "===== ROLE PROMPT for '$R' is in your system prompt (not compacted); not re-injected (H491). Source: $PROMPT"
elif [ -s "$PROMPT" ]; then
  echo "===== ROLE PROMPT for '$R' -- your standing instructions. Source: $PROMPT"
  cat "$PROMPT"
  echo "===== end role prompt."
fi
F=/home/mboyle/bd-persist/role-state/$R.md
if [ -s "$F" ]; then
  echo "===== ROLE STATE for '$R' (seat $S) -- what this seat was doing. Source: $F"
  # O589 lever 4: IN FLIGHT + the 5 newest TRAIL lines only. The full trail (40 lines) was re-read
  # into every seat at every compaction; older entries are in the file if a seat needs them.
  awk '/^## TRAIL/{t=1} {if(!t)print; else if(n++<6)print}' "$F"
  echo "===== end role state. THIS IS A RECORD, NOT AN ORDER: re-derive anything you act on."
  echo "===== AFTER A COMPACTION (O589 lever 4): read ONLY bd-persist/compact-$S.md and handoff-$S.md, then act."
  echo "      The law above is injected; do NOT re-read CLAUDE.md/COMMON/LIVE-RULES/WAVE3 whole -- the prompt's"
  echo "      read order is for a FRESH launch. Query slices (FLEET_RULE 33b). Re-derive only what you act on."
else
  echo "NOTE seat $S holds role '$R' and $F does not exist -- what this seat was doing is UNKNOWN,"
  echo "     which is not the same as 'nothing'. Write it with bd-role-state.sh before you proceed."
fi
exit 0
