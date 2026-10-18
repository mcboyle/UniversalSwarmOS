#!/bin/bash
# bd-hot-pin.sh -- O1698 C6 (queue row o1698-hub-ram-pin): keep the hub's hot fleet state in the page cache.
#
# ONE RUN = residency census of the hot set (vmtouch without flags: mincore only, reads no data) -> `vmtouch -t`
# (touch: reads the non-resident pages in) -> census again -> ONE TSV line appended to state/hot-pin.tsv.
# It never locks or daemonizes (no -l/-L/-d): the brief allows a lock only after hub-samples show iowait p99 > 20%
# while residency < 100%, and that has not been measured. -F keeps the walk on the hot set's own filesystem.
#
# rc 0 = touched, measured AND recorded (status OK). rc 2 = COULD NOT LOOK (status COULD-NOT-LOOK): vmtouch missing,
# no hot-set member present, a vmtouch failure or timeout, an unparseable census, a zero-page hot set, or a record
# line that could not be appended (stderr says so: a run that cannot leave its row never reports OK). Each run that
# can write still writes its line, so the 24 h record shows a gap as a row, not a silence.
# Each vmtouch call is bounded by `timeout` (BD_HOT_PIN_STEP_TIMEOUT s) and the unit's TimeoutStartSec bounds the run,
# so a hung call becomes a COULD-NOT-LOOK row and the timer keeps firing.
#
# Env: BD_HOT_PIN_ROOT          hot-set parent           (default /home/mboyle/bd-persist)
#      BD_HOT_PIN_SET           members under ROOT       (default "board inbox role-state queues state claims")
#      BD_HOT_PIN_OUT           TSV record               (default $ROOT/state/hot-pin.tsv)
#      BD_HOT_PIN_VMTOUCH       vmtouch binary           (default: vmtouch on PATH)
#      BD_HOT_PIN_STEP_TIMEOUT  seconds per vmtouch call (default 30; lens measured a cold full hub set at 9.5 s)
# Run by bd-hot-pin.timer every 5 min (user unit). Uses bash builtins plus date, mkdir, timeout and the vmtouch it names.
set -u
ROOT=${BD_HOT_PIN_ROOT:-/home/mboyle/bd-persist}
SET=${BD_HOT_PIN_SET:-board inbox role-state queues state claims}
OUT=${BD_HOT_PIN_OUT:-$ROOT/state/hot-pin.tsv}
VMT=${BD_HOT_PIN_VMTOUCH:-$(command -v vmtouch)}
STEP=${BD_HOT_PIN_STEP_TIMEOUT:-30}
HEADER=$'# utc\tstatus\tfiles\tpages\tresident_before\tpct_before\tresident_after\tpct_after\tmissing\tdetail'
UTC=$(date -u +%FT%TZ)

paths=(); missing=()
for name in $SET; do
  if [ -e "$ROOT/$name" ]; then paths+=("$ROOT/$name"); else missing+=("$name"); fi
done
MISSING=${missing[*]:--}

emit() {  # status files pages res_before pct_before res_after pct_after detail -> stdout + one appended line
  local line rc=1
  printf -v line '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s' "$UTC" "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$MISSING" "${8//$'\t'/ }"
  printf '%s\n' "$line"
  if mkdir -p -- "${OUT%/*}" 2>/dev/null; then
    if [ -s "$OUT" ]; then printf '%s\n' "$line" 2>/dev/null >> "$OUT"; else printf '%s\n%s\n' "$HEADER" "$line" 2>/dev/null >> "$OUT"; fi
    rc=$?
  fi
  if [ "$rc" -ne 0 ]; then  # the row is the product: a run that cannot leave it is COULD NOT LOOK, never OK
    echo "bd-hot-pin: COULD NOT LOOK: cannot append the record line to $OUT (status was $1)" >&2
    exit 2
  fi
}

vmt() {  # one bounded vmtouch call; rc 124 = it ran past STEP seconds (-k: KILL 5 s after the TERM)
  timeout -k 5 "$STEP" "$VMT" "$@"
}

why() {  # rc -> "rc=N" plus the timeout reading for 124
  if [ "$1" -eq 124 ]; then echo "rc=124 (timed out after ${STEP}s)"; else echo "rc=$1"; fi
}

could_not_look() {  # detail [files pages res_before pct_before]
  emit COULD-NOT-LOOK "${2:--}" "${3:--}" "${4:--}" "${5:--}" - - "$1"
  echo "bd-hot-pin: COULD NOT LOOK: $1" >&2
  exit 2
}

CENSUS_FILES=; CENSUS_RES=; CENSUS_PAGES=; CENSUS_ERR=
census() {  # sets CENSUS_FILES / CENSUS_RES / CENSUS_PAGES from vmtouch's summary; returns 1 when it cannot
  local out rc re_files='^ *Files: ([0-9]+)' re_res='^ *Resident Pages: ([0-9]+)/([0-9]+) '
  CENSUS_FILES=; CENSUS_RES=; CENSUS_PAGES=
  out=$(vmt -F -- "${paths[@]}" 2>&1); rc=$?
  [ "$rc" -eq 0 ] || { CENSUS_ERR="vmtouch census $(why "$rc")"; return 1; }
  while IFS= read -r l; do
    [[ $l =~ $re_files ]] && CENSUS_FILES=${BASH_REMATCH[1]}
    [[ $l =~ $re_res ]] && { CENSUS_RES=${BASH_REMATCH[1]}; CENSUS_PAGES=${BASH_REMATCH[2]}; }
  done <<< "$out"
  [ -n "$CENSUS_FILES" ] && [ -n "$CENSUS_PAGES" ] || { CENSUS_ERR="unparseable vmtouch census"; return 1; }
  [ "$CENSUS_PAGES" -gt 0 ] || { CENSUS_ERR="hot set has zero pages"; return 1; }   # before AND after: no division by 0
}

[ -n "$VMT" ] && [ -x "$VMT" ] || could_not_look "vmtouch not found${VMT:+ at $VMT}"
[ "${#paths[@]}" -gt 0 ] || could_not_look "no hot-set member under $ROOT ($SET)"
census || could_not_look "$CENSUS_ERR (before)" "${CENSUS_FILES:--}" "${CENSUS_PAGES:--}" "${CENSUS_RES:--}"
files=$CENSUS_FILES; pages=$CENSUS_PAGES; before=$CENSUS_RES
pct_before=$(( before * 100 / pages ))
vmt -t -F -q -- "${paths[@]}" > /dev/null 2>&1
rc=$?
[ "$rc" -eq 0 ] || could_not_look "vmtouch -t $(why "$rc")" "$files" "$pages" "$before" "$pct_before"
census || could_not_look "$CENSUS_ERR (after)" "$files" "$pages" "$before" "$pct_before"
emit OK "$files" "$pages" "$before" "$pct_before" "$CENSUS_RES" "$(( CENSUS_RES * 100 / CENSUS_PAGES ))" "touched ${#paths[@]} member(s)"
