---
name: boylenet-dual-oracle-e2e
description: Dual-Node Windows Chrome CDP Browser Oracle (.137:9222 BattleStation & .181:9222 Bittorrent) and E2E Portal Verification skill for Kimi K2.8, Claude Code, Codex, and AGY.
---

# Boylenet Dual-Node Browser Oracle & E2E Verifier (`boylenet-dual-oracle-e2e`)

Drives the dual Windows Chrome CDP bridges on BattleStation (`10.0.10.137:9222`) and Bittorrent (`10.0.70.181:9222`) for `$0` marginal-cost multi-model AI consensus (`Gemini`, `ChatGPT`, `Claude A/B`) and 60-FPS E2E web portal verification across all Boylenet cockpits and studios.

## 1. Core Verification Invariants (Rule 79 & CDP Frame/Scroll Controls)
- **Reasoning Completion Invariant**: Never return on interim thinking states; wait for the stop-button element to disappear before extracting browser oracle answers.
- **Visible-Window FPS Control**: Verify `document.visibilityState === "visible"` before measuring `requestAnimationFrame` FPS (`>=55 FPS` target).
- **Nonzero-Overflow Scroll Control**: Verify `scrollHeight > clientHeight` (`overflowDelta > 0`) before classifying scroll behavior.

## 2. Command Reference

### Multi-Model Browser Oracle Consensus (`$0` Marginal Cost)
```bash
/home/mboyle/bin/bd-oracle --oracle all --json "Evaluate candidate patch safety and concurrency invariants"
```

### Dual-Oracle CDP Portal & UI Verifier Suite
```bash
python3 /home/mboyle/bin/bd-oracle-suite-verifier.py --json
```

### Full Boylenet Portal & Service E2E Test Suite
```bash
python3 /home/mboyle/bin/bd-full-suite-e2e-test.py --json
```

### OpenWebUI Super-Suite E2E Verifier (`:8090`, `.72:8080`, `:4079`)
```bash
python3 /home/mboyle/bin/bd-openwebui-e2e-test.py
```
