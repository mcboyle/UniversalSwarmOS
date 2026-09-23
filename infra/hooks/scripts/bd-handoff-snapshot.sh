#!/bin/bash
# bd-handoff-snapshot.sh -- PreCompact hook. No arguments.
#
# A compaction summary is not evidence. This writes down what the session HELD
# at the moment it compacted, so the session on the other side can re-derive
# instead of trusting a summary: which dirs it claimed, whether a verdict file
# already exists in each, its train rows, and a pointer to its handoff.
#
# It OVERWRITES bd-persist/compact-<name>.md and NEVER touches handoff-<name>.md:
# the handoff is the session's own considered statement and a hook must not edit it.
set -u
P=${BD_PERSIST:-/home/mboyle/bd-persist}
NAME=${BD_SNAPSHOT_SESSION:-$(tmux display-message -p '#S' 2>/dev/null || true)}
case "$NAME" in
  bd-*|cx-*) : ;;
  *) exit 0 ;;                    # not a fleet session: say nothing, change nothing
esac
OUT=$P/compact-$NAME.md
CLAIMS=${BD_SNAPSHOT_CLAIMS:-$P/review-claims.tsv}
TRAINS=${BD_SNAPSHOT_TRAINS:-$P/trains/claims.tsv}
WT=${BD_SNAPSHOT_WT:-/home/mboyle/bd-review-wt}

TMP=$(mktemp "$OUT.XXXXXX") || exit 0
{
  echo "# compaction snapshot -- $NAME -- $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  echo "Read this, then bd-persist/handoff-$NAME.md. NEVER file a verdict from a"
  echo "compaction summary: re-run the census and the commands, not your memory of them."
  echo
  echo "## dirs this session claims ($CLAIMS, column 3 == $NAME)"
  if [ -f "$CLAIMS" ]; then
    rows=$(awk -F'\t' -v n="$NAME" '$3==n' "$CLAIMS" 2>/dev/null)
    if [ -n "$rows" ]; then
      printf '%s\n' "$rows" | while IFS=$'\t' read -r id lens who rest; do
        echo "- $id  lens=$lens  $rest"
        for v in "$WT/$id"/.review/VERDICT-*.md; do
          [ -e "$v" ] && echo "    VERDICT PRESENT: $(basename "$v") ($(stat -c %s "$v") bytes)"
        done
      done
    else
      echo "(none)"
    fi
  else
    echo "UNKNOWN: $CLAIMS is absent"
  fi
  echo
  echo "## train rows ($TRAINS)"
  if [ -f "$TRAINS" ]; then
    letter=${NAME#bd-integrator}; letter=${letter#-}
    hits=$(grep -iE "(^|[[:space:]])(${NAME}|${letter:-__none__})([[:space:]]|$)" "$TRAINS" 2>/dev/null | head -20)
    [ -n "$hits" ] && printf '%s\n' "$hits" || echo "(no row mentions $NAME)"
  else
    echo "UNKNOWN: $TRAINS is absent"
  fi
  echo
  echo "## handoff"
  if [ -f "$P/handoff-$NAME.md" ]; then
    echo "bd-persist/handoff-$NAME.md ($(stat -c %s "$P/handoff-$NAME.md") bytes, $(date -u -r "$P/handoff-$NAME.md" +%H:%MZ))"
  else
    echo "NO handoff-$NAME.md -- write one before the next task."
  fi
} > "$TMP" 2>/dev/null
mv -f "$TMP" "$OUT" 2>/dev/null || rm -f "$TMP"
# ** MY FIRST VERSION APPENDED THIS BLOCK BELOW AN `exit 0` ON LINE 64, SO IT NEVER RAN AND THE
# CONTROL SHOWED NOTHING WRITTEN. Same shape as the codex guard defined after its call site
# earlier tonight: DEAD CODE THAT LOOKS LIKE A FIX.
# ---- STAMP THE ROLE STATE TOO. ADDED 2026-09-09 after the operator asked what happens when
# dispatch or the PM compacts. MEASURED THEN: this hook wrote compact-<seat>.md and NOTHING touched
# role-state, so a seat that compacted mid-assignment left its ROLE's memory untouched and its
# successor -- or itself, one turn later -- had no marker that a compaction had even happened.
# THE ROLE SURVIVES A COMPACTION ALREADY (it is in --append-system-prompt-file, which is not
# compacted). WHAT WAS IN FLIGHT DID NOT. This closes that half.
# The ROLE is derived from ROLE-OCCUPANCY by seat name -- never typed, never guessed. A seat with no
# claim gets no stamp, which is correct: it holds no role to record.
_rs_role=$(awk -F'\t' -v s="${NAME:-}" 'NR>1 && $2==s {print $1; exit}' \
           /home/mboyle/bd-persist/ROLE-OCCUPANCY.tsv 2>/dev/null)
if [ -n "$_rs_role" ] && [ -x /home/mboyle/bd-role-state.sh ]; then
  _rs_prev=$(sed -n '/^## IN FLIGHT NOW/,/^$/p' "/home/mboyle/bd-persist/role-state/$_rs_role.md" 2>/dev/null | sed '1d' | head -3 | tr '\n' ' ')
  /home/mboyle/bd-role-state.sh set "$_rs_role" "${NAME:-unknown}" \
    "COMPACTED $(date -u +%FT%TZ). Detail: /home/mboyle/bd-persist/compact-${NAME}.md. Last known in-flight before the compaction: ${_rs_prev:-nothing recorded -- THIS SEAT NEVER WROTE ITS ROLE STATE, so what it was doing is UNKNOWN, not nothing}" >/dev/null 2>&1 \
    && echo "role-state stamped for $_rs_role" || echo "WARN could not stamp role-state for $_rs_role" >&2
fi

exit 0
