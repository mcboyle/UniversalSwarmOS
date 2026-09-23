#!/usr/bin/env python3
"""PreToolUse hook: BLOCK a bare invocation of a repository toolchain tool.

THE LAW (operator, standing): `./venv/bin/python toolchain/bin/<tool>` ALWAYS;
`bd-<tool>` NEVER, on any host including test5. "Install nothing, remove nothing,
refresh nothing."

WHY IT BLOCKS AND DOES NOT WARN. /usr/local/bin carries 241 bd-* copies on this host
alone and 43 of them differ from the repository. Among the divergent ones are
bd-band-derive, which DECIDES WHICH TESTS RUN, plus bd-freshcheck, bd-ci-verdict and
bd-imports. A STALE TOOL RETURNS A WRONG NUMBER THAT LOOKS EXACTLY LIKE A RIGHT ONE AND
LEAVES NO TRACE -- there is no error, no exit code and nothing in the transcript to tell
a later reader which binary produced the figure. The fleet routed around warnings all
night, so this refuses.

THE DENOMINATOR IS ENUMERATED FROM THE REPOSITORY, NEVER FROM A LIST. The blocked set is
exactly `git ls-tree origin/main toolchain/bin/` restricted to names beginning `bd`.
A tool added to the repo tomorrow is covered tomorrow with no edit here. If the repo
cannot be read the hook ALLOWS and says so on stderr: a guard that cannot look must not
block work it cannot justify blocking, and silence would hide that it never ran.
"""
import json, os, re, subprocess, sys

REPO = os.environ.get("BD_TOOLPIN_REPO", "/home/mboyle/BulkDownloader")
CACHE = "/home/mboyle/bd-persist/harness/.toolpin-names"

def tool_names():
    """Names under toolchain/bin/ that begin with 'bd'. Repo first, cache as fallback."""
    try:
        out = subprocess.run(["git", "-C", REPO, "ls-tree", "--name-only",
                              "origin/main", "toolchain/bin/"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            names = {os.path.basename(p) for p in out.stdout.split()
                     if os.path.basename(p).startswith("bd")}
            if names:
                try:
                    with open(CACHE, "w") as f:
                        f.write("\n".join(sorted(names)))
                except OSError:
                    pass
                return names, "repo"
    except Exception:
        pass
    try:
        with open(CACHE) as f:
            names = {n.strip() for n in f if n.strip()}
        if names:
            return names, "cache"
    except OSError:
        pass
    return set(), "none"

# Shell metacharacters that start a new COMMAND POSITION. A tool name is only an
# invocation when it sits in one of these; `grep bd-precut` and `echo "use bd-precut"`
# are ARGUMENTS and blocking them would train everyone to disable the hook.
OPS = ("||", "&&", "$(", ";", "|", "&", "\n", "(", ")", "{", "}", "`")
# words that legitimately precede the real command word
PREFIX = {"sudo", "env", "time", "nohup", "exec", "command", "builtin", "xargs",
          "timeout", "stdbuf", "nice", "ionice", "setsid", "watch", "then", "do",
          "else", "elif", "!", "&&", "||"}
# Commands whose QUOTED ARGUMENT is itself a command line to be run somewhere else.
# These, and ONLY these, get their quoted payload re-analysed -- the law covers any host.
REMOTE = {"ssh", "rsh", "dsh", "pdsh", "sshpass"}

HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

def strip_heredocs(cmd):
    """Remove heredoc BODIES. They are data, not commands.

    CAUGHT IN PRODUCTION MINUTES AFTER THIS HOOK WAS WIRED, 2026-09-07T12:3xZ: writing a
    findings file with `cat > f <<'EOF' ... EOF` was REFUSED, because the file's own text
    quoted `bd-footguns --help` and `bd-precut` at the start of a line and the segmenter
    read those lines as commands. Every document this fleet writes about the tool-pin law
    would have been unwritable by the guard that enforces it.
    """
    out, lines, i = [], cmd.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        tags = [m.group(2) for m in HEREDOC.finditer(line)]
        i += 1
        for tag in tags:
            while i < len(lines) and lines[i].strip() != tag:
                i += 1
            i += 1                          # consume the terminator itself
    return "\n".join(out)

def segments(cmd):
    """Split into command-position segments, RESPECTING QUOTES.

    THIS FUNCTION EXISTS BECAUSE OF THE THIRD FALSE REFUSAL FROM THIS HOOK, 2026-09-07T13:4xZ.
    The previous version stripped every quote first, so that a tool invoked inside an ssh
    payload would still be seen -- and its comment claimed 'removing them cannot promote an
    argument into command position, because position is decided by the operators below, not
    by quoting.' THAT CLAIM IS FALSE, AND IT IS FALSE EXACTLY WHEN A QUOTED STRING CONTAINS
    AN OPERATOR. `pgrep -af 'bd-collect-gate|bd-precut'` became `... bd-collect-gate | bd-precut`
    and the second half read as a fresh command. A grep for two tool names -- the most ordinary
    thing an operator does while debugging the toolchain -- was refused.
    THIRD OCCURRENCE OF MY OWN GUARD OVER-REFUSING ON A SPAN/WINDOW MISTAKE (bd-say's menu
    detector, then heredoc bodies, now quote spans). Every time the predicate was right and the
    TEXT IT WAS APPLIED TO was wrong. THE WINDOW IS THE BUG, NOT THE PREDICATE.

    Yields (tokens, was_quoted_payload_of) pairs. Quotes are preserved as span markers here
    and removed per-token by the caller, so a quoted operator can never split a segment.
    """
    segs, cur, i, n, q = [], [], 0, len(cmd), None
    while i < n:
        c = cmd[i]
        if q:
            cur.append(c)
            if c == q:
                q = None
            i += 1
            continue
        if c in "'\"":
            q = c
            cur.append(c)
            i += 1
            continue
        two = cmd[i:i+2]
        if two in ("||", "&&", "$("):
            segs.append("".join(cur)); cur = []; i += 2; continue
        if c in ";|&\n(){}`":
            segs.append("".join(cur)); cur = []; i += 1; continue
        cur.append(c); i += 1
    segs.append("".join(cur))
    return segs

def tokenize(seg):
    """Whitespace-split a segment WITHOUT breaking a quoted span apart.

    `seg.split()` turned `ssh h "cd w && bd-freshcheck"` into seven tokens, none of which was a
    quoted string, so the remote-exec recursion below never fired and an ssh payload stopped
    being inspected at all. THE FIX FOR AN OVER-REFUSAL MUST NOT SILENTLY BECOME AN UNDER-REFUSAL:
    the selftest's two ssh cases caught this in the same minute it was written, which is the only
    reason it is not live. A guard's negative cases are the half that keeps it honest.
    """
    toks, cur, q = [], [], None
    for c in seg:
        if q:
            cur.append(c)
            if c == q:
                q = None
            continue
        if c in "'\"":
            q = c; cur.append(c); continue
        if c.isspace():
            if cur: toks.append("".join(cur)); cur = []
            continue
        cur.append(c)
    if cur: toks.append("".join(cur))
    return toks

def unquote(tok):
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "'\"":
        return tok[1:-1]
    return tok.replace("'", "").replace('"', "")

def offenders(cmd, names, _depth=0):
    hits = []
    flat = strip_heredocs(cmd) if _depth == 0 else cmd
    for seg in segments(flat):
        toks = tokenize(seg)
        i = 0
        while i < len(toks):
            t = toks[i]
            if "=" in t and not t.startswith("-") and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
                i += 1; continue          # VAR=value prefix assignment
            if t in PREFIX:
                # `command -v NAME` / `command -V NAME` ASK ABOUT the name; they do not run it.
                # The name is an ARGUMENT to a lookup, exactly as in `which` / `type` / `hash`,
                # which this parser already allows because they are not in PREFIX at all.
                # `command NAME` and `command -p NAME` DO run it and stay refused.
                # WHY THIS IS NOT A NUISANCE FIX: `command -v`, `type` and
                # `readlink -f $(command -v x)` are the exact diagnostics you use to INVESTIGATE
                # the tool-pin problem, so the guard was blocking the investigation of the thing
                # it guards, and bd-pm-b had to obfuscate a string to measure their own fleet.
                # FOURTH OCCURRENCE OF THIS GUARD'S ONE BUG: bd-say's menu detector, heredoc
                # bodies, quote spans, now lookup arguments. THE WINDOW IS THE BUG, NOT THE
                # PREDICATE -- every time, the predicate was right and the TEXT IT WAS APPLIED TO
                # was wrong.
                is_lookup = (t == "command")
                query = False
                i += 1
                # `timeout 240 bd-x` / `xargs -0 -r bd-x`: skip this prefix's own options
                while i < len(toks) and (toks[i].startswith("-") or toks[i].isdigit()
                                         or re.match(r"^\d+[smhd]$", toks[i])):
                    o = toks[i]
                    if is_lookup and o.startswith("-") and not o.startswith("--") and (
                            set(o[1:]) & {"v", "V"}):
                        query = True          # -v, -V, and clusters such as -pv
                    i += 1
                if query:
                    break                     # a lookup, not an invocation: this segment is clean
                continue
            word = unquote(t)
            # A REMOTE-EXEC PAYLOAD IS A COMMAND LINE, NOT A STRING. Recurse into the quoted
            # arguments of ssh and kin -- and ONLY of ssh and kin. That is the whole reason the
            # old version stripped quotes globally, and it is achievable without doing so.
            if word in REMOTE and _depth < 3:
                for rest in toks[i+1:]:
                    if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "'\"":
                        hits.extend(offenders(rest[1:-1], names, _depth + 1))
                break
            if "/" not in word and word in names:
                hits.append(word)
            break                          # only the command word of this segment
    return sorted(set(hits))

def _remedy(one):
    """The remedy line -- or, when the name is ambiguous, the LIST and no remedy."""
    objs = objects_for(one)
    if len(objs) > 1:
        lines = ["AND `%s` NAMES %d DIFFERENT OBJECTS ON THIS HOST. THIS HOOK PICKS NONE OF THEM:\n"
                 % (one, len(objs))]
        for kind, where in objs:
            lines.append("  %s %s\n" % (kind, where))
        lines.append("SAY WHICH ONE YOU MEANT, IN FULL. If it is the repo tool, write\n"
                     "  ./venv/bin/python toolchain/bin/%s   (from the repo root)\n" % one)
        return "".join(lines)
    return ("WRITE INSTEAD:  ./venv/bin/python toolchain/bin/%s   (from the repo root)\n"
            "REMOTELY:       cd <worktree> && ./venv/bin/python toolchain/bin/%s\n" % (one, one))


def objects_for(name):
    """EVERY live object a bare name could mean, enumerated at run time from the filesystem
    and from tmux -- never from a list in this file.

    WHY THIS EXISTS (bd-ideas' path check, 2026-09-07): `bd-status` is THREE different objects --
    toolchain/bin/bd-status (6,057 B, the sandbox health check), ~/bd-status.sh (2,621 B, a
    DIFFERENT PROGRAM, the cron status page), and a live tmux seat of that name. The refusal used
    to name the first and say nothing about the choice. A GUARD THAT RESOLVES AN AMBIGUITY ON THE
    USER'S BEHALF HAS STOPPED BEING A GUARD AND STARTED BEING A ROUTER.
    """
    out = []
    p = os.path.join(REPO, "toolchain", "bin", name)
    if os.path.exists(p):
        out.append(("repo tool      ", p))
    for cand in ("/home/mboyle/%s.sh" % name, "/home/mboyle/%s" % name):
        if os.path.exists(cand):
            out.append(("harness script ", cand))
    for cand in ("/home/mboyle/bd-persist/harness/%s.sh" % name,
                 "/home/mboyle/bd-persist/harness/%s" % name):
        if os.path.exists(cand):
            out.append(("harness mirror ", cand))
    try:
        r = subprocess.run(["tmux", "list-sessions", "-F", "#{session_name}"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and name in r.stdout.split():
            out.append(("tmux seat      ", name))
    except Exception:
        pass                                   # tmux absent -> one fewer object listed, never a crash
    return out


def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        sys.exit(0)                        # cannot parse the event -> never block
    if ev.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (ev.get("tool_input") or {}).get("command") or ""
    if not cmd:
        sys.exit(0)
    names, src = tool_names()
    if src == "none":
        print("bd-toolpin: COULD NOT LOOK -- toolchain/bin could not be enumerated from "
              f"{REPO} and no cache exists. THE TOOL-PIN GUARD DID NOT RUN. Allowing.",
              file=sys.stderr)
        sys.exit(0)
    bad = offenders(cmd, names)
    if not bad:
        sys.exit(0)
    one = bad[0]
    print(
        "bd-toolpin: REFUSED -- bare " + ", ".join(bad) + " in command position.\n"
        "THE TOOL PIN LAW: ./venv/bin/python toolchain/bin/<tool> ALWAYS; bd-<tool> NEVER,\n"
        "on any host including test5. Install nothing, remove nothing, refresh nothing.\n"
        f"A bare name resolves through PATH to /usr/local/bin/{one}, which is a COPY. 43 of\n"
        "the PATH copies differ from the repository -- among them bd-band-derive, which\n"
        "decides which tests run. A stale tool returns a wrong number that looks exactly\n"
        "like a right one and leaves no trace.\n"
        + _remedy(one) +
        "Nothing was run.", file=sys.stderr)
    sys.exit(2)

if __name__ == "__main__":
    main()
