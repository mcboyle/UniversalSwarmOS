"""
lib/lens_manager.py - Ephemeral Lens Lifecycle Manager

Eliminates persistent 3-hour resident tmux sessions by providing strictly
on-demand lens seat execution scoped per cut/batch.

Key Architectural Invariants:
1. On-Demand Execution: Spawns lens runner only when a task is assigned.
2. Process Group Isolation: Executes in a dedicated process group (`setsid`)
   so that the entire descendant tree (bash, pytest, git, python child processes)
   shares a single PGID.
3. Two-Tier Process Termination:
   - Tier 1: Sends SIGTERM to the entire process group (-PGID).
   - Grace period: Waits up to 3.0s for graceful shutdown.
   - Tier 2: Escalates to SIGKILL to -PGID if any process remains alive.
4. Zero-Zombie Invariant:
   - Registers as PR_SET_CHILD_SUBREAPER so reparented grandchildren become
     children of the manager when their immediate parent dies.
   - Iteratively calls waitpid(-1, WNOHANG) to reap all child processes.
   - Explicitly audits `/proc/<pid>/status` for `State: Z` and verifies 0 zombies remain.
   - Audits process group via `/proc` and `ps` to verify 0 orphan processes remain.
5. Resource Teardown:
   - Cleans up scratch directories and execution artifacts.
"""

from __future__ import annotations

import ctypes
import dataclasses
import json
import logging
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

# PR_SET_CHILD_SUBREAPER constant for Linux prctl
PR_SET_CHILD_SUBREAPER = 36

logger = logging.getLogger("lens_manager")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [lens_manager] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def enable_subreaper() -> bool:
    """
    Enables PR_SET_CHILD_SUBREAPER on Linux.
    When set, orphaned grandchildren whose parent exits are reparented
    to this process instead of init (PID 1), allowing this manager to
    reap all dead descendants and eliminate zombie processes.
    """
    try:
        libc = ctypes.CDLL(None)
        rc = libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)
        return rc == 0
    except (OSError, AttributeError) as e:
        logger.debug("Failed to set PR_SET_CHILD_SUBREAPER: %s", e)
        return False


def get_process_status(pid: int) -> dict[str, Any] | None:
    """
    Reads /proc/<pid>/status and returns a dictionary with process metadata:
    name, state, ppid, pid. Returns None if process does not exist.
    """
    status_path = Path(f"/proc/{pid}/status")
    if not status_path.exists():
        return None

    info: dict[str, Any] = {"pid": pid, "exists": True}
    try:
        with open(status_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("State:"):
                    info["state"] = line.split(":", 1)[1].strip()
                elif line.startswith("PPid:"):
                    info["ppid"] = int(line.split(":", 1)[1].strip())
                elif line.startswith("Name:"):
                    info["name"] = line.split(":", 1)[1].strip()
                elif line.startswith("Tgid:"):
                    info["tgid"] = int(line.split(":", 1)[1].strip())
        return info
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


def get_process_stat(pid: int) -> dict[str, Any] | None:
    """
    Reads /proc/<pid>/stat and safely parses state, ppid, pgid, and session.
    Handles process names containing spaces and parentheses.
    """
    stat_path = Path(f"/proc/{pid}/stat")
    if not stat_path.exists():
        return None

    try:
        with open(stat_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        r_paren = content.rfind(")")
        if r_paren == -1:
            return None

        # After ')', fields are: state(0), ppid(1), pgrp(2), session(3)...
        fields = content[r_paren + 2 :].split()
        if len(fields) < 3:
            return None

        return {
            "pid": pid,
            "state": fields[0],
            "ppid": int(fields[1]),
            "pgid": int(fields[2]),
            "session": int(fields[3]) if len(fields) > 3 else None,
        }
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


def find_processes_in_pgid(pgid: int) -> list[int]:
    """
    Discovers all alive process IDs belonging to the specified process group ID (PGID).
    Excludes zombie/dead processes (State: Z or X).
    """
    if pgid <= 0:
        return []

    pids: list[int] = []
    proc_dir = Path("/proc")
    if proc_dir.exists():
        try:
            for entry in proc_dir.iterdir():
                if not entry.name.isdigit():
                    continue
                pid = int(entry.name)
                stat_info = get_process_stat(pid)
                if stat_info and stat_info.get("pgid") == pgid:
                    state = stat_info.get("state", "")
                    if not state.startswith(("Z", "X")):
                        pids.append(pid)
        except (FileNotFoundError, PermissionError):
            pass

    # Cross-check with ps tool
    try:
        ps_proc = subprocess.run(
            ["ps", "-o", "pid=,state=", "--no-headers", "-g", str(pgid)],
            capture_output=True,
            text=True,
            check=False,
        )
        if ps_proc.returncode == 0 and ps_proc.stdout:
            for line in ps_proc.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0].isdigit():
                    val = int(parts[0])
                    st = parts[1]
                    if not st.startswith(("Z", "X")) and val not in pids:
                        pids.append(val)
                elif len(parts) == 1 and parts[0].isdigit():
                    val = int(parts[0])
                    stat_info = get_process_stat(val)
                    if stat_info and not stat_info.get("state", "").startswith(("Z", "X")) and val not in pids:
                        pids.append(val)
    except (subprocess.SubprocessError, OSError):
        pass

    return sorted(set(pids))


def find_children_of_pid(ppid: int) -> list[int]:
    """
    Discovers all alive direct child process IDs for a given parent PID (PPID).
    Excludes zombie/dead processes (State: Z or X).
    """
    if ppid <= 0:
        return []

    pids: list[int] = []
    proc_dir = Path("/proc")
    if proc_dir.exists():
        try:
            for entry in proc_dir.iterdir():
                if not entry.name.isdigit():
                    continue
                pid = int(entry.name)
                if pid == ppid:
                    continue
                status_info = get_process_status(pid)
                if status_info and status_info.get("ppid") == ppid:
                    state = status_info.get("state", "")
                    if not state.startswith(("Z", "X")):
                        pids.append(pid)
            return sorted(set(pids))
        except (FileNotFoundError, PermissionError):
            pass

    # Fallback to ps tool only if /proc inspection failed or unavailable
    try:
        ps_proc = subprocess.run(
            ["ps", "-o", "pid=,state=", "--no-headers", "--ppid", str(ppid)],
            capture_output=True,
            text=True,
            check=False,
        )
        if ps_proc.returncode == 0 and ps_proc.stdout:
            for line in ps_proc.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0].isdigit():
                    val = int(parts[0])
                    st = parts[1]
                    if not st.startswith(("Z", "X")) and val not in pids:
                        pids.append(val)
                elif len(parts) == 1 and parts[0].isdigit():
                    val = int(parts[0])
                    stat_info = get_process_status(val)
                    if stat_info and not stat_info.get("state", "").startswith(("Z", "X")) and val not in pids:
                        pids.append(val)
    except (subprocess.SubprocessError, OSError):
        pass

    return sorted(set(pids))


def audit_zombies(
    pgid: int | None = None,
    ppid: int | None = None,
) -> list[dict[str, Any]]:
    """
    Audits /proc for zombie processes (State: Z).
    Optionally filters by parent PID (ppid) or process group ID (pgid).
    Returns a list of dicts describing detected zombies.
    """
    zombies: list[dict[str, Any]] = []
    proc_dir = Path("/proc")
    if not proc_dir.exists():
        return zombies

    try:
        for entry in proc_dir.iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            status_info = get_process_status(pid)
            if not status_info:
                continue

            state = status_info.get("state", "")
            if state.startswith("Z"):
                parent_pid = status_info.get("ppid")
                if ppid is not None and parent_pid != ppid:
                    continue

                stat_info = get_process_stat(pid)
                proc_pgid = stat_info.get("pgid") if stat_info else None
                if pgid is not None and proc_pgid != pgid:
                    continue

                zombies.append(
                    {
                        "pid": pid,
                        "ppid": parent_pid,
                        "pgid": proc_pgid,
                        "name": status_info.get("name", "<unknown>"),
                        "state": state,
                    }
                )
    except (FileNotFoundError, PermissionError):
        pass

    return zombies


def audit_process_tree(pgid: int, ppid: int | None = None) -> dict[str, Any]:
    """
    Comprehensive audit for process group termination:
    - Verifies 0 orphan processes remain alive in pgid or reparented to ppid.
    - Verifies 0 zombie processes remain in pgid or for ppid.
    """
    active_pids = find_processes_in_pgid(pgid)
    if ppid is not None:
        for cpid in find_children_of_pid(ppid):
            if cpid not in active_pids:
                active_pids.append(cpid)
    active_pids = sorted(set(active_pids))

    zombies_map: dict[int, dict[str, Any]] = {}
    if pgid > 0:
        for z in audit_zombies(pgid=pgid):
            zombies_map[z["pid"]] = z
    if ppid is not None:
        for z in audit_zombies(ppid=ppid):
            zombies_map[z["pid"]] = z
    zombies = list(zombies_map.values())

    return {
        "pgid": pgid,
        "active_pids": active_pids,
        "active_count": len(active_pids),
        "zombies": zombies,
        "zombie_count": len(zombies),
        "clean": (len(active_pids) == 0 and len(zombies) == 0),
    }


def reap_all_children() -> list[int]:
    """
    Reaps all terminated child processes via waitpid(-1, os.WNOHANG).
    Returns list of reaped process IDs.
    """
    reaped: list[int] = []
    while True:
        try:
            rpid, _ = os.waitpid(-1, os.WNOHANG)
            if rpid <= 0:
                break
            reaped.append(rpid)
        except ChildProcessError:
            break
        except OSError:
            break
    return reaped


def kill_process_group(
    pgid: int,
    grace_period: float = 3.0,
    poll_interval: float = 0.05,
    custom_logger: logging.Logger | None = None,
    ppid: int | None = None,
) -> dict[str, Any]:
    """
    Two-Tier Process Termination:
    1. Sends SIGTERM to the entire process group (`kill -TERM -<PGID>`) and reparented children.
    2. Waits for up to grace_period (polling every poll_interval).
    3. If any process in the process group is still alive, escalates to SIGKILL.
    4. Reaps all reparented children.
    """
    log = custom_logger or logger
    result: dict[str, Any] = {
        "pgid": pgid,
        "sigterm_sent": False,
        "sigkill_sent": False,
        "grace_period_expired": False,
        "surviving_pids_before_kill": [],
        "reaped_pids": [],
    }

    if pgid <= 1 and ppid is None:
        log.warning("Invalid pgid %d supplied to kill_process_group; skipping.", pgid)
        return result

    def _get_alive() -> list[int]:
        p = find_processes_in_pgid(pgid) if pgid > 1 else []
        if ppid is not None:
            for cpid in find_children_of_pid(ppid):
                if cpid not in p:
                    p.append(cpid)
        return sorted(set(p))

    def _signal_pid_or_pgid(p: int, sig: signal.Signals) -> None:
        child_stat = get_process_stat(p)
        c_pgid = child_stat.get("pgid") if child_stat else None
        if c_pgid and c_pgid > 1 and c_pgid != os.getpgrp() and c_pgid != os.getpid():
            try:
                os.killpg(c_pgid, sig)
            except (ProcessLookupError, PermissionError):
                pass
        try:
            os.kill(p, sig)
        except (ProcessLookupError, PermissionError):
            pass

    alive = _get_alive()
    if not alive:
        result["reaped_pids"] = reap_all_children()
        return result

    # Tier 1: Send SIGTERM to pgid and reparented children
    if pgid > 1:
        try:
            os.killpg(pgid, signal.SIGTERM)
            result["sigterm_sent"] = True
            log.info("Sent SIGTERM to process group %d", pgid)
        except ProcessLookupError:
            pass
        except PermissionError as e:
            log.error("Permission denied sending SIGTERM to pgid %d: %s", pgid, e)

    if ppid is not None:
        for cpid in find_children_of_pid(ppid):
            _signal_pid_or_pgid(cpid, signal.SIGTERM)
            result["sigterm_sent"] = True

    # Poll during grace period
    start_time = time.time()
    while (time.time() - start_time) < grace_period:
        reap_all_children()
        alive = _get_alive()
        if not alive:
            log.info("Process group %d cleanly terminated under SIGTERM", pgid)
            result["reaped_pids"] = reap_all_children()
            return result
        if ppid is not None:
            for cpid in find_children_of_pid(ppid):
                _signal_pid_or_pgid(cpid, signal.SIGTERM)
        time.sleep(poll_interval)

    # Tier 2: Escalate to SIGKILL if processes survived
    alive = _get_alive()
    if alive:
        result["grace_period_expired"] = True
        result["surviving_pids_before_kill"] = alive
        log.warning(
            "Process group %d / ppid %s still active after %.1fs grace; escalating to SIGKILL. Surviving PIDs: %s",
            pgid,
            ppid,
            grace_period,
            alive,
        )
        if pgid > 1:
            try:
                os.killpg(pgid, signal.SIGKILL)
                result["sigkill_sent"] = True
            except ProcessLookupError:
                pass
            except PermissionError as e:
                log.error("Permission denied sending SIGKILL to pgid %d: %s", pgid, e)

        if ppid is not None:
            for cpid in find_children_of_pid(ppid):
                _signal_pid_or_pgid(cpid, signal.SIGKILL)
                result["sigkill_sent"] = True

        # Brief settle time for kernel to dispatch SIGKILL
        time.sleep(0.1)

    result["reaped_pids"] = reap_all_children()
    return result


@dataclasses.dataclass
class ExecutionReceipt:
    status: str
    seat: str
    batch_id: str | None = None
    cut: str | None = None
    role: str | None = None
    pid: int | None = None
    pgid: int | None = None
    exit_code: int | None = None
    timed_out: bool = False
    duration_seconds: float = 0.0
    verdict: str | None = None
    verdict_file: str | None = None
    zombies_detected: int = 0
    orphans_detected: int = 0
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "status": self.status,
            "seat": self.seat,
            "duration_seconds": round(self.duration_seconds, 3),
            "zombies_detected": self.zombies_detected,
            "orphans_detected": self.orphans_detected,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
        }
        if self.batch_id is not None:
            data["batch_id"] = self.batch_id
        if self.cut is not None:
            data["cut"] = self.cut
        if self.role is not None:
            data["role"] = self.role
        if self.pid is not None:
            data["pid"] = self.pid
        if self.pgid is not None:
            data["pgid"] = self.pgid
        if self.verdict is not None:
            data["verdict"] = self.verdict
        if self.verdict_file is not None:
            data["verdict_file"] = self.verdict_file
        if self.stdout:
            data["stdout"] = self.stdout
        if self.stderr:
            data["stderr"] = self.stderr
        return data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class LensManager:
    """
    Manages the lifecycle of an on-demand Ephemeral Lens session.
    """

    def __init__(
        self,
        seat: str | None = None,
        task_cmd: str | list[str] | None = None,
        timeout: float = 600.0,
        grace_period: float = 3.0,
        workdir: str | None = None,
        cut: str | None = None,
        batch_id: str | None = None,
        role: str | None = None,
        pool: str | None = None,
        is_mock: bool = False,
        clean_workdir: bool = False,
        capture_output: bool = True,
    ) -> None:
        self.batch_id = batch_id
        self.cut = cut
        self.role = role or "review-correctness"
        self.pool = pool
        self.is_mock = is_mock
        self.timeout = float(timeout)
        self.grace_period = float(grace_period)
        self.clean_workdir = clean_workdir
        self.capture_output = capture_output

        # Generate seat name if not provided
        self.seat = seat or f"ephemeral-lens-{self.batch_id or 'adhoc'}-{os.getpid()}"

        # Workdir setup
        self._created_temp_workdir = False
        if workdir:
            self.workdir = str(Path(workdir).resolve())
        elif clean_workdir:
            self.workdir = tempfile.mkdtemp(prefix=f"lens_{self.seat}_")
            self._created_temp_workdir = True
        else:
            self.workdir = os.getcwd()

        self.task_cmd = task_cmd
        self.proc: subprocess.Popen | None = None
        self.pid: int | None = None
        self.pgid: int | None = None
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.timed_out: bool = False
        self.stdout_data: str = ""
        self.stderr_data: str = ""
        self._stdout_file: Any = None
        self._stderr_file: Any = None

    def _build_command(self) -> str | list[str]:
        """
        Builds the task command. If --mock is enabled and no task_cmd is specified,
        generates an internal mock lens verification command.
        """
        if self.task_cmd:
            return self.task_cmd

        if self.is_mock:
            # Deterministic mock lens implementation
            cut_arg = self.cut or self.workdir
            role_arg = self.role
            clean_role = role_arg.removeprefix("review-")
            batch_arg = self.batch_id or "batch-mock"

            # Mock script creates verdict file and exits 0 cleanly
            mock_py = (
                "import os, sys\n"
                f"cut_path = r'{cut_arg}'\n"
                f"role = r'{role_arg}'\n"
                f"clean_role = r'{clean_role}'\n"
                f"batch = r'{batch_arg}'\n"
                "review_dir = os.path.join(cut_path, '.review')\n"
                "os.makedirs(review_dir, exist_ok=True)\n"
                "content = f'# REVIEW VERDICT: BOARD\\nRole: {role}\\nBatch: {batch}\\nVerdict: BOARD\\nStatus: PASS\\n'\n"
                "f1 = os.path.join(review_dir, f'VERDICT-{role}.md')\n"
                "f2 = os.path.join(review_dir, f'VERDICT-{clean_role}.md')\n"
                "with open(f1, 'w', encoding='utf-8') as f:\n"
                "    f.write(content)\n"
                "if f1 != f2:\n"
                "    with open(f2, 'w', encoding='utf-8') as f:\n"
                "        f.write(content)\n"
                "print(f'[MOCK_LENS] Generated verdict at {f2}')\n"
                "sys.exit(0)\n"
            )
            return ["python3", "-c", mock_py]

        raise ValueError("Either task_cmd or --mock must be specified")

    def spawn(self) -> subprocess.Popen:
        """
        Spawns the seat task in an isolated process group (via start_new_session=True / setsid).
        """
        enable_subreaper()
        cmd = self._build_command()
        use_shell = isinstance(cmd, str)

        logger.info(
            "Spawning seat '%s' in isolated process group (workdir: %s)",
            self.seat,
            self.workdir,
        )
        self.start_time = time.time()

        if self.capture_output:
            self._stdout_file = tempfile.TemporaryFile(mode="w+b")  # noqa: SIM115
            self._stderr_file = tempfile.TemporaryFile(mode="w+b")  # noqa: SIM115
            stdout_dest = self._stdout_file
            stderr_dest = self._stderr_file
        else:
            self._stdout_file = None
            self._stderr_file = None
            stdout_dest = None
            stderr_dest = None

        self.proc = subprocess.Popen(
            cmd,
            shell=use_shell,
            cwd=self.workdir,
            stdout=stdout_dest,
            stderr=stderr_dest,
            start_new_session=True,  # Creates new session and process group (setsid)
        )

        self.pid = self.proc.pid
        self.pgid = os.getpgid(self.pid)
        logger.info(
            "Seat '%s' running with PID=%d, PGID=%d", self.seat, self.pid, self.pgid
        )
        return self.proc

    def monitor(self, poll_interval: float = 0.05) -> int | None:
        """
        Monitors execution until process exits, verdict file is produced, or timeout expires.
        """
        if not self.proc:
            raise RuntimeError("Cannot monitor: process not spawned")

        deadline = (self.start_time or time.time()) + self.timeout

        while True:
            # Check if process has terminated
            ret = self.proc.poll()
            if ret is not None:
                logger.info("Seat process PID=%d exited with rc=%d", self.pid, ret)
                return ret

            # Check if timeout exceeded
            now = time.time()
            if now >= deadline:
                logger.warning(
                    "Seat '%s' (PID=%d, PGID=%d) exceeded timeout of %.1fs; marking for termination",
                    self.seat,
                    self.pid,
                    self.pgid,
                    self.timeout,
                )
                self.timed_out = True
                return None

            time.sleep(poll_interval)

    def terminate(self, grace_period: float | None = None) -> dict[str, Any]:
        """
        Executes two-tier signal escalation and reaps all descendant processes.
        """
        gp = self.grace_period if grace_period is None else grace_period
        term_result = {"pgid": self.pgid}
        if self.pgid is not None:
            term_result = kill_process_group(
                self.pgid,
                grace_period=gp,
                custom_logger=logger,
                ppid=os.getpid(),
            )

        # Collect direct child status
        if self.proc is not None:
            try:
                self.proc.wait(timeout=0.5)
            except (subprocess.TimeoutExpired, OSError) as e:
                logger.debug("Wait on child encountered: %s", e)

        # Collect output if captured
        if self.capture_output:
            if self._stdout_file is not None:
                try:
                    self._stdout_file.seek(0)
                    self.stdout_data = self._stdout_file.read().decode("utf-8", errors="replace")
                except (OSError, ValueError) as e:
                    logger.debug("Error reading stdout spool: %s", e)
                try:
                    self._stdout_file.close()
                except OSError:
                    pass
                self._stdout_file = None
            if self._stderr_file is not None:
                try:
                    self._stderr_file.seek(0)
                    self.stderr_data = self._stderr_file.read().decode("utf-8", errors="replace")
                except (OSError, ValueError) as e:
                    logger.debug("Error reading stderr spool: %s", e)
                try:
                    self._stderr_file.close()
                except OSError:
                    pass
                self._stderr_file = None

        # Reap any reparented child processes
        reap_all_children()
        return term_result

    def check_verdict(self) -> tuple[str | None, str | None]:
        """
        Checks for the presence of a verdict file in the cut directory or workdir.
        Returns (verdict_label, verdict_file_path).
        """
        target_dir = Path(self.cut) if self.cut else Path(self.workdir)
        review_dir = target_dir / ".review"
        if not review_dir.exists():
            return None, None

        clean_role = self.role.removeprefix("review-")
        candidates_to_try = [
            review_dir / f"VERDICT-{clean_role}.md",
            review_dir / f"VERDICT-{self.role}.md",
        ]
        verdict_file = None
        for cand in candidates_to_try:
            if cand.exists():
                verdict_file = cand
                break
        if verdict_file is None:
            all_cands = list(review_dir.glob("VERDICT-*.md"))
            if all_cands:
                verdict_file = all_cands[0]
            else:
                return None, None

        try:
            with open(verdict_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            verdict_label = None
            for line in content.splitlines():
                if "REVIEW VERDICT:" in line:
                    verdict_label = line.split("REVIEW VERDICT:", 1)[1].strip()
                    break
                elif "VERDICT:" in line:
                    verdict_label = line.split("VERDICT:", 1)[1].strip()
                    break
                elif line.startswith("Verdict:"):
                    verdict_label = line.split(":", 1)[1].strip()
                    break
            return verdict_label or "RECORDED", str(verdict_file)
        except (OSError, UnicodeDecodeError):
            return None, str(verdict_file)

    def cleanup(self) -> None:
        """
        Cleans up temporary workdir if created and requested, and closes spool files.
        """
        if self._stdout_file is not None:
            try:
                self._stdout_file.close()
            except OSError:
                pass
            self._stdout_file = None

        if self._stderr_file is not None:
            try:
                self._stderr_file.close()
            except OSError:
                pass
            self._stderr_file = None

        if self._created_temp_workdir and self.clean_workdir:
            try:
                shutil.rmtree(self.workdir, ignore_errors=True)
                logger.debug("Removed temporary workdir %s", self.workdir)
            except OSError as e:
                logger.warning("Failed to clean up workdir %s: %s", self.workdir, e)

    def run(self) -> ExecutionReceipt:
        """
        Executes the full lifecycle:
        1. Enable subreaper
        2. Spawn process group
        3. Monitor until exit or timeout
        4. Two-tier process group termination (SIGTERM -> grace -> SIGKILL)
        5. Reap all children via waitpid
        6. Zero-zombie & zero-orphan invariant audit
        7. Cleanup and construct ExecutionReceipt
        """
        enable_subreaper()
        self.spawn()
        self.monitor()
        self.end_time = time.time()
        duration = self.end_time - (self.start_time or self.end_time)

        # Always execute process group teardown to ensure nested background children are terminated
        self.terminate()

        # Reap any remaining processes
        reap_all_children()

        # Audit process group and parent for zero-zombie and zero-orphan invariants
        audit = audit_process_tree(self.pgid or 0, ppid=os.getpid())
        if audit["zombie_count"] > 0:
            # Re-reap once more in case of race
            time.sleep(0.05)
            reap_all_children()
            audit = audit_process_tree(self.pgid or 0, ppid=os.getpid())

        # Determine exit code and status
        exit_code: int | None
        if self.timed_out:
            status = "TIMEOUT"
            exit_code = 124  # Standard Linux timeout exit code
        elif self.proc and self.proc.returncode is not None:
            exit_code = self.proc.returncode
            status = "SUCCESS" if exit_code == 0 else "FAILED"
        else:
            exit_code = 1
            status = "TERMINATED"

        verdict_label, verdict_file = self.check_verdict()
        self.cleanup()

        receipt = ExecutionReceipt(
            status=status,
            seat=self.seat,
            batch_id=self.batch_id,
            cut=self.cut,
            role=self.role,
            pid=self.pid,
            pgid=self.pgid,
            exit_code=exit_code,
            timed_out=self.timed_out,
            duration_seconds=duration,
            verdict=verdict_label,
            verdict_file=verdict_file,
            zombies_detected=audit["zombie_count"],
            orphans_detected=audit["active_count"],
            stdout=self.stdout_data,
            stderr=self.stderr_data,
        )

        logger.info(
            "Seat '%s' finished: status=%s, rc=%s, zombies=%d, orphans=%d, duration=%.2fs",
            self.seat,
            status,
            exit_code,
            receipt.zombies_detected,
            receipt.orphans_detected,
            duration,
        )
        return receipt
