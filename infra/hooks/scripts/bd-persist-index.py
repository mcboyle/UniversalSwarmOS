#!/usr/bin/env python3
"""Maintain /home/mboyle/bd-persist/INDEX.tsv -- one row per .md in that directory.

WHY. 745 .md files sit in bd-persist root with no index. Every seat that needs a prior
finding either greps 745 files or asks somebody. The index is four columns and answers
"what exists, when, of what class, called what" in one read of ~90KB instead of a scan.

WHY IT RECONCILES RATHER THAN APPENDS ON CREATE. An append-on-create hook only sees files
created by the tool it is hooked to. These files also arrive by heredoc, by scp from a
host, by a collect, and by another account's session on the same filesystem. A RECONCILER
IS CORRECT FOR EVERY WRITER; AN APPENDER IS CORRECT ONLY FOR ITS OWN. It is also cheap:
it stats the directory, compares against the rows it already has, and writes only when
something is missing -- no re-read of file bodies that are already indexed.

STAMP PRECEDENCE. A UTC stamp embedded in the FILENAME is the authored time and outranks
mtime, which changes on every later append and would silently re-sort the history. Files
with no stamp in the name fall back to mtime and are MARKED `~` so a reader can tell a
recorded time from a guessed one -- three outcomes, not two.

CLASS is the leading ALL-CAPS token of the filename (LANDED, RAISE, MEASURE, RULING,
ORDER, RESOLVED, WITHDRAW, DEPLOYED...). A file with no such token gets `-`, which is
honest: it is not a claim that the file is uncategorised, only that the name carries no class.

Usage:  bd-persist-index.py [--check]     (--check exits 1 if rows are missing, writes nothing)
"""
import os, re, sys, time

ROOT = os.environ.get("BD_PERSIST_ROOT", "/home/mboyle/bd-persist")
INDEX = os.path.join(ROOT, "INDEX.tsv")
HEADER = "stamp\tclass\tfile\ttitle"
STAMP = re.compile(r"(\d{8}T\d{6}Z)")
CLASS = re.compile(r"^([A-Z][A-Z0-9_]{2,})[-_.]")

def title(path):
    try:
        with open(path, "r", errors="replace") as f:
            for _ in range(40):
                line = f.readline()
                if not line:
                    break
                t = line.strip().lstrip("#").strip()
                if t:
                    return re.sub(r"\s+", " ", t)[:160]
    except OSError:
        return "COULD NOT READ"
    return "(empty)"

def row(name):
    p = os.path.join(ROOT, name)
    m = STAMP.search(name)
    if m:
        s = m.group(1)
    else:
        s = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(os.path.getmtime(p))) + "~"
    c = CLASS.match(name)
    return "\t".join((s, c.group(1) if c else "-", name, title(p)))

def main():
    check = "--check" in sys.argv
    try:
        names = sorted(n for n in os.listdir(ROOT)
                       if n.endswith(".md") and os.path.isfile(os.path.join(ROOT, n)))
    except OSError as e:
        print(f"bd-persist-index: COULD NOT LOOK -- {ROOT}: {e}", file=sys.stderr)
        return 2
    have, rows = {}, []
    if os.path.exists(INDEX):
        with open(INDEX, errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line == HEADER:
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    have[parts[2]] = line
    missing = [n for n in names if n not in have]
    gone = [n for n in have if n not in set(names)]
    if check:
        print(f"bd-persist-index: {len(names)} files, {len(have)} indexed, "
              f"{len(missing)} MISSING, {len(gone)} indexed-but-absent")
        for n in missing[:20]:
            print("  MISSING " + n)
        return 1 if (missing or gone) else 0
    for n in names:
        rows.append(have.get(n) or row(n))
    rows.sort()
    tmp = INDEX + ".tmp"
    with open(tmp, "w") as f:
        f.write(HEADER + "\n")
        f.write("\n".join(rows) + "\n")
    os.replace(tmp, INDEX)          # atomic: a reader never sees a half-written index
    # SILENT WHEN NOTHING CHANGED. This runs as a PostToolUse hook on every Write, and a
    # hook that narrates on every no-op is a hook somebody switches off. Speak only on a delta.
    if missing or gone or "-v" in sys.argv:
        print(f"bd-persist-index: {len(rows)} rows (+{len(missing)} new, -{len(gone)} removed) -> {INDEX}",
              file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
