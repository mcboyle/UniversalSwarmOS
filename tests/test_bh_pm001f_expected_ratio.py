"""BH-PM001F: the repo copies of the expected checkpoint ratio carry no 0.90 floor.

Findings FINDING-BH-bd-cx-worker-2-PM001-{cron,hook}-expected-ratio-floor (follow-on of
the landed harness twin, bd-persist/harness bd-telemetry-guard.py @ 37bf90b). The ratio is
a model (locked checkpoint tokens / total tokens), not provider-measured cache telemetry,
so a session without a locked checkpoint expects 0.0 and 47,500 tokens expect
25,000 / 47,500 -- never a floor of 0.90. The cron copy writes the value into a PRUNE
order file, so the order is checked too.
"""

import json
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

BD_GATE_SCOPE = "module"

ROOT = Path(__file__).resolve().parents[1]
CRON = ROOT / "infra" / "cron" / "bd-telemetry-guard.py"
HOOK = ROOT / "infra" / "hooks" / "context_watermark_hook.py"


def _load(path: Path) -> dict[str, Any]:
    # run_name != "__main__": neither script's main() touches fleet state on load.
    return runpy.run_path(str(path), run_name="bh_pm001f_regression")


def _cron_fn(ns: dict[str, Any]):
    # The legacy name is accepted only so the behaviour tests pair with the RED base.
    return ns.get("expected_cache_hit_rate") or ns["calculate_cache_hit_rate"]


def _hook_ratio(ns: dict[str, Any], tokens: int, pruner: Any = None) -> float:
    pruner = pruner or ns["CheckpointWindowPruner"](window_size=25000)
    method = getattr(pruner, "expected_cache_hit_ratio", None) or pruner.calculate_cache_hit_ratio
    return method(tokens)


@pytest.fixture(scope="module")
def cron() -> dict[str, Any]:
    return _load(CRON)


@pytest.fixture(scope="module")
def hook() -> dict[str, Any]:
    return _load(HOOK)


CASES = [
    (47500, 25000 / 47500),   # finding repro: modeled 0.526, floored to 0.90 before the fix
    (174999, 150000 / 174999),
    (12500, 0.0),             # finding repro: first window, no locked checkpoint
    (999, 0.0),
    (500000, 0.95),           # paired above-floor control: unchanged by the fix
    (100001, 100000 / 100001),
]


@pytest.mark.parametrize(("tokens", "expected"), CASES)
def test_cron_expected_ratio_is_unfloored(cron, tokens, expected):
    got = _cron_fn(cron)(tokens, window_size=25000)
    assert got == pytest.approx(expected), f"BH-PM001F cron: {tokens} tokens -> {got}, modeled {expected}"


@pytest.mark.parametrize(("tokens", "expected"), CASES)
def test_hook_expected_ratio_is_unfloored(hook, tokens, expected):
    got = _hook_ratio(hook, tokens)
    assert got == pytest.approx(expected), f"BH-PM001F hook: {tokens} tokens -> {got}, modeled {expected}"


@pytest.mark.parametrize("tokens", [0, -1])
def test_no_observation_is_could_not_look(cron, hook, tokens):
    # Rule 6: an absent denominator is COULD NOT LOOK, never a ratio (base said 1.0, gen1 said 0.0).
    assert _cron_fn(cron)(tokens, window_size=25000) is None, "BH-PM001F cron: no tokens reported as a ratio"
    assert _hook_ratio(hook, tokens) is None, "BH-PM001F hook: no tokens reported as a ratio"


@pytest.mark.parametrize(("stdin", "extra"), [("[]", []), ("[]", ["--tokens", "0"]), ("", []), (" \n\t", []),
                                           ("", ["--tokens", "0"]), ("null", []), ("{}", [])])
def test_hook_cli_empty_input_is_could_not_look(stdin, extra):
    # [] = no records; "" / whitespace = no input at all (REFUTE G2: fell through to the line filter, rc 0, no output);
    # null / {} = JSON with no record list (same fall-through).
    res = subprocess.run([sys.executable, str(HOOK), "-", "--checkpoint-prune", "--json", *extra], input=stdin,
                         capture_output=True, text=True, timeout=30, check=False)
    assert res.stdout.strip(), f"BH-PM001F hook CLI: stdin {stdin!r} -> rc {res.returncode}, no could-not-look response"
    out = json.loads(res.stdout)
    assert (res.returncode, out["status"], out["expected_cache_hit_ratio"], out["reduction_percent"]) == (
        2, "could-not-look", None, None), f"BH-PM001F hook CLI: empty input reported as {res.returncode} {out}"


def test_hook_cli_real_record_is_ok():
    # Paired control: the same CLI with one real record still reports a ratio.
    record = [{"role": "user", "content": "x " * 190000}]
    res = subprocess.run([sys.executable, str(HOOK), "-", "--checkpoint-prune", "--json"], input=json.dumps(record),
                         capture_output=True, text=True, timeout=30, check=False)
    out = json.loads(res.stdout)
    assert res.returncode == 0 and out["status"] == "ok" and 0 < out["expected_cache_hit_ratio"] < 1, out


def test_hook_cli_plain_text_still_uses_the_line_filter():
    # Paired control: non-JSON text is the documented line-filter fallback, unchanged from BASE.
    res = subprocess.run([sys.executable, str(HOOK), "-", "--checkpoint-prune", "--json"], input="plain text line\n",
                         capture_output=True, text=True, timeout=30, check=False)
    assert (res.returncode, res.stdout) == (0, "plain text line\n"), (res.returncode, res.stdout)


def test_cron_prune_order_without_tokens_says_could_not_look(cron, tmp_path):
    fn = cron["trigger_zero_reset_pruning"]
    fn.__globals__["ORDERS_DIR"] = str(tmp_path)
    fn.__globals__["SAY_SH"] = str(tmp_path / "no-say.sh")
    body = Path(fn("bd-worker-test", 0, 150000)).read_text()
    assert "EXPECTED-CACHE-HIT-RATIO: COULD-NOT-LOOK" in body, "BH-PM001F cron: order fabricates a ratio from 0 tokens"


def test_hook_manifest_floor_key_is_inert(hook, tmp_path):
    # The live prefix_manifest.json still carries "min_cache_hit_ratio": 0.90.
    manifest = tmp_path / "prefix_manifest.json"
    manifest.write_text(json.dumps({"architecture": {"compaction_policy": {
        "checkpoint_window_tokens": 25000, "min_cache_hit_ratio": 0.90}}}))
    pruner = hook["CheckpointWindowPruner"].from_manifest(manifest)
    got = _hook_ratio(hook, 47500, pruner)
    assert got == pytest.approx(25000 / 47500), f"BH-PM001F hook: manifest floor applied -> {got}"


def test_cron_prune_order_states_the_modeled_ratio(cron, tmp_path):
    fn = cron["trigger_zero_reset_pruning"]
    fn.__globals__["ORDERS_DIR"] = str(tmp_path)
    fn.__globals__["SAY_SH"] = str(tmp_path / "no-say.sh")
    body = Path(fn("bd-worker-test", 174999, 150000)).read_text()
    assert "EXPECTED-CACHE-HIT-RATIO: 0.86\n" in body, "BH-PM001F cron: order carries a floored ratio: " + next(
        line for line in body.splitlines() if line.startswith("EXPECTED-CACHE-HIT-RATIO"))
    assert "guaranteed" not in body, "BH-PM001F cron: order still guarantees a >= 90% cache hit rate"


def test_floor_names_are_gone(cron, hook):
    assert "expected_cache_hit_rate" in cron and "calculate_cache_hit_rate" not in cron
    assert "MIN_CACHE_HIT_RATIO" not in cron
    assert "expected_cache_hit_rate" in hook and "calculate_cache_hit_rate" not in hook
    assert "DEFAULT_MIN_CACHE_HIT_RATIO" not in hook
    assert not hasattr(hook["CheckpointWindowPruner"], "calculate_cache_hit_ratio")
