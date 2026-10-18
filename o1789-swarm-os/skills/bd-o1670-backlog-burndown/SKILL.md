---
name: bd-o1670-backlog-burndown
description: Autonomous verification, .82 64-core /dev/shm ramdisk pytest delta probing, R4 F001-F064 feature delta synthesis, and 69-row reconciliation skill for O1670-QUEUE.tsv and UNPARK-CENSUS.tsv via /home/mboyle/bin/bd-o1670-backlog-runner.py.
---

# `bd-o1670-backlog-burndown` — Autonomous O1670 69-Row Backlog Verification & Re-Exercise Skill

## Overview

Provides zero-contention, hermetic verification and reconciliation of all `69` non-closed rows in `/home/mboyle/bd-persist/queues/O1670-QUEUE.tsv` (`148` total rows: `79` closed + `65` open + `3` built-unlanded + `1` unknown in `UNPARK-CENSUS-SUMMARY.md`):

- **Group 1 (`5` rows)**: `o1670-r1-t154`, `o1670-r2-testguard`, `o1670-r3-recall-kimi`, `o1670-r5-flaky`, `o1670-r6-mcp-trim` (`MCP-TRIM.md`)
- **Group 2 (`4` rows)**: `o1670-r4-s1..s4` (`APP-FEATURE F001–F064` read-only delta re-exercise -> `R4-s1-1754.md`, `R4-s2-bd-worker-D1.md`, `R4-s3-bd-agy-worker-c1.md`, `R4-s4.md`, and `R4-DELTA-SUMMARY-F001-F064.md`)
- **Group 3 (`60` rows)**: Remaining `o1671-*`, `o1672-*`, `o1675-*`, `o1698-*`, `o1713-*`, and `sg-*` rows in `O1670-QUEUE.tsv`

## Command & Runner

```bash
/home/mboyle/bin/bd-o1670-backlog-runner.py
```

## Key Invariants

1. **Benchmark Isolation**: Never touches `.72` or `.83`. All pytest suites and RED->GREEN candidate delta probes run on `.82` (`10.0.70.82` `wrk-test04` 64-core `/dev/shm` ramdisk) piped through `/home/mboyle/bin/bd-pytest-digest`.
2. **Rule 7 Positive Control**: Every execution runs an intentional failing control on `.82:/dev/shm` before certifying `PASS: 122 passed` across the landed `O1670`/`O1671`/`O1673`/`O1675`/`O1698`/`O1713` test modules and `RED -> GREEN` deltas for `o1671-a07-pgbackend-pragma-quote` and `o1671-a18-relocate-store-dry-run-mkdir`.
3. **Rule 22 Anti-Hallucination Shield**: Zero destructive git operations; uses streaming `git archive HEAD` into ephemeral `/dev/shm` directories on `.82`.

## Generated Artifacts

- `/home/mboyle/bd-persist/harness-work/O1670/R4-s4.md` & `R4-DELTA-SUMMARY-F001-F064.md`
- `/home/mboyle/bd-persist/harness-work/O1670/results/<id>-RESULT.md` (`69` files)
- `/home/mboyle/bd-persist/harness-work/O1789/unpark/<id>/RESULT.md` & `RESULT-AGENT113-RECONCILED.md` (`69` directories)
- `/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/O1670-69ROW-RECONCILIATION.tsv` & `.json`
- `/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/AGENT113-O1670-69ROW-BACKLOG-BURNDOWN-RECEIPTS.md`
