# E2E Test Infra: Prompt Cache Optimization Architecture

## Test Philosophy
- Opaque-box, requirement-driven verification derived directly from ORIGINAL_REQUEST.md.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise Combinatorial Testing + Real-World Workload Testing.
- Strict invariant enforcement: Rule 22 clean BulkDownloader, wire-level cache hit rate extraction (not synthetic heuristics).

## Feature Inventory
| # | Feature | Source (Requirement) | Tier 1 (Coverage >=5) | Tier 2 (Boundary >=5) | Tier 3 (Cross-Feature) | Tier 4 (Real-World) |
|---|---------|----------------------|:---------------------:|:---------------------:|:----------------------:|:-------------------:|
| 1 | Static Preamble Enforcement | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 2 | Trailing Dynamic Metadata Relocation | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 3 | Append-Only Transcript Model | ORIGINAL_REQUEST §R4 | 5 | 5 | ✓ | ✓ |
| 4 | Deterministic MCP Tool Serialization | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 5 | Mid-Session Tool Mutation Prohibition | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 6 | Ephemeral TTL Keepalive Daemon | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 7 | Extended 1-Hour Cache Pinning | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 8 | LiteLLM Consistent Hashing Router | ORIGINAL_REQUEST §R5 | 5 | 5 | ✓ | ✓ |
| 9 | Satellite AI RadixAttention / Prefix Retention | ORIGINAL_REQUEST §R5 | 5 | 5 | ✓ | ✓ |
| 10 | Real Wire Telemetry to usage.tsv & Cockpit | ORIGINAL_REQUEST §Acceptance | 5 | 5 | ✓ | ✓ |
| 11 | Automated Benchmark Harness `bd-verify-cache-pipeline` | ORIGINAL_REQUEST §Acceptance | 5 | 5 | ✓ | ✓ |
| 12 | Fleet Rule 22 Preservation (Clean BulkDownloader) | ORIGINAL_REQUEST §Acceptance | 5 | 5 | ✓ | ✓ |

## Test Architecture
- Test runner: `/home/mboyle/bin/bd-verify-cache-pipeline`
- Invocation:
  `bd-verify-cache-pipeline --backends grok,kimi,claude,codex,agy-gemini,agy-claude --turns 20 --json`
  Unit/tier suites: `python3 -m pytest /home/mboyle/UniversalSwarmOS/tests/test_cache_pipeline.py -v`
- Pass/Fail semantics:
  1. Exit code 0 if and only if all tests pass.
  2. Wire-level prompt cache hit rates on turns 5..20 $\ge 99.0\%$ across all 6 backends.
  3. Tool schema serialization diff between consecutive turns is exactly 0 bytes.
  4. System preamble token diff contains zero dynamic variables (timestamps, UUIDs, PIDs).
  5. Keepalive heartbeat daemon survives a 6-minute simulated tool execution pause without provider TTL cache eviction.
  6. All test results, wire logs, and telemetry are logged to `/home/mboyle/bd-persist/usage.tsv` and visible in Cockpit (`http://10.0.70.164:9999`).
  7. Working tree `/home/mboyle/BulkDownloader` remains 100% clean (Rule 22).

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Full 20-Turn Session on Claude Native | F1, F2, F3, F4, F5, F6, F10, F11, F12 | High |
| 2 | Full 20-Turn Session on Codex | F1, F2, F3, F4, F5, F6, F10, F11, F12 | High |
| 3 | Full 20-Turn Session on AGY Gemini & AGY Claude | F1, F2, F3, F4, F5, F6, F10, F11, F12 | High |
| 4 | Full 20-Turn Session on Grok Build & Kimi Code | F1, F2, F3, F4, F5, F6, F10, F11, F12 | High |
| 5 | Multi-Turn Satellite AI Routing via LiteLLM to ai-ollama01 / ai-infer01 | F8, F9, F10, F11, F12 | High |
| 6 | 6-Minute Tool Execution Pause with Keepalive Heartbeats | F4, F6, F10, F11 | High |

## Coverage Thresholds
- Tier 1: 5 × 12 = 60 feature tests
- Tier 2: 5 × 12 = 60 boundary and corner cases
- Tier 3: 12 pairwise feature interaction tests
- Tier 4: 6 realistic application scenarios (including 20-turn runs on all 6 backends)
- Total tests: 138 tests minimum
