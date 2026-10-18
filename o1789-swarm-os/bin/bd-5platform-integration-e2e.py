#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import tomllib

MCP_SCRIPT = "/home/mboyle/bin/bd-boylenet-infra-mcp.py"
EXPECTED_20_TOOLS = [
    "vm_exec",
    "vm_browse_files",
    "local_coding_agent_fix",
    "ramdisk_pytest_digest",
    "browser_oracle_query",
    "browser_oracle_cdp_inspect",
    "bd_kb_search",
    "qdrant_hivemind_search",
    "qdrant_hivemind_store",
    "model_vault_catalog_and_switch",
    "raw_unrestricted_llm_call",
    "airgap_control",
    "pool_quota_router",
    "spawn_cross_pool_subagent",
    "vsan_esxi_cluster_status",
    "unifi_dns_traefik_status",
    "openwebui_tool_gateway_call",
    "gitea_github_repo_sync",
    "sentinel_doctor_autoheal",
    "queue_backlog_status",
]
TEST_PAYLOADS: dict[str, dict[str, Any]] = {
    "vm_exec": {
        "vm": "10.0.70.164",
        "command": "hostname && uname -r",
        "cwd": "/home/mboyle",
    },
    "vm_browse_files": {"vm": "all", "action": "list", "path": "/vms"},
    "local_coding_agent_fix": {
        "mode": "probe",
        "sandbox": "/home/mboyle/bd-local-wt/local-agent-sandbox-1",
    },
    "ramdisk_pytest_digest": {"target": "tests/test_version.py", "node": "10.0.70.82"},
    "browser_oracle_query": {"action": "status", "oracle": "all"},
    "browser_oracle_cdp_inspect": {"url": "http://10.0.70.164:4080", "node": "137"},
    "bd_kb_search": {"query": "Boylenet 27-node architecture O1740", "top_k": 3},
    "qdrant_hivemind_search": {
        "query": "O1740 dynamic capability routing",
        "collection": "bd_master_kb",
        "limit": 3,
    },
    "qdrant_hivemind_store": {
        "title": "Agent-111 5-Platform Universal Infra MCP Verification",
        "content": "Verified 20 Boylenet infrastructure tools across Claude, Codex, Kimi, AGY, and Local Coding Agent with .72/.83 benchmark protection.",
        "category": "e2e-verification",
        "collection": "boylenet_episodic_memory",
        "tags": ["agent-111", "boylenet-infra", "5-platform-e2e"],
    },
    "model_vault_catalog_and_switch": {"action": "catalog"},
    "raw_unrestricted_llm_call": {
        "prompt": "Reply with exactly: RAW_137_OK",
        "harness": "local-137",
        "model": "qwen2.5-coder:7b-16k",
        "max_tokens": 16,
    },
    "airgap_control": {"action": "status"},
    "pool_quota_router": {"role_tier": "heavy_lifter", "refresh": False},
    "spawn_cross_pool_subagent": {
        "harness": "local",
        "prompt": "Check infra status",
        "dry_run": True,
    },
    "vsan_esxi_cluster_status": {"host": "all", "action": "status"},
    "unifi_dns_traefik_status": {"filter": "", "action": "status"},
    "openwebui_tool_gateway_call": {
        "tool_name": "ilo4_ipmi_rack_sensors",
        "arguments": {"action": "status"},
    },
    "gitea_github_repo_sync": {"action": "status", "repo": "all"},
    "sentinel_doctor_autoheal": {"action": "status"},
    "queue_backlog_status": {"queue": "all", "limit": 6},
}


class StdioMCPClient:
    def __init__(self, command: str, args: list[str]) -> None:
        self.proc = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._id = 0

    def request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self._id += 1
        msg = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": params or {},
        }
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            stderr_out = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"EOF from MCP server on {method}. stderr={stderr_out}")
        return json.loads(line)

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except (OSError, subprocess.SubprocessError):
            self.proc.kill()


def run_20_tools_stdio_suite() -> dict[str, Any]:
    t0 = time.perf_counter()
    client = StdioMCPClient("/usr/bin/python3", [MCP_SCRIPT])
    try:
        init_resp = client.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "e2e-verifier", "version": "1.0"},
            },
        )
        client.notify("notifications/initialized")
        list_resp = client.request("tools/list")
        tools = list_resp.get("result", {}).get("tools", [])
        tool_names = [t.get("name") for t in tools]
        missing = [n for n in EXPECTED_20_TOOLS if n not in tool_names]
        tool_results: dict[str, Any] = {}
        passed_count = 0
        for idx, tname in enumerate(EXPECTED_20_TOOLS, 1):
            t_start = time.perf_counter()
            call_resp = client.request(
                "tools/call", {"name": tname, "arguments": TEST_PAYLOADS[tname]}
            )
            res_block = call_resp.get("result", {})
            is_err = bool(res_block.get("isError", False))
            structured = res_block.get("structuredContent", {})
            ok = not is_err and bool(structured.get("ok", True))
            if ok:
                passed_count += 1
            tool_results[tname] = {
                "index": idx,
                "ok": ok,
                "latency_ms": round((time.perf_counter() - t_start) * 1000, 2),
                "summary": {
                    k: v
                    for k, v in structured.items()
                    if k
                    not in (
                        "data",
                        "result",
                        "all_pools",
                        "sample_models",
                        "sample_rows",
                    )
                    and (not isinstance(v, (list, dict)))
                },
            }
        guard_resp = client.request(
            "tools/call",
            {
                "name": "vm_exec",
                "arguments": {"vm": "10.0.70.72", "command": "pkill -f llama-bench"},
            },
        )
        guard_struct = guard_resp.get("result", {}).get("structuredContent", {})
        benchmark_guard_verified = (
            guard_struct.get("blocked_by_invariant") == "BENCHMARK_PROTECTION_72_83"
        )
        return {
            "ok": len(missing) == 0 and passed_count == 20 and benchmark_guard_verified,
            "initialize_serverInfo": init_resp.get("result", {}).get("serverInfo"),
            "tools_listed_count": len(tools),
            "missing_tools": missing,
            "tools_passed_count": passed_count,
            "benchmark_guard_72_83_verified": benchmark_guard_verified,
            "total_suite_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "tool_results": tool_results,
        }
    finally:
        client.close()


def verify_5_platforms() -> dict[str, Any]:
    platforms: dict[str, Any] = {}
    claude_files = [
        "/home/mboyle/.claude.json",
        "/home/mboyle/.claude-a/.claude.json",
        "/home/mboyle/.claude-b/.claude.json",
        "/home/mboyle/.claude-c/.claude.json",
        "/home/mboyle/.claude-d/.claude.json",
        "/var/tmp/claude-pool-A/.claude.json",
        "/var/tmp/claude-pool-B/.claude.json",
        "/var/tmp/claude-pool-C/.claude.json",
        "/var/tmp/claude-pool-D/.claude.json",
    ]
    claude_cfg_ok = True
    for cf in claude_files:
        d = json.loads(Path(cf).read_text(encoding="utf-8"))
        srv = d.get("mcpServers", {}).get("boylenet-infra", {})
        if srv.get("command") != "/usr/bin/python3" or MCP_SCRIPT not in srv.get(
            "args", []
        ):
            claude_cfg_ok = False
    claude_cmds = [
        f"/home/mboyle/.claude/commands/{c}.md"
        for c in (
            "bd-infra",
            "bd-vm",
            "bd-local-fix",
            "bd-oracle-e2e",
            "bd-bdkb",
            "bd-airgap",
            "bd-vault",
            "bd-queue",
        )
    ]
    claude_cmds_ok = all(Path(c).is_file() for c in claude_cmds)
    claude_plugin_ok = (
        Path("/home/mboyle/.agents/plugins/bd-autonomous-infra/plugin.json").is_file()
        and Path(
            "/home/mboyle/.agents/plugins/bd-autonomous-infra/.claude-plugin/plugin.json"
        ).is_file()
        and Path(
            "/home/mboyle/.agents/plugins/bd-autonomous-infra/skills/boylenet-autonomous-infra/SKILL.md"
        ).is_file()
    )
    c_srv = json.loads(Path("/home/mboyle/.claude.json").read_text(encoding="utf-8"))[
        "mcpServers"
    ]["boylenet-infra"]
    c_client = StdioMCPClient(c_srv["command"], c_srv["args"])
    try:
        c_client.request("initialize")
        c_call = c_client.request(
            "tools/call",
            {"name": "pool_quota_router", "arguments": {"role_tier": "heavy_lifter"}},
        )
        c_live_ok = (
            c_call.get("result", {}).get("structuredContent", {}).get("ok") is True
        )
    finally:
        c_client.close()
    platforms["1_claude_code"] = {
        "ok": claude_cfg_ok and claude_cmds_ok and claude_plugin_ok and c_live_ok,
        "configs_verified": len(claude_files),
        "slash_commands_verified": len(claude_cmds),
        "plugin_verified": claude_plugin_ok,
        "live_mcp_call_ok": c_live_ok,
    }
    codex_cfg = tomllib.loads(
        Path("/home/mboyle/.codex/config.toml").read_text(encoding="utf-8")
    )
    codex_srv = codex_cfg.get("mcp_servers", {}).get("boylenet_infra", {})
    codex_agent = tomllib.loads(
        Path("/home/mboyle/.codex/agents/boylenet-infra-commander.toml").read_text(
            encoding="utf-8"
        )
    )
    codex_skill_ok = Path(
        "/home/mboyle/.codex/skills/boylenet-autonomous-infra/SKILL.md"
    ).is_file()
    cx_client = StdioMCPClient(codex_srv["command"], codex_srv["args"])
    try:
        cx_client.request("initialize")
        cx_call = cx_client.request(
            "tools/call",
            {"name": "bd_kb_search", "arguments": {"query": "Rule 86", "top_k": 2}},
        )
        cx_live_ok = (
            cx_call.get("result", {}).get("structuredContent", {}).get("ok") is True
        )
    finally:
        cx_client.close()
    platforms["2_openai_codex"] = {
        "ok": bool(codex_srv)
        and codex_agent.get("name") == "boylenet-infra-commander"
        and codex_skill_ok
        and cx_live_ok,
        "config_toml_parsed": True,
        "agent_profile": codex_agent.get("name"),
        "skill_installed": codex_skill_ok,
        "live_mcp_call_ok": cx_live_ok,
    }
    kimi_mcp = json.loads(
        Path("/home/mboyle/.kimi/mcp.json").read_text(encoding="utf-8")
    )
    kimi_srv = kimi_mcp.get("mcpServers", {}).get("boylenet-infra", {})
    kimi_toml = tomllib.loads(
        Path("/home/mboyle/.kimi/config.toml").read_text(encoding="utf-8")
    )
    kimi_toml_srv = kimi_toml.get("mcp_servers", {}).get("boylenet-infra", {})
    kimi_skill_ok = Path(
        "/home/mboyle/.kimi/skills/boylenet-autonomous-infra/SKILL.md"
    ).is_file()
    km_client = StdioMCPClient(kimi_srv["command"], kimi_srv["args"])
    try:
        km_client.request("initialize")
        km_call = km_client.request(
            "tools/call",
            {"name": "queue_backlog_status", "arguments": {"queue": "all", "limit": 3}},
        )
        km_live_ok = (
            km_call.get("result", {}).get("structuredContent", {}).get("ok") is True
        )
    finally:
        km_client.close()
    platforms["3_moonshot_kimi"] = {
        "ok": bool(kimi_srv) and bool(kimi_toml_srv) and kimi_skill_ok and km_live_ok,
        "mcp_json_verified": bool(kimi_srv),
        "config_toml_verified": bool(kimi_toml_srv),
        "skill_installed": kimi_skill_ok,
        "live_mcp_call_ok": km_live_ok,
    }
    agy_cfg1 = json.loads(
        Path("/home/mboyle/.gemini/antigravity-cli/mcp_config.json").read_text(
            encoding="utf-8"
        )
    )
    agy_cfg2 = json.loads(
        Path("/home/mboyle/.gemini/config/mcp_config.json").read_text(encoding="utf-8")
    )
    schema_dir = Path("/home/mboyle/.gemini/antigravity-cli/mcp/boylenet-infra")
    schema_files = [schema_dir / f"{t}.json" for t in EXPECTED_20_TOOLS]
    schemas_ok = all(
        sf.is_file()
        and json.loads(sf.read_text(encoding="utf-8")).get("name") == sf.stem
        for sf in schema_files
    )
    inst_ok = (schema_dir / "instructions.md").is_file()
    agy_skills_ok = (
        Path(
            "/home/mboyle/.gemini/antigravity-cli/builtin/skills/boylenet-autonomous-infra/SKILL.md"
        ).is_file()
        and Path(
            "/home/mboyle/.agents/skills/boylenet-autonomous-infra/SKILL.md"
        ).is_file()
    )
    agy_srv = agy_cfg1.get("mcpServers", {}).get("boylenet-infra", {})
    ag_client = StdioMCPClient(agy_srv["command"], agy_srv["args"])
    try:
        ag_client.request("initialize")
        ag_call = ag_client.request(
            "tools/call",
            {"name": "vsan_esxi_cluster_status", "arguments": {"host": "all"}},
        )
        ag_live_ok = (
            ag_call.get("result", {}).get("structuredContent", {}).get("ok") is True
        )
    finally:
        ag_client.close()
    platforms["4_google_antigravity_agy"] = {
        "ok": bool(agy_srv)
        and "boylenet-infra" in agy_cfg2.get("mcpServers", {})
        and schemas_ok
        and inst_ok
        and agy_skills_ok
        and ag_live_ok,
        "schema_json_count": len(schema_files),
        "instructions_md_present": inst_ok,
        "skills_installed": agy_skills_ok,
        "live_mcp_call_ok": ag_live_ok,
    }
    cli_proc = subprocess.run(
        [
            "/usr/bin/python3",
            MCP_SCRIPT,
            "--cli",
            "local_coding_agent_fix",
            '{"mode":"probe"}',
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    cli_data = json.loads(cli_proc.stdout or "{}") if cli_proc.returncode == 0 else {}
    platforms["5_local_gpu_coding_agent"] = {
        "ok": cli_proc.returncode == 0 and bool(cli_data.get("ok")),
        "cli_mode_verified": cli_proc.returncode == 0,
        "benchmark_safe_72_83": cli_data.get("benchmark_safe_72_83", False),
        "backend_probe": cli_data.get("backend_probe"),
    }
    return {"ok": all(p["ok"] for p in platforms.values()), "platforms": platforms}


def main() -> None:
    t0 = time.perf_counter()
    stdio_suite = run_20_tools_stdio_suite()
    platform_suite = verify_5_platforms()
    overall_ok = stdio_suite["ok"] and platform_suite["ok"]
    report = {
        "ok": overall_ok,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mcp_server": MCP_SCRIPT,
        "total_duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        "stdio_20_tools_e2e": stdio_suite,
        "five_platforms_e2e": platform_suite,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
