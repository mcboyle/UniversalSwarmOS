#!/bin/bash
# bd-usage-probe.sh -- refresh the usage cache both accounts read. cron */10.
#
# `/usage` is the only thing that updates .cachedUsageUtilization, so the
# predictive half of the sentinel is only as fresh as this probe. It types into
# ONE designated pane per pool and nothing else.
#
# IT TYPES INTO A LIVE SESSION, so every guard here is about not disturbing one:
# it refuses unless the pane is at an EMPTY prompt with no work running, it
# closes the panel it opened, and if the pane is not back at an empty prompt
# afterwards it writes usage-probe.stuck and NEVER TOUCHES THAT PANE AGAIN until
# a human removes the file. A probe that leaves a session wedged costs more than
# the freshness it buys.
set -u
P=${BD_PERSIST:-/home/mboyle/bd-persist}
USAGE=${BD_USAGE_TSV:-$P/USAGE.tsv}
STUCK=${BD_USAGE_STUCK:-$P/usage-probe.stuck}
# CANDIDATE LISTS, first idle pane wins. A single designated pane is a single
# point of failure: measured 04:3x-04:4xZ, pool B's only candidate (bd-status)
# was "working" or "prompt not empty" on EVERY tick, so B never refreshed and the
# sentinel read UNKNOWN with the probe cron running perfectly. Pool A refreshed
# every tick because its pane does nothing but this.
# ---- CANDIDATES ARE RESOLVED FROM THE ROLE REGISTRY, NOT TYPED. Fixed 2026-09-09.
# ** THE HARDCODED NAMES HAD ALREADY GONE STALE, AND SILENTLY. ** This probe looked for panes
# literally called `usage-a` / `usage-b` / `bd-status`. The smoke test launched the usage seats as
# bd-usage-a-A and bd-usage-B under the derived -A/-B naming, so THE PROBE WOULD HAVE MATCHED
# NOTHING: both pools keep reading UNKNOWN with the probe cron running perfectly -- which is
# word for word the failure this file's own comments record from 2026-09-07 04:3xZ.
# A HAND-MAINTAINED SEAT NAME IS A FACT WITH AN EXPIRY NOBODY WATCHES. Ask who holds the role.
# THE POOL IS READ FROM THE SEAT NAME'S SUFFIX, which is exactly why the launcher derives it.
RCLAIM=${BD_USAGE_ROLE_CLAIM:-/home/mboyle/bd-role-claim.sh}
resolve_panes() {   # $1 = A or B
  local suffix=-$1 out=""
  if [ -x "$RCLAIM" ]; then
    out=$("$RCLAIM" who-all 2>/dev/null | awk -F'\t' '$1 ~ /^usage/ {print $2}' \
          | while IFS= read -r seat; do case "$seat" in *"$suffix") printf '%s ' "$seat" ;; esac; done)
  fi
  printf '%s' "$out"
}
# The literal names remain as a FALLBACK ONLY, so a registry that cannot be read degrades to the old
# behaviour instead of to nothing. An empty candidate list is reported, never treated as "no work".
PANE_A=${BD_USAGE_PANE_A:-$(resolve_panes A)}
PANE_B=${BD_USAGE_PANE_B:-$(resolve_panes B)}
# H505 (O668): the registry can be EMPTY while the seats are up (every row was reaped at 20:4xZ 2026-09-14 with
# every session live; POOL_STATE read UNKNOWN for 5 h). The fallback is the launcher's DERIVED name shape,
# read from tmux itself, never a typed literal: `usage-a`/`usage-b` had already been stale for a week.
# WARNED every tick it is used, so a hollow registry is visible in the cron log instead of silently routed around.
fallback_panes() {   # $1 = A or B -> live tmux sessions named bd-usage*-<pool>
  ${BD_USAGE_TMUX:-tmux} list-sessions -F '#S' 2>/dev/null < /dev/null | grep -E "^bd-usage.*-$1$" | tr '\n' ' '; }
for _p in A B; do
  eval "_v=\$PANE_$_p"
  [ -n "$_v" ] && continue
  _v=$(fallback_panes "$_p")
  [ -n "$_v" ] && echo "WARN REGISTRY-EMPTY $_p: no usage role holder in ROLE-OCCUPANCY; falling back to tmux names [$_v] (H505)" >&2
  eval "PANE_$_p=\$_v"
done; unset _p _v
[ -n "$PANE_A" ] || PANE_A="usage-a"
[ -n "$PANE_B" ] || PANE_B="usage-b"
# 2026-09-12: ONLY A PANE THIS PROBE OWNS IS EVER TYPED INTO. bd-status was a shared pane and is gone from the
# fallback; the registry answer is ALSO filtered so a mis-claimed role can never route /usage into a PM,
# worker, lens or the operator-driven capture seat (FLEET_RULE 21).
DENY_RE=${BD_USAGE_DENY_RE:-"^(BD-PM|bd-cx-|bd-cl-|bd-PM|bd-capture|bd-adjudic|bd-integr|bd-worker|bd-review|bd-trainer)"}
filter_panes() { local out=""; for c in $1; do case "$c" in *usage*) printf "%s" "$c" | grep -qE "$DENY_RE" || out="$out $c";; esac; done; printf "%s" "$out"; }
PANE_A=$(filter_panes "$PANE_A"); PANE_B=$(filter_panes "$PANE_B")
_DEDICATED_PANES="${BD_USAGE_DEDICATED:-usage-a usage-b $PANE_A $PANE_B}"
CACHE_A=${BD_USAGE_CACHE_A:-/home/mboyle/.claude.json}
CACHE_B=${BD_USAGE_CACHE_B:-/home/mboyle/.claude-b/.claude.json}
SETTLE=${BD_USAGE_SETTLE:-8}
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)

fetched_ms() { python3 -c "
import json,sys
try: print(int(json.load(open(sys.argv[1]))['cachedUsageUtilization']['fetchedAtMs']))
except Exception: print(0)" "$1" 2>/dev/null || echo 0; }

row() { python3 - "$1" "$2" "$3" <<'PY' 2>/dev/null || printf '%s\tUNKNOWN\t-\t-\t-\t%s\n' "$1" "$3"
import json,sys,datetime
pool,f,now=sys.argv[1],sys.argv[2],sys.argv[3]
u=json.load(open(f))["cachedUsageUtilization"]["utilization"]
# H452 (15:0xZ): resets_at is null right after a window resets (A read 0%/null at 14:53Z) and the join raised ->
# the row fell to UNKNOWN, which FLEET_RULE 29 treats as an unseen limit. A null reset is "-", the figure is real.
print("\t".join([pool,str(u["five_hour"]["utilization"]),str(u["five_hour"].get("resets_at") or "-"),
                 str(u["seven_day"]["utilization"]),str(u["seven_day"].get("resets_at") or "-"),now]))
PY
}

# A pane whose ONLY job is this probe (usage-a / usage-b). A fresh Claude pane
# shows a rotating PLACEHOLDER inside its empty input box -- `❯ Try "fix
# typecheck errors"` -- which is not typed input. On a pane we own that is
# definitionally empty; on a SHARED pane (bd-status) it is not safe to assume,
# so the strict rule stands there and the probe simply skips the tick.

# O945 (2026-09-20): Claude Code draws a DIM prompt-suggestion GHOST on the live prompt line
# ("❯ check inbox for new dispatch", "❯ Press up to edit queued messages"). A plain `capture-pane -p`
# renders it as typed-but-unsubmitted text. Capture with `-e` and blank every \e[2m ... \e[0m|\e[22m run
# before reading the ❯ line; real typed input is never dim. Also strips remaining SGR and the U+00A0
# prompt separator, so callers keep their `^❯ +$` empty-prompt tests.
_o945_strip_ghost() {
  sed -E 's/\x1b\[(2|2;[0-9;]+|[0-9;]+;2)m(\x1b\[([1-9]|1[0-9]|2[013-9]|[3-9][0-9]|38;[0-9;]+|48;[0-9;]+)m|[^\x1b])*\x1b\[(0|22)(;[0-9;]+)?m//g; s/\x1b\[[0-9;?]*[A-Za-z]//g; s/\xc2\xa0/ /g'
}

# H749: `capture-pane -J` joins a line wider than the pane (a marker split across rows never matched), but it keeps
# the trailing padding and, with -e, carries the SGR state over the newline (the close lands at the head of the next
# line, so a dim ghost is no longer closed on its own line). Re-close each line as the unjoined capture did and trim
# the padding: an unwrapped line comes out as `capture-pane -e -p` printed it.
_h749_trim_e() {
  LC_ALL=C awk '
    function sgr(p,  t, n, i, k) {
      n = split(p, t, ";")
      for (i = 1; i <= n; i++) {
        k = t[i]
        if (k == "" || k == "0") { split("", A); fg = "39"; bg = "49"; us = "59" }
        else if (k ~ /^([1-9]|53|4:[1-5])$/) A[k] = 1
        else if (k == "22") { delete A["1"]; delete A["2"] }
        else if (k ~ /^(24|4:0)$/) { delete A["4"]; delete A["4:2"]; delete A["4:3"]; delete A["4:4"]; delete A["4:5"] }
        else if (k ~ /^2[35789]$/) delete A[substr(k, 2)]
        else if (k == "55") delete A["53"]
        else if (k ~ /^(3[0-79]|9[0-7])$/ || k ~ /^38:/) fg = k
        else if (k ~ /^(4[0-79]|10[0-7])$/ || k ~ /^48:/) bg = k
        else if (k == "59" || k ~ /^58:/) us = k
        else if (k ~ /^[345]8$/ && t[i+1] == "5") { k = k ";5;" t[i+2]; i += 2 }
        else if (k ~ /^[345]8$/ && t[i+1] == "2") { k = k ";2;" t[i+2] ";" t[i+3] ";" t[i+4]; i += 4 }
        if (k ~ /^38;/) fg = k; else if (k ~ /^48;/) bg = k; else if (k ~ /^58;/) us = k
      }
    }
    function sgr_open(  s, j) {
      s = ""
      for (j = 1; j <= nord; j++) if (ORD[j] in A) s = s (s == "" ? "" : ";") ORD[j]
      s = (s == "" ? "" : "\033[" s "m")
      if (fg != "39") s = s "\033[" fg "m"
      if (bg != "49") s = s "\033[" bg "m"
      if (us != "59") s = s "\033[" us "m"
      return s
    }
    function sgr_close(  k) {
      for (k in A) return "\033[0m"
      if (us != "59") return "\033[0m"
      return (fg != "39" ? "\033[39m" : "") (bg != "49" ? "\033[49m" : "")
    }
    BEGIN { nord = split("1 2 3 4 5 7 8 9 4:2 4:3 4:4 4:5 53", ORD, " "); sgr("0") }
    {
      rest = $0; out = ""; lit = 0
      while (rest != "") {
        if (match(rest, /\033\[[0-9;:]*m/)) { pre = substr(rest, 1, RSTART - 1); seq = substr(rest, RSTART, RLENGTH); rest = substr(rest, RSTART + RLENGTH) }
        else { pre = rest; seq = ""; rest = "" }
        if (pre != "") { if (!lit) out = sgr_open(); lit = 1; out = out pre }
        if (seq != "") { if (lit) out = out seq; sgr(substr(seq, 3, length(seq) - 3)) }
      }
      if (lit) out = out sgr_close()
      sub(/ +$/, "", out); print out
    }'
}

idle_pane() {  # a pane is probe-able only at an EMPTY live prompt with no work
  local s=$1 cap last dedicated=0
  for d in $_DEDICATED_PANES; do [ "$d" = "$s" ] && dedicated=1; done
  tmux has-session -t "=$s" 2>/dev/null || { echo "no session"; return 1; }
  # U+00A0 is the prompt separator, not an ASCII space -- an empty prompt is
  # "❯\u00a0" and every naive ^❯ +$ test calls it non-empty and never probes.
  # O945: -e + ghost strip -- the dim suggestion ghost is blanked, so an idle box reads as `❯ ` (empty).
  cap=$(tmux capture-pane -J -e -pt "$s:" -S -40 2>/dev/null | _h749_trim_e | _o945_strip_ghost) || { echo "capture failed"; return 1; }
  printf '%s\n' "$cap" | grep -qE 'esc to interrupt|\([0-9]+m [0-9]+s|\([0-9]+s ·' && { echo "working"; return 1; }
  last=$(printf '%s\n' "$cap" | grep '^❯' | tail -1)
  [ -n "$last" ] || { echo "no prompt"; return 1; }
  if printf '%s' "$last" | grep -qE '^❯ +$|^❯$'; then return 0; fi
  if [ "$dedicated" = 1 ] && printf '%s' "$last" | grep -qE '^❯ +Try "[^"]*"$'; then
    return 0   # the placeholder hint in an empty box on a pane we own
  fi
  # O945: the DIM suggestion ghost was already blanked by _o945_strip_ghost above (any pane, not only
  # dedicated ones): a bare `❯` here means EMPTY. Anything still left after the strip is real typed text.
  echo "prompt not empty"; return 1
}

probe() { # pool "pane [pane...]" cache -> prints a USAGE.tsv row
  local pool=$1 candidates=$2 cache=$3 why before after pane="" skipped=""
  if [ -f "$STUCK" ]; then
    # 2026-09-12: a stuck marker EXPIRES (default 30 min) -- one wedged tick froze both pools for 48 h
    # (2026-09-10T23:40Z -> 2026-09-12) with nobody watching the file. Reported once, then cleared.
    local age=$(( $(date -u +%s) - $(stat -c %Y "$STUCK" 2>/dev/null || echo 0) ))
    if [ "$age" -ge "${BD_USAGE_STUCK_TTL:-1800}" ]; then
      echo "STUCK-EXPIRED $pool: $(head -1 "$STUCK") -- ${age}s old, clearing and retrying" >&2; rm -f "$STUCK" "$STUCK.reported"
    else
      printf '%s\tUNKNOWN\t-\t-\t-\t%s\n' "$pool" "$NOW"
      [ -f "$STUCK.reported" ] || { echo "SKIP $pool: $STUCK present ($(head -1 "$STUCK")); expires in $(( ${BD_USAGE_STUCK_TTL:-1800} - age ))s" >&2; : > "$STUCK.reported"; }
      return
    fi
  fi
  # If the cache is ALREADY fresh there is nothing to buy by typing into a live
  # pane, and `/usage` does not re-fetch when called again straight away -- which
  # showed up as NOT-REFRESHED/UNKNOWN a minute after a good cron tick. Report
  # the row we already have.
  local age_ms now_ms
  now_ms=$(( $(date -u +%s) * 1000 )); age_ms=$(( now_ms - $(fetched_ms "$cache") ))
  # 300s, and the number is load-bearing: it must sit WELL BELOW the 600s cron
  # interval. At 600s it raced the tick -- measured "FRESH A: cache 598s old,
  # not typing into a pane", after which the cache aged to ~1198s and crossed
  # the sentinel's 900s staleness bound, so the skip produced the very UNKNOWN
  # it was added to avoid. At 300s a tick always refreshes anything older than
  # half the interval, so the cache can never reach 900s.
  if [ "$age_ms" -lt "${BD_USAGE_FRESH_MS:-300000}" ] 2>/dev/null; then
    row "$pool" "$cache" "$NOW"
    echo "FRESH $pool: cache $((age_ms/1000))s old, not typing into a pane" >&2; return
  fi
  for c in $candidates; do
    if why=$(idle_pane "$c"); then pane=$c; break; fi
    skipped="$skipped $c($why)"
  done
  [ -n "$pane" ] || {
    printf '%s\tUNKNOWN\t-\t-\t-\t%s\n' "$pool" "$NOW"
    echo "SKIP $pool: no idle candidate --$skipped" >&2; return; }
  before=$(fetched_ms "$cache")
  tmux send-keys -t "=$pane:" -l "/usage" && sleep 1 && tmux send-keys -t "=$pane:" Enter || {
    printf '%s\tUNKNOWN\t-\t-\t-\t%s\n' "$pool" "$NOW"; echo "SEND-FAILED $pool/$pane" >&2; return; }
  sleep "$SETTLE"
  tmux send-keys -t "=$pane:" Escape; sleep 2
  # 2026-09-12: a DIALOG (permission / trust / y-n / selection) is the bd-say rc=6 shape: back off with a second
  # Escape and re-check before ever writing the stuck marker.
  if tmux capture-pane -J -pt "$pane:" -S -30 2>/dev/null | sed 's/ *$//' | grep -qiE "esc to cancel|\(y/n\)|Yes, |No, |Allow|Deny|Do you trust|Press Enter|Select"; then
    echo "DIALOG $pool/$pane: backing off with Escape" >&2; tmux send-keys -t "=$pane:" Escape; sleep 2
  fi
  if ! idle_pane "$pane" >/dev/null; then
    printf '%s %s/%s did not return to an empty prompt after /usage\n' "$NOW" "$pool" "$pane" > "$STUCK"
    printf '%s\tUNKNOWN\t-\t-\t-\t%s\n' "$pool" "$NOW"
    echo "PROBE-STUCK $pool/$pane -- wrote $STUCK; no further probes until it is cleared" >&2; return
  fi
  after=$(fetched_ms "$cache")
  if [ "$after" -le "$before" ] 2>/dev/null; then
    printf '%s\tUNKNOWN\t-\t-\t-\t%s\n' "$pool" "$NOW"
    echo "NOT-REFRESHED $pool: fetchedAtMs did not advance ($before -> $after)" >&2; return
  fi
  row "$pool" "$cache" "$NOW"
}

TMP=$(mktemp "${USAGE}.XXXXXX") || { echo "bd-usage-probe: cannot write beside $USAGE"; exit 4; }
# Legacy columns remain percentages USED; appended columns are REMAINING.
codex_row() { local out win used age resets five=- weekly=- fr=- wr=-
  out=$(bash "$P/harness/bd-codex-usage.sh" --windows 2>/dev/null) || out=""
  while read -r win used age resets; do
    case "$win" in
      300) five=$used; fr=$(date -u -d "@$resets" +%FT%TZ 2>/dev/null || echo -);;
      10080) weekly=$used; wr=$(date -u -d "@$resets" +%FT%TZ 2>/dev/null || echo -);;
    esac
  done <<<"$out"
  printf 'codex\t%s\t%s\t%s\t%s\t%s\n' "$five" "$fr" "$weekly" "$wr" "$NOW"
}
agy_row() { local g5 gw c5 cw observed five=- weekly=-
  python3 - <<'AGY_PY' 2>/dev/null || true
import subprocess, re, datetime, os
qfile = "/home/mboyle/bd-persist/AGY-QUOTA.tsv"
stale = True
if os.path.exists(qfile):
    try:
        age = datetime.datetime.now().timestamp() - os.path.getmtime(qfile)
        if age < 300: stale = False
    except Exception: pass
if stale:
    res = subprocess.run(["agy", "-p", "/usage"], capture_output=True, text=True, timeout=15)
    g_5h = g_wk = c_5h = c_wk = None
    for line in res.stdout.splitlines():
        m = re.search(r"(Gemini Models|Claude and GPT models)\s+(Weekly Limit Remaining|Five Hour Limit Remaining)\s+([0-9]+)%\s+(\S+)", line)
        if m:
            group, limit_type, pct, resets = m.groups()
            if group == "Gemini Models":
                if "Five Hour" in limit_type: g_5h = pct
                elif "Weekly" in limit_type: g_wk = pct
            elif group == "Claude and GPT models":
                if "Five Hour" in limit_type: c_5h = pct
                elif "Weekly" in limit_type: c_wk = pct
    if all(x is not None for x in [g_5h, g_wk, c_5h, c_wk]):
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        header = "measured_at\tgemini_five_hour_remaining_pct\tgemini_weekly_remaining_pct\tclaude_gpt_five_hour_remaining_pct\tclaude_gpt_weekly_remaining_pct\n"
        row = f"{now_iso}\t{g_5h}\t{g_wk}\t{c_5h}\t{c_wk}\n"
        with open(qfile, "w") as f: f.write(header + row)
AGY_PY
  IFS=$'\t' read -r g5 gw c5 cw observed < <(bash "$P/harness/bd-agy-usage.sh" --remaining)
  if [ "${g5:--}" != - ]; then five=$(awk -v x="$g5" 'BEGIN {print 100-x}'); fi
  if [ "${gw:--}" != - ]; then weekly=$(awk -v x="$gw" 'BEGIN {print 100-x}'); fi
  printf 'AGY\t%s\t-\t%s\t-\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$five" "$weekly" "$NOW" "${g5:--}" "${g5:--}" "${gw:--}" "${c5:--}" "${cw:--}" "${observed:--}"
}
# Enrich all legacy rows once; do not reinterpret unknown or weekly figures as 5h.
usage_fields() {
  awk 'BEGIN {FS=OFS="\t"}
    NR==1 {print $0,"five_hour_remaining_pct","gemini_five_hour_remaining_pct","gemini_weekly_remaining_pct","claude_gpt_five_hour_remaining_pct","claude_gpt_weekly_remaining_pct","quota_observed_at"; next}
    NF==6 {left="-"; if ($2 ~ /^[0-9]+([.][0-9]+)?$/ && $2<=100) left=100-$2; print $0,left,"-","-","-","-","-"; next}
    {print}'
}

{
  printf 'pool\tfive_hour_pct\tresets_at\tweekly_pct\tweekly_resets\tfetched_at\n'
  probe A "$PANE_A" "$CACHE_A"
  probe B "$PANE_B" "$CACHE_B"
  [ "${BD_USAGE_PROBE_EXTRA_POOLS:-1}" = 1 ] && { codex_row; agy_row; }
} | usage_fields > "$TMP"
chmod 0600 "$TMP" && mv -f "$TMP" "$USAGE" || { rm -f "$TMP"; echo "bd-usage-probe: replace failed"; exit 4; }
awk -F'\t' 'NR>1 {printf "%s=%s%%/%s%%w ", $1, $2, $4}' "$USAGE"; echo   # 5h%/weekly%w (H394: weekly was only in the tsv)
