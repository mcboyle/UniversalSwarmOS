#!/usr/bin/env python3
"""
test_milestone1_preamble_and_transcript.py

Verification suite for Milestone 1: Preamble & Transcript Immutability (R1 + R4)
Tests:
1. Static Preamble Enforcement & Trailing Dynamic Metadata in bd-launch-role.sh
2. Token Offset 0 Immutability & Trailing Metadata in bd-codex-lens.sh
3. Append-Only Transcript Invariance (<150k compaction prohibition) in bd-amnesia-hook.py
4. Fleet Rule 77: 20-Turn Maximum Ceiling & RESUME_STATE.md generation
5. Emergency Compaction Gating (>=150k) in bd-amnesia-hook.py
6. Fleet Rule 22: BulkDownloader Working Tree Cleanliness
"""

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

# Paths
REPO_ROOT = Path("/home/mboyle/UniversalSwarmOS")
BD_LAUNCH_ROLE_SH = REPO_ROOT / "infra/scripts/bd-launch-role.sh"
BD_CODEX_LENS_SH = Path("/home/mboyle/bd-codex-lens.sh")
BD_AMNESIA_HOOK_PY = REPO_ROOT / "infra/hooks/bd-amnesia-hook.py"
BULKDOWNLOADER_DIR = Path("/home/mboyle/BulkDownloader")

# Import bd-amnesia-hook components using importlib
import importlib.util

_spec = importlib.util.spec_from_file_location("bd_amnesia_hook", str(BD_AMNESIA_HOOK_PY))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["bd_amnesia_hook"] = _mod
_spec.loader.exec_module(_mod)

AmnesiaDaemon = _mod.AmnesiaDaemon
build_arg_parser = _mod.build_arg_parser
get_thresholds_for_file = _mod.get_thresholds_for_file
DEFAULT_TRIGGER_TOKENS = _mod.DEFAULT_TRIGGER_TOKENS
DEFAULT_MAX_TURNS = _mod.DEFAULT_MAX_TURNS


def test_rule_22_bulkdownloader_clean():
    """Rule 22: Verify BulkDownloader working tree remains 100% clean."""
    res = subprocess.run(
        ["git", "-C", str(BULKDOWNLOADER_DIR), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"git status failed: {res.stderr}"
    assert res.stdout.strip() == "", f"BulkDownloader is dirty:\n{res.stdout}"


def test_bd_launch_role_preamble_frozen_and_zero_dynamic():
    """
    R1: Verify that bd-launch-role.sh produces 100% frozen, byte-identical system preambles
    across different seats of the same role, and quarantines dynamic variables into the kick message.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_role_dir = tmp_path / "roles"
        test_role_dir.mkdir(parents=True)
        role_prompt = test_role_dir / "worker.prompt"
        static_role_text = (
            "# STATIC WORKER ROLE PROMPT (FROZEN LAYER 1)\n"
            "You are a persistent headless worker agent in UniversalSwarmOS.\n"
            "Execute tasks deterministically. Follow Fleet Rules 74, 77, 80.\n"
        )
        role_prompt.write_text(static_role_text)

        test_persist_dir = tmp_path / "persist"
        test_persist_dir.mkdir(parents=True)
        (test_persist_dir / "ROLE-CARDINALITY.tsv").write_text("worker\tMULTI\n")

        # Run bd-launch-role.sh in DRY mode for two distinct seats
        env1 = os.environ.copy()
        env1["BD_LAUNCH_ROLE_DIR"] = str(test_role_dir)
        env1["BD_PERSIST_ROOT"] = str(test_persist_dir)
        env1["BD_ROLE_CARDINALITY"] = str(test_persist_dir / "ROLE-CARDINALITY.tsv")
        env1["BD_LAUNCH_ALLOW_DUP"] = "1"

        res1 = subprocess.run(
            ["bash", str(BD_LAUNCH_ROLE_SH), "worker", "A", "bd-worker-test1", "--dry-run"],
            env=env1,
            capture_output=True,
            text=True,
            check=False,
        )
        assert res1.returncode == 0, f"bd-launch-role dry-run 1 failed:\n{res1.stderr}\n{res1.stdout}"

        res2 = subprocess.run(
            ["bash", str(BD_LAUNCH_ROLE_SH), "worker", "A", "bd-worker-test2", "--dry-run"],
            env=env1,
            capture_output=True,
            text=True,
            check=False,
        )
        assert res2.returncode == 0, f"bd-launch-role dry-run 2 failed:\n{res2.stderr}\n{res2.stdout}"

        # Inspect generated SPFILE
        spfile = Path("/home/mboyle/bd-persist/role-systemprompts/worker.frozen.systemprompt")
        assert spfile.exists(), f"Expected frozen SPFILE does not exist at {spfile}"
        sp_content = spfile.read_text()

        # Invariant checks on SPFILE: zero dynamic variables
        assert "bd-worker-test1" not in sp_content, "Seat name leaked into frozen system prompt!"
        assert "bd-worker-test2" not in sp_content, "Seat name leaked into frozen system prompt!"
        assert "handoff-" not in sp_content, "Volatile handoff pointer found in system prompt!"
        assert "compact-" not in sp_content, "Volatile compact pointer found in system prompt!"
        assert "role-state/" not in sp_content, "Volatile role state pointer found in system prompt!"

        # Aliases for both seats must resolve to the identical frozen file
        alias1 = Path("/home/mboyle/bd-persist/role-systemprompts/bd-worker-test1-A.systemprompt")
        alias2 = Path("/home/mboyle/bd-persist/role-systemprompts/bd-worker-test2-A.systemprompt")
        assert alias1.exists(), f"Alias {alias1} does not exist"
        assert alias2.exists(), f"Alias {alias2} does not exist"
        assert alias1.read_text() == alias2.read_text() == sp_content

        # Cleanup test aliases
        alias1.unlink(missing_ok=True)
        alias2.unlink(missing_ok=True)


def test_bd_codex_lens_onboarding_token_offset_0_frozen():
    """
    R1: Verify that bd-codex-lens.sh places static brief at token offset 0 of .onboard.md,
    removes session names, worktrees, scratch paths, and commit hashes from token offset 0,
    and isolates dynamic variables in the trailing <!-- DYNAMIC_METADATA_START --> block.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        brief_file = tmp_path / "test_brief.md"
        static_brief_content = (
            "# LENS CORRECTNESS STATIC SPECIFICATION\n"
            "Review candidate diffs per protocol B and Rule 76.\n"
            "Report verdicts in single-line JSON format.\n"
        )
        brief_file.write_text(static_brief_content)

        wt_root = tmp_path / "wt_root"
        wt_root.mkdir()
        wt1 = wt_root / "bd-cx-test1"
        wt2 = wt_root / "bd-cx-test2"
        wt1.mkdir()
        wt2.mkdir()

        # Initialize mock git repos in worktrees
        for wt in (wt1, wt2):
            subprocess.run(["git", "-C", str(wt), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(wt), "config", "user.email", "test@test.local"], check=True)
            subprocess.run(["git", "-C", str(wt), "config", "user.name", "Test"], check=True)
            (wt / "README.md").write_text("test")
            subprocess.run(["git", "-C", str(wt), "add", "."], check=True)
            subprocess.run(["git", "-C", str(wt), "commit", "-q", "-m", "init"], check=True)

        # Generate .onboard.md for seat 1 and seat 2 using the logic in bd-codex-lens.sh
        for wt, name in [(wt1, "bd-cx-test1"), (wt2, "bd-cx-test2")]:
            base = subprocess.run(
                ["git", "-C", str(wt), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip()
            # Execute the onboarding generation snippet extracted from bd-codex-lens.sh
            gen_script = f"""
            set -euo pipefail
            BRIEF="{brief_file}"
            NAME="{name}"
            W="{wt}"
            BASE="{base}"
            source <(sed -n '168,197p' "{BD_CODEX_LENS_SH}")
            """
            subprocess.run(["bash", "-c", gen_script], check=True)

        onboard1 = (wt1 / ".onboard.md").read_text()
        onboard2 = (wt2 / ".onboard.md").read_text()

        # 1. Token offset 0 MUST start with the static brief
        assert onboard1.startswith(static_brief_content), "Token offset 0 does not start with static brief!"
        assert onboard2.startswith(static_brief_content), "Token offset 0 does not start with static brief!"

        # 2. Token offset 0 must NOT contain dynamic identity lines
        assert "## YOUR IDENTITY" not in onboard1[:200]
        assert "SESSION NAME:" not in onboard1[:200]
        assert "YOUR WORKTREE" not in onboard1[:200]
        assert "YOUR SCRATCH DIR" not in onboard1[:200]
        assert "HOST:" not in onboard1[:200]

        # 3. Dynamic metadata must be quarantined into the trailing comment block
        assert "<!-- DYNAMIC_METADATA_START -->" in onboard1
        assert "<!-- DYNAMIC_METADATA_END -->" in onboard1
        assert "SEAT_UUID: bd-cx-test1" in onboard1
        assert "SEAT_UUID: bd-cx-test2" in onboard2

        # 4. Compare prefix up to the trailing comment block: MUST BE EXACTLY 0 BYTES DIFF
        prefix1 = onboard1.split("<!-- DYNAMIC_METADATA_START -->")[0]
        prefix2 = onboard2.split("<!-- DYNAMIC_METADATA_START -->")[0]
        assert prefix1 == prefix2, "Prefix before dynamic metadata block differs between seats!"


def test_amnesia_hook_prohibits_compaction_below_150k():
    """
    R4: Verify that bd-amnesia-hook.py enforces strictly append-only transcript invariance
    and PROHIBITS mid-session compaction when context is below 150k tokens.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        transcript = tmp_path / "session_below_150k.jsonl"

        # Create a mock Claude DAG transcript with ~80k tokens (< 150k ceiling)
        # Using ~250,000 characters (~70k tokens)
        records = []
        u0 = str(uuid.uuid4())
        records.append({"type": "last-prompt", "leafUuid": u0, "sessionId": "test-sess-1"})
        records.append({
            "uuid": u0,
            "parentUuid": None,
            "type": "user",
            "message": {"role": "user", "content": "Execute task step 1. " + ("A" * 200_000)},
        })

        with open(transcript, "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in records)

        init_size = transcript.stat().st_size
        init_mtime = transcript.stat().st_mtime_ns

        # Run AmnesiaDaemon on this transcript
        parser = build_arg_parser()
        args = parser.parse_args([
            "--file", str(transcript),
            "--threshold", "150000",
            "--target-tokens", "60000",
        ])
        daemon = AmnesiaDaemon(args)

        # Gating check: get_thresholds_for_file must return >= 150,000
        trig, _targ = get_thresholds_for_file(transcript, records, default_trigger=150_000)
        assert trig >= 150_000, f"Trigger threshold {trig} is less than 150,000!"

        # process_file MUST return False (compaction prohibited)
        pruned = daemon.process_file(transcript)
        assert pruned is False, "Amnesia hook illegally pruned context below 150k tokens!"

        # Transcript must be 100% byte-identical (append-only invariant preserved)
        final_size = transcript.stat().st_size
        final_mtime = transcript.stat().st_mtime_ns
        assert init_size == final_size, "File size changed despite compaction prohibition!"
        assert init_mtime == final_mtime, "File was modified despite compaction prohibition!"


def test_amnesia_hook_rule_77_20_turns_clean_retirement():
    """
    R4 & Fleet Rule 77: Verify that bd-amnesia-hook.py enforces 20-turn maximum ceiling
    with clean termination and RESUME_STATE.md generation.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        transcript = tmp_path / "session_turn_20.jsonl"

        # Build a mock 20-turn transcript
        records = []
        last_uuid = None
        sess_id = f"test-sess-{uuid.uuid4().hex[:8]}"

        for turn in range(1, 21):
            u_user = f"u-{turn}"
            records.append({
                "uuid": u_user,
                "parentUuid": last_uuid,
                "type": "user",
                "message": {"role": "user", "content": f"User command for turn {turn}"},
            })
            u_asst = f"a-{turn}"
            records.append({
                "uuid": u_asst,
                "parentUuid": u_user,
                "type": "assistant",
                "message": {"role": "assistant", "content": f"Assistant response for turn {turn}", "model": "claude-sonnet-4-6"},
            })
            last_uuid = u_asst

        records.insert(0, {"type": "last-prompt", "leafUuid": last_uuid, "sessionId": sess_id})

        with open(transcript, "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in records)

        # Run AmnesiaDaemon with max_turns=20
        parser = build_arg_parser()
        args = parser.parse_args([
            "--file", str(transcript),
            "--max-turns", "20",
            "--threshold", "150000",
        ])
        daemon = AmnesiaDaemon(args)

        # Temporary redirect of working directory
        os.environ["BD_LAUNCH_WORKDIR"] = str(tmp_path)
        os.environ["BD_SEAT"] = "test-worker-turn20"

        try:
            retired = daemon.process_file(transcript)
            assert retired is True, "process_file did not trigger Rule 77 retirement at Turn 20!"

            # Verify RESUME_STATE.md was generated
            resume_file = tmp_path / "RESUME_STATE.md"
            assert resume_file.exists(), f"RESUME_STATE.md was not created in {tmp_path}"
            content = resume_file.read_text()

            # Verify schema & contents
            assert "artifact_contract: \"ce-handoff/v1\"" in content
            assert "Fleet Rule 77" in content
            assert "turn_count: 20" in content
            assert "seat: \"test-worker-turn20\"" in content
            assert "claude-sonnet-4-6" in content
        finally:
            os.environ.pop("BD_LAUNCH_WORKDIR", None)
            os.environ.pop("BD_SEAT", None)


def test_amnesia_hook_emergency_compaction_above_150k():
    """
    R4: Verify that when context breaches 150k tokens, emergency structured compaction is permitted.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        transcript = tmp_path / "session_breach_150k.jsonl"

        # Create a mock transcript with > 150k tokens (~600k chars)
        records = []
        u0 = "node-0"
        records.append({"type": "last-prompt", "leafUuid": "node-1", "sessionId": "sess-breach"})
        records.append({
            "uuid": u0,
            "parentUuid": None,
            "type": "user",
            "message": {"role": "user", "content": "Initial prompt"},
        })

        # Add a large tool result in an older turn to trigger compaction
        u_tool = "node-1"
        huge_tool_output = "OUTPUT DATA " * 50_000  # ~600,000 chars (~165k tokens)
        records.append({
            "uuid": u_tool,
            "parentUuid": u0,
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_abc123",
                        "content": huge_tool_output,
                    }
                ],
            },
        })

        with open(transcript, "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in records)

        parser = build_arg_parser()
        args = parser.parse_args([
            "--file", str(transcript),
            "--threshold", "150000",
            "--target-tokens", "60000",
            "--dry-run",
        ])
        daemon = AmnesiaDaemon(args)
        # In dry run, it should report True (would prune) because est_tokens > 150k
        would_prune = daemon.process_file(transcript)
        assert would_prune is True, "Emergency compaction failed to trigger when context > 150k tokens!"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
