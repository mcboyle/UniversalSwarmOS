#!/bin/bash
# swarm-pm-pass.sh -- ONE COMPACT CENSUS FOR THE PM'S 10-MINUTE PASS (O1155c).
# Written because the pass was costing 3-4 tool rounds of raw tmux/ls output per tick, and rule 33
# says the operator's context is his money. Output is <=40 lines. Facts only; the PM decides.
# BUSY vs IDLE is read from the seat's own status line ("Working"/"esc to interrupt"/"N shell"),
# never from the last text line -- a narrow tail reports a working seat as idle (measured 12:3xZ).
set -u
P=${SWARM_PERSIST_DIR}
pm_inbox_summary(){
  local IB CUR mark b
  local -a newer=()
  echo "== inbox: new since last pass =="
  IB=$P/inbox/$(grep -v '^#' "$P/PM-SEAT" 2>/dev/null | head -1 | tr -d '[:space:]' || echo swarm-pm-Opus-B)
  CUR=$P/state/pm-inbox-cursor
  [ -d "$IB" ] || return 0
  [ ! -e "$CUR" ] || newer=(-newer "$CUR")
  # Snapshot before reading, so arrivals during this pass remain eligible next time.
  mark=$(mktemp "$CUR.XXXXXX") || return 4
  if ! (set -o pipefail; find "$IB" -name 'BATCH-*.md' "${newer[@]}" -print0 | sort -z |
    while IFS= read -r -d '' b; do
      awk -v path="$b" '
        /^\[from / { print "  " substr($0,1,160) " | " path; messages++; next }
        !/^#/ && /[^[:space:]]/ && first=="" { first=$0 }
        END { if (!messages && first!="") print "  " substr(first,1,160) " | " path }
      ' "$b" || exit 4
    done | awk -v inbox="$IB" '
      { count++; if (count<=14) line[count]=$0 }
      END {
        limit=(count<=14 ? count : 13)
        for (i=1;i<=limit;i++) print line[i]
        if (count>14) print "  " count-13 " more messages | " inbox
      }'); then
    echo "  UNKNOWN inbox summary failed | $IB" >&2
    return 4
  fi
  mv -- "$mark" "$CUR"
}
if [ "${1:-}" = --inbox-only ]; then
  P=${2:?fixture or persist root required}
  set -o pipefail
  pm_inbox_summary
  exit $?
fi
echo "== HB BOARD not deployed =="
for d in $P/harness-work/HB-*/*/; do s=$(basename "$d"); [ -f "$d/DONE.md" ] || continue
  # law-slim keeps its review at <slug>/cut/.review/, not <slug>/.review/, so a one-level glob
  # missed a live BOARD (13:0xZ). Look one level deeper too.
  v=$(ls "$d"/.review/VERDICT-*.md "$d"/*/.review/VERDICT-*.md 2>/dev/null | head -1); [ -n "$v" ] || continue
  head -1 "$v" | grep -q BOARD || continue
  # A deploy is recorded either as HARNESS-<slug>-<ts>.md or inside a DEPLOY-ORDER record, so grep
  # the CONTENT too; the name alone missed three cuts deployed under DEPLOY-ORDER-3 (12:17Z).
  ls $P/harness-work/FIXER/ 2>/dev/null | grep -q "HARNESS-$s-" && continue
  grep -rqF "$s" $P/harness-work/FIXER/ 2>/dev/null && continue
  echo "  $s"
done
echo "== cuts PATCH with no verdict anywhere =="
for f in /home/mboyle/swarm-cuts/cut/*/DONE.md; do c=$(basename "$(dirname "$f")")
  head -1 "$f" 2>/dev/null | grep -q PATCH || continue
  # swarm-review-prep.sh:84 names the review home row<stem>-local, so a cut NOT already called row*
  # lives at rowregister-122-close-local. Globbing <cut>-local alone read an empty path for every
  # non-row cut and inflated this list from 28 to 52 (swarm-integrator-C-B, REPORT-O1155b2, 12:38Z).
  n=$(ls /home/mboyle/swarm-review-wt/$c-local/.review/VERDICT-*.md \
         /home/mboyle/swarm-review-wt/row$c-local/.review/VERDICT-*.md 2>/dev/null | wc -l)
  sp=$(ls $P/verdicts/$c-VERDICT-*.md 2>/dev/null | wc -l)
  [ "$n" -eq 0 ] && [ "$sp" -eq 0 ] && echo "  $c $(stat -c %y "$f" | cut -c1-16)"
done
echo "== REFUTE/BOUNCE verdicts, newest first =="
grep -l '^VERDICT: \(REFUTE\|BOUNCE\)' $P/verdicts/*.md /home/mboyle/swarm-review-wt/*/.review/VERDICT-*.md 2>/dev/null |
  xargs -r ls -t 2>/dev/null | head -5 | sed 's/^/  /'
echo "== seats: BUSY n / IDLE list =="
busy=0; idle=""
for s in $(tmux ls -F '#{session_name}' 2>/dev/null | grep -E '^swarm-(worker|cx-worker|review|integrator|trainer|triage|agy-lens|agy-briefauthor)'); do
  t=$(tmux capture-pane -p -t "$s" 2>/dev/null | tail -6)
  # The footer is TRUNCATED to the pane width, so "esc to interrupt" arrives as "esc to inter…".
  # Matching the full phrase reported 15 busy seats as idle (measured 12:4xZ). Match the prefix, and
  # match the elapsed-timer line every Claude/Codex spinner prints ("… (3m 51s" / "(43m 24s").
  if printf '%s' "$t" | grep -qE 'esc to inter|\([0-9]+m ?[0-9]*s|[0-9]+ (shell|background terminal)'; then busy=$((busy+1)); else idle="$idle $s"; fi
done
echo "  BUSY=$busy IDLE:${idle:- none}"
# THE PM'S OWN INBOX IS THE PASS'S FIRST DUTY (O1155e). swarm-say files non-escalation traffic for any
# swarm-pm-* target into inbox/<seat>/BATCH-*.md and types NOTHING, by design (H471). A PM that reads only
# its pane is blind to it: at 12:47Z nine batches had accumulated unread, holding a REFUTE, a premise
# challenge, a question from swarm-triage-A, a stuck codex seat and four BOARDs. The cursor is a file so
# the drain survives a compaction.
pm_inbox_summary
echo "== quota buckets (O1157) =="
grep -v '^#' $P/state/quota-buckets.tsv 2>/dev/null | awk -F'\t' '$2!="HEALTHY"{print "  *** "$1" "$2" since "$3} END{}' 
grep -cv '^#' $P/state/quota-buckets.tsv 2>/dev/null | sed 's/^/  buckets tracked: /'
echo "== landed / inbox =="
echo "  $(tail -1 $P/trains/landed.tsv | cut -f1,3)"
echo "  inbox/PM newest: $(ls -t $P/inbox/PM/*.md 2>/dev/null | head -1)"
