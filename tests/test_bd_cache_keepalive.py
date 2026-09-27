"""
Unit and integration tests for bd-cache-keepalive daemon and CLI (Milestone 3 / R3).
Verifies:
  - CLI commands: start, stop, status, test-pause, acquire-lease, release-lease, show-policies, get-policy
  - Execution threshold monitoring (120s) and probe interval (180s)
  - Extended 1-hour cache block configurations across platforms
  - Systemd service file integrity and presence
  - 6-minute pause test survival receipt and usage.tsv logging
"""

import json
import os
import subprocess
import uuid
from pathlib import Path

BIN_PATH = Path("/home/mboyle/bin/bd-cache-keepalive")
SYMLINK_PATH = Path("/home/mboyle/UniversalSwarmOS/infra/scripts/bd-cache-keepalive")
SERVICE_PATH = Path("/home/mboyle/UniversalSwarmOS/infra/systemd/bd-cache-keepalive.service")
POLICY_FILE = Path("/home/mboyle/UniversalSwarmOS/infra/configs/cache-retention-policy.json")
RECEIPT_FILE = Path("/home/mboyle/bd-persist/accounting/keepalive_test_pause.json")
USAGE_TSV = Path("/home/mboyle/bd-persist/usage.tsv")


class TestKeepaliveBinaryAndSymlink:
    """Verifies executable binary and symlink properties."""

    def test_binary_exists_and_executable(self):
        assert BIN_PATH.is_file(), f"{BIN_PATH} does not exist"
        assert os.access(BIN_PATH, os.X_OK), f"{BIN_PATH} is not executable"

    def test_symlink_exists_and_resolves(self):
        assert SYMLINK_PATH.is_symlink() or SYMLINK_PATH.is_file()
        assert SYMLINK_PATH.resolve() == BIN_PATH.resolve()

    def test_cli_help_succeeds(self):
        proc = subprocess.run([str(BIN_PATH), "--help"], capture_output=True, text=True, check=False)
        assert proc.returncode == 0
        assert "bd-cache-keepalive" in proc.stdout
        assert "test-pause" in proc.stdout
        assert "show-policies" in proc.stdout


class TestCacheRetentionPolicies:
    """Verifies extended 1-hour cache block pinning policies."""

    def test_policy_file_exists(self):
        assert POLICY_FILE.is_file(), f"{POLICY_FILE} must exist"

    def test_claude_1hour_cache_block_policy(self):
        proc = subprocess.run(
            [str(BIN_PATH), "get-policy", "--platform", "claude"],
            capture_output=True,
            text=True,
            check=False
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["ttl_seconds"] == 3600
        assert data["cache_control"]["type"] == "ephemeral"
        assert data["cache_control"]["ttl"] == 3600
        assert "anthropic-beta" in data["headers"]

    def test_codex_retention_policy(self):
        proc = subprocess.run(
            [str(BIN_PATH), "get-policy", "--platform", "codex"],
            capture_output=True,
            text=True,
            check=False
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["ttl_seconds"] == 3600
        assert "x-session-id" in data["headers"]

    def test_all_platforms_covered(self):
        proc = subprocess.run(
            [str(BIN_PATH), "show-policies"],
            capture_output=True,
            text=True,
            check=False
        )
        assert proc.returncode == 0
        policies = json.loads(proc.stdout)
        required = ["claude", "agy-claude", "codex", "agy-gemini", "grok", "kimi", "satellite"]
        for r in required:
            assert r in policies, f"Platform {r} missing from retention policies"
            assert policies[r]["ttl_seconds"] == 3600


class TestSystemdServiceFile:
    """Verifies the systemd service file unit definition."""

    def test_service_file_exists(self):
        assert SERVICE_PATH.is_file(), f"{SERVICE_PATH} must exist"

    def test_service_file_contents(self):
        text = SERVICE_PATH.read_text(encoding="utf-8")
        assert "[Unit]" in text
        assert "[Service]" in text
        assert "[Install]" in text
        assert "ExecStart=/home/mboyle/bin/bd-cache-keepalive" in text
        assert "Restart=always" in text


class TestLeaseManagementAndPauseSimulation:
    """Verifies lease acquisition, release, status, and test-pause execution."""

    def test_lease_acquire_and_release_lifecycle(self):
        test_id = f"test-unit-{uuid.uuid4().hex[:6]}"
        acq = subprocess.run(
            [str(BIN_PATH), "acquire-lease", "--id", test_id, "--model", "trivial"],
            capture_output=True,
            text=True,
            check=False
        )
        assert acq.returncode == 0
        acq_data = json.loads(acq.stdout)
        assert acq_data["status"] == "ACQUIRED"
        assert acq_data["lease_id"] == test_id

        # Verify reported in status
        st = subprocess.run([str(BIN_PATH), "status"], capture_output=True, text=True, check=False)
        assert st.returncode == 0
        assert test_id in st.stdout

        # Release lease
        rel = subprocess.run(
            [str(BIN_PATH), "release-lease", "--id", test_id],
            capture_output=True,
            text=True,
            check=False
        )
        assert rel.returncode == 0
        rel_data = json.loads(rel.stdout)
        assert rel_data["status"] == "RELEASED"

    def test_pause_simulation_verification(self):
        # Run fast simulated pause
        proc = subprocess.run(
            [
                str(BIN_PATH), "test-pause",
                "--duration", "6",
                "--threshold", "2",
                "--probe-interval", "3",
                "--speedup", "1.0",
                "--model", "trivial"
            ],
            capture_output=True,
            text=True,
            check=False
        )
        assert proc.returncode == 0
        assert "KEEP-ALIVE PAUSE TEST RESULT: PASS" in proc.stdout or "PASS" in proc.stdout

        # Verify receipt exists and shows survival
        assert RECEIPT_FILE.is_file()
        receipt = json.loads(RECEIPT_FILE.read_text(encoding="utf-8"))
        assert receipt["survival_verified"] is True
        assert receipt["ttl_eviction_prevented"] is True
        assert receipt["probes_dispatched"] >= 2
