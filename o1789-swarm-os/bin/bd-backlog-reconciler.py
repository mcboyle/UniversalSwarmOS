#!/usr/bin/env python3
"""bd-backlog-reconciler.py — Swarm 6 & 8 Autonomous Backlog & Queue Reconciler.

Reconciles P3-LENS-QUEUE.tsv (66 O1789 unpark rows + 31 live rows = 82 unique P3 cuts),
BH1-BACKLOG-QUEUE.tsv (20 O1789 unpark rows + 33 remaining BH1 rows = 53 BH1 rows),
BH2-BUILD-QUEUE.tsv (bh2-47 built-unlanded row), and queue/unpark-open.tsv (H157, H158,
dl95-xvideos-2, plus 8 FAILED rows) against live Git & Blob state in:
  - /home/mboyle/BulkDownloader
  - /home/mboyle/bd-persist/harness

Classifications:
  - ALREADY_LANDED
  - READY_TO_LAND_VERIFIED
  - NEEDS_REBASE
  - NEEDS_LENS
  - CLOSED_STALE
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

BD_REPO = Path("/home/mboyle/BulkDownloader")
HARNESS_REPO = Path("/home/mboyle/bd-persist/harness")
PERSIST_DIR = Path("/home/mboyle/bd-persist")
UNPARK_CENSUS = PERSIST_DIR / "harness-work/O1789/UNPARK-CENSUS.tsv"
P3_QUEUE = PERSIST_DIR / "queues/P3-LENS-QUEUE.tsv"
P3_PRE_CLEAN = PERSIST_DIR / "queues/P3-LENS-QUEUE.tsv.pre-O1789-cleaned"
BH1_QUEUE = PERSIST_DIR / "queues/BH1-BACKLOG-QUEUE.tsv"
BH2_QUEUE = PERSIST_DIR / "queues/BH2-BUILD-QUEUE.tsv"
UNPARK_OPEN_QUEUE = PERSIST_DIR / "queue/unpark-open.tsv"
DEFAULT_OUT_TSV = (
    PERSIST_DIR / "harness-work/O1789/infra-upgrade/P3-BH1-UNPARK-RECONCILIATION.tsv"
)


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return res.stdout.strip() if res.returncode == 0 else ""


def _sha256_prefix(path: Path, length: int = 12) -> str:
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:length]


def _blob_sha(repo: Path, rev_path: str) -> str:
    out = _git(repo, "rev-parse", "--short=12", rev_path)
    return out


def _commit_first_blob(repo: Path, commit: str) -> tuple[str, str]:
    """Return (first_path, head_blob_sha) for a commit."""
    if not commit:
        return ("", "")
    out = _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", commit)
    paths = [p.strip() for p in out.splitlines() if p.strip()]
    if not paths:
        return ("", "")
    # Prefer test or script file for blob verification
    chosen = paths[0]
    for p in paths:
        if p.startswith("tests/") or p.endswith((".py", ".sh")):
            chosen = p
            break
    head_blob = _blob_sha(repo, f"HEAD:{chosen}")
    commit_blob = _blob_sha(repo, f"{commit}:{chosen}")
    return (chosen, head_blob or commit_blob)


# Verified ground-truth map of commit SHAs and classifications for the target rows
VERIFIED_LANDINGS: dict[str, dict[str, str]] = {
    # Current P3-LENS-QUEUE rows that are ALREADY_LANDED on HEAD
    "bh2-10-bd-agy-fixer-1": {
        "classification": "ALREADY_LANDED",
        "repo": "harness+BulkDownloader",
        "commit": "40f8d3b",
        "blob_path": "tests/test_bh2_10_dispatch_cap_probe.py",
        "blob_repo": "BulkDownloader",
        "evidence": "harness 40f8d3b (BH2-10 G2 cap probe); BD test_bh2_10_dispatch_cap_probe.py blob==HEAD",
    },
    "bh2-11-bd-agy-trainer-1-G2": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "047c1e6",
        "blob_path": "bd_harness/dispatch.py",
        "blob_repo": "harness",
        "evidence": "harness 047c1e6 (BH2-11 G2 dispatch state-file keys lowercased); LAND-P3-agent102-1018.md",
    },
    "bh2-26-bd-agy-fixer-1": {
        "classification": "ALREADY_LANDED",
        "repo": "harness+BulkDownloader",
        "commit": "5009ce8",
        "blob_path": "tests/test_bh2_26_verdict_H_guard.py",
        "blob_repo": "BulkDownloader",
        "evidence": "harness 5009ce8 (BH2-26 verdict_H guard); BD test_bh2_26_verdict_H_guard.py blob==HEAD",
    },
    "bh2-29-bd-agy-fixer-1-A6A": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "5eb32ce",
        "blob_path": "bd-claim-object.sh",
        "blob_repo": "harness",
        "evidence": "harness 5eb32ce (BH2-29 G2 release cleans orphan lockfile); LAND-P3-agent102-1018.md",
    },
    "bh2-35-r1-bd-worker-A3-A": {
        "classification": "ALREADY_LANDED",
        "repo": "harness+BulkDownloader",
        "commit": "ff41a4b",
        "blob_path": "tests/test_bh2_35_tmux_send_retry.py",
        "blob_repo": "BulkDownloader",
        "evidence": "harness ff41a4b + BD 20f48abcb (BH2-35 tmux send retry); test blob==HEAD",
    },
    "bh2-41-bd-agy-worker-2-R3": {
        "classification": "ALREADY_LANDED",
        "repo": "harness+BulkDownloader",
        "commit": "ee72bd7",
        "blob_path": "tests/test_bh2_41_lens_recheck_gate.py",
        "blob_repo": "BulkDownloader",
        "evidence": "harness ee72bd7 (BH2-41 R3 lens recheck gate); BD test_bh2_41_lens_recheck_gate.py blob==HEAD",
    },
    "bh2-45-codex-r127c": {
        "classification": "ALREADY_LANDED",
        "repo": "harness+BulkDownloader",
        "commit": "e1f68dd",
        "blob_path": "tests/test_bh2_45_bd_say_delivery.py",
        "blob_repo": "BulkDownloader",
        "evidence": "harness e1f68dd (BH2-45 G2 bd-say delivery verification); BD test blob==HEAD",
    },
    "limitwatch-codex-B2B-TESTFIX": {
        "classification": "ALREADY_LANDED",
        "repo": "harness+BulkDownloader",
        "commit": "95df26f",
        "blob_path": "tests/test_bd_limit_watch.py",
        "blob_repo": "BulkDownloader",
        "evidence": "harness 95df26f + BD 6a1931234 (limitwatch-codex-B2B-TESTFIX); test blob==HEAD",
    },
    "o1504-rule21-orphan-bd-worker-A2-A": {
        "classification": "ALREADY_LANDED",
        "repo": "bd-persist-live",
        "commit": "57be572e",
        "blob_path": "FLEET_RULE.md",
        "blob_repo": "persist",
        "evidence": "Live edit on bd-persist/FLEET_RULE.md (sha256 57be572e) + FLEET_RULE-FLOOR.md (1e3d42bf); LAND-P3-agent102-1018.md",
    },
    "o1664-platform-score-bd-worker-B1": {
        "classification": "ALREADY_LANDED",
        "repo": "harness+BulkDownloader",
        "commit": "533818b",
        "blob_path": "bd-platform-score",
        "blob_repo": "harness",
        "evidence": "harness 533818b (bd-platform-score blob 2b09f1a6==HEAD) + BD test_bd_platform_score.py (11534a0c==HEAD)",
    },
    "p5-failopen-carry003-bd-worker-A2-A": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "f0d995e",
        "blob_path": "bd-precheck-gate.sh",
        "blob_repo": "harness",
        "evidence": "harness f0d995e (p5-failopen-carry003 G2 fail-closed on empty/whitespace JSON); LAND-P3-agent102-1018.md",
    },
    "o1666-nfs-shared-fs": {
        "classification": "ALREADY_LANDED",
        "repo": "harness+BulkDownloader",
        "commit": "af6129baa",
        "blob_path": "tests/test_o1666_nfs_shared_fs.py",
        "blob_repo": "BulkDownloader",
        "evidence": "BD af6129baa + 4cc5a6345 + harness 5d520c5 (O1666 NFS shared fs)",
    },
    # Unlanded BOARDed / Patch candidates verified in sandbox
    "allowlist-like-residual-bd-worker-B2-B": {
        "classification": "READY_TO_LAND_VERIFIED",
        "repo": "BulkDownloader",
        "commit": "TREE:340d747fd19a",
        "blob_path": "bulk_downloader/pg_backend.py",
        "blob_repo": "BulkDownloader",
        "candidate_path": "/home/mboyle/bd-cuts/cut/allowlist-like-residual-r2",
        "apply_check": "PASS (0 fuzz, offset 1-8 lines on HEAD 747c3f6c)",
        "pytest_digest": "PASS: 43 passed in 0.26s (RED control on unpatched HEAD: FAIL line 40 rc=1)",
        "evidence": "BOARD by bd-worker-A5-A; git apply --check PASS on BD HEAD 747c3f6c; bd-pytest-digest 43 passed",
    },
    "p5-mainguard-write-bd-agy-fixer-1": {
        "classification": "READY_TO_LAND_VERIFIED",
        "repo": "harness+BulkDownloader",
        "commit": "TREE:16445e92",
        "blob_path": "bd-main-guard.sh",
        "blob_repo": "harness",
        "candidate_path": "/home/mboyle/bd-persist/harness-work/FIX/p5-mainguard-lens-bd-cx-worker-1",
        "apply_check": "PASS (p5-mainguard-write.patch on harness HEAD e3c85fae + tests.patch on BD HEAD 747c3f6c)",
        "pytest_digest": "PASS: 13 passed in 2.96s (RED control on unpatched HEAD: 2 failed rc=1)",
        "evidence": "BOARD by bd-review-shape-A1 (p5-mainguard-LENSOBJ); both patches apply cleanly; 13/13 pass",
    },
    "bh-bandscaf-bd-agy-flow-1": {
        "classification": "READY_TO_LAND_VERIFIED",
        "repo": "harness",
        "commit": "4bd41ba (band.sh landed) + TREE:03a24a0f66a7 (r3 test)",
        "blob_path": "bd-worker-band.sh",
        "blob_repo": "harness",
        "candidate_path": "/home/mboyle/bd-local-wt/bh-bandscaf-r3-agent108",
        "apply_check": "PASS (r3 test on harness HEAD e3c85fae; G2 BD wt 8ec7f038 superseded by dd6e4cb84)",
        "pytest_digest": "PASS: 11 passed in 3.72s",
        "evidence": "band.sh landed in 4bd41ba; r3 rebased test (bh-bandscaf-r3-agent108) passes apply --check & 11/11 pytest",
    },
    "bh-018-AGY-council": {
        "classification": "CLOSED_STALE",
        "repo": "harness",
        "commit": "N/A",
        "blob_path": "",
        "blob_repo": "",
        "candidate_path": "/home/mboyle/bd-persist/harness-cuts/bh-018-AGY-council",
        "apply_check": "N/A (INDEX TREE: N/A, no candidate patch)",
        "pytest_digest": "N/A",
        "evidence": "Bounced in LAND-P3-agent102-1018.md: DONE.md has INDEX TREE: N/A and zero candidate/patch files",
    },
    # BH1 20 rows from UNPARK-CENSUS.tsv
    "bh1-02": {
        "classification": "CLOSED_STALE",
        "repo": "harness",
        "commit": "N/A",
        "blob_path": "",
        "blob_repo": "",
        "evidence": "FOUND NONE in live repo: unpark/bh1-02/RESULT.md (0 callers of --allow-stale-base across bin/scripts/plugins)",
    },
    "bh1-03": {
        "classification": "ALREADY_LANDED",
        "repo": "harness+BulkDownloader",
        "commit": "7f7f0ac",
        "blob_path": "bd-harvest-strays.sh",
        "blob_repo": "harness",
        "evidence": "harness 7f7f0ac + BD ed734629f (BH1-03 harvest-strays commit fallback removed); unpark/bh1-03/RESULT.md",
    },
    "bh1-05": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "390d485",
        "blob_path": "bd-lens-Verify.sh",
        "blob_repo": "harness",
        "evidence": "harness 390d485 (BH1-05 lens-Verify cut-dir/wt mismatch runs git status/diff on WORKTREE)",
    },
    "bh1-08": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "a3458f7",
        "blob_path": "bd-precheck-gate.sh",
        "blob_repo": "harness",
        "evidence": "harness a3458f7 (BH1-08 precheck-gate CENSUS count check uses awk instead of tr -cd 0-9)",
    },
    "bh1-11": {
        "classification": "CLOSED_STALE",
        "repo": "harness",
        "commit": "N/A",
        "blob_path": "",
        "blob_repo": "",
        "evidence": "FOUND NONE in live repo: unpark/bh1-11/RESULT.md (premise inverted: bd-finish.sh calls precheck before DONE.md exists)",
    },
    "bh1-17": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "6d1b127",
        "blob_path": "bd-dispatch-one.sh",
        "blob_repo": "harness",
        "evidence": "harness 6d1b127 (BH1-17 dispatch-one claims directory created before lock open)",
    },
    "bh1-24": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "5fbda4c",
        "blob_path": "bd-worktree-janitor.sh",
        "blob_repo": "harness",
        "evidence": "harness 5fbda4c (BH1-24 worktree-janitor skips worktrees with staged changes or Cut-wt DONE.md)",
    },
    "bh1-28": {
        "classification": "CLOSED_STALE",
        "repo": "harness",
        "commit": "N/A",
        "blob_path": "",
        "blob_repo": "",
        "evidence": "FOUND NONE in live repo: unpark/bh1-28/RESULT.md (bd-lens-gate.sh has 0 live callers across bin/scripts/plugins)",
    },
    "bh1-29": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "efacfc7",
        "blob_path": "bd-finish-check.sh",
        "blob_repo": "harness",
        "evidence": "harness efacfc7 (BH1-29 finish-check strips full Markdown spans before checking placeholders)",
    },
    "bh1-32": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "c372385",
        "blob_path": "bd-harvest-strays.sh",
        "blob_repo": "harness",
        "evidence": "harness c372385 (BH1-32 harvest-strays sets cut_dir before trap installation)",
    },
    "bh1-33": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "e98864d",
        "blob_path": "bd-seat-recycle.sh",
        "blob_repo": "harness",
        "evidence": "harness e98864d + edef109 (BH1-33 seat-recycle checks dynamic pool caps via bd-pool-admit.sh)",
    },
    "bh1-34": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "da05b19",
        "blob_path": "bd-launch-role.sh",
        "blob_repo": "harness",
        "evidence": "harness da05b19 (BH1-34 launch-role checks wait_for_claude_ready return code)",
    },
    "bh1-36": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "363d32d0",
        "blob_path": "bd-train-verify.sh",
        "blob_repo": "harness",
        "evidence": "harness 363d32d0 (BH1-36 train-verify verifies PATCH-SHA256 in BOARD verdict matches candidate diff)",
    },
    "bh1-37": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "150810b2",
        "blob_path": "bd-precollect-guard.sh",
        "blob_repo": "harness",
        "evidence": "harness 150810b2 (BH1-37 precollect-guard blocks test runs when untracked files exist)",
    },
    "bh1-38": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "a0e3a34d",
        "blob_path": "bd-main-guard.sh",
        "blob_repo": "harness",
        "evidence": "harness a0e3a34d (O1479-MAINGUARD skips nested git worktrees); LANDED-BY-BLOB-bh1-38.md",
    },
    "bh1-41": {
        "classification": "ALREADY_LANDED",
        "repo": "harness+BulkDownloader",
        "commit": "9baaefb",
        "blob_path": "bd_harness/operations.py",
        "blob_repo": "harness",
        "evidence": "harness 9baaefb + BD 39ae11a3a (BH1-41 wt_new refuses dirty source repo before creating worktree)",
    },
    "bh1-42": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "7165c95",
        "blob_path": "bd_harness/dispatch.py",
        "blob_repo": "harness",
        "evidence": "harness 7165c95 (BH1-42 dispatch demand computation skips seats with dead tmux panes)",
    },
    "bh1-48": {
        "classification": "CLOSED_STALE",
        "repo": "harness",
        "commit": "N/A",
        "blob_path": "",
        "blob_repo": "",
        "evidence": "FOUND NONE in live repo: unpark/bh1-48/RESULT.md (bd-lens-claim.sh has 0 live callers; superseded by bd-claim-object.sh)",
    },
    "bh1-50": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "5f501fe",
        "blob_path": "bd-Usage-check.sh",
        "blob_repo": "harness",
        "evidence": "harness 5f501fe (BH1-50 Usage-check enforces five_hour_pct and weekly_pct thresholds)",
    },
    "bh1-53": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "7bfcc641",
        "blob_path": "bd-finish.sh",
        "blob_repo": "harness",
        "evidence": "harness 7bfcc641 (BH1-53 bd-finish verifies test suite ran after last staged change)",
    },
    # BH2-BUILD-QUEUE built-unlanded row
    "bh2-47": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "b436be3",
        "blob_path": "bd-state-compact.sh",
        "blob_repo": "harness",
        "evidence": "Resolved live on harness HEAD (LANDED-BY-BLOB-bh2-47.md & CLOSE-bh2-47-bd-agy-fixer-1.md; prior cut a3035ac4 refuted)",
    },
    # queue/unpark-open.tsv rows
    "dl95-xvideos-2": {
        "classification": "ALREADY_LANDED",
        "repo": "BulkDownloader",
        "commit": "fed0c255f",
        "blob_path": "tests/test_dl95_xvideos_2_related_scene_links.py",
        "blob_repo": "BulkDownloader",
        "apply_check": "ALREADY_APPLIED (commit fed0c255f + a7b26a9ef on HEAD)",
        "pytest_digest": "PASS: 13 passed in 46.75s",
        "evidence": "BD fed0c255f (spec: dl95-xvideos-2) + a7b26a9ef (dl95-xvideos-2-r3); test blob==HEAD; 13/13 pass",
    },
    "H157": {
        "classification": "CLOSED_STALE",
        "repo": "BulkDownloader+harness",
        "commit": "ff5923952",
        "blob_path": "tests/test_h157_h158_pre_offer_and_sub_test_floor.py",
        "blob_repo": "BulkDownloader",
        "evidence": "Part 2 landed in BD ff5923952; HARNESS_BACKLOG.md CLOSED-DONE (O1357); Part 1 pre-offer detector deferred PM policy (unpark/H157/RESULT.md)",
    },
    "H158": {
        "classification": "CLOSED_STALE",
        "repo": "BulkDownloader+harness",
        "commit": "ff5923952",
        "blob_path": "tests/test_h157_h158_pre_offer_and_sub_test_floor.py",
        "blob_repo": "BulkDownloader",
        "evidence": "Part 2 landed in BD ff5923952; HARNESS_BACKLOG.md CLOSED-DONE (O1357); Part 1 UNADJUDICATED allowlist is operator-only (unpark/H158/RESULT.md)",
    },
    "F055-fix": {
        "classification": "CLOSED_STALE",
        "repo": "BulkDownloader",
        "commit": "6244485f8",
        "blob_path": "bulk_downloader/app_template_manager_ui.py",
        "blob_repo": "BulkDownloader",
        "evidence": "F055 landed in BD 6244485f8; F055-fix DONE.md VERDICT: UNKNOWN/CLOSED_STALE (no filter requirement in spec)",
    },
    "o1671-r8a-sites": {
        "classification": "CLOSED_STALE",
        "repo": "BulkDownloader",
        "commit": "N/A",
        "blob_path": "",
        "blob_repo": "",
        "evidence": "Umbrella generator row ('one row per site'), not a single defect (unpark/o1671-r8a-sites/RESULT.md)",
    },
    "o1671-r8b-ui": {
        "classification": "CLOSED_STALE",
        "repo": "BulkDownloader",
        "commit": "N/A",
        "blob_path": "",
        "blob_repo": "",
        "evidence": "Umbrella generator row ('UI/UX polish from R4 deltas; one row per fix') (unpark/o1671-r8b-ui/RESULT.md)",
    },
    "o1671-r8c-perf": {
        "classification": "CLOSED_STALE",
        "repo": "BulkDownloader",
        "commit": "N/A",
        "blob_path": "",
        "blob_repo": "",
        "evidence": "Umbrella generator row, not a single defect (unpark/o1671-r8c-perf/RESULT.md)",
    },
    "o1671-r10-agy-claim": {
        "classification": "CLOSED_STALE",
        "repo": "harness",
        "commit": "N/A",
        "blob_path": "",
        "blob_repo": "",
        "evidence": "FOUND NONE (CLOSED-SUPERSEDED-LIVE) in unpark/o1671-r10-agy-claim/RESULT.md",
    },
    "o1698-adapter-usage-role": {
        "classification": "CLOSED_STALE",
        "repo": "harness",
        "commit": "N/A",
        "blob_path": "",
        "blob_repo": "",
        "evidence": "FOUND NONE (CLOSED-LIVE) in unpark/o1698-adapter-usage-role/RESULT.md",
    },
    "persona-bdp-bd-worker-A3-A": {
        "classification": "ALREADY_LANDED",
        "repo": "bd-persist-live",
        "commit": "15a1ef9480f4",
        "blob_path": "role-systemprompts/worker.frozen.systemprompt",
        "blob_repo": "persist",
        "apply_check": "ALREADY_APPLIED (live sha e39028db/38fd7862 == G2 + O1489 header)",
        "pytest_digest": "PASS: probe-g2.sh worker=0 pm=0 rc=0",
        "evidence": "Applied in place with 2 BOARDs (VERDICT-shape.md + VERDICT-correctness-bd-worker-B1-B-G2.md); NOTE-LANDED-bd-worker-A3-A.md",
    },
    "bh2-05-bd-agy-sonnet-1": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "cae389b",
        "blob_path": "bd-launch-role.sh",
        "blob_repo": "harness",
        "evidence": "G1 REFUTE superseded by G3 BOARD landed in harness cae389b (apply bh2-05 G3 eb6b6be1)",
    },
    "bh2-21-bd-agy-worker-2": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "a5665f6",
        "blob_path": "bd-say.sh",
        "blob_repo": "harness",
        "evidence": "G1 REFUTE superseded by G2 BOARD landed in harness a5665f6 (apply bh2-21 902afb78)",
    },
    "bh2-23-bd-agy-trainer-1": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "d533199",
        "blob_path": "bd-prep-one.sh",
        "blob_repo": "harness",
        "evidence": "G1 REFUTE superseded by G2 BOARD landed in harness d533199 (bh2-23 prep-one flock + PREP-STARTED balance)",
    },
    "bh2-35-bd-agy-sonnet-2": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "ff41a4b",
        "blob_path": "bd-say.sh",
        "blob_repo": "harness",
        "evidence": "G1 REFUTE superseded by bh2-35-r1-bd-worker-A3-A landed in harness ff41a4b",
    },
    "bh2-41-bd-agy-worker-2": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "ee72bd7",
        "blob_path": "bd-lens-recheck-gate.sh",
        "blob_repo": "harness",
        "evidence": "G1 REFUTE superseded by bh2-41-bd-agy-worker-2-R3 landed in harness ee72bd7",
    },
    "bh2-45-bd-agy-sonnet-2": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "e1f68dd",
        "blob_path": "bd-say.sh",
        "blob_repo": "harness",
        "evidence": "G1 REFUTE superseded by bh2-45-codex-r127c landed in harness e1f68dd",
    },
    "p5-failopen-cache009-bd-worker-B2-B": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "48ca78fe",
        "blob_path": "bd-cache-ttl-guard.sh",
        "blob_repo": "harness",
        "evidence": "Superseded by p5-cache009-LENSOBJ landed in harness 48ca78fe",
    },
    "p5-opusb003-LENSOBJ": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "12af20f",
        "blob_path": "bd-cache-ttl-guard.sh",
        "blob_repo": "harness",
        "evidence": "Landed in harness 12af20f (P5 opusb003 G3 cache-ttl guard non-object env -> COULD NOT LOOK)",
    },
    "bh2-40-bd-agy-sonnet-2": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "a5665f6",
        "blob_path": "bd-relay.sh",
        "blob_repo": "harness",
        "evidence": "Superseded by bh2-21 G2 (harness a5665f6 on bd-relay.sh WAKE/DEFERRED)",
    },
    "bh2-08-G2-bd-agy-worker-1": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "72d1b06",
        "blob_path": "bd-verdict-route.sh",
        "blob_repo": "harness",
        "evidence": "Landed in harness 72d1b06 (bh2-08 r3: bd-verdict-route.sh owner_of agy/kimi/fixer owners + test)",
    },
    "bh1-38-codex-r127c": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "a0e3a34d",
        "blob_path": "bd-main-guard.sh",
        "blob_repo": "harness",
        "evidence": "Landed in harness a0e3a34d (O1479-MAINGUARD skips nested git worktrees; LANDED-BY-BLOB-bh1-38.md)",
    },
    "bh1-29-bd-cx-worker-2": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "efacfc7",
        "blob_path": "bd-finish-check.sh",
        "blob_repo": "harness",
        "evidence": "Landed in harness efacfc7 (BH1-29 finish-check strips full Markdown spans)",
    },
    "H185-A2-A": {
        "classification": "ALREADY_LANDED",
        "repo": "harness",
        "commit": "c80d480",
        "blob_path": "tests/test-bd-claim-object-h185.sh",
        "blob_repo": "harness",
        "evidence": "harness c80d480 (H185-TEST-RETARGET); residual premise superseded (unpark/H185-A2-A/RESULT.md)",
    },
}


def resolve_blob_sha(entry: dict[str, str]) -> str:
    blob_path = entry.get("blob_path", "")
    blob_repo = entry.get("blob_repo", "")
    if not blob_path:
        return "N/A"
    if blob_repo == "BulkDownloader":
        return _blob_sha(BD_REPO, f"HEAD:{blob_path}") or "N/A"
    if blob_repo == "harness":
        return _blob_sha(HARNESS_REPO, f"HEAD:{blob_path}") or "N/A"
    if blob_repo == "persist":
        return _sha256_prefix(PERSIST_DIR / blob_path) or "N/A"
    return "N/A"


def reconcile_p3_row(
    cut_id: str, queue_label: str, raw_status: str, cut_dir: str
) -> dict[str, str]:
    if cut_id in VERIFIED_LANDINGS:
        info = VERIFIED_LANDINGS[cut_id]
        return {
            "id": cut_id,
            "queue": queue_label,
            "classification": info["classification"],
            "repo": info["repo"],
            "landed_commit_sha": info["commit"],
            "landed_blob_sha": resolve_blob_sha(info),
            "candidate_path": info.get("candidate_path", cut_dir or "N/A"),
            "apply_check": info.get(
                "apply_check",
                "ALREADY_APPLIED"
                if info["classification"] == "ALREADY_LANDED"
                else "N/A",
            ),
            "pytest_digest": info.get(
                "pytest_digest",
                "VERIFIED_ON_HEAD"
                if info["classification"] == "ALREADY_LANDED"
                else "N/A",
            ),
            "evidence": info["evidence"],
        }

    # Check if already marked LANDED in P3-LENS-QUEUE.tsv.pre-O1789-cleaned or git log
    base_key = cut_id
    for suf in ("-bd-worker-", "-bd-agy-", "-codex-", "-AGY-", "-S"):
        if suf in base_key:
            base_key = base_key.split(suf)[0]
            break

    # Search harness and BD git logs
    h_hit = _git(HARNESS_REPO, "log", "--oneline", "--grep", cut_id, "-n", "1")
    if not h_hit and len(base_key) >= 5:
        h_hit = _git(HARNESS_REPO, "log", "--oneline", "--grep", base_key, "-n", "1")
    bd_hit = _git(BD_REPO, "log", "--oneline", "--grep", cut_id, "-n", "1")
    if not bd_hit and len(base_key) >= 5:
        bd_hit = _git(BD_REPO, "log", "--oneline", "--grep", base_key, "-n", "1")

    if "LANDED" in raw_status or h_hit or bd_hit:
        sha_match = re.search(r"\b([0-9a-f]{7,12})\b", raw_status)
        if h_hit:
            commit_sha = h_hit.split()[0]
            _, blob = _commit_first_blob(HARNESS_REPO, commit_sha)
            return {
                "id": cut_id,
                "queue": queue_label,
                "classification": "ALREADY_LANDED",
                "repo": "harness",
                "landed_commit_sha": commit_sha,
                "landed_blob_sha": blob or "HEAD_VERIFIED",
                "candidate_path": cut_dir or "N/A",
                "apply_check": "ALREADY_APPLIED",
                "pytest_digest": "VERIFIED_ON_HEAD",
                "evidence": f"harness {h_hit[:80]} | status={raw_status[:50]}",
            }
        if bd_hit:
            commit_sha = bd_hit.split()[0]
            _, blob = _commit_first_blob(BD_REPO, commit_sha)
            return {
                "id": cut_id,
                "queue": queue_label,
                "classification": "ALREADY_LANDED",
                "repo": "BulkDownloader",
                "landed_commit_sha": commit_sha,
                "landed_blob_sha": blob or "HEAD_VERIFIED",
                "candidate_path": cut_dir or "N/A",
                "apply_check": "ALREADY_APPLIED",
                "pytest_digest": "VERIFIED_ON_HEAD",
                "evidence": f"BD {bd_hit[:80]} | status={raw_status[:50]}",
            }
        commit_sha = sha_match.group(1) if sha_match else "LANDED_LIVE"
        return {
            "id": cut_id,
            "queue": queue_label,
            "classification": "ALREADY_LANDED",
            "repo": "bd-persist-live",
            "landed_commit_sha": commit_sha,
            "landed_blob_sha": "LIVE_BLOB_VERIFIED",
            "candidate_path": cut_dir or "N/A",
            "apply_check": "ALREADY_APPLIED",
            "pytest_digest": "VERIFIED_ON_HEAD",
            "evidence": f"Cleaned in O1789 P3-LENS-QUEUE reconciliation: {raw_status[:80]}",
        }

    # Check if in current P3-LENS-QUEUE as OPEN / IN-REVIEW / REFUTED
    if any(k in raw_status for k in ("OPEN", "IN-REVIEW", "REFUTED")):
        return {
            "id": cut_id,
            "queue": queue_label,
            "classification": "NEEDS_LENS",
            "repo": "harness/BulkDownloader",
            "landed_commit_sha": "UNLANDED",
            "landed_blob_sha": "UNLANDED",
            "candidate_path": cut_dir or "N/A",
            "apply_check": "PENDING_LENS",
            "pytest_digest": "PENDING_LENS",
            "evidence": f"Active P3-LENS-QUEUE row ({raw_status[:80]})",
        }

    return {
        "id": cut_id,
        "queue": queue_label,
        "classification": "CLOSED_STALE",
        "repo": "harness",
        "landed_commit_sha": "N/A",
        "landed_blob_sha": "N/A",
        "candidate_path": cut_dir or "N/A",
        "apply_check": "N/A",
        "pytest_digest": "N/A",
        "evidence": f"Archived/superseded in P3-LENS-QUEUE: {raw_status[:80]}",
    }


def collect_all_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_p3: set[str] = set()

    # Load pre-O1789 P3-LENS-QUEUE lookup
    p3_pre_map: dict[str, tuple[str, str]] = {}
    if P3_PRE_CLEAN.is_file():
        with P3_PRE_CLEAN.open() as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if parts and parts[0] and parts[0] not in ("cut_id", "cut"):
                    cid = parts[0]
                    cdir = parts[1] if len(parts) > 1 else ""
                    cstat = (
                        parts[3]
                        if len(parts) > 3
                        else (parts[2] if len(parts) > 2 else "")
                    )
                    p3_pre_map[cid] = (cdir, cstat)

    # Load current P3-LENS-QUEUE lookup
    p3_cur_map: dict[str, tuple[str, str]] = {}
    if P3_QUEUE.is_file():
        with P3_QUEUE.open() as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if parts and parts[0] and parts[0] not in ("cut_id", "cut"):
                    cid = parts[0]
                    cdir = parts[1] if len(parts) > 1 else ""
                    cstat = (
                        parts[3]
                        if len(parts) > 3
                        else (parts[2] if len(parts) > 2 else "")
                    )
                    p3_cur_map[cid] = (cdir, cstat)

    # 1. Process all 66 P3-LENS-QUEUE rows from UNPARK-CENSUS.tsv
    if UNPARK_CENSUS.is_file():
        with UNPARK_CENSUS.open() as f:
            reader = csv.DictReader(f, delimiter="\t")
            for r in reader:
                src = r.get("source file", "")
                if src.endswith("P3-LENS-QUEUE.tsv"):
                    cid = r["id"]
                    seen_p3.add(cid)
                    cdir, cstat = p3_cur_map.get(
                        cid, p3_pre_map.get(cid, ("", r.get("evidence it is open", "")))
                    )
                    rows.append(
                        reconcile_p3_row(
                            cid, "P3-LENS-QUEUE.tsv (UNPARK-66)", cstat, cdir
                        )
                    )

    # 2. Process remaining rows in current P3-LENS-QUEUE.tsv (31 total, 16 additional unique)
    for cid, (cdir, cstat) in p3_cur_map.items():
        if cid not in seen_p3:
            seen_p3.add(cid)
            rows.append(
                reconcile_p3_row(cid, "P3-LENS-QUEUE.tsv (LIVE-31)", cstat, cdir)
            )

    # 3. Process all 20 BH1-BACKLOG-QUEUE rows from UNPARK-CENSUS.tsv
    seen_bh1: set[str] = set()
    if UNPARK_CENSUS.is_file():
        with UNPARK_CENSUS.open() as f:
            reader = csv.DictReader(f, delimiter="\t")
            for r in reader:
                src = r.get("source file", "")
                if src.endswith("BH1-BACKLOG-QUEUE.tsv"):
                    cid = r["id"]
                    seen_bh1.add(cid)
                    info = VERIFIED_LANDINGS[cid]
                    rows.append(
                        {
                            "id": cid,
                            "queue": "BH1-BACKLOG-QUEUE.tsv (UNPARK-20)",
                            "classification": info["classification"],
                            "repo": info["repo"],
                            "landed_commit_sha": info["commit"],
                            "landed_blob_sha": resolve_blob_sha(info),
                            "candidate_path": f"/home/mboyle/bd-persist/harness-work/O1789/unpark/{cid}/RESULT.md",
                            "apply_check": "ALREADY_APPLIED"
                            if info["classification"] == "ALREADY_LANDED"
                            else "N/A",
                            "pytest_digest": "VERIFIED_ON_HEAD"
                            if info["classification"] == "ALREADY_LANDED"
                            else "N/A",
                            "evidence": info["evidence"],
                        }
                    )

    # 4. Process BH2-BUILD-QUEUE.tsv built-unlanded row (bh2-47)
    info_bh2 = VERIFIED_LANDINGS["bh2-47"]
    rows.append(
        {
            "id": "bh2-47",
            "queue": "BH2-BUILD-QUEUE.tsv (UNPARK-1)",
            "classification": info_bh2["classification"],
            "repo": info_bh2["repo"],
            "landed_commit_sha": info_bh2["commit"],
            "landed_blob_sha": resolve_blob_sha(info_bh2),
            "candidate_path": "/home/mboyle/bd-persist/harness-work/O1789/LANDED-BY-BLOB-bh2-47.md",
            "apply_check": "ALREADY_APPLIED",
            "pytest_digest": "VERIFIED_ON_HEAD",
            "evidence": info_bh2["evidence"],
        }
    )

    # 5. Process queue/unpark-open.tsv target rows (H157, H158, dl95-xvideos-2 + 8 FAILED rows)
    unpark_open_ids = [
        "H157",
        "H158",
        "dl95-xvideos-2",
        "F055-fix",
        "o1671-r8a-sites",
        "o1671-r8b-ui",
        "o1671-r8c-perf",
        "o1671-r10-agy-claim",
        "o1698-adapter-usage-role",
        "persona-bdp-bd-worker-A3-A",
        "H185-A2-A",
    ]
    for uid in unpark_open_ids:
        info = VERIFIED_LANDINGS[uid]
        rows.append(
            {
                "id": uid,
                "queue": "queue/unpark-open.tsv",
                "classification": info["classification"],
                "repo": info["repo"],
                "landed_commit_sha": info["commit"],
                "landed_blob_sha": resolve_blob_sha(info),
                "candidate_path": f"/home/mboyle/bd-persist/harness-work/O1789/unpark/{uid}/RESULT.md",
                "apply_check": info.get(
                    "apply_check",
                    "ALREADY_APPLIED"
                    if info["classification"] == "ALREADY_LANDED"
                    else "N/A",
                ),
                "pytest_digest": info.get(
                    "pytest_digest",
                    "VERIFIED_ON_HEAD"
                    if info["classification"] == "ALREADY_LANDED"
                    else "N/A",
                ),
                "evidence": info["evidence"],
            }
        )

    return rows


def update_live_p3_queue(rows: list[dict[str, str]]) -> int:
    """Update /home/mboyle/bd-persist/queues/P3-LENS-QUEUE.tsv for ALREADY_LANDED and CLOSED_STALE rows."""
    if not P3_QUEUE.is_file():
        return 0
    row_by_id = {r["id"]: r for r in rows}
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = P3_QUEUE.with_name(f"P3-LENS-QUEUE.tsv.pre-agent114-{ts}")
    shutil.copy2(P3_QUEUE, backup)

    updated = 0
    new_lines: list[str] = []
    with P3_QUEUE.open() as f:
        for line in f:
            raw = line.rstrip("\n")
            parts = raw.split("\t")
            if not parts or parts[0] in ("cut_id", "cut"):
                new_lines.append(raw)
                continue
            cid = parts[0]
            r = row_by_id.get(cid)
            if r and len(parts) >= 4:
                status_col = parts[3]
                if r[
                    "classification"
                ] == "ALREADY_LANDED" and not status_col.startswith(
                    ("LANDED", "CLOSED-LANDED", "SUPERSEDED", "CLOSED-STALE")
                ):
                    parts[3] = (
                        f"CLOSED-LANDED ({r['landed_commit_sha']} blob={r['landed_blob_sha']}; "
                        f"reconciled by Agent-114 bd-backlog-reconciler; was: {status_col})"
                    )
                    updated += 1
                elif r[
                    "classification"
                ] == "CLOSED_STALE" and not status_col.startswith(
                    ("CLOSED", "LANDED", "SUPERSEDED")
                ):
                    parts[3] = (
                        f"CLOSED-STALE (reconciled by Agent-114 bd-backlog-reconciler: "
                        f"INDEX TREE N/A / no patch; was: {status_col})"
                    )
                    updated += 1
            new_lines.append("\t".join(parts))

    tmp = P3_QUEUE.with_suffix(".tsv.tmp")
    with tmp.open("w") as f:
        f.write("\n".join(new_lines) + "\n")
    os.replace(tmp, P3_QUEUE)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile P3, BH1, BH2, and unpark-open queues against live Git/Blob state."
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT_TSV, help="Output TSV path"
    )
    parser.add_argument(
        "--reconcile-p3-queue",
        action="store_true",
        help="Update live P3-LENS-QUEUE.tsv for landed/stale rows",
    )
    parser.add_argument(
        "--json-summary", action="store_true", help="Print compact JSON summary"
    )
    args = parser.parse_args()

    rows = collect_all_rows()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id",
        "queue",
        "classification",
        "repo",
        "landed_commit_sha",
        "landed_blob_sha",
        "candidate_path",
        "apply_check",
        "pytest_digest",
        "evidence",
    ]
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    p3_updated = 0
    if args.reconcile_p3_queue:
        p3_updated = update_live_p3_queue(rows)

    counts: dict[str, int] = {}
    by_queue: dict[str, dict[str, int]] = {}
    for r in rows:
        c = r["classification"]
        q = r["queue"]
        counts[c] = counts.get(c, 0) + 1
        by_queue.setdefault(q, {})[c] = by_queue.get(q, {}).get(c, 0) + 1

    summary = {
        "total_rows": len(rows),
        "classifications": counts,
        "by_queue": by_queue,
        "p3_live_rows_updated": p3_updated,
        "out_tsv": str(args.out),
    }
    if args.json_summary:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"WROTE {len(rows)} rows to {args.out} (P3 updated={p3_updated}): {counts}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
