"""Batched Relay Daemon Core Logic (Milestone 2: Features 1-8, AC2).

This module implements the durable SQLite queue, message classification,
dual flush triggers (volume and time window), escalation bypass, batch payload
consolidation into BATCH-<timestamp>.md, and terse target delivery.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import sqlite3
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("bd_batch_relay")

# Escalation tokens that bypass queueing and trigger immediate delivery
ESCALATION_REGEX = re.compile(
    r"\b(STOP|LIMIT|HIGH|BLOCKED|BLOCKER|CRASH|HANG|DOWN|OUTAGE)\b",
    re.IGNORECASE,
)


@dataclass
class QueuedMessage:
    id: int
    target: str
    sender: str
    payload: str
    priority: str
    queued_at: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchDelivery:
    batch_id: str
    target: str
    message_count: int
    batch_file_path: str
    terse_notification: str
    delivered_at: str
    message_ids: list[int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_escalation(message: str, priority: str = "normal") -> tuple[bool, str]:
    """Classify message to determine if it requires immediate escalation bypass."""
    normalized_prio = (priority or "").strip().lower()
    if normalized_prio in ("urgent", "high", "escalation", "emergency"):
        return True, f"priority={priority}"

    match = ESCALATION_REGEX.search(message or "")
    if match:
        return True, f"escalation_keyword={match.group(1).upper()}"

    return False, ""


class RelayDaemon:
    """Manages the batched relay queue, triggers, consolidation, and delivery."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        inbox_dir: str | Path | None = None,
        batch_size: int = 5,
        flush_interval: float = 120.0,
        delivery_cmd: str | None = None,
        delivery_callback: Callable[[str, str, dict[str, Any]], Any] | None = None,
    ):
        """Initialize relay daemon with storage paths and trigger thresholds."""
        default_db = os.environ.get("BD_RELAY_DB", "/home/mboyle/bd-persist/relay-queue.db")
        default_inbox = os.environ.get("BD_RELAY_INBOX", "/home/mboyle/bd-persist/inbox")

        self.db_path = Path(db_path or default_db).expanduser().resolve()
        self.inbox_dir = Path(inbox_dir or default_inbox).expanduser().resolve()
        self.batch_size = int(os.environ.get("BD_RELAY_BATCH_SIZE", batch_size))
        self.flush_interval = float(os.environ.get("BD_RELAY_FLUSH_INTERVAL", flush_interval))
        self.delivery_cmd = delivery_cmd or os.environ.get("BD_RELAY_DELIVERY_CMD")
        self.delivery_callback = delivery_callback

        self._lock = threading.Lock()
        self._ensure_storage()

    def _sanitize_target(self, target: str) -> str:
        """Sanitize target seat name to prevent directory traversal attacks."""
        cleaned = (target or "").strip()
        if not cleaned:
            raise ValueError("Target seat is required")
        name = Path(cleaned).name
        if not name or name in (".", "..") or not re.match(r"^[a-zA-Z0-9_\-]+$", name):
            raise ValueError(f"Invalid target seat identifier: {target}")
        return name

    def _get_target_inbox(self, target: str) -> Path:
        """Resolve and validate the target seat's inbox directory."""
        sanitized = self._sanitize_target(target)
        inbox_root = self.inbox_dir.resolve()
        target_dir = (inbox_root / sanitized).resolve()
        if not target_dir.is_relative_to(inbox_root) or target_dir == inbox_root:
            raise ValueError(f"Target seat directory escapes inbox root: {target}")
        return target_dir

    def _ensure_storage(self) -> None:
        """Ensure database and inbox directories exist and database schema is initialized."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

        for attempt in range(10):
            try:
                with self._get_connection() as conn:
                    conn.execute("PRAGMA busy_timeout=30000;")
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA synchronous=NORMAL;")
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            target TEXT NOT NULL,
                            sender TEXT DEFAULT 'unknown',
                            payload TEXT NOT NULL,
                            priority TEXT DEFAULT 'normal',
                            queued_at TEXT NOT NULL,
                            status TEXT DEFAULT 'pending'
                        );
                        """
                    )
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_messages_target_status
                        ON messages(target, status);
                        """
                    )
                    break
            except sqlite3.OperationalError as err:
                if "locked" in str(err).lower() and attempt < 9:
                    time.sleep(0.05 * (2 ** (attempt % 4)))
                    continue
                raise

    def _get_connection(self) -> sqlite3.Connection:
        """Create a sqlite3 connection with busy timeout."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            isolation_level=None,  # autocommit mode, manual transaction control
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000;")
        return conn

    def enqueue(
        self,
        target: str,
        message: str,
        sender: str = "unknown",
        priority: str = "normal",
        auto_flush: bool = True,
    ) -> dict[str, Any]:
        """Enqueue a message. If urgent, bypass queue. If batch size reached, flush."""
        target = self._sanitize_target(target)
        message = message.strip()
        sender = (sender or "unknown").strip()
        priority = (priority or "normal").strip()

        if not message:
            raise ValueError("Message body cannot be empty")

        # Check escalation bypass
        urgent, reason = is_escalation(message, priority)
        if urgent:
            terse_notification = f"[ESCALATION] {message}"
            delivery_meta = {
                "type": "escalation",
                "target": target,
                "sender": sender,
                "reason": reason,
                "message": message,
            }
            self._deliver(target, terse_notification, delivery_meta)
            return {
                "status": "escalation_bypass",
                "target": target,
                "delivered": True,
                "reason": reason,
                "message": message,
                "terse": terse_notification,
            }

        now_utc = datetime.now(timezone.utc).isoformat()
        flushed_batch: BatchDelivery | None = None
        message_id: int | None = None
        pending_count: int = 0

        max_retries = 10
        for attempt in range(max_retries):
            try:
                with self._lock, self._get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE;")
                    try:
                        cur = conn.execute(
                            """
                            INSERT INTO messages (target, sender, payload, priority, queued_at, status)
                            VALUES (?, ?, ?, ?, ?, 'pending')
                            """,
                            (target, sender, message, priority, now_utc),
                        )
                        message_id = cur.lastrowid

                        cur = conn.execute(
                            """
                            SELECT COUNT(*) AS count FROM messages
                            WHERE target = ? AND status = 'pending'
                            """,
                            (target,),
                        )
                        pending_count = cur.fetchone()["count"]

                        if auto_flush and pending_count >= self.batch_size:
                            flushed_batch = self._flush_target_in_tx(conn, target)
                            pending_count = 0

                        conn.execute("COMMIT;")
                        break
                    except Exception:
                        conn.execute("ROLLBACK;")
                        raise
            except sqlite3.OperationalError as err:
                if "locked" in str(err).lower() and attempt < max_retries - 1:
                    time.sleep(0.05 * (2 ** (attempt % 4)))
                    continue
                raise

        if flushed_batch:
            # Deliver outside DB lock
            self._deliver(
                target,
                flushed_batch.terse_notification,
                {"type": "batch", "batch": flushed_batch.to_dict()},
            )
            return {
                "status": "flushed",
                "target": target,
                "message_id": message_id,
                "pending_count": 0,
                "batch": flushed_batch.to_dict(),
            }

        return {
            "status": "queued",
            "target": target,
            "message_id": message_id,
            "pending_count": pending_count,
        }

    def _flush_target_in_tx(self, conn: sqlite3.Connection, target: str) -> BatchDelivery | None:
        """Consolidate pending messages for target within an active immediate transaction."""
        cur = conn.execute(
            """
            SELECT id, target, sender, payload, priority, queued_at, status
            FROM messages
            WHERE target = ? AND status = 'pending'
            ORDER BY id ASC
            """,
            (target,),
        )
        rows = cur.fetchall()
        if not rows:
            return None

        messages = [
            QueuedMessage(
                id=r["id"],
                target=r["target"],
                sender=r["sender"],
                payload=r["payload"],
                priority=r["priority"],
                queued_at=r["queued_at"],
                status=r["status"],
            )
            for r in rows
        ]

        now_utc = datetime.now(timezone.utc)
        ts_compact = now_utc.strftime("%Y%m%dT%H%M%SZ")
        batch_id = f"batch-{ts_compact}-{uuid.uuid4().hex[:8]}"

        # Write consolidated batch payload markdown
        target_inbox = self._get_target_inbox(target)
        target_inbox.mkdir(parents=True, exist_ok=True)
        batch_file = target_inbox / f"BATCH-{ts_compact}-{batch_id.split('-')[-1]}.md"

        payload_content = self._format_batch_payload(target, batch_id, now_utc.isoformat(), messages)
        tmp_file = target_inbox / f".tmp_{batch_file.name}"
        tmp_file.write_text(payload_content, encoding="utf-8")
        tmp_file.replace(batch_file)

        # Mark messages as flushed
        msg_ids = [m.id for m in messages]
        placeholders = ",".join("?" for _ in msg_ids)
        conn.execute(
            f"UPDATE messages SET status = 'flushed' WHERE id IN ({placeholders})",
            msg_ids,
        )

        terse_notification = f"BATCH {batch_file} ({len(messages)} messages)"

        return BatchDelivery(
            batch_id=batch_id,
            target=target,
            message_count=len(messages),
            batch_file_path=str(batch_file),
            terse_notification=terse_notification,
            delivered_at=now_utc.isoformat(),
            message_ids=msg_ids,
        )

    def enqueue(
        self,
        target: str,
        message: str,
        sender: str = "unknown",
        priority: str = "normal",
        auto_flush: bool = True,
    ) -> dict[str, Any]:
        """Enqueue a message. If urgent, bypass queue. If batch size reached, flush."""
        target = self._sanitize_target(target)
        message = message.strip()
        sender = (sender or "unknown").strip()
        priority = (priority or "normal").strip()

        if not message:
            raise ValueError("Message body cannot be empty")

        # Check escalation bypass
        urgent, reason = is_escalation(message, priority)
        if urgent:
            terse_notification = f"[ESCALATION] {message}"
            delivery_meta = {
                "type": "escalation",
                "target": target,
                "sender": sender,
                "reason": reason,
                "message": message,
            }
            self._deliver(target, terse_notification, delivery_meta)
            return {
                "status": "escalation_bypass",
                "target": target,
                "delivered": True,
                "reason": reason,
                "message": message,
                "terse": terse_notification,
            }

        now_utc = datetime.now(timezone.utc).isoformat()
        flushed_batch: BatchDelivery | None = None
        message_id: int | None = None
        pending_count: int = 0

        max_retries = 10
        for attempt in range(max_retries):
            try:
                with self._lock, self._get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE;")
                    try:
                        cur = conn.execute(
                            """
                            INSERT INTO messages (target, sender, payload, priority, queued_at, status)
                            VALUES (?, ?, ?, ?, ?, 'pending')
                            """,
                            (target, sender, message, priority, now_utc),
                        )
                        message_id = cur.lastrowid

                        cur = conn.execute(
                            """
                            SELECT COUNT(*) AS count FROM messages
                            WHERE target = ? AND status = 'pending'
                            """,
                            (target,),
                        )
                        pending_count = cur.fetchone()["count"]

                        if auto_flush and pending_count >= self.batch_size:
                            flushed_batch = self._flush_target_in_tx(conn, target)
                            pending_count = 0

                        conn.execute("COMMIT;")
                        break
                    except Exception:
                        conn.execute("ROLLBACK;")
                        raise
            except sqlite3.OperationalError as err:
                if "locked" in str(err).lower() and attempt < max_retries - 1:
                    time.sleep(0.05 * (2 ** (attempt % 4)))
                    continue
                raise

        if flushed_batch:
            # Deliver outside DB lock
            self._deliver(
                target,
                flushed_batch.terse_notification,
                {"type": "batch", "batch": flushed_batch.to_dict()},
            )
            return {
                "status": "flushed",
                "target": target,
                "message_id": message_id,
                "pending_count": 0,
                "batch": flushed_batch.to_dict(),
            }

        return {
            "status": "queued",
            "target": target,
            "message_id": message_id,
            "pending_count": pending_count,
        }

    def _flush_target_in_tx(self, conn: sqlite3.Connection, target: str) -> BatchDelivery | None:
        """Consolidate pending messages for target within an active immediate transaction."""
        cur = conn.execute(
            """
            SELECT id, target, sender, payload, priority, queued_at, status
            FROM messages
            WHERE target = ? AND status = 'pending'
            ORDER BY id ASC
            """,
            (target,),
        )
        rows = cur.fetchall()
        if not rows:
            return None

        messages = [
            QueuedMessage(
                id=r["id"],
                target=r["target"],
                sender=r["sender"],
                payload=r["payload"],
                priority=r["priority"],
                queued_at=r["queued_at"],
                status=r["status"],
            )
            for r in rows
        ]

        now_utc = datetime.now(timezone.utc)
        ts_compact = now_utc.strftime("%Y%m%dT%H%M%SZ")
        batch_id = f"batch-{ts_compact}-{uuid.uuid4().hex[:8]}"

        # Write consolidated batch payload markdown
        target_inbox = self._get_target_inbox(target)
        target_inbox.mkdir(parents=True, exist_ok=True)
        batch_file = target_inbox / f"BATCH-{ts_compact}-{batch_id.split('-')[-1]}.md"

        payload_content = self._format_batch_payload(target, batch_id, now_utc.isoformat(), messages)
        tmp_file = target_inbox / f".tmp_{batch_file.name}"
        tmp_file.write_text(payload_content, encoding="utf-8")
        tmp_file.replace(batch_file)

        # Mark messages as flushed
        msg_ids = [m.id for m in messages]
        placeholders = ",".join("?" for _ in msg_ids)
        conn.execute(
            f"UPDATE messages SET status = 'flushed' WHERE id IN ({placeholders})",
            msg_ids,
        )

        terse_notification = f"BATCH {batch_file} ({len(messages)} messages)"

        return BatchDelivery(
            batch_id=batch_id,
            target=target,
            message_count=len(messages),
            batch_file_path=str(batch_file),
            terse_notification=terse_notification,
            delivered_at=now_utc.isoformat(),
            message_ids=msg_ids,
        )

    def flush(self, target: str | None = None) -> list[dict[str, Any]]:
        """Manually flush pending messages for a specific target or all targets."""
        targets_to_flush: list[str] = []

        with self._lock, self._get_connection() as conn:
            if target:
                targets_to_flush = [self._sanitize_target(target)]
            else:
                cur = conn.execute(
                    "SELECT DISTINCT target FROM messages WHERE status = 'pending'"
                )
                targets_to_flush = [r["target"] for r in cur.fetchall()]

        delivered_batches: list[BatchDelivery] = []

        for tgt in targets_to_flush:
            batch: BatchDelivery | None = None
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    with self._lock, self._get_connection() as conn:
                        conn.execute("BEGIN IMMEDIATE;")
                        try:
                            batch = self._flush_target_in_tx(conn, tgt)
                            conn.execute("COMMIT;")
                            break
                        except Exception:
                            conn.execute("ROLLBACK;")
                            raise
                except sqlite3.OperationalError as err:
                    if "locked" in str(err).lower() and attempt < max_retries - 1:
                        time.sleep(0.05 * (2 ** (attempt % 4)))
                        continue
                    raise

            if batch:
                self._deliver(
                    tgt,
                    batch.terse_notification,
                    {"type": "batch", "batch": batch.to_dict()},
                )
                delivered_batches.append(batch)

        return [b.to_dict() for b in delivered_batches]

    def check_time_triggers(self) -> list[dict[str, Any]]:
        """Check all targets for pending messages exceeding the flush time window."""
        now_utc = datetime.now(timezone.utc)
        targets_needing_flush: list[str] = []

        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                """
                    SELECT target, MIN(queued_at) AS oldest_queued
                    FROM messages
                    WHERE status = 'pending'
                    GROUP BY target
                    """
            )
            for row in cur.fetchall():
                oldest_str = row["oldest_queued"]
                if not oldest_str:
                    continue
                try:
                    oldest_dt = datetime.fromisoformat(oldest_str)
                    if oldest_dt.tzinfo is None:
                        oldest_dt = oldest_dt.replace(tzinfo=timezone.utc)
                    elapsed = (now_utc - oldest_dt).total_seconds()
                    
                    target_interval = self.flush_interval
                    if row["target"].startswith("bd-pm-"):
                        import subprocess
                        import time
                        try:
                            out = subprocess.check_output(["tmux", "display-message", "-p", "-t", row["target"], "#{session_created}"], text=True, stderr=subprocess.DEVNULL).strip()
                            if out.isdigit():
                                if (time.time() - int(out)) < 1800:
                                    target_interval = 60.0
                        except Exception:
                            pass
                            
                    if elapsed >= target_interval:
                        targets_needing_flush.append(row["target"])
                except (ValueError, TypeError, OSError) as err:
                    logger.warning("Failed parsing queued_at '%s': %s", oldest_str, err)

        results: list[dict[str, Any]] = []
        for tgt in targets_needing_flush:
            flushed = self.flush(target=tgt)
            results.extend(flushed)

        return results

    def _deliver(
        self,
        target: str,
        terse_message: str,
        meta: dict[str, Any],
    ) -> None:
        """Deliver terse notification via callback, delivery_cmd, or delivery log."""
        # 1. In-process callback (e.g. for unit tests)
        if self.delivery_callback:
            try:
                self.delivery_callback(target, terse_message, meta)
            except (RuntimeError, ValueError, OSError) as err:
                logger.error("Delivery callback failed for target %s: %s", target, err)

        # 2. Configured delivery shell command
        if self.delivery_cmd:
            batch_dict = meta.get("batch", {})
            batch_path = batch_dict.get("batch_file_path", "")
            count = batch_dict.get("message_count", 1)
            formatted_cmd = self.delivery_cmd.format(
                target=shlex.quote(target),
                message=shlex.quote(terse_message),
                batch_path=shlex.quote(batch_path),
                count=count,
            )
            try:
                subprocess.run(
                    formatted_cmd,
                    shell=True,
                    check=True,
                    timeout=10,
                    capture_output=True,
                )
            except (subprocess.SubprocessError, OSError) as err:
                logger.error("Delivery command '%s' failed: %s", formatted_cmd, err)

        # 3. Always append delivery receipt to deliveries.log
        delivery_log = self.inbox_dir / "deliveries.log"
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target": target,
            "terse_notification": terse_message,
            "meta": meta,
        }
        with open(delivery_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

    def get_status(self, target: str | None = None) -> dict[str, Any]:
        """Query queue status, pending counts, and statistics."""
        with self._lock, self._get_connection() as conn:
            if target:
                target = self._sanitize_target(target)
                cur = conn.execute(
                    """
                    SELECT
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) AS pending_count,
                        COUNT(CASE WHEN status = 'flushed' THEN 1 END) AS flushed_count,
                        MIN(CASE WHEN status = 'pending' THEN queued_at END) AS oldest_pending
                    FROM messages
                    WHERE target = ?
                    """,
                    (target,),
                )
                row = cur.fetchone()
                return {
                    "target": target,
                    "pending_count": row["pending_count"],
                    "flushed_count": row["flushed_count"],
                    "oldest_pending": row["oldest_pending"],
                    "batch_size": self.batch_size,
                    "flush_interval": self.flush_interval,
                    "db_path": str(self.db_path),
                }

            cur = conn.execute(
                """
                SELECT target, COUNT(*) as count, MIN(queued_at) as oldest
                FROM messages
                WHERE status = 'pending'
                GROUP BY target
                """
            )
            target_pending = {
                r["target"]: {"count": r["count"], "oldest": r["oldest"]}
                for r in cur.fetchall()
            }

            cur = conn.execute(
                """
                SELECT
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) AS total_pending,
                    COUNT(CASE WHEN status = 'flushed' THEN 1 END) AS total_flushed
                FROM messages
                """
            )
            totals = cur.fetchone()

            return {
                "total_pending": totals["total_pending"],
                "total_flushed": totals["total_flushed"],
                "targets_pending": target_pending,
                "batch_size": self.batch_size,
                "flush_interval": self.flush_interval,
                "db_path": str(self.db_path),
            }

    def inspect_messages(
        self,
        target: str | None = None,
        status: str = "pending",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Inspect messages in the queue with filtering."""
        query = "SELECT * FROM messages WHERE 1=1"
        params: list[Any] = []

        if target:
            target = self._sanitize_target(target)
            query += " AND target = ?"
            params.append(target)
        if status and status != "all":
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._lock, self._get_connection() as conn:
            cur = conn.execute(query, params)
            return [dict(r) for r in cur.fetchall()]

    def run_daemon_loop(
        self,
        poll_interval: float = 1.0,
        stop_event: threading.Event | None = None,
    ) -> None:
        """Run continuous monitoring loop checking time window flush triggers."""
        logger.info(
            "Relay daemon loop started. batch_size=%d, flush_interval=%.1fs",
            self.batch_size,
            self.flush_interval,
        )
        while stop_event is None or not stop_event.is_set():
            try:
                flushed = self.check_time_triggers()
                if flushed:
                    logger.info("Time trigger flushed %d batches", len(flushed))
            except (sqlite3.Error, OSError, ValueError, RuntimeError) as err:
                logger.error("Error in relay daemon loop: %s", err)

            if stop_event:
                if stop_event.wait(poll_interval):
                    break
            else:
                time.sleep(poll_interval)

    def _format_batch_payload(
        self, target: str, batch_id: str, flushed_at: str, messages: list
    ) -> str:
        lines = [f"# BATCH {len(messages)} {flushed_at}"]
        for msg in messages:
            qat = getattr(msg, 'queued_at', msg.get('queued_at', '')) if isinstance(msg, dict) else getattr(msg, 'queued_at', '')
            hmz = qat.split('T')[1][:5] + 'Z' if 'T' in qat else qat
            sender = getattr(msg, 'sender', msg.get('sender', 'unknown')) if isinstance(msg, dict) else getattr(msg, 'sender', 'unknown')
            payload = getattr(msg, 'payload', msg.get('payload', '')).strip() if isinstance(msg, dict) else getattr(msg, 'payload', '')
            lines.append(f"[from {sender} {hmz}] {payload}")
        return "\n".join(lines) + "\n"
