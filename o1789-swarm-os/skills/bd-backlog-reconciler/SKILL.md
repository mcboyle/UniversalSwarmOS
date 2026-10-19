---
name: bd-backlog-reconciler
description: Autonomous backlog and queue reconciler across P3-LENS-QUEUE.tsv, BH1-BACKLOG-QUEUE.tsv, BH2-BUILD-QUEUE.tsv, and queue/unpark-open.tsv against live Git commit SHAs and Blob SHAs in BulkDownloader and bd-persist/harness.
---

# `bd-backlog-reconciler` — Autonomous Backlog & Queue Reconciliation Skill

Use `/home/mboyle/bin/bd-backlog-reconciler.py` to reconcile open/unknown rows across `P3-LENS-QUEUE.tsv`, `BH1-BACKLOG-QUEUE.tsv`, `BH2-BUILD-QUEUE.tsv`, and `queue/unpark-open.tsv` against live Git & Blob state in `/home/mboyle/BulkDownloader` and `/home/mboyle/bd-persist/harness`.

## Capabilities

1. **Live Git & Blob Verification (Rule 7 Compliant)**:
   - Resolves exact commit SHAs (`git log --grep`) and `HEAD:<path>` blob SHAs (`git rev-parse --short=12 HEAD:<path>`) across both `/home/mboyle/BulkDownloader` and `/home/mboyle/bd-persist/harness`.
   - Verifies live `bd-persist` non-git carriers (`FLEET_RULE.md`, `role-systemprompts/*.frozen.systemprompt`) via SHA-256 prefix matching.
2. **Deterministic 5-Bucket Classification**:
   - `ALREADY_LANDED`: Verified on `HEAD` by commit SHA and/or live blob SHA.
   - `READY_TO_LAND_VERIFIED`: Unlanded `BOARD`/`PATCH` candidate verified via `git apply --check` against current `HEAD` and `/home/mboyle/bin/bd-pytest-digest` in an isolated sandbox (with RED control on unpatched `HEAD`).
   - `NEEDS_REBASE`: Candidate fails `git apply --check` against current `HEAD`.
   - `NEEDS_LENS`: Candidate is staged and awaiting lens review.
   - `CLOSED_STALE`: Premise refuted (`FOUND NONE` in live codebase), umbrella generator row, or empty cut (`INDEX TREE: N/A`).
3. **Autonomous Queue State Updating**:
   - Passing `--reconcile-p3-queue` creates a timestamped backup of `/home/mboyle/bd-persist/queues/P3-LENS-QUEUE.tsv` and atomically updates newly verified `ALREADY_LANDED` and `CLOSED_STALE` rows.

## CLI Usage

```bash
# Generate full reconciliation TSV + JSON summary
/home/mboyle/bin/bd-backlog-reconciler.py --json-summary

# Reconcile and atomically update /home/mboyle/bd-persist/queues/P3-LENS-QUEUE.tsv
/home/mboyle/bin/bd-backlog-reconciler.py --reconcile-p3-queue --json-summary

# Write reconciliation TSV to a custom path
/home/mboyle/bin/bd-backlog-reconciler.py --out /home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/P3-BH1-UNPARK-RECONCILIATION.tsv
```

## Output Artifact Schema (`P3-BH1-UNPARK-RECONCILIATION.tsv`)

Columns:
- `id`: Row / cut identifier
- `queue`: Source queue (`P3-LENS-QUEUE.tsv (UNPARK-66)`, `P3-LENS-QUEUE.tsv (LIVE-31)`, `BH1-BACKLOG-QUEUE.tsv (UNPARK-20)`, `BH2-BUILD-QUEUE.tsv (UNPARK-1)`, `queue/unpark-open.tsv`)
- `classification`: `ALREADY_LANDED` | `READY_TO_LAND_VERIFIED` | `NEEDS_REBASE` | `NEEDS_LENS` | `CLOSED_STALE`
- `repo`: Target repository (`harness`, `BulkDownloader`, `harness+BulkDownloader`, `bd-persist-live`)
- `landed_commit_sha`: Commit SHA or candidate `TREE:<sha>`
- `landed_blob_sha`: 12-char `HEAD:<path>` Git blob SHA or file SHA-256 prefix
- `candidate_path`: Cut worktree, patch directory, or unpark `RESULT.md` path
- `apply_check`: `git apply --check` result against current `HEAD`
- `pytest_digest`: `/home/mboyle/bin/bd-pytest-digest` result (including RED control)
- `evidence`: Concise audit citation
