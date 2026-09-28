"""Verified API list rates through the dashboard's actual SQLite aggregation."""
from __future__ import annotations

import importlib.util
import io
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

BD_GATE_SCOPE = "module"
SOURCE = Path(__file__).resolve().parents[1] / "infra/scripts/dashboard_server.py"


@pytest.fixture
def dashboard(monkeypatch: pytest.MonkeyPatch) -> Any:
    spec = importlib.util.spec_from_file_location("dashboard_prices", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "open", lambda *args: io.StringIO(""), raising=False)
    return module


@pytest.mark.parametrize(
    "model,input_tokens,cached,output_tokens,expected",
    [
        ("claude-opus-5-5", 1_000_000, 0, 0, "$4.00"),
        ("claude-opus-5-5", 1_000_000, 1_000_000, 0, "$0.20"),
        ("claude-opus-5-5", 0, 0, 1_000_000, "$20.00"),
        ("claude-opus-5-5", 1_250_000, 1_000_000, 100_000, "$3.20"),
        ("claude-fable-5-1", 1_000_000, 0, 0, "$10.00"),
        ("claude-fable-5-1", 1_000_000, 1_000_000, 0, "$0.25"),
        ("claude-fable-5-1", 0, 0, 1_000_000, "$50.00"),
        ("claude-fable-5-1", 1_250_000, 1_000_000, 100_000, "$7.75"),
        ("claude-opus-5-5", 0, 0, 0, "$0.00"),
    ],
)
def test_dashboard_request_list_price(
    dashboard: Any, monkeypatch: pytest.MonkeyPatch, model: str,
    input_tokens: int, cached: int, output_tokens: int, expected: str,
) -> None:
    data = _data(dashboard, monkeypatch, [(model, input_tokens, cached, output_tokens)])
    assert data["metrics"]["total_turns"] == 1
    assert len(data["agents"]) == 1
    assert data["agents"][0]["cost"] == expected
    assert data["metrics"]["total_cost"] == expected
    assert data["metrics"]["unpriced_turns"] == 0
    assert data["metrics"]["unpriced_models"] == 0


def _data(
    dashboard: Any, monkeypatch: pytest.MonkeyPatch,
    requests: list[tuple[str, int, int, int]],
) -> dict[str, Any]:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        "CREATE TABLE usage_responses (provider TEXT, response_id TEXT, model TEXT, "
        "usage TEXT, timestamp TEXT);"
        "CREATE TABLE usage_occurrences (provider TEXT, response_id TEXT, thread TEXT);"
    )
    for index, (model, input_tokens, cached, output_tokens) in enumerate(requests):
        usage = json.dumps({"input_tokens": input_tokens, "cache_read_input_tokens": cached,
                            "output_tokens": output_tokens})
        conn.execute("INSERT INTO usage_responses VALUES (?, ?, ?, ?, ?)",
                     ("claude", str(index), model, usage, "2026-09-28T01:00:00Z"))
        conn.execute("INSERT INTO usage_occurrences VALUES (?, ?, ?)",
                     ("claude", str(index), model))
    monkeypatch.setattr(dashboard.sqlite3, "connect", lambda *args, **kwargs: conn)
    try:
        result: dict[str, Any] = dashboard.get_data()
        return result
    finally:
        conn.close()


@pytest.mark.parametrize("model", ["unlisted-model", "UNKNOWN", "gpt-6-sol"])
def test_unpriced_model_has_no_guessed_cost(
    dashboard: Any, monkeypatch: pytest.MonkeyPatch, model: str,
) -> None:
    data = _data(dashboard, monkeypatch, [(model, 1_000_000, 0, 0)])
    assert data["agents"][0]["cost"] == "COULD NOT LOOK"
    assert data["metrics"]["total_cost"] == "COULD NOT LOOK"
    assert data["metrics"]["unpriced_turns"] == 1
    assert data["metrics"]["unpriced_models"] == 1
    assert data["metrics"]["total_turns"] == 1


def test_mixed_total_is_explicitly_partial(
    dashboard: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _data(dashboard, monkeypatch, [
        ("claude-opus-5-5", 1_000_000, 0, 0),
        ("unlisted-model", 1_000_000, 0, 0),
        ("unlisted-model", 1_000_000, 0, 0),
        ("gpt-6-sol", 1_000_000, 0, 0),
    ])
    assert data["metrics"]["total_cost"] == "$4.00 (partial)"
    assert data["metrics"]["unpriced_turns"] == 3
    assert data["metrics"]["unpriced_models"] == 2
    assert data["metrics"]["total_turns"] == 4
    costs = {agent["model"]: agent["cost"] for agent in data["agents"]}
    assert costs == {"claude-opus-5-5": "$4.00", "unlisted-model": "COULD NOT LOOK",
                     "gpt-6-sol": "COULD NOT LOOK"}


def test_empty_usage_has_no_measured_cost(
    dashboard: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _data(dashboard, monkeypatch, [])
    assert data["metrics"]["total_cost"] == "COULD NOT LOOK"
    assert data["metrics"]["total_turns"] == 0
    assert data["metrics"]["unpriced_turns"] == 0
    assert data["agents"] == []
