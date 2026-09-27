# Project: Prompt Cache Optimization Architecture (R1-R5)

## Architecture
UniversalSwarmOS multi-platform prompt caching pipeline ensuring $\ge 99.0\%$ (targeting $99.9999\%$ asymptotic) wire-level prompt cache hit rates across all 6 fleet platforms (Claude Native, Codex, AGY Gemini, AGY Claude, Grok Build, Kimi Code) and satellite AI inference nodes (`ai-ollama01`, `ai-infer01`).

```
                              User Prompt
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ System Preamble & MCP Tool Schemas (100% Frozen & Byte-Identical)         │
│  - Layer 0: Fleet Rules & Constitution (Frozen)                          │
│  - Layer 1: Static Role Contracts (Frozen)                                │
│  - Layer 2: Deterministic MCP Schemas (Alphabetical, sorted_keys=True)   │
└───────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Append-Only Immutable KV Transcript (Turns 1..t-1)                       │
│  - Strictly immutable history; mid-session compaction banned (<150k)      │
│  - Rule 77: Hard ceiling of 20 turns before scheduled retirement          │
└───────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Latest Turn Payload (Turn t)                                              │
│  - User Content & Context                                                 │
│  - [TRAILING METADATA BLOCK]: UTC timestamp, turn count, seat UUID, git   │
└───────────────────────────────────────────────────────────────────────────┘
               │                                      │
               ▼                                      ▼
┌───────────────────────────────┐     ┌─────────────────────────────────────┐
│ Frontier Providers (Claude,   │     │ LiteLLM Proxy Router (Port 4000)    │
│ Codex, Gemini, Grok, Kimi)    │     │  - Consistent Hashing on conv_id    │
│  - 1-hour cache blocks        │     └─────────────────────────────────────┘
│  - bd-cache-keepalive daemon  │                        │
│    (1-token probe every 180s) │                        ▼
└───────────────────────────────┘     ┌─────────────────────────────────────┐
               │                      │ Satellite AI Nodes (Ollama/T4 GPUs) │
               │                      │  - ai-ollama01 (10.0.70.228)        │
               │                      │  - ai-infer01 (10.0.70.125)         │
               │                      │  - RadixAttention/Prefix KV reuse   │
               │                      └─────────────────────────────────────┘
               ▼                                         │
┌───────────────────────────────────────────────────────────────────────────┐
│ Wire Telemetry & Ingestion                                                │
│  - True wire-level cached tokens normalized into usage.tsv                │
│  - Cockpit live visualization (http://10.0.70.164:9999)                   │
│  - Automated Benchmark Harness: bd-verify-cache-pipeline                  │
└───────────────────────────────────────────────────────────────────────────┘
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Static Preamble Enforcement | System prompts, fleet rules, role profiles 100% frozen across turns | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Trailing Dynamic Metadata | Relocate all ephemeral metadata (timestamps, turn counts, UUIDs, git status) to trailing block on user message | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Append-Only Transcript Model | Enforce immutable transcripts without mid-session compaction (<150k tokens) and Turn 20 retirement | M1 | ORIGINAL_REQUEST §R4 |
| 4 | Deterministic MCP Tool Serialization | Pre-register tools at Turn 1, sort alphabetically by name, serialize with `json.dumps(sort_keys=True)` | M2 | ORIGINAL_REQUEST §R2 |
| 5 | Mid-Session Tool Mutation Prohibition | Forbid dynamic tool addition/deferral; enforce 0-byte schema diff across consecutive turns | M2 | ORIGINAL_REQUEST §R2 |
| 6 | Ephemeral TTL Keepalive Daemon | `bd-cache-keepalive` sending 1-token dummy probe every 180s when tool/subagent execution > 2 min | M3 | ORIGINAL_REQUEST §R3 |
| 7 | Extended Cache Block Pinning | Configure 1-hour explicit cache blocks for Claude/Anthropic and persistent KV retention | M3 | ORIGINAL_REQUEST §R3 |
| 8 | LiteLLM Consistent Hashing Router | Reconfigure LiteLLM proxy router (10.0.70.164:4000) with sticky hash routing on `conversation_id`/`seat` | M4 | ORIGINAL_REQUEST §R5 |
| 9 | Satellite AI RadixAttention / Prefix Retention | Verify and sustain prefix KV cache reuse across turns on `ai-ollama01` and `ai-infer01` | M4 | ORIGINAL_REQUEST §R5 |
| 10 | Real Wire Telemetry to usage.tsv & Cockpit | Normalize provider wire token metrics into `/home/mboyle/bd-persist/usage.tsv` for Cockpit rendering | M5 | ORIGINAL_REQUEST §Acceptance |
| 11 | Automated Benchmark Harness `bd-verify-cache-pipeline` | 20-turn benchmark across all 6 backends proving $\ge 99.0\%$ hit rates, 0-byte schema diff, 0 dynamic preamble diff, keepalive survival | E2E & M5 | ORIGINAL_REQUEST §Acceptance |
| 12 | Fleet Rule 22 Preservation | Strictly ensure `/home/mboyle/BulkDownloader` remains 100% clean | All | ORIGINAL_REQUEST §Acceptance |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Preamble & Transcript Immutability (R1 + R4) | Static preambles, trailing user metadata block, append-only transcripts, 150k ceiling, Rule 77 turn 20 retirement | none | DONE |
| M2 | Deterministic MCP Tool Canonicalization (R2) | Turn 1 tool pre-registration, alphabetical sort, sorted JSON keys, disable dynamic tool search/loading | none | DONE |
| M3 | Ephemeral TTL Keepalive Daemon & Pinning (R3) | `bd-cache-keepalive` service (1-token probe every 180s), 1-hour cache blocks | none | DONE |
| M4 | Satellite AI Consistent Hashing (R5) | LiteLLM router sticky hash routing on conversation_id/seat, RadixAttention KV retention on satellite nodes | none | DONE |
| E2E | E2E Testing Track (`bd-verify-cache-pipeline`) | Opaque-box test harness, Tiers 1-4 tests covering all 12 features, output format, generates TEST_READY.md | none | DONE |
| M5 | Final Milestone: Integration, Verification & Tier 5 Hardening | Phase 1: Pass 100% of E2E test suite across all 6 backends (>=99.0% hit rate, 0-byte schema diff, 0 dynamic preamble tokens, keepalive survival). Phase 2: Tier 5 adversarial hardening | M1, M2, M3, M4, E2E | DONE |

## Interface Contracts
### Preamble Builder ↔ Client Launchers (M1)
- Function/File: `infra/scripts/bd-launch-role.sh`, `bd-codex-lens.sh`, `infra/hooks/*`
- Contract: System preamble must contain 0 dynamic variables. Dynamic variables must be formatted as:
  ```
  <!-- DYNAMIC_METADATA_START -->
  UTC_TIMESTAMP: <iso8601>
  TURN_COUNT: <int>
  SEAT_UUID: <uuid>
  GIT_STATUS: <sha/status>
  <!-- DYNAMIC_METADATA_END -->
  ```
  Appended strictly to the latest user message.

### MCP Serialization ↔ Providers (M2)
- Function/File: `bd-mcp/server.py`, `infra/hooks/claude/settings.json`, `infra/hooks/kimi/config.toml`, `infra/hooks/agy/mcp_config.json`
- Contract: Pre-registered tools array sorted alphabetically by `name`. Every JSON schema serialized with `json.dumps(schema, sort_keys=True)`. Mid-session tool addition prohibited.

### Keepalive Daemon ↔ Provider APIs (M3)
- Function/File: `/home/mboyle/bin/bd-cache-keepalive`
- Contract: Probe payload:
  ```json
  {"model": "<model>", "max_tokens": 1, "messages": [{"role": "user", "content": "ping"}], "stream": false}
  ```
  Fired every 180s when tool execution > 120s.

### LiteLLM Proxy ↔ Satellite AI Nodes (M4)
- Function/File: `/home/mboyle/infra/support-layer/litellm/config.yaml`, `/home/mboyle/UniversalSwarmOS/infra/compose/litellm-config.yaml`
- Contract: Routing setting:
  ```yaml
  router_settings:
    routing_strategy: usage-based-routing-v2 # or consistent-hashing / session-affinity
    enable_pre_call_checks: true
  ```
  Sticky hashing based on `metadata.conversation_id` or `metadata.seat`.

### Benchmark Harness ↔ Telemetry (M5 & E2E)
- Command: `bd-verify-cache-pipeline --backends grok,kimi,claude,codex,agy-gemini,agy-claude --turns 20`
- TSV Output: `/home/mboyle/bd-persist/usage.tsv` (12 tab-separated columns):
  `timestamp_utc \t seat \t backend \t model \t conv_id \t status \t input_tokens \t output_tokens \t thinking_tokens \t cache_read_tokens \t total_tokens \t duration_s`

## Code Layout
- `UniversalSwarmOS/infra/scripts/`: `bd-launch-role.sh`, `bd-cache-keepalive`
- `UniversalSwarmOS/infra/hooks/`: platform settings and interceptors
- `UniversalSwarmOS/infra/compose/`: `litellm/config.yaml`
- `/home/mboyle/bin/`: `bd-verify-cache-pipeline`, `bd-cache-keepalive`
- `/home/mboyle/bd-persist/`: `usage.tsv`
- `/home/mboyle/BulkDownloader/`: READ-ONLY / UNTOUCHED (Rule 22)
