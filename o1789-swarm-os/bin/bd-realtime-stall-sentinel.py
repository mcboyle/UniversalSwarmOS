#!/usr/bin/env python3
"""bd-realtime-stall-sentinel.py -- Realtime Event-Driven Stall & Deadlock Sentinel.

Replaces 5-minute cron latency with an in-memory, deterministic, zero-LLM polling
sentinel. Monitors tmux pane activity, tool execution durations, unhandled modal dialogs,
content filter / safety halts, provider usage limits, held claims, and unread inboxes.

Objectives (Fleet Rule 60, Rule 81, O1911, O2771):
1. Sub-minute / realtime detection (default 5s loop) instead of 5-10m cron blind windows.
2. In-memory state tracking: per-seat pane hashes, tool run duration, modal/error states.
3. Immediate localized nudges (bd-say) and atomic PM notes (inbox/PM/) on unhandled modals,
   content filters, tool hangs, or silent claim stalls past STALL_MIN.
4. Zero LLM polling: 100% deterministic telemetry from tmux, /proc, and filesystem.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import enum
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# ---- REGEX PATTERNS ----
RE_WORKING = re.compile(
    r"(?i)(esc to interrupt|working \(|\bthinking\b|\bcomposing\b|[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏])"
)

RE_MODAL_CONFIRM = re.compile(
    r"(\(y/n\)|\(yes/no\)|\b[Yy]/[Nn]\b|\[y/N\]|\[Y/n\]|"
    r"do you want to (proceed|continue|run)|ready to submit your answers|"
    r"press enter to (confirm|continue)|esc to cancel|tab to amend|"
    r"allow this tool\?|enter to select)",
    re.IGNORECASE,
)

RE_MODAL_MENU = re.compile(
    r"^[ \t]*[>❯][ \t]*\d+\.[ \t]+",
    re.MULTILINE,
)

RE_CONTENT_FILTER = re.compile(
    r"(?i)(content[ _-]?filter|blocked by (safety|content) filters?|"
    r"content policy violation|request was blocked|prompt blocked|output blocked|"
    r"overloaded_error|API error: 400|model is overloaded)"
)

RE_PROVIDER_LIMIT = re.compile(
    r"(?i)(purchase extra usage|reached your [0-9a-z-]* *usage limit|"
    r"usage limit reached|hit your limit|exceeded your current quota)"
)

RE_PROMPT_IDLE = re.compile(
    r"^[│|]?[ \t]*(❯|›|>)[ \t]*$",
    re.MULTILINE,
)

# Standard ignored session prefixes or exact names
DEFAULT_EXCLUDED_SEATS = {"AGY-council", "0"}
DEFAULT_EXCLUDED_PREFIXES = ("bd-usage-", "bd-triage-", "bd-status")


class SeatState(str, enum.Enum):
    IDLE_NOMINAL = "IDLE_NOMINAL"
    IDLE_STALLED = "IDLE_STALLED"
    WORKING = "WORKING"
    TOOL_STALLED = "TOOL_STALLED"
    MODAL_BLOCKED = "MODAL_BLOCKED"
    CONTENT_FILTER = "CONTENT_FILTER"
    PROVIDER_LIMIT = "PROVIDER_LIMIT"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"


@dataclasses.dataclass
class SeatSnapshot:
    seat: str
    pane_text: str
    pane_hash: str
    is_working: bool
    is_modal: bool
    is_content_filter: bool
    is_provider_limit: bool
    is_idle_prompt: bool


@dataclasses.dataclass
class SeatMemory:
    seat: str
    last_hash: str = ""
    last_change_time: float = 0.0
    current_state: SeatState = SeatState.UNKNOWN
    state_entered_time: float = 0.0
    tool_start_time: float | None = None
    tool_hash: str | None = None
    nudges_count: int = 0
    nudge_failed_count: int = 0
    last_nudge_time: float = 0.0
    last_escalated_time: float = 0.0
    last_limit_escalated_time: float = 0.0
    last_modal_alert_time: float = 0.0
    last_filter_alert_time: float = 0.0


@dataclasses.dataclass
class ReviewClaim:
    seat: str
    object_name: str
    cut_path: str
    claimed_at: str
    epoch: float
    lens: str


@dataclasses.dataclass
class FileClaim:
    seat: str
    claim_id: str
    claim_file: Path
    claimed_at: str
    epoch: float


@dataclasses.dataclass
class SentinelConfig:
    persist_root: Path = Path("/home/mboyle/bd-persist")
    stall_min: int = 10
    nudge_min: int = 15
    max_nudges: int = 2
    tool_timeout_s: int = 300
    modal_timeout_s: int = 60
    poll_interval_s: float = 5.0
    say_sh: Path = Path("/home/mboyle/bd-say.sh")
    tmux_bin: str = "tmux"
    status_json: Path = Path("/home/mboyle/bd-persist/state/stall_sentinel_live.json")
    log_file: Path = Path("/home/mboyle/bd-persist/logs/stall-sentinel.log")
    cut_roots: list[Path] = dataclasses.field(
        default_factory=lambda: [
            Path("/home/mboyle/bd-cuts/cut"),
            Path("/home/mboyle/bd-local-wt"),
            Path("/home/mboyle/bd-persist/harness-work/BURN/cuts"),
        ]
    )
    claim_lanes: dict[str, str] = dataclasses.field(
        default_factory=lambda: {"appfeat": "APPFEAT-fix"}
    )
    dry_run: bool = False


class StallSentinel:
    def __init__(self, config: SentinelConfig):
        self.config = config
        self.memory: dict[str, SeatMemory] = {}
        self.running = True
        self.log_file = config.log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.status_json.parent.mkdir(parents=True, exist_ok=True)

    def log(self, msg: str) -> None:
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{ts} {msg}\n"
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass
        if not self.config.dry_run and os.isatty(sys.stdout.fileno()):
            sys.stdout.write(line)
            sys.stdout.flush()

    def pm_note(self, tag: str, content: str) -> bool:
        """Write atomic note to inbox/PM/ using dot-temp-and-rename invariant."""
        if self.config.dry_run:
            self.log(f"DRY would-pm-note tag={tag} content={content.strip()[:80]}")
            return True

        pm_inbox = self.config.persist_root / "inbox" / "PM"
        pm_inbox.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target_name = f"{ts}-{tag}.md"
        target_path = pm_inbox / target_name
        tmp_path = (
            pm_inbox
            / f".{target_name}.tmp.{os.getpid()}.{int(time.time() * 1000) % 100000}"
        )

        try:
            tmp_path.write_text(content, encoding="utf-8")
            tmp_path.replace(target_path)
            return True
        except OSError as e:
            self.log(f"COULD-NOT-WRITE {target_path}: {e}")
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            return False

    def send_nudge(self, seat: str, message: str) -> int:
        """Deliver localized nudge via bd-say.sh."""
        if self.config.dry_run:
            self.log(f"DRY would-nudge seat={seat} msg={message[:80]}")
            return 0

        say_path = str(self.config.say_sh)
        if not os.path.exists(say_path) or not os.access(say_path, os.X_OK):
            self.log(f"COULD-NOT-EXEC say_sh={say_path}")
            return 127

        env = os.environ.copy()
        env["BD_SEAT"] = "sentinel:bd-realtime-stall-sentinel"
        try:
            res = subprocess.run(
                [say_path, seat, message],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            return res.returncode
        except (subprocess.SubprocessError, OSError) as e:
            self.log(f"NUDGE-EXEC-ERROR {seat}: {e}")
            return -1

    def list_tmux_sessions(self) -> list[str]:
        """List active tmux sessions matching seat criteria."""
        try:
            res = subprocess.run(
                [self.config.tmux_bin, "ls", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode != 0:
                return []
            sessions = []
            pm_seat = self.get_pm_seat()
            for line in res.stdout.splitlines():
                s = line.strip()
                if not s:
                    continue
                if s == pm_seat or s in DEFAULT_EXCLUDED_SEATS:
                    continue
                if any(s.startswith(p) for p in DEFAULT_EXCLUDED_PREFIXES):
                    continue
                # Match seats starting with bd- or custom test seats
                if s.startswith(("bd-", "test-seat-")):
                    sessions.append(s)
            return sorted(sessions)
        except (subprocess.SubprocessError, OSError):
            return []

    def get_pm_seat(self) -> str:
        pm_file = self.config.persist_root / "PM-SEAT"
        if pm_file.exists():
            try:
                for line in pm_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line
            except OSError:
                pass
        return "AGY-council"

    def capture_pane(self, seat: str, lines: int = 50) -> SeatSnapshot | None:
        """Capture tail lines of pane and parse diagnostic signals."""
        try:
            res = subprocess.run(
                [
                    self.config.tmux_bin,
                    "capture-pane",
                    "-p",
                    "-t",
                    f"{seat}:",
                    "-S",
                    f"-{lines}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode != 0:
                return None
            pane_text = res.stdout
            pane_hash = hashlib.md5(pane_text.encode("utf-8")).hexdigest()[:16]

            # Analyze tail 25 lines
            tail_lines = "\n".join(pane_text.splitlines()[-25:])
            is_working = bool(RE_WORKING.search(tail_lines))
            is_modal = bool(
                RE_MODAL_CONFIRM.search(tail_lines) or RE_MODAL_MENU.search(tail_lines)
            )
            is_content_filter = bool(RE_CONTENT_FILTER.search(tail_lines))
            is_provider_limit = bool(RE_PROVIDER_LIMIT.search(tail_lines))
            is_idle = bool(RE_PROMPT_IDLE.search(tail_lines))

            return SeatSnapshot(
                seat=seat,
                pane_text=pane_text,
                pane_hash=pane_hash,
                is_working=is_working,
                is_modal=is_modal,
                is_content_filter=is_content_filter,
                is_provider_limit=is_provider_limit,
                is_idle_prompt=is_idle,
            )
        except (subprocess.SubprocessError, OSError):
            return None

    def get_active_review_claims(self) -> dict[str, list[ReviewClaim]]:
        """Parse active review claims from review-claims.tsv.
        Last state per object+lens is CLAIM -> active; RELEASE / RELEASED -> cleared.
        """
        review_file = self.config.persist_root / "review-claims.tsv"
        if not review_file.exists():
            return {}

        active: dict[tuple[str, str], ReviewClaim] = {}
        try:
            with open(review_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) < 4:
                        continue
                    action = parts[0].strip()
                    cut_path = parts[1].strip()
                    lens = parts[2].strip()
                    seat = parts[3].strip()
                    claimed_at = parts[4].strip() if len(parts) >= 5 else ""

                    obj_name = cut_path.rstrip("/").split("/")[-1] if cut_path else ""
                    key = (obj_name, lens)

                    if action == "CLAIM":
                        epoch = 0.0
                        if claimed_at:
                            try:
                                dt = datetime.datetime.fromisoformat(
                                    claimed_at.replace("Z", "+00:00")
                                )
                                epoch = dt.timestamp()
                            except ValueError:
                                epoch = time.time()
                        else:
                            epoch = time.time()

                        active[key] = ReviewClaim(
                            seat=seat,
                            object_name=obj_name,
                            cut_path=cut_path,
                            claimed_at=claimed_at,
                            epoch=epoch,
                            lens=lens,
                        )
                    elif action in ("RELEASE", "RELEASED"):
                        active.pop(key, None)
        except OSError:
            return {}

        by_seat: dict[str, list[ReviewClaim]] = {}
        for claim in active.values():
            by_seat.setdefault(claim.seat, []).append(claim)
        return by_seat

    def get_active_file_claims(self) -> dict[str, list[FileClaim]]:
        """Parse active claims from claims/*.claim."""
        claims_dir = self.config.persist_root / "claims"
        if not claims_dir.exists():
            return {}

        by_seat: dict[str, list[FileClaim]] = {}
        try:
            for entry in claims_dir.glob("*.claim"):
                if not entry.is_file():
                    continue
                try:
                    line = (
                        entry.read_text(encoding="utf-8", errors="replace")
                        .splitlines()[0]
                        .strip()
                    )
                    parts = line.split()
                    if not parts:
                        continue
                    seat = parts[0]
                    claimed_at = parts[1] if len(parts) > 1 else ""
                    mtime = entry.stat().st_mtime
                    claim_id = entry.stem
                    claim = FileClaim(
                        seat=seat,
                        claim_id=claim_id,
                        claim_file=entry,
                        claimed_at=claimed_at,
                        epoch=mtime,
                    )
                    by_seat.setdefault(seat, []).append(claim)
                except (OSError, IndexError):
                    continue
        except OSError:
            pass
        return by_seat

    def is_review_answered(
        self, seat: str, claimed_path: str, claim_epoch: float
    ) -> bool:
        """Check STALL-GUARD-1: .review/VERDICT-*.md written at/after claim names the seat."""
        if not claimed_path or not os.path.isabs(claimed_path):
            return False
        rev_dir = Path(claimed_path) / ".review"
        if not rev_dir.is_dir():
            return False

        obj_name = Path(claimed_path).name
        try:
            for v in rev_dir.glob("VERDICT-*.md"):
                if not v.is_file():
                    continue
                st = v.stat()
                if st.st_mtime < claim_epoch:
                    continue
                v_name = v.name
                if (
                    f"-{seat}-{obj_name}.md" in v_name
                    or f"-{seat}-{obj_name}-" in v_name
                ):
                    return True
                # Check header
                try:
                    head = v.read_text(encoding="utf-8", errors="replace")[:2000]
                    if re.search(
                        rf"^SEAT:[ \t]*{re.escape(seat)}([ \t;,]|$)", head, re.MULTILINE
                    ):
                        return True
                except OSError:
                    continue
        except OSError:
            pass
        return False

    def is_file_claim_answered(
        self, seat: str, claim_id: str, claim_epoch: float, claim_file: Path
    ) -> bool:
        """Check STALL-GUARD-2: DONE.md written at/after claim by seat in cut roots or claim lanes."""
        dirs_to_check: list[Path] = []
        for r in self.config.cut_roots:
            dirs_to_check.append(r / claim_id)
            dirs_to_check.append(r / f"{claim_id}-{seat}")
            for prefix, lane in self.config.claim_lanes.items():
                if claim_id.startswith(f"{prefix}-"):
                    suffix = claim_id[len(prefix) + 1 :]
                    dirs_to_check.append(r / lane / suffix)

        # Check explicit paths recorded in claim file
        try:
            head = claim_file.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()[0]
            parts = head.split()
            for p in parts[2:]:
                if os.path.isabs(p):
                    dirs_to_check.append(Path(p))
        except (OSError, IndexError):
            pass

        for d in dirs_to_check:
            done_file = d / "DONE.md"
            if not done_file.is_file():
                continue
            try:
                if done_file.stat().st_mtime < claim_epoch:
                    continue
                content = done_file.read_text(encoding="utf-8", errors="replace")[:3000]
                if re.search(
                    rf"(^|[^A-Za-z0-9_-])SEAT:[ \t]*{re.escape(seat)}([^A-Za-z0-9_-]|$)",
                    content,
                ):
                    return True
            except OSError:
                continue

        return False

    def get_unread_inbox_count(self, seat: str, since_epoch: float) -> int:
        """Count unread news in inbox/<seat>/ arrived at/after since_epoch (excluding cron pings)."""
        inbox_dir = self.config.persist_root / "inbox" / seat
        if not inbox_dir.is_dir():
            return 0

        unread = 0
        try:
            for entry in inbox_dir.iterdir():
                if entry.name.startswith("."):
                    continue
                if not entry.is_file():
                    continue
                try:
                    st = entry.stat()
                    if st.st_mtime < since_epoch:
                        continue
                    # Skip cron batches & pings
                    name = entry.name
                    if re.match(r"^BATCH-.*Z-[0-9a-fA-F]{8}\.md$", name):
                        unread += 1
                        continue
                    if name.startswith("BATCH-"):
                        continue
                    head = entry.read_text(encoding="utf-8", errors="replace")[:64]
                    if re.search(r"^\[from:?[ \t]+cron:", head):
                        continue
                    unread += 1
                except OSError:
                    continue
        except OSError:
            pass

        return unread

    def evaluate_seat(
        self,
        seat: str,
        snap: SeatSnapshot,
        mem: SeatMemory,
        now: float,
        active_review_claims: list[ReviewClaim],
        active_file_claims: list[FileClaim],
    ) -> tuple[SeatState, str, str | None]:
        """Evaluate snapshot & telemetry against stall / deadlock invariants.
        Returns: (state, diagnostic_details, action_message)
        """
        # 1. Update hash freshness
        if mem.last_hash != snap.pane_hash:
            mem.last_hash = snap.pane_hash
            mem.last_change_time = now
            mem.tool_hash = snap.pane_hash
            # If pane changed, clear failures
            mem.nudge_failed_count = 0

        quiet_s = now - mem.last_change_time
        quiet_m = quiet_s / 60.0

        # 2. Check Provider Limit
        if snap.is_provider_limit:
            return (
                SeatState.PROVIDER_LIMIT,
                f"provider limit/quota page in pane (quiet {quiet_m:.1f}m)",
                None,
            )

        # 3. Check Interactive Modal / Confirm Prompt
        if snap.is_modal:
            return (
                SeatState.MODAL_BLOCKED,
                f"unhandled modal/confirm dialog in pane (quiet {quiet_m:.1f}m)",
                None,
            )

        # 4. Check Content Filter / Safety Error
        if snap.is_content_filter and (snap.is_idle_prompt or not snap.is_working):
            return (
                SeatState.CONTENT_FILTER,
                f"content filter / API error halted pane (quiet {quiet_m:.1f}m)",
                None,
            )

        # 5. Check Working vs Hung Tool
        if snap.is_working:
            if mem.tool_start_time is None:
                mem.tool_start_time = now
                mem.tool_hash = snap.pane_hash
            tool_dur_s = now - mem.tool_start_time

            # If pane output has been completely frozen while in working state >= tool_timeout_s
            if quiet_s >= self.config.tool_timeout_s:
                return (
                    SeatState.TOOL_STALLED,
                    f"tool execution frozen {quiet_s:.0f}s >= {self.config.tool_timeout_s}s (total {tool_dur_s:.0f}s)",
                    None,
                )
            return (
                SeatState.WORKING,
                f"actively working (tool elapsed {tool_dur_s:.0f}s, quiet {quiet_s:.0f}s)",
                None,
            )
        else:
            # Not working -> reset tool timer
            mem.tool_start_time = None
            mem.tool_hash = None

        # 6. Check Active Claims & Unread Inbox
        unanswered_claims: list[str] = []
        for rc in active_review_claims:
            if not self.is_review_answered(seat, rc.cut_path, rc.epoch):
                unanswered_claims.append(f"lens:{rc.object_name}")

        for fc in active_file_claims:
            if not self.is_file_claim_answered(
                seat, fc.claim_id, fc.epoch, fc.claim_file
            ):
                unanswered_claims.append(f"claim:{fc.claim_id}")

        unread_count = self.get_unread_inbox_count(seat, mem.last_change_time)

        # If holding no claims and 0 unread inbox -> Nominal idle
        if not unanswered_claims and unread_count == 0:
            return (
                SeatState.IDLE_NOMINAL,
                f"idle nominal (quiet {quiet_m:.1f}m, 0 held claims, 0 unread)",
                None,
            )

        # Holding work but quiet < stall_min -> Waiting within threshold
        work_desc = ", ".join(unanswered_claims)
        if unread_count > 0:
            work_desc = (
                f"{work_desc}, {unread_count} unread inbox"
                if work_desc
                else f"{unread_count} unread inbox"
            )

        if quiet_m < self.config.stall_min:
            return (
                SeatState.IDLE_NOMINAL,
                f"idle with work ({work_desc}) quiet {quiet_m:.1f}m < {self.config.stall_min}m",
                None,
            )

        # Silent past stall_min while holding work -> STALLED!
        return (
            SeatState.IDLE_STALLED,
            f"silent {quiet_m:.1f}m >= {self.config.stall_min}m holding {work_desc}",
            work_desc,
        )

    def scan_once(self) -> dict[str, Any]:
        """Perform a single comprehensive pass across all seats."""
        now = time.time()
        sessions = self.list_tmux_sessions()
        all_review = self.get_active_review_claims()
        all_file_claims = self.get_active_file_claims()

        seat_statuses: dict[str, Any] = {}
        stalled_count = 0
        modal_count = 0
        filter_count = 0
        tool_hung_count = 0

        for seat in sessions:
            snap = self.capture_pane(seat)
            if snap is None:
                continue

            if seat not in self.memory:
                self.memory[seat] = SeatMemory(
                    seat=seat,
                    last_hash=snap.pane_hash,
                    last_change_time=now,
                    current_state=SeatState.UNKNOWN,
                    state_entered_time=now,
                )

            mem = self.memory[seat]
            rev_claims = all_review.get(seat, [])
            f_claims = all_file_claims.get(seat, [])

            new_state, diag, work_desc = self.evaluate_seat(
                seat, snap, mem, now, rev_claims, f_claims
            )

            if new_state != mem.current_state:
                mem.current_state = new_state
                mem.state_entered_time = now

            quiet_m = (now - mem.last_change_time) / 60.0

            # Act on State
            if new_state == SeatState.PROVIDER_LIMIT:
                if (now - mem.last_limit_escalated_time) >= 3600:
                    note = (
                        f"[from sentinel:bd-realtime-stall-sentinel] LIMIT {seat}: "
                        f"provider usage/quota page in pane; reroute its lenses. "
                        f"Look: tmux capture-pane -p -t {seat}\n"
                    )
                    if self.pm_note(f"limit-{seat}", note):
                        mem.last_limit_escalated_time = now
                        self.log(f"LIMIT {seat} escalated to PM inbox")

            elif new_state == SeatState.MODAL_BLOCKED:
                modal_count += 1
                if (now - mem.last_modal_alert_time) >= self.config.modal_timeout_s:
                    note = (
                        f"[from sentinel:bd-realtime-stall-sentinel] MODAL {seat}: "
                        f"seat is blocked on an interactive modal/confirm dialog in pane. "
                        f"Details: {diag}. Look: tmux capture-pane -p -t {seat}\n"
                    )
                    if self.pm_note(f"modal-{seat}", note):
                        mem.last_modal_alert_time = now
                        self.log(f"ALERT-MODAL {seat} escalated to PM inbox ({diag})")

            elif new_state == SeatState.CONTENT_FILTER:
                filter_count += 1
                if (now - mem.last_filter_alert_time) >= self.config.nudge_min * 60:
                    note = (
                        f"[from sentinel:bd-realtime-stall-sentinel] CONTENT-FILTER {seat}: "
                        f"turn terminated abruptly on content filter/error while holding work. "
                        f"Details: {diag}. Look: tmux capture-pane -p -t {seat}\n"
                    )
                    self.pm_note(f"filter-{seat}", note)
                    msg = (
                        "ORDER ERROR RECOVERY: pane shows content filter / API error. "
                        "Write VERDICT/DONE UNKNOWN with reason, or retry with bounded prompt."
                    )
                    rc = self.send_nudge(seat, msg)
                    mem.last_filter_alert_time = now
                    self.log(
                        f"ALERT-FILTER {seat} nudged (rc={rc}) and escalated to PM"
                    )

            elif new_state == SeatState.TOOL_STALLED:
                tool_hung_count += 1
                if (now - mem.last_nudge_time) >= self.config.nudge_min * 60:
                    msg = (
                        f"ORDER TOOL TIMEOUT: command frozen {self.config.tool_timeout_s}s with no output. "
                        f"Press esc or kill hanging child process to resume."
                    )
                    rc = self.send_nudge(seat, msg)
                    mem.last_nudge_time = now
                    self.log(f"ALERT-TOOL-HUNG {seat} nudged (rc={rc}): {diag}")

            elif new_state == SeatState.IDLE_STALLED:
                stalled_count += 1
                time_since_nudge = now - mem.last_nudge_time
                if time_since_nudge >= (self.config.nudge_min * 60):
                    if mem.nudges_count >= self.config.max_nudges:
                        # Max nudges exceeded -> Escalate to PM
                        if (now - mem.last_escalated_time) >= (
                            self.config.nudge_min * 60
                        ):
                            note = (
                                f"[from sentinel:bd-realtime-stall-sentinel] STALLED {seat}: "
                                f"quiet {quiet_m:.0f}m after {mem.nudges_count} nudges ({work_desc}). "
                                f"Look: tmux capture-pane -p -t {seat}\n"
                            )
                            if self.pm_note(f"stall-{seat}", note):
                                mem.last_escalated_time = now
                                self.log(
                                    f"ESCALATE-STALL {seat} quiet={quiet_m:.0f}m nudges={mem.nudges_count} ({work_desc})"
                                )
                    else:
                        # Send localized nudge
                        msg = (
                            f"ORDER STALL CHECK: quiet {quiet_m:.0f}m, {work_desc}. "
                            f"Resume now, or write VERDICT/DONE UNKNOWN with reason and say router."
                        )
                        rc = self.send_nudge(seat, msg)
                        if rc == 0:
                            mem.nudges_count += 1
                            mem.last_nudge_time = now
                            self.log(
                                f"NUDGE {seat} quiet={quiet_m:.0f}m n={mem.nudges_count} rc={rc} ({work_desc})"
                            )
                        else:
                            mem.nudge_failed_count += 1
                            self.log(
                                f"NUDGE-FAILED {seat} quiet={quiet_m:.0f}m rc={rc} fail_count={mem.nudge_failed_count}"
                            )

            seat_statuses[seat] = {
                "state": new_state.value,
                "diagnostic": diag,
                "quiet_seconds": round(now - mem.last_change_time, 1),
                "tool_duration_seconds": round(now - mem.tool_start_time, 1)
                if mem.tool_start_time
                else None,
                "nudges_count": mem.nudges_count,
                "last_nudge_time": mem.last_nudge_time,
            }

        # Write atomic live JSON status
        report = {
            "written_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "monitored_seats": len(sessions),
            "stalled_seats": stalled_count,
            "modal_blocked_seats": modal_count,
            "filter_blocked_seats": filter_count,
            "tool_hung_seats": tool_hung_count,
            "seats": seat_statuses,
        }

        try:
            tmp_json = self.config.status_json.with_suffix(f".tmp.{os.getpid()}")
            tmp_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
            tmp_json.replace(self.config.status_json)
        except OSError as e:
            self.log(f"COULD-NOT-WRITE-STATUS {self.config.status_json}: {e}")

        return report

    def run_daemon(self) -> None:
        """Run continuous event-driven monitoring loop."""
        self.log(
            f"START sentinel poll_interval={self.config.poll_interval_s}s stall_min={self.config.stall_min}m"
        )

        def handle_signal(sig, frame):
            self.running = False
            self.log(f"STOP received signal {sig}")

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        while self.running:
            start_t = time.time()
            try:
                self.scan_once()
            except (subprocess.SubprocessError, OSError, ValueError, KeyError, json.JSONDecodeError) as e:
                self.log(f"CYCLE-ERROR: {e}")

            elapsed = time.time() - start_t
            sleep_t = max(0.1, self.config.poll_interval_s - elapsed)
            time.sleep(sleep_t)


def run_selftest() -> int:
    """Hermetic self-test suite running against /tmp/ fixtures."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="sentinel-selftest-") as tmpdir:
        tmp_path = Path(tmpdir)
        persist = tmp_path / "bd-persist"
        persist.mkdir()
        (persist / "claims").mkdir()
        (persist / "inbox" / "PM").mkdir(parents=True)
        (persist / "state").mkdir()
        (persist / "logs").mkdir()

        # Dummy bd-say.sh
        say_sh = tmp_path / "bd-say.sh"
        say_sh.write_text(
            '#!/bin/bash\necho "$@" >> /tmp/sentinel-said.log\nexit 0\n',
            encoding="utf-8",
        )
        say_sh.chmod(0o755)

        # Config
        config = SentinelConfig(
            persist_root=persist,
            stall_min=2,  # 2 minutes for test
            nudge_min=1,
            max_nudges=2,
            tool_timeout_s=5,
            poll_interval_s=0.1,
            say_sh=say_sh,
            status_json=persist / "state" / "stall_sentinel_live.json",
            log_file=persist / "logs" / "sentinel.log",
            cut_roots=[tmp_path / "cuts"],
            dry_run=False,
        )

        sentinel = StallSentinel(config)

        # Scenario 1: Active claim holder silent past stall_min
        seat = "bd-worker-TEST1"
        claim_file = persist / "claims" / "test-cut-001.claim"
        claim_file.write_text(f"{seat} 2026-10-16T12:00:00Z\n", encoding="utf-8")

        snap_idle = SeatSnapshot(
            seat=seat,
            pane_text="some prompt\n❯ \n",
            pane_hash="hash001",
            is_working=False,
            is_modal=False,
            is_content_filter=False,
            is_provider_limit=False,
            is_idle_prompt=True,
        )

        now = time.time()
        mem = SeatMemory(
            seat=seat,
            last_hash="hash001",
            last_change_time=now - 150,  # 2.5 minutes ago (exceeds stall_min=2)
            current_state=SeatState.UNKNOWN,
            state_entered_time=now - 150,
        )
        sentinel.memory[seat] = mem

        f_claims = [
            FileClaim(
                seat=seat,
                claim_id="test-cut-001",
                claim_file=claim_file,
                claimed_at="2026-10-16T12:00:00Z",
                epoch=now - 200,
            )
        ]
        state, _, _ = sentinel.evaluate_seat(seat, snap_idle, mem, now, [], f_claims)
        assert state == SeatState.IDLE_STALLED, f"Expected IDLE_STALLED, got {state}"
        print("PASS: Scenario 1 - Active Claim Holder Silent Past STALL_MIN detected")

        # Scenario 2: Answered claim is NOT stalled
        (tmp_path / "cuts" / "test-cut-001").mkdir(parents=True)
        done_file = tmp_path / "cuts" / "test-cut-001" / "DONE.md"
        done_file.write_text(f"SEAT: {seat}\nSTATUS: PASS\n", encoding="utf-8")
        os.utime(done_file, (now, now))

        state2, _, _ = sentinel.evaluate_seat(seat, snap_idle, mem, now, [], f_claims)
        assert state2 == SeatState.IDLE_NOMINAL, f"Expected IDLE_NOMINAL, got {state2}"
        print("PASS: Scenario 2 - Answered Claim Correctly Ignored")

        # Scenario 3: Interactive Modal Prompt
        snap_modal = SeatSnapshot(
            seat=seat,
            pane_text="Command requires confirmation.\nDo you want to proceed? (y/n)\n",
            pane_hash="hash_modal",
            is_working=False,
            is_modal=True,
            is_content_filter=False,
            is_provider_limit=False,
            is_idle_prompt=False,
        )
        state3, _, _ = sentinel.evaluate_seat(seat, snap_modal, mem, now, [], [])
        assert state3 == SeatState.MODAL_BLOCKED, (
            f"Expected MODAL_BLOCKED, got {state3}"
        )
        print("PASS: Scenario 3 - Unhandled Interactive Modal detected")

        # Scenario 4: Content Filter
        snap_filter = SeatSnapshot(
            seat=seat,
            pane_text="Error: prompt blocked by safety filters.\n❯ \n",
            pane_hash="hash_filter",
            is_working=False,
            is_modal=False,
            is_content_filter=True,
            is_provider_limit=False,
            is_idle_prompt=True,
        )
        state4, _, _ = sentinel.evaluate_seat(seat, snap_filter, mem, now, [], [])
        assert state4 == SeatState.CONTENT_FILTER, (
            f"Expected CONTENT_FILTER, got {state4}"
        )
        print("PASS: Scenario 4 - Content Filter / Safety Halts detected")

        # Scenario 5: Hung Tool
        snap_tool = SeatSnapshot(
            seat=seat,
            pane_text="Working (esc to interrupt)...\n",
            pane_hash="hash_tool",
            is_working=True,
            is_modal=False,
            is_content_filter=False,
            is_provider_limit=False,
            is_idle_prompt=False,
        )
        mem_tool = SeatMemory(
            seat=seat,
            last_hash="hash_tool",
            last_change_time=now - 10,  # 10s frozen > 5s timeout
            current_state=SeatState.WORKING,
            state_entered_time=now - 20,
            tool_start_time=now - 20,
            tool_hash="hash_tool",
        )
        state5, _, _ = sentinel.evaluate_seat(seat, snap_tool, mem_tool, now, [], [])
        assert state5 == SeatState.TOOL_STALLED, f"Expected TOOL_STALLED, got {state5}"
        print("PASS: Scenario 5 - Hung Tool Frozen Past Timeout detected")

        # Scenario 6: PM Note Atomicity
        ok = sentinel.pm_note("test-note", "TEST CONTENT\n")
        assert ok, "pm_note failed"
        notes = list((persist / "inbox" / "PM").glob("*-test-note.md"))
        assert len(notes) == 1, f"Expected 1 note, found {len(notes)}"
        assert notes[0].read_text(encoding="utf-8") == "TEST CONTENT\n"
        print("PASS: Scenario 6 - Atomic PM Note Writing Verified")

    print("\nALL SELFTESTS PASSED (6/6).")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Realtime Event-Driven Stall and Deadlock Sentinel"
    )
    parser.add_argument(
        "--daemon", action="store_true", help="Run continuously in background"
    )
    parser.add_argument(
        "--once", action="store_true", help="Run single scan pass and exit"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without nudging or writing PM notes",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Loop interval in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--stall-min",
        type=int,
        default=10,
        help="Stall threshold minutes (default: 10)",
    )
    parser.add_argument(
        "--tool-timeout",
        type=int,
        default=300,
        help="Tool freeze threshold seconds (default: 300)",
    )
    parser.add_argument(
        "--modal-timeout",
        type=int,
        default=60,
        help="Modal alert cadence seconds (default: 60)",
    )
    parser.add_argument(
        "--nudge-min",
        type=int,
        default=15,
        help="Cooldown between nudges in minutes (default: 15)",
    )
    parser.add_argument(
        "--max-nudges",
        type=int,
        default=2,
        help="Max nudges before PM escalation (default: 2)",
    )
    parser.add_argument(
        "--root",
        type=str,
        default="/home/mboyle/bd-persist",
        help="bd-persist root directory",
    )
    parser.add_argument(
        "--say", type=str, default="/home/mboyle/bd-say.sh", help="Path to bd-say.sh"
    )
    parser.add_argument(
        "--status-json",
        type=str,
        default="/home/mboyle/bd-persist/state/stall_sentinel_live.json",
        help="Live status JSON path",
    )
    parser.add_argument(
        "--selftest", action="store_true", help="Run hermetic synthetic selftest"
    )

    args = parser.parse_args()

    if args.selftest:
        sys.exit(run_selftest())

    config = SentinelConfig(
        persist_root=Path(args.root),
        stall_min=args.stall_min,
        nudge_min=args.nudge_min,
        max_nudges=args.max_nudges,
        tool_timeout_s=args.tool_timeout,
        modal_timeout_s=args.modal_timeout,
        poll_interval_s=args.interval,
        say_sh=Path(args.say),
        status_json=Path(args.status_json),
        dry_run=args.dry_run,
    )

    sentinel = StallSentinel(config)

    if args.once or not args.daemon:
        report = sentinel.scan_once()
        print(json.dumps(report, indent=2))
        sys.exit(0)
    else:
        sentinel.run_daemon()


if __name__ == "__main__":
    main()
