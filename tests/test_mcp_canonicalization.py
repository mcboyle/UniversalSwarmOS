"""Test Suite for Milestone 2: Deterministic MCP Tool Schema Canonicalization (R2).

Validates:
1. Deterministic Tool Serialization across all MCP servers and platforms.
2. Alphabetical tool sorting and recursive sorted JSON keys.
3. Mid-session tool mutation prohibition:
   - Claude settings: ENABLE_TOOL_SEARCH is false.
   - Kimi config: dynamically_loaded_tools eliminated.
   - AGY mcp_config: defer_loading disabled across all servers.
4. 0-byte tool schema diff across consecutive turns.
5. Rule 22: BulkDownloader clean working tree.
"""
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
import tomllib

SWARM_ROOT = Path("/home/mboyle/UniversalSwarmOS")
CLAUDE_SETTINGS = SWARM_ROOT / "infra/hooks/claude/settings.json"
KIMI_CONFIG = SWARM_ROOT / "infra/hooks/kimi/config.toml"
AGY_MCP_CONFIG = SWARM_ROOT / "infra/hooks/agy/mcp_config.json"
BULKDOWNLOADER_DIR = Path("/home/mboyle/BulkDownloader")

MCP_SERVERS = [
    ("/home/mboyle/bd-persist/harness/bd-mcp/venv/bin/python", str(SWARM_ROOT / "infra/mcp/bd-mcp/server.py")),
    ("/home/mboyle/bd-persist/harness/bd-mcp/venv/bin/python", "/home/mboyle/bd-mcp/server.py"),
    ("/home/mboyle/bd-persist/harness/bd-mcp/venv/bin/python", str(SWARM_ROOT / "infra/mcp/bd-fleet-mcp/server.py")),
    ("/home/mboyle/bd-persist/harness/bd-mcp/venv/bin/python", "/home/mboyle/bd-fleet-mcp/server.py"),
    ("python3", str(SWARM_ROOT / "infra/mcp/bd_bus_mcp.py")),
    ("python3", str(SWARM_ROOT / "infra/mcp/mcp_server_mypy.py")),
    ("python3", str(SWARM_ROOT / "infra/mcp/mcp_server_ratf.py")),
    ("python3", str(SWARM_ROOT / "infra/mcp/mcp_server_ruff.py")),
    ("python3", str(SWARM_ROOT / "infra/mcp/mcp_server_vmware.py")),
]


def test_claude_settings_disable_tool_search():
    """Verify ENABLE_TOOL_SEARCH is false in Claude settings."""
    assert CLAUDE_SETTINGS.is_file(), f"Missing {CLAUDE_SETTINGS}"
    with open(CLAUDE_SETTINGS, "r", encoding="utf-8") as f:
        data = json.load(f)
    env = data.get("env", {})
    assert env.get("ENABLE_TOOL_SEARCH") == "false", f"ENABLE_TOOL_SEARCH must be 'false', got {env.get('ENABLE_TOOL_SEARCH')}"


def test_kimi_config_no_dynamic_tools():
    """Verify dynamically_loaded_tools is eliminated from Kimi config."""
    assert KIMI_CONFIG.is_file(), f"Missing {KIMI_CONFIG}"
    with open(KIMI_CONFIG, "rb") as f:
        data = tomllib.load(f)
    models = data.get("models", {})
    for model_name, model_cfg in models.items():
        caps = model_cfg.get("capabilities", [])
        assert "dynamically_loaded_tools" not in caps, f"Model {model_name} still contains dynamically_loaded_tools"


def test_agy_mcp_config_no_defer_loading():
    """Verify defer_loading is disabled (false) across all AGY MCP servers."""
    assert AGY_MCP_CONFIG.is_file(), f"Missing {AGY_MCP_CONFIG}"
    with open(AGY_MCP_CONFIG, "r", encoding="utf-8") as f:
        data = json.load(f)
    servers = data.get("mcpServers", {})
    assert len(servers) > 0, "No servers found in AGY mcp config"
    for server_name, server_cfg in servers.items():
        defer = server_cfg.get("defer_loading")
        assert defer is False or defer is None, f"Server {server_name} has defer_loading={defer} (expected false or absent)"


@pytest.mark.parametrize("py_bin, server_path", MCP_SERVERS)
def test_mcp_server_canonical_schema_alphabetical(py_bin, server_path):
    """Verify that each MCP server outputs tool schemas sorted alphabetically by name."""
    res = subprocess.run([py_bin, server_path, "--canonical-schemas"], capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"{server_path} exited with code {res.returncode}: {res.stderr}"
    tools = json.loads(res.stdout)
    assert len(tools) > 0, f"{server_path} returned 0 tools"
    names = [t["name"] for t in tools]
    assert names == sorted(names), f"{server_path} tools not sorted: {names}"


@pytest.mark.parametrize("py_bin, server_path", MCP_SERVERS)
def test_mcp_server_canonical_schema_sorted_keys(py_bin, server_path):
    """Verify that each MCP server JSON schema is serialized with sorted keys."""
    res = subprocess.run([py_bin, server_path, "--canonical-schemas"], capture_output=True, text=True, check=False)
    assert res.returncode == 0
    tools = json.loads(res.stdout)
    re_dump = json.dumps(tools, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    lines = [l for l in res.stdout.strip().splitlines() if l.startswith('[')]
    assert lines, "No JSON array found in output"
    assert lines[-1] == re_dump, f"{server_path} serialization not sorted-key canonical"


@pytest.mark.parametrize("py_bin, server_path", MCP_SERVERS)
def test_mcp_server_zero_byte_diff_across_turns(py_bin, server_path):
    """Verify exact 0-byte schema diff across consecutive simulated turns (Turns 1..10)."""
    turn_outputs = []
    for _ in range(10):
        res = subprocess.run([py_bin, server_path, "--canonical-schemas"], capture_output=True, text=True, check=False)
        assert res.returncode == 0
        turn_outputs.append(res.stdout.strip())

    t1_bytes = turn_outputs[0].encode("utf-8")
    t1_sha = hashlib.sha256(t1_bytes).hexdigest()
    for turn_idx, t_out in enumerate(turn_outputs[1:], start=2):
        t_bytes = t_out.encode("utf-8")
        diff_bytes = abs(len(t_bytes) - len(t1_bytes))
        assert diff_bytes == 0, f"{server_path} Turn {turn_idx} diff is {diff_bytes} bytes"
        assert t_out == turn_outputs[0], f"{server_path} Turn {turn_idx} content differs"
        assert hashlib.sha256(t_bytes).hexdigest() == t1_sha


def test_bulkdownloader_untouched():
    """Verify Fleet Rule 22: BulkDownloader working tree remains 100% clean."""
    res = subprocess.run(["git", "-C", str(BULKDOWNLOADER_DIR), "status", "--porcelain"], capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert res.stdout.strip() == "", f"BulkDownloader is dirty: {res.stdout.strip()}"
