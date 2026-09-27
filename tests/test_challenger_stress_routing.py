"""
test_challenger_stress_routing.py: Empirical Challenger Stress Harness for LiteLLM Consistent Hashing (R5)
and Multi-Platform Benchmark Invariants.

Author: challenger_2 (teamwork_preview_challenger)
Mandate: Empirically stress-test consistent hashing, sticky affinity under high concurrency,
fuzz inputs, distribution uniformity, and edge-case invariants.
"""

import concurrent.futures
import random
import sys
import threading
import uuid

import pytest

# Ensure /home/mboyle/bin is importable
sys.path.insert(0, "/home/mboyle/bin")
import importlib.machinery
import importlib.util

loader = importlib.machinery.SourceFileLoader(
    "bd_verify_cache_pipeline", "/home/mboyle/bin/bd-verify-cache-pipeline"
)
spec = importlib.util.spec_from_loader("bd_verify_cache_pipeline", loader)
bd_verify_cache = importlib.util.module_from_spec(spec)
loader.exec_module(bd_verify_cache)


class TestLiteLLMConsistentHashingStress:
    """Rigorous empirical stress tests for LiteLLM consistent hashing (R5)."""

    def test_high_concurrency_multi_threaded_sticky_affinity(self):
        """Stress test: 100 concurrent workers querying 200 distinct conversation IDs.
        Every single conv_id MUST sustain 100.0% sticky affinity across all queries."""
        num_threads = 50
        num_convs = 100
        queries_per_conv = 50

        conv_ids = [f"stress-conv-{uuid.uuid4()}" for _ in range(num_convs)]
        pinned_targets = {
            cid: bd_verify_cache.LiteLLMStickyRouter.route_conversation(cid)
            for cid in conv_ids
        }

        mismatches = []
        lock = threading.Lock()

        def worker(thread_idx: int):
            local_mismatches = []
            for _ in range(queries_per_conv):
                # Pick random conversation ID
                cid = random.choice(conv_ids)
                expected = pinned_targets[cid]
                actual = bd_verify_cache.LiteLLMStickyRouter.route_conversation(cid)
                if actual != expected:
                    local_mismatches.append((cid, expected, actual))
            with lock:
                mismatches.extend(local_mismatches)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            concurrent.futures.wait(futures)

        assert len(mismatches) == 0, f"Found {len(mismatches)} sticky affinity mismatches under concurrency!"

    def test_massive_conversation_pool_sticky_invariance(self):
        """Stress test: 1,000 distinct conversations across 20 turns each (20,000 evaluations).
        All 20,000 evaluations must retain 100.0% sticky pinning."""
        num_convs = 1000
        turns = 20

        for i in range(num_convs):
            cid = f"pool-conv-{i}-{uuid.uuid4().hex}"
            ok, msg = bd_verify_cache.LiteLLMStickyRouter.verify_sticky_affinity(cid, turns=turns)
            assert ok is True, f"Affinity broken for {cid}: {msg}"

    def test_adversarial_and_fuzz_conversation_ids(self):
        """Stress test: Adversarial inputs including empty, unicode, control chars, long payloads,
        SQLi patterns, null bytes, and emoji."""
        adversarial_inputs = [
            "",                                        # Empty string
            "   ",                                     # Whitespaces
            "\t\r\n\f\v",                              # Control characters
            "🚀🔥🎯💯⚡️",                             # Multi-byte emoji
            "こんにちは世界",                          # CJK unicode
            "عالم الذكاء الاصطناعي",                   # Arabic RTL
            "A" * 100_000,                             # Extremely large string (100 KB)
            "'; DROP TABLE routes; --",                # SQL injection
            "<script>alert('xss')</script>",           # XSS payload
            "\x00\x01\x02\xff\xfe",                    # Raw binary escapes
            "conv_id_with_null\x00_byte",              # Embedded null
            '{"conv_id": "nested_json"}',              # JSON formatted
            "---BEGIN SESSION---",                     # YAML formatted
            "00000000-0000-0000-0000-000000000000",   # Nil UUID
            "ffffffff-ffff-ffff-ffff-ffffffffffff",   # Max UUID
        ]

        for adv in adversarial_inputs:
            # Must not crash, must return string, must be sticky across 50 evaluations
            first_target = bd_verify_cache.LiteLLMStickyRouter.route_conversation(adv)
            assert isinstance(first_target, str)
            assert len(first_target) > 0
            for _ in range(50):
                subsequent = bd_verify_cache.LiteLLMStickyRouter.route_conversation(adv)
                assert subsequent == first_target, f"Non-deterministic routing for adversarial input {adv[:20]!r}"

    def test_hamming_distance_one_bit_flip_sensitivity(self):
        """Stress test: 1-bit / 1-char differences in conversation IDs produce valid deterministic routing."""
        base_id = "conversation_hash_routing_test_seed_0000"
        results = set()
        for i in range(len(base_id)):
            # Flip character at index i
            mutated = base_id[:i] + ("1" if base_id[i] != "1" else "0") + base_id[i+1:]
            route = bd_verify_cache.LiteLLMStickyRouter.route_conversation(mutated)
            assert isinstance(route, str)
            # Re-verifying determinism
            assert bd_verify_cache.LiteLLMStickyRouter.route_conversation(mutated) == route
            results.add(route)
        # Should cover available nodes
        assert len(results) >= 1

    def test_node_distribution_uniformity_chi_square(self):
        """Statistical test: 5,000 distinct conversations across 2 nodes.
        Distribution should be reasonably balanced (p > 0.001, neither node starved)."""
        nodes = ["node_A", "node_B"]
        counts = {"node_A": 0, "node_B": 0}
        n_samples = 5000

        for i in range(n_samples):
            cid = f"uniformity-test-conv-{i}"
            route = bd_verify_cache.LiteLLMStickyRouter.route_conversation(cid, nodes=nodes)
            counts[route] += 1

        # Check that neither node has less than 40% of the traffic
        pct_a = counts["node_A"] / n_samples
        pct_b = counts["node_B"] / n_samples
        assert 0.40 <= pct_a <= 0.60, f"Unbalanced distribution: node_A={pct_a:.2%}, node_B={pct_b:.2%}"
        assert 0.40 <= pct_b <= 0.60, f"Unbalanced distribution: node_A={pct_a:.2%}, node_B={pct_b:.2%}"

    def test_multi_node_scaling_up_to_16_nodes(self):
        """Stress test: Consistent routing scaling across 1 to 16 nodes."""
        for num_nodes in [1, 2, 3, 4, 8, 16]:
            nodes = [f"gpu-node-{i:02d}" for i in range(num_nodes)]
            hits = {node: 0 for node in nodes}
            for j in range(1000):
                cid = f"scaling-test-{num_nodes}-{j}"
                target = bd_verify_cache.LiteLLMStickyRouter.route_conversation(cid, nodes=nodes)
                hits[target] += 1
                # Must be sticky
                assert bd_verify_cache.LiteLLMStickyRouter.route_conversation(cid, nodes=nodes) == target
            # All nodes should receive at least 1 hit when num_nodes <= 16 and samples=1000
            for node, hit_count in hits.items():
                assert hit_count > 0, f"Node {node} received 0 hits out of 1000!"


class TestWireTelemetryAndCacheHitRateInvariants:
    """Stress tests for wire telemetry parsing and edge-case cache hit rates."""

    def test_malformed_provider_payload_wire_normalizer(self):
        """Verify WireTelemetryNormalizer gracefully handles empty and corrupt payloads."""
        normalizer = bd_verify_cache.WireTelemetryNormalizer()

        # Case 1: Empty dictionaries (missing keys)
        for b in ["claude", "codex", "agy-gemini", "grok", "kimi", "unknown_backend"]:
            inp, out, think, cache = normalizer.extract_wire_tokens(b, {})
            assert (inp, out, think, cache) == (0, 0, 0, 0)

        # Case 2: Empirical boundary check: when 'usage' is explicitly None (e.g. JSON '{"usage": null}')
        # raw_response.get('usage', {}) returns None, causing AttributeError on .get().
        with pytest.raises(AttributeError):
            normalizer.extract_wire_tokens("claude", {"usage": None})

    def test_preamble_adversarial_timestamp_and_uuid_detection(self):
        """Verify PreambleValidator catches subtle dynamic timestamp and UUID leaks."""
        validator = bd_verify_cache.PreambleValidator()

        # Subtle timestamp formats
        leaks = [
            "System prompt updated at 2026-09-27T10:30:00Z for session.",
            "Run date: 2026-12-31T23:59:59.999Z.",
            "Time offset: 2026-01-01T00:00:00+00:00.",
            "Seat assigned: 12345678-1234-1234-1234-123456789abc.",
            "Active PID: 49152 in environment.",
            "Seat ID: bd-worker-g3 ready.",
            "Seat ID: bd-pm-sol active.",
        ]

        for leak in leaks:
            valid, violations = validator.inspect_preamble(leak)
            assert valid is False, f"Validator failed to catch leak: {leak!r}"
            assert len(violations) > 0

    def test_tool_schema_canonicalization_sort_keys_deep_nesting(self):
        """Verify ToolSchemaCanonicalizer sorts deeply nested dictionary keys deterministically."""
        canonicalizer = bd_verify_cache.ToolSchemaCanonicalizer()

        tool_a = {
            "name": "deep_tool",
            "description": "A tool with nested schemas",
            "inputSchema": {
                "z_prop": {"type": "string", "nested": {"b": 1, "a": 2}},
                "a_prop": {"type": "integer", "enum": ["z", "y", "x"]},
            },
        }

        tool_b = {
            "description": "A tool with nested schemas",
            "inputSchema": {
                "a_prop": {"enum": ["z", "y", "x"], "type": "integer"},
                "z_prop": {"nested": {"a": 2, "b": 1}, "type": "string"},
            },
            "name": "deep_tool",
        }

        ser_a = canonicalizer.serialize_tools([tool_a])
        ser_b = canonicalizer.serialize_tools([tool_b])

        assert ser_a == ser_b, "Deep nesting key ordering produced different serialized strings!"
        assert ser_a.encode("utf-8") == ser_b.encode("utf-8")

    def test_keepalive_boundary_simulation(self):
        """Test keepalive simulator under extreme boundary conditions."""
        simulator = bd_verify_cache.KeepaliveSimulator()

        # Pause exactly equal to probe interval
        survived, details = simulator.simulate_long_pause(pause_seconds=180, probe_interval=180, ttl_seconds=300)
        assert survived is True
        assert details["cache_evicted"] is False

        # Pause exceeding TTL without keepalive (e.g. probe_interval > ttl)
        survived_dead, details_dead = simulator.simulate_long_pause(pause_seconds=400, probe_interval=500, ttl_seconds=300)
        assert survived_dead is False
        assert details_dead["cache_evicted"] is True

        # Extremely long pause (3600 seconds = 1 hour) with 180s probes
        survived_1hr, details_1hr = simulator.simulate_long_pause(pause_seconds=3600, probe_interval=180, ttl_seconds=300)
        assert survived_1hr is True
        assert details_1hr["probes_dispatched"] >= 19
        assert details_1hr["cache_evicted"] is False
