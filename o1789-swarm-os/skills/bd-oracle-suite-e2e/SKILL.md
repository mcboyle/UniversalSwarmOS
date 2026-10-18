---
name: bd-oracle-suite-e2e
description: Autonomous Dual Browser Oracle (.137:9222 BattleStation & .181:9222 Bittorrent) + bd-oracle Visual, Interactive, Dynamic-State & Consensus E2E Verification Suite for all Boylenet portals (:4080-:4099, :8090, :3000).
---
# bd-oracle-suite-e2e

Autonomous Dual Browser Oracle CDP + `bd-oracle` E2E verification runbook and CLI integration for verifying visual rendering, 60fps `requestAnimationFrame` wallboard budgets, interactive buttons/bars/tabs/modals, and live dynamic state updates across all Boylenet portals.

## 1. CLI Verifier Tool

- **Executable**: `/home/mboyle/bin/bd-oracle-suite-verifier.py`
- **Interpreter**: `/home/mboyle/BulkDownloader/venv/bin/python3`
- **Live Headless Stream**: `/var/tmp/bd-headless-streams/agent112-dual-oracle-cdp-e2e.log`
- **Markdown Receipt Output**: `/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/AGENT112-DUAL-ORACLE-CDP-FULL-SUITE-E2E-RECEIPTS.md`
- **JSON Report Output**: `/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/agent112-dual-oracle-e2e-results.json`

```bash
# Run full Dual-Node (.137:9222 & .181:9222) visual, interactive & dynamic-update E2E suite
/home/mboyle/bin/bd-oracle-suite-verifier.py --json
```

## 2. Owned-Window CDP Controls & Safety Invariants

1. **Owned Temporary Window/Page (`cdp-frame-scroll-controls` Parity)**:
   - Restores window bounds (`Browser.setWindowBounds(windowState='normal')`), enables focus emulation (`Emulation.setFocusEmulationEnabled(true)`), and brings the owned page to front (`Page.bringToFront`) before sampling `requestAnimationFrame` FPS.
   - Never modifies or closes pre-existing operator tabs on `.137:9222` or `.181:9222`.
2. **Benchmark Contention Guard**:
   - Checks `pgrep -f bench_worker` and never contends with GPU inference on `.72` or `.83` while `bench_worker.py` is active.
3. **Dynamic Live State Verification**:
   - Appends live probe tokens to `/var/tmp/bd-headless-streams/e2e-live-probe.log` and verifies live DOM reflection in `:4083` (Agent TV Wall) and `:4088` (165-View HiveMind CoT & ticker).
   - Verifies `:4088` `GET/POST /api/preferred-view` reload persistence, `:4084` `LOCAL` vs `CLOUD` filter tabs, `:4082` 8-service live auth handshakes + QR generator, `:4081` 12-Point Cluster Doctor + Favorites drawer, and `:4098` 12-Harness Studio + Smart Auto-Pilot + Supercharge Prompt.
