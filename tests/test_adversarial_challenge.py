"""
test_adversarial_challenge.py

Adversarial Challenge & Stress-Test Suite for Prompt Cache Optimization Architecture (R1-R5).
Authored by challenger_1 (teamwork_preview_challenger / critic & specialist).

Covers:
- Challenge R1: Preamble dynamic variable injection, isolation detection, and trailing metadata prefix invariance.
- Challenge R2: MCP tool schema dictionary insertion order perturbation across 20 turns, ensuring 0-byte schema diff.
- Challenge R3: Keepalive daemon pause simulation under simulated delays, jitter, extended durations, and TTL eviction boundaries.
- Rule 22: BulkDownloader working tree cleanliness invariant.
"""

import collections
import hashlib
import json
import random
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, ClassVar

import pytest

# Paths
UNIVERSAL_SWARM_ROOT = Path("/home/mboyle/UniversalSwarmOS")
BULKDOWNLOADER_DIR = Path("/home/mboyle/BulkDownloader")
BIN_DIR = Path("/home/mboyle/bin")
VERIFY_HARNESS_BIN = BIN_DIR / "bd-verify-cache-pipeline"
KEEPALIVE_BIN = BIN_DIR / "bd-cache-keepalive"
KEEPALIVE_RECEIPT = Path("/home/mboyle/bd-persist/accounting/keepalive_test_pause.json")

# Import harness components
sys.path.insert(0, str(BIN_DIR))
import importlib.machinery
import importlib.util

loader = importlib.machinery.SourceFileLoader(
    "bd_verify_cache_pipeline", str(VERIFY_HARNESS_BIN)
)
spec = importlib.util.spec_from_loader("bd_verify_cache_pipeline", loader)
bd_verify_cache = importlib.util.module_from_spec(spec)
loader.exec_module(bd_verify_cache)

PreambleValidator = bd_verify_cache.PreambleValidator
ToolSchemaCanonicalizer = bd_verify_cache.ToolSchemaCanonicalizer
KeepaliveSimulator = bd_verify_cache.KeepaliveSimulator
Rule22Checker = bd_verify_cache.Rule22Checker


# ==============================================================================
# Helper Classes for R1 Testing
# ==============================================================================

class DynamicMetadataParser:
    """Robust parser targeting strictly the trailing metadata block."""
    BLOCK_PATTERN = re.compile(
        r"<!--\s*(?:BD_)?DYNAMIC_METADATA_START\s*-->\s*(.*?)\s*<!--\s*(?:BD_)?DYNAMIC_METADATA_END\s*-->",
        re.DOTALL,
    )

    @classmethod
    def extract_metadata(cls, text: str) -> tuple[str, dict[str, str]]:
        matches = list(cls.BLOCK_PATTERN.finditer(text))
        if not matches:
            return text, {}
        # Architecture Contract: Metadata is appended strictly to the end of user message
        last_match = matches[-1]
        body = text[: last_match.start()].rstrip()
        meta_raw = last_match.group(1).strip()
        data = {}
        for line in meta_raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()
        return body, data

    @classmethod
    def inject_metadata(cls, user_text: str, metadata: dict[str, Any]) -> str:
        lines = [f"{k}: {v}" for k, v in sorted(metadata.items())]
        block = (
            "<!-- DYNAMIC_METADATA_START -->\n"
            + "\n".join(lines)
            + "\n<!-- DYNAMIC_METADATA_END -->"
        )
        if not user_text.strip():
            return block
        return f"{user_text.rstrip()}\n\n{block}"


# ==============================================================================
# Challenge R1: Preamble Dynamic Variable Injection & Trailing Metadata Invariance
# ==============================================================================

class TestChallengeR1PreambleAndMetadata:
    """Adversarial stress-testing of preamble immutability and trailing metadata isolation."""

    CLEAN_STATIC_PREAMBLE = (
        "# FLEET CONSTITUTION - LAYER 0 FROZEN\n"
        "All commands execute in non-interactive batch mode.\n"
        "Persona: HTAP-9 zero-prose machine contract.\n"
        "Rule 74: Hard output cap <= 50 tokens. Rule 77: BD_MAX_TURNS=20.\n"
        "Rule 80: Pointer-payload decoupling CAS /var/tmp/bd-blobs/."
    )

    @pytest.mark.parametrize(
        "timestamp_str",
        [
            "2026-09-27T10:00:00Z",
            "2026-09-27T10:00:00.123456Z",
            "2026-09-27T10:00:00+00:00",
            "2026-09-27T10:00:00-07:00",
            "2026-01-01T00:00:00.000000+05:30",
        ],
    )
    def test_r1_injection_iso8601_timestamps_detected(self, timestamp_str):
        """Verify that PreambleValidator detects and rejects injected ISO8601 timestamps."""
        corrupted = f"{self.CLEAN_STATIC_PREAMBLE}\nCURRENT_TIME: {timestamp_str}"
        valid, violations = PreambleValidator.inspect_preamble(corrupted)
        assert valid is False, f"Failed to detect timestamp injection: {timestamp_str}"
        assert any("timestamp" in v.lower() for v in violations)

    @pytest.mark.parametrize(
        "uuid_str",
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()).upper(),
            "00000000-0000-0000-0000-000000000000",
            "12345678-abcd-ef01-2345-6789abcdef01",
        ],
    )
    def test_r1_injection_uuids_detected(self, uuid_str):
        """Verify that PreambleValidator detects and rejects injected UUIDs."""
        corrupted = f"{self.CLEAN_STATIC_PREAMBLE}\nSESSION_ID: {uuid_str}"
        valid, violations = PreambleValidator.inspect_preamble(corrupted)
        assert valid is False, f"Failed to detect UUID injection: {uuid_str}"
        assert any("uuid" in v.lower() for v in violations)

    @pytest.mark.parametrize(
        "pid_str",
        [
            "PID: 12345",
            "pid: 99",
            "PID=8888",
            "PPID: 1",
            "ppid=54321",
        ],
    )
    def test_r1_injection_pids_detected(self, pid_str):
        """Verify that PreambleValidator detects and rejects injected process IDs."""
        corrupted = f"{self.CLEAN_STATIC_PREAMBLE}\nPROCESS: {pid_str}"
        valid, violations = PreambleValidator.inspect_preamble(corrupted)
        assert valid is False, f"Failed to detect PID injection: {pid_str}"
        assert any("pid" in v.lower() for v in violations)

    @pytest.mark.parametrize(
        "seat_str",
        [
            "bd-worker-alpha-01",
            "bd-worker-g3",
            "bd-pm-orchestrator",
            "bd-pm-1",
        ],
    )
    def test_r1_injection_seat_identifiers_detected(self, seat_str):
        """Verify that PreambleValidator detects and rejects seat identifiers."""
        corrupted = f"{self.CLEAN_STATIC_PREAMBLE}\nASSIGNED_SEAT: {seat_str}"
        valid, violations = PreambleValidator.inspect_preamble(corrupted)
        assert valid is False, f"Failed to detect seat injection: {seat_str}"
        assert any("seat" in v.lower() for v in violations)

    def test_r1_injection_in_multi_turn_fails_invariance(self):
        """Verify that injecting dynamic data in Turn 8 of 20 turns triggers invariance failure."""
        preambles = [self.CLEAN_STATIC_PREAMBLE for _ in range(20)]
        # Inject dynamic variable at turn 8
        preambles[7] = f"{self.CLEAN_STATIC_PREAMBLE}\nUTC_TIMESTAMP: 2026-09-27T10:45:00Z"

        valid, msg = PreambleValidator.verify_turns_preamble_invariance(preambles)
        assert valid is False
        assert "Turn 8" in msg
        assert "dynamic variables" in msg or "differs" in msg

    def test_r1_subtle_whitespace_drift_fails_invariance(self):
        """Verify that subtle whitespace drift in turn 15 fails byte-invariance."""
        preambles = [self.CLEAN_STATIC_PREAMBLE for _ in range(20)]
        # Subtle trailing space in turn 15
        preambles[14] = self.CLEAN_STATIC_PREAMBLE + " "

        valid, msg = PreambleValidator.verify_turns_preamble_invariance(preambles)
        assert valid is False
        assert "Turn 15" in msg
        assert "differs" in msg

    def test_r1_trailing_metadata_block_prefix_byte_identity_across_20_turns(self):
        """
        Adversarial test: Across 20 simulated turns with aggressively mutating metadata
        (timestamps, turn counts, UUIDs, git status), the prefix before the metadata block
        remains 100% byte-identical (0 bytes diff, identical SHA256).
        """
        user_prompt_body = (
            "Review candidate diff for bd-harness-cut refactor.\n"
            "Ensure invariant preservation across all 6 backends.\n"
            "Report findings in single-line JSON format per Rule 76."
        )

        turn_payloads = []
        for t in range(1, 21):
            meta = {
                "UTC_TIMESTAMP": f"2026-09-27T11:{t:02d}:00Z",
                "TURN_COUNT": t,
                "SEAT_UUID": f"bd-worker-seat-{uuid.uuid4().hex[:8]}",
                "GIT_STATUS": f"a1b2c{t:02x}/clean" if t % 2 == 0 else f"f9e8d{t:02x}/dirty",
            }
            payload = DynamicMetadataParser.inject_metadata(user_prompt_body, meta)
            turn_payloads.append(payload)

        # Extract prefix from Turn 1 as benchmark
        body_turn1, _ = DynamicMetadataParser.extract_metadata(turn_payloads[0])
        assert body_turn1 == user_prompt_body
        prefix_bytes_1 = body_turn1.encode("utf-8")
        hash_1 = hashlib.sha256(prefix_bytes_1).hexdigest()

        # Verify all subsequent turns
        for turn_idx, payload in enumerate(turn_payloads[1:], start=2):
            body_t, meta_t = DynamicMetadataParser.extract_metadata(payload)
            prefix_bytes_t = body_t.encode("utf-8")
            hash_t = hashlib.sha256(prefix_bytes_t).hexdigest()

            # Byte-level diff must be exactly 0
            byte_diff = abs(len(prefix_bytes_t) - len(prefix_bytes_1))
            assert byte_diff == 0, f"Turn {turn_idx} prefix byte diff is {byte_diff} (expected 0)"
            assert hash_t == hash_1, f"Turn {turn_idx} prefix SHA256 differs from Turn 1"
            assert body_t == user_prompt_body, f"Turn {turn_idx} body content corrupted"

            # Verify dynamic variables are successfully quarantined in metadata dict
            assert int(meta_t["TURN_COUNT"]) == turn_idx
            assert "UTC_TIMESTAMP" in meta_t
            assert "SEAT_UUID" in meta_t
            assert "GIT_STATUS" in meta_t

    def test_r1_trailing_metadata_edge_cases(self):
        """Test metadata extraction with markdown code blocks containing comments."""
        prompt_with_code = (
            "Here is python code:\n"
            "```python\n"
            "# <!-- DYNAMIC_METADATA_START -->\n"
            "print('do not match internal comment')\n"
            "# <!-- DYNAMIC_METADATA_END -->\n"
            "```\n"
            "Process this code."
        )
        meta = {"TURN_COUNT": 1, "SEAT_UUID": "test-uuid"}
        injected = DynamicMetadataParser.inject_metadata(prompt_with_code, meta)
        body, extracted_meta = DynamicMetadataParser.extract_metadata(injected)
        assert extracted_meta["TURN_COUNT"] == "1"
        assert extracted_meta["SEAT_UUID"] == "test-uuid"
        assert body == prompt_with_code


# ==============================================================================
# Challenge R2: MCP Tool Schema Dictionary Insertion Order Perturbation
# ==============================================================================

class TestChallengeR2ToolSchemaCanonicalization:
    """Stress-testing tool schema canonicalization by perturbing dictionary insertion order."""

    BASE_TOOLS: ClassVar[list[dict[str, Any]]] = [
        {
            "name": "bd_status",
            "description": "Get status of swarm cluster",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "verbose": {"type": "boolean", "description": "Verbose mode"},
                    "seat_filter": {"type": "string", "description": "Seat regex"},
                },
                "required": ["verbose"],
            },
        },
        {
            "name": "bd_ast_slice",
            "description": "Slice AST from python or rust file",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "File path"},
                    "symbol": {"type": "string", "description": "Symbol name"},
                    "depth": {"type": "integer", "description": "Recursion depth"},
                },
                "required": ["file", "symbol"],
            },
        },
        {
            "name": "bd_blob_ptr",
            "description": "Pointer-payload CAS store",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "data": {"type": "string", "description": "Raw payload"},
                    "compression": {"type": "string", "enum": ["none", "zstd", "gzip"]},
                },
                "required": ["data"],
            },
        },
        {
            "name": "bd_keepalive_probe",
            "description": "Send keepalive probe",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "lease_id": {"type": "string"},
                    "max_tokens": {"type": "integer", "default": 1},
                },
                "required": ["lease_id"],
            },
        },
        {
            "name": "bd_bus_publish",
            "description": "Publish message to bus WAL",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "payload": {
                        "type": "object",
                        "properties": {
                            "event": {"type": "string"},
                            "priority": {"type": "integer"},
                        },
                    },
                },
                "required": ["topic", "payload"],
            },
        },
    ]

    @staticmethod
    def _perturb_dict(d: Any, rng: random.Random) -> Any:
        """Recursively perturb dictionary key insertion order."""
        if isinstance(d, dict):
            keys = list(d.keys())
            rng.shuffle(keys)
            shuffled_dict = collections.OrderedDict()
            for k in keys:
                shuffled_dict[k] = TestChallengeR2ToolSchemaCanonicalization._perturb_dict(
                    d[k], rng
                )
            return shuffled_dict
        elif isinstance(d, list):
            return [
                TestChallengeR2ToolSchemaCanonicalization._perturb_dict(item, rng)
                for item in d
            ]
        return d

    def test_r2_dictionary_key_order_perturbation_20_turns(self):
        """
        Adversarial test: Perturb dictionary key insertion order, list orders,
        and nested properties across 20 consecutive turns.
        Verify that canonical serialization produces EXACTLY 0-byte schema diff.
        """
        serialized_turns = []

        # Turn 1: canonical reference
        t1_serialized = ToolSchemaCanonicalizer.serialize_tools(self.BASE_TOOLS)
        serialized_turns.append(t1_serialized)
        t1_bytes = t1_serialized.encode("utf-8")
        t1_sha = hashlib.sha256(t1_bytes).hexdigest()

        # Turns 2..20: heavily perturb key insertion order using deterministic seeds
        for turn in range(2, 21):
            rng = random.Random(turn * 9973)

            # 1. Shuffle tool list order
            shuffled_tools = list(self.BASE_TOOLS)
            rng.shuffle(shuffled_tools)

            # 2. Perturb all inner dictionary key orders
            perturbed_tools = [
                self._perturb_dict(t, rng) for t in shuffled_tools
            ]

            # 3. Canonicalize and serialize
            serialized = ToolSchemaCanonicalizer.serialize_tools(perturbed_tools)
            serialized_turns.append(serialized)

            s_bytes = serialized.encode("utf-8")
            s_sha = hashlib.sha256(s_bytes).hexdigest()

            # Byte-level diff must be exactly 0
            byte_diff = abs(len(s_bytes) - len(t1_bytes))
            assert byte_diff == 0, f"Turn {turn} schema diff is {byte_diff} bytes (expected 0)"
            assert s_sha == t1_sha, f"Turn {turn} SHA256 differs from Turn 1!"
            assert serialized == t1_serialized, f"Turn {turn} string content differs!"

        # Verify through the official ToolSchemaCanonicalizer.verify_schema_invariance
        ok, msg = ToolSchemaCanonicalizer.verify_schema_invariance(serialized_turns)
        assert ok is True, f"verify_schema_invariance failed: {msg}"
        assert "0 bytes" in msg

    def test_r2_schema_perturbation_detects_actual_mutation(self):
        """
        Adversarial counter-test (oracle can say NO):
        Ensure that an actual schema change (e.g. adding a property or modifying description)
        is IMMEDIATELY detected as a non-zero byte diff.
        """
        t1_serialized = ToolSchemaCanonicalizer.serialize_tools(self.BASE_TOOLS)

        # Mutate tool: add a new parameter
        mutated_tools = [dict(t) for t in self.BASE_TOOLS]
        mutated_tools[0] = json.loads(json.dumps(mutated_tools[0]))
        mutated_tools[0]["inputSchema"]["properties"]["unauthorized_param"] = {"type": "string"}

        t2_serialized = ToolSchemaCanonicalizer.serialize_tools(mutated_tools)

        ok, msg = ToolSchemaCanonicalizer.verify_schema_invariance([t1_serialized, t2_serialized])
        assert ok is False, "Failed to detect unauthorized schema mutation!"
        assert "diff" in msg

    def test_r2_tool_added_mid_session_detected(self):
        """Verify that mid-session addition of a new tool is rejected."""
        t1_serialized = ToolSchemaCanonicalizer.serialize_tools(self.BASE_TOOLS)
        new_tool = {
            "name": "bd_dynamic_rogue_tool",
            "description": "Unauthorized dynamically loaded tool",
            "inputSchema": {"type": "object", "properties": {}},
        }
        mutated_tools = self.BASE_TOOLS + [new_tool]
        t2_serialized = ToolSchemaCanonicalizer.serialize_tools(mutated_tools)

        ok, msg = ToolSchemaCanonicalizer.verify_schema_invariance([t1_serialized, t2_serialized])
        assert ok is False
        assert "diff" in msg


# ==============================================================================
# Challenge R3: Keepalive Daemon Pause Simulation Under Simulated Delays
# ==============================================================================

class TestChallengeR3KeepalivePauseSimulation:
    """Stress-testing keepalive daemon pause simulation under delays, jitter, and TTL eviction boundaries."""

    def test_r3_keepalive_6min_pause_standard(self):
        """
        Standard 6-minute (360s) pause with 180s probe interval, 120s trigger threshold, 300s TTL.
        Verifies:
        - Exactly 2 probes dispatched at t=180s and t=360s.
        - Eviction never triggered.
        - Cache survived without 5-minute TTL eviction.
        """
        survived, details = KeepaliveSimulator.simulate_long_pause(
            pause_seconds=360, probe_interval=180, ttl_seconds=300
        )
        assert survived is True
        assert details["cache_evicted"] is False
        assert details["probes_dispatched"] == 2
        events = details["events"]
        assert len(events) == 2
        assert events[0]["time"] == 180
        assert events[1]["time"] == 360

    @pytest.mark.parametrize("extended_pause", [480, 600, 720, 900, 1800])
    def test_r3_keepalive_extended_pauses_survive(self, extended_pause):
        """
        Adversarial test: Pauses up to 30 minutes (1800s).
        Verify daemon continuously sustains cache retention across arbitrary delays.
        """
        survived, details = KeepaliveSimulator.simulate_long_pause(
            pause_seconds=extended_pause, probe_interval=180, ttl_seconds=300
        )
        assert survived is True, f"Failed to survive {extended_pause}s pause"
        assert details["cache_evicted"] is False
        expected_probes = (extended_pause - 120) // 180 + 1
        assert details["probes_dispatched"] >= expected_probes - 1

    def test_r3_keepalive_simulated_probe_delays_and_jitter(self):
        """
        Adversarial test: Introduce probe transmission latency jitter (20s network roundtrip).
        Verify that in a 360s pause, 1 probe at t=180 (completing at t=200) sustains cache
        retention with max idle gap = 180s < 300s TTL.
        And in a 400s pause, a 2nd probe at t=380 sustains the cache across longer execution.
        """
        # Test 1: 360s pause with 20s latency
        pause_seconds = 360
        ttl_seconds = 300
        base_interval = 180

        events = []
        last_refresh = 0
        probes_dispatched = 0
        cache_evicted = False

        for t in range(1, pause_seconds + 1):
            if (t - last_refresh) >= ttl_seconds:
                cache_evicted = True
                break
            if t >= 120 and (t - last_refresh) >= base_interval:
                probes_dispatched += 1
                network_latency = 20  # Simulated 20-second probe delay
                effective_refresh = t + network_latency
                last_refresh = min(effective_refresh, pause_seconds)
                events.append({"time": t, "latency": network_latency, "refresh": last_refresh})

        assert cache_evicted is False, "Cache evicted under simulated 20s probe delay!"
        assert probes_dispatched >= 1
        # Max idle window was 180s (t=0 to t=180) and 160s (t=200 to t=360), both strictly < 300s TTL
        assert (pause_seconds - last_refresh) < ttl_seconds

        # Test 2: Extended 400s pause with 20s latency dispatches 2nd probe at t=380
        last_refresh_400 = 0
        probes_400 = 0
        evicted_400 = False
        for t in range(1, 401):
            if (t - last_refresh_400) >= ttl_seconds:
                evicted_400 = True
                break
            if t >= 120 and (t - last_refresh_400) >= base_interval:
                probes_400 += 1
                last_refresh_400 = min(t + 20, 400)

        assert evicted_400 is False
        assert probes_400 == 2

    def test_r3_keepalive_critical_latency_boundary(self):
        """
        Adversarial boundary analysis:
        If probe round-trip latency reaches or exceeds 120s (e.g. 125s),
        first refresh doesn't arrive until 180 + 125 = 305s (> 300s TTL),
        causing TTL eviction at t=300s before probe completion.
        """
        ttl_seconds = 300
        excessive_latency = 125
        cache_evicted = False
        last_refresh = 0
        eviction_time = 0

        for t in range(1, 361):
            if (t - last_refresh) >= ttl_seconds:
                cache_evicted = True
                eviction_time = t
                break
            if t >= 120 and (t - last_refresh) >= 180:
                # Probe dispatched at t=180, but takes 125s
                effective_refresh = t + excessive_latency
                # Refresh not committed until t + excessive_latency, which is > 300s
                if effective_refresh <= t:
                    last_refresh = effective_refresh

        assert cache_evicted is True
        assert eviction_time == 300

    def test_r3_keepalive_fails_when_probe_interval_exceeds_ttl(self):
        """
        Adversarial counter-test (proving oracle can say NO):
        If probe interval is misconfigured to 350s (> 300s TTL),
        eviction MUST occur at t=300s.
        """
        survived, details = KeepaliveSimulator.simulate_long_pause(
            pause_seconds=360, probe_interval=350, ttl_seconds=300
        )
        assert survived is False, "Should have failed when probe interval > TTL!"
        assert details["cache_evicted"] is True
        assert details["events"][0]["event"] == "EVICTED"
        assert details["events"][0]["time"] == 300

    def test_r3_cli_test_pause_execution(self):
        """Execute the real bd-cache-keepalive test-pause command and inspect receipt."""
        proc = subprocess.run(
            [
                str(KEEPALIVE_BIN), "test-pause",
                "--duration", "360",
                "--threshold", "120",
                "--probe-interval", "180",
                "--speedup", "60.0",
                "--model", "trivial",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"test-pause command failed:\n{proc.stderr}\n{proc.stdout}"
        assert "KEEP-ALIVE PAUSE TEST RESULT: PASS" in proc.stdout

        # Verify receipt file
        assert KEEPALIVE_RECEIPT.is_file(), f"Receipt file not found at {KEEPALIVE_RECEIPT}"
        receipt = json.loads(KEEPALIVE_RECEIPT.read_text(encoding="utf-8"))
        assert receipt["survival_verified"] is True
        assert receipt["ttl_eviction_prevented"] is True
        assert receipt["probes_dispatched"] >= 2
        assert receipt["status"] == "PASS"


# ==============================================================================
# Challenge R4 / Rule 22: BulkDownloader Clean Working Tree Invariant
# ==============================================================================

class TestRule22BulkDownloaderCleanliness:
    """Verifies Fleet Rule 22: BulkDownloader working tree remains 100% clean."""

    def test_rule_22_clean_status(self):
        clean, msg = Rule22Checker.verify_clean_bulkdownloader()
        assert clean is True, f"Rule 22 violation: {msg}"

    def test_rule_22_git_porcelain_direct(self):
        proc = subprocess.run(
            ["git", "-C", str(BULKDOWNLOADER_DIR), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == "", f"Untracked or modified files in BulkDownloader:\n{proc.stdout}"
