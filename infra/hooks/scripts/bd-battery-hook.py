#!/usr/bin/env python3
"""bd-battery-hook.py -- PreToolUse(Bash) guard: at most BD_BATTERY_MAX (default 2, O358) DISTINCT local pytest batteries per host (H315).
Deterministic, no model. Exit 2 + stderr = refused (the seat sees the reason, nothing runs). Exit 0 = proceed.
Refuses a Bash command that would START a battery (pytest / bd-precut / bd-band / bd-mutate invocation) while another
battery is already running on this host, anchored by invocation (rule 10): 'python... -m pytest' or 'toolchain/bin/bd-precut'.
Never touches the running battery (bd-load-gate.sh's rule: nothing running is ever touched). Override for the integrator's
sanctioned path only: BD_BATTERY_HOOK=off in that seat's env."""
import json, os, re, shlex, subprocess, sys, time
if os.environ.get("BD_BATTERY_HOOK") == "off": sys.exit(0)
try: ev = json.load(sys.stdin)
except Exception: sys.exit(0)
cmd = (ev.get("tool_input") or {}).get("command") or ""
# v6 (H333, B4 FINDING 04:07Z): a battery is a tool in COMMAND POSITION, not a token anywhere. Split into simple
# commands, strip leading VAR=val and wrappers (env/exec/nice/nohup/time/timeout N/flock/sudo/stdbuf/command/ionice),
# then judge the FIRST token(s). `grep -c def toolchain/bin/bd-mutate` names a path; it starts nothing.
TOOLS = r"toolchain/bin/bd-(precut|band|mutate|ci-shards)$"
WRAP = {"env", "exec", "nice", "nohup", "time", "timeout", "flock", "sudo", "stdbuf", "command", "ionice"}
# H496(6b): a wrapper flag that takes a FOLLOWING value, not a bare switch (env -u NAME, flock -w SECONDS).
# Both stripping loops below used to leave that value dangling as its own token, misread as the command
# itself -- `env -u BD_INSTALL_DIR BD_DISABLE_KEEPALIVE=1 venv/bin/python -m pytest ...` (the real battery
# under /tmp/bd-battery.lock, INCIDENT-bd-worker-A10-A-20260914T2200Z.md) was never seen as a battery at all.
WRAP_VALUE_FLAGS = {"env": {"-u"}, "flock": {"-w"}}
def strip_wrappers(toks):
    while toks:
        t = toks[0]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t): toks.pop(0); continue
        if t in WRAP:
            toks.pop(0)
            valflags = WRAP_VALUE_FLAGS.get(t, set())
            while toks:
                nt = toks[0]
                if nt in valflags:
                    toks.pop(0)
                    if toks: toks.pop(0)
                    continue
                if nt.startswith("-") or (t == "timeout" and re.match(r"^\d+[smhd]?$", nt)) or (t == "flock" and nt.startswith("/")):
                    toks.pop(0); continue
                break
            continue
        break
    return toks
def battery_segment(seg):
    toks = strip_wrappers(seg.strip().split())
    if not toks: return False
    t0 = toks[0]; t1 = toks[1] if len(toks) > 1 else ""; t2 = toks[2] if len(toks) > 2 else ""
    if re.search(r"(^|/)python[0-9.]*$", t0):
        return (t1 == "-m" and t2 == "pytest") or bool(re.search(TOOLS, t1))
    return bool(re.search(r"(^|/)pytest$", t0) or re.search(TOOLS, t0))
def unwrap_shc(seg):
    """H496(6b), SIDE FINDING (a) of ACCEPTANCE-H496-6: `env -u X bash -c '<battery>'` is one argument to
    bash, not a pipeline -- quote-blanking made it invisible to detection AND route() refused it as
    'a pipeline/compound command' if the inner string happened to contain ;|(). Unwrap it to the inner
    text ONLY when the wrapped shell call is one WHOLE `&&`-segment (nothing trails it within that
    segment) -- a genuinely compound inner ('cmd1 && cmd2') is unwrapped too, but then judged on its own
    merits downstream (each half becomes its own segment), same as if the seat had typed it unwrapped."""
    try: toks = shlex.split(seg, posix=True)
    except ValueError: return seg
    rest = strip_wrappers(list(toks))
    if len(rest) == 3 and rest[0] in ("bash", "sh") and rest[1] == "-c":
        return rest[2]
    return seg
def unwrap_shc_text(text):
    """Apply unwrap_shc PER `&&`/newline-separated segment (a `cd <wt> &&` prefix must not hide a
    trailing `bash -c '<battery>'` segment from either detection or route())."""
    segs = re.split(r"&&|\n", text)
    new_segs = [unwrap_shc(s.strip()) for s in segs]
    if new_segs == [s.strip() for s in segs]: return text
    return " && ".join(new_segs)
for _ in range(3):
    nxt = unwrap_shc_text(cmd)
    if nxt == cmd: break
    cmd = nxt
raw = cmd   # H496(6): routing re-reads the ORIGINAL (post-unwrap) text; the judged copy below has its quotes and heredocs blanked
# Only INVOCATIONS count: drop heredoc bodies and quoted strings first (a brief that MENTIONS pytest is not a battery).
cmd = re.sub(r"<<-?\s*'?(\w+)'?[^\n]*\n.*?\n\1\s*$", " ", cmd, flags=re.S | re.M)
cmd = re.sub(r"'[^']*'|\"[^\"]*\"", " ", cmd)
segs = [x for x in re.split(r"\n|;|&&|\|\||\||&|\(|\)", cmd) if x.strip()]
bat = [x for x in segs if battery_segment(x)]
if not bat: sys.exit(0)
# bd-worker-precut.sh is a REMOTE driver (the battery runs on bd2): neither gated nor counted (B5 STALL 02:32Z, O358).
MAXB = int(os.environ.get("BD_BATTERY_MAX", "2"))   # O358: test5 survived cpu96/mem192 (O355); LIVE-RULES one relaxed to TWO local batteries
def probe(seg):   # a probe, not a battery: --version/--co, or a single node id without -n
    if re.search(r"pytest\s+(--version|--co\b|--collect-only)", seg): return True
    return bool(re.search(r"pytest\b[^\n]*\S+::\S+", seg) and not re.search(r"pytest\b[^\n]*\s-n\s*\d", seg))
if all(probe(x) for x in bat): sys.exit(0)
try:
    ps = subprocess.run(["ps", "-eo", "pid,etimes,args"], capture_output=True, text=True, timeout=5).stdout.splitlines()[1:]
except Exception: sys.exit(0)
me = os.getpid(); running = []
for l in ps:
    f = l.split(None, 2)
    if len(f) < 3: continue
    pid, et, args = int(f[0]), int(f[1]), f[2]
    if pid == me or pid == os.getppid(): continue
    # Anchor on the INVOCATION at argv start (rule 10, B6 FINDING 02:38Z): a Bash-tool wrapper shell carries the whole
    # command text in its argv (`bash -c source snapshot... eval '<cmd>'`), so a wait loop that MENTIONS the pattern is not a battery.
    if "shell-snapshots/" in args or args.startswith(("/bin/bash ", "bash ", "sh ", "/bin/sh ")): continue
    if re.search(r"^\S*python[0-9.]*\s+-m\s+pytest\b|^\S*python[0-9.]*\s+\S*toolchain/bin/bd-(precut|mutate)\b", args):
        try: cwd = os.readlink(f"/proc/{pid}/cwd")
        except OSError: cwd = "?"
        # B5 DEFECT 4 (03:24Z): a pytest run inside a /tmp or scratchpad sandbox is a probe, not a battery. Only a run
        # rooted in a repo checkout (BulkDownloader, bd-local-wt, bd-worker-wt, bd-cuts, .bd-bands) counts.
        if cwd.startswith(("/tmp/", "/var/tmp/", "/dev/shm/")): continue
        running.append((pid, et, cwd))
# count DISTINCT batteries (one pytest -n 12 battery is many processes sharing a cwd), not processes
if len({r[2] for r in running}) < MAXB: sys.exit(0)
running.sort(key=lambda r: -r[1])
pid, et, cwd = running[0]
distinct = sorted({r[2] for r in running})
HOOKLOG = "/home/mboyle/bd-persist/logs/battery-hook.log"

# H496(6) (O639, 2026-09-14): THE LOCAL CAP IS NOT THE POOL'S CAP. Four seats sat in "wait in a separate command" loops
# while bd2 idled at load 0. A battery this seat can run remotely is ROUTED (PreToolUse updatedInput) to
# bd-worker-precut.sh -- the pool's own admission (slots, load, rc 64 = full) -- with BD_PRECUT_QUEUE_WAIT=0 so a full
# pool comes straight back as 64 instead of blocking the tool call; only THEN does the seat queue locally, told who
# holds the local slots and its position. Routable = a single battery (optionally after `cd <wt> &&`/VAR=val) that
# bd-worker-precut.sh can express: pytest over EXISTING test paths, `bd-precut --gate`, or bd-mutate --spec (no --work).
WT_ROOTS = tuple(os.environ.get("BD_BATTERY_WT_ROOTS", "/home/mboyle/bd-local-wt/:/home/mboyle/bd-cuts/:/home/mboyle/bd-worker-wt/").split(":"))   # env = TEST SEAM
PYOPT_WITH_VALUE = {"-n", "-p", "-k", "-o", "-c", "-W", "-m", "--timeout", "--timeout-method", "--dist", "--max-worker-restart", "--maxfail"}

def strip_outer_parens(s):
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        is_outer = True
        for i, c in enumerate(s):
            if c == '(': depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0 and i < len(s) - 1:
                    is_outer = False
                    break
        if is_outer and depth == 0:
            s = s[1:-1].strip()
        else:
            break
    return s

def extract_battery_selectors(seg):
    toks = strip_wrappers(seg.strip().split())
    if not toks: return None
    if re.search(r"(^|/)python[0-9.]*$", toks[0]): toks.pop(0)
    if toks[:2] == ["-m", "pytest"] or re.search(r"(^|/)pytest$", toks[0]):
        toks = toks[2:] if toks[0] == "-m" else toks[1:]
        selectors = []; i = 0
        while i < len(toks):
            t = toks[i]
            if t.startswith("-"):
                if t in PYOPT_WITH_VALUE: i += 1
                i += 1; continue
            selectors.append(t)
            i += 1
        return ("pytest", selectors)
    elif re.search(r"toolchain/bin/bd-precut$", toks[0]):
        return ("precut", [])
    elif re.search(r"toolchain/bin/bd-mutate$", toks[0]):
        return ("mutate", toks[1:])
    return None

def route(cmd):
    """The bd-worker-precut.sh command that runs this battery on the pool, or None with the reason it cannot."""
    # O1084 / SYN-67: allow output-truncating pipeline (| tail, | head, | cat) and outer parentheses
    cmd = re.sub(r"\s*\|\s*(tail|head|cat)\b[^\n;&|()]*$", "", cmd).strip()
    cmd = strip_outer_parens(cmd)

    segs = [x.strip() for x in re.split(r"&&|\n", cmd) if x.strip()]
    cwd = os.getcwd(); bats = []
    for seg in segs:
        seg = strip_outer_parens(seg)
        toks = seg.split()
        if toks and toks[0] == "cd" and len(toks) == 2:
            cwd = os.path.abspath(os.path.join(cwd, os.path.expanduser(toks[1])))
            continue

        # O1084 / SYN-67: allow (a || b) naming the same file twice as one battery
        if "||" in seg:
            branches = [strip_outer_parens(b) for b in re.split(r"\|\|", seg) if b.strip()]
            if len(branches) > 1 and all(battery_segment(b) for b in branches):
                infos = [extract_battery_selectors(b) for b in branches]
                if all(info is not None for info in infos):
                    first_kind, first_sel = infos[0]
                    if all(kind == first_kind and set(sel) == set(first_sel) for kind, sel in infos):
                        seg = branches[0]
                        toks = seg.split()

        if re.search(r"\|\||;|\||\(|\)", seg):
            return None, "a pipeline/compound command (route the bare battery yourself)"
        if battery_segment(seg):
            bats.append(toks)
            continue
        return None, f"a segment that is neither cd nor a battery: {seg[:60]}"
    if len(bats) != 1: return None, f"{len(bats)} batteries in one command"
    if not cwd.startswith(WT_ROOTS) or not os.path.exists(os.path.join(cwd, ".git")):
        return None, f"cwd {cwd} is not a cut worktree under {'|'.join(WT_ROOTS)}"
    toks = strip_wrappers(bats[0])   # H496(6b): shared with battery_segment -- was a lone linear pop that
    # left a value-taking flag's value (env -u NAME, flock -w SECONDS) as a dangling bogus command head.
    if not toks: return None, "empty battery"
    if re.search(r"(^|/)python[0-9.]*$", toks[0]): toks.pop(0)
    mode, args = None, []
    if toks[:2] == ["-m", "pytest"] or re.search(r"(^|/)pytest$", toks[0]):
        toks = toks[2:] if toks[0] == "-m" else toks[1:]; mode = "band"; i = 0
        while i < len(toks):
            t = toks[i]
            if t.startswith("-"):
                if t in PYOPT_WITH_VALUE: i += 1
                i += 1; continue
            path = t.split("::", 1)[0]
            if not os.path.exists(os.path.join(cwd, path)): return None, f"selector {t} is not a path in {cwd}"
            args.append(t); i += 1
        if not args: return None, "pytest with no test paths (a whole-suite run is the lane's, never a worker's)"
        # O1084 / SYN-67: deduplicate paths while preserving order
        args = list(dict.fromkeys(args))
    elif re.search(r"toolchain/bin/bd-precut$", toks[0]):
        mode = "precut"
    elif re.search(r"toolchain/bin/bd-mutate$", toks[0]):
        if any(t == "--work" or t.startswith("--work=") for t in toks): return None, "bd-mutate --work names a scratch; use bd-mutate-wt.sh or drop --work to route"
        mode = "mutate"; args = toks[1:]
    else:
        return None, f"{toks[0]} has no remote mode"
    try:
        head = subprocess.run(["git", "-C", cwd, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip()
        staged = subprocess.run(["git", "-C", cwd, "diff", "--cached", "--quiet"], timeout=5).returncode == 1
    except Exception as exc:
        return None, f"git in {cwd}: {exc}"
    if not re.fullmatch(r"[0-9a-f]{40}", head): return None, f"no HEAD in {cwd}"
    pre = "BD_PRECUT_QUEUE_WAIT=0 " + ("" if staged else "BD_WORKER_BASE_CONTROL=1 ") + ("BD_WORKER_MODE=mutate " if mode == "mutate" else "")
    q = " ".join(subprocess.list2cmdline([a]) for a in args)
    return f"cd {cwd} && {pre}/home/mboyle/bd-worker-precut.sh {cwd} {head}{(' ' + q) if q else ''}", mode

routed, why = route(raw)
ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
if routed:
    with open(HOOKLOG, "a") as w:
        w.write(f"{ts} ROUTED seat_cwd={os.getcwd()} mode={why} running={len(running)} cmd={routed}\n")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
        "updatedInput": {"command": routed},
        "permissionDecisionReason": f"H496(6): {len(distinct)} local batteries running (cap {MAXB}); routed to the pool"},
        "systemMessage": f"bd-battery-hook H496(6): local cap {MAXB} reached ({', '.join(distinct)}); this battery was ROUTED to the pool as `{routed}`. "
                         f"rc 64 = pool full too: re-run the ORIGINAL command later (the hook then tells you holder+position). Read the .worker-precut-*.log it names."}))
    sys.exit(0)
# residual: cannot route -> local queue, with the holders and this seat's position (refusals by OTHER seat cwds in the last 10 min)
ahead = set()
try:
    cutoff = time.time() - 600
    for l in open(HOOKLOG).read().splitlines()[-400:]:
        m = re.match(r"(\S+) REFUSED seat_cwd=(\S+)", l)
        if m and m.group(2) != os.getcwd() and time.mktime(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ")) - time.timezone > cutoff: ahead.add(m.group(2))
except Exception: pass
cmd_excerpt = " ".join(raw.split())[:300]   # H496(6b): a REFUSED line named no cmd, so its shape (bash -c?
# flock -w? a real pipe?) was unrecoverable after the fact -- exactly what blocked auditing the 7/8 real
# refusals this row was dispatched to explain.
with open(HOOKLOG, "a") as w:
    w.write(f"{ts} REFUSED seat_cwd={os.getcwd()} running={len(running)} oldest pid={pid} {et}s cwd={cwd} unroutable={why} cmd={cmd_excerpt}\n")
holders = "; ".join(f"pid {p} {e}s in {c}" for p, e, c in sorted({(r[0], r[1], r[2]) for r in running if r[2] in distinct}, key=lambda r: r[2])[:MAXB * 2])
print(f"REFUSED (bd-battery-hook, O358: at most {MAXB} distinct local batteries on this host): {len(distinct)} already running "
      f"({len(running)} processes). HOLDERS: {holders}. POSITION: {len(ahead) + 1} (seats refused here in the last 10 min: {len(ahead)} ahead). "
      f"NOT ROUTED to the pool (H496(6)): {why}. Nothing was run. "
      f"WAIT IN A SEPARATE COMMAND (a wait loop and the battery in ONE command is refused, D5): "
      f"`while pgrep -f 'python[0-9.]* -m pytest' >/dev/null; do sleep 60; done` on its own, then re-run this exact command. "
      f"Or use `bd-pytest-wait <test-file>` (sanctioned wait helper for compound wait shapes, SYN-67). "
      f"Or route it yourself: /home/mboyle/bd-worker-precut.sh <wt> <base> [tests/x.py ...] (not gated). Do NOT kill a running battery.", file=sys.stderr)
sys.exit(2)
