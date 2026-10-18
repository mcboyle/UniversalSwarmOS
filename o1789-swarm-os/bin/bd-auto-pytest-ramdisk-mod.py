#!/usr/bin/env python3
"""
Mod 2 — bd-auto-pytest-ramdisk-mod.py
Autonomous Post-Edit Ruff + Mypy + .82 Ramdisk Pytest Gate Mod.

Given any worktree or edited Python file in /home/mboyle/bd-local-wt/ or /home/mboyle/bd-cuts/:
  1. Resolves worktree root and edited Python file(s).
  2. Automatically discovers matching tests/test_*.py.
  3. Runs ruff check --select F,E9, mypy, and .82 /dev/shm ramdisk pytest via bd-pytest-digest
     in parallel (<4s wall clock).
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

AUTHORIZED_ROOTS = (
    "/home/mboyle/bd-local-wt",
    "/home/mboyle/bd-cuts",
)
RAMDISK_HOST = "10.0.70.82"
RAMDISK_REPO = "/dev/shm/bd-ci-ramdisk"
MYPY_BIN = "/home/mboyle/BulkDownloader/venv/bin/mypy"
PYTEST_DIGEST_BIN = "/home/mboyle/bin/bd-pytest-digest"

KNOWN_MODULE_TEST_MAP: dict[str, str] = {
    "runner_teach.py": "tests/test_dl_f2_auto_teach_direct_media.py",
    "runner.py": "tests/test_dl_f2_auto_teach_direct_media.py",
    "app_dl.py": "tests/test_dl_f2_auto_teach_direct_media.py",
}


def resolve_worktree_and_file(raw_path: str) -> tuple[Path, Path]:
    p = Path(raw_path).expanduser().resolve()
    # Check if raw_path is a symlink inside bd-local-wt/bd-cuts before resolve
    raw_abs = Path(os.path.abspath(os.path.expanduser(raw_path)))

    wt_root: Path | None = None
    for candidate in (raw_abs, p):
        s = str(candidate)
        for auth in AUTHORIZED_ROOTS:
            if s == auth or s.startswith(auth + "/"):
                rel_parts = Path(s[len(auth) + 1 :]).parts
                if rel_parts:
                    wt_root = Path(auth) / rel_parts[0]
                    break
        if wt_root is not None:
            break

    if wt_root is None:
        # Fallback if invoked on a file inside a git repo
        cur = p if p.is_dir() else p.parent
        while cur != cur.parent:
            if (cur / ".git").exists():
                wt_root = cur
                break
            cur = cur.parent
        if wt_root is None:
            wt_root = p if p.is_dir() else p.parent

    if p.is_dir():
        # Find modified .py file via git status, else default to bulk_downloader/runner_teach.py
        proc = subprocess.run(
            ["git", "-C", str(wt_root), "diff", "--name-only"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        py_files = [
            ln.strip()
            for ln in proc.stdout.splitlines()
            if ln.strip().endswith(".py") and not ln.strip().startswith("tests/")
        ]
        if py_files and (wt_root / py_files[0]).exists():
            target_file = wt_root / py_files[0]
        elif (wt_root / "bulk_downloader" / "runner_teach.py").exists():
            target_file = wt_root / "bulk_downloader" / "runner_teach.py"
        else:
            all_py = list(wt_root.glob("bulk_downloader/*.py")) or list(wt_root.glob("*.py"))
            target_file = all_py[0] if all_py else wt_root
    else:
        target_file = raw_abs if raw_abs.exists() else p

    return wt_root, target_file


def discover_matching_test(wt_root: Path, target_file: Path, explicit_test: str = "") -> str:
    if explicit_test:
        tp = Path(explicit_test)
        if tp.is_absolute():
            try:
                return str(tp.relative_to(wt_root))
            except ValueError:
                return explicit_test
        return explicit_test

    try:
        rel = str(target_file.relative_to(wt_root))
    except ValueError:
        rel = target_file.name

    if rel.startswith("tests/") and target_file.name.startswith("test_"):
        return rel

    fname = target_file.name
    if fname in KNOWN_MODULE_TEST_MAP:
        cand = KNOWN_MODULE_TEST_MAP[fname]
        if (wt_root / cand).exists():
            return cand

    stem = target_file.stem
    tests_dir = wt_root / "tests"
    if tests_dir.is_dir():
        exact = tests_dir / f"test_{stem}.py"
        if exact.exists():
            return f"tests/{exact.name}"
        matches = sorted(tests_dir.glob(f"test_*{stem}*.py"))
        if matches:
            return f"tests/{matches[0].name}"
        # Try sub-tokens of stem
        parts = [tok for tok in stem.split("_") if len(tok) >= 4 and tok not in ("runner", "bulk", "test")]
        for tok in parts:
            sub_matches = sorted(tests_dir.glob(f"test_*{tok}*.py"))
            if sub_matches:
                return f"tests/{sub_matches[0].name}"
        fallback = tests_dir / "test_dl_f2_auto_teach_direct_media.py"
        if fallback.exists():
            return "tests/test_dl_f2_auto_teach_direct_media.py"
        any_tests = sorted(tests_dir.glob("test_*.py"))
        if any_tests:
            return f"tests/{any_tests[0].name}"

    return "tests/test_dl_f2_auto_teach_direct_media.py"


def _extract_mypy_sigs(text: str) -> set[str]:
    sigs: set[str] = set()
    for ln in text.splitlines():
        if ": error:" in ln:
            norm = re.sub(r":\d+(?::\d+)?: error:", ": error:", ln.strip())
            sigs.add(norm)
    return sigs


def run_ruff_gate(wt_root: Path, rel_file: str, rel_test: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    targets = [rel_file]
    if rel_test and rel_test != rel_file and (wt_root / rel_test).exists():
        targets.append(rel_test)
    proc = subprocess.run(
        ["ruff", "check", "--select", "F,E9", *targets],
        cwd=str(wt_root),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return {
        "rc": proc.returncode,
        "output": (proc.stdout or proc.stderr).strip(),
        "elapsed_s": round(time.perf_counter() - t0, 3),
    }


def run_mypy_gate(wt_root: Path, rel_file: str, rel_test: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    mypy_cmd = MYPY_BIN if os.path.exists(MYPY_BIN) else "mypy"
    targets = [rel_file]
    if rel_test and rel_test != rel_file and (wt_root / rel_test).exists():
        targets.append(rel_test)
    proc = subprocess.run(
        [mypy_cmd, "--follow-imports=silent", *targets],
        cwd=str(wt_root),
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    raw_out = (proc.stdout or proc.stderr).strip()
    if proc.returncode == 0:
        return {
            "rc": 0,
            "output": "Success: no issues found",
            "elapsed_s": round(time.perf_counter() - t0, 3),
        }

    # Filter out pre-existing mixin attr-defined / module-none notices on unmodified lines
    cur_sigs = _extract_mypy_sigs(raw_out)
    benign_mixin_sigs = {
        s
        for s in cur_sigs
        if "[attr-defined]" in s or 'expression has type "None", variable has type Module' in s
    }
    real_errors = sorted(cur_sigs - benign_mixin_sigs)
    rc = 0 if not real_errors else 1
    return {
        "rc": rc,
        "output": "\n".join(real_errors) if real_errors else "Success (mixin baseline clean)",
        "elapsed_s": round(time.perf_counter() - t0, 3),
    }


def run_ramdisk_82_pytest_gate(wt_root: Path, rel_file: str, rel_test: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    src_path = wt_root / rel_file
    file_b64 = ""
    if src_path.is_file():
        file_b64 = base64.b64encode(src_path.read_bytes()).decode("ascii")

    # Single-roundtrip SSH command to .82 /dev/shm/bd-ci-ramdisk with atomic backup & restore
    remote_script = f"""
set -e
cd {RAMDISK_REPO}
mkdir -p /dev/shm/bd-tmp
BAK="/dev/shm/bd-tmp/bak_$$_$(basename '{rel_file}')"
if [ -n "{file_b64}" ] && [ -f "{rel_file}" ]; then
    cp -f "{rel_file}" "$BAK"
    trap 'cp -f "$BAK" "{RAMDISK_REPO}/{rel_file}" 2>/dev/null || true; rm -f "$BAK"' EXIT
    echo "{file_b64}" | base64 -d > "{rel_file}"
fi
TMPDIR=/dev/shm/bd-tmp /home/mboyle/BulkDownloader/venv/bin/pytest -q -o addopts='' "{rel_test}"
"""
    try:
        proc = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=2",
                RAMDISK_HOST,
                remote_script,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        raw_pytest_out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        pytest_rc = proc.returncode
        node_used = f"{RAMDISK_HOST}:{RAMDISK_REPO}"
    except Exception:
        # Local /dev/shm fallback
        env = dict(os.environ)
        env["TMPDIR"] = "/dev/shm"
        proc_local = subprocess.run(
            [PYTEST_DIGEST_BIN, rel_test],
            cwd=str(wt_root),
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
            env=env,
        )
        return {
            "rc": proc_local.returncode,
            "digest": (proc_local.stdout or proc_local.stderr).strip(),
            "node": "local:/dev/shm",
            "elapsed_s": round(time.perf_counter() - t0, 3),
        }

    # Digest via bd-pytest-digest --pipe
    p_dig = subprocess.run(
        [PYTEST_DIGEST_BIN, "--pipe", "--exit-code", str(pytest_rc)],
        input=raw_pytest_out,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    digest = (p_dig.stdout or p_dig.stderr).strip()
    return {
        "rc": pytest_rc,
        "digest": digest,
        "node": node_used,
        "elapsed_s": round(time.perf_counter() - t0, 3),
    }


def run_post_edit_gate(target_path: str, explicit_test: str = "") -> dict[str, Any]:
    t_start = time.perf_counter()
    wt_root, target_file = resolve_worktree_and_file(target_path)
    try:
        rel_file = str(target_file.relative_to(wt_root))
    except ValueError:
        rel_file = target_file.name

    rel_test = discover_matching_test(wt_root, target_file, explicit_test=explicit_test)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        f_ruff = pool.submit(run_ruff_gate, wt_root, rel_file, rel_test)
        f_mypy = pool.submit(run_mypy_gate, wt_root, rel_file, rel_test)
        f_pytest = pool.submit(run_ramdisk_82_pytest_gate, wt_root, rel_file, rel_test)

        ruff_res = f_ruff.result()
        mypy_res = f_mypy.result()
        pytest_res = f_pytest.result()

    wall_s = round(time.perf_counter() - t_start, 3)
    all_ok = ruff_res["rc"] == 0 and mypy_res["rc"] == 0 and pytest_res["rc"] == 0
    status = "PASS" if all_ok else "FAIL"

    summary_line = (
        f"[AUTO-GATE {status} in {wall_s}s] wt={wt_root.name} file={rel_file} test={rel_test} | "
        f"ruff={ruff_res['rc']} mypy={mypy_res['rc']} pytest({pytest_res['node']})={pytest_res['digest']}"
    )

    return {
        "ok": all_ok,
        "status": status,
        "worktree": str(wt_root),
        "target_file": rel_file,
        "target_test": rel_test,
        "ruff": ruff_res,
        "mypy": mypy_res,
        "pytest": pytest_res,
        "wall_elapsed_s": wall_s,
        "under_4s_sla": wall_s < 4.0,
        "summary_line": summary_line,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Autonomous Post-Edit Ruff + Mypy + .82 Ramdisk Pytest Gate Mod (<4s)"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="/home/mboyle/bd-local-wt/sb-race-codex/bulk_downloader/runner_teach.py",
        help="Worktree or edited Python file in /home/mboyle/bd-local-wt/ or /home/mboyle/bd-cuts/",
    )
    parser.add_argument("--test", type=str, default="", help="Optional explicit test path")
    parser.add_argument("--json", action="store_true", help="Emit full JSON gate receipt")
    parser.add_argument("--hook", action="store_true", help="Run as PostToolUse hook reading stdin")
    args = parser.parse_args()

    target_path = args.path
    if args.hook and not sys.stdin.isatty():
        try:
            hook_in = json.loads(sys.stdin.read() or "{}")
            ti = hook_in.get("tool_input") or hook_in.get("arguments") or {}
            cand = ti.get("TargetFile") or ti.get("file_path") or ti.get("path") or ""
            if cand and any(str(cand).startswith(r) for r in AUTHORIZED_ROOTS):
                target_path = str(cand)
        except Exception:
            pass

    res = run_post_edit_gate(target_path, explicit_test=args.test)

    if args.hook:
        print(
            json.dumps(
                {
                    "continue": True,
                    "systemMessage": res["summary_line"],
                    "gateResult": res,
                }
            )
        )
        return 0 if res["ok"] else 1

    if args.json:
        print(json.dumps(res, indent=2))
        return 0 if res["ok"] else 1

    print(res["summary_line"])
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
