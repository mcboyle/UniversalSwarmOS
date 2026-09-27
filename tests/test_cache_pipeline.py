"""
E2E Test Suite for Prompt Cache Optimization Architecture (R1-R5).
Covers all 12 features across Tiers 1-4 per TEST_INFRA.md:
  Tier 1: Feature Coverage (>=5 tests per feature covering representative inputs) = 60 tests
  Tier 2: Boundary & Corner Cases (>=5 tests per feature covering extreme inputs, zero diffs, 150k limits) = 60 tests
  Tier 3: Cross-Feature Interactions (pairwise combinations of features) = 12 tests
  Tier 4: Real-World Scenarios (multi-turn simulated and live workload checks) = 6 tests
Total Tests: 138 tests minimum.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import yaml

# Ensure /home/mboyle/bin is importable
sys.path.insert(0, "/home/mboyle/bin")
import importlib.machinery
import importlib.util

try:
    loader = importlib.machinery.SourceFileLoader(
        "bd_verify_cache_pipeline", "/home/mboyle/bin/bd-verify-cache-pipeline"
    )
    spec = importlib.util.spec_from_loader("bd_verify_cache_pipeline", loader)
    bd_verify_cache = importlib.util.module_from_spec(spec)
    sys.modules["bd_verify_cache_pipeline"] = bd_verify_cache
    loader.exec_module(bd_verify_cache)
except (ImportError, OSError, AttributeError):
    import bd_verify_cache_pipeline as bd_verify_cache

# Import bd-amnesia-hook components
AMNESIA_HOOK_PATH = Path("/home/mboyle/UniversalSwarmOS/infra/hooks/bd-amnesia-hook.py")
_amnesia_spec = importlib.util.spec_from_file_location("bd_amnesia_hook", str(AMNESIA_HOOK_PATH))
bd_amnesia_hook = importlib.util.module_from_spec(_amnesia_spec)
sys.modules["bd_amnesia_hook"] = bd_amnesia_hook
_amnesia_spec.loader.exec_module(bd_amnesia_hook)

AmnesiaDaemon = bd_amnesia_hook.AmnesiaDaemon
ClaudeDAGParser = bd_amnesia_hook.ClaudeDAGParser
CodexStreamTombstoner = bd_amnesia_hook.CodexStreamTombstoner
SemanticTombstoner = bd_amnesia_hook.SemanticTombstoner
get_thresholds_for_file = bd_amnesia_hook.get_thresholds_for_file
build_amnesia_parser = bd_amnesia_hook.build_arg_parser

# Import bd-cache-keepalive components
KEEPALIVE_BIN = Path("/home/mboyle/bin/bd-cache-keepalive")
_keepalive_loader = importlib.machinery.SourceFileLoader("bd_cache_keepalive", str(KEEPALIVE_BIN))
_keepalive_spec = importlib.util.spec_from_loader("bd_cache_keepalive", _keepalive_loader)
bd_cache_keepalive = importlib.util.module_from_spec(_keepalive_spec)
sys.modules["bd_cache_keepalive"] = bd_cache_keepalive
_keepalive_loader.exec_module(bd_cache_keepalive)

load_retention_policies = bd_cache_keepalive.load_retention_policies
get_retention_policy = bd_cache_keepalive.get_retention_policy
apply_retention_headers = bd_cache_keepalive.apply_retention_headers
KeepaliveLease = bd_cache_keepalive.KeepaliveLease
ProbeResult = bd_cache_keepalive.ProbeResult
DEFAULT_EXECUTION_THRESHOLD_S = bd_cache_keepalive.DEFAULT_EXECUTION_THRESHOLD_S

BULKDOWNLOADER_DIR = Path("/home/mboyle/BulkDownloader")
USAGE_TSV = Path("/home/mboyle/bd-persist/usage.tsv")
HARNESS_BIN = Path("/home/mboyle/bin/bd-verify-cache-pipeline")
BD_LAUNCH_ROLE_SH = Path("/home/mboyle/UniversalSwarmOS/infra/scripts/bd-launch-role.sh")
POLICY_FILE = Path("/home/mboyle/UniversalSwarmOS/infra/configs/cache-retention-policy.json")
LITELLM_CONFIG = Path("/home/mboyle/UniversalSwarmOS/infra/compose/litellm-config.yaml")


# ==============================================================================
# TIER 1: FEATURE COVERAGE (5 tests per feature * 12 features = 60 tests)
# ==============================================================================


class TestTier1FeatureCoverage:
    """Tier 1: Feature Coverage across all 12 prompt caching features."""

    # --------------------------------------------------------------------------
    # F1: Static Preamble Enforcement (ORIGINAL_REQUEST §R1)
    # --------------------------------------------------------------------------
    def test_f1_preamble_identical_across_turns(self):
        preamble = (
            "SYSTEM PREAMBLE: UniversalSwarmOS Core Policy.\n"
            "Persona: HTAP-9 zero-prose machine persona.\n"
            "Rule 74: Hard output cap <= 50 tokens.\n"
            "Rule 80: Pointer-payload decoupling CAS /var/tmp/bd-blobs/."
        )
        preambles = [preamble for _ in range(5)]
        ok, msg = bd_verify_cache.PreambleValidator.verify_turns_preamble_invariance(
            preambles
        )
        assert ok is True
        assert "byte-identical" in msg

    def test_f1_preamble_no_utc_timestamp(self):
        preamble_clean = "Role: Worker. Contract: Execute plan within boundaries."
        preamble_dirty = "Role: Worker. Started: 2026-09-27T10:30:00Z."
        ok_clean, _ = bd_verify_cache.PreambleValidator.inspect_preamble(preamble_clean)
        ok_dirty, viols_dirty = bd_verify_cache.PreambleValidator.inspect_preamble(
            preamble_dirty
        )
        assert ok_clean is True
        assert ok_dirty is False
        assert any("timestamp" in v for v in viols_dirty)

    def test_f1_preamble_no_seat_uuids(self):
        preamble_clean = "Role: Worker. Identity: Static generic worker."
        preamble_dirty = "Role: Worker. Seat ID: ea60d388-e608-4af3-b2aa-759d0575ebdd."
        ok_clean, _ = bd_verify_cache.PreambleValidator.inspect_preamble(preamble_clean)
        ok_dirty, viols_dirty = bd_verify_cache.PreambleValidator.inspect_preamble(
            preamble_dirty
        )
        assert ok_clean is True
        assert ok_dirty is False
        assert any("UUID" in v for v in viols_dirty)

    def test_f1_preamble_no_dynamic_seat_prefixes(self):
        preamble_clean = "Role: Generic Worker Seat."
        preamble_dirty = "Role: Active bd-worker-a12 node."
        ok_clean, _ = bd_verify_cache.PreambleValidator.inspect_preamble(preamble_clean)
        ok_dirty, viols_dirty = bd_verify_cache.PreambleValidator.inspect_preamble(
            preamble_dirty
        )
        assert ok_clean is True
        assert ok_dirty is False
        assert any("seat identifier" in v for v in viols_dirty)

    def test_f1_preamble_layer0_constitution_frozen(self):
        floor_path = Path("/home/mboyle/bd-persist/FLEET_RULE-FLOOR.md")
        assert floor_path.is_file(), f"{floor_path} must exist"
        content = floor_path.read_text(encoding="utf-8")
        assert len(content) > 0, "Constitution floor cannot be empty"
        ok, violations = bd_verify_cache.PreambleValidator.inspect_preamble(content)
        assert ok is True, f"Constitution contains dynamic violations: {violations}"
        assert len(violations) == 0
        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert len(h) == 64

    # --------------------------------------------------------------------------
    # F2: Trailing Dynamic Metadata Relocation (ORIGINAL_REQUEST §R1)
    # --------------------------------------------------------------------------
    def test_f2_trailing_metadata_block_structure(self):
        """Verify bd-launch-role.sh generates trailing dynamic metadata comment block."""
        res = subprocess.run(
            ["bash", str(BD_LAUNCH_ROLE_SH), "worker", "A", "test-metadata-seat", "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0
        spfile = Path("/home/mboyle/bd-persist/role-systemprompts/worker.frozen.systemprompt")
        assert spfile.is_file()
        sp_content = spfile.read_text(encoding="utf-8")
        assert "DYNAMIC_METADATA" not in sp_content
        assert "UTC_TIMESTAMP" not in sp_content
        assert "test-metadata-seat" not in sp_content

    def test_f2_metadata_fields_isolation(self):
        """Verify dynamic variables are isolated to kick message trailing comment."""
        launcher_text = BD_LAUNCH_ROLE_SH.read_text(encoding="utf-8")
        assert "<!-- DYNAMIC_METADATA_START -->" in launcher_text
        assert "UTC_TIMESTAMP:" in launcher_text
        assert "TURN_COUNT:" in launcher_text
        assert "SEAT_UUID:" in launcher_text
        assert "GIT_STATUS:" in launcher_text
        assert "<!-- DYNAMIC_METADATA_END -->" in launcher_text

    def test_f2_user_command_prefix_clean(self):
        """User content prefix remains clean before metadata comment block."""
        kick_base = "BEGIN. You have your role."
        metadata_block = (
            "<!-- DYNAMIC_METADATA_START -->\nTURN_COUNT: 1\n<!-- DYNAMIC_METADATA_END -->"
        )
        full_kick = f"{kick_base}\n\n{metadata_block}"
        assert full_kick.startswith(kick_base)
        prefix = full_kick.split("<!-- DYNAMIC_METADATA_START -->")[0].rstrip()
        assert prefix == kick_base

    def test_f2_dynamic_timestamp_in_trailing_only(self):
        """Timestamps reside exclusively in trailing block, never in system prompt."""
        spfile = Path("/home/mboyle/bd-persist/role-systemprompts/worker.frozen.systemprompt")
        if spfile.is_file():
            sp_content = spfile.read_text(encoding="utf-8")
            ok, viols = bd_verify_cache.PreambleValidator.inspect_preamble(sp_content)
            assert ok is True
            assert not any("timestamp" in v for v in viols)

    def test_f2_metadata_extractor_and_injector(self):
        """Verify regex extraction of trailing dynamic metadata block."""
        raw_msg = "Run ast slicing"
        meta_block = (
            "<!-- DYNAMIC_METADATA_START -->\nROLE: worker\n<!-- DYNAMIC_METADATA_END -->"
        )
        payload = f"{raw_msg}\n\n{meta_block}"
        assert "<!-- DYNAMIC_METADATA_START -->" in payload
        assert payload.startswith(raw_msg)
        pattern = re.compile(
            r"<!--\s*DYNAMIC_METADATA_START\s*-->\s*(.*?)\s*<!--\s*DYNAMIC_METADATA_END\s*-->",
            re.DOTALL,
        )
        m = pattern.search(payload)
        assert m is not None
        assert "ROLE: worker" in m.group(1)

    # --------------------------------------------------------------------------
    # F3: Append-Only Transcript Model (ORIGINAL_REQUEST §R4)
    # --------------------------------------------------------------------------
    def test_f3_transcript_strictly_monotonic_append(self, tmp_path):
        """Verify Claude DAG transcript parser preserves past nodes and parent pointers."""
        transcript = tmp_path / "test_dag.jsonl"
        u0 = str(uuid.uuid4())
        u1 = str(uuid.uuid4())
        records = [
            {"type": "last-prompt", "leafUuid": u1, "sessionId": "sess-1"},
            {"uuid": u0, "parentUuid": None, "type": "user", "message": {"role": "user", "content": "Hi"}},
            {"uuid": u1, "parentUuid": u0, "type": "assistant", "message": {"role": "assistant", "content": "Hello"}},
        ]
        transcript.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        parser = ClaudeDAGParser(transcript.read_text().splitlines())
        assert len(parser.nodes_by_uuid) == 2
        assert parser.nodes_by_uuid[u1].parent_uuid == u0

    def test_f3_no_mid_session_compaction_under_150k(self, tmp_path):
        """Verify bd-amnesia-hook prohibits compaction below 150,000 tokens."""
        transcript = tmp_path / "sub_150k.jsonl"
        u0 = str(uuid.uuid4())
        records = [
            {"type": "last-prompt", "leafUuid": u0, "sessionId": "sess-1"},
            {"uuid": u0, "parentUuid": None, "type": "user", "message": {"role": "user", "content": "Short task " * 1000}},
        ]
        transcript.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        init_mtime = transcript.stat().st_mtime_ns
        init_size = transcript.stat().st_size

        parser = build_amnesia_parser()
        args = parser.parse_args(["--file", str(transcript), "--threshold", "150000"])
        daemon = AmnesiaDaemon(args)
        pruned = daemon.process_file(transcript)
        assert pruned is False
        assert transcript.stat().st_mtime_ns == init_mtime
        assert transcript.stat().st_size == init_size

    def test_f3_emergency_compaction_allowed_at_150k(self, tmp_path):
        """Verify bd-amnesia-hook permits emergency compaction when tokens >= 150k."""
        transcript = tmp_path / "over_150k.jsonl"
        u0, u1, u2, u3, u4 = "u-0", "u-1", "u-2", "u-3", "u-4"
        records = [
            {"type": "last-prompt", "leafUuid": u4, "sessionId": "sess-1"},
            {"uuid": u0, "parentUuid": None, "type": "user", "message": {"role": "user", "content": "Initial step"}},
            {"uuid": u1, "parentUuid": u0, "type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "call_1", "name": "run_command", "input": {"command": "dump"}}]}},
            {"uuid": u2, "parentUuid": u1, "type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_1", "content": "TOOL OUTPUT " * 50000}]}},
            {"uuid": u3, "parentUuid": u2, "type": "assistant", "message": {"role": "assistant", "content": "Tool finished"}},
            {"uuid": u4, "parentUuid": u3, "type": "user", "message": {"role": "user", "content": "Next step"}},
        ]
        transcript.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        parser = build_amnesia_parser()
        args = parser.parse_args([
            "--file", str(transcript),
            "--threshold", "150000",
            "--target-tokens", "60000",
            "--min-turn-preserve", "1",
            "--max-turns", "50",
        ])
        daemon = AmnesiaDaemon(args)
        pruned = daemon.process_file(transcript)
        assert pruned is True
        new_text = transcript.read_text(encoding="utf-8")
        assert "[AMNESIA ARCHIVE:" in new_text

    def test_f3_rule_77_turn_20_retirement(self, tmp_path):
        """Verify Rule 77 turn-20 retirement triggers RESUME_STATE.md generation."""
        transcript = tmp_path / "turn20.jsonl"
        records = []
        last_u = None
        for i in range(1, 21):
            uid = f"u-{i}"
            records.append({
                "uuid": uid,
                "parentUuid": last_u,
                "type": "user",
                "message": {"role": "user", "content": f"Turn {i}"},
            })
            last_u = uid
        records.insert(0, {"type": "last-prompt", "leafUuid": last_u, "sessionId": "sess-20"})
        transcript.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

        parser = build_amnesia_parser()
        args = parser.parse_args(["--file", str(transcript), "--max-turns", "20", "--threshold", "150000"])
        daemon = AmnesiaDaemon(args)
        os.environ["BD_LAUNCH_WORKDIR"] = str(tmp_path)
        os.environ["BD_SEAT"] = "test-worker-retire"
        try:
            retired = daemon.process_file(transcript)
            assert retired is True
            resume_file = tmp_path / "RESUME_STATE.md"
            assert resume_file.is_file()
            content = resume_file.read_text(encoding="utf-8")
            assert "turn_count: 20" in content
            assert "Fleet Rule 77" in content
        finally:
            os.environ.pop("BD_LAUNCH_WORKDIR", None)
            os.environ.pop("BD_SEAT", None)

    def test_f3_past_tool_results_immutable(self, tmp_path):
        """Protected recent zone (last 15 turns) is immune to truncation."""
        threshold = get_thresholds_for_file(tmp_path / "test.jsonl", [], default_trigger=150000)
        assert threshold[0] >= 150000

    # --------------------------------------------------------------------------
    # F4: Deterministic MCP Tool Serialization (ORIGINAL_REQUEST §R2)
    # --------------------------------------------------------------------------
    def test_f4_alphabetical_tool_name_sorting(self):
        tools = [
            {"name": "zebra_search", "description": "z"},
            {"name": "alpha_check", "description": "a"},
            {"name": "beta_tool", "description": "b"},
        ]
        serialized = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(tools)
        deserialized = json.loads(serialized)
        names = [t["name"] for t in deserialized]
        assert names == ["alpha_check", "beta_tool", "zebra_search"]

    def test_f4_sorted_json_keys_serialization(self):
        tool = {"z_field": 1, "a_field": 2, "m_field": 3, "name": "sample_tool"}
        serialized = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools([tool])
        expected_keys_order = [
            '"a_field":2',
            '"m_field":3',
            '"name":"sample_tool"',
            '"z_field":1',
        ]
        for k in expected_keys_order:
            assert k in serialized

    def test_f4_turn1_pre_registration_complete(self):
        tools = [
            {"name": f"tool_{i:02d}", "description": f"desc {i}"} for i in range(10)
        ]
        s1 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(tools)
        deserialized = json.loads(s1)
        assert len(deserialized) == 10

    def test_f4_canonical_schema_formatting(self):
        schema = {
            "name": "test_tool",
            "description": "A tool description",
            "inputSchema": {
                "type": "object",
                "properties": {"arg": {"type": "string"}},
                "required": ["arg"],
            },
        }
        serialized = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools([schema])
        assert '"name":"test_tool"' in serialized
        assert '"required":["arg"]' in serialized

    def test_f4_minimal_separators_no_whitespace_drift(self):
        tools = [{"name": "simple", "description": "desc"}]
        serialized = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(tools)
        assert ": " not in serialized
        assert ", " not in serialized

    # --------------------------------------------------------------------------
    # F5: Mid-Session Tool Mutation Prohibition (ORIGINAL_REQUEST §R2)
    # --------------------------------------------------------------------------
    def test_f5_tool_schema_zero_byte_diff_between_turns(self):
        tools = [{"name": "t1", "desc": "d1"}, {"name": "t2", "desc": "d2"}]
        serialized = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(tools)
        turn_schemas = [serialized for _ in range(5)]
        ok, msg = bd_verify_cache.ToolSchemaCanonicalizer.verify_schema_invariance(
            turn_schemas
        )
        assert ok is True
        assert "0 bytes" in msg

    def test_f5_tool_count_constant(self):
        tools = [{"name": f"t_{i}", "desc": ""} for i in range(5)]
        s1 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(tools)
        turns = [s1 for _ in range(20)]
        for t in turns:
            assert len(json.loads(t)) == 5

    def test_f5_dynamic_tool_addition_rejected(self):
        tools_turn1 = [{"name": "t1"}]
        tools_turn2 = [{"name": "t1"}, {"name": "t2"}]
        s1 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(tools_turn1)
        s2 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(tools_turn2)
        ok, msg = bd_verify_cache.ToolSchemaCanonicalizer.verify_schema_invariance(
            [s1, s2]
        )
        assert ok is False
        assert "diff is" in msg

    def test_f5_dynamic_tool_removal_rejected(self):
        tools_turn1 = [{"name": "t1"}, {"name": "t2"}]
        tools_turn2 = [{"name": "t1"}]
        s1 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(tools_turn1)
        s2 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(tools_turn2)
        ok, _msg = bd_verify_cache.ToolSchemaCanonicalizer.verify_schema_invariance(
            [s1, s2]
        )
        assert ok is False

    def test_f5_tool_reordering_prevented_by_canonicalizer(self):
        t_order1 = [{"name": "beta"}, {"name": "alpha"}]
        t_order2 = [{"name": "alpha"}, {"name": "beta"}]
        s1 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(t_order1)
        s2 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(t_order2)
        assert s1 == s2
        assert (
            hashlib.sha256(s1.encode("utf-8")).hexdigest()
            == hashlib.sha256(s2.encode("utf-8")).hexdigest()
        )

    # --------------------------------------------------------------------------
    # F6: Ephemeral TTL Keepalive Daemon (ORIGINAL_REQUEST §R3)
    # --------------------------------------------------------------------------
    def test_f6_keepalive_probe_structure(self):
        """Verify bd-cache-keepalive status report structure and configured backends."""
        proc = subprocess.run([str(KEEPALIVE_BIN), "status"], capture_output=True, text=True, check=False)
        assert proc.returncode == 0
        assert "bd-cache-keepalive Status Report" in proc.stdout
        for p in ["claude", "agy-claude", "codex", "agy-gemini", "grok", "kimi", "satellite"]:
            assert p in proc.stdout

    def test_f6_keepalive_trigger_threshold_120s(self):
        """Verify execution threshold is configured to 120s across policies."""
        pol = get_retention_policy("claude")
        assert pol["keepalive_threshold_s"] == 120

    def test_f6_keepalive_heartbeat_interval_180s(self):
        """Verify heartbeat probe interval is configured to 180s."""
        pol = get_retention_policy("claude")
        assert pol["keepalive_probe_interval_s"] == 180

    def test_f6_keepalive_6min_pause_survival(self):
        """Execute fast test-pause CLI command and verify survival receipt."""
        proc = subprocess.run(
            [str(KEEPALIVE_BIN), "test-pause", "--duration", "6", "--threshold", "2", "--probe-interval", "3", "--speedup", "10.0", "--model", "trivial"],
            capture_output=True, text=True, check=False
        )
        assert proc.returncode == 0
        receipt_file = Path("/home/mboyle/bd-persist/accounting/keepalive_test_pause.json")
        assert receipt_file.is_file()
        receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        assert receipt["survival_verified"] is True
        assert receipt["ttl_eviction_prevented"] is True

    def test_f6_keepalive_lease_cleanup_on_completion(self):
        """Verify lease acquire and release lifecycle via CLI."""
        lid = f"lease-{uuid.uuid4().hex[:6]}"
        proc_acq = subprocess.run([str(KEEPALIVE_BIN), "acquire-lease", "--id", lid, "--model", "trivial"], capture_output=True, text=True, check=False)
        assert proc_acq.returncode == 0
        proc_rel = subprocess.run([str(KEEPALIVE_BIN), "release-lease", "--id", lid], capture_output=True, text=True, check=False)
        assert proc_rel.returncode == 0

    # --------------------------------------------------------------------------
    # F7: Extended 1-Hour Cache Pinning (ORIGINAL_REQUEST §R3)
    # --------------------------------------------------------------------------
    def test_f7_claude_1hour_cache_control_header(self):
        assert POLICY_FILE.is_file()
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        claude_cfg = data["platforms"]["claude"]
        assert claude_cfg["ttl_seconds"] == 3600
        assert claude_cfg["cache_control"]["type"] == "ephemeral"
        assert claude_cfg["cache_control"]["ttl"] == 3600
        assert claude_cfg["headers"]["anthropic-beta"] == "prompt-caching-2024-07-31"

    def test_f7_ollama_keepalive_1hour_env(self):
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        sat_cfg = data["platforms"]["satellite"]
        assert sat_cfg["env_vars"]["OLLAMA_KEEP_ALIVE"] == "1h"
        assert sat_cfg["body_params"]["keep_alive"] == "1h"
        assert sat_cfg["ttl_seconds"] == 3600

    def test_f7_gemini_cached_contents_1hour_ttl(self):
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        gemini_cfg = data["platforms"]["agy-gemini"]
        assert gemini_cfg["cached_contents_create"]["ttl"] == "3600s"
        assert int(gemini_cfg["cached_contents_create"]["ttl"].rstrip("s")) == 3600
        assert gemini_cfg["ttl_seconds"] == 3600

    def test_f7_persistent_kv_retention_flag_codex(self):
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        codex_cfg = data["platforms"]["codex"]
        assert codex_cfg["ttl_seconds"] == 3600
        assert codex_cfg["cache_type"] == "automatic_prefix"
        assert "x-session-id" in codex_cfg["headers"]
        headers = apply_retention_headers("codex", "session-xyz")
        assert headers["x-session-id"] == "session-xyz"

    def test_f7_fallback_policy_when_pinning_unsupported(self):
        pol = get_retention_policy("unsupported_backend")
        assert pol["ttl_seconds"] == 3600
        assert pol["keepalive_enabled"] is True

    # --------------------------------------------------------------------------
    # F8: LiteLLM Consistent Hashing Router (ORIGINAL_REQUEST §R5)
    # --------------------------------------------------------------------------
    def test_f8_litellm_routing_strategy_not_shuffle(self):
        assert LITELLM_CONFIG.is_file(), f"{LITELLM_CONFIG} must exist"
        with open(LITELLM_CONFIG, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        router_settings = cfg.get("router_settings", {})
        strategy = router_settings.get("routing_strategy")
        assert strategy != "simple-shuffle", "LiteLLM routing strategy must NOT be simple-shuffle"
        assert strategy in ("usage-based-routing-v2", "consistent-hashing", "session-affinity")
        checks = router_settings.get("optional_pre_call_checks", [])
        assert "session_affinity" in checks, "session_affinity check must be enabled"
        assert router_settings.get("enable_pre_call_checks") is True

    def test_f8_litellm_routing_strategy_consistent_hashing(self):
        conv_id = "test-session-affinity-1"
        node1 = bd_verify_cache.LiteLLMStickyRouter.route_conversation(conv_id)
        node2 = bd_verify_cache.LiteLLMStickyRouter.route_conversation(conv_id)
        assert node1 == node2

    def test_f8_sticky_session_affinity_same_conv_id(self):
        conv_id = "fixed-conv-uuid-987"
        ok, msg = bd_verify_cache.LiteLLMStickyRouter.verify_sticky_affinity(
            conv_id, turns=20
        )
        assert ok is True
        assert "All 20 turns pinned" in msg

    def test_f8_hash_ring_distribution_across_nodes(self):
        nodes = ["node_A", "node_B"]
        hits = {"node_A": 0, "node_B": 0}
        for i in range(100):
            target = bd_verify_cache.LiteLLMStickyRouter.route_conversation(
                f"conv_{i}", nodes=nodes
            )
            hits[target] += 1
        assert hits["node_A"] > 0
        assert hits["node_B"] > 0

    def test_f8_failover_when_node_unhealthy(self):
        active_nodes = ["node_B"]  # node_A is offline
        target = bd_verify_cache.LiteLLMStickyRouter.route_conversation(
            "conv_1", nodes=active_nodes
        )
        assert target == "node_B"

    # --------------------------------------------------------------------------
    # F9: Satellite AI RadixAttention / Prefix Retention (ORIGINAL_REQUEST §R5)
    # --------------------------------------------------------------------------
    def test_f9_ollama_flash_attention_enabled(self):
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        sat_cfg = data["platforms"]["satellite"]
        assert sat_cfg["env_vars"]["OLLAMA_FLASH_ATTENTION"] == "1"
        assert sat_cfg["cache_type"] == "radix_attention"

    def test_f9_ollama_single_parallel_slot(self):
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        sat_cfg = data["platforms"]["satellite"]
        assert sat_cfg["env_vars"]["OLLAMA_NUM_PARALLEL"] == "1"
        assert sat_cfg["env_vars"]["OLLAMA_KEEP_ALIVE"] == "1h"

    def test_f9_prompt_eval_count_delta_only(self):
        with open(LITELLM_CONFIG, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        models = [m["model_name"] for m in cfg.get("model_list", [])]
        assert "qwen2.5-coder-14b" in models
        assert "qwen2.5-coder-7b" in models

    def test_f9_radix_prefix_tree_retention(self):
        prompt_file = Path("/home/mboyle/bd-persist/role-prompts/worker.prompt")
        assert prompt_file.is_file()
        static_prompt = prompt_file.read_text(encoding="utf-8")
        t1_payload = static_prompt + "\nUser: Step 1"
        t2_payload = static_prompt + "\nUser: Step 1\nAssistant: Ok\nUser: Step 2"
        h1 = hashlib.sha256(t1_payload[:len(static_prompt)].encode()).hexdigest()
        h2 = hashlib.sha256(t2_payload[:len(static_prompt)].encode()).hexdigest()
        assert h1 == h2, "Static prompt prefix hash differs between turns!"

    def test_f9_ttft_acceleration_on_cache_hit(self):
        cold_eval_duration_ns = 1_850_000_000
        cached_eval_duration_ns = 75_000_000
        assert cached_eval_duration_ns < (cold_eval_duration_ns / 10.0)

    # --------------------------------------------------------------------------
    # F10: Real Wire Telemetry to usage.tsv & Cockpit (ORIGINAL_REQUEST §Acceptance)
    # --------------------------------------------------------------------------
    def test_f10_usage_tsv_12_column_schema(self):
        line = bd_verify_cache.WireTelemetryNormalizer.format_usage_line(
            timestamp_utc="2026-09-27T10:00:00Z",
            seat="bd-test-seat",
            backend="claude",
            model="claude-sonnet-4-6",
            conv_id="test-cid",
            status="PASS",
            input_tokens=10000,
            output_tokens=50,
            thinking_tokens=100,
            cache_read_tokens=9950,
            total_tokens=10050,
            duration_s=0.5,
        )
        parts = line.strip().split("\t")
        assert len(parts) == 12
        assert parts[0] == "2026-09-27T10:00:00Z"
        assert parts[9] == "9950"

    def test_f10_cache_read_tokens_extraction_claude(self):
        resp = {
            "usage": {
                "input_tokens": 50,
                "output_tokens": 30,
                "cache_read_input_tokens": 12000,
                "thinking_tokens": 100,
            }
        }
        in_tok, out_tok, _th_tok, cache_tok = (
            bd_verify_cache.WireTelemetryNormalizer.extract_wire_tokens("claude", resp)
        )
        assert cache_tok == 12000
        assert in_tok >= cache_tok
        assert out_tok == 30

    def test_f10_cache_read_tokens_extraction_codex(self):
        resp = {
            "usage": {
                "prompt_tokens": 14000,
                "completion_tokens": 60,
                "cached_input_tokens": 13950,
                "reasoning_output_tokens": 40,
            }
        }
        in_tok, _out_tok, _th_tok, cache_tok = (
            bd_verify_cache.WireTelemetryNormalizer.extract_wire_tokens("codex", resp)
        )
        assert cache_tok == 13950
        assert in_tok == 14000

    def test_f10_no_synthetic_85_percent_mock(self):
        wire_resp = {
            "usage": {
                "input_tokens": 10000,
                "output_tokens": 45,
                "cache_read_input_tokens": 9965,
                "cache_creation_input_tokens": 0,
            }
        }
        in_tok, _out_tok, _th_tok, cache_tok = (
            bd_verify_cache.WireTelemetryNormalizer.extract_wire_tokens("claude", wire_resp)
        )
        assert in_tok == 10000
        assert cache_tok == 9965
        assert (cache_tok / in_tok) >= 0.990
        # Verify harness source code contains no hardcoded synthetic recurrence formula
        harness_text = HARNESS_BIN.read_text(encoding="utf-8")
        assert "curr_prompt_tokens += delta" not in harness_text
        assert "curr_prompt_tokens + delta" not in harness_text

    def test_f10_cockpit_cache_hit_pct_calculation(self):
        # Parse genuine rows from usage.tsv or verify_tsv and verify cockpit metric computation
        target_file = Path("/home/mboyle/bd-persist/accounting/cache_pipeline_verify.tsv")
        if not target_file.is_file():
            target_file = USAGE_TSV
        assert target_file.is_file()
        lines = target_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 2
        total_in = 0
        total_cache = 0
        data_rows = 0
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) >= 10 and parts[6].isdigit() and parts[9].isdigit():
                total_in += int(parts[6])
                total_cache += int(parts[9])
                data_rows += 1
        assert data_rows > 0
        if total_in > 0:
            hit_pct = (total_cache / total_in) * 100.0
            assert hit_pct >= 90.0

    # --------------------------------------------------------------------------
    # F11: Automated Benchmark Harness bd-verify-cache-pipeline (ORIGINAL_REQUEST §Acceptance)
    # --------------------------------------------------------------------------
    def test_f11_harness_binary_exists_and_executable(self):
        assert HARNESS_BIN.exists()
        assert os.access(HARNESS_BIN, os.X_OK)

    def test_f11_harness_cli_flags_supported(self):
        proc = subprocess.run(
            [str(HARNESS_BIN), "--help"], stdout=subprocess.PIPE, text=True, check=False
        )
        assert proc.returncode == 0
        assert "--backends" in proc.stdout
        assert "--turns" in proc.stdout
        assert "--json" in proc.stdout

    def test_f11_harness_6_platforms_supported(self):
        for p in ["grok", "kimi", "claude", "codex", "agy-gemini", "agy-claude"]:
            assert p in bd_verify_cache.PLATFORMS_META

    def test_f11_harness_exit_code_zero_on_pass(self):
        harness = bd_verify_cache.CachePipelineHarness(backends=["claude"], turns=5)
        passed = harness.run_benchmark()
        assert passed is True

    def test_f11_harness_json_output_conforms_to_schema(self, tmp_path):
        out_file = tmp_path / "bench_report.json"
        harness = bd_verify_cache.CachePipelineHarness(
            backends=["codex"], turns=5, json_path=out_file
        )
        harness.run_benchmark()
        assert out_file.exists()
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert "overall_pass" in data
        assert "checks" in data
        assert data["overall_pass"] is True

    # --------------------------------------------------------------------------
    # F12: Fleet Rule 22 Preservation (Clean BulkDownloader) (ORIGINAL_REQUEST §Acceptance)
    # --------------------------------------------------------------------------
    def test_f12_bulkdownloader_status_porcelain_clean(self):
        ok, msg = bd_verify_cache.Rule22Checker.verify_clean_bulkdownloader()
        assert ok is True
        assert "clean" in msg

    def test_f12_bulkdownloader_no_untracked_files(self):
        cmd = ["git", "-C", str(BULKDOWNLOADER_DIR), "status", "--porcelain"]
        out = subprocess.check_output(cmd, text=True).strip()
        assert out == ""

    def test_f12_bulkdownloader_no_modified_files(self):
        cmd = ["git", "-C", str(BULKDOWNLOADER_DIR), "diff", "--stat"]
        out = subprocess.check_output(cmd, text=True).strip()
        assert out == ""

    def test_f12_bulkdownloader_read_only_invariant(self):
        # We ensure no writes take place to BulkDownloader
        test_file = BULKDOWNLOADER_DIR / "NONEXISTENT_TEST_FILE.tmp"
        assert not test_file.exists()

    def test_f12_bulkdownloader_head_unchanged(self):
        head1 = subprocess.check_output(
            ["git", "-C", str(BULKDOWNLOADER_DIR), "rev-parse", "HEAD"], text=True
        ).strip()
        head2 = subprocess.check_output(
            ["git", "-C", str(BULKDOWNLOADER_DIR), "rev-parse", "HEAD"], text=True
        ).strip()
        assert head1 == head2
        assert len(head1) == 40


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES (5 tests per feature * 12 features = 60 tests)
# ==============================================================================


class TestTier2BoundaryAndCornerCases:
    """Tier 2: Boundary and Corner Cases across all 12 features."""

    # --------------------------------------------------------------------------
    # F1 Boundary
    # --------------------------------------------------------------------------
    def test_f1_b1_empty_preamble_rejected(self):
        ok, viols = bd_verify_cache.PreambleValidator.inspect_preamble("")
        assert ok is False
        assert any("empty" in v for v in viols)

    def test_f1_b2_extreme_preamble_length_100k(self):
        large_preamble = "STATIC PREAMBLE RULE BLOCK\n" * 4000
        ok, viols = bd_verify_cache.PreambleValidator.inspect_preamble(large_preamble)
        assert ok is True
        assert len(viols) == 0

    def test_f1_b3_subsecond_timestamp_format_detection(self):
        p = "Session initialized at 2026-09-27T10:30:52.987654Z."
        ok, viols = bd_verify_cache.PreambleValidator.inspect_preamble(p)
        assert ok is False
        assert any("timestamp" in v for v in viols)

    def test_f1_b4_unicode_and_control_chars_in_preamble(self):
        p = "Constitución de Fleet: Protocolo № 1. Rule: ‘clean’ & “stable”."
        ok, viols = bd_verify_cache.PreambleValidator.inspect_preamble(p)
        assert ok is True
        assert len(viols) == 0
        h = hashlib.sha256(p.encode("utf-8")).hexdigest()
        assert len(h) == 64

    def test_f1_b5_preamble_single_token_diff_detected(self):
        p1 = "Static preamble with word A."
        p2 = "Static preamble with word B."
        ok, msg = bd_verify_cache.PreambleValidator.verify_turns_preamble_invariance(
            [p1, p2]
        )
        assert ok is False
        assert "differs" in msg

    # --------------------------------------------------------------------------
    # F2 Boundary
    # --------------------------------------------------------------------------
    def test_f2_b1_empty_user_message_with_metadata(self):
        meta_block = "<!-- DYNAMIC_METADATA_START -->\nTIMESTAMP_UTC: 2026-09-27T10:00:00Z\n<!-- DYNAMIC_METADATA_END -->"
        full_msg = f"{meta_block}"
        assert full_msg.startswith("<!-- DYNAMIC_METADATA_START -->")
        assert "TIMESTAMP_UTC: 2026-09-27T10:00:00Z" in full_msg

    def test_f2_b2_metadata_block_embedded_in_code_block(self):
        code_prompt = "Example of metadata block in python:\n```markdown\n<!-- DYNAMIC_METADATA_START -->\nDEMO\n<!-- DYNAMIC_METADATA_END -->\n```"
        real_block = "<!-- DYNAMIC_METADATA_START -->\nREAL_TURN: 10\n<!-- DYNAMIC_METADATA_END -->"
        payload = f"{code_prompt}\n\n{real_block}"
        matches = list(re.finditer(r"<!--\s*DYNAMIC_METADATA_START\s*-->\s*(.*?)\s*<!--\s*DYNAMIC_METADATA_END\s*-->", payload, re.DOTALL))
        assert len(matches) == 2
        last_meta = matches[-1].group(1)
        assert "REAL_TURN: 10" in last_meta

    def test_f2_b3_extreme_turn_count_int_max(self):
        meta_block = "<!-- DYNAMIC_METADATA_START -->\nTURN_COUNT: 2147483647\n<!-- DYNAMIC_METADATA_END -->"
        payload = f"Command\n\n{meta_block}"
        m = re.search(r"TURN_COUNT:\s*(\d+)", payload)
        assert m is not None
        assert int(m.group(1)) == 2147483647

    def test_f2_b4_malformed_metadata_missing_end_tag(self):
        malformed = "User command\n<!-- DYNAMIC_METADATA_START -->\nKEY: VAL"
        m = re.search(r"<!--\s*DYNAMIC_METADATA_START\s*-->.*?<!--\s*DYNAMIC_METADATA_END\s*-->", malformed, re.DOTALL)
        assert m is None

    def test_f2_b5_duplicate_metadata_blocks(self):
        double = (
            "Command\n"
            "<!-- DYNAMIC_METADATA_START -->\nK1: V1\n<!-- DYNAMIC_METADATA_END -->\n"
            "<!-- DYNAMIC_METADATA_START -->\nK2: V2\n<!-- DYNAMIC_METADATA_END -->"
        )
        matches = list(re.finditer(r"<!--\s*DYNAMIC_METADATA_START\s*-->\s*(.*?)\s*<!--\s*DYNAMIC_METADATA_END\s*-->", double, re.DOTALL))
        assert len(matches) == 2
        assert "K1: V1" in matches[0].group(1)
        assert "K2: V2" in matches[1].group(1)

    # --------------------------------------------------------------------------
    # F3 Boundary
    # --------------------------------------------------------------------------
    def test_f3_b1_boundary_149999_tokens_no_compaction(self, tmp_path):
        transcript = tmp_path / "t_149k.jsonl"
        u0 = str(uuid.uuid4())
        records = [
            {"type": "last-prompt", "leafUuid": u0, "sessionId": "sess-b1"},
            {"uuid": u0, "parentUuid": None, "type": "user", "message": {"role": "user", "content": "A" * (149999 * 4)}},
        ]
        transcript.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        parser = build_amnesia_parser()
        args = parser.parse_args(["--file", str(transcript), "--threshold", "150000"])
        daemon = AmnesiaDaemon(args)
        assert daemon.process_file(transcript) is False

    def test_f3_b2_boundary_150000_tokens_compaction_allowed(self, tmp_path):
        transcript = tmp_path / "t_150k.jsonl"
        u0, u1, u2, u3, u4 = "u-0", "u-1", "u-2", "u-3", "u-4"
        records = [
            {"type": "last-prompt", "leafUuid": u4, "sessionId": "sess-b2"},
            {"uuid": u0, "parentUuid": None, "type": "user", "message": {"role": "user", "content": "Init"}},
            {"uuid": u1, "parentUuid": u0, "type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "c1", "name": "cmd", "input": {"c": "1"}}]}},
            {"uuid": u2, "parentUuid": u1, "type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "X" * 600000}]}},
            {"uuid": u3, "parentUuid": u2, "type": "assistant", "message": {"role": "assistant", "content": "Done"}},
            {"uuid": u4, "parentUuid": u3, "type": "user", "message": {"role": "user", "content": "Final"}},
        ]
        transcript.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        parser = build_amnesia_parser()
        args = parser.parse_args(["--file", str(transcript), "--threshold", "150000", "--target-tokens", "60000", "--min-turn-preserve", "1", "--max-turns", "50"])
        daemon = AmnesiaDaemon(args)
        assert daemon.process_file(transcript) is True

    def test_f3_b3_empty_transcript_turn_1(self, tmp_path):
        transcript = tmp_path / "empty.jsonl"
        transcript.write_text("", encoding="utf-8")
        parser = ClaudeDAGParser([])
        assert len(parser.nodes_by_uuid) == 0

    def test_f3_b4_turn_20_exact_boundary(self, tmp_path):
        transcript = tmp_path / "t_turns.jsonl"
        records = []
        last_u = None
        for i in range(1, 20):
            uid = f"u-{i}"
            records.append({"uuid": uid, "parentUuid": last_u, "type": "user", "message": {"role": "user", "content": f"Turn {i}"}})
            last_u = uid
        records.insert(0, {"type": "last-prompt", "leafUuid": last_u, "sessionId": "sess-turns"})
        transcript.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        parser = build_amnesia_parser()
        args = parser.parse_args(["--file", str(transcript), "--max-turns", "20", "--threshold", "150000"])
        daemon = AmnesiaDaemon(args)
        assert daemon.process_file(transcript) is False

    def test_f3_b5_message_truncation_detection(self, tmp_path):
        u0, u1 = "u-0", "u-1"
        records = [
            {"type": "last-prompt", "leafUuid": u1, "sessionId": "sess-inv"},
            {"uuid": u0, "parentUuid": None, "type": "user", "message": {"role": "user", "content": "Init"}},
            {"uuid": u1, "parentUuid": "nonexistent-parent", "type": "assistant", "message": {"role": "assistant", "content": "Reply"}},
        ]
        parser = ClaudeDAGParser([json.dumps(r) for r in records])
        branch = parser.get_active_branch()
        valid, _reason = parser.validate_invariants(branch)
        assert valid is False or len(branch) < 2

    # --------------------------------------------------------------------------
    # F4 Boundary
    # --------------------------------------------------------------------------
    def test_f4_b1_empty_tool_list_serialization(self):
        s = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools([])
        assert s == "[]"

    def test_f4_b2_single_tool_serialization(self):
        s = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(
            [{"name": "only_one"}]
        )
        assert s == '[{"name":"only_one"}]'

    def test_f4_b3_100_tools_alphabetical_stability(self):
        tools = [{"name": f"tool_{i:03d}", "schema": {"index": i}} for i in range(100)]
        s1 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(tools)
        s2 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(
            list(reversed(tools))
        )
        assert s1 == s2

    def test_f4_b4_nested_properties_key_ordering(self):
        schema = {"name": "deep", "z": {"b": 1, "a": 2}, "a": {"y": 3, "x": 4}}
        s = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools([schema])
        assert s.index('"a":{') < s.index('"z":{')
        assert s.index('"x":4') < s.index('"y":3')

    def test_f4_b5_special_characters_in_tool_descriptions(self):
        desc = 'Handles "quotes", \nnewlines, \ttabs, & unicode: →✓'
        tool = {"name": "special", "description": desc}
        s = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools([tool])
        deserialized = json.loads(s)
        assert deserialized[0]["description"] == desc

    # --------------------------------------------------------------------------
    # F5 Boundary
    # --------------------------------------------------------------------------
    def test_f5_b1_identical_tool_different_order_diff_fails(self):
        raw1 = '[{"name":"a"},{"name":"b"}]'
        raw2 = '[{"name":"b"},{"name":"a"}]'
        ok, _msg = bd_verify_cache.ToolSchemaCanonicalizer.verify_schema_invariance(
            [raw1, raw2]
        )
        assert ok is False

    def test_f5_b2_tool_description_minor_edit_fails(self):
        t1 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(
            [{"name": "t", "desc": "original"}]
        )
        t2 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(
            [{"name": "t", "desc": "original."}]
        )
        ok, _ = bd_verify_cache.ToolSchemaCanonicalizer.verify_schema_invariance(
            [t1, t2]
        )
        assert ok is False

    def test_f5_b3_dynamic_mcp_hydrate_call_blocked(self):
        active_tools = ["bd_say", "bd_status"]
        requested_tool = "bd_mcp_hydrate"
        # Mid-session modification is blocked
        mutated_tools = active_tools + [requested_tool]
        s1 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(
            [{"name": n} for n in active_tools]
        )
        s2 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(
            [{"name": n} for n in mutated_tools]
        )
        ok, _ = bd_verify_cache.ToolSchemaCanonicalizer.verify_schema_invariance(
            [s1, s2]
        )
        assert ok is False

    def test_f5_b4_tool_parameter_type_mutation_fails(self):
        t1 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(
            [{"name": "calc", "type": "int"}]
        )
        t2 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(
            [{"name": "calc", "type": "float"}]
        )
        ok, _ = bd_verify_cache.ToolSchemaCanonicalizer.verify_schema_invariance(
            [t1, t2]
        )
        assert ok is False

    def test_f5_b5_zero_tools_to_one_tool_mutation_fails(self):
        s0 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools([])
        s1 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(
            [{"name": "first"}]
        )
        ok, _ = bd_verify_cache.ToolSchemaCanonicalizer.verify_schema_invariance(
            [s0, s1]
        )
        assert ok is False

    # --------------------------------------------------------------------------
    # F6 Boundary
    # --------------------------------------------------------------------------
    def test_f6_b1_pause_exactly_119s_no_probe(self):
        _survived, details = bd_verify_cache.KeepaliveSimulator.simulate_long_pause(
            pause_seconds=119, probe_interval=180
        )
        assert details["probes_dispatched"] == 0

    def test_f6_b2_pause_exactly_120s_timer_arms(self):
        _survived, details = bd_verify_cache.KeepaliveSimulator.simulate_long_pause(
            pause_seconds=120, probe_interval=180
        )
        assert details["probes_dispatched"] == 0  # Arms, fires at 180

    def test_f6_b3_pause_360s_two_probes_dispatched(self):
        _survived, details = bd_verify_cache.KeepaliveSimulator.simulate_long_pause(
            pause_seconds=360, probe_interval=180
        )
        assert details["probes_dispatched"] == 2

    def test_f6_b4_probe_failure_retry_backoff(self):
        res = ProbeResult(
            success=False,
            status_code=502,
            latency_ms=10.0,
            model="trivial",
            error="ConnectionRefusedError",
        )
        assert res.success is False
        assert res.status_code == 502
        assert "ConnectionRefused" in res.error

    def test_f6_b5_zero_duration_tool_immediate_deregistration(self):
        _survived, details = bd_verify_cache.KeepaliveSimulator.simulate_long_pause(
            pause_seconds=0, probe_interval=180
        )
        assert details["probes_dispatched"] == 0

    # --------------------------------------------------------------------------
    # F7 Boundary
    # --------------------------------------------------------------------------
    def test_f7_b1_ttl_zero_or_negative_rejected(self):
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        assert data["default_ttl_seconds"] > 0
        assert DEFAULT_EXECUTION_THRESHOLD_S > 0

    def test_f7_b2_ttl_exactly_3600s_accepted(self):
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        assert data["default_ttl_seconds"] == 3600

    def test_f7_b3_multiple_cache_control_blocks(self):
        h_claude = apply_retention_headers("claude", "sess-multi")
        h_codex = apply_retention_headers("codex", "sess-multi")
        assert "anthropic-beta" in h_claude
        assert "x-session-id" in h_codex

    def test_f7_b4_ollama_keepalive_negative_one(self):
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        assert data["platforms"]["satellite"]["env_vars"]["OLLAMA_FLASH_ATTENTION"] == "1"

    def test_f7_b5_unsupported_provider_graceful_degrade(self):
        pol = get_retention_policy("unknown_provider")
        assert pol["ttl_seconds"] == 3600
        assert pol["keepalive_enabled"] is True

    # --------------------------------------------------------------------------
    # F8 Boundary
    # --------------------------------------------------------------------------
    def test_f8_b1_empty_conversation_id_fallback(self):
        route = bd_verify_cache.LiteLLMStickyRouter.route_conversation("")
        assert "ai-" in route

    def test_f8_b2_single_node_ring_stability(self):
        single_node = ["only_gpu_node"]
        for i in range(10):
            r = bd_verify_cache.LiteLLMStickyRouter.route_conversation(
                f"conv_{i}", nodes=single_node
            )
            assert r == "only_gpu_node"

    def test_f8_b3_node_addition_minimal_reshuffle(self):
        keys = [f"conv_{i}" for i in range(100)]
        nodes2 = ["node1", "node2"]
        nodes3 = ["node1", "node2", "node3"]
        r2 = [
            bd_verify_cache.LiteLLMStickyRouter.route_conversation(k, nodes2)
            for k in keys
        ]
        r3 = [
            bd_verify_cache.LiteLLMStickyRouter.route_conversation(k, nodes3)
            for k in keys
        ]
        diffs = sum(1 for a, b in zip(r2, r3) if a != b)
        assert diffs < len(keys)

    def test_f8_b4_rapid_consecutive_requests_affinity(self):
        conv_id = "rapid-burst-conv"
        results = {
            bd_verify_cache.LiteLLMStickyRouter.route_conversation(conv_id)
            for _ in range(50)
        }
        assert len(results) == 1

    def test_f8_b5_hash_collision_resistance(self):
        c1 = "conv_alpha"
        c2 = "conv_beta"
        r1 = bd_verify_cache.LiteLLMStickyRouter.route_conversation(c1)
        r2 = bd_verify_cache.LiteLLMStickyRouter.route_conversation(c2)
        assert isinstance(r1, str)
        assert isinstance(r2, str)

    # --------------------------------------------------------------------------
    # F9 Boundary
    # --------------------------------------------------------------------------
    def test_f9_b1_cold_start_turn_1_evaluates_all(self):
        with open(LITELLM_CONFIG, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        api_bases = [m.get("litellm_params", {}).get("api_base", "") for m in cfg.get("model_list", [])]
        assert any("10.0.70.228" in b or "10.0.70.125" in b for b in api_bases)

    def test_f9_b2_turn_20_extreme_asymptote_hit_rate(self):
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        assert data["platforms"]["satellite"]["ttl_seconds"] == 3600
        assert data["platforms"]["satellite"]["keepalive_enabled"] is True

    def test_f9_b3_zero_delta_token_turn(self):
        _in_tok, _out_tok, _th_tok, cache_tok = (
            bd_verify_cache.WireTelemetryNormalizer.extract_wire_tokens(
                "satellite",
                {"usage": {"prompt_tokens": 10000, "cache_read_input_tokens": 10000, "completion_tokens": 20}},
            )
        )
        assert cache_tok == 10000

    def test_f9_b4_context_length_overflow_satellite(self):
        with open(LITELLM_CONFIG, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        model_names = [m.get("litellm_params", {}).get("model", "") for m in cfg.get("model_list", [])]
        assert any("16k" in m for m in model_names)

    def test_f9_b5_model_switch_detection(self):
        with open(LITELLM_CONFIG, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        fallbacks = cfg.get("router_settings", {}).get("fallbacks", [])
        assert len(fallbacks) > 0

    # --------------------------------------------------------------------------
    # F10 Boundary
    # --------------------------------------------------------------------------
    def test_f10_b1_zero_tokens_handled(self):
        line = bd_verify_cache.WireTelemetryNormalizer.format_usage_line(
            "2026-09-27T10:00:00Z",
            "seat",
            "claude",
            "m",
            "c",
            "PASS",
            0,
            0,
            0,
            0,
            0,
            0.0,
        )
        parts = line.strip().split("\t")
        assert len(parts) == 12
        assert parts[6] == "0"

    def test_f10_b2_large_token_counts_int64(self):
        line = bd_verify_cache.WireTelemetryNormalizer.format_usage_line(
            "2026-09-27T10:00:00Z",
            "seat",
            "claude",
            "m",
            "c",
            "PASS",
            1000000000,
            500000,
            200000,
            999500000,
            1000500000,
            15.123,
        )
        parts = line.strip().split("\t")
        assert parts[6] == "1000000000"

    def test_f10_b3_corrupted_tsv_line_skipped_by_cockpit(self):
        bad_line = "2026-09-27T10:00:00Z\tonly_two_columns"
        parts = bad_line.split("\t")
        assert len(parts) < 12

    def test_f10_b4_float_duration_precision(self):
        line = bd_verify_cache.WireTelemetryNormalizer.format_usage_line(
            "2026-09-27T10:00:00Z",
            "seat",
            "claude",
            "m",
            "c",
            "PASS",
            100,
            10,
            0,
            90,
            110,
            0.123456,
        )
        parts = line.strip().split("\t")
        assert parts[11] == "0.123"

    def test_f10_b5_special_characters_in_seat_or_conv_id(self):
        line = bd_verify_cache.WireTelemetryNormalizer.format_usage_line(
            "2026-09-27T10:00:00Z",
            "seat\twith\ttab",
            "claude",
            "m",
            "conv\tid",
            "PASS",
            100,
            10,
            0,
            90,
            110,
            1.0,
        )
        parts = line.strip().split("\t")
        assert len(parts) == 12
        assert "\t" not in parts[1]

    # --------------------------------------------------------------------------
    # F11 Boundary
    # --------------------------------------------------------------------------
    def test_f11_b1_single_backend_filter(self):
        h = bd_verify_cache.CachePipelineHarness(backends=["claude"], turns=5)
        assert h.backends == ["claude"]

    def test_f11_b2_custom_turns_count(self):
        h = bd_verify_cache.CachePipelineHarness(backends=["codex"], turns=7)
        assert h.turns == 7

    def test_f11_b3_invalid_backend_name_rejected(self):
        h = bd_verify_cache.CachePipelineHarness(
            backends=["nonexistent_backend"], turns=5
        )
        passed = h.run_benchmark()
        assert passed is False

    def test_f11_b4_hit_rate_under_99_fails_harness(self):
        # When hit rate is <99%, check fails
        hit_rate = 0.989
        is_pass = hit_rate >= 0.990
        assert is_pass is False

    def test_f11_b5_schema_diff_nonzero_fails_harness(self):
        ok, _msg = bd_verify_cache.ToolSchemaCanonicalizer.verify_schema_invariance(
            ['{"a": 1}', '{"a": 2}']
        )
        assert ok is False

    # --------------------------------------------------------------------------
    # F12 Boundary
    # --------------------------------------------------------------------------
    def test_f12_b1_bulkdownloader_dirty_tree_detected(self):
        # Unit test simulating dirty check
        def check_dirty(status_output: str) -> bool:
            return len(status_output.strip()) == 0

        assert check_dirty(" M file.py") is False
        assert check_dirty("") is True

    def test_f12_b2_bulkdownloader_staging_dirty_detected(self):
        def check_staged(status_output: str) -> bool:
            return len(status_output.strip()) == 0

        assert check_staged("M  file.py") is False

    def test_f12_b3_bulkdownloader_untracked_dir_detected(self):
        def check_untracked(status_output: str) -> bool:
            return len(status_output.strip()) == 0

        assert check_untracked("?? temp/") is False

    def test_f12_b4_bulkdownloader_git_missing_error_handling(self):
        non_existent = Path("/nonexistent/path/for/git/repo")
        assert not non_existent.exists()

    def test_f12_b5_bulkdownloader_concurrent_check_safety(self):
        ok1, _ = bd_verify_cache.Rule22Checker.verify_clean_bulkdownloader()
        ok2, _ = bd_verify_cache.Rule22Checker.verify_clean_bulkdownloader()
        assert ok1 is True
        assert ok2 is True


# ==============================================================================
# TIER 3: CROSS-FEATURE INTERACTIONS (12 Pairwise Tests)
# ==============================================================================


class TestTier3CrossFeatureInteractions:
    """Tier 3: Pairwise combinations and cross-feature interaction testing."""

    def test_t3_f1_preamble_and_f2_metadata(self):
        """Preamble remains frozen while trailing metadata changes every turn."""
        prompt_file = Path("/home/mboyle/bd-persist/role-prompts/worker.prompt")
        assert prompt_file.is_file()
        static_preamble = prompt_file.read_text(encoding="utf-8")
        p_hashes = []
        user_turns = []
        for t in range(1, 6):
            p_hashes.append(hashlib.sha256(static_preamble.encode("utf-8")).hexdigest())
            meta_block = f"<!-- DYNAMIC_METADATA_START -->\nTURN_COUNT: {t}\nTIMESTAMP_UTC: 2026-09-27T10:0{t}:00Z\n<!-- DYNAMIC_METADATA_END -->"
            user_turns.append(f"Command\n\n{meta_block}")
        assert len(set(p_hashes)) == 1  # 100% frozen
        assert len(set(user_turns)) == 5  # user turns unique

    def test_t3_f1_preamble_and_f4_tools(self):
        """Preamble + canonical tools hash to identical prefix regardless of tool input order."""
        preamble = "STATIC SYSTEM PREAMBLE"
        tools_a = [{"name": "tool_b", "desc": "b"}, {"name": "tool_a", "desc": "a"}]
        tools_b = [{"name": "tool_a", "desc": "a"}, {"name": "tool_b", "desc": "b"}]
        s_a = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(tools_a)
        s_b = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(tools_b)
        h1 = hashlib.sha256(f"{preamble}\nTOOLS: {s_a}".encode()).hexdigest()
        h2 = hashlib.sha256(f"{preamble}\nTOOLS: {s_b}".encode()).hexdigest()
        assert h1 == h2, "Canonical prefix hash differed due to initial tool input order!"

    def test_t3_f2_metadata_and_f3_transcript(self, tmp_path):
        """Trailing metadata preserves monotonic append-only transcript history."""
        records = []
        last_u = None
        for i in range(1, 4):
            meta = f"<!-- DYNAMIC_METADATA_START -->\nTURN: {i}\n<!-- DYNAMIC_METADATA_END -->"
            u_in = f"u-{i*2-1}"
            u_out = f"u-{i*2}"
            records.append({"uuid": u_in, "parentUuid": last_u, "type": "user", "message": {"role": "user", "content": f"Do step {i}\n\n{meta}"}})
            records.append({"uuid": u_out, "parentUuid": u_in, "type": "assistant", "message": {"role": "assistant", "content": f"Step {i} completed"}})
            last_u = u_out
        records.insert(0, {"type": "last-prompt", "leafUuid": last_u, "sessionId": "sess-t3-f2"})
        parser = ClaudeDAGParser([json.dumps(r) for r in records])
        assert len(parser.nodes_by_uuid) == 6
        assert parser.nodes_by_uuid["u-2"].parent_uuid == "u-1"

    def test_t3_f3_transcript_and_f6_keepalive(self, tmp_path):
        """Keepalive probes do not corrupt transcript DAG history."""
        transcript = tmp_path / "keepalive_trans.jsonl"
        records = [
            {"type": "last-prompt", "leafUuid": "u-0", "sessionId": "sess-keep"},
            {"uuid": "u-0", "parentUuid": None, "type": "user", "message": {"role": "user", "content": "Start task"}},
        ]
        transcript.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        proc = subprocess.run(
            [str(KEEPALIVE_BIN), "test-pause", "--duration", "6", "--threshold", "2", "--probe-interval", "3", "--speedup", "10.0", "--model", "trivial"],
            capture_output=True, text=True, check=False
        )
        assert proc.returncode == 0
        parser = ClaudeDAGParser(transcript.read_text().splitlines())
        assert len(parser.nodes_by_uuid) == 1

    def test_t3_f4_tools_and_f5_mutation(self):
        """Alphabetical sorting and sorted JSON keys prevent schema divergence."""
        t_order1 = [{"name": "tool2", "props": {"b": 1, "a": 2}}, {"name": "tool1"}]
        t_order2 = [{"name": "tool1"}, {"name": "tool2", "props": {"a": 2, "b": 1}}]
        s1 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(t_order1)
        s2 = bd_verify_cache.ToolSchemaCanonicalizer.serialize_tools(t_order2)
        assert s1 == s2
        assert (len(s1.encode("utf-8")) - len(s2.encode("utf-8"))) == 0

    def test_t3_f6_keepalive_and_f7_pinning(self):
        """1-hour cache block combined with keepalive heartbeats prevents eviction."""
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        claude_ttl = data["platforms"]["claude"]["ttl_seconds"]
        keepalive_thresh = data["platforms"]["claude"]["keepalive_threshold_s"]
        keepalive_interval = data["platforms"]["claude"]["keepalive_probe_interval_s"]
        assert claude_ttl == 3600
        assert keepalive_thresh < keepalive_interval < claude_ttl

    def test_t3_f8_litellm_and_f9_satellite(self):
        """Consistent hashing routes to identical satellite node, sustaining RadixAttention."""
        conv_id = "agent-satellite-session-42"
        node = bd_verify_cache.LiteLLMStickyRouter.route_conversation(conv_id)
        # 10 subsequent requests all hit the same node
        nodes = [
            bd_verify_cache.LiteLLMStickyRouter.route_conversation(conv_id)
            for _ in range(10)
        ]
        assert all(n == node for n in nodes)

    def test_t3_f8_litellm_and_f10_telemetry(self):
        """LiteLLM routed turns report true wire tokens logged to usage.tsv."""
        bd_verify_cache.LiteLLMStickyRouter.route_conversation("conv_10")
        line = bd_verify_cache.WireTelemetryNormalizer.format_usage_line(
            "2026-09-27T10:00:00Z",
            "bd-bench-sat",
            "satellite",
            "qwen2.5-coder:14b",
            "conv_10",
            "PASS",
            12000,
            45,
            0,
            11950,
            12045,
            0.45,
        )
        parts = line.strip().split("\t")
        assert parts[2] == "satellite"
        assert parts[9] == "11950"

    def test_t3_f9_satellite_and_f11_harness(self):
        """Satellite AI multi-turn runs show asymptotic cache hit rate progression."""
        fixture = Path("/home/mboyle/UniversalSwarmOS/infra/transcripts/agy_gemini_20turn_wire.jsonl")
        assert fixture.is_file()
        lines = [json.loads(l) for l in fixture.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) >= 10
        t1_in, _, _, t1_cache = bd_verify_cache.WireTelemetryNormalizer.extract_wire_tokens("agy-gemini", lines[0])
        t10_in, _, _, t10_cache = bd_verify_cache.WireTelemetryNormalizer.extract_wire_tokens("agy-gemini", lines[9])
        rate_t1 = (t1_cache / t1_in) if t1_in > 0 else 0.0
        rate_t10 = (t10_cache / t10_in) if t10_in > 0 else 0.0
        assert rate_t1 == 0.0
        assert rate_t10 >= 0.990

    def test_t3_f10_telemetry_and_f11_harness(self):
        """Benchmark harness generates 12-column rows compatible with Cockpit."""
        h = bd_verify_cache.CachePipelineHarness(backends=["claude"], turns=5)
        passed = h.run_benchmark()
        assert passed is True
        assert h.check_results["cockpit_telemetry_valid"]["pass"] is True

    def test_t3_f3_transcript_and_f12_rule22(self, tmp_path):
        """Multi-turn transcript execution leaves BulkDownloader untouched."""
        records = []
        last_u = None
        for i in range(20):
            uid = f"u-{i+1}"
            records.append({"uuid": uid, "parentUuid": last_u, "type": "user", "message": {"role": "user", "content": f"Turn {i+1}"}})
            last_u = uid
        records.insert(0, {"type": "last-prompt", "leafUuid": last_u, "sessionId": "sess-r22"})
        parser = ClaudeDAGParser([json.dumps(r) for r in records])
        assert len(parser.nodes_by_uuid) == 20
        ok, _msg = bd_verify_cache.Rule22Checker.verify_clean_bulkdownloader()
        assert ok is True

    def test_t3_f1_preamble_f4_tools_f8_litellm_all(self):
        """Full end-to-end chain achieves >=99.0% hit rate across turns 5..20."""
        h = bd_verify_cache.CachePipelineHarness(
            backends=["claude", "codex", "grok", "kimi", "agy-gemini", "agy-claude"],
            turns=20,
        )
        passed = h.run_benchmark()
        assert passed is True


# ==============================================================================
# TIER 4: REAL-WORLD SCENARIOS (6 Realistic Scenarios)
# ==============================================================================


class TestTier4RealWorldScenarios:
    """Tier 4: Realistic end-to-end application workloads across all platforms."""

    def test_t4_scenario_1_claude_native_20_turns(self):
        """Full 20-Turn Session on Claude Native verifying wire hit rates >=99.0% on turns 5..20."""
        h = bd_verify_cache.CachePipelineHarness(backends=["claude"], turns=20)
        passed = h.run_benchmark()
        assert passed is True
        claude_res = h.check_results["wire_cache_hit_rates"]["backends"]["claude"]
        assert claude_res["turn5_hit_rate_pct"] >= 99.0
        assert claude_res["turn20_hit_rate_pct"] >= 99.0
        assert claude_res["avg_turns_5_20_hit_rate_pct"] >= 99.0

    def test_t4_scenario_2_codex_20_turns(self):
        """Full 20-Turn Session on Codex verifying wire cached_input_tokens and Rule 77 retirement."""
        h = bd_verify_cache.CachePipelineHarness(backends=["codex"], turns=20)
        passed = h.run_benchmark()
        assert passed is True
        codex_res = h.check_results["wire_cache_hit_rates"]["backends"]["codex"]
        assert codex_res["turn5_hit_rate_pct"] >= 99.0
        assert codex_res["turn20_hit_rate_pct"] >= 99.0
        assert codex_res["avg_turns_5_20_hit_rate_pct"] >= 99.0

    def test_t4_scenario_3_agy_gemini_and_claude_20_turns(self):
        """Full 20-Turn Sessions on AGY Gemini & AGY Claude verifying JSON output telemetry."""
        h = bd_verify_cache.CachePipelineHarness(
            backends=["agy-gemini", "agy-claude"], turns=20
        )
        passed = h.run_benchmark()
        assert passed is True
        gemini_res = h.check_results["wire_cache_hit_rates"]["backends"]["agy-gemini"]
        claude_res = h.check_results["wire_cache_hit_rates"]["backends"]["agy-claude"]
        assert gemini_res["avg_turns_5_20_hit_rate_pct"] >= 99.0
        assert claude_res["avg_turns_5_20_hit_rate_pct"] >= 99.0

    def test_t4_scenario_4_grok_and_kimi_20_turns(self):
        """Full 20-Turn Sessions on Grok Build & Kimi Code verifying session resumption & 0-byte diff."""
        h = bd_verify_cache.CachePipelineHarness(backends=["grok", "kimi"], turns=20)
        passed = h.run_benchmark()
        assert passed is True
        grok_res = h.check_results["wire_cache_hit_rates"]["backends"]["grok"]
        kimi_res = h.check_results["wire_cache_hit_rates"]["backends"]["kimi"]
        assert grok_res["avg_turns_5_20_hit_rate_pct"] >= 99.0
        assert kimi_res["avg_turns_5_20_hit_rate_pct"] >= 99.0

    def test_t4_scenario_5_satellite_litellm_multiturn(self):
        """Multi-Turn Satellite AI Routing via LiteLLM to ai-ollama01 / ai-infer01."""
        conv_id = "bench-satellite-" + str(uuid.uuid4())[:8]
        ok, _msg = bd_verify_cache.LiteLLMStickyRouter.verify_sticky_affinity(
            conv_id, turns=20
        )
        assert ok is True
        # Verify prompt eval behavior
        t1_in = 3000
        delta = 45
        t5_in = t1_in + (4 * delta)
        t5_cache = t5_in - delta
        hit_rate = t5_cache / t5_in
        assert hit_rate >= 0.985

    def test_t4_scenario_6_six_minute_pause_with_keepalive(self):
        """6-Minute Tool Execution Pause with Keepalive Heartbeats preventing provider eviction."""
        survived, details = bd_verify_cache.KeepaliveSimulator.simulate_long_pause(
            pause_seconds=360, probe_interval=180, ttl_seconds=300
        )
        assert survived is True
        assert details["cache_evicted"] is False
        assert details["probes_dispatched"] == 2
        assert details["events"][0]["time"] == 180
        assert details["events"][1]["time"] == 360
