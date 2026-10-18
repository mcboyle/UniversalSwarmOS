---
name: boylenet-local-coding-agent
description: Boylenet $0 Local GPU Coding Agent skill for Kimi K2.8, Claude Code, Codex, and AGY. Dispatches autonomous code generation and .82 64-core ramdisk pytest self-healing via .137 RTX 2080 Ti or .83 Dual T4 Qwen3.6-Heretic.
---

# Boylenet `$0` Local GPU Coding Agent (`boylenet-local-coding-agent`)

Dispatches zero-cost (`$0`) autonomous coding tasks to Boylenet's local GPU fleet with automatic `.72`/`.83` benchmark contention avoidance, Tree-sitter AST slicing (`ratf` `ctx_slice`), and 3-turn self-healing verification (`ruff_check` + `mypy_check` + `.82` 64-core `/dev/shm` ramdisk pytest).

## 1. Smart Backend Routing (Rule 84)
- **Active `.72`/`.83` Benchmark Protection**: Automatically probes `.72` and `.83` for `bench_worker.py`. When active, routes 100% of coding requests to BattleStation `10.0.10.137:11434` (`qwen2.5-coder:14b` / `qwen2.5-coder:7b` on 11GB RTX 2080 Ti).
- **Dual Tesla T4 32GB VRAM (`10.0.70.83:8081`)**: When `.83` is idle, routes complex multi-file coding to `Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-IQ4_XS.gguf`.
- **Authorized Sandboxes Only (Rule 22)**: Edits are strictly restricted to `/home/mboyle/bd-local-wt/*` and `/home/mboyle/bd-cuts/*`.

## 2. CLI & Daemon Usage

### Probe GPU Backends & Contention State
```bash
/home/mboyle/bin/bd-local-coding-agent --probe-backends
```

### Run Autonomous Coding Task with Self-Healing Verification
```bash
/home/mboyle/bin/bd-local-coding-agent \
  --sandbox /home/mboyle/bd-local-wt/sb-race-local \
  --target-file bulk_downloader/utils.py \
  --target-test tests/test_utils.py \
  --prompt "Fix URL normalization edge case and preserve type annotations" \
  --backend auto \
  --max-turns 3 \
  --json
```

### Query HTTP Worker Daemon (`127.0.0.1:4099`)
```bash
curl -fsS http://127.0.0.1:4099/health
```
