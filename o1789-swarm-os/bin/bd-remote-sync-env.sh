#!/usr/bin/env bash
# bd-remote-sync-env.sh -- sync agent skills and pre-tool hooks to the hosts that RUN remote seats; report every host.
# remote-env-r1 (WORD O2596 P2; dispatch A-dispatch-FX243-mount-reading.md, reading B). Base: phase-2 bytes 28ddb639.
# remote-env-r1b: comments only -- the APPLY GATE is a binding/accident guard, not an authority (PM-D A-pm-D-remote-env-WORD-gate.md).
# remote-env-r2: caller overrides are test-only (BD_TEST=1); the probe imports with python -B; pip is gated on the venv's
#   lib/site-packages and bin as well as the venv dir; a tmux read error other than a real no-server is COULD-NOT-LOOK
#   (post-hoc F1, cx37: "error connecting to ... (Permission denied)" read as no sessions made a live host STALE, exit 0).
#
# usage: bd-remote-sync-env.sh [--host H]... [--apply WORD-FILE]
#   DEFAULT = DRY RUN: every target is probed READ-ONLY; prints BEFORE, the drift, the PLAN, then AFTER (a second probe that
#     must equal BEFORE). Nothing is written anywhere.
#   --host H   restrict the run to H. H must be a derived target; --host never adds a host.
#   --apply W  write, bound to the word file W (APPLY GATE below). Without a valid W: REFUSED, exit 3, before any ssh.
#              Only the PM runs --apply, on a PM word, after BOARD x2.
#
# TARGETS (rule 8): derived, never handed. Registry = $BD_SEAT_HOSTS read by bd_remote_map of lib_remote_seat.sh (O1664;
#   last row per seat wins, "-" = hub). A host is a TARGET when its own tmux holds >=1 session the registry places there;
#   a registry host with none of its seats running is STALE (listed, never written). A host that cannot answer is
#   COULD-NOT-LOOK (rule 6), never "no seats".
# APPLY GATE -- a BINDING / ACCIDENT guard, NOT an authority boundary.
#   W is a regular file (not a symlink) under $BD_SYNC_WORD_ROOT, named WORD-pm-*.md, carrying exactly one line
#     APPLY bd-remote-sync-env sha256=<sha256 of THIS script's bytes> hosts=<h1,h2,...>
#   It binds the exact script bytes and host list, so a stray or old invocation cannot apply. Only hosts both derived AND
#   named in the word are written; the rest are listed. It grants no reach: any seat already reaches these hosts over ssh
#   as mboyle, and any seat that can write harness-work can write W. The AUTHORITY is the PM running --apply on a PM word
#   after BOARD x2.
# MOUNT GATE (reading B): every WRITE PATH is resolved (readlink -f; findmnt -T on the nearest existing ancestor).
#   The host is REFUSED when ~ is read-only or a network fs. A step is REFUSED when its path resolves read-only, onto a
#   network fs, under /mnt/bd*, or inside /home/mboyle/bd-persist. bd-persist's own mount is reported per host, never written.
#   pip is gated on the venv dir AND its lib*/python*/site-packages AND bin (a local venv whose lib or bin links to NFS).
# PER HOST: import ruff + mypy in ~/BulkDownloader/venv; skill counts (~/.agents ~/.claude ~/.codex skills); sha256 of
#   ~/.claude/settings.json and ~/.codex/hooks.json; MISSING-SKILL / EXTRA-SKILL per name against the hub's ~/.agents/skills.
#   Every write prints its rc; nothing is swallowed. No --delete: a remote-only skill is reported EXTRA, never removed.
#   rsync --checksum: a differing file of the same size and mtime is still sent (the quick check skips it).
#   pip runs only when an import fails.
# EXIT: 0 clean; 1 dry run found drift (a write is planned); 3 refused (usage, apply gate, --host not a target);
#   4 COULD NOT LOOK (registry, hub source, a host); 5 a host or step REFUSED or FAILED (the other hosts still run).
set -uo pipefail

SRC=${BD_SYNC_SRC:-/home/mboyle}
WORD_ROOT=${BD_SYNC_WORD_ROOT:-/home/mboyle/bd-persist/harness-work}
LIB=${BD_REMOTE_SEAT_LIB:-/home/mboyle/bd-persist/harness/lib_remote_seat.sh}
BDP=${BD_SYNC_BDP:-/home/mboyle/bd-persist}   # the hub share as the host sees it; never written
SSHO=(-o BatchMode=yes -o ConnectTimeout="${BD_REMOTE_TIMEOUT:-5}")

die(){ echo "$2"; echo "EXIT $1"; exit "$1"; }
is_sha(){ [ "${#1}" = 64 ] && case $1 in *[!0123456789abcdef]*) false ;; esac; }

# ---- CALLER OVERRIDES are TEST-ONLY (remote-env-r2). Each one redirects the hub source, the word root, the registry
#   lib/file or the share the gate excludes: honoured on a live run, the ENVIRONMENT (not the PM word) would choose what is
#   copied from where to which hosts. Refused before anything is read or any ssh runs, unless BD_TEST=1 names a rig. ----
for v in BD_SYNC_SRC BD_SYNC_WORD_ROOT BD_REMOTE_SEAT_LIB BD_SYNC_BDP BD_SEAT_HOSTS; do
  [ -n "${!v:-}" ] && [ "${BD_TEST:-}" != 1 ] && die 3 "REFUSED: $v is a test-only override (set BD_TEST=1 only in a rig; a live run takes the defaults)"
done

APPLY=0 WORD="" ONLY=()
while [ $# -gt 0 ]; do
  case $1 in
    --apply) [ $# -ge 2 ] || die 3 "REFUSED --apply: no PM word file named (usage: --apply WORD-FILE)"; APPLY=1 WORD=$2; shift 2 ;;
    --host) [ $# -ge 2 ] || die 3 "REFUSED --host: no host named"; ONLY+=("$2"); shift 2 ;;
    *) die 3 "REFUSED: unknown argument '$1' (a host list is never handed; targets are derived)" ;;
  esac
done

# ---- APPLY GATE: before any ssh ----
WORD_HOSTS=""
if [ "$APPLY" = 1 ]; then
  [ -f "$WORD" ] && [ ! -L "$WORD" ] || die 3 "REFUSED --apply: $WORD is not a regular file (a symlink or missing)"
  wr=$(readlink -f -- "$WORD") && root=$(readlink -f -- "$WORD_ROOT") || die 3 "REFUSED --apply: cannot resolve $WORD or $WORD_ROOT"
  case $wr in "$root"/*) ;; *) die 3 "REFUSED --apply: $WORD is not under $WORD_ROOT" ;; esac
  case ${wr##*/} in WORD-pm-*.md) ;; *) die 3 "REFUSED --apply: ${wr##*/} is not a PM word (WORD-pm-*.md)" ;; esac
  n=$(grep -c '^APPLY bd-remote-sync-env ' "$wr")
  [ "$n" = 1 ] || die 3 "REFUSED --apply: $n APPLY bd-remote-sync-env lines in $WORD (exactly 1 required)"
  line=$(grep '^APPLY bd-remote-sync-env ' "$wr")
  set -f; set -- $line; set +f
  [ $# = 4 ] && [ "${3%%=*}" = sha256 ] && [ "${4%%=*}" = hosts ] || die 3 "REFUSED --apply: APPLY line is not 'APPLY bd-remote-sync-env sha256=<64 hex> hosts=<h,...>'"
  want=${3#sha256=} WORD_HOSTS=${4#hosts=}
  is_sha "$want" || die 3 "REFUSED --apply: the word's sha256 is not 64 lowercase hex"
  self=$(readlink -f -- "${BASH_SOURCE[0]}") && have=$(sha256sum < "$self") || die 3 "REFUSED --apply: cannot hash this script"
  have=${have%% *}
  [ "$have" = "$want" ] || die 3 "REFUSED --apply: the word names sha256 $want, these bytes are $have"
  [ -n "$WORD_HOSTS" ] || die 3 "REFUSED --apply: the word names no host"
  case $WORD_HOSTS in *[!0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.,_-]*) die 3 "REFUSED --apply: hosts= holds a character outside [A-Za-z0-9.,_-]" ;; esac
  echo "MODE apply word=$wr sha256=$have hosts=$WORD_HOSTS"
else
  echo "MODE dry-run (nothing is written; --apply WORD-FILE writes on a PM word)"
fi

# ---- HUB SOURCE ----
[ -d "$SRC/.agents/skills" ] || die 4 "COULD-NOT-LOOK hub source $SRC/.agents/skills is not a directory"
list_skills(){ local e; for e in "$1"/* "$1"/.[!.]* "$1"/..?*; do
  { [ -e "$e" ] || [ -L "$e" ]; } || continue; [ "${e##*/}" = .git ] && continue; printf '%s\n' "${e##*/}"; done | LC_ALL=C sort; }
SRC_SKILLS=$(list_skills "$SRC/.agents/skills")
src_sha(){ local h; [ -f "$1" ] || { echo absent; return; }; h=$(sha256sum < "$1") || { echo unreadable; return; }; echo "${h%% *}"; }
SRC_CLAUDE=$(src_sha "$SRC/.claude/settings.json"); SRC_CODEX=$(src_sha "$SRC/.codex/hooks.json")
echo "SOURCE $SRC skills=$(printf '%s' "$SRC_SKILLS" | grep -c .) claude=$SRC_CLAUDE codex=$SRC_CODEX"

# ---- REGISTRY -> candidate hosts ----
[ -r "$LIB" ] || die 4 "COULD-NOT-LOOK remote-seat lib $LIB unreadable"
# shellcheck disable=SC1090
. "$LIB" || die 4 "COULD-NOT-LOOK remote-seat lib $LIB did not load"
unset -f tmux 2>/dev/null   # the lib's routing wrapper; this script asks each host's own tmux over ssh
[ -r "$BD_SEAT_HOSTS" ] || die 4 "COULD-NOT-LOOK registry $BD_SEAT_HOSTS unreadable"
MAP=$(bd_remote_map) || die 4 "COULD-NOT-LOOK bd_remote_map failed on $BD_SEAT_HOSTS"
HOSTS=$(printf '%s\n' "$MAP" | awk -F'\t' 'NF>=2 {print $2}' | LC_ALL=C sort -u)
echo "REGISTRY $BD_SEAT_HOSTS seats-off-hub=$(printf '%s' "$MAP" | grep -c .) hosts=$(printf '%s' "$HOSTS" | grep -c .)"

# ---- the read-only probe (runs on the host as: sh -c '<PROBE>') ----
read -r -d '' PROBE <<'EOF'
res() { p=$1; t=""; while [ ! -e "$p" ] && [ ! -L "$p" ]; do t="/${p##*/}$t"; p=${p%/*}; [ -n "$p" ] || { p=/; break; }; done
  r=$(readlink -f -- "$p") || return 1; printf "%s%s\n" "${r%/}" "$t"; }
mnt() { p=$1; while [ ! -e "$p" ]; do p=${p%/*}; [ -n "$p" ] || p=/; done; findmnt -n -o FSTYPE,OPTIONS -T "$p" 2>/dev/null | head -n 1; }
m1() { if r=$(res "$2") && m=$(mnt "$r") && [ -n "$m" ]; then set -- "$1" "$r" $m; printf "P\tMNT\t%s\t%s\t%s\t%s\n" "$1" "$2" "$3" "$4"
  else printf "P\tMNT\t%s\t%s\t?\t?\n" "$1" "$2"; fi; }
printf "P\tHOME\t%s\n" "$HOME"
m1 home "$HOME"; m1 bdp @BDP@; m1 agents "$HOME/.agents/skills"
m1 claude_settings "$HOME/.claude/settings.json"; m1 codex_hooks "$HOME/.codex/hooks.json"; v="$HOME/BulkDownloader/venv"; m1 venv "$v"
sp=""; for d in "$v"/lib*/python*/site-packages; do [ -d "$d" ] && { sp=$d; break; }; done; m1 venv_lib "${sp:-$v/lib}"; m1 venv_bin "$v/bin"
for d in agents claude codex; do s="$HOME/.$d/skills"; if [ -d "$s" ]; then n=0
  for e in "$s"/* "$s"/.[!.]* "$s"/..?*; do { [ -e "$e" ] || [ -L "$e" ]; } || continue; [ "${e##*/}" = .git ] && continue; n=$((n+1))
    [ "$d" = agents ] && printf "P\tSKILL\t%s\n" "${e##*/}"; done; printf "P\tSKILLS\t%s\t%s\n" "$d" "$n"
  else printf "P\tSKILLS\t%s\tabsent\n" "$d"; fi; done
for f in claude:.claude/settings.json codex:.codex/hooks.json; do p="$HOME/${f#*:}"
  if [ -f "$p" ]; then h=$(sha256sum < "$p") && h=${h%% *} || h=unreadable; else h=absent; fi; printf "P\tHOOK\t%s\t%s\n" "${f%%:*}" "$h"; done
py="$HOME/BulkDownloader/venv/bin/python"
for m in ruff mypy; do if [ -x "$py" ]; then "$py" -B -c "import $m" >/dev/null 2>&1; rc=$?; else rc=127; fi; printf "P\tIMPORT\t%s\t%s\n" "$m" "$rc"; done
if command -v tmux >/dev/null 2>&1; then o=$(tmux ls -F "#{session_name}" 2>&1); rc=$?
  if [ "$rc" = 0 ]; then printf "%s\n" "$o" | while IFS= read -r s; do [ -n "$s" ] && printf "P\tTMUX\t%s\n" "$s"; done; printf "P\tTMUXRC\tok\n"
  else case $o in *"no server running"*|*"error connecting to"*"(No such file or directory)"*) printf "P\tTMUXRC\tnone\n" ;;
    *) printf "P\tTMUXRC\tfail\t%s\n" "$(printf "%s" "$o" | head -n 1 | tr "\t" " ")" ;; esac; fi
else printf "P\tTMUXRC\tnotmux\n"; fi
printf "P\tEND\n"
EOF
case $BDP in /*) ;; *) die 3 "REFUSED: BD_SYNC_BDP must be absolute" ;; esac
case $BDP in *[!0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ/._-]*) die 3 "REFUSED: BD_SYNC_BDP holds a character outside [A-Za-z0-9/._-]" ;; esac
PROBE=${PROBE//@BDP@/$BDP}
case $PROBE in *"'"*) die 4 "COULD-NOT-LOOK internal: the probe holds a single quote" ;; esac

declare -A RES FS OPT SK HOOK IMP TM TMRC TMMSG SKN FP
probe(){ # host tag -> fills the arrays under "$1|$2|..."; returns 1 when the host could not be read
  local h=$1 g=$2 out rc k a b c d
  out=$(ssh -n "${SSHO[@]}" "$h" "sh -c '$PROBE'" 2>/dev/null); rc=$?
  [ "$rc" = 0 ] && printf '%s\n' "$out" | grep -qx "P	END" || { echo "COULD-NOT-LOOK $h probe rc=$rc"; return 1; }
  FP[$h|$g]=$(printf '%s\n' "$out" | grep -v '^P	TMUX')
  SK[$h|$g]=""; TM[$h|$g]=""
  while IFS=$'\t' read -r _ k a b c d; do
    case $k in
      MNT) RES[$h|$g|$a]=$b FS[$h|$g|$a]=$c OPT[$h|$g|$a]=$d ;;
      SKILL) SK[$h|$g]+="$a"$'\n' ;;
      SKILLS) SKN[$h|$g|$a]=$b ;;
      HOOK) HOOK[$h|$g|$a]=$b ;;
      IMPORT) IMP[$h|$g|$a]=$b ;;
      TMUX) TM[$h|$g]+="$a"$'\n' ;;
      TMUXRC) TMRC[$h|$g]=$a; TMMSG[$h|$g]=$b ;;
    esac
  done <<< "$out"
  return 0
}
show(){ # host tag -> BEFORE/AFTER line
  local h=$1 g=$2
  echo "$3 $h import=ruff:${IMP[$h|$g|ruff]:-?},mypy:${IMP[$h|$g|mypy]:-?} skills=agents:${SKN[$h|$g|agents]:-?},claude:${SKN[$h|$g|claude]:-?},codex:${SKN[$h|$g|codex]:-?} hook=claude:${HOOK[$h|$g|claude]:-?},codex:${HOOK[$h|$g|codex]:-?} bd-persist=${FS[$h|$g|bdp]:-?}:${OPT[$h|$g|bdp]%%,*}"
}
net_fs(){ case $1 in nfs|nfs4|cifs|smb3|smbfs|9p|ceph|glusterfs|afs|lustre|gpfs|beegfs|ncpfs|coda|davfs|fuse|fuse.*|sshfs) return 0 ;; esac; return 1; }
gate(){ # host label -> 0 writable, else prints why
  local h=$1 l=$2 r=${RES[$1|B|$2]:-} fs=${FS[$1|B|$2]:-?} o=${OPT[$1|B|$2]:-?} bdp=${RES[$1|B|bdp]:-}
  [ -n "$r" ] && [ "$fs" != "?" ] || { echo "mount unreadable for $l"; return 1; }
  net_fs "$fs" && { echo "network fs $fs ($r)"; return 1; }
  case ",$o," in *,ro,*) echo "read-only mount ($r)"; return 1 ;; esac
  case $r in /mnt/bd*) echo "under /mnt/bd* ($r)"; return 1 ;; esac
  [ -n "$bdp" ] && [ "$bdp" != / ] || { echo "bd-persist unresolved; cannot exclude it"; return 1; }
  case $r/ in "$bdp"/*) echo "inside bd-persist ($r)"; return 1 ;; esac
  return 0
}

# ---- targets ----
WORST=0
bump(){ case $1 in 4) WORST=4 ;; 5) [ "$WORST" = 4 ] || WORST=5 ;; 1) [ "$WORST" = 0 ] && WORST=1 ;; esac; }
TARGETS=()
for h in $HOSTS; do
  seats=$(printf '%s\n' "$MAP" | awk -F'\t' -v h="$h" '$2==h {print $1}')
  if ! bd_host_ok "$h"; then echo "HOST $h status=REFUSED reason=host name"; bump 5; continue; fi
  if ! probe "$h" B; then echo "HOST $h seats=$(echo $seats | tr ' ' ,) status=COULD-NOT-LOOK"; bump 4; continue; fi
  case ${TMRC[$h|B]} in ok|none|notmux) ;; *) echo "HOST $h status=COULD-NOT-LOOK reason=tmux ls failed: ${TMMSG[$h|B]:-no message}"; bump 4; continue ;; esac
  live=0; for s in $seats; do printf '%s' "${TM[$h|B]}" | grep -qxF -- "$s" && live=$((live+1)); done
  if [ "$live" -gt 0 ]; then echo "HOST $h seats=$(echo $seats | tr ' ' ,) live=$live status=TARGET"; TARGETS+=("$h")
  else echo "HOST $h seats=$(echo $seats | tr ' ' ,) live=0 status=STALE"; fi
done
for o in ${ONLY[@]+"${ONLY[@]}"}; do
  printf '%s\n' ${TARGETS[@]+"${TARGETS[@]}"} | grep -qxF -- "$o" || die 3 "REFUSED --host $o: not a derived target (targets: ${TARGETS[*]:-none})"
done
SEL=()
for h in ${TARGETS[@]+"${TARGETS[@]}"}; do
  if [ ${#ONLY[@]} -gt 0 ] && ! printf '%s\n' "${ONLY[@]}" | grep -qxF -- "$h"; then continue; fi
  if [ "$APPLY" = 1 ] && ! printf '%s\n' ${WORD_HOSTS//,/ } | grep -qxF -- "$h"; then echo "SKIPPED $h not named in the word"; continue; fi
  SEL+=("$h")
done
for w in ${WORD_HOSTS//,/ }; do printf '%s\n' ${TARGETS[@]+"${TARGETS[@]}"} | grep -qxF -- "$w" || echo "NOT-DERIVED $w named in the word, not a target: not written"; done
echo "TARGETS ${SEL[*]:-none}"

# ---- per host ----
do_skills(){ ssh -n "${SSHO[@]}" "$1" mkdir -p .agents/skills && rsync -a --checksum --exclude=.git -e "ssh ${SSHO[*]}" "$SRC/.agents/skills/" "$1:.agents/skills/"; }
do_hook(){ ssh -n "${SSHO[@]}" "$1" mkdir -p "${3%/*}" && rsync -a --checksum -e "ssh ${SSHO[*]}" "$2" "$1:$3"; }
do_pip(){ ssh -n "${SSHO[@]}" "$1" BulkDownloader/venv/bin/pip install --quiet ruff mypy; }
step(){ # host step-name label[,label...] -> runs "$@" after EVERY named gate when applying, prints the plan otherwise
  local h=$1 n=$2 ls=$3 why rc l; shift 3
  for l in ${ls//,/ }; do if ! why=$(gate "$h" "$l"); then echo "REFUSED $h $n $why"; return 5; fi; done
  if [ "$APPLY" = 0 ]; then echo "PLAN $h $n"; return 1; fi
  "$@" </dev/null; rc=$?
  echo "STEP $h $n rc=$rc"; [ "$rc" = 0 ] || return 5; return 0
}
for h in ${SEL[@]+"${SEL[@]}"}; do
  st=0
  show "$h" B BEFORE
  echo "MOUNT $h bd-persist=${RES[$h|B|bdp]:-?} ${FS[$h|B|bdp]:-?} ${OPT[$h|B|bdp]%%,*}"
  for l in agents claude_settings codex_hooks venv venv_lib venv_bin; do
    if why=$(gate "$h" "$l"); then echo "GATE $h $l writable (${RES[$h|B|$l]} ${FS[$h|B|$l]})"; else echo "GATE $h $l REFUSED $why"; fi
  done
  if ! why=$(gate "$h" home); then echo "REFUSED $h host ~ $why"; echo "RESULT $h REFUSED"; bump 5; continue; fi
  missing=$(comm -23 <(printf '%s\n' "$SRC_SKILLS" | grep .) <(printf '%s' "${SK[$h|B]}" | grep . | LC_ALL=C sort))
  extra=$(comm -13 <(printf '%s\n' "$SRC_SKILLS" | grep .) <(printf '%s' "${SK[$h|B]}" | grep . | LC_ALL=C sort))
  for s in $missing; do echo "MISSING-SKILL $h $s"; done
  for s in $extra; do echo "EXTRA-SKILL $h $s (kept: no --delete)"; done
  # skills: always synced (content updates); additions only
  step "$h" skills agents do_skills "$h" || { r=$?; [ "$r" = 1 ] && [ -z "$missing" ] && r=0; [ "$r" -gt "$st" ] && st=$r; }
  for k in claude:claude_settings:.claude/settings.json:$SRC_CLAUDE codex:codex_hooks:.codex/hooks.json:$SRC_CODEX; do
    IFS=: read -r name lab rel want <<< "$k"
    have=${HOOK[$h|B|$name]:-?}
    case $want in absent|unreadable) echo "SOURCE-ABSENT $h $name hub $rel is $want: not copied"; [ 5 -gt "$st" ] && st=5; continue ;; esac
    [ "$have" = "$want" ] && continue
    echo "HOOK-DIFF $h $name remote=$have hub=$want"
    src=$SRC/.claude/settings.json; [ "$name" = codex ] && src=$SRC/.codex/hooks.json
    step "$h" "hook-$name" "$lab" do_hook "$h" "$src" "$rel" || { r=$?; [ "$r" -gt "$st" ] && st=$r; }
  done
  for m in ruff mypy; do [ "${IMP[$h|B|$m]:-?}" = 0 ] || echo "IMPORT-FAIL $h $m rc=${IMP[$h|B|$m]:-?}"; done
  if [ "${IMP[$h|B|ruff]:-?}" != 0 ] || [ "${IMP[$h|B|mypy]:-?}" != 0 ]; then
    step "$h" pip venv,venv_lib,venv_bin do_pip "$h" || { r=$?; [ "$r" -gt "$st" ] && st=$r; }
  fi
  if ! probe "$h" A; then echo "RESULT $h COULD-NOT-LOOK (after)"; bump 4; continue; fi
  show "$h" A AFTER
  if [ "$APPLY" = 0 ]; then
    if [ "${FP[$h|A]}" = "${FP[$h|B]}" ]; then echo "UNCHANGED $h (dry run wrote nothing)"; else echo "CHANGED-IN-DRY-RUN $h"; st=5; fi
  else
    left=$(comm -23 <(printf '%s\n' "$SRC_SKILLS" | grep .) <(printf '%s' "${SK[$h|A]}" | grep . | LC_ALL=C sort))
    for s in $left; do echo "STILL-MISSING $h $s"; st=5; done
    for name in claude codex; do w=$SRC_CLAUDE; [ "$name" = codex ] && w=$SRC_CODEX
      case $w in absent|unreadable) continue ;; esac
      [ "${HOOK[$h|A|$name]:-?}" = "$w" ] || { echo "STILL-DIFF $h $name remote=${HOOK[$h|A|$name]:-?}"; [ 5 -gt "$st" ] && st=5; }; done
    for m in ruff mypy; do [ "${IMP[$h|A|$m]:-?}" = 0 ] || { echo "STILL-IMPORT-FAIL $h $m"; [ 5 -gt "$st" ] && st=5; }; done
  fi
  case $st in 0) echo "RESULT $h OK" ;; 1) echo "RESULT $h DRIFT" ;; *) echo "RESULT $h FAILED-OR-REFUSED" ;; esac
  bump "$st"
done
echo "EXIT $WORST"; exit "$WORST"
