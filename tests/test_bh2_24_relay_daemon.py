"""bh2-24 (findings/BH2-bd-relay-bd-agy-sonnet-1.md #1, #2): lib/relay_daemon.py.

#1 an escalation embedded the whole message in the terse notification handed to bd-say (200 B rule, O1470).
#2 a batch was marked flushed before delivery; a failed delivery lost its messages for good.
Hermetic: tmp db/inbox, in-process callback or /bin/false|/bin/true as the delivery command; no tmux, no network.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.relay_daemon import RelayDaemon  # noqa: E402

TERSE_MAX_BYTES = 200


def _daemon(tmp_path, **kw):
    kw.setdefault("batch_size", 2)
    return RelayDaemon(db_path=tmp_path / "relay.db", inbox_dir=tmp_path / "inbox", **kw)


def _statuses(tmp_path):
    with sqlite3.connect(tmp_path / "relay.db") as conn:
        return [r[0] for r in conn.execute("SELECT status FROM messages ORDER BY id")]


def test_escalation_terse_is_bounded(tmp_path):
    sent = []
    d = _daemon(tmp_path, delivery_callback=lambda t, m, meta: sent.append(m))
    d.enqueue("pm", "STOP " + "x" * 10000)
    assert len(sent) == 1
    size = len(sent[0].encode("utf-8"))
    assert size <= TERSE_MAX_BYTES, f"BH2_24_ESCALATION_UNBOUNDED: terse is {size} B (cap {TERSE_MAX_BYTES})"
    assert sent[0].startswith("[ESCALATION] STOP x")


def test_escalation_terse_bounded_on_multibyte_text(tmp_path):
    sent = []
    d = _daemon(tmp_path, delivery_callback=lambda t, m, meta: sent.append(m))
    d.enqueue("pm", "BLOCKED " + "é" * 500)
    size = len(sent[0].encode("utf-8"))
    assert size <= TERSE_MAX_BYTES, f"BH2_24_ESCALATION_UNBOUNDED: terse is {size} B (cap {TERSE_MAX_BYTES})"


def test_short_escalation_passes_unchanged(tmp_path):
    sent = []
    d = _daemon(tmp_path, delivery_callback=lambda t, m, meta: sent.append((m, meta)))
    d.enqueue("pm", "STOP the train now")
    assert sent[0][0] == "[ESCALATION] STOP the train now"
    assert sent[0][1]["message"] == "STOP the train now"


def test_long_escalation_full_text_kept_in_meta(tmp_path):
    body = "STOP " + "x" * 10000
    sent = []
    d = _daemon(tmp_path, delivery_callback=lambda t, m, meta: sent.append(meta))
    d.enqueue("pm", body)
    assert sent[0]["message"] == body


def test_failed_command_delivery_stays_pending(tmp_path):
    d = _daemon(tmp_path, delivery_cmd="/bin/false")
    d.enqueue("pm", "one")
    result = d.enqueue("pm", "two")  # batch_size=2 -> flush -> delivery fails
    assert _statuses(tmp_path) == ["pending", "pending"], (
        f"BH2_24_WAKE_DROPPED: failed delivery left {_statuses(tmp_path)}"
    )
    assert result["status"] == "queued" and result.get("delivery_failed") is True, result
    assert list((tmp_path / "inbox" / "pm").glob("BATCH-*.md")) == [], "an undelivered batch file would be re-batched"


def test_failed_callback_delivery_stays_pending_then_retries(tmp_path):
    calls = []

    def flaky(target, message, meta):
        calls.append(message)
        if len(calls) == 1:
            raise RuntimeError("bd-say down")

    d = _daemon(tmp_path, delivery_callback=flaky)
    d.enqueue("pm", "one")
    d.enqueue("pm", "two")
    assert _statuses(tmp_path) == ["pending", "pending"], (
        f"BH2_24_WAKE_DROPPED: failed delivery left {_statuses(tmp_path)}"
    )
    batches = d.flush("pm")
    assert len(batches) == 1 and batches[0]["message_count"] == 2
    assert _statuses(tmp_path) == ["flushed", "flushed"]
    assert len(calls) == 2


def test_successful_delivery_marks_flushed(tmp_path):
    d = _daemon(tmp_path, delivery_cmd="/bin/true")
    d.enqueue("pm", "one")
    result = d.enqueue("pm", "two")
    assert result["status"] == "flushed"
    assert _statuses(tmp_path) == ["flushed", "flushed"]
    assert Path(result["batch"]["batch_file_path"]).is_file()


def test_failed_flush_reports_no_batch(tmp_path):
    d = _daemon(tmp_path, delivery_cmd="/bin/false", batch_size=99)
    d.enqueue("pm", "one")
    assert d.flush("pm") == []
    assert _statuses(tmp_path) == ["pending"]


@pytest.mark.parametrize("cmd", ["/bin/false", "/bin/true"])
def test_queue_below_batch_size_untouched(tmp_path, cmd):
    d = _daemon(tmp_path, delivery_cmd=cmd, batch_size=5)
    assert d.enqueue("pm", "one")["status"] == "queued"
    assert _statuses(tmp_path) == ["pending"]
