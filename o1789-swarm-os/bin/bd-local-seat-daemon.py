#!/usr/bin/env python3
"""
bd-local-seat-daemon.py — Active Autonomous Local GPU Worker Seat Daemon (O3341 / O3353).

In addition to draining `/home/mboyle/bd-persist/inbox/<seat>/*.md`, each local GPU seat
autonomously pulls and executes real fleet work every cycle:
1. Inbox packets (`/home/mboyle/bd-persist/inbox/<seat>/*.md`)
2. Local Pre-Gate Diff Reviews (`--mode pregate`): scans active worktrees in `/home/mboyle/bd-cuts/`
   and `/home/mboyle/bd-review-wt/`, computes `git diff` against base/HEAD~1, runs local LLM
   behavioral defect review, and writes `/home/mboyle/bd-persist/harness-work/O1789/local-seats/<seat>/PREGATE-<cut>.md`.
3. Queue Row Triage & Code Probe (`--mode triage`): scans open/held/stale rows in
   `P2-FIX-QUEUE.tsv`, `BH2-BUILD-QUEUE.tsv`, and `BH1-BACKLOG-QUEUE.tsv`, inspects referenced
   files in `/home/mboyle/BulkDownloader` or `/home/mboyle/bd-persist/harness`, and writes
   actionable local triage & patch briefs for dispatchers (`F1-D`, `B5-B`, `D2-D`, `H1-A`).
"""

import argparse
import csv
import glob
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path


SHADOW_BOOT_TS = time.time()
LOADED_CANON_MODELS = ("cyberstrike-35b:q4_k_m", "Qwen3.6-35B-A3B-Heretic", "Qwen3-Coder-30B-A3B", "Qwen2.5-Coder-32B")

def _canon_model_name(endpoint: str, model: str) -> str:
    ml = model.lower()
    if "10.0.10.137" in endpoint or "cyberstrike" in ml:
        return "cyberstrike-35b:q4_k_m"
    if "10.0.70.83" in endpoint or "heretic" in ml:
        return "Qwen3.6-35B-A3B-Heretic"
    if "10.0.70.72" in endpoint or "30b" in ml:
        return "Qwen3-Coder-30B-A3B"
    if "10.0.70.125" in endpoint or "32b" in ml:
        return "Qwen2.5-Coder-32B"
    return model

def _is_loaded_scored_model(canon_model: str) -> bool:
    return canon_model in LOADED_CANON_MODELS

def _model_slug(canon_model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", canon_model)

def _host_lock_path(endpoint: str) -> str:
    m = re.search(r"10\.0\.\d+\.(\d+)", endpoint)
    host_id = m.group(1) if m else "local"
    return f"/var/tmp/bd-gpu-ep-{host_id}.lock"

def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def run_completion(endpoint: str, model: str, system_prompt: str, user_prompt: str, deadline_ts: float | None=None, enable_thinking: bool=True) -> tuple[str, float, float]:
    import fcntl
    if deadline_ts is not None and time.time() > deadline_ts:
        return ("SKIPPED: exceeded 10m start window before GPU lock", 0.0, 0.0)
    t0 = time.monotonic()
    req = urllib.request.Request(f"{endpoint}/v1/chat/completions", data=json.dumps({"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "max_tokens": 1536, "temperature": 0.1, "chat_template_kwargs": {"enable_thinking": enable_thinking}}).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    lock_fd = None
    try:
        lock_fd = open(_host_lock_path(endpoint), "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if deadline_ts is not None and time.time() > deadline_ts:
            return ("SKIPPED: exceeded 10m start window waiting for GPU lock", 0.0, 0.0)
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=240) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        elapsed = max(round(time.monotonic() - t0, 2), 0.05)
        return (f"ERROR: {exc}", elapsed, 0.0)
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass
    elapsed = max(round(time.monotonic() - t0, 2), 0.05)
    msg = data["choices"][0]["message"]
    content_part = (msg.get("content") or "").strip()
    reason_part = (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
    if content_part and reason_part:
        text = f"{content_part}\n\n<think>\n{reason_part}\n</think>"
    else:
        text = content_part or reason_part
    usage = data.get("usage") or {}
    comp_toks = usage.get("completion_tokens") or max(len(text) // 4, 1)
    tps = round(comp_toks / elapsed, 1)
    return (text, elapsed, tps)


def _norm_path(pstr: str) -> str:
    s = pstr.strip().rstrip(".,;:")
    if s.startswith("/mnt/bd/"):
        s = "/home/mboyle/" + s[len("/mnt/bd/") :]
    return s


def _extract_base_from_text(txt: str) -> str:
    import re
    m = re.search(r"\bBASE\s*[:=]+\s*([0-9a-f]{40})\b", txt)
    if m:
        return m.group(1)
    m2 = re.search(r"\bmain\s+([0-9a-f]{40})\b", txt)
    if m2:
        return m2.group(1)
    return ""


def _resolve_git_index(wt: Path) -> Path | None:
    dot_git = wt / ".git"
    try:
        if dot_git.is_dir():
            idx = dot_git / "index"
            return idx if idx.is_file() else None
        if dot_git.is_file():
            raw = dot_git.read_text(encoding="utf-8", errors="replace").strip()
            if raw.startswith("gitdir:"):
                gdir = raw.split("gitdir:", 1)[1].strip()
                if gdir.startswith("/mnt/bd/"):
                    alt = "/home/mboyle/" + gdir[len("/mnt/bd/") :]
                    if Path(alt).is_dir():
                        gdir = alt
                gp = Path(gdir)
                if not gp.is_absolute():
                    gp = (wt / gp).resolve()
                idx = gp / "index"
                return (
                    idx
                    if idx.is_file()
                    else gp / "HEAD"
                    if (gp / "HEAD").is_file()
                    else None
                )
    except Exception:
        pass
    return None


def _git_cmd_for_wt(wt: Path) -> list[str]:
    dot_git = wt / ".git"
    try:
        if dot_git.is_file():
            raw = dot_git.read_text(encoding="utf-8", errors="replace").strip()
            if raw.startswith("gitdir:"):
                gdir = raw.split("gitdir:", 1)[1].strip()
                if gdir.startswith("/mnt/bd/"):
                    alt = "/home/mboyle/" + gdir[len("/mnt/bd/") :]
                    if Path(alt).is_dir():
                        gdir = alt
                return ["git", f"--git-dir={gdir}", f"--work-tree={wt}"]
    except Exception:
        pass
    return ["git", "-C", str(wt)]


def _extract_cut_diff_and_pins(
    wt: Path, base_hint: str = "", cut_dir: Path | None = None
) -> dict[str, str]:
    import hashlib

    info: dict[str, str] = {
        "worktree": str(wt),
        "base": "",
        "head": "",
        "tree": "",
        "patch_sha256": "",
        "done_sha256": "",
        "files": "",
        "diff": "",
    }
    if not wt.is_dir() or not (wt / ".git").exists():
        return info
    try:
        gcmd = _git_cmd_for_wt(wt)
        head = subprocess.check_output(
            gcmd + ["rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
        if not head:
            return info
        info["head"] = head
        tree = subprocess.check_output(
            gcmd + ["write-tree"], stderr=subprocess.DEVNULL, text=True, timeout=5
        ).strip()
        info["tree"] = tree
        base = base_hint
        for cand_done in ([cut_dir / "DONE.md"] if cut_dir else []) + [
            wt / "DONE.md",
            wt / "ORDER.md",
        ]:
            if cand_done.is_file():
                raw_done = cand_done.read_bytes()
                if not info["done_sha256"] and cand_done.name == "DONE.md":
                    info["done_sha256"] = hashlib.sha256(raw_done).hexdigest()
                if not base:
                    base = _extract_base_from_text(
                        raw_done.decode("utf-8", errors="replace")
                    )
        if not base:
            base = head
        info["base"] = base
        diff_mode = "cached"
        full_diff = subprocess.check_output(
            gcmd + ["diff", "--cached", "--full-index", base],
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        if not full_diff.strip():
            diff_mode = "wt"
            full_diff = subprocess.check_output(
                gcmd + ["diff", "--full-index", base],
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        if not full_diff.strip() and base != head:
            diff_mode = "base_head"
            full_diff = subprocess.check_output(
                gcmd + ["diff", "--full-index", base, "HEAD"],
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        if not full_diff.strip():
            diff_mode = "head1"
            full_diff = subprocess.check_output(
                gcmd + ["diff", "--full-index", "HEAD~1", "HEAD"],
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        if len(full_diff.strip()) < 20:
            return info
        info["patch_sha256"] = hashlib.sha256(full_diff).hexdigest()
        if diff_mode == "cached":
            files_out = subprocess.check_output(
                gcmd + ["diff", "--cached", "--name-only", base],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            ).strip()
        elif diff_mode == "wt":
            files_out = subprocess.check_output(
                gcmd + ["diff", "--name-only", base],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            ).strip()
        elif diff_mode == "base_head":
            files_out = subprocess.check_output(
                gcmd + ["diff", "--name-only", base, "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            ).strip()
        else:
            files_out = subprocess.check_output(
                gcmd + ["diff", "--name-only", "HEAD~1", "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            ).strip()
        files_list = [f for f in files_out.splitlines() if f.strip()]
        info["files"] = " ".join(files_list[:25]) + (
            f" (+{len(files_list) - 25} more)" if len(files_list) > 25 else ""
        )
        raw_str = full_diff.decode("utf-8", errors="replace")
        chunks = re.split(r"(?=^diff --git )", raw_str, flags=re.M)
        prod_chunks = [
            c
            for c in chunks
            if c.strip() and not re.search(r"^diff --git a/\S*(?:test_|tests/)", c)
        ]
        test_chunks = [
            c
            for c in chunks
            if c.strip() and re.search(r"^diff --git a/\S*(?:test_|tests/)", c)
        ]
        code_diff = "".join(prod_chunks + test_chunks)
        info["diff"] = code_diff[:10000]
    except Exception:
        pass
    return info


def _is_worktree_path(p: Path) -> bool:
    s = _norm_path(str(p))
    if any(
        s.startswith(prefix)
        for prefix in (
            "/home/mboyle/bd-local-wt/",
            "/home/mboyle/bd-cuts/",
            "/home/mboyle/bd-review-wt/",
        )
    ):
        return True
    return (p / ".git").exists()


def _verify_done_cut(cut_dir: Path) -> dict[str, str] | None:
    """
    O3401 strict object pin check:
    LOCAL-LENS (scored) runs ONLY on cuts with DONE.md.
    Read TREE + PATCH-SHA256 + BASE + WORKTREE from DONE.md; re-measure in the builder
    WORKTREE named in DONE (write-tree + sha256 of git diff --cached --full-index <BASE>).
    Mismatch -> return None (skip, write nothing).
    """
    import hashlib

    if not cut_dir.is_dir() or _is_worktree_path(cut_dir):
        return None
    done_p = cut_dir / "DONE.md"
    if not done_p.is_file():
        return None
    try:
        raw_done = done_p.read_bytes()
        txt = raw_done.decode("utf-8", errors="replace")
        m_tree = re.search(r"\bTREE\s*[:=]+\s*([0-9a-f]{40})\b", txt)
        m_psha = re.search(r"\bPATCH-SHA256\s*[:=]+\s*([0-9a-f]{64})\b", txt)
        m_base = re.search(r"\bBASE\s*[:=]+\s*([0-9a-f]{40})\b", txt)
        m_wt = re.search(
            r"\b(?:WORKTREE|WT)\s*[:=]+\s*(/(?:home/mboyle|mnt/bd)/[^\s()]+)", txt
        )
        if not (m_tree and m_psha and m_base and m_wt):
            return None
        done_tree = m_tree.group(1)
        done_psha = m_psha.group(1)
        done_base = m_base.group(1)
        wt = Path(_norm_path(m_wt.group(1)))
        if not wt.is_dir() or not (wt / ".git").exists():
            return None
        gcmd = _git_cmd_for_wt(wt)
        actual_tree = subprocess.check_output(
            gcmd + ["write-tree"], stderr=subprocess.DEVNULL, text=True, timeout=5
        ).strip()
        if actual_tree != done_tree:
            return None
        full_diff = subprocess.check_output(
            gcmd + ["diff", "--cached", "--full-index", done_base],
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        if not full_diff.strip():
            return None
        actual_psha = hashlib.sha256(full_diff).hexdigest()
        if actual_psha != done_psha:
            return None
        files_out = subprocess.check_output(
            gcmd + ["diff", "--cached", "--name-only", done_base],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
        files_list = [f for f in files_out.splitlines() if f.strip()]
        files_str = " ".join(files_list[:25]) + (
            f" (+{len(files_list) - 25} more)" if len(files_list) > 25 else ""
        )
        return {
            "CUT": str(cut_dir),
            "worktree": str(wt),
            "base": done_base,
            "head": done_base,
            "tree": done_tree,
            "patch_sha256": done_psha,
            "done_sha256": hashlib.sha256(raw_done).hexdigest(),
            "files": files_str,
            "diff": full_diff.decode("utf-8", errors="replace")[:5000],
            "done_verified": "1",
        }
    except Exception:
        return None


def _clean_code_diff(wt: Path, base_hint: str = "", cut_dir: Path | None = None) -> str:
    return _extract_cut_diff_and_pins(wt, base_hint, cut_dir).get("diff", "")


_EMPTY_WT_CACHE: dict[str, int] = {}


def _has_model_lens_score(cut_label: str, canon_model: str) -> bool:
    score_p = Path("/home/mboyle/bd-persist/state/LOCAL-LENS-SCORE.tsv")
    if not score_p.is_file():
        return False
    try:
        for line in score_p.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) >= 3 and parts[0].split()[0] == cut_label and (parts[1] == canon_model) and (not parts[2].startswith("INVALID")):
                return True
    except Exception:
        pass
    return False

def discover_done_cut_for_local_lens(done_set: set[str], shard_idx: int, shard_mod: int, seat: str, canon_model: str, allow_steal: bool=False) -> tuple[str, dict[str, str]] | None:
    if not _is_loaded_scored_model(canon_model):
        return None
    patterns = ["/home/mboyle/bd-persist/harness-work/O1789/dispatch-*/*/DONE.md", "/home/mboyle/bd-persist/harness-work/O1789/dispatch-*/*/*/DONE.md", "/home/mboyle/bd-persist/harness-work/O1789/dispatch-*/*/*/*/DONE.md", "/home/mboyle/bd-persist/harness-work/O1789/landing/*/DONE.md", "/home/mboyle/bd-persist/harness-work/O1789/harness-rows/*/DONE.md", "/home/mboyle/bd-persist/harness-work/O1789/harness-rows/*/*/DONE.md", "/home/mboyle/bd-persist/harness-work/O1789/unpark/*/*/DONE.md", "/home/mboyle/bd-persist/harness-work/BURN/cuts/*/DONE.md", "/home/mboyle/bd-persist/harness-work/BURN/cuts/*/*/DONE.md", "/home/mboyle/bd-persist/harness-work/FIX/*/DONE.md", "/home/mboyle/bd-persist/harness-work/FRONTIER/*/DONE.md", "/home/mboyle/bd-persist/harness-cuts/*/DONE.md"]
    cand_files: list[tuple[float, str]] = []
    now_s = time.time()
    for pat in patterns:
        for f in glob.glob(pat):
            try:
                mt = Path(f).stat().st_mtime
                if mt >= SHADOW_BOOT_TS - 4500:
                    cand_files.append((mt, f))
            except Exception:
                pass
    cand_files.sort(reverse=True)
    mslug = _model_slug(canon_model)
    for idx, (mt, dpath) in enumerate(cand_files):
        if not allow_steal and canon_model == "cyberstrike-35b:q4_k_m" and (idx % shard_mod != shard_idx):
            continue
        dp = Path(dpath)
        cut_dir = dp.parent
        if _is_worktree_path(cut_dir) or _dir_has_prefix(cut_dir, ("CLOSED", "SUPERSEDED", "PARK")):
            continue
        cut_label = f"{cut_dir.parent.name}-{cut_dir.name}" if re.match(r"^r\d+$", cut_dir.name) else cut_dir.name
        info = _verify_done_cut(cut_dir)
        if not info:
            continue
        item_key = f"LOCAL-LENS:{cut_label}:{mslug}:{info['tree'][:12]}"
        if item_key in done_set:
            continue
        if _has_model_lens_score(cut_label, canon_model):
            done_set.add(item_key)
            continue
        rev_dir = cut_dir / ".review"
        rev_dir.mkdir(parents=True, exist_ok=True)
        already_done = False
        for lf in rev_dir.glob("LOCAL-LENS-*.md"):
            try:
                ltxt = lf.read_text(encoding="utf-8", errors="replace")
                if f"TREE: {info['tree']}" in ltxt and canon_model in ltxt:
                    already_done = True
                    break
            except Exception:
                pass
        if already_done:
            done_set.add(item_key)
            continue
        deadline_ts = max(mt, SHADOW_BOOT_TS) + 600.0
        if now_s > deadline_ts:
            print(f"[{now_iso()}] [{seat}] SKIPPED LOCAL-LENS `{cut_label}` ({canon_model}): exceeded 10m start window (age={int(now_s - mt)}s)", flush=True)
            done_set.add(item_key)
            continue
        claim_p = rev_dir / f".claim-lens-{mslug}-{info['tree'][:12]}"
        if claim_p.exists():
            try:
                if now_s - claim_p.stat().st_mtime < 300:
                    continue
            except Exception:
                continue
        try:
            claim_p.write_text(f"{seat} {now_iso()}\n", encoding="utf-8")
        except Exception:
            continue
        info["cut_label"] = cut_label
        info["item_key"] = item_key
        info["deadline_ts"] = str(deadline_ts)
        info["claim_path"] = str(claim_p)
        return (cut_label, info)
    return None

def _has_model_build_score(row_label: str, canon_model: str) -> bool:
    score_p = Path("/home/mboyle/bd-persist/state/LOCAL-BUILD-SCORE.tsv")
    if not score_p.is_file():
        return False
    try:
        for line in score_p.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) >= 3 and parts[0] == row_label and (parts[1] == canon_model) and (parts[2] != "NO_DIFF"):
                return True
    except Exception:
        pass
    return False

def discover_order_for_shadow_build(done_set: set[str], shard_idx: int, shard_mod: int, seat: str, canon_model: str, allow_steal: bool=False) -> tuple[str, dict[str, str]] | None:
    if not _is_loaded_scored_model(canon_model):
        return None
    patterns = ["/home/mboyle/bd-persist/harness-work/O1789/dispatch-*/*/*.md", "/home/mboyle/bd-persist/harness-work/O1789/dispatch-*/*/*/*.md", "/home/mboyle/bd-persist/harness-work/O1789/dispatch-*/*/*/*/*.md", "/home/mboyle/bd-persist/harness-work/O1789/landing/*/*.md", "/home/mboyle/bd-persist/harness-work/O1789/harness-rows/*/*.md", "/home/mboyle/bd-persist/harness-work/O1789/harness-rows/*/*/*.md", "/home/mboyle/bd-persist/harness-work/BURN/cuts/*/*.md", "/home/mboyle/bd-persist/harness-work/BURN/cuts/*/*/*.md", "/home/mboyle/bd-persist/harness-work/FIX/*/*.md", "/home/mboyle/bd-persist/harness-cuts/*/*.md"]
    cand_files: list[tuple[float, str]] = []
    now_s = time.time()
    for pat in patterns:
        for f in glob.glob(pat):
            bn = Path(f).name
            if not (bn.startswith("ORDER") or bn.startswith("BRIEF")):
                continue
            try:
                mt = Path(f).stat().st_mtime
                if mt >= SHADOW_BOOT_TS - 7200:
                    cand_files.append((mt, f))
            except Exception:
                pass
    cand_files.sort(reverse=True)
    mslug = _model_slug(canon_model)
    for idx, (mt, opath) in enumerate(cand_files):
        if not allow_steal and canon_model == "cyberstrike-35b:q4_k_m" and (idx % shard_mod != shard_idx):
            continue
        op = Path(opath)
        cut_dir = op.parent
        if _is_worktree_path(cut_dir) or (cut_dir / "DONE.md").is_file() or _dir_has_prefix(cut_dir, ("DONE", "LANDED", "CLOSED", "SUPERSEDED", "PARK", "RESULT", "BOARD")):
            continue
        row_label = f"{cut_dir.parent.name}-{cut_dir.name}" if re.match(r"^r\d+$", cut_dir.name) else cut_dir.name
        item_key = f"SHADOW-BUILD:{row_label}:{mslug}"
        if item_key in done_set:
            continue
        if _has_model_build_score(row_label, canon_model):
            done_set.add(item_key)
            continue
        already_built = False
        for sb in cut_dir.glob("SHADOW-BUILD-*.md"):
            try:
                stxt = sb.read_text(encoding="utf-8", errors="replace")
                if canon_model in stxt and "SHADOW-BUILD: NO_DIFF" not in stxt:
                    already_built = True
                    break
            except Exception:
                pass
        if already_built:
            done_set.add(item_key)
            continue
        try:
            txt = op.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for aux_dir in (cut_dir, cut_dir.parent):
            for pat_aux in ("STEP0*.md", "RULING*.md", "QUESTION*.md", "ANSWER*.md"):
                for aux_f in sorted(aux_dir.glob(pat_aux)):
                    if aux_f.is_file():
                        try:
                            mt = max(mt, aux_f.stat().st_mtime)
                            txt += f"\n\n--- {aux_f.name} ---\n" + aux_f.read_text(encoding="utf-8", errors="replace")[:3000]
                        except Exception:
                            pass
        m_rnd = re.match(r"^r(\d+)$", cut_dir.name)
        if m_rnd and int(m_rnd.group(1)) > 1:
            prev_done = cut_dir.parent / f"r{int(m_rnd.group(1)) - 1}" / "DONE.md"
            if prev_done.is_file():
                try:
                    txt += f"\n\n--- PREV ROUND DONE.md ({prev_done}) ---\n" + prev_done.read_text(encoding="utf-8", errors="replace")[:3000]
                except Exception:
                    pass
        m_repo = re.search(r"\bREPO\s*[:=]+\s*(/(?:home/mboyle|mnt/bd)/[^\s()]+)", txt)
        repo_path = _norm_path(m_repo.group(1)) if m_repo else "/home/mboyle/BulkDownloader"
        base_sha = _extract_base_from_text(txt)
        if not base_sha:
            for extra_p in re.findall(r"(/(?:home/mboyle|mnt/bd)/[^\s|'\")>\]]+\.md)", txt)[:5]:
                ep = Path(_norm_path(extra_p))
                if ep.is_file():
                    try:
                        base_sha = _extract_base_from_text(ep.read_text(encoding="utf-8", errors="replace"))
                        if base_sha:
                            txt = txt + "\n\n" + ep.read_text(encoding="utf-8", errors="replace")[:4000]
                            break
                    except Exception:
                        pass
        if not base_sha:
            m_short = re.search(r"\bBASE\s*[:=]?\s*([0-9a-f]{8,40})\b", txt)
            if m_short:
                try:
                    base_sha = subprocess.check_output(["git", "-C", repo_path, "rev-parse", m_short.group(1)], stderr=subprocess.DEVNULL, text=True, timeout=5).strip()
                except Exception:
                    base_sha = ""
        if not base_sha:
            continue
        m_owns = re.search(r"\bOWNS(?:\s*\([^)]*\))?\s*[:=]+\s*([^\n]+)", txt)
        owns_raw = m_owns.group(1) if m_owns else ""
        owns_files: list[str] = []
        for tok in re.split(r"[;,\s+]+", owns_raw):
            t_clean = tok.strip().strip("`'\"()")
            if t_clean and ("/" in t_clean or t_clean.endswith((".py", ".sh", ".ts", ".js", ".md"))) and ("*" not in t_clean) and ("{" not in t_clean) and (not t_clean.startswith("(")):
                owns_files.append(t_clean)
        if "_common.py" in txt and "bulk_downloader/login_impl/_common.py" not in owns_files:
            if (Path(repo_path) / "bulk_downloader/login_impl/_common.py").is_file():
                owns_files.insert(0, "bulk_downloader/login_impl/_common.py")
        if "submit.py" in txt and "bulk_downloader/login_impl/submit.py" not in owns_files:
            if (Path(repo_path) / "bulk_downloader/login_impl/submit.py").is_file():
                owns_files.append("bulk_downloader/login_impl/submit.py")
        for m_pf in re.findall(r"\b((?:bulk_downloader|tests|tools|scripts)/[A-Za-z0-9_./-]+\.(?:py|sh))\b", txt):
            if m_pf not in owns_files:
                owns_files.append(m_pf)
        if not owns_files:
            continue
        deadline_ts = max(mt, SHADOW_BOOT_TS) + 600.0
        if now_s > deadline_ts:
            print(f"[{now_iso()}] [{seat}] SKIPPED SHADOW-BUILD `{row_label}` ({canon_model}): exceeded 10m start window (age={int(now_s - mt)}s)", flush=True)
            done_set.add(item_key)
            continue
        claim_p = cut_dir / f".claim-build-{mslug}"
        if claim_p.exists():
            try:
                if now_s - claim_p.stat().st_mtime < 300:
                    continue
            except Exception:
                continue
        try:
            claim_p.write_text(f"{seat} {now_iso()}\n", encoding="utf-8")
        except Exception:
            continue
        return (row_label, {"row": row_label, "cut_dir": str(cut_dir), "order_path": str(op), "order_text": txt[:6500], "repo": repo_path, "base": base_sha, "owns": ";".join(owns_files[:6]), "item_key": item_key, "deadline_ts": str(deadline_ts), "claim_path": str(claim_p)})
    return None


def discover_cut_for_pregate(
    done_set: set[str], shard_idx: int, shard_mod: int, allow_steal: bool = False
) -> tuple[str, dict[str, str]] | None:
    roots = sorted(
        glob.glob("/home/mboyle/bd-local-wt/*") + glob.glob("/home/mboyle/bd-cuts/*")
    )
    now_s = time.time()
    for idx, rpath in enumerate(roots):
        if not allow_steal and idx % shard_mod != shard_idx:
            continue
        p = Path(rpath)
        if not p.is_dir() or p.name in done_set:
            continue
        git_idx = _resolve_git_index(p)
        if git_idx is None:
            done_set.add(p.name)
            continue
        try:
            st = git_idx.stat()
        except Exception:
            continue
        if now_s - st.st_mtime > 21600:
            done_set.add(p.name)
            continue
        if _EMPTY_WT_CACHE.get(p.name) == st.st_mtime_ns:
            continue
        info = _extract_cut_diff_and_pins(p)
        if (
            len(info.get("diff", "").strip()) >= 20
            and info.get("patch_sha256")
            and info.get("head")
        ):
            return (p.name, info)
        _EMPTY_WT_CACHE[p.name] = st.st_mtime_ns
    return None


TERMINAL_FILE_PREFIXES = (
    "RESULT",
    "CLOSED",
    "LANDED",
    "DONE",
    "SUPERSEDED",
    "PARK",
    "RULING",
    "REASSIGNED",
    "BLOCKED",
)
CUT_MARKER_PREFIXES = ("CLOSED", "LANDED", "SUPERSEDED", "PARK", "RESULT")


def _claims_dir_for_queue(q_stem: str) -> Path:
    q_dir = Path("/home/mboyle/bd-persist/queues")
    if q_stem.endswith("-QUEUE"):
        c1 = q_dir / f"{q_stem[:-6]}-CLAIMS"
        if c1.is_dir():
            return c1
    return q_dir / f"{q_stem}-CLAIMS"


def _dir_has_prefix(d: Path, prefixes: tuple[str, ...]) -> bool:
    if not d.is_dir():
        return False
    try:
        for p in d.iterdir():
            if p.name.upper().startswith(prefixes):
                return True
            if p.is_dir():
                for sub in p.iterdir():
                    if sub.name.upper().startswith(prefixes):
                        return True
    except Exception:
        pass
    return False


def _is_row_terminal(q_stem: str, rid: str, row: dict) -> bool:
    rid_s = rid.strip()
    if not rid_s or rid_s.startswith("#"):
        return True
    raw_u = json.dumps(row).upper()
    if any(
        (
            tok in raw_u
            for tok in (
                "STATE=DONE",
                "STATE=CLOSED",
                "STATE=LANDED",
                "STATE=SUPERSEDED",
                "STATE=PARKED",
                "LANDED-ON-MAIN",
                "ALREADY_LANDED",
                "CLOSED-",
                "LANDED-",
                "SUPERSEDED",
            )
        )
    ):
        return True
    cdir = _claims_dir_for_queue(q_stem) / rid_s
    if _dir_has_prefix(cdir, TERMINAL_FILE_PREFIXES):
        return True
    hw_dir = Path("/home/mboyle/bd-persist/harness-work")
    cut_dirs = [
        hw_dir / "BURN/cuts" / rid_s,
        hw_dir / "O1789/landing" / rid_s,
        Path("/home/mboyle/bd-persist/harness-cuts") / rid_s,
        hw_dir / "O1789/harness-rows" / rid_s,
    ]
    for v in row.values():
        if isinstance(v, str) and v.startswith("/home/mboyle/"):
            vp = Path(v)
            if vp.is_dir():
                cut_dirs.append(vp)
            elif vp.parent.is_dir() and vp.parent.name == rid_s:
                cut_dirs.append(vp.parent)
    if any((_dir_has_prefix(cd, CUT_MARKER_PREFIXES) for cd in cut_dirs)):
        return True
    return False


def discover_row_for_triage(
    done_set: set[str], shard_idx: int, shard_mod: int, allow_steal: bool = False
) -> tuple[str, dict] | None:
    cache_file = Path("/var/tmp/bd-local-triage-rows-cache.json")
    all_rows = None
    if cache_file.is_file():
        try:
            if time.time() - cache_file.stat().st_mtime < 180:
                all_rows = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            all_rows = None
    if all_rows is None:
        queues = [
            "/home/mboyle/bd-persist/queues/P2-FIX-QUEUE.tsv",
            "/home/mboyle/bd-persist/queues/BH2-BUILD-QUEUE.tsv",
            "/home/mboyle/bd-persist/queues/BH1-BACKLOG-QUEUE.tsv",
            "/home/mboyle/bd-persist/queues/O1670-QUEUE.tsv",
            "/home/mboyle/bd-persist/queues/O1671-PRODUCT-CANDIDATES.tsv",
            "/home/mboyle/bd-persist/queues/APP-DL-FIX-QUEUE.tsv",
        ]
        all_rows = []
        for q in queues:
            qp = Path(q)
            if not qp.exists():
                continue
            try:
                with qp.open("r", encoding="utf-8", errors="replace") as f:
                    for row in csv.DictReader(f, delimiter="\t"):
                        rid = (
                            row.get("id") or row.get("row_id") or row.get("cut") or ""
                        ).strip()
                        if not _is_row_terminal(qp.stem, rid, row):
                            all_rows.append([f"{qp.stem}:{rid}", row])
            except Exception:
                continue
        try:
            cache_file.write_text(json.dumps(all_rows), encoding="utf-8")
        except Exception:
            pass
    for idx, (key, row) in enumerate(all_rows):
        if not allow_steal and idx % shard_mod != shard_idx:
            continue
        if key not in done_set:
            return (key, row)
    return None


SEAT_TO_BACKEND = {
    "bd-local-83-1": "t4-heretic",
    "bd-local-t4-swarm-2": "t4-72",
    "bd-local-125-1": "t4-125",
    "bd-local-228-1": "t4-228",
    "bd-local-137-1": "2080ti",
    "bd-local-137-2": "2080ti",
}


def _parse_verdict_token(reply: str) -> str:
    import re

    s = reply.strip()
    if not s or s.startswith("ERROR:"):
        return "UNKNOWN"
    clean = re.sub(r"<think>.*?(?:</think>|$)", "", s, flags=re.S).strip()
    if not clean:
        clean = s
    u = clean.upper()
    first_line = u.splitlines()[0] if u.splitlines() else u
    if "BOARD-WITH-ADVISORY" in first_line:
        return "BOARD-WITH-ADVISORY"
    if re.search(r"\bREFUTE\b", first_line):
        return "REFUTE"
    if re.search(r"\b(BOARD|LAND)\b", first_line) or "FOUND NONE" in first_line:
        return "BOARD"
    if "BOARD-WITH-ADVISORY" in u:
        return "BOARD-WITH-ADVISORY"
    if re.search(r"\bVERDICT\s*[:=]\s*REFUTE\b", u):
        return "REFUTE"
    if re.search(r"\bVERDICT\s*[:=]\s*(BOARD|LAND)\b", u):
        return "BOARD"
    if (
        re.search(r"\bREFUTE\b", u)
        and "NO GROUNDS TO REFUTE" not in u
        and "NOT REFUTE" not in u
    ):
        return "REFUTE"
    if "BOUNCE" in u:
        return "BOUNCE"
    return "BOARD"


def _format_stamped_verdict(
    seat: str,
    endpoint: str,
    model: str,
    elapsed: float,
    tps: float,
    meta: dict[str, str],
    reply: str,
    title: str,
    header_tag: str = "VERDICT",
    mode_label: str = "",
) -> str:
    v_tok = _parse_verdict_token(reply)
    hdr = [
        f"{header_tag}: {v_tok}",
        f"SEAT: {seat} ({endpoint}, {model})",
        f"WRITTEN-AT: {now_iso()}",
    ]
    if mode_label:
        hdr.append(f"MODE: {mode_label}")
    if meta.get("CUT"):
        hdr.append(f"CUT: {meta['CUT']}")
    if meta.get("worktree"):
        hdr.append(f"WORKTREE: {meta['worktree']}")
    if meta.get("base"):
        hdr.append(f"BASE: {meta['base']}")
    if meta.get("tree"):
        hdr.append(f"TREE: {meta['tree']}")
    if meta.get("patch_sha256"):
        hdr.append(f"PATCH-SHA256: {meta['patch_sha256']}")
    if meta.get("done_sha256"):
        hdr.append(f"DONE-SHA256: {meta['done_sha256']}")
    if meta.get("files"):
        hdr.append(f"FILES: {meta['files']}")
    hdr.append("WORKFLOWS: none")
    hdr.append(f"LATENCY: {elapsed}s ({tps} tok/s)")
    hdr.append("")
    hdr.append(f"## {title}")
    hdr.append(reply.strip())
    hdr.append("")
    return "\n".join(hdr)


def _record_local_lens_score(cut_name: str, canon_model: str, v_tok: str) -> None:
    if not _is_loaded_scored_model(canon_model):
        return
    score_p = Path("/home/mboyle/bd-persist/state/LOCAL-LENS-SCORE.tsv")
    try:
        if not score_p.exists():
            score_p.write_text(
                "cut\tmodel\tlocal_verdict\tofficial_verdict\tfindings_matched\tfindings_missed\tfalse_refutes\tunique_true_finds\n",
                encoding="utf-8",
            )
        existing = score_p.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in existing[1:]:
            parts = line.split("\t")
            if (
                len(parts) >= 3
                and parts[0] == cut_name
                and parts[1] == canon_model
                and not parts[2].startswith("INVALID")
            ):
                return
        with score_p.open("a", encoding="utf-8") as sf:
            sf.write(f"{cut_name}\t{canon_model}\t{v_tok}\tPENDING\t0\t0\t0\t0\n")
    except Exception:
        pass


def _record_local_build_score(
    row_name: str,
    canon_model: str,
    tests_pass: str,
    claude_tree_landed: str,
    overlap_pct: str,
    lens_findings: str,
) -> None:
    if not _is_loaded_scored_model(canon_model):
        return
    score_p = Path("/home/mboyle/bd-persist/state/LOCAL-BUILD-SCORE.tsv")
    try:
        header = "row\tmodel\ttests_pass\tclaude_tree_landed\tshadow_diff_overlap%\tlens_findings_on_shadow\n"
        if not score_p.exists():
            score_p.write_text(header, encoding="utf-8")
        lines = score_p.read_text(encoding="utf-8", errors="replace").splitlines()
        out_lines = [lines[0] if lines else header.strip()]
        updated = False
        new_row = f"{row_name}\t{canon_model}\t{tests_pass}\t{claude_tree_landed}\t{overlap_pct}\t{lens_findings}"
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0] == row_name and parts[1] == canon_model:
                out_lines.append(new_row)
                updated = True
            else:
                out_lines.append(line)
        if not updated:
            out_lines.append(new_row)
        score_p.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def _diff_changed_lines_set(diff_str: str) -> set[str]:
    s: set[str] = set()
    cur_file = ""
    for line in diff_str.splitlines():
        if line.startswith("+++ b/"):
            cur_file = line[6:].strip()
        elif line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            norm = line[1:].strip()
            if norm:
                s.add(f"{cur_file}:{line[0]}:{norm}")
    return s


def _claude_status_and_overlap(cut_dir: Path, shadow_diff: str) -> tuple[str, str]:
    cand_dirs = [cut_dir] + sorted(
        [d for d in cut_dir.iterdir() if d.is_dir() and re.match(r"^r\d+$", d.name)],
        reverse=True,
    )
    landed = _dir_has_prefix(cut_dir, ("LANDED", "CLOSED", "RESULT"))
    for cd in cand_dirs:
        if _dir_has_prefix(cd, ("LANDED", "CLOSED", "RESULT")):
            landed = True
        verified = _verify_done_cut(cd)
        if verified and verified.get("diff"):
            c_set = _diff_changed_lines_set(verified["diff"])
            s_set = _diff_changed_lines_set(shadow_diff)
            if not s_set:
                ov = "0.0%"
            else:
                inter = len(c_set & s_set)
                union = max(len(c_set | s_set), 1)
                ov = f"{round(100.0 * inter / union, 1)}%"
            return ("YES" if landed else f"STAGED({verified['tree'][:8]})", ov)
        for pf in list(cd.glob("*.patch")) + list(cd.glob("*.diff")):
            try:
                ptxt = pf.read_text(encoding="utf-8", errors="replace")
                if "diff --git " in ptxt or "@@ " in ptxt:
                    c_set = _diff_changed_lines_set(ptxt)
                    s_set = _diff_changed_lines_set(shadow_diff)
                    if not s_set:
                        ov = "0.0%"
                    else:
                        inter = len(c_set & s_set)
                        union = max(len(c_set | s_set), 1)
                        ov = f"{round(100.0 * inter / union, 1)}%"
                    return ("YES" if landed else f"PATCH({pf.name})", ov)
            except Exception:
                pass
    return ("YES" if landed else "PENDING", "PENDING")


def _extract_symbol_slices(fp: Path, order_text: str) -> str:
    try:
        lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return ""
    if len(lines) <= 240:
        return "\n".join(lines)
    syms = set(
        re.findall(
            r"\b([A-Za-z_][A-Za-z0-9_]{3,})\b",
            order_text,
        )
    ) - {
        "ORDER",
        "BRIEF",
        "KIND",
        "REPO",
        "BASE",
        "OWNS",
        "WIRING",
        "SYMBOLS",
        "SOURCE",
        "TASK",
        "STEP",
        "LANDED",
        "PASS",
        "NONE",
        "True",
        "False",
        "home",
        "mboyle",
        "BulkDownloader",
        "bulk_downloader",
        "tests",
    }
    hit_ranges: list[tuple[int, int]] = [(0, min(80, len(lines)))]
    for idx, ln in enumerate(lines):
        if any(
            f"def {sym}" in ln or f"class {sym}" in ln or f"{sym}(" in ln
            for sym in syms
        ):
            hit_ranges.append((max(0, idx - 15), min(len(lines), idx + 45)))
            if len(hit_ranges) >= 5:
                break
    merged: list[tuple[int, int]] = []
    for s_i, e_i in sorted(hit_ranges):
        if merged and s_i <= merged[-1][1] + 5:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e_i))
        else:
            merged.append((s_i, e_i))
    chunks: list[str] = []
    for s_i, e_i in merged[:4]:
        chunks.append(f"# --- lines {s_i + 1}..{e_i} ---\n" + "\n".join(lines[s_i:e_i]))
    return "\n\n".join(chunks)[:4500]


def _apply_search_replace_fuzzy(orig: str, s_blk: str, r_blk: str) -> str | None:
    if s_blk in orig:
        return orig.replace(s_blk, r_blk, 1)
    orig_lines = orig.splitlines()
    s_lines = [ln.strip() for ln in s_blk.strip().splitlines() if ln.strip()]
    if not s_lines:
        return None
    n = len(s_lines)
    for i in range(len(orig_lines) - n + 1):
        window = [orig_lines[i + j].strip() for j in range(n)]
        if window == s_lines:
            new_lines = orig_lines[:i] + r_blk.splitlines() + orig_lines[i + n :]
            return "\n".join(new_lines) + ("\n" if orig.endswith("\n") else "")
    return None


def run_shadow_build(
    seat: str,
    endpoint: str,
    model: str,
    canon_model: str,
    build_info: dict[str, str],
) -> dict[str, str]:
    import hashlib

    row = build_info["row"]
    cut_dir = Path(build_info["cut_dir"])
    repo_p = Path(build_info["repo"])
    base_sha = build_info["base"]
    owns_list = [x for x in build_info["owns"].split(";") if x.strip()]
    deadline_ts = float(build_info["deadline_ts"])
    wt_path = Path(f"/home/mboyle/bd-local-wt/{row}-shadow-{seat}")

    if time.time() > deadline_ts:
        return {"status": "SKIPPED", "reason": "exceeded 10m start window before worktree"}

    if not wt_path.exists():
        wt_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_p),
                "worktree",
                "add",
                "--lock",
                "--detach",
                str(wt_path),
                base_sha,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    if not wt_path.is_dir() or not (wt_path / ".git").exists():
        return {"status": "ERROR", "reason": f"worktree creation failed at {wt_path}"}

    gcmd = _git_cmd_for_wt(wt_path)
    # If cut_dir is r<N> (e.g. r7) and r<N-1>/DONE.md exists with a verified staged patch, apply r<N-1> baseline first
    m_rnd = re.match(r"^r(\d+)$", cut_dir.name)
    if m_rnd and int(m_rnd.group(1)) > 1:
        prev_dir = cut_dir.parent / f"r{int(m_rnd.group(1)) - 1}"
        prev_ver = _verify_done_cut(prev_dir)
        if prev_ver and prev_ver.get("worktree"):
            try:
                prev_gcmd = _git_cmd_for_wt(Path(prev_ver["worktree"]))
                cur_diff = subprocess.check_output(
                    gcmd + ["diff", "--cached", "--name-only", base_sha],
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=5,
                ).strip()
                if not cur_diff:
                    prev_patch = subprocess.check_output(
                        prev_gcmd + ["diff", "--cached", "--full-index", base_sha],
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                    )
                    if prev_patch.strip():
                        subprocess.run(
                            gcmd + ["apply", "--index"],
                            input=prev_patch,
                            capture_output=True,
                            timeout=15,
                            check=False,
                        )
            except Exception:
                pass

    file_contexts: list[str] = []
    for rel_f in owns_list[:3]:
        fp = wt_path / rel_f
        if fp.is_file():
            snippet = _extract_symbol_slices(fp, build_info["order_text"])
            if snippet:
                file_contexts.append(f"=== FILE: {rel_f} ===\n{snippet}")

    b_sys = (
        f"You are {seat}, a Boylenet Local GPU Shadow Builder ({canon_model}) on {endpoint}. "
        "Produce a minimal, surgical code change for the ORDER/BRIEF in the shadow worktree. "
        "Do NOT output <think> or markdown prose. Output ONLY a single valid JSON object with schema:\n"
        '{"summary": "<1-line summary>", "edits": [{"file": "<rel_path>", "search": "<exact existing lines from FILE>", "replace": "<replacement lines>"}]}'
    )
    b_user = (
        f"ROW: {row}\nBASE: {base_sha}\nOWNS: {', '.join(owns_list)}\n\n"
        f"--- ORDER / BRIEF ---\n{build_info['order_text'][:3600]}\n\n"
        + "\n\n".join(file_contexts)
    )
    reply, elapsed, tps = run_completion(
        endpoint,
        model,
        b_sys,
        b_user,
        deadline_ts=deadline_ts,
        enable_thinking=False,
    )
    if reply.startswith("SKIPPED:"):
        return {"status": "SKIPPED", "reason": reply}
    if reply.startswith("ERROR:"):
        return {"status": "ERROR", "reason": reply}

    clean = re.sub(r"<think>.*?(?:</think>|$)", "", reply, flags=re.S).strip()
    m_json = re.search(r"\{.*\}", clean, flags=re.S)
    applied_edits = 0
    summary_txt = "shadow build attempt"
    if m_json:
        try:
            parsed = json.loads(m_json.group(0))
            summary_txt = str(parsed.get("summary") or summary_txt)[:200]
            for ed in parsed.get("edits") or []:
                rel_f = str(ed.get("file") or "").strip().lstrip("/")
                s_blk = str(ed.get("search") or "")
                r_blk = str(ed.get("replace") or "")
                if not rel_f or not s_blk or s_blk == r_blk:
                    continue
                target_fp = (wt_path / rel_f).resolve()
                if not str(target_fp).startswith(str(wt_path.resolve())):
                    continue
                if target_fp.is_file():
                    orig = target_fp.read_text(encoding="utf-8", errors="replace")
                    updated_txt = _apply_search_replace_fuzzy(orig, s_blk, r_blk)
                    if updated_txt is not None and updated_txt != orig:
                        target_fp.write_text(updated_txt, encoding="utf-8")
                        applied_edits += 1
        except Exception:
            pass

    subprocess.run(gcmd + ["add", "-A"], capture_output=True, timeout=10, check=False)
    tree_sha = subprocess.check_output(
        gcmd + ["write-tree"], stderr=subprocess.DEVNULL, text=True, timeout=5
    ).strip()
    diff_bytes = subprocess.check_output(
        gcmd + ["diff", "--cached", "--full-index", base_sha],
        stderr=subprocess.DEVNULL,
        timeout=10,
    )
    patch_sha = hashlib.sha256(diff_bytes).hexdigest() if diff_bytes.strip() else "NONE"
    diff_str = diff_bytes.decode("utf-8", errors="replace")

    test_files: list[str] = []
    for f in owns_list:
        if "test" in f and (wt_path / f).is_file():
            test_files.append(f)
    if not test_files:
        for m_tf in re.findall(r"([A-Za-z0-9_/]*test_[A-Za-z0-9_]+\.py)", build_info["order_text"]):
            if (wt_path / m_tf).is_file() and m_tf not in test_files:
                test_files.append(m_tf)
    if not test_files and owns_list:
        stem = Path(owns_list[0]).stem.replace("bd-", "").replace("-", "_")
        cand_t = f"tests/test_{stem}.py"
        if (wt_path / cand_t).is_file():
            test_files.append(cand_t)

    if not diff_bytes.strip() or applied_edits == 0:
        tests_pass = "NO_DIFF"
        test_out = "0 edits applied from model output"
    elif test_files:
        import os

        env = os.environ.copy()
        env["PYTHONPATH"] = str(wt_path)
        py_bin = "/home/mboyle/BulkDownloader/venv/bin/python" if Path("/home/mboyle/BulkDownloader/venv/bin/python").is_file() else "python3"
        r_test = subprocess.run(
            [py_bin, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short"] + test_files[:2],
            cwd=str(wt_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        tests_pass = "PASS" if r_test.returncode == 0 else f"FAIL(rc={r_test.returncode})"
        test_out = (r_test.stdout + "\n" + r_test.stderr).strip()[-600:]
    else:
        tests_pass = "UNPROBED"
        test_out = "no target test file resolved"

    lens_findings = "0"
    if diff_bytes.strip() and applied_edits > 0:
        touched = [
            f
            for f in owns_list
            if f.endswith(".py") and (wt_path / f).is_file()
        ]
        if touched:
            r_ruff = subprocess.run(
                ["ruff", "check", "--quiet"] + touched,
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            f_cnt = len([ln for ln in r_ruff.stdout.splitlines() if ln.strip()])
            lens_findings = str(f_cnt)
    else:
        lens_findings = "NO_DIFF"

    claude_landed, overlap_pct = _claude_status_and_overlap(cut_dir, diff_str if applied_edits > 0 else "")

    # O3409: FIRST-FINISHER -> write DONE-local-<seat>.md and ping lensrouter if local finishes green before Claude DONE.md
    if tests_pass == "PASS" and applied_edits > 0 and diff_bytes.strip() and not _is_worktree_path(cut_dir):
        claude_done = cut_dir / "DONE.md"
        existing_local_dones = list(cut_dir.glob("DONE-local-*.md"))
        if not claude_done.exists() and not existing_local_dones:
            done_local_p = cut_dir / f"DONE-local-{seat}.md"
            done_local_body = (
                f"VERDICT: PATCH\n"
                f"SEAT: {seat} ({endpoint}, {canon_model}; O3409 local first-finisher)\n"
                f"WRITTEN-AT: {now_iso()}\n"
                f"REPO: {repo_p}\n"
                f"BASE: {base_sha}\n"
                f"WORKTREE: {wt_path}\n"
                f"TREE: {tree_sha}\n"
                f"PATCH-SHA256: {patch_sha}\n"
                f"OWNS: {', '.join(owns_list)}\n"
                f"GREEN: pytest {' '.join(test_files[:2])} -> PASS\n"
                f"SUMMARY: {summary_txt}\n"
            )
            done_local_p.write_text(done_local_body, encoding="utf-8")
            claude_landed = f"LOCAL_FIRST({seat})"
            lr_target = (
                "bd-lensrouter-B4-D"
                if ("harness" in str(cut_dir) or "harness" in str(repo_p))
                else "bd-lensrouter-B3-C"
            )
            for recip in (lr_target, "bd-pm-B"):
                subprocess.run(
                    [
                        "/home/mboyle/bd-persist/harness/bd-say.sh",
                        recip,
                        f"O3409 DONE-local {row} {done_local_p}",
                    ],
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
        elif claude_done.exists():
            try:
                if abs(time.time() - claude_done.stat().st_mtime) <= 60:
                    claude_landed = f"TIE({claude_landed})"
            except Exception:
                pass

    sb_path = cut_dir / f"SHADOW-BUILD-{seat}.md"
    sb_body = (
        f"SHADOW-BUILD: {tests_pass}\n"
        f"ROW: {row}\n"
        f"SEAT: {seat} ({endpoint}, {canon_model})\n"
        f"WRITTEN-AT: {now_iso()}\n"
        f"SHADOW-WORKTREE: {wt_path}\n"
        f"BASE: {base_sha}\n"
        f"TREE: {tree_sha}\n"
        f"PATCH-SHA256: {patch_sha}\n"
        f"APPLIED-EDITS: {applied_edits}\n"
        f"TESTS-PASS: {tests_pass}\n"
        f"CLAUDE-TREE-LANDED: {claude_landed}\n"
        f"SHADOW-DIFF-OVERLAP%: {overlap_pct}\n"
        f"LENS-FINDINGS-ON-SHADOW: {lens_findings}\n"
        f"LATENCY: {elapsed}s ({tps} tok/s)\n\n"
        f"## Summary\n{summary_txt}\n\n"
        f"## Test Output\n```\n{test_out}\n```\n"
    )
    if not _is_worktree_path(cut_dir):
        sb_path.write_text(sb_body, encoding="utf-8")
    _record_local_build_score(
        row, canon_model, tests_pass, claude_landed, overlap_pct, lens_findings
    )
    return {
        "status": "DONE",
        "tests_pass": tests_pass,
        "tree": tree_sha,
        "patch_sha256": patch_sha,
        "overlap_pct": overlap_pct,
        "lens_findings": lens_findings,
        "elapsed": str(elapsed),
        "tps": str(tps),
        "out": str(sb_path),
    }


def _enrich_inbox_order(
    raw_msg: str, filename: str = ""
) -> tuple[str, str, dict[str, str]]:
    import hashlib
    import re

    sender = ""
    m_sender = re.search(r"\[from\s+([^\]]+)\]", raw_msg)
    if m_sender:
        sender = m_sender.group(1).strip()
    paths = re.findall(r"(/(?:home/mboyle|mnt/bd)/[^\s|'\")>\]]+)", raw_msg)
    enriched = [raw_msg]
    meta: dict[str, str] = {}
    for pstr in paths[:6]:
        p = Path(_norm_path(pstr))
        if p.is_file():
            try:
                ftxt = p.read_text(encoding="utf-8", errors="replace")[:5000]
                enriched.append(f"\n--- REFERENCED FILE: {p} ---\n{ftxt}")
                for extra_p in re.findall(
                    r"(/(?:home/mboyle|mnt/bd)/[^\s|'\")>\]]+)", ftxt
                )[:6]:
                    ep = Path(_norm_path(extra_p))
                    if ep.is_file() and ep.name in ("DONE.md", "BRIEF.md", "ORDER.md"):
                        try:
                            eftxt = ep.read_text(encoding="utf-8", errors="replace")[
                                :4000
                            ]
                            enriched.append(f"\n--- REFERENCED FILE: {ep} ---\n{eftxt}")
                        except Exception:
                            pass
            except Exception:
                pass
    full_txt = "\n".join(enriched)
    if not sender:
        m_req = re.search(r"REQUESTED-BY\s*:\s*(bd-[A-Za-z0-9_-]+)", full_txt)
        if m_req:
            sender = m_req.group(1).strip()
    if not sender:
        m_from = re.search(
            r"\bfrom\s+(bd-(?:lensrouter|dispatch|pm|integrator)-[A-Za-z0-9_-]+)",
            full_txt,
        )
        if m_from:
            sender = m_from.group(1).strip()
    if not sender and filename:
        m_fn = re.search(
            r"((?:bd-)?(?:lensrouter|dispatch|pm|integrator)-[A-Za-z0-9_-]+?)(?:-\d{8}T\d+Z)?\.md$",
            filename,
        )
        if m_fn:
            s_cand = m_fn.group(1)
            sender = s_cand if s_cand.startswith("bd-") else f"bd-{s_cand}"
    for k in (
        "SANDBOX",
        "TARGET_FILE",
        "TARGET_TEST",
        "VERDICT_PATH",
        "WRITE",
        "WORKTREE",
        "WT",
        "CUT",
        "BRIEF",
        "DONE-SHA256",
    ):
        mk = re.search(rf"\b{k}\s*[:=]\s*([^\s\n]+)", full_txt)
        if mk:
            val = mk.group(1).strip("`'\"")
            meta[k] = _norm_path(val) if val.startswith("/") else val
    if not meta.get("VERDICT_PATH"):
        if meta.get("WRITE"):
            meta["VERDICT_PATH"] = meta["WRITE"]
        else:
            m_wr = re.search(
                r"\bWrite\s+(/(?:home/mboyle|mnt/bd)/[^\s:()]+\.md)",
                full_txt,
                flags=re.I,
            )
            if m_wr:
                meta["VERDICT_PATH"] = _norm_path(m_wr.group(1))
    if not meta.get("WORKTREE") and meta.get("WT"):
        meta["WORKTREE"] = meta["WT"]
    base_hint = _extract_base_from_text(full_txt)
    cut_dir = Path(meta["CUT"]) if meta.get("CUT") else None
    if not cut_dir and meta.get("VERDICT_PATH"):
        vp_cand = Path(meta["VERDICT_PATH"])
        if vp_cand.parent.name == ".review" and not _is_worktree_path(
            vp_cand.parent.parent
        ):
            cut_dir = vp_cand.parent.parent
            meta["CUT"] = str(cut_dir)
    if cut_dir and (cut_dir / "DONE.md").is_file():
        verified = _verify_done_cut(cut_dir)
        if verified is None:
            meta["done_mismatch"] = "1"
            return sender, "\n".join(enriched), meta
        meta.update(verified)
        try:
            dtxt = (cut_dir / "DONE.md").read_text(encoding="utf-8", errors="replace")[
                :4000
            ]
            if f"REFERENCED FILE: {cut_dir / 'DONE.md'}" not in full_txt:
                enriched.append(
                    f"\n--- CUT DONE.md ({cut_dir / 'DONE.md'}) ---\n{dtxt}"
                )
        except Exception:
            pass
        enriched.append(
            f"\n--- STAGED CUT DIFF (DONE-PINNED: git -C {verified['worktree']} diff --cached --full-index {verified['base']}) ---\n"
            f"TREE: {verified['tree']}\nPATCH-SHA256: {verified['patch_sha256']}\nFILES: {verified['files']}\n\n"
            f"{verified['diff']}"
        )
        return sender, "\n".join(enriched), meta

    wt_str = meta.get("WORKTREE") or ""
    if not wt_str:
        for extra_p in re.findall(
            r"(/(?:home/mboyle|mnt/bd)/[^\s|'\")>\]]+)", "\n".join(enriched)
        ):
            ep = Path(_norm_path(extra_p))
            if ep.is_dir() and (ep / ".git").exists():
                wt_str = str(ep)
                break
    if wt_str:
        wt_path = Path(_norm_path(wt_str))
        meta["worktree"] = str(wt_path)
        info = _extract_cut_diff_and_pins(wt_path, base_hint=base_hint, cut_dir=cut_dir)
        meta.update({k: v for k, v in info.items() if v})
        if info.get("diff"):
            enriched.append(
                f"\n--- STAGED CUT DIFF (git -C {wt_path} diff --cached --full-index {info.get('base')}) ---\n"
                f"TREE: {info.get('tree')}\nPATCH-SHA256: {info.get('patch_sha256')}\nFILES: {info.get('files')}\n\n"
                f"{info['diff']}"
            )
    elif "diff --git " in full_txt:
        idx = full_txt.find("diff --git ")
        inline_diff = full_txt[idx:].strip()
        meta["patch_sha256"] = hashlib.sha256(
            inline_diff.encode("utf-8", errors="replace")
        ).hexdigest()
        f_matches = re.findall(r"^diff --git a/(\S+) b/(\S+)", inline_diff, flags=re.M)
        if f_matches:
            meta["files"] = " ".join(sorted({b for _, b in f_matches}))
    return sender, "\n".join(enriched), meta


QUEUE_TO_DISPATCH = {
    "P2-FIX-QUEUE": "bd-dispatch-F1-D",
    "BH2-BUILD-QUEUE": "bd-dispatch-B5-B",
    "BH1-BACKLOG-QUEUE": "bd-dispatch-H1-A",
    "O1670-QUEUE": "bd-dispatch-D2-D",
    "O1671-PRODUCT-CANDIDATES": "bd-dispatch-P1-C",
    "APP-DL-FIX-QUEUE": "bd-dispatch-F2-D",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seat", required=True)
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--role", default="local-worker")
    ap.add_argument("--mode", choices=["pregate", "triage"], default="pregate")
    ap.add_argument("--shard-idx", type=int, default=0)
    ap.add_argument("--shard-mod", type=int, default=2)
    args = ap.parse_args()
    canon_model = _canon_model_name(args.endpoint, args.model)

    inbox_dir = Path(f"/home/mboyle/bd-persist/inbox/{args.seat}")
    done_dir = inbox_dir / "processed"
    out_dir = Path(
        f"/home/mboyle/bd-persist/harness-work/O1789/local-seats/{args.seat}"
    )
    inbox_dir.mkdir(parents=True, exist_ok=True)
    done_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / "LEDGER.jsonl"

    done_items: set[str] = set()
    if ledger_path.exists():
        for line in ledger_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            try:
                done_items.add(json.loads(line).get("item", ""))
            except Exception:
                pass

    sec_clause = (
        "Act as an Attacker & Offensive Security Review Agent (review-security): hunt specifically for command/shell injection, path traversal, SSRF, credential/secret leaks, auth/permission bypasses, symlink/TOCTOU races, and trust-boundary defects. "
        if ("cyberstrike" in canon_model.lower() or "137" in args.seat)
        else ""
    )
    sys_prompt = (
        f"You are {args.seat} ({args.role}), a Boylenet $0 Local GPU Agent running on {args.endpoint} ({canon_model}). "
        f"{sec_clause}"
        "Review ONLY the files in STAGED CUT DIFF (FILES list). Never invent files outside the staged diff. "
        "Provide concise, machine-actionable output (<=12 lines): verdict (BOARD / BOARD-WITH-ADVISORY / REFUTE or LAND / LENS / REBRIEF / CLOSE), "
        "key findings with exact file:line coordinates from the staged diff, and any surgical fix needed."
    )

    print(
        f"[{now_iso()}] [{args.seat}] ACTIVE Local GPU Seat online -> {args.endpoint} (canon={canon_model}, mode={args.mode}, shard={args.shard_idx}/{args.shard_mod})",
        flush=True,
    )
    auto_counter = 0

    while True:
        try:
            # 1. Drain explicit inbox packets first (supports BUILD orders via bd-local-coding-agent + LENS/PREGATE orders)
            msgs = sorted(glob.glob(str(inbox_dir / "*.md")))
            for mpath in msgs:
                mp = Path(mpath)
                if mp.name.startswith("BATCH-"):
                    mp.rename(done_dir / mp.name)
                    continue
                raw_content = mp.read_text(encoding="utf-8", errors="replace")
                sender, content, meta = _enrich_inbox_order(raw_content, mp.name)
                print(
                    f"[{now_iso()}] [{args.seat}] INBOX work: {mp.name} (sender={sender or 'direct'}, {len(content)}B)...",
                    flush=True,
                )
                if meta.get("done_mismatch") == "1":
                    print(
                        f"[{now_iso()}] [{args.seat}] SKIP_MISMATCH inbox {mp.name}: DONE.md TREE/PATCH-SHA256 mismatch in builder WORKTREE (O3401 write nothing)",
                        flush=True,
                    )
                    mp.rename(done_dir / mp.name)
                    continue
                res_path = out_dir / f"RESULT-{mp.stem}.md"
                notify_path = res_path
                if (
                    meta.get("SANDBOX")
                    and meta.get("TARGET_FILE")
                    and meta.get("TARGET_TEST")
                ):
                    backend_id = SEAT_TO_BACKEND.get(args.seat, "auto")
                    t0 = time.monotonic()
                    r_build = subprocess.run(
                        [
                            "/home/mboyle/bin/bd-local-coding-agent",
                            "--backend",
                            backend_id,
                            "--sandbox",
                            meta["SANDBOX"],
                            "--target-file",
                            meta["TARGET_FILE"],
                            "--target-test",
                            meta["TARGET_TEST"],
                            "--prompt",
                            content[:6000],
                            "--json",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=300,
                        check=False,
                    )
                    elapsed = round(time.monotonic() - t0, 2)
                    tps = 0.0
                    reply = r_build.stdout.strip() or r_build.stderr.strip()
                    res_path.write_text(
                        f"# {args.seat} Cut Build Result (`{mp.name}`)\n- **Backend**: `{backend_id}` (`{args.endpoint}`, `{canon_model}`)\n- **Elapsed**: `{elapsed}s`\n- **RC**: `{r_build.returncode}`\n\n```json\n{reply}\n```\n",
                        encoding="utf-8",
                    )
                else:
                    expected_done = meta.get("DONE-SHA256", "")
                    actual_done = meta.get("done_sha256", "")
                    if expected_done and actual_done and expected_done != actual_done:
                        print(
                            f"[{now_iso()}] [{args.seat}] SKIP_MISMATCH inbox {mp.name}: DONE-SHA256 mismatch ({expected_done[:10]} != {actual_done[:10]})",
                            flush=True,
                        )
                        mp.rename(done_dir / mp.name)
                        continue
                    if meta.get("VERDICT_PATH") and not meta.get("patch_sha256"):
                        print(
                            f"[{now_iso()}] [{args.seat}] SKIP_MISMATCH inbox {mp.name}: empty staged diff in WORKTREE={meta.get('worktree')}",
                            flush=True,
                        )
                        mp.rename(done_dir / mp.name)
                        continue
                    ib_deadline = mp.stat().st_mtime + 600.0
                    reply, elapsed, tps = run_completion(
                        args.endpoint,
                        args.model,
                        sys_prompt,
                        content[-6500:],
                        deadline_ts=ib_deadline,
                    )
                    if reply.startswith("SKIPPED:"):
                        print(
                            f"[{now_iso()}] [{args.seat}] SKIPPED inbox {mp.name}: {reply}",
                            flush=True,
                        )
                        mp.rename(done_dir / mp.name)
                        continue
                    v_tok_ib = _parse_verdict_token(reply)
                    if v_tok_ib == "UNKNOWN":
                        print(
                            f"[{now_iso()}] [{args.seat}] SKIP_ERROR inbox {mp.name}: {reply[:120]}",
                            flush=True,
                        )
                        continue
                    is_done_verified = meta.get("done_verified") == "1"
                    hdr_tag = (
                        "VERDICT-ADVISORY" if is_done_verified else "PREGATE-VERDICT"
                    )
                    mode_lbl = (
                        "LOCAL-LENS (scored, DONE-pinned)"
                        if is_done_verified
                        else "PREGATE (pre-DONE, unscored)"
                    )
                    body = _format_stamped_verdict(
                        args.seat,
                        args.endpoint,
                        canon_model,
                        elapsed,
                        tps,
                        meta,
                        reply,
                        f"{args.seat} Inbox Review (`{mp.name}`)",
                        header_tag=hdr_tag,
                        mode_label=mode_lbl,
                    )
                    res_path.write_text(body, encoding="utf-8")
                    cut_p = Path(meta["CUT"]) if meta.get("CUT") else None
                    if (
                        is_done_verified
                        and cut_p
                        and cut_p.is_dir()
                        and not _is_worktree_path(cut_p)
                    ):
                        rev_dir = cut_p / ".review"
                        rev_dir.mkdir(parents=True, exist_ok=True)
                        lens_p = rev_dir / f"LOCAL-LENS-{args.seat}.md"
                        lens_p.write_text(body, encoding="utf-8")
                        notify_path = lens_p
                        if meta.get("VERDICT_PATH"):
                            vp = Path(meta["VERDICT_PATH"])
                            if not _is_worktree_path(
                                vp.parent
                            ) and not vp.name.startswith("VERDICT-"):
                                vp.parent.mkdir(parents=True, exist_ok=True)
                                vp.write_text(body, encoding="utf-8")
                                notify_path = vp
                        cut_label = (
                            f"{cut_p.parent.name}-{cut_p.name}"
                            if re.match(r"^r\d+$", cut_p.name)
                            else cut_p.name
                        )
                        _record_local_lens_score(cut_label, canon_model, v_tok_ib)
                    elif meta.get("VERDICT_PATH") and meta.get("patch_sha256"):
                        vp = Path(meta["VERDICT_PATH"])
                        if not _is_worktree_path(vp.parent):
                            vp.parent.mkdir(parents=True, exist_ok=True)
                            if vp.name.startswith("VERDICT-") or vp.name.startswith(
                                "LOCAL-LENS-"
                            ):
                                vp = vp.parent / f"LOCAL-PREGATE-{args.seat}.md"
                            vp.write_text(body, encoding="utf-8")
                            notify_path = vp
                mp.rename(done_dir / mp.name)
                if sender and sender not in (args.seat, "unknown"):
                    subprocess.run(
                        [
                            "/home/mboyle/bd-persist/harness/bd-say.sh",
                            sender,
                            f"DONE {args.seat} {notify_path}",
                        ],
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                print(
                    f"[{now_iso()}] [{args.seat}] DONE inbox {mp.name} -> {notify_path.name} (notified={sender or 'none'}, {elapsed}s, {tps} tok/s)",
                    flush=True,
                )

            # 2. Priority 1: Scored LOCAL-LENS on cuts with verified DONE.md (O3401/O3406/O3407)
            done_cut_item = discover_done_cut_for_local_lens(
                done_items, args.shard_idx, args.shard_mod, args.seat, canon_model
            )
            if not done_cut_item:
                done_cut_item = discover_done_cut_for_local_lens(
                    done_items,
                    args.shard_idx,
                    args.shard_mod,
                    args.seat,
                    canon_model,
                    allow_steal=True,
                )
            if done_cut_item:
                cut_label, cut_info = done_cut_item
                diff_text = cut_info.get("diff", "")
                item_key = cut_info.get("item_key", f"LOCAL-LENS:{cut_label}")
                deadline_ts = float(cut_info.get("deadline_ts") or (time.time() + 600.0))
                print(
                    f"[{now_iso()}] [{args.seat}] LOCAL-LENS reviewing DONE cut `{cut_label}` ({len(diff_text)}B staged diff, tree={cut_info.get('tree', '')[:8]})...",
                    flush=True,
                )
                prompt = (
                    f"Review DONE-pinned staged git diff for cut `{cut_label}` (FILES: {cut_info.get('files')}, BASE: {cut_info.get('base')}, TREE: {cut_info.get('tree')}, PATCH-SHA256: {cut_info.get('patch_sha256')}) under Rule 86 (Behavioral Defect vs Mutation Coverage Severance).\n"
                    f"Review ONLY the changed files ({cut_info.get('files')}). Output verdict (BOARD | BOARD-WITH-ADVISORY | REFUTE) and <=5 bullet findings:\n\n{diff_text}"
                )
                reply, elapsed, tps = run_completion(
                    args.endpoint,
                    args.model,
                    sys_prompt,
                    prompt,
                    deadline_ts=deadline_ts,
                )
                if reply.startswith("SKIPPED:"):
                    print(
                        f"[{now_iso()}] [{args.seat}] SKIPPED LOCAL-LENS `{cut_label}` ({canon_model}): {reply}",
                        flush=True,
                    )
                    done_items.add(item_key)
                    continue
                v_tok = _parse_verdict_token(reply)
                if v_tok == "UNKNOWN":
                    print(
                        f"[{now_iso()}] [{args.seat}] SKIP_ERROR LOCAL-LENS `{cut_label}` ({elapsed}s): {reply[:120]}",
                        flush=True,
                    )
                    time.sleep(2)
                    continue
                cut_dir_p = Path(cut_info["CUT"])
                reverified = _verify_done_cut(cut_dir_p)
                if (
                    not reverified
                    or reverified["tree"] != cut_info["tree"]
                    or reverified["patch_sha256"] != cut_info["patch_sha256"]
                ):
                    print(
                        f"[{now_iso()}] [{args.seat}] SKIP_MISMATCH LOCAL-LENS `{cut_label}`: tree changed during review",
                        flush=True,
                    )
                    continue
                body = _format_stamped_verdict(
                    args.seat,
                    args.endpoint,
                    canon_model,
                    elapsed,
                    tps,
                    cut_info,
                    reply,
                    f"Local Lens Review (DONE-Pinned): `{cut_label}`",
                    header_tag="VERDICT-ADVISORY",
                    mode_label="LOCAL-LENS (scored, DONE-pinned)",
                )
                res_path = out_dir / f"LOCAL-LENS-{cut_label}.md"
                res_path.write_text(body, encoding="utf-8")
                if not _is_worktree_path(cut_dir_p):
                    rev_dir = cut_dir_p / ".review"
                    rev_dir.mkdir(parents=True, exist_ok=True)
                    (rev_dir / f"LOCAL-LENS-{args.seat}.md").write_text(
                        body, encoding="utf-8"
                    )
                _record_local_lens_score(cut_label, canon_model, v_tok)
                done_items.add(item_key)
                with ledger_path.open("a", encoding="utf-8") as lf:
                    lf.write(
                        json.dumps(
                            {
                                "ts": now_iso(),
                                "seat": args.seat,
                                "model": canon_model,
                                "mode": "local-lens",
                                "item": item_key,
                                "cut": cut_label,
                                "tree": cut_info.get("tree", ""),
                                "patch_sha256": cut_info.get("patch_sha256", ""),
                                "verdict": v_tok,
                                "elapsed_s": elapsed,
                                "tok_s": tps,
                                "out": str(
                                    cut_dir_p / ".review" / f"LOCAL-LENS-{args.seat}.md"
                                ),
                            }
                        )
                        + "\n"
                    )
                summary_1l = (
                    reply.strip().splitlines()[0][:90] if reply.strip() else "OK"
                )
                print(
                    f"[{now_iso()}] [{args.seat}] DONE LOCAL-LENS `{cut_label}` (tree={cut_info.get('tree', '')[:8]}) in {elapsed}s ({tps} tok/s) -> {v_tok}: {summary_1l}",
                    flush=True,
                )
                time.sleep(2)
                continue

            # 3. Priority 2: Shadow Builds on new ORDER/BRIEF (O3406/O3407)
            build_item = discover_order_for_shadow_build(
                done_items, args.shard_idx, args.shard_mod, args.seat, canon_model
            )
            if not build_item:
                build_item = discover_order_for_shadow_build(
                    done_items,
                    args.shard_idx,
                    args.shard_mod,
                    args.seat,
                    canon_model,
                    allow_steal=True,
                )
            if build_item:
                row_label, b_info = build_item
                item_key = b_info["item_key"]
                print(
                    f"[{now_iso()}] [{args.seat}] SHADOW-BUILD starting `{row_label}` (model={canon_model}, base={b_info['base'][:8]}, owns={b_info['owns']})...",
                    flush=True,
                )
                b_res = run_shadow_build(
                    args.seat, args.endpoint, args.model, canon_model, b_info
                )
                done_items.add(item_key)
                if b_res.get("status") == "SKIPPED":
                    print(
                        f"[{now_iso()}] [{args.seat}] SKIPPED SHADOW-BUILD `{row_label}` ({canon_model}): {b_res.get('reason')}",
                        flush=True,
                    )
                    continue
                if b_res.get("status") == "ERROR":
                    print(
                        f"[{now_iso()}] [{args.seat}] ERROR SHADOW-BUILD `{row_label}` ({canon_model}): {b_res.get('reason')}",
                        flush=True,
                    )
                    continue
                with ledger_path.open("a", encoding="utf-8") as lf:
                    lf.write(
                        json.dumps(
                            {
                                "ts": now_iso(),
                                "seat": args.seat,
                                "model": canon_model,
                                "mode": "shadow-build",
                                "item": item_key,
                                "row": row_label,
                                "tree": b_res.get("tree", ""),
                                "patch_sha256": b_res.get("patch_sha256", ""),
                                "tests_pass": b_res.get("tests_pass", ""),
                                "overlap_pct": b_res.get("overlap_pct", ""),
                                "out": b_res.get("out", ""),
                            }
                        )
                        + "\n"
                    )
                print(
                    f"[{now_iso()}] [{args.seat}] DONE SHADOW-BUILD `{row_label}` ({canon_model}) -> tests={b_res.get('tests_pass')}, overlap={b_res.get('overlap_pct')}, tree={b_res.get('tree', '')[:8]}",
                    flush=True,
                )
                time.sleep(2)
                continue

            if _is_loaded_scored_model(canon_model):
                time.sleep(6)
                continue
            cut_item = discover_cut_for_pregate(done_items, args.shard_idx, args.shard_mod) if args.mode == "pregate" else None
            triage_item = (
                discover_row_for_triage(done_items, args.shard_idx, args.shard_mod)
                if args.mode == "triage"
                else None
            )
            if not cut_item and not triage_item:
                if args.mode == "triage":
                    cut_item = discover_cut_for_pregate(
                        done_items, args.shard_idx, args.shard_mod
                    )
                else:
                    triage_item = discover_row_for_triage(
                        done_items, args.shard_idx, args.shard_mod
                    )
            if not cut_item and not triage_item:
                cut_item = discover_cut_for_pregate(
                    done_items, args.shard_idx, args.shard_mod, allow_steal=True
                )
            if not cut_item and not triage_item:
                triage_item = discover_row_for_triage(
                    done_items, args.shard_idx, args.shard_mod, allow_steal=True
                )

            if cut_item:
                cut_name, cut_info = cut_item
                diff_text = cut_info.get("diff", "")
                print(
                    f"[{now_iso()}] [{args.seat}] PREGATE (pre-DONE, unscored) reviewing wt `{cut_name}` ({len(diff_text)}B diff, tree={cut_info.get('tree', '')[:8]})...",
                    flush=True,
                )
                done_items.add(cut_name)
                prompt = (
                    f"Review pre-DONE git diff for worktree `{cut_name}` (FILES: {cut_info.get('files')}, BASE: {cut_info.get('base')}, TREE: {cut_info.get('tree')}, PATCH-SHA256: {cut_info.get('patch_sha256')}) under Rule 86 (Behavioral Defect vs Mutation Coverage Severance).\n"
                    f"Review ONLY the changed files ({cut_info.get('files')}). Output verdict (BOARD | BOARD-WITH-ADVISORY | REFUTE) and <=5 bullet findings:\n\n{diff_text}"
                )
                reply, elapsed, tps = run_completion(
                    args.endpoint, args.model, sys_prompt, prompt
                )
                v_tok = _parse_verdict_token(reply)
                if v_tok == "UNKNOWN":
                    print(
                        f"[{now_iso()}] [{args.seat}] SKIP_ERROR PREGATE `{cut_name}` ({elapsed}s): {reply[:120]}",
                        flush=True,
                    )
                    time.sleep(2)
                    continue
                res_path = out_dir / f"PREGATE-{cut_name}.md"
                body = _format_stamped_verdict(
                    args.seat,
                    args.endpoint,
                    args.model,
                    elapsed,
                    tps,
                    cut_info,
                    reply,
                    f"Local Pre-Gate Review (pre-DONE, unscored): `{cut_name}`",
                    header_tag="PREGATE-VERDICT",
                    mode_label="PREGATE (pre-DONE, unscored)",
                )
                res_path.write_text(body, encoding="utf-8")
                # O3401: NEVER write inside a worktree (wt_p / ".review"), and NEVER score pre-DONE PREGATE in LOCAL-LENS-SCORE.tsv.
                rollup_p = Path("/home/mboyle/bd-persist/state/LOCAL-PREGATE-LATEST.md")
                try:
                    with rollup_p.open("a", encoding="utf-8") as rf:
                        rf.write(
                            f"- `{now_iso()}` | `{args.seat}` | `PREGATE` | `{cut_name}` | **`{v_tok}`** | `TREE={cut_info.get('tree', '')[:10]}` | `{res_path}`\n"
                        )
                except Exception:
                    pass
                auto_counter += 1
                done_items.add(cut_name)
                with ledger_path.open("a", encoding="utf-8") as lf:
                    lf.write(
                        json.dumps(
                            {
                                "ts": now_iso(),
                                "seat": args.seat,
                                "mode": "pregate",
                                "item": cut_name,
                                "verdict": v_tok,
                                "elapsed_s": elapsed,
                                "tok_s": tps,
                                "out": str(res_path),
                            }
                        )
                        + "\n"
                    )
                summary_1l = (
                    reply.strip().splitlines()[0][:90] if reply.strip() else "OK"
                )
                print(
                    f"[{now_iso()}] [{args.seat}] DONE PREGATE `{cut_name}` in {elapsed}s ({tps} tok/s) -> {summary_1l}",
                    flush=True,
                )
                time.sleep(2)
                continue
            elif triage_item:
                row_key, row_dict = triage_item
                print(
                    f"[{now_iso()}] [{args.seat}] TRIAGE analyzing queue row `{row_key}`...",
                    flush=True,
                )
                prompt = (
                    f"Triage Boylenet backlog queue row `{row_key}` per ORDER-pm-local-llm-use.md:\n"
                    f"Row fields: {json.dumps(row_dict, indent=2)}\n"
                    f"Classify disposition as one of: LAND / LENS / REBRIEF / CLOSE, and give concrete next step."
                )
                reply, elapsed, tps = run_completion(
                    args.endpoint, args.model, sys_prompt, prompt
                )
                safe_key = row_key.replace(":", "__").replace("/", "_")
                res_path = out_dir / f"TRIAGE-{safe_key}.md"
                triage_body = f"# Local Queue Triage: `{row_key}`\n- **Seat**: `{args.seat}` (`{args.endpoint}`, `{args.model}`)\n- **Timestamp**: `{now_iso()}`\n- **Speed**: `{elapsed}s` (`{tps} tok/s`)\n\n{reply}\n"
                res_path.write_text(triage_body, encoding="utf-8")
                if ":" in row_key:
                    q_stem, rid_part = row_key.split(":", 1)
                    cdir = _claims_dir_for_queue(q_stem) / rid_part
                    try:
                        cdir.mkdir(parents=True, exist_ok=True)
                        (cdir / f"LOCAL-TRIAGE-{args.seat}.md").write_text(
                            triage_body, encoding="utf-8"
                        )
                    except Exception:
                        pass
                rollup_t = Path("/home/mboyle/bd-persist/state/LOCAL-TRIAGE-LATEST.md")
                try:
                    with rollup_t.open("a", encoding="utf-8") as tf:
                        tf.write(
                            f"- `{now_iso()}` | `{args.seat}` | `{row_key}` | `{res_path}`\n"
                        )
                except Exception:
                    pass
                auto_counter += 1
                if auto_counter % 25 == 0 and ":" in row_key:
                    q_stem = row_key.split(":", 1)[0]
                    target_disp = QUEUE_TO_DISPATCH.get(q_stem, "bd-pm-B")
                    subprocess.run(
                        [
                            "/home/mboyle/bd-say.sh",
                            target_disp,
                            f"LOCAL TRIAGE+{auto_counter}|{rollup_t}",
                        ],
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                done_items.add(row_key)
                with ledger_path.open("a", encoding="utf-8") as lf:
                    lf.write(
                        json.dumps(
                            {
                                "ts": now_iso(),
                                "seat": args.seat,
                                "mode": "triage",
                                "item": row_key,
                                "elapsed_s": elapsed,
                                "tok_s": tps,
                                "out": str(res_path),
                            }
                        )
                        + "\n"
                    )
                summary_1l = (
                    reply.strip().splitlines()[0][:90] if reply.strip() else "OK"
                )
                print(
                    f"[{now_iso()}] [{args.seat}] DONE TRIAGE `{row_key}` in {elapsed}s ({tps} tok/s) -> {summary_1l}",
                    flush=True,
                )
                time.sleep(2)
                continue
        except Exception as e:
            print(f"[{now_iso()}] [{args.seat}] Cycle error: {e}", flush=True)
        time.sleep(8)


if __name__ == "__main__":
    main()
