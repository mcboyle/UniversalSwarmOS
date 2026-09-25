# RFC-0012: Universal Batch Relay Import Path Resolution & Daemon Portability
Date: 2026-09-25T07:08:00Z
Author: AGY-Council
Status: RATIFIED

## 1. Problem Statement
When `bd-batch-relay` is symlinked or executed directly from `/home/mboyle/bin/bd-batch-relay`, its dynamic root resolution (`repo_root = Path(__file__).resolve().parent.parent`) resolves to `/home/mboyle`, rather than the project or repository root containing `lib/relay_daemon.py`. This caused an unhandled `ModuleNotFoundError: No module named 'lib'` during automated cron and inter-agent message delivery.

## 2. Root Cause Analysis
The script relied on a single relative filesystem depth (`parent.parent`) which broke when installed into flat user binary directories (`/home/mboyle/bin/` or `/usr/local/bin/`), and `UniversalSwarmOS` lacked a bundled `lib/` directory mirroring the shared utilities.

## 3. Resolution & Invariants
1. **Multi-Root Search Fallback**:
   `bd-batch-relay` now iterates through candidate roots:
   - Script `repo_root`
   - `/home/mboyle/UniversalSwarmOS`
   - `/home/mboyle/teamwork_projects/lifecycle_optimizer`
   Injecting the first valid path containing `lib/relay_daemon.py` into `sys.path[0]`.
2. **Bundled Library Parity**:
   Mirrored `lib/relay_daemon.py`, `lib/lens_manager.py`, and `lib/backup_engine.py` into `UniversalSwarmOS/lib/` to make the repository self-contained.
3. **Model Tier Invariant**:
   Enforced `gpt-6-sol` strictly across all Codex advisory and review roles, removing all deprecated references to `gpt-5.6-sol`.

## 4. Verification & Prevention
- Verified with `bd-batch-relay --help` (exit code 0).
- Successfully executed live queue flush `bd-batch-relay flush --target bd-pm-B`.
