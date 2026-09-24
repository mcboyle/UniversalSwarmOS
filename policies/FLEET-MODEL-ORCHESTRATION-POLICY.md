# Fleet Multi-Model Orchestration & Integration Policy

**Timestamp**: 2026-09-24T19:27:30Z  
**Status**: **DEPLOYED & ACTIVE**  

---

## 1. Blueprint Modules Live Fleet Binding
- **Configuration**: Linked via `/home/mboyle/.local/lib/python3.12/site-packages/frontier_blueprint.pth`.
- **Live Modules**:
  - `dag_task_compiler`: Directed Acyclic Graph execution schedules & parallel leaf dispatch.
  - `axtree_distill`: Zero-token AXTree semantic browser distillation.
  - `smt_invariants`: SMT/Z3 symbolic invariant verification & multi-model consensus.
  - `pd_remote_adapter`: Disaggregated prefill-decode remote compute offloader (`wrk-test04`).
- **Fleet Scope**: Immediately accessible to all Python environments, Codex, Claude A/B MCP servers, and Antigravity.

---

## 2. Dynamic Model Routing Matrix
Per operator directive, execution dynamically targets the optimal model pool:

| Tier / Workload | Optimal Model / Target | Channel / Access Method | Cost / Efficiency |
| :--- | :--- | :--- | :--- |
| **High-Volume Trivial Tasks** (AST slicing, lint triage, format) | LiteLLM Satellite Models (`ai-ollama01`, `ai-infer01`, DeepSeek-V3) | Local LiteLLM Gateway | Near-Zero Latency / \$0.14/MTok |
| **Precision File Edits & Code Synthesis** | Claude 3.5 Sonnet / Claude Code | CLI Tmux Sessions (`claude-a`, `claude-b`) | Native Filesystem / Fast Tooling |
| **Structural Assembly & Measurement** | `gpt-5.6-terra` / OpenAI Codex | Codex CLI / Socket | High Accuracy / Structured Gates |
| **Advisory & High-Context Reasoning Oracles** | Gemini Ultra / Gemini Pro | Virtual Browser CDP Bridge (`bd-gemini-ultra-client.py` on `10.0.70.181`) | **\$0 (Free)** — Consumes flat consumer subscription |
| **Multi-Agent Orchestration & Native Pairing** | Google Antigravity (AGY / Gemini 2.0 Pro) | Native AGY Daemon / MCP Fleet | Direct Cluster Telemetry & Tooling |
| **Judgement & Red Review** | `gpt-6-astra` | Fleet Launch Role (`bd-launch-role.sh`) | Peak Empirical Verification |
