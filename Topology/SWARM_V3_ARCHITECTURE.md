# Swarm V3 Architecture Roadmap: Extreme Edge Optimizations

> **Status**: APPROVED (Blue/Green Staging Active)
> **Goal**: Achieve >99% cache efficiency, zero-latency orchestration, and evolutionary resilience.

## Core Infrastructure Overhauls

### 1. Precision AST Slicing (Mandatory Context Shrink)
- **Mechanism**: Agents will be permanently banned from using `cat` or `view_file` on large source files. All read operations will be forcefully routed through the `ratf.ctx_slice` MCP tool to ingest only targeted Abstract Syntax Tree (AST) nodes.
- **Impact**: Drops base read context by ~80%, preserving tokens for extreme long-horizon memory.

### 2. Local Satellite Offloading (Zero-Cost Inference)
- **Mechanism**: The PM will intercept all trivial/deterministic tasks (linting, log parsing, syntax checks) and route them to local, free Llama/Mistral instances (`ai-ollama01`). 
- **Impact**: Reserves the premium Opus/Fable API quota strictly for deep architectural generation.

### 3. SQLite WAL Pub/Sub (`swarm-bus`)
- **Mechanism**: The primary orchestration mechanism will shift from writing expensive `.md` files to publishing binary states to a distributed SQLite Write-Ahead Log via the `swarm-bus` MCP tool.
- **Impact**: Cuts inter-agent communication latency from seconds down to milliseconds.

---

## The Bleeding Edge

### 4. Genetic Context Bidding
- **Mechanism**: The 44 worker nodes will no longer be randomly assigned rows. Instead, they will ping the PM with their current prefix-cache footprint. The PM will assign tasks strictly to the workers that already have the required files cached in memory.

### 5. Vectorized Infinite Memory
- **Mechanism**: When an agent hits the 150k token ceiling, the `caveman_toon_encode` serialization will pipe the wiped context into a local vector DB (`context-mode`). Agents will retain perfect recall of previous decisions without paying the context penalty.

### 6. Pre-emptive Prefix Caching
- **Mechanism**: The orchestration dispatcher will aggressively stream file structures into the API gateway before a worker even claims a row, ensuring the KV cache is pre-warmed.

### 7. Dynamic Peer-Review Distillation
- **Mechanism**: Every time the Astra Gatekeeper rejects a PR, the diff and the critique will be streamed into a background dataset to eventually fine-tune the Terra workers.

---

## 8. The Adversarial Chaos Monkey
- **Mechanism**: A rogue Claude Fable agent designed to execute random `kill -9` commands, lock TSV ledgers, and inject subtle logic flaws into open PRs.
- **Safety Lock**: **INERT**. The Chaos Monkey scripts will be fully built and deployed to the cluster, but execution is hard-locked behind the explicit environment variable `SWARM_CHAOS_ENABLED=1`. It will remain completely dormant until the operator issues the manual Go-Ahead.
