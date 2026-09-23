#!/usr/bin/env bash
# bd-auto-merge.sh -- H705 (bd-pm-B fork, 2026-09-23, O1265 e / POLICY-0010 s5).
# Cron (*/3, flock /tmp/bd-auto-merge.lock): for every OPEN PR whose head branch is train/*, lowest PR number first,
# fast-forward origin/main to the PR head when (1) every REQUIRED status context is green on that head and
# (2) the mechanical pre-auth checks the PM ran by hand for T61-T63 all pass (landing/PM-PREAUTH-T63-272cd897.md):
#   base: merge-base(origin/main, head) == origin/main         no-conflict: git merge-tree --write-tree rc=0
#   version: __version__ at head > main; CHANGELOG + settings-center slice carry the head version (the trio)
#   register both ways (H694): every row newly not-OPEN at head is named by the train's STAGED record, every
#     member row named by the record is not OPEN at head, nothing re-opens, no foreign status
#   precut: logs/precut-T<NN>-<sha8>.log with no BLOCKED/[VIOLATION] line, OR PLAN-2040/T<NN>-STAGED-<sha8>-*.md
# The push is `git push origin <sha>:refs/heads/main` -- exact sha, fast-forward only, never --force.
# A stacked PR whose base is not main is skipped this tick (lands after the integrator retargets it).
# Lock: bd-persist/locks/main-merge.lock (flock on the file, same convention as bd-regen-main/bd-land/bd-ship) is shared with the H702 regen-on-main cron; released on exit.
# BD_AUTO_MERGE_DRY=1 does everything except the push. Blocked reasons go to landing/AUTO-MERGE-BLOCKED-T<NN>-<sha8>.md;
# an inbox note to bd-pm-B is filed only when a PR's blocked reason CHANGES (state under landing/.auto-merge-state/).
# Rule 22: this script never checks out, resets or deletes anything; it reads refs after `git fetch` only.
set -u
export HOME=/home/mboyle
export PATH=/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin
REPO=/home/mboyle/BulkDownloader
PERSIST=/home/mboyle/bd-persist
LAND=$PERSIST/landing
STATE=$LAND/.auto-merge-state
PLAN=$PERSIST/harness-work/PLAN-2040
LOCKDIR=$PERSIST/locks/main-merge.lock
DRY=${BD_AUTO_MERGE_DRY:-0}
ONLY=${BD_AUTO_MERGE_ONLY:-}          # comma list of PR numbers (dry-run / test)
SKIPCI=${BD_AUTO_MERGE_SKIP_CI:-1}     # dry-run only: pretend required contexts are green, to exercise the mechanical checks
GATE=${BD_AUTO_MERGE_GATE:-vm}   # O1304 2026-09-23 13:5xZ (operator, interactive): VM gate only; was both (O1288)        # O1286/O1288 2026-09-23 (operator): "both" (default) = VM-GATE: PASS line in the record AND required contexts green (protection kept); "vm" = VM line only; "ci" = contexts only
REGISTER=project-knowledge/IMPROVEMENT_BACKLOG.md
NOW() { date -u +%Y-%m-%dT%H:%M:%SZ; }
HHMM() { date -u +%H:%MZ; }
TS=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$STATE" "$PERSIST/locks" "$PERSIST/logs"
log() { echo "$(NOW) bd-auto-merge $*"; }

inbox_note() {  # seat, line
  local d=$PERSIST/inbox/$1; mkdir -p "$d"
  printf '%s\n' "$2" > "$d/$TS-automerge-$$.md.tmp" && mv "$d/$TS-automerge-$$.md.tmp" "$d/$TS-automerge-$$.md"
}

cd "$REPO" || { log "FATAL: repo missing"; exit 0; }
git fetch -q origin main 2>/dev/null || { log "FATAL: fetch main failed"; exit 0; }
MAIN=$(git rev-parse origin/main)

REQ=$(gh api repos/{owner}/{repo}/branches/main/protection/required_status_checks --jq '.contexts[]' 2>/dev/null)
if [ -z "$REQ" ]; then
  # O1304 (2026-09-23, operator): required contexts may be EMPTY (VM gate only). Empty is fatal only when the gate needs them.
  case "$GATE" in vm) log "required contexts empty (O1304 VM gate only)";; *) log "FATAL: could not read required contexts"; exit 0;; esac
fi
NREQ=$(printf '%s\n' "$REQ" | grep -c .)

PRS=$(gh pr list --state open --limit 50 --json number,headRefName,baseRefName,headRefOid \
      --jq '.[] | select(.headRefName|startswith("train/")) | "\(.number) \(.headRefName) \(.baseRefName) \(.headRefOid)"' 2>/dev/null | sort -n)
[ -z "$PRS" ] && { log "no open train PRs (main=${MAIN:0:12})"; exit 0; }

while read -r NUM BRANCH BASE HEAD; do
  [ -n "$ONLY" ] && ! printf ',%s,' "$ONLY" | grep -q ",$NUM," && continue
  TN=$(printf '%s' "$BRANCH" | sed -E 's#^train/([0-9]+).*#\1#')
  S8=${HEAD:0:8}; S12=${HEAD:0:12}
  REASON=""; DETAIL=""
  fail() { REASON="$1"; DETAIL="${2:-}"; }

  # 0. already on main?
  if git merge-base --is-ancestor "$HEAD" "$MAIN" 2>/dev/null; then
    log "PR$NUM T$TN $S12 already reachable from main -- nothing to do"; continue
  fi
  # 1. stacked: base must be main
  if [ "$BASE" != "main" ]; then fail "base-not-main" "PR base is $BASE; lands after the lower train merges and the PR is retargeted to main"; fi

  # 2. required contexts on the head sha
  CIRED=""
  if [ -z "$REASON" ] && { [ "$GATE" = ci ] || [ "$GATE" = both ]; } && { [ "$DRY" != 1 ] || [ "$SKIPCI" != 1 ]; }; then
    # H714 (03:3xZ 2026-09-23): latest check run PER NAME decides (GitHub's own rule); an older cancelled/failed duplicate
    # run (push vs pull_request on the same sha) no longer reds a context that the newer run passed.
    CHECKS=$(gh api "repos/{owner}/{repo}/commits/$HEAD/check-runs?per_page=100" --paginate \
      --jq '.check_runs[] | "\(.name)\t\(.status)\t\(.conclusion // "")\t\(.started_at // "")"' 2>/dev/null \
      | sort -t$'\t' -k1,1 -k4,4 | awk -F'\t' '{ if($2!="completed") pend[$1]=1; else if($3=="cancelled") canc[$1]=1; else last[$1]=$3 } END{for(n in last) print n"\t"(n in pend?"in_progress":"completed")"\t"last[n]; for(n in pend) if(!(n in last)) print n"\tin_progress\t"; for(n in canc) if(!(n in last) && !(n in pend)) print n"\tcompleted\tcancelled"}')
    # H714c: a cancelled check run never outranks a decisive one for the same name (duplicate push run cancelled seconds after the pull_request run passed)
    # H714b: any queued/in-progress run for a context = pending (a cancelled duplicate must not decide while the live run has not started)
    MISSING=""; PENDING=""; RED=""
    while IFS= read -r ctx; do
      [ -z "$ctx" ] && continue
      st=$(printf '%s\n' "$CHECKS" | awk -F'\t' -v c="$ctx" '$1==c{print $2"\t"$3}' | head -1)
      status=${st%%$'\t'*}; concl=${st#*$'\t'}
      if [ -z "$st" ]; then MISSING="$MISSING $ctx"
      elif [ "$status" != completed ]; then PENDING="$PENDING $ctx"
      elif [ "$concl" = success ] || [ "$concl" = skipped ] || [ "$concl" = neutral ]; then :
      else RED="$RED $ctx"
      fi
    done <<< "$REQ"
    if [ -n "$RED" ]; then fail "required-red" "red required contexts:$RED"
    elif [ -n "$PENDING$MISSING" ]; then fail "required-pending" "pending:$PENDING missing:$MISSING"; fi
  elif [ -z "$REASON" ] && [ "$GATE" = vm ]; then
    CIRED=$(gh pr checks "$NUM" 2>/dev/null | awk -F'\t' '$2=="fail"{printf "%s ",$1}')   # informational only (O1286): a CI red after landing is a hotfix row
  fi

  # 3. mechanical checks on fetched refs
  if [ -z "$REASON" ]; then
    git fetch -q origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" 2>/dev/null
    REMOTE=$(git rev-parse "origin/$BRANCH" 2>/dev/null || echo none)
    [ "$REMOTE" != "$HEAD" ] && fail "head-moved" "PR head $S12 != branch tip ${REMOTE:0:12} (rerun next tick)"
  fi
  if [ -z "$REASON" ]; then
    MB=$(git merge-base "$MAIN" "$HEAD" 2>/dev/null || echo none)
    [ "$MB" != "$MAIN" ] && fail "not-ff" "merge-base ${MB:0:12} != origin/main ${MAIN:0:12}; train needs a rebase"
  fi
  if [ -z "$REASON" ]; then
    MT=$(git merge-tree --write-tree "$MAIN" "$HEAD" 2>&1); MTRC=$?
    [ $MTRC -ne 0 ] && fail "merge-conflict" "git merge-tree rc=$MTRC: $(printf '%s' "$MT" | head -c 600)"
  fi
  if [ -z "$REASON" ]; then
    VH=$(git show "$HEAD:bulk_downloader/__init__.py" 2>/dev/null | sed -nE 's/^__version__ *= *"([^"]+)".*/\1/p' | head -1)
    VM=$(git show "$MAIN:bulk_downloader/__init__.py" 2>/dev/null | sed -nE 's/^__version__ *= *"([^"]+)".*/\1/p' | head -1)
    if [ -z "$VH" ] || [ -z "$VM" ]; then fail "version-unreadable" "head=$VH main=$VM"
    elif [ "$(printf '%s\n%s\n' "$VM" "$VH" | sort -V | tail -1)" != "$VH" ] || [ "$VH" = "$VM" ]; then fail "version-not-bumped" "head $VH <= main $VM"
    else
      for f in CHANGELOG.md tests/test_settings_center_slice4.py; do
        git show "$HEAD:$f" 2>/dev/null | grep -q -F "$VH" || fail "trio-incomplete" "$f at head lacks $VH"
      done
    fi
  fi
  # 4. precut / staged record
  RECORD=""
  if [ -z "$REASON" ]; then
    PLOG=$PERSIST/logs/precut-T$TN-$S8.log
    RECORD=$(ls "$PLAN"/T$TN-STAGED-$S8-*.md "$PLAN"/T$TN-PRECUT-$S8-*.md "$PLAN"/T$TN[A-Za-z]-STAGED-$S8-*.md "$PLAN"/T$TN[A-Za-z]-PRECUT-$S8-*.md 2>/dev/null | head -1)   # H715: hotfix trains T66H etc.
    if [ -f "$PLOG" ] && ! grep -qE '^BLOCKED|\[VIOLATION\]' "$PLOG"; then :
    elif [ -n "$RECORD" ] && ! grep -qE '^BLOCKED|\[VIOLATION\]|^VERDICT: (BOUNCE|REFUTE)' "$RECORD" && { { [ "$GATE" != vm ] && [ "$GATE" != both ]; } || grep -qE '^VM-GATE: PASS' "$RECORD"; }; then :
    elif [ -n "$RECORD" ] && { [ "$GATE" = vm ] || [ "$GATE" = both ]; }; then fail "no-vm-gate" "$RECORD has no 'VM-GATE: PASS <host> <sha8> <utc>' line (O1286: integrator runs the fast gates + member tests on a VMware host and writes it)"
    else fail "no-precut-record" "neither $PLOG (clean) nor a clean $PLAN/T$TN-(STAGED|PRECUT)-$S8-*.md"; fi
  fi
  # 5. register both ways (H694)
  if [ -z "$REASON" ]; then
    DIFF=$(git diff "$MAIN" "$HEAD" -- "$REGISTER" | grep -E '^[-+]\| *[0-9]+ \|')
    # re-opened = status was not OPEN at main and is OPEN at head (a text-only amendment of an OPEN row is not a reopen)
    REOPEN=$(printf '%s\n' "$DIFF" | awk -F'|' '{id=$2; gsub(/ /,"",id); s=$3; gsub(/ /,"",s); if(/^-/) was[id]=s; else now[id]=s} END{for(id in now) if(now[id]=="OPEN" && (id in was) && was[id]!="OPEN") print id}' | tr -d ' ')
    NEWCLOSED=$(printf '%s\n' "$DIFF" | awk -F'|' '/^\+/{s=$3; gsub(/^ +| +$/,"",s); if(s!="OPEN") print $2"="s}' | tr -d ' ')
    FOREIGN=$(printf '%s\n' "$NEWCLOSED" | awk -F'=' '$2!~/^(CLOSED@?[0-9.]*|MOOT.*|REFUTED.*)$/{print}')
    [ -n "$REOPEN" ] && fail "register-reopen" "rows re-opened at head: $REOPEN"
    [ -z "$REASON" ] && [ -n "$FOREIGN" ] && fail "register-foreign-status" "$FOREIGN"
    if [ -z "$REASON" ]; then
      BODY=$(gh pr view "$NUM" --json body --jq .body 2>/dev/null)
      NAMED=$( { [ -n "$RECORD" ] && cat "$RECORD"; printf '%s\n' "$BODY"; } | grep -oE '(row|rows? |#|\b)[0-9]{3,4}\b' | grep -oE '[0-9]{3,4}' | sort -u)
      for kv in $NEWCLOSED; do id=${kv%%=*}; printf '%s\n' "$NAMED" | grep -qx "$id" || fail "register-unnamed-close" "row $id newly ${kv#*=} at head but not named in the STAGED record / PR body"; done
    fi
    if [ -z "$REASON" ] && [ -n "$RECORD" ]; then
      # members = row ids in the record's "## Members" section, excluding lines the integrator marked NOT included / dropped / excluded
      MEMBERS=$(awk '/^## Members/{m=1; next} /^## /{m=0} m' "$RECORD" | grep -viE 'not included|dropped|excluded|removed' | grep -oE '\brow[0-9]{3,4}\b' | grep -oE '[0-9]+' | sort -u)
      for id in $MEMBERS; do
        st=$(git show "$HEAD:$REGISTER" | awk -F'|' -v i="$id" '{gsub(/ /,"",$2)} $2==i{s=$3; gsub(/^ +| +$/,"",s); print s; exit}')
        [ "$st" = "OPEN" ] && fail "register-member-open" "member row $id still OPEN at head"
      done
    fi
  fi

  if [ -n "$REASON" ]; then
    BF=$LAND/AUTO-MERGE-BLOCKED-T$TN-$S8.md
    { echo "BLOCKED: $REASON"; echo "T$TN = PR #$NUM $BRANCH head $HEAD base $BASE. main=${MAIN:0:12}. $(NOW) by bd-auto-merge (dry=$DRY)."; echo; echo "$DETAIL"; } > "$BF.tmp" && mv "$BF.tmp" "$BF"
    SF=$STATE/T$TN-$S8.reason
    if [ "$(cat "$SF" 2>/dev/null)" != "$REASON" ]; then
      printf '%s' "$REASON" > "$SF.tmp" && mv "$SF.tmp" "$SF"
      [ "$DRY" = 1 ] || inbox_note bd-pm-B "[from bd-auto-merge $(HHMM)] T$TN BLOCKED $REASON | $BF"
    fi
    log "PR$NUM T$TN $S12 BLOCKED $REASON -- $BF"; continue
  fi

  # H725: PM hold file -- touch $STATE/HOLD-T<NN> to keep a green train from landing (O1282 drop before land); rm to release
  if [ -f "$STATE/HOLD-T$TN" ]; then log "PR$NUM T$TN $S12 HELD by PM ($STATE/HOLD-T$TN: $(head -c 80 "$STATE/HOLD-T$TN" 2>/dev/null))"; continue; fi
  # ---- all checks pass: land ----
  exec 9>"$LOCKDIR"; if ! flock -n 9; then log "PR$NUM T$TN lock held ($(head -c 80 "$LOCKDIR" 2>/dev/null)); retry next tick"; exec 9>&-; continue; fi
  printf 'bd-auto-merge pid=%s since=%s\n' "$$" "$(NOW)" >&9; trap 'flock -u 9 2>/dev/null; exec 9>&- 2>/dev/null' EXIT
  git fetch -q origin main; MAIN2=$(git rev-parse origin/main)
  if [ "$MAIN2" != "$MAIN" ]; then log "PR$NUM main moved during checks (${MAIN:0:12} -> ${MAIN2:0:12}); retry next tick"; flock -u 9; exec 9>&-; trap - EXIT; continue; fi
  REC=$LAND/LANDED-TRAIN$TN-$S8-AUTO.md
  if [ "$DRY" = 1 ]; then
    PUSH="DRY-RUN: would run  git push origin $HEAD:refs/heads/main"; PRC=0
  else
    PUSH=$(git push origin "$HEAD:refs/heads/main" 2>&1); PRC=$?
  fi
  if [ $PRC -ne 0 ]; then
    log "PR$NUM T$TN PUSH FAILED rc=$PRC: $PUSH"; printf 'push-failed' > "$STATE/T$TN-$S8.reason"
    inbox_note bd-pm-B "[from bd-auto-merge $(HHMM)] T$TN PUSH FAILED rc=$PRC | $LAND/AUTO-MERGE-BLOCKED-T$TN-$S8.md"
    { echo "BLOCKED: push-failed rc=$PRC"; echo "$PUSH"; } > "$LAND/AUTO-MERGE-BLOCKED-T$TN-$S8.md"
    flock -u 9; exec 9>&-; trap - EXIT; continue
  fi
  git fetch -q origin main; AFTER=$(git rev-parse origin/main)
  {
    echo "VERDICT: LANDED"
    echo "T$TN = PR #$NUM $BRANCH = $HEAD = v$VH. Fast-forwarded onto main $(NOW) by bd-auto-merge (H705, O1265 e). dry=$DRY"
    echo "origin/main before ${MAIN:0:12}, after ${AFTER:0:12}. Record: ${RECORD:-none} ; precut log: $([ -f "$PLOG" ] && echo "$PLOG" || echo none)"
    echo
    echo "## Checks (all passed)"
    if [ "$DRY" = 1 ] && [ "$SKIPCI" = 1 ]; then echo "- required contexts: NOT CHECKED (dry run with BD_AUTO_MERGE_SKIP_CI=1)"; else echo "- required contexts: $NREQ, all pass on $S12 (no fail on either run)"; fi
    echo "- merge-base(origin/main, head) == origin/main ${MAIN:0:12}; git merge-tree --write-tree rc=0"
    [ "$GATE" = vm ] && echo "- gate: VM-GATE PASS in $RECORD (O1286); GitHub CI not awaited; CI red at landing time: ${CIRED:-none}"
    [ "$GATE" = both ] && echo "- gate: VM-GATE PASS in $RECORD AND required contexts green (O1288: branch protection kept)"
    echo "- version: main $VM -> head $VH; CHANGELOG.md + tests/test_settings_center_slice4.py carry $VH"
    echo "- register (H694): newly non-OPEN at head = $(printf '%s ' $NEWCLOSED); all named in the record; members not OPEN; no re-open; no foreign status"
    echo "- push: $PUSH"
    echo
    echo "## What is left"
    echo "- deploy by cron (bd-deploy-trio.sh); live proof = /api/health build.sha on both hosts; content proof = landed_by_content (PM)."
    echo "- any stacked train whose base was $BRANCH must be retargeted to main by its integrator before it can land."
  } > "$REC.tmp" && mv "$REC.tmp" "$REC"
  printf '%s T%s LANDED %s v%s by bd-auto-merge -- %s\n' "$(NOW)" "$TN" "$S12" "$VH" "$REC" >> "$PERSIST/DIGEST.md"
  INTEG=$(printf '%s' "$RECORD" | grep -oE 'bd-integrator-[A-Za-z0-9-]+' | head -1)
  if [ "$DRY" != 1 ]; then
    inbox_note bd-pm-B "[from bd-auto-merge $(HHMM)] T$TN LANDED $S12 | $REC"
    [ -n "$INTEG" ] && inbox_note "$INTEG" "[from bd-auto-merge $(HHMM)] T$TN LANDED $S12 | $REC"
  fi
  rm -f "$STATE/T$TN-$S8.reason"
  log "PR$NUM T$TN $S12 LANDED (dry=$DRY) -- $REC"
  flock -u 9 2>/dev/null; exec 9>&- 2>/dev/null; trap - EXIT
  # H721: regen indexes on main right after the landing (RULING-0039/H702) so the next restack sees the final tip
  if [ "$DRY" != 1 ]; then
    flock -n /tmp/bd-regen-main.lock bash /home/mboyle/bd-persist/harness/bd-regen-main.sh >> "/home/mboyle/bd-persist/logs/regen-main.cron.log" 2>&1 || log "regen after T$TN rc=$? (cron will retry)"
    git fetch -q origin main; AFTER=$(git rev-parse origin/main)
  fi
  MAIN=$AFTER
  [ "$DRY" = 1 ] && MAIN=$HEAD   # dry-run: pretend, so a stacked upper train is evaluated against the would-be main
done <<< "$PRS"
exit 0
