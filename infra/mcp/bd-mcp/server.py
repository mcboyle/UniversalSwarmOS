#!/usr/bin/env python3
"""bd-mcp -- ONE MCP server (stdio) that WRAPS the bd harness so a seat gets a bounded JSON
answer instead of a shell round trip and a log dump. Every tool calls the existing script or
reads the existing artifact; nothing is re-implemented. Reads are bounded by default; the only
mutations are say() and role_state_set(), both logged to bd-persist/logs/mcp.log.
FLEET_RULE 21: anything naming test2 / 10.0.70.95 / bd-capture-test2 is refused.

  run:      bd-mcp/venv/bin/python bd-mcp/server.py            (stdio; registered as "bd")
  selftest: bd-mcp/venv/bin/python bd-mcp/server.py --selftest
"""
from __future__ import annotations
import asyncio, json, os, re, sqlite3, subprocess, sys, time, hashlib, urllib.request, socket
from pathlib import Path

HOME = Path("/home/mboyle")
PERSIST = HOME / "bd-persist"
HARNESS = PERSIST / "harness"
ART = HOME / "fleet-run-artifacts"
ART_INFLIGHT = ART / "2026-08-25" / "inflight"          # bd-verify-cut.sh ART default
MCP_LOG = PERSIST / "logs" / "mcp.log"
USAGE_DB = PERSIST / "accounting" / "usage.sqlite"
GITEA = "http://10.0.70.162:3000"
GITEA_TOKEN = HOME / ".config" / "bd" / "gitea-token"
RUNNER_HOST = "10.0.70.83"
FORBIDDEN = ("test2", "10.0.70.95", "bd-capture-test2")
DEFAULT_MAX_LINES = 60
DEFAULT_MAX_BYTES = 12000

from pydantic import Field
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase

ArgModelBase.model_config["populate_by_name"] = True
def _custom_model_dump_one_level(self):
    return {fname: getattr(self, fname) for fname in self.__class__.model_fields}
ArgModelBase.model_dump_one_level = _custom_model_dump_one_level

mcp = FastMCP("bd")


# ---------------------------------------------------------------- helpers
def _refuse_forbidden(*texts: str):
    for t in texts:
        low = (t or "").lower()
        for f in FORBIDDEN:
            if f in low:
                raise ValueError(f"REFUSED: '{f}' is operator-only (FLEET_RULE 21)")


def _log(kind: str, **kw):
    MCP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with MCP_LOG.open("a") as fh:
        fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "kind": kind, **kw}) + "\n")


def _run(cmd: list[str], timeout: int = 60, cwd: str | None = None, env: dict | None = None) -> dict:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
                           env={**os.environ, **(env or {})})
        return {"rc": p.returncode, "out": _bound(p.stdout), "err": _bound(p.stderr, 2000)}
    except subprocess.TimeoutExpired:
        return {"rc": 124, "out": "", "err": f"timeout after {timeout}s"}
    except FileNotFoundError as e:
        return {"rc": 127, "out": "", "err": str(e)}


def _bound(s: str, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
    if s is None:
        return ""
    b = s.encode("utf-8", "replace")
    if len(b) <= max_bytes:
        return s
    return b[:max_bytes].decode("utf-8", "replace") + f"\n...[truncated {len(b) - max_bytes} bytes]"


def _cap_line(s: str, limit: int = 300) -> str:
    if not s or len(s) <= limit:
        return s or ""
    return s[:limit] + "..."


def _git(wt: str, *args: str) -> str:
    r = _run(["git", "-C", wt, *args], timeout=30)
    return r["out"].strip() if r["rc"] == 0 else f"UNKNOWN({r['err'].strip()[:120]})"


def _proc_start(pid: str) -> str | None:
    try:
        return open(f"/proc/{pid}/stat").read().split()[21]
    except Exception:
        return None


def _verify_holder(wt: str) -> dict:
    """Mirror of bd-land's bd_land_verify_holder: NONE | LIVE | STALE | UNKNOWN, over both artifact dirs."""
    real = os.path.realpath(wt)
    key = hashlib.sha256(real.encode()).hexdigest()
    out = {}
    for art in (ART_INFLIGHT, ART):
        lock = art / f".worktree-{key}.lock"
        if not lock.exists():
            out[str(art)] = "NONE"
            continue
        rec = lock / "holder"
        if not rec.is_file():
            out[str(art)] = "UNKNOWN no readable holder record"
            continue
        kv = dict(l.split("=", 1) for l in rec.read_text().splitlines() if "=" in l)
        pid, start, tag = kv.get("pid", ""), kv.get("start", ""), kv.get("tag", "unknown")
        if not pid.isdigit() or not start:
            out[str(art)] = "UNKNOWN holder record malformed"
            continue
        out[str(art)] = f"LIVE {pid} {tag}" if _proc_start(pid) == start else f"STALE {pid} {tag}"
    return out


# ---------------------------------------------------------------- tools: channel / roles
@mcp.tool()
def say(
    target: str,
    text: str,
    kind: str = "",
    from_seat: str = Field("", alias="from", description="Calling seat (sender identity, sets BD_SEAT)"),
    sender: str = "",
) -> dict:
    """Send text to a seat via bd-say.sh (the ONLY fleet channel). kind='bootstrap' only for a launch role prompt.
    Refuses test2/bd-capture-test2. Refuses when sender identity ('from' or 'sender') is missing.
    ~30 chars for updates; put detail in a file and send the PATH."""
    _refuse_forbidden(target, text)
    seat = (from_seat or sender or os.environ.get("BD_SEAT", "")).strip()
    if not seat:
        raise ValueError("REFUSED: sender identity required (pass 'from' or set BD_SEAT in environment)")
    env = {"BD_SEAT": seat}
    if kind == "bootstrap":
        env["BD_SAY_KIND"] = "bootstrap"
    r = _run(["bash", str(HOME / "bd-say.sh"), target, text], timeout=90, env=env)
    _log("say", target=target, chars=len(text), rc=r["rc"], sender=seat)
    return {"target": target, "rc": r["rc"], "result": (r["out"] + r["err"]).strip()[-300:]}


@mcp.tool()
def role_state_get(role: str) -> dict:
    """What a role has in flight (bd-role-state.sh get). exit 2 = no state."""
    r = _run(["bash", str(HARNESS / "bd-role-state.sh"), "get", role])
    return {"role": role, "rc": r["rc"], "state": r["out"].strip()}


@mcp.tool()
def role_state_set(role: str, seat: str, text: str) -> dict:
    """Record what a role has in flight (bd-role-state.sh set). Mutation; logged."""
    _refuse_forbidden(role, seat, text)
    r = _run(["bash", str(HARNESS / "bd-role-state.sh"), "set", role, seat, text])
    _log("role_state_set", role=role, seat=seat, rc=r["rc"])
    return {"role": role, "rc": r["rc"], "result": (r["out"] + r["err"]).strip()[-300:]}


@mcp.tool()
def who_all() -> dict:
    """Every LIVE role holder: role -> seat (bd-role-claim.sh who-all)."""
    r = _run(["bash", str(HOME / "bd-role-claim.sh"), "who-all"])
    rows = [l.split("\t", 1) for l in r["out"].splitlines() if "\t" in l]
    return {"rc": r["rc"], "holders": [{"role": a, "seat": b} for a, b in rows], "raw": r["out"].strip()[-800:] if not rows else ""}


@mcp.tool()
def claims() -> dict:
    """Object claims (which cut/train is held by which lens/seat) from bd-claim-object.sh's store review-claims.tsv."""
    cl = Path(os.environ.get("BD_OBJECT_CLAIMS", str(PERSIST / "review-claims.tsv")))  # bd-claim-object.sh store
    if not cl.is_file():
        return {"source": str(cl), "claims": [], "note": "FOUND NONE: claims file absent"}
    rows = []
    for l in cl.read_text().splitlines():
        parts = l.split("\t")
        if len(parts) >= 3 and not l.startswith("#"):
            rows.append({"object": parts[0], "lens": parts[1], "seat": parts[2], "ts": parts[3] if len(parts) > 3 else None})
    return {"source": str(cl), "claims": rows[-DEFAULT_MAX_LINES:], "count": len(rows), "note": "object,lens,seat,ts; take/release via bd-claim-object.sh"}


@mcp.tool()
def limits() -> dict:
    """Per-pool 5h/weekly headroom as bd-limit-watch.sh last wrote it (POOL_STATE.tsv). UNKNOWN is not permission."""
    p = PERSIST / "POOL_STATE.tsv"
    if not p.is_file():
        return {"pools": [], "note": "COULD NOT LOOK: POOL_STATE.tsv absent"}
    lines = p.read_text().splitlines()
    hdr = lines[0].split("\t")
    pools = [dict(zip(hdr, l.split("\t"))) for l in lines[1:] if l.strip()]
    return {"written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.stat().st_mtime)), "pools": pools}


# ---------------------------------------------------------------- tools: cuts / lanes / review
@mcp.tool()
def cut_status(worktree: str) -> dict:
    """Git identity of a cut worktree: branch, HEAD, index write-tree, dirty state, DONE.md/VERDICT line, verify-lock state."""
    _refuse_forbidden(worktree)
    wt = os.path.realpath(worktree)
    if not Path(wt, ".git").exists():
        return {"worktree": wt, "note": "COULD NOT LOOK: not a git worktree"}
    porcelain = _git(wt, "status", "--porcelain")
    done = Path(wt, "DONE.md")
    verdicts = sorted(str(p.relative_to(wt)) for p in Path(wt, ".review").glob("VERDICT-*.md")) if Path(wt, ".review").is_dir() else []
    return {
        "worktree": wt,
        "branch": _git(wt, "branch", "--show-current") or "DETACHED",
        "head": _git(wt, "rev-parse", "HEAD"),
        "head_tree": _git(wt, "rev-parse", "HEAD^{tree}"),
        "index_tree": _git(wt, "write-tree"),
        "mid_rebase": Path(wt, ".git", "rebase-merge").exists() or Path(wt, ".git", "rebase-apply").exists(),
        "dirty_lines": len([l for l in porcelain.splitlines() if l.strip()]),
        "untracked": [l[3:] for l in porcelain.splitlines() if l.startswith("??")][:20],
        "done_md": {"present": done.is_file(), "line1": done.read_text().splitlines()[0] if done.is_file() and done.read_text().strip() else None},
        "verdict_files": verdicts[:20],
        "verify_lock": _verify_holder(wt),
    }


@mcp.tool()
def lane_status(tag: str, max_lines: int = 12) -> dict:
    """Parse fleet-run-artifacts/verify-<tag>.log: phase RCs, start/end, VERDICT line, last lines. Bounded."""
    log = ART / f"verify-{tag}.log"
    if not log.is_file():
        return {"tag": tag, "note": f"COULD NOT LOOK: {log} absent"}
    txt = log.read_text(errors="replace")
    kv = {}
    for m in re.finditer(r"^([A-Z][A-Z0-9_]+)=(.*)$", txt, re.M):
        kv[m.group(1)] = m.group(2).strip()[:200]
    start = re.search(r"^\s*start (\S+)", txt, re.M)
    end = re.search(r"^\s*end (\S+)", txt, re.M)
    verdict = re.search(r"^VERDICT .*$", txt, re.M)
    tail_hint = [l for l in txt.splitlines() if re.match(r"^(NOT SHIPPABLE|SHIPPABLE|READY|RED:|RESULT:|LANDED|DOCS-ONLY)", l)]
    return {
        "tag": tag, "log": str(log),
        "start": start.group(1) if start else None, "end": end.group(1) if end else None,
        "running": end is None,
        "rcs": {k: v for k, v in kv.items() if k.endswith("_RC")},
        "identity": {k: kv[k] for k in ("CANDIDATE_SHA", "CANDIDATE_TREE", "BASE_SHA", "CHANGED_FILES", "BAND_FILES") if k in kv},
        "verdict": _cap_line(verdict.group(0)) if verdict else None,
        "outcome_lines": [_cap_line(l) for l in tail_hint[-6:]],
        "tail": [_cap_line(l) for l in txt.splitlines()[-max_lines:]],
    }


@mcp.tool()
def collect_gate(cut: str) -> dict:
    """Read-only review summary of a cut: each .review/VERDICT-*.md first line, traps.txt, MECHANICAL.md head, DONE.md line 1."""
    _refuse_forbidden(cut)
    wt = os.path.realpath(cut)
    rv = Path(wt, ".review")
    out = {"cut": wt, "verdicts": [], "traps": None, "mechanical": None, "done_line1": None}
    done = Path(wt, "DONE.md")
    if done.is_file():
        out["done_line1"] = (done.read_text().splitlines() or [""])[0]
    if rv.is_dir():
        for p in sorted(rv.glob("VERDICT-*.md")):
            lines = p.read_text(errors="replace").splitlines()
            out["verdicts"].append({"file": p.name, "line1": lines[0] if lines else "", "tree_line": next((l for l in lines[:15] if re.search(r"(TREE|PATCH-SHA256)", l)), None)})
        t = rv / "traps.txt"
        if t.is_file():
            out["traps"] = t.read_text().splitlines()[:DEFAULT_MAX_LINES]
        m = rv / "MECHANICAL.md"
        if m.is_file():
            out["mechanical"] = m.read_text().splitlines()[:20]
    return out


# ---------------------------------------------------------------- tools: accounting
@mcp.tool()
def usage(since_iso: str = "", group_by: str = "session", limit: int = 25) -> dict:
    """Token accounting from usage.sqlite: per session|role|model|host -> turns, max/mean context, total in/out tokens, cache read.
    since_iso like 2026-09-12T20:30:00Z (default: last 6h). Context = input+cached input per response."""
    return _usage(USAGE_DB, since_iso, group_by, limit)


def _usage(db_path, since_iso: str, group_by: str, limit: int) -> dict:
    # split from usage() so a test can point it at a scratch usage.sqlite (H485 acceptance)
    USAGE_DB = Path(db_path)
    if not USAGE_DB.is_file():
        return {"note": "COULD NOT LOOK: usage.sqlite absent"}
    if not since_iso:
        since_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 6 * 3600))
    if group_by not in ("session", "role", "model", "host"):
        return {"note": "group_by must be session|role|model|host"}
    c = sqlite3.connect(f"file:{USAGE_DB}?mode=ro", uri=True)
    rows = c.execute("""
        select r.provider, r.timestamp, r.model, r.usage, o.host, o.thread
        from usage_responses r left join usage_occurrences o
          on o.provider=r.provider and o.response_id=r.response_id
        where r.timestamp >= ? and r.quarantined=0""", (since_iso,)).fetchall()
    owners = {}
    for host, thread, owner in c.execute("select host, thread, owner from usage_assignments where owner is not null"):
        owners[(host, thread)] = owner
    agg = {}
    for provider, ts, model, uj, host, thread in rows:
        try:
            u = json.loads(uj or "{}")
        except Exception:
            u = {}
        # H485: the stored usage column is bd_cost_accounting.normalize() output, where input_tokens ALREADY
        # equals fresh+cache_creation+cache_read for BOTH providers (bd-usage-audit.py subtracts them back out).
        # Re-adding the cache fields here doubled every cached context (integrator-B: 933380 reported, 466691 real).
        # The jsonl's repeated assistant lines are deduped upstream by usage_responses PRIMARY KEY(provider,response_id).
        ctx = int(u.get("input_tokens", 0) or 0)
        key = {"session": (thread or "?")[:60], "role": owners.get((host, thread), thread or "?")[:60],
               "model": model or "?", "host": host or "?"}[group_by]
        a = agg.setdefault(key, {"turns": 0, "max_ctx": 0, "sum_ctx": 0, "out": 0, "cache_read": 0, "models": set(), "first": ts, "last": ts})
        a["turns"] += 1
        a["max_ctx"] = max(a["max_ctx"], ctx)
        a["sum_ctx"] += ctx
        a["out"] += int(u.get("output_tokens", 0) or 0)
        a["cache_read"] += int(u.get("cache_read_input_tokens", 0) or u.get("cached_input_tokens", 0) or 0)
        a["models"].add(model or "?")
        a["first"] = min(a["first"], ts); a["last"] = max(a["last"], ts)
    table = []
    for k, a in agg.items():
        table.append({"key": k, "turns": a["turns"], "max_ctx": a["max_ctx"], "mean_ctx": a["sum_ctx"] // max(a["turns"], 1),
                      "total_ctx": a["sum_ctx"], "out_tokens": a["out"], "cache_read": a["cache_read"],
                      "models": sorted(a["models"]), "first": a["first"], "last": a["last"]})
    table.sort(key=lambda r: -r["total_ctx"])
    return {"since": since_iso, "group_by": group_by, "responses": len(rows), "rows": table[:limit],
            "note": "total_ctx = sum over turns of context read (the cost function CONTEXT x TURNS)"}


# ---------------------------------------------------------------- tools: local CI
def _gitea(path: str):
    tok = GITEA_TOKEN.read_text().strip()
    req = urllib.request.Request(f"{GITEA}/api/v1{path}", headers={"Authorization": f"token {tok}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


@mcp.tool()
def gitea_ci(run: str = "latest", repo: str = "Mboyle/BD-ci", journal_job: str = "", journal_lines: int = 40) -> dict:
    """Local Gitea Actions run status: counts by status/conclusion, failed job names, wall time.
    journal_job='<job name>' adds a bounded failure slice from the .83 act_runner journal (the jobs API omits step stdout)."""
    try:
        if run == "latest":
            runs = _gitea(f"/repos/{repo}/actions/runs?limit=1").get("workflow_runs", [])
            if not runs:
                return {"note": "FOUND NONE: no runs"}
            run = str(runs[0]["id"])
        jobs = _gitea(f"/repos/{repo}/actions/runs/{run}/jobs?limit=100").get("jobs", [])
    except Exception as e:
        return {"note": f"COULD NOT LOOK: {e}"}
    from collections import Counter
    st = Counter(j["status"] for j in jobs)
    cc = Counter(j.get("conclusion") or "-" for j in jobs)
    failed = [j["name"] for j in jobs if j.get("conclusion") == "failure"]
    starts = [j["started_at"] for j in jobs if j.get("started_at") and not j["started_at"].startswith("0001")]
    ends = [j["completed_at"] for j in jobs if j.get("completed_at") and not j["completed_at"].startswith("0001")]
    out = {"repo": repo, "run": run, "jobs": len(jobs), "status": dict(st), "conclusion": dict(cc), "failed": failed,
           "first_start": min(starts) if starts else None, "last_end": max(ends) if ends and st.get("completed") == len(jobs) else None}
    if journal_job:
        _refuse_forbidden(journal_job)
        pat = re.escape(f"[CI/{journal_job}]")
        cmd = ("sudo journalctl -u act_runner --since '6 hours ago' --no-pager | grep -F '" + f"[CI/{journal_job}]" + "' "
               "| grep -vE 'DEBUG|::debug|Collecting|Downloading|━━|Requirement already' "
               "| grep -E 'FAILED|Error|error|❌|AssertionError|No module|E   |exitcode' | tail -n " + str(int(journal_lines)))
        r = _run(["ssh", "-o", "ConnectTimeout=8", RUNNER_HOST, cmd], timeout=60)
        out["journal"] = {"job": journal_job, "rc": r["rc"], "lines": r["out"].splitlines()[-int(journal_lines):], "err": r["err"][-200:]}
    return out


# ---------------------------------------------------------------- tools: fleet / logs
@mcp.tool()
def fleet_hosts(probe: bool = True) -> dict:
    """~/.config/bd/hosts with a 3s TCP:22 reachability probe per host (test2 listed, never probed)."""
    p = HOME / ".config" / "bd" / "hosts"
    hosts = []
    for l in p.read_text().splitlines():
        parts = l.split()
        if len(parts) >= 2:
            hosts.append({"name": parts[0], "ip": parts[1], "flags": parts[2:]})
    if probe:
        for h in hosts:
            if any(f in (h["name"] + h["ip"]) for f in FORBIDDEN):
                h["ssh"] = "NOT-PROBED (operator-only)"
                continue
            s = socket.socket(); s.settimeout(3)
            try:
                s.connect((h["ip"], 22)); h["ssh"] = "up"
            except Exception as e:
                h["ssh"] = f"down ({type(e).__name__})"
            finally:
                s.close()
    return {"hosts": hosts, "note": "hostnames are labels; the IP is the identity"}


@mcp.tool()
def log_slice(path: str, pattern: str = "", before: int = 0, after: int = 0, max_lines: int = DEFAULT_MAX_LINES, tail: bool = True) -> dict:
    """Bounded read of a file: lines matching a regex (with context) or the tail. Never returns more than max_lines. Use this instead of cat."""
    _refuse_forbidden(path)
    p = Path(os.path.expanduser(path))
    if not p.is_file():
        return {"path": str(p), "note": "COULD NOT LOOK: not a file"}
    lines = p.read_text(errors="replace").splitlines()
    total = len(lines)
    if pattern:
        rx = re.compile(pattern)
        idx = [i for i, l in enumerate(lines) if rx.search(l)]
        if tail:
            idx = idx[-max_lines:]
        else:
            idx = idx[:max_lines]
        keep = set()
        for i in idx:
            keep.update(range(max(0, i - before), min(total, i + after + 1)))
        sel = [(i + 1, lines[i]) for i in sorted(keep)][: max_lines * (1 + before + after)]
        return {"path": str(p), "total_lines": total, "matches": len(idx), "lines": [f"{n}: {_bound(l, 400)}" for n, l in sel]}
    sel = lines[-max_lines:] if tail else lines[:max_lines]
    return {"path": str(p), "total_lines": total, "lines": [_bound(l, 400) for l in sel]}


# ---------------------------------------------------------------- knowledge tools (Phase B, KNOWLEDGE-PLANE-PLAN W3, O326)
# T2 = bd-rag v2 over HTTP (cache .182, fallback test5). Every answer is a bounded SLICE with (path, heading, commit),
# never a file: a retrieved chunk is a claim about a commit (CLAUDE.md A1). No numpy here; the retriever owns that.
RAG_URLS = ("http://10.0.70.182:8099", "http://10.0.70.164:8099")
REPO = HOME / "BulkDownloader"
BRIEFS = HOME / "bd-codex-briefs"
LAW_PATHS = r"(COMMON\.md|COMMON-FLOOR\.md|FLEET_RULE\.md|LIVE-RULES\.md|CLAUDE\.md|CUT-WORKFLOW\.md|OPERATOR_DECISIONS\.md|CUT_TIERING\.md|LENS-)"
DOC_QUOTES = ('"""', "'''")


def _rag(endpoint: str, **qs):
    import urllib.parse
    q = urllib.parse.urlencode({k: v for k, v in qs.items() if v not in (None, "")})
    last = "no RAG endpoint reachable"
    for base in RAG_URLS:
        try:
            with urllib.request.urlopen(f"{base}{endpoint}?{q}", timeout=25) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001 -- the next endpoint is the remedy; the last error is reported
            last = f"{base}: {type(e).__name__}: {str(e)[:80]}"
    return {"note": f"COULD NOT LOOK: {last}"}


def _header_block(text: str, max_lines: int = 40) -> str:
    """Shebang + leading comment/docstring block: what a tool SAYS it does."""
    out, in_doc = [], False
    for i, l in enumerate(text.splitlines()[: max_lines + 20]):
        st = l.strip()
        if i == 0 and st.startswith("#!"):
            out.append(l); continue
        if in_doc:
            out.append(l)
            if any(q in st for q in DOC_QUOTES): in_doc = False
            continue
        if st.startswith(DOC_QUOTES):
            out.append(l); in_doc = not any(st.count(q) >= 2 for q in DOC_QUOTES); continue
        if st.startswith("#") or st == "" or st.startswith("from __future__"):
            out.append(l); continue
        break
    return "\n".join(out[:max_lines]).strip()


@mcp.tool()
def ask(question: str, k: int = 5, path_filter: str = "") -> dict:
    """Ask the authoritative knowledge plane (repo@commit, harness usage headers, live fleet law/state). Returns <=k slices
    {id,path,heading,commit,score,slice}; call more(id) for a chunk's neighbours. Hybrid BM25+dense: exact identifiers
    (bd-land-trio, O316, test_v3_66_939, rule 16) work. Never a whole file. path_filter is a regex on the path."""
    _refuse_forbidden(question, path_filter)
    r = _rag("/q", q=question, k=max(1, min(int(k), 8)), path=path_filter)
    return {"question": question, "hits": r} if isinstance(r, list) else r


@mcp.tool()
def more(chunk_id: int) -> dict:
    """The chunk named by an ask()/law() hit, whole, with its neighbours in the same path (<=3 chunks)."""
    r = _rag("/more", id=int(chunk_id))
    return {"chunks": r} if isinstance(r, list) else r


@mcp.tool()
def law(topic: str, k: int = 4) -> dict:
    """The fleet LAW on a topic -- COMMON.md sections, FLEET_RULE, LIVE-RULES, CLAUDE.md, CUT-WORKFLOW, OPERATOR_DECISIONS
    (O-numbers), CUT_TIERING, LENS-* -- as <=k slices. Quote a COMMON.md heading from COMMON-FLOOR.md to get its full section.
    Use this INSTEAD of reading COMMON.md (37K tokens) or OPERATOR_DECISIONS.md (2.3 MB)."""
    _refuse_forbidden(topic)
    r = _rag("/q", q=topic, k=max(1, min(int(k), 8)), path=LAW_PATHS)
    return {"topic": topic, "hits": r} if isinstance(r, list) else r


@mcp.tool()
def row(row_id: int) -> dict:
    """One backlog row by id: the canonical register line (project-knowledge/IMPROVEMENT_BACKLOG.md at the checkout's HEAD),
    the PM's re-derived ALL.tsv line, TRAINS.md mentions, and the newest brief path. The register is a lead, not a spec."""
    rid = str(int(row_id))
    out = {"row": rid}
    reg = REPO / "project-knowledge" / "IMPROVEMENT_BACKLOG.md"
    rx = re.compile(rf"^\|\s*{rid}\s*\|")
    hits = [l for l in reg.read_text(errors="replace").splitlines() if rx.match(l)] if reg.is_file() else []
    out["register"] = _bound(hits[0], 3000) if hits else "FOUND NONE in IMPROVEMENT_BACKLOG.md (archive/closed?)"
    out["register_head"] = _git(str(REPO), "rev-parse", "--short=8", "HEAD")
    alls = sorted(PERSIST.glob("PM-HANDOFF-*/REDERIVE-*/ALL.tsv"))
    if alls:
        ln = [l for l in alls[-1].read_text(errors="replace").splitlines() if l.startswith(rid + "\t")]
        out["rederived"] = {"file": str(alls[-1]), "line": _bound(ln[0], 2000) if ln else "FOUND NONE"}
    trains = PERSIST / "TRAINS.md"
    if trains.is_file():
        out["trains"] = [_bound(l.strip(), 300) for l in trains.read_text(errors="replace").splitlines() if re.search(rf"\b{rid}\b", l)][:6]
    briefs = sorted(BRIEFS.glob(f"ROW{rid}-*.md"), key=lambda p: p.stat().st_mtime)
    out["brief"] = str(briefs[-1]) if briefs else "FOUND NONE"
    return out


@mcp.tool()
def brief(row_id: int, max_bytes: int = DEFAULT_MAX_BYTES) -> dict:
    """The newest brief for a row (bd-codex-briefs/ROW<id>-*.md), bounded. Read this instead of the briefs directory."""
    rid = str(int(row_id))
    briefs = sorted(BRIEFS.glob(f"ROW{rid}-*.md"), key=lambda p: p.stat().st_mtime)
    if not briefs:
        return {"row": rid, "note": "FOUND NONE"}
    p = briefs[-1]
    return {"row": rid, "path": str(p), "bytes": p.stat().st_size, "text": _bound(p.read_text(errors="replace"), max_bytes)}


@mcp.tool()
def tool_doc(tool: str) -> dict:
    """What a tool SAYS it does: the usage header of toolchain/bin/<name> (at the checkout's HEAD), else bd-persist/harness/<name>,
    else ~/<name>. Verify what it EXECUTES before relying on it (A1). Returns the first comment/docstring block, <=40 lines."""
    _refuse_forbidden(tool)
    base = os.path.basename(tool)
    for cand in (REPO / "toolchain" / "bin" / base, HARNESS / base, HOME / base, HARNESS / (base + ".sh"), HOME / (base + ".sh")):
        if cand.is_file():
            return {"name": base, "path": str(cand), "header": _header_block(cand.read_text(errors="replace"))}
    return {"name": base, "note": "FOUND NONE in toolchain/bin, harness, ~"}


@mcp.tool()
def landed(path: str) -> dict:
    """Has a path landed, and as what? Last commit touching it on origin/main (after fetch), its blob at origin/main, and whether
    the checkout's HEAD carries the same blob. Compare BLOBS, not SHAs (A7: containment is a denominator choice)."""
    _refuse_forbidden(path)
    _run(["git", "-C", str(REPO), "fetch", "-q", "origin"], timeout=40)
    last = _git(str(REPO), "log", "-1", "--format=%h %cI %s", "origin/main", "--", path)
    blob_main = _git(str(REPO), "rev-parse", f"origin/main:{path}")
    blob_head = _git(str(REPO), "rev-parse", f"HEAD:{path}")
    return {"path": path, "origin_main": _git(str(REPO), "rev-parse", "--short=8", "origin/main"), "last_commit": last or "FOUND NONE on origin/main",
            "blob_main": blob_main[:12], "blob_head": blob_head[:12], "head_matches_main": blob_main == blob_head and not blob_main.startswith("UNKNOWN")}


@mcp.tool()
def evidence(path: str, ref: str = "main", repo: str = "Mboyle/BD-evidence", max_bytes: int = DEFAULT_MAX_BYTES) -> dict:
    """ONE FILE AT ONE COMMIT from Gitea without a clone (KNOWLEDGE-PLANE-PLAN W4): default repo BD-evidence (what
    bd-evidence-push.sh wrote: <host-ip>/<date>/<name>-<sha8>.<ext>), or any Gitea repo (e.g. Mboyle/BD-ci) at a sha/branch.
    Returns the decoded text bounded to max_bytes plus the blob sha; a missing path is FOUND NONE, transport failure is COULD NOT LOOK."""
    _refuse_forbidden(path, ref, repo)
    import base64, urllib.parse
    url = f"{GITEA}/api/v1/repos/{repo}/contents/{urllib.parse.quote(path)}?ref={urllib.parse.quote(ref)}"
    try:
        tok = GITEA_TOKEN.read_text().strip()
        req = urllib.request.Request(url, headers={"Authorization": f"token {tok}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        return {"repo": repo, "path": path, "ref": ref, "note": f"FOUND NONE (HTTP {e.code})" if e.code == 404 else f"COULD NOT LOOK: HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"repo": repo, "path": path, "ref": ref, "note": f"COULD NOT LOOK: {type(e).__name__}: {str(e)[:100]}"}
    text = base64.b64decode(d.get("content", "") or "").decode("utf-8", "replace") if d.get("encoding") == "base64" else ""
    return {"repo": repo, "path": path, "ref": ref, "blob_sha": d.get("sha"), "size": d.get("size"), "text": _bound(text, max_bytes)}


# ---------------------------------------------------------------- selftest
async def _selftest() -> int:
    tools = await mcp.list_tools()
    names = sorted(t.name for t in tools)
    print("TOOLS", len(names), " ".join(names))
    fails = 0

    async def call(name, **kw):
        nonlocal fails
        try:
            res = await mcp.call_tool(name, kw)
            content = res[0] if isinstance(res, tuple) else res
            txt = content[0].text if content and hasattr(content[0], "text") else str(content)
            d = json.loads(txt) if txt.startswith("{") else {"raw": txt}
            keys = list(d)[:6]
            print(f"OK   {name}({', '.join(f'{k}={v!r}' for k, v in kw.items())}) -> keys={keys} bytes={len(txt)}")
            return d
        except Exception as e:
            fails += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
            return {}

    await call("who_all")
    await call("limits")
    u = await call("usage", group_by="model")
    assert u.get("responses", 0) >= 0
    await call("gitea_ci", run="latest")
    await call("lane_status", tag="compact-backlog-1536")
    await call("cut_status", worktree="/home/mboyle/bd-cuts/compact-backlog-20260912")
    await call("collect_gate", cut="/home/mboyle/bd-cuts/compact-backlog-20260912")
    ls = await call("log_slice", path="/home/mboyle/bd-persist/roles-prompts/FLEET_RULE.md", pattern="^ ?2[0-9]\\.", max_lines=5)
    assert ls.get("matches", 0) >= 1, "positive control: FLEET_RULE numbered rules must match"
    await call("fleet_hosts", probe=False)
    a = await call("ask", question="which tool stamps the release trio at landing", k=3)
    hits = a.get("hits") if isinstance(a.get("hits"), list) else []
    assert any("bd-land-trio" in h.get("path", "") for h in hits), "positive control: ask() must find bd-land-trio"
    await call("law", topic="RUN PRECUT, THEN RESTORE, THEN WRITE DONE.md", k=2)
    r = await call("row", row_id=656)
    assert "656" in r.get("register", "") or "FOUND NONE" in r.get("register", ""), "row() must read the register line or say FOUND NONE"
    await call("brief", row_id=656, max_bytes=800)
    td = await call("tool_doc", tool="bd-land-trio")
    assert "Stamp" in td.get("header", ""), "positive control: bd-land-trio header"
    await call("landed", path="CLAUDE.md")
    ev = await call("evidence", path="README.md", ref="main")
    assert ev.get("blob_sha") or "COULD NOT LOOK" in ev.get("note", ""), "evidence(): README.md at main must resolve or say COULD NOT LOOK"
    ev404 = await call("evidence", path="does/not/exist.md")
    assert "FOUND NONE" in ev404.get("note", ""), "negative control: a missing evidence path is FOUND NONE"
    # negative control: forbidden target is refused, not sent
    try:
        await mcp.call_tool("say", {"target": "bd-capture-test2", "text": "x"})
        print("FAIL say(bd-capture-test2) was not refused"); fails += 1
    except Exception as e:
        print("OK   say(bd-capture-test2) refused:", str(e)[:80])
    # negative control: missing sender identity is refused
    old_bd_seat = os.environ.pop("BD_SEAT", None)
    try:
        await mcp.call_tool("say", {"target": "bd-pm-O5-A", "text": "x"})
        print("FAIL say() without sender was not refused"); fails += 1
    except Exception as e:
        print("OK   say() without sender refused:", str(e)[:80])
    finally:
        if old_bd_seat is not None:
            os.environ["BD_SEAT"] = old_bd_seat
    print("SELFTEST", "PASS" if fails == 0 else f"FAIL ({fails})")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(asyncio.run(_selftest()))
    if "--http" in sys.argv:
        # Phase B (O331): ONE server process on test5 (where role-state, claims, cuts, usage.sqlite and lane artifacts LIVE),
        # reachable by every seat on every host at http://10.0.70.164:8100/mcp (streamable-http). stdio stays for local use.
        mcp.settings.host = "0.0.0.0"; mcp.settings.port = int(os.environ.get("BD_MCP_PORT", "8100"))
        # The library's DNS-rebinding guard answers 421 to any Host but localhost; seats address this box by IP.
        from mcp.server.transport_security import TransportSecuritySettings
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=["10.0.70.164:*", "test5:*", "localhost:*", "127.0.0.1:*"], allowed_origins=[])
        mcp.run(transport="streamable-http")
    mcp.run(transport="stdio")
