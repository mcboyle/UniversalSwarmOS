#!/bin/bash
# bd-launch-role.sh <role> <pool A|B|codex|auto> [name] [--dry-run] [--resume <session-id>] [--allow-unconfirmed-kick]
#   --resume: relaunch a crashed seat ON ITS OLD TRANSCRIPT (claude --resume). The transcript must
#   exist under the pool's config dir for the seat cwd; set BD_LAUNCH_WORKDIR to the cwd the dead
#   session ran in (a session is keyed by cwd). Added 2026-09-14: bd-pm-opus-A VM crash.
#
# Three-pool failover launcher. Creates the tmux session, starts claude under the
# right account, answers the folder-trust menu, and feeds the role bootstrap.
#
# It NEVER fails open. Every refusal names the step that failed and carries the
# evidence, because "launch failed" and "the trust menu defaulted to No and the
# session exited" lead to opposite actions and the wrong one was pursued first.
#
# Exit: 0 launched (or printed, under --dry-run)   2 usage      3 unknown role/pool
#       4 bootstrap prompt missing                 5 session exists
#       6 claude never reached bypass permissions  7 bootstrap not consumed or unconfirmed kick
#       8 codex backend absent
set -u
# O1073 sec 4 (enacted O1084, 2026-09-20): lens verification fan-out cap, read by review-correctness.prompt. Override per launch.
export BD_LENS_MAX_AGENTS=${BD_LENS_MAX_AGENTS:-3}

# Overrides exist for the fixtures and for nothing else; the defaults are the
# real paths, so a plain invocation is never pointed somewhere harmless by accident.
ROLE_DIR=${BD_LAUNCH_ROLE_DIR:-/home/mboyle/bd-persist/role-prompts}
WORKDIR=${BD_LAUNCH_WORKDIR:-}   # default resolved below, once ROLE is known (W6a)
CONFIG_B=/home/mboyle/.claude-b
# ** THE ACCOUNT AUTOCOMPACT WINDOW IS OWNED HERE (rule 37; H485b; O604/O615). ** ~/.claude*/settings.json
# autoCompactWindow is ONE value per account, rewritten by any seat that types /autocompact, and it
# OUTRANKS --autocompact argv (O603: B ran at 468k against argv 200k). Every launch WARNs when the
# account file differs from this value; bd-codex-drift-check.sh REDs on it. Change it HERE, then the
# two files, then record the O-line -- never the other way round.
ACCOUNT_AUTOCOMPACT_WINDOW=500000   # O861 2026-09-19: 500k both accounts; was 200000 (O615 20:2xZ: 150000 (O604) thrashed at ~87k effective -> 200000
settings_window() { python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1])).get("autoCompactWindow","ABSENT"))
except Exception as e: print("UNREADABLE")' "$1/settings.json" 2>/dev/null || echo UNREADABLE; }
CODEX=${BD_LAUNCH_CODEX:-/home/mboyle/bd-codex-lens.sh}
SAY=${BD_LAUNCH_SAY:-/home/mboyle/bd-say.sh}
export PATH="/home/mboyle:$PATH"
POOL_STATE=${BD_LAUNCH_POOL_STATE:-/home/mboyle/bd-persist/POOL_STATE.tsv}

die() { echo "bd-launch-role: $2"; exit "$1"; }
[ -x "$SAY" ] || die 6 "message tool is absent or not executable at $SAY -- refusing to launch a seat that cannot report"


# THE THREE ROLE TABLES. A role absent from model_for is not a role this fleet
# runs, and the launcher refuses it rather than starting a session with an empty
# --model. ** THE "22" IN THIS LINE WAS WRONG AND IS CORRECTED 2026-09-08 BY AN ADVERSARIAL AUDIT. **
# The population is role-prompts/*.prompt = ** 24 **, enumerated from the filesystem. Before the
# 2026-09-08 rewrite exactly TWO exited 3, not nine: worker and worker-b. After it, THE SAME TWO --
# the rewrite added nine role NAMES that have no .prompt file, so they merely moved from die 3 to
# die 4, and net launchable roles changed by ZERO. worker/worker-b are now added, which is the fix
# that was actually owed: they are the fleet's most numerous seat type (12 live) and the only roles
# with a prompt that this launcher could not start.
# ** THE PM MEASURED A REMEMBERED LIST OF ROLE NAMES INSTEAD OF THE role-prompts DIRECTORY. **
model_for() {
  # ROLE TABLES REWRITTEN 2026-09-08 ON THE OPERATOR'S APPROVAL. Three defects fixed:
  #  1. NINE LIVE ROLES HAD NO ENTRY and fell through to `*) echo ""`, launching with NO model and
  #     NO effort -- adjudicator, dispatch, verify, cartograph, audit, codexwatch, nurse, ideas and
  #     the null seats. That is why six spellings for four models appeared in `ps`: those seats were
  #     launched by hand. A MISSING TABLE ROW DOES NOT ERROR, IT LAUNCHES A SEAT WITH NO SETTINGS.
  #  2. INTEGRATORS RAN AT medium. They merge to main and deploy to 13 hosts -- the only seat whose
  #     mistakes are NOT undone by re-running something. Raised to high.
  #  3. briefauthor AND local-a RAN ON opus for assembly and measurement work. Moved to sonnet.
  # UNCHANGED DELIBERATELY: the lenses stay opus/high -- a wrong BOARD ships a defect and a wrong
  # REFUTE burns a worker round.
  case "$1" in
    # ** OPERATOR 2026-09-08: THE JUDGEMENT SEATS MOVE TO opus. FABLE 5.1 IS NOW THE ADVISOR ONLY. **
    # Fable was previously the model for pm/fable/panel/adjudicator/flakecourt. It is now held for a
    # single ADVISORY seat, so the fleet has one Fable reading rather than several -- an advisor that
    # runs the same model as the seat it advises is not a second opinion.
    fable|fable-b)                                      echo opus ;;
    pm|pm-b)                                            echo fable ;;   # O688 operator 2026-09-15: PM->FABLE (supersedes 2026-09-08 for pm only)
    panel|panel-b)                                      echo fable ;;
    flakecourt|flakecourt-a|flakecourt-b)               echo fable ;;
    adjudicator|adjudicator-b)                          echo fable ;;
    advisor|advisor-b)                                  echo fable ;;
    integrator|integrator-b|integrator-c|integrator-d)  echo fable ;;
    trainer|registrar)                                  echo fable ;;
    review-correctness|review-shape)                    echo fable ;;
    # ** OPERATOR 2026-09-12 (item 16): review-lite = the single lens for T0/T1 and the T2 shape lens.
    #    review-correctness (T2/T3 correctness) and review-shape (T3) stay opus. Dispatch T0/T1 as review-lite. **
    review-lite|review-lite-b)                          echo sonnet ;; # O635 2026-09-14: operator, lite (T1 shape) lenses sonnet; correctness/shape stay opus
    dispatch)                                           echo opus ;;
    triage)                                             echo haiku ;;  # O860c 2026-09-19: haiku (was sonnet, O670)
    # cx-pm: the CODEX PM seat (2026-09-09, operator: "add a project management role on Codex so
    # the work does not die"). opus maps to gpt-6-astra in bd-gen-codex-roles.sh -- a judgement seat.
    cx-pm)                                              echo opus ;;
    worker|worker-b)                                    echo claude-opus-5-5 ;;  # O1119 2026-09-21: operator: Claude workers = Opus 5.5 (was sonnet, O1034) 2026-09-20: operator: Claude workers = Sonnet 5 medium (Opus control seats via BD_LAUNCH_MODEL=opus)
    briefauthor|briefauthor-2)                          echo sonnet ;;
    local-runner|local-a)                               echo sonnet ;;
    landverify|landverify-a|prereview)                  echo sonnet ;;
    flow|status)                                        echo sonnet ;;
    # ** ideas IS opus/high, NOT sonnet/medium. CORRECTED 2026-09-08 ON MEASURED OUTPUT. ** Its work
    # on 2026-09-07 -- face 10 "a gate nobody has ever seen fail" (1,389 of 1,637 test files with no
    # retained mutant proving they CAN fail), the finding that every session had been recording its
    # own token cost all along and nothing read it, and 31 ranked native-machinery proposals -- was
    # the highest-leverage analysis any seat produced in 48 hours and it REFRAMED THE PROGRAM.
    # A read-only seat is not automatically a cheap seat. THE MODEL FOLLOWS THE WORK, NOT THE TOOL GRANT.
    # ** OPERATOR 2026-09-12 (relitigation item 16): ideas -> sonnet; read-only judgment roles run sonnet. **
    ideas)                                              echo sonnet ;;
    verify|cartograph|audit|codexwatch|nurse|closure-audit|preflight|scribe|landing) echo sonnet ;;
    codex-tender)                                       echo sonnet ;;  # O1277 2026-09-23: feeds/heals codex seats
    fixer)                                              echo claude-opus-5-5 ;;  # O1281 2026-09-23: operator: two Opus 5.5 max fixer seats take every bounced/refuted/red row
    usage|usage-a|usage-b|login|b-login)                echo haiku ;;
    askbox|smoketest)                                   echo haiku ;;  # smoketest O854
    notes)                                              echo sonnet ;; # O676 deferred operator notes; O679 haiku skipped the tool call
    *)                                                  echo "" ;;
  esac
}

# Effort, per the 21:37Z/21:44Z rulings. NOTHING IS LOWERED HERE: the review
# lenses stay HIGH, because lowering them needs a night of REFUTE-rate data
# (OPEN 5) and a cheaper lens that misses an escape costs more than it saves.
# An empty value means "the binary's current default" and omits the flag.
effort_for() {
  # EFFORT FOLLOWS CONSEQUENCE, NOT SENIORITY. The question is what a wrong answer costs and whether
  # it can be undone by re-running something.
  case "$1" in
    fable|fable-b|pm|pm-b|cx-pm|panel|panel-b|flakecourt|flakecourt-a|flakecourt-b) echo high ;;
    adjudicator|adjudicator-b)                          echo high ;;
    review-correctness|review-shape)                    echo high ;;
    review-lite|review-lite-b)                          echo medium ;;
    integrator|integrator-b|integrator-c|integrator-d)  echo high ;;
    trainer|registrar)                                  echo high ;;
    dispatch)                                           echo high ;;
    triage)                                             echo low ;;    # O860c
    worker|worker-b)                                    echo medium ;;
    briefauthor|briefauthor-2)                          echo medium ;;
    local-runner|local-a)                               echo medium ;;
    ideas)                                              echo high ;;
    advisor|advisor-b)                                  echo high ;;
    verify|cartograph|audit|codexwatch|nurse|closure-audit|preflight|scribe) echo medium ;;
    status|flow|landverify|landverify-a|prereview|landing) echo low ;;
    usage|usage-a|usage-b|login|b-login)                echo low ;;
    askbox|smoketest)                                   echo low ;;
    notes)                                              echo low ;; # O676
    fixer)                                              echo max ;; # O1281
    *)                                                  echo "" ;;
  esac
}

# The auto-compact window. A REVIEW CENSUS MUST FIT IN ONE WINDOW, so the lenses,
# the panel and fable get the largest cap; the reporting roles get the smallest
# because a long context is 92% of the spend and they never need one.
autocompact_for() {
  # O860/O861 (2026-09-19, operator): HEAVY 500k / LIGHT 300k / WATCHERS 100k. The account window is 500k on
  # BOTH accounts (it outranks argv, H485b); light roles are bounded by the 150/200 TURN CAP (bd-turn-watch.sh).
  case "$1" in
    pm|pm-b|adjudicator|adjudicator-b|integrator|integrator-b|integrator-c|integrator-d|fable|fable-b|advisor|advisor-b|review-correctness|review-shape|panel|panel-b|flakecourt|flakecourt-a|flakecourt-b|trainer|registrar|dispatch) echo 500000 ;;
    usage|usage-a|usage-b|login|b-login|askbox|smoketest)      echo 100000 ;;
    triage)                                                     echo 300000 ;;   # O860c haiku triage
    *)                                                          echo 300000 ;;   # LIGHT: worker, briefauthor, review-lite, landing/landverify/prereview/preflight, verify/audit/cartograph/nurse/closure-audit/scribe, status/flow, ideas/notes, local-*
  esac
}

# The pool a role runs on by default (01:32Z: the heavy roles on B; fable,
# integrator and integrator-b on A). Only consulted for `--pool auto`.
default_pool_for() {
  case "$1" in
    # ---- R13, 2026-09-09: integrator SPLIT into three roles by what they actually do.
    # integrator = harness batch + deploy + SOLE WRITER to main; trainer = patch-train assembly
    # (MULTI, claims candidates per-object); registrar = register rows (SINGLE, a global sequence).
    # integrator KEEPS its A affinity but is NO LONGER PINNED there -- resolve_auto_pool ranks by
    # headroom, so a deploy is still possible once A hits its 95% stop. That pin was the failure the
    # triplet design exists to prevent.
    fable|integrator|integrator-b|registrar|integrator-c)   echo A ;;
    *)                                         echo B ;;
  esac
}

# `--pool auto` tilts to the other account when POOL_STATE says the default is
# spent, and refuses when BOTH are. It still never launches on its own.
# STOP is the operator's 95% rule and is TREATED EXACTLY LIKE LIMITED here: a pool
# that takes no new task items cannot be the target of a launch, which IS a new
# task item. Adding the state to the sentinel without adding it here would have
# left the harder rule visible and unenforced.
pool_state_of() {
  [ -f "$POOL_STATE" ] || { echo UNKNOWN; return; }
  awk -F'\t' -v p="$1" 'NR>1 && $1==p {print $2}' "$POOL_STATE" | tail -1
}
# ** HEADROOM-RANKED ACROSS THREE POOLS. Item 1, operator ruling R6, 2026-09-09. **
# THE OLD VERSION KNEW ONLY TWO POOLS: `other=B; [ "$want" = B ] && other=A`. Codex was NEVER a
# failover target, so with A and B both spent it returned BOTH:... and refused -- while thirteen
# codex hosts sat idle. Under the triplet design (A, B and codex run an IDENTICAL set of agents)
# that is a third of the fleet excluded from every failover decision.
# AND IT WAS NOT RANKED. It was want-or-other, with no comparison of how much headroom each had,
# so it could hand work to a pool at 94% while another sat at 5%.
# ** UNKNOWN IS NOT A CANDIDATE (FLEET_RULE 29). ** A pool whose state cannot be read is not
# "probably fine" -- it is unreadable, and a limit the tool cannot see is UNKNOWN. This is not
# pedantry: POOL_STATE reads UNKNOWN for all three pools RIGHT NOW, on a usage cache 7.4 h stale,
# so a version that treated UNKNOWN as available would route every launch onto a blind guess.
pool_pct_of() {
  # The worst of the two published numbers, because either can bind. Column 5 is the 5-hour
  # percentage and column 7 the weekly; a missing or non-numeric value yields "-" (unusable).
  awk -F'\t' -v p="$1" 'NR>1 && $1==p {
      five=$5; wk=$7
      f=(five ~ /^[0-9]+$/)?five+0:-1
      w=(wk   ~ /^[0-9]+$/)?wk+0:-1
      worst=(f>w)?f:w
      print (worst<0)?"-":worst
    }' "$POOL_STATE" 2>/dev/null | tail -1
}
resolve_auto_pool() {
  local want cand best best_pct st pct p
  want=$(default_pool_for "$1")
  # The role's default pool wins outright when it is usable -- affinity beats a marginal
  # headroom edge, and churning a role between backends costs more than the points it saves.
  st=$(pool_state_of "$want"); pct=$(pool_pct_of "$want")
  case "$st" in
    STOP|FAILOVER|LIMITED|UNKNOWN|"") : ;;
# ** THROTTLE = 90, operator ruling 2026-09-09 (was 85). THE 95%% HARD STOP IS UNCHANGED. **
# The throttle is a PREFERENCE (route elsewhere if you can); 95%% is a REFUSAL (take no new
# task items at all). Only the preference moved. THE LITERAL 90 APPEARS IN FOUR PLACES:
#   bd-launch-role.sh resolve_auto_pool (affinity threshold)
#   bd-limit-watch.sh x3 (the threshold loop, the FAILOVER test, the rank-3 FAILOVER note)
# If you change it again, change all four -- they were four literals before this comment.
    *) if [ "$pct" != "-" ] && [ "${pct:-100}" -lt 90 ]; then echo "$want"; return 0; fi ;;
  esac
  best=""; best_pct=101
  for p in A B codex; do
    st=$(pool_state_of "$p"); pct=$(pool_pct_of "$p")
    case "$st" in STOP|FAILOVER|LIMITED|UNKNOWN|"") continue ;; esac
    [ "$pct" = "-" ] && continue
    if [ "$pct" -lt "$best_pct" ]; then best=$p; best_pct=$pct; fi
  done
  if [ -n "$best" ]; then echo "$best"; return 0; fi
  # THREE OUTCOMES: the refusal NAMES every pool and why, so "nothing is available" can be
  # told apart from "nothing could be read" without opening POOL_STATE by hand.
  echo "NONE:$(for p in A B codex; do printf '%s=%s/%s ' "$p" "$(pool_state_of "$p")" "$(pool_pct_of "$p")"; done)"
  return 1
}

# Default session names, by pool. B sessions carry the -b suffix so a pane can be
# read back to its account without opening its config.
# ** THE POOL SUFFIX IS ADDED ONCE, BELOW, AND NOT HERE. Fixed 2026-09-09 from a LIVE seat. **
# This used to echo "bd-$1-b" for pool B, and the suffix block further down then appended "-B" --
# so `bd-launch-role.sh usage-b B` produced ** bd-usage-b-b-B **. Measured on a real launch, not
# predicted: the smoke-test seat came up under that name. The same shape gave bd-flakecourt-b-B.
# ONE DECISION, ONE PLACE: the account belongs in the suffix the pool derives, never in the base.
default_name() {
  case "$2" in
    A|B)   echo "bd-$1" ;;
    codex) echo "cx-$1" ;;
  esac
}

[ $# -ge 2 ] || die 2 "usage: bd-launch-role.sh <role> <pool A|B|codex|auto> [name] [--dry-run] [--resume <session-id>] [--allow-unconfirmed-kick]"
ROLE=$1; POOL=$2; shift 2
# W6a (KNOWLEDGE-PLANE-PLAN, O326): a STABLE per-role cwd. The old mktemp /tmp/bd-seat-claude.XXXXXX keyed Claude's
# memory namespace to a random dir (78 memories in 2 namespaces, 0 in all 23 seat namespaces, measured 2026-09-13)
# and the recovery's /tmp wipe erased every one. /var/tmp survives reboots and tmpfiles; the role name makes every
# seat of a role on this host share one memory dir. BD_LAUNCH_WORKDIR still overrides (fixtures).
if [ -z "$WORKDIR" ]; then
  WORKDIR=/var/tmp/bd-seats/$ROLE
  mkdir -p "$WORKDIR" || die 6 "could not create the seat cwd $WORKDIR"
fi
NAME=""; DRY=""; RESUME=""; WANT_RESUME=""; ALLOW_UNCONFIRMED_KICK="${BD_LAUNCH_ALLOW_UNCONFIRMED_KICK:-}"
for a in "$@"; do
  if [ -n "$WANT_RESUME" ]; then RESUME=$a; WANT_RESUME=""; continue; fi
  case "$a" in
    --dry-run) DRY=1 ;;
    --resume)  WANT_RESUME=1 ;;
    --allow-unconfirmed-kick) ALLOW_UNCONFIRMED_KICK=1 ;;
    -*)        die 2 "unknown option $a" ;;
    *)         [ -z "$NAME" ] && NAME=$a || die 2 "two names given: $NAME and $a" ;;
  esac
done

if [ "$POOL" = auto ]; then
  POOL=$(resolve_auto_pool "$ROLE") || die 3 "both pools are spent ($POOL) -- nothing to launch onto"
  echo "bd-launch-role: --pool auto resolved to $POOL for $ROLE"
fi
case "$POOL" in A|B|codex) : ;; *) die 3 "unknown pool $POOL (want A, B, codex or auto)" ;; esac

# H571: claim pool-suffixed role for usage*|login (usage-a for pool A, usage-b for pool B, usage for codex)
# so ROLE-CARDINALITY.tsv's three SINGLE roles are respected without collisions.
case "$ROLE" in
  usage|usage-*|login)
    case "$POOL" in
      A) ROLE="usage-a" ;;
      B) ROLE="usage-b" ;;
      codex) ROLE="usage" ;;
    esac
    ;;
  b-login)
    ROLE="usage-b"
    ;;
esac

MODEL=$(model_for "$ROLE")
EFFORT=$(effort_for "$ROLE")
# O366 (2026-09-14): explicit per-launch override for a dedicated seat (e.g. 648 on Fable HIGH). Logged so the
# table (rule 37: one decision, one place) stays the default and every exception is visible in the launch line.
if [ -n "${BD_LAUNCH_MODEL:-}" ] || [ -n "${BD_LAUNCH_EFFORT:-}" ]; then
  MODEL=${BD_LAUNCH_MODEL:-$MODEL}; EFFORT=${BD_LAUNCH_EFFORT:-$EFFORT}
  echo "$(date -u +%FT%TZ) OVERRIDE $NAME role=$ROLE model=$MODEL effort=$EFFORT (BD_LAUNCH_MODEL/BD_LAUNCH_EFFORT, O366)" >> /home/mboyle/bd-persist/logs/launch-override.log
  OVR=" model=$MODEL(OVERRIDE) effort=$EFFORT(OVERRIDE)"
fi
# 2026-09-13 O318/O322 (bd-pm-opus-A): per-launch override for the operator's model-by-task rules
# (sonnet workers -> opus medium on bounce rate; one opus HIGH worker for row 648). The table stays
# the single default (rule 37); an override is explicit, per launch, and printed on the LAUNCHED
# line so the seat's model is recorded where the census reads it. Before this, the only way was to
# switch model in-session, which no record captured (CLAUDE-WORKERS-LAUNCH.md, 2026-09-12).
MODEL_SRC=table; EFFORT_SRC=table
case "${BD_LAUNCH_MODEL:-}" in "") ;; opus|sonnet|haiku|fable|claude-*|gpt-*) MODEL=$BD_LAUNCH_MODEL; MODEL_SRC=override ;; *) die 3 "BD_LAUNCH_MODEL='$BD_LAUNCH_MODEL' is not opus|sonnet|haiku|fable|claude-<id>|gpt-<id> (O838: full id allowed, e.g. claude-opus-4-8)" ;; esac
case "${BD_LAUNCH_EFFORT:-}" in "") ;; low|medium|high|xhigh|ultra|max) EFFORT=$BD_LAUNCH_EFFORT; EFFORT_SRC=override ;; *) die 3 "BD_LAUNCH_EFFORT='$BD_LAUNCH_EFFORT' is not low|medium|high|xhigh|ultra|max -- was low|medium|high" ;; esac
# H553 (O819): the codex pool exec'd bd-codex-lens.sh with NO model and NO effort, so it fell to
# BD_LENS_MODEL's own default (gpt-5.6-sol) and picked its own effort -- BD_LAUNCH_MODEL/
# BD_LAUNCH_EFFORT (O366) were accepted, logged as an OVERRIDE, and then silently DROPPED on this
# pool, with nothing in the DRY or LAUNCHED line to say so. The PM launched bd-cx-astra-ultra as
# sol that way. The tier -> codex model table is sourced, never copied (FLEET_RULE 37).
. "${BD_CODEX_MODEL_LIB:-/home/mboyle/bd-persist/harness/lib_codex_model.sh}" || die 3 "model routing library unavailable"
CODEX_MODEL=$(codex_model_for "$MODEL")
CODEX_PROVIDER=$(codex_launch_provider) || die 3 "provider routing failed"
CODEX_DISPLAY_MODEL=$(codex_launch_model "$CODEX_MODEL") || die 3 "model routing failed"
CAP=$(autocompact_for "$ROLE")
[ -n "$MODEL" ] || die 3 "unknown role $ROLE -- add it to model_for and write $ROLE_DIR/$ROLE.prompt"
NAME_WAS_EXPLICIT=1
[ -n "$NAME" ] || { NAME=$(default_name "$ROLE" "$POOL"); NAME_WAS_EXPLICIT=""; }
# ** THE ACCOUNT MUST BE READABLE FROM THE SEAT NAME. Added 2026-09-09 on operator ruling. **
# MEASURED before the change: 6 of 30 live seats were on account B with NOTHING in the name to say
# so -- bd-briefauthor-2, bd-flakecourt-1, bd-integrator-d, bd-panel-1, bd-prereview, bd-status-1.
# Worse than absent: bd-flakecourt-1 sits beside bd-flakecourt-b1 and READS as the A-account one
# while being on B. The operator could not tell who was who, and neither could I without opening
# /proc/<pid>/environ for CLAUDE_CONFIG_DIR on every seat.
# The suffix is DERIVED FROM $POOL here, so a name can never disagree with the account again --
# the same fix shape as deriving the codex model from this launcher instead of a second table.
# ---- THE POOL SUFFIX, AND A NUMBER ONLY WHERE THE ROLE IS PLURAL. Operator schema 2026-09-09:
# "Each role will have a -A, and if it is like workers that have multiple agents in the role then
#  it is -A1 or -A2."
# ** THE INDEX IS DERIVED, NEVER TYPED. ** It is the lowest free slot, and "free" is measured the
# same way liveness is everywhere else: no tmux session of that name AND no live claim. A
# hand-picked index is a hand-maintained fact with an expiry nobody watches -- the class that gave
# us a dead bd-PM target, a probe hunting panes that no longer exist, and four retired seats in a
# health check. An explicit name from the caller is respected and only gets the pool suffix.
next_seat_index() {   # $1 role, $2 base, $3 pool-suffix
  local i=1
  while [ "$i" -le 32 ]; do
    tmux has-session -t "=$2-$3$i" 2>/dev/null < /dev/null || { echo "$i"; return; }
    i=$((i+1))
  done
  echo 1   # 32 live seats of one role is not a naming problem; let the tmux check refuse it.
}
case "$POOL" in
  A|B)
    SUF=$POOL
    case "$NAME" in
      *-A|*-B) : ;;
      *)
        CARD_N=$(awk -F'\t' -v r="$ROLE" '$1==r && $2!=""{print $2; exit}' \
                 "${BD_ROLE_CARDINALITY:-/home/mboyle/bd-persist/ROLE-CARDINALITY.tsv}" 2>/dev/null)
        if [ -z "$NAME_WAS_EXPLICIT" ] && [ "$CARD_N" = MULTI ]; then
          NAME="$NAME-$SUF$(next_seat_index "$ROLE" "$NAME" "$SUF")"
        else
          NAME="$NAME-$SUF"
        fi ;;
    esac ;;
esac

# ---- ROLE CARDINALITY GUARD. Item 3 of the triplet-HA plan, 2026-09-09, on operator rulings R1/R3.
# ** THE ARBITRATION EXISTED AND WAS FED BY NOBODY. ** bd-role-claim.sh could already answer "am I
# the active holder?", but MEASURED 2026-09-09: this launcher never claimed a role, and 0 of 24
# role prompts mention the tool. A registry nothing writes to answers every question with UNKNOWN.
# TWO HALVES, BOTH ASSERTED HERE -- the same contract shape that failed twice for bootstraps:
#   BEFORE the launch, REFUSE a second live holder of a SINGLE role (this block).
#   AFTER  the launch, CLAIM the role so the next launcher can see it (end of file).
# A refusal here costs nothing; a duplicate PM discovered later cost the operator an evening.
# UNKNOWN IS NOT PERMISSION (FLEET_RULE 6): a role absent from the table is refused, not allowed.
# This runs BEFORE the --dry-run exit on purpose, so the guard is testable without starting a seat.
RCLAIM=${BD_LAUNCH_ROLE_CLAIM:-/home/mboyle/bd-role-claim.sh}
if [ "${BD_LAUNCH_ALLOW_DUP:-0}" = 1 ]; then
  echo "bd-launch-role: ** BD_LAUNCH_ALLOW_DUP=1 -- cardinality guard BYPASSED for $ROLE. **" >&2
elif [ -x "$RCLAIM" ]; then
  CARDF=${BD_ROLE_CARDINALITY:-/home/mboyle/bd-persist/ROLE-CARDINALITY.tsv}
  CARD=$(awk -F'\t' -v r="$ROLE" '$1==r && $2!=""{print $2; f=1; exit} END{if(!f) print "UNKNOWN"}' "$CARDF" 2>/dev/null)
  case "$CARD" in
    MULTI) : ;;
    SINGLE)
      # `who` reaps first, so a dead holder never blocks a launch. Liveness is session AND pid.
      HOLDERS=$("$RCLAIM" who "$ROLE" 2>/dev/null | grep -v '^$' | grep -vxF "$NAME" || true)
      [ -z "$HOLDERS" ] || die 8 "$ROLE is SINGLE-HOLDER and is already held by: $(printf '%s' "$HOLDERS" | paste -sd, -). Launching $NAME would create a second authority. Stand the holder down first, or re-run with BD_LAUNCH_ALLOW_DUP=1 if you mean it."
      ;;
    *) die 8 "$ROLE has no cardinality in $CARDF, so it cannot be known whether a second copy is safe. UNKNOWN IS NOT PERMISSION -- add the role to the table." ;;
  esac
else
  echo "WARN cardinality guard SKIPPED: $RCLAIM is absent or not executable. A second SINGLE holder will NOT be refused." >&2
fi

PROMPT=$ROLE_DIR/$ROLE.prompt
[ -s "$PROMPT" ] || die 4 "no bootstrap prompt at $PROMPT (it must exist and be non-empty)"

# One line: send-keys -l sends a newline as Enter, which would submit the first
# line alone and leave the rest typing into a running turn. The prompt keeps its
# words; it loses only its line breaks. NAME is substituted so the generic
# handoff pointer names this session.
# The prompts are written by several authors and spell the placeholder three
# ways; all of them are made concrete, so a launched session is told the name of
# ITS OWN handoff rather than a template.
TEXT=$(tr '\n' ' ' < "$PROMPT" | tr -s ' ')
[ -n "$TEXT" ] || die 4 "bootstrap prompt $PROMPT collapsed to nothing"


# ---- 2026-09-08 T18:2xZ. THE ROLE NOW TRAVELS AS A SYSTEM-PROMPT FILE, NOT AS A MESSAGE.
# WHY, and it is the single most expensive class this fleet has hit twice in opposite directions:
#   05:5xZ  bd-say's LENGTH GUARD REFUSED a 4612-char role prompt -> bd-worker-b5/b6 ran ROLELESS 4h40m.
#   11:5xZ+ bd-say's INBOX SPOOL FILED it -> a seat received the 75-char string "INBOX /path" AS ITS
#           ENTIRE ROLE for ~8.5h. Both leave a seat ALIVE, IDLE AND ROLELESS -- indistinguishable
#           from one that is thinking, which is why neither was caught for hours.
# BOTH FAILURES EXIST ONLY BECAUSE THE ROLE TRAVELLED AS A MESSAGE. As --append-system-prompt-file
# it is part of the cached system prompt: it cannot be length-refused, cannot be spooled, cannot
# arrive truncated, and it survives a compaction without being re-sent. It also stops costing a
# fresh ~3k-token user message on every relaunch.
# The BD_SAY_KIND=bootstrap carve-out is now DEAD WEIGHT for this caller and is left in bd-say
# only because other callers may still assert it. A carve-out nobody triggers is not a carve-out.
SPFILE=/home/mboyle/bd-persist/role-systemprompts/$NAME.systemprompt
mkdir -p /home/mboyle/bd-persist/role-systemprompts
# NOT flattened: a system-prompt file keeps its line breaks. The one-line squeeze existed only
# because send-keys -l turns a newline into Enter and would submit the first line on its own.
# ---- ROW 864: SUBAGENT-PROMPT-CACHE-PREFIX-LOCK-AND-VOLATILE-TAIL-ISOLATION ----
# Freeze a static byte-exact prefix block (role prompt text, invariant rules, tools)
# across all seats of the same role, and isolate all seat-specific volatile data strictly
# to the tail. Prepending volatile timestamps or seat-name substitutions into the prefix
# invalidates provider KV prompt caches across LLM worker pools (O870c).
{
  # 1. STATIC BYTE-EXACT PREFIX BLOCK (FROZEN)
  cat "$PROMPT"
  echo
  # 2. VOLATILE TURN TAIL (ISOLATED SEAT IDENTITY & DYNAMIC POINTERS)
  echo "# ---- VOLATILE TAIL: SEAT IDENTITY & DYNAMIC POINTERS (ROW 864) ----"
  echo "YOU ARE $NAME. Your handoff is /home/mboyle/bd-persist/handoff-$NAME.md -- read it if it exists."
  echo "Your compact file is /home/mboyle/bd-persist/compact-$NAME.md."
  echo "Message tool: $SAY. Use this exact path; never guess a suffix."
  # ---- THE ROLE'S STATE, WHICH IS NOT THE SEAT'S HANDOFF. Item 9, 2026-09-09, ruling R2.
  # MEASURED: all 47 handoff files are keyed by SEAT NAME and none by role, and the three sed lines
  # above point every seat at handoff-<ITS OWN NAME>.md. So under R2, when the twin on the other
  # account TAKES OVER a stopped pool's SINGLE role, it is pointed at ITS OWN history and never at
  # the predecessor's in-flight work. THE HANDOVER READ THE WRONG FILE BY CONSTRUCTION and would
  # have looked like a clean start. This names the ROLE-keyed file as well.
  # BOTH HALVES ASSERTED HERE: the tool writes it, and this is what makes a seat READ it.
  echo "YOUR ROLE IS $ROLE. Its state is /home/mboyle/bd-persist/role-state/$ROLE.md -- READ IT FIRST."
  echo "That file is keyed by ROLE, not by seat: if you are taking this role over from another seat"
  echo "or another account, IT IS WHERE THE PREDECESSOR'S IN-FLIGHT WORK IS. Your own handoff above"
  echo "is your memory across a compaction; the role state is the ROLE's memory across a SEAT."
  echo "Keep it current: /home/mboyle/bd-role-state.sh set $ROLE $NAME \"<what is in flight>\""
} > "$SPFILE" || die 4 "could not write system-prompt file $SPFILE"
[ -s "$SPFILE" ] || die 4 "system-prompt file $SPFILE is empty"

if [ "$POOL" = codex ]; then
  [ -x "$CODEX" ] || die 8 "codex backend $CODEX is absent or not executable -- build it (harness-work/codex-lens) before launching a codex role"
  if [ -n "$DRY" ]; then
    echo "DRY $NAME pool=codex provider=$CODEX_PROVIDER role=$ROLE model=$CODEX_DISPLAY_MODEL($MODEL_SRC, claude tier $MODEL) effort=${EFFORT:-medium}($EFFORT_SRC) via $CODEX start $NAME $PROMPT"
    echo "DRY claim: $RCLAIM claim $ROLE $NAME"
    exit 0
  fi
  tmux has-session -t "=$NAME" 2>/dev/null && die 5 "tmux session $NAME already exists -- never relaunch over a live session"
  BD_LENS_MODEL=$CODEX_MODEL BD_LENS_EFFORT=${EFFORT:-medium} "$CODEX" start "$NAME" "$PROMPT" || die 6 "$CODEX start $NAME returned nonzero"
  if [ -x "$RCLAIM" ]; then
    "$RCLAIM" claim "$ROLE" "$NAME" >/dev/null 2>&1 \
      && CLAIMED=ok \
      || { CLAIMED=FAILED; echo "WARN could not record the role claim for $ROLE/$NAME -- the seat is UP but INVISIBLE to the guard" >&2; }
  else
    CLAIMED=skipped
  fi
  echo "LAUNCHED $NAME pool=codex provider=$CODEX_PROVIDER role=$ROLE model=$CODEX_DISPLAY_MODEL($MODEL_SRC, claude tier $MODEL) effort=${EFFORT:-medium}($EFFORT_SRC) autocompact=$CAP trust=none rolefile=systemprompt kick=none claim=${CLAIMED:-none} resume=${RESUME:-none} via bd-codex-lens.sh"
  exit 0
fi

# ** A1, 2026-09-08T19:4xZ. --name IS THE MESSAGING IDENTITY; --remote-control IS NOT. **
# MEASURED: seat launched as `--remote-control bd-msgtest-a` appeared in ListAgents as
# `bulkdownloader-35`, auto-generated from the cwd. Every seat this fleet ever launched was
# therefore UNADDRESSABLE BY ITS FLEET NAME over SendMessage -- the PM could not have messaged a
# seat by name even if it had tried. The docs say a session answers to --name or /rename; we set
# neither. Both flags now carry $NAME so the RC name and the messaging name are the same string.
# ** THE SEAT'S ENVIRONMENT MUST NOT DISABLE REMOTE CONTROL. Added 2026-09-09. **
# MEASURED, each one independently: DISABLE_TELEMETRY, DISABLE_ERROR_REPORTING and
# CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC EACH make claude refuse Remote Control --
#   "Remote Control requires feature-flag evaluation, which is disabled because <VAR> is set."
# All three were added to settings.json on 2026-09-08 as a token-efficiency measure and pushed to
# 12 hosts. Every seat after that took --remote-control, ran, answered SendMessage, AND WAS INVISIBLE
# IN THE APP -- breaking the standing rule that every VM launches with RC enabled.
# They are gone from settings now, but a launcher must not depend on the ambient environment being
# clean: this session, and any shell that started before the fix, still carries them and would pass
# them to a child. `env -u` guarantees the seat is RC-capable no matter who launches it.
# ** 2026-09-14 (BD-PM-A, VM-crash relaunch): ~/.claude/settings.json env sets ANTHROPIC_BASE_URL to the caveman proxy
# (127.0.0.1:8787) and claude REFUSES Remote Control on any endpoint that is not api.anthropic.com
# ("Remote Control is only available when using Claude via api.anthropic.com", debug log, bd-rctest-A).
# settings env is applied by claude itself, so `env -u` cannot clear it; --settings overrides it per launch.
# MEASURED: without it [bridge:repl] "bridge not enabled"; with it "v2 transport connected" and the operator saw the seat.
# Seats lose the caveman proxy (they already run --strict-mcp-config without caveman, O326.5); RC outranks it (operator rule).
# ** 2026-09-14 H492 (bd-worker-A4-A): ~/.claude/settings.json env sets ENABLE_TOOL_SEARCH=auto; in auto mode account A
# loads ALL 78 tool schemas (180 KB, first-response cache_read 64,885) while account B (unset = true) defers 64 of them
# (14 loaded, 88 KB, cache_read 30,529). Captured request bodies: bd-persist/ACCEPTANCE-H492-*. Forcing true here
# makes every launched seat identical on both accounts (rule 37: one decision, one place).
RCSET='{"env":{"ANTHROPIC_BASE_URL":"https://api.anthropic.com","ENABLE_TOOL_SEARCH":"true"}}'
CMD="env -u DISABLE_TELEMETRY -u DISABLE_ERROR_REPORTING -u CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC claude --settings '$RCSET' --remote-control $NAME --name $NAME --append-system-prompt-file $SPFILE"
[ -n "$MODEL" ] && CMD="$CMD --model $MODEL"   # O772: pin the resolved table/override model; the CLI otherwise inherits the config default (seats drifted to the wrong model). Short aliases (fable/opus/sonnet/haiku) match settings.json.
[ -n "$EFFORT" ] && CMD="$CMD --effort $EFFORT"
[ -n "$CAP" ] && CMD="$CMD --autocompact $CAP"
CMD="$CMD --permission-mode bypassPermissions"
# ** 2026-09-14 H494 (bd-worker-A4-A): the Artifact tool schema is 50,674 B in EVERY request (~13k tok) and tool search
# cannot defer it. MEASURED (H492 capture probe): body 125,568 -> 75,846 B with --disallowedTools Artifact. PM keeps it.
case "$ROLE" in pm|pm-b|cx-pm) ;; *) CMD="$CMD --disallowedTools Artifact" ;; esac
# O326.5 / Phase B: seats carry EXACTLY the fleet MCP (bd over http from test5) -- builders add serena (symbol-level reads
# instead of whole-file Reads). --strict-mcp-config ignores every user/project MCP (caveman, plugins) on the seat host.
case "$ROLE" in worker|worker-b|trainer|local-runner|local-a) MCPCFG=/home/mboyle/bd-persist/harness/mcp-seat-builder.json ;; *) MCPCFG=/home/mboyle/bd-persist/harness/mcp-seat-base.json ;; esac
[ -r "$MCPCFG" ] || die 6 "MCP seat config $MCPCFG unreadable -- a seat without the fleet MCP re-reads law by hand"
CMD="$CMD --strict-mcp-config --mcp-config $MCPCFG"
[ "$POOL" = B ] && CMD="CLAUDE_CONFIG_DIR=$CONFIG_B $CMD"
# --resume: the transcript is keyed by cwd (projects/<cwd with / and . -> ->) under the pool's config dir.
# Asserted HERE, before anything is started: a missing transcript makes claude open a FRESH session
# that looks exactly like a resumed one from the pane -- the silent-substitution class.
if [ -n "$RESUME" ]; then
  [ "$POOL" != codex ] || die 2 "--resume is a claude flag; pool codex has no transcript to resume"
  case "$RESUME" in [0-9a-f]*-[0-9a-f]*-[0-9a-f]*-[0-9a-f]*-[0-9a-f]*) : ;; *) die 2 "--resume '$RESUME' is not a session id" ;; esac
  RCFG=/home/mboyle/.claude; [ "$POOL" = B ] && RCFG=$CONFIG_B
  RKEY=$(printf '%s' "$WORKDIR" | sed 's#[/.]#-#g')
  RFILE=$RCFG/projects/$RKEY/$RESUME.jsonl
  [ -s "$RFILE" ] || die 4 "--resume transcript $RFILE absent or empty -- set BD_LAUNCH_WORKDIR to the cwd the dead session ran in"
  CMD="$CMD --resume $RESUME"
fi

# H485b: the account file outranks argv, so a file that differs from the owned value silently re-caps this seat.
# WARN, never refuse: a refused launch on an operator's typed /autocompact is worse than a recorded drift.
# stderr on purpose: bd-codex-drift-check.sh parses `head -1` of this script's stdout. BD_LAUNCH_SETTINGS_DIR is the test hook.
SEAT_CFG=/home/mboyle/.claude; [ "$POOL" = B ] && SEAT_CFG=$CONFIG_B; SEAT_CFG=${BD_LAUNCH_SETTINGS_DIR:-$SEAT_CFG}
SW=$(settings_window "$SEAT_CFG")
[ "$SW" = "$ACCOUNT_AUTOCOMPACT_WINDOW" ] || echo "WARN account-window: $SEAT_CFG/settings.json autoCompactWindow=$SW != launcher-owned $ACCOUNT_AUTOCOMPACT_WINDOW (H485b; the file wins over --autocompact $CAP)" >&2

if [ -n "$DRY" ]; then
  echo "DRY $NAME pool=$POOL role=$ROLE model=$MODEL effort=${EFFORT:-default} autocompact=$CAP cwd=$WORKDIR mcp=${MCPCFG##*/}"
  echo "DRY cmd: $CMD"
  [ -n "$RESUME" ] && echo "DRY resume: $RFILE ($(stat -c %s "$RFILE") bytes)"
  echo "DRY bootstrap: ${TEXT:0:80}..."
  # The tail matters more than the head: the pointer this session needs after a
  # limit or a compaction lives at the end, so name it rather than truncating it.
  case "$TEXT" in
    *"handoff-$NAME.md"*) echo "DRY bootstrap names handoff-$NAME.md (${#TEXT} chars)" ;;
    *) echo "DRY bootstrap NAMES NO HANDOFF (${#TEXT} chars)" ;;
  esac
  echo "DRY claim: $RCLAIM claim $ROLE $NAME"
  exit 0
fi

tmux has-session -t "=$NAME" 2>/dev/null && die 5 "tmux session $NAME already exists -- never relaunch over a live session"
[ -d "$WORKDIR" ] || die 6 "work dir $WORKDIR not found"
tmux new-session -d -s "$NAME" -x 220 -y 50 -c "$WORKDIR" -e BD_SEAT="$NAME" || die 6 "tmux new-session $NAME failed"   # O854: BD_SEAT = explicit bd-say identity
sleep 1
tmux send-keys -t "=$NAME:" -l "$CMD" || die 6 "could not type the launch command into $NAME"
sleep 1
tmux send-keys -t "=$NAME:" Enter || die 6 "could not submit the launch command in $NAME"

# The folder-trust menu DEFAULTS TO No and plain Enter EXITS the session
# (measured, bd-fable 22:3xZ). Answer it by moving down one line first.
TRUSTED=""
for _ in $(seq 1 20); do
  sleep 2
  P=$(tmux capture-pane -pt "$NAME:" 2>/dev/null)
  # ** A2. AN ENUMERATED DIALOG LIST IS A DENOMINATOR THAT GOES STALE. **
  # This loop matched exactly one string, "Yes, I trust this folder". On 2026-09-08 a seat came up
  # on a ** "Claude in Chrome" ** first-run dialog instead, sat blocked, and its kick was consumed
  # by the dialog -- ALIVE, IDLE AND ROLELESS again, from a dialog nobody had met before.
  # The fix is not to add Chrome to the list. It is to treat ANY dialog as a dialog.
  if printf '%s\n' "$P" | grep -q "Yes, I trust this folder"; then
    tmux send-keys -t "=$NAME:" Down; sleep 1; tmux send-keys -t "=$NAME:" Enter
    TRUSTED=answered; break
  fi
  # ANY OTHER CONFIRM SHAPE -> decline it. Esc/cancel is the safe answer to a dialog we do not know:
  # it never enables a feature, never trusts a folder, and never answers Yes to an unknown question.
  if printf '%s\n' "$P" | grep -qE 'Enter to confirm|Esc to cancel|Do you want to proceed|requires approval|❯ *1\. Yes'; then
    echo "NOTE $NAME hit an UNRECOGNISED startup dialog; declining it with Esc. Pane said: $(printf '%s' "$P" | grep -m1 -E 'Enter to confirm|Do you want to proceed|requires approval' | cut -c1-90)" >&2
    tmux send-keys -t "=$NAME:" Escape; sleep 2; TRUSTED=declined-unknown-dialog; continue
  fi
  printf '%s\n' "$P" | grep -q "bypass permissions on" && { TRUSTED=${TRUSTED:-not-asked}; break; }
done

READY=""
for _ in $(seq 1 30); do
  sleep 2
  tmux has-session -t "=$NAME" 2>/dev/null || die 6 "session $NAME EXITED during startup (trust=${TRUSTED:-none}) -- the trust menu default is No"
  tmux capture-pane -pt "$NAME:" | grep -q "bypass permissions on" && { READY=1; break; }
done
[ -n "$READY" ] || die 6 "$NAME never showed 'bypass permissions on' (trust=${TRUSTED:-none}); pane tail: $(tmux capture-pane -pt "$NAME:" | tail -3 | tr '\n' ' ')"

# ---- F6 FIX (bd-pm-b 2026-09-07 20:3xZ). THE MARKER MUST BE SET *HERE*, BY THE CALLER.
# bd-say carves bootstraps out of the length guard AND the inbox spool -- but BOTH carve-outs
# test BD_SAY_KIND, and THIS LINE, THE ONLY PLACE A ROLE PROMPT IS EVER SENT, NEVER SET IT.
# So from the S3 spool (11:5xZ) onward every ~3000-char role prompt was SPOOLED: the new seat
# received the 75-character string "INBOX /home/mboyle/bd-persist/inbox/<seat>/<stamp>.md"
# AS ITS ENTIRE ROLE, and came up ALIVE, IDLE AND ROLELESS -- which is indistinguishable from
# a seat that is thinking. That is the 4h40m unbootstrapping incident of 05:5xZ, rebuilt by a
# different mechanism: then the guard REFUSED the bootstrap, now the guard FILES it.
# MEASURED BEFORE THE FIX, on this exact call shape: no marker -> LEN=75 "INBOX ...";
# with marker -> LEN=2939, delivered verbatim.
# THE LESSON, AND IT IS THE NIGHT'S RECURRING ONE: A CARVE-OUT NOBODY TRIGGERS IS NOT A
# CARVE-OUT. The exemption was correct in bd-say and unreachable from the only caller that
# needed it, and nothing anywhere asserted that a bootstrap arrives whole.
# THE ROLE IS ALREADY IN THE SYSTEM PROMPT (see SPFILE above). This send is now only a KICK:
# a session that has its role but has taken no turn sits idle knowing who it is. The kick is
# ~30 characters, so it is inside bd-say's length guard by a wide margin and cannot be spooled
# for size -- the two failure modes that made a 3000-char bootstrap unreliable do not apply.
# ** AND THE FAILURE IS NOW LOUD INSTEAD OF SILENT. ** If this send is refused, the seat is
# ROLE-CORRECT and merely un-started; re-kicking it is safe and idempotent. Under the old scheme
# a refused send left a seat that would never know its role no matter how long you waited.
KICK="BEGIN. You have your role."
[ -n "$RESUME" ] && KICK="RESUMED as $NAME after a crash. Re-read role state; you have your role."
BD_SAY_KIND=bootstrap "$SAY" "$NAME" "$KICK" || die 7 "kick not consumed by $NAME (role IS loaded via --append-system-prompt-file; the seat is up and un-started, re-kick it)"

# PROVE THE SEAT ACTUALLY TOOK A TURN. A send that returns 0 is not a seat that started work --
# that conflation is the rc=6 class (FLEET_RULE 33) in the outbound direction.
# ** A3. THE FIRST VERSION OF THIS CHECK COULD ONLY SEE A TURN IN PROGRESS. **
# It polled for 'esc to interrupt' every 2s. bd-msgtest-a finished its whole turn in 4 seconds and
# the check printed "kick=UNCONFIRMED" on a seat that had worked perfectly. A PROBE THAT CAN ONLY
# SEE THE MIDDLE OF AN EVENT CANNOT CONFIRM A SHORT ONE. Now it accepts either evidence: a turn
# running, OR a turn that has ended (claude prints a "done H:MM" completion stamp).
KICKED=""
for _ in $(seq 1 15); do
  sleep 2
  P2=$(tmux capture-pane -pt "$NAME:" 2>/dev/null)
  # H-F1 (2026-09-21, lens bd-review-correctness-B1-B): THE PHRASE IS TRUNCATED, NOT ABSENT.
  # At tmux pane width 78 the Claude Code footer renders
  #   "bypass permissions on (shift+tab to cycle) . 4 memories . esc to inter…"
  # -- the "· N memories ·" segment (auto-memory, account B) costs exactly the width that pushes
  # "esc to interrupt" past the edge, so the full phrase NEVER appears and five live pool-B opus
  # seats that were demonstrably working read as unconfirmed (rc=7, FIXER/LAUNCH-RC7-POOLB-20260921T0950Z.md).
  # Pool A and the haiku usage-B seat carry no memories segment, render the phrase whole, and passed --
  # which is why this looked like a pool difference. It is a WIDTH difference. Match the surviving prefix.
  # NOT matched here: 'bypass permissions on'. That segment is on an IDLE pane too (measured, 12 live
  # seats), so keying on it would confirm a kick nobody took. Not matched either: a spinner VERB such as
  # 'Initializing agent role' -- the verb is randomised ('Booping…' was live on a working seat at 3m04s),
  # so one verb fixes one launch in N and leaves the false negative in place.
  printf '%s' "$P2" | grep -qi 'esc to inter'             && { KICKED=working; break; }
  printf '%s' "$P2" | grep -qE 'done [0-9]+:[0-9]+ [AP]M' && { KICKED=turn-completed; break; }
done
UNCONFIRMED=""
if [ -z "$KICKED" ]; then
  if [ -n "$ALLOW_UNCONFIRMED_KICK" ]; then
    echo "WARN $NAME took the kick but never showed a working state in 30s -- CHECK IT, do not assume it is thinking (allowed via --allow-unconfirmed-kick)" >&2
  else
    # H-F1: DO NOT `die` HERE. The old exit-in-place skipped BOTH the role claim and the LAUNCHED
    # line, so a seat that was merely LATE to render was left running, unclaimed and invisible to the
    # cardinality guard -- and a scripted caller, reading rc=7 as a failed launch, would start a
    # DUPLICATE on top of it. An unconfirmed kick is an unconfirmed MEASUREMENT, not a dead seat, and
    # unknown is never permission to act as if the seat is absent. Record the claim, print the line
    # (kick=UNCONFIRMED is visible in it), then exit 7 exactly as before so no caller's rc changes.
    UNCONFIRMED=7
    echo "bd-launch-role: $NAME took the kick but never showed a working state in 30s -- unconfirmed kick (use --allow-unconfirmed-kick to override); claiming the role anyway, the session IS up"
  fi
fi
# ---- CLAIM THE ROLE. The second half of the contract asserted by the guard above.
# The pid is derived by bd-role-claim.sh from the seat's tmux pane, NOT from this script: passing
# $$ would record the launcher's own pid, which exits immediately, and pid-based liveness would
# then reap the claim on the next sweep. Measured and fixed 2026-09-09 in item 2.
# NON-FATAL: the seat is up and working. A failed bookkeeping write must not read as a failed
# launch -- but it IS reported, because a silent claim failure returns us to a registry nothing
# writes to, which is the exact defect this item exists to close.
if [ -x "$RCLAIM" ]; then
  "$RCLAIM" claim "$ROLE" "$NAME" >/dev/null 2>&1 \
    && CLAIMED=ok \
    || { CLAIMED=FAILED; echo "WARN could not record the role claim for $ROLE/$NAME -- the seat is UP but INVISIBLE to the cardinality guard" >&2; }
else
  CLAIMED=skipped
fi
echo "LAUNCHED $NAME pool=$POOL provider=native-claude role=$ROLE model=$MODEL($MODEL_SRC) effort=${EFFORT:-default}($EFFORT_SRC) autocompact=$CAP trust=${TRUSTED:-none} rolefile=systemprompt kick=${KICKED:-UNCONFIRMED} claim=${CLAIMED:-none} resume=${RESUME:-none}"
# H-F1: the rc the caller sees is unchanged (7); what changed is that the claim and the
# LAUNCHED line now happen first, so the late seat is visible instead of orphaned.
[ -n "${UNCONFIRMED:-}" ] && exit "$UNCONFIRMED"
exit 0
