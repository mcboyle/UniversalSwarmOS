---
name: bd-p2-appdl-verifier
description: Autonomous verification, PATCH-SHA256 derivation, and queue reconciliation skill for P2-FIX-QUEUE.tsv (20 open rows) and APP-DL-FIX-QUEUE.tsv / app-dl-reprobe.tsv (5 open/built/unknown + 4 reprobe rows). Use when auditing or verifying P2-FIX and APP-DL-FIX cuts, running hermetic ruff/mypy/bd-pytest-digest gates in bd-local-wt sandboxes, or emitting canonical PRECHECK: PASS gate blocks.
---

# bd-p2-appdl-verifier

Autonomous verification and reconciliation workflow for Swarm 9 (`P2-FIX-QUEUE.tsv` & `APP-DL-FIX-QUEUE.tsv`).

## Capabilities

1. **Zero-Destruction Sandbox Verification (Rule 22 & Rule 83)**
   - Reuses `/home/mboyle/bd-local-wt/agent115-p2-appdl-sandbox` without deleting or resetting any existing git worktree.
   - Binds all opt-in candidate environment variables (`BD_BH104105_DIR`, `BD_BH_K2_021_CANDIDATE`, `BD_TOKEN_OPT_0004_CANDIDATE`, `BD_TOKENOPT_0005_AGY_CANDIDATE`, `BD_EFF_P1_CANDIDATE`, `BD_EFF_P2_CANDIDATE`, `BD_BH_BANDSCAF_BAND_CANDIDATE`, `BD_BH_BANDSCAF_OPS_CANDIDATE`, `BD_BH2_33_CANDIDATE`, `BD_BH2_37_CANDIDATE`, `BD_BH2_44_CANDIDATE`, `BD_BH_K2_001_FIXDIR`, `BD_CX_CACHE_02_R2_CANDIDATE`) so zero candidate tests skip during verification.

2. **Canonical Gate Block Generation**
   - Emits `WRITTEN-AT`, `CENSUS`, `PRECHECK: PASS`, and `PATCH-SHA256: <hex>` for all 25 `UNPARK-CENSUS.tsv` rows (`20` `P2-FIX` + `5` `APP-DL-FIX`) and `8` additional `P2-FIX` / `app-dl-reprobe` rows (`33` total).

## Usage

```bash
/home/mboyle/BulkDownloader/venv/bin/python \
  /home/mboyle/bd-local-wt/agent115-p2-appdl-sandbox/agent115_suite/bd_p2_appdl_swarm_verifier.py \
  --json-out /home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/agent115_p2_and_app_dl_fix_audit.json
```

```bash
PYTHONPATH=/home/mboyle/bd-local-wt/agent115-p2-appdl-sandbox \
  /home/mboyle/bin/bd-pytest-digest -o addopts="" \
  /home/mboyle/bd-local-wt/agent115-p2-appdl-sandbox/agent115_suite/test_agent115_p2_and_app_dl_fix_swarm.py
```
