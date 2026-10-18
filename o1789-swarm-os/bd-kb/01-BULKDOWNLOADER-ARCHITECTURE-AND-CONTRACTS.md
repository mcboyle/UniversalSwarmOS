# 📥 BD-KB 1: BulkDownloader (`bd`) Codebase, Extractors, CLI, Testing & `yt-dlp` Contracts

- **Document ID**: `bd-kb-01-bulkdownloader`
- **Canonical Path**: `/home/mboyle/bd-persist/bd-kb/01-BULKDOWNLOADER-ARCHITECTURE-AND-CONTRACTS.md`
- **Source Authority**: `/home/mboyle/BulkDownloader/CLAUDE.md` (`mcboyle/BD`)

---

## 1. Repository Architecture & Directory Populations

BulkDownloader (`BD`) is a self-hosted Flask, Playwright, and React/TypeScript batch media downloader and site-extraction platform operated by Matthew at `/home/mboyle/BulkDownloader` (official origin `mcboyle/BD`).

| Directory / File | Population & Responsibility |
|---|---|
| `bulk_downloader/` | Core application Python package (`app.py`, extractors, download engine, site adapters, cockpit tasks, auth/cookies, SQLite history & video hashes) |
| `tests/` | `1,700+` pytest modules (`12,500+` test cases), fixtures, and regression corpus |
| `toolchain/bin/` | Authoritative extensionless developer/release tools (`bd-precut`, `bd-regen-order`, `bd-band-derive`, `bd-mutate`, `bd-land-trio`, `bd-freshcheck`, `bd-guardcheck`, `bd-git-hermetic-check`) |
| `tools/` | Build, static analysis, and auxiliary verification utilities |
| `frontend/` | React / TypeScript Single-Page Application (`frontend/src/`, built to `frontend/dist/`) |
| `scripts/` | Deployment (`scripts/deploy.sh`), host provisioning (`scripts/provision_test_host.sh`), Linux/Windows installers |
| `project-knowledge/` | Canonical backlog (`IMPROVEMENT_BACKLOG.md`), cut tiering (`CUT_TIERING.md`), test mapping (`TOUCHED_FILE_TO_TEST.md`), and `STATIC_KB_MANIFEST.json` |
| `PIN_INDEX.json` | Deterministic version and dependency pin manifest |
| `FUNCTION_INDEX.md` | Generated function/symbol line index across `bulk_downloader/` |
| `ENDPOINT_CATALOG.md` | Generated Flask HTTP route and API endpoint catalog |
| `INVARIANTS.json` & `FOOTGUNS.json` | Machine-enforced safety invariants and known hazard signatures |
| `guards.json` | Guarded file ownership and modification boundaries |

---

## 2. Core Engineering Contracts (`CLAUDE.md` §§ A1–A8)

### 2.1 Dependency & `yt-dlp` Pin Invariance
- **Strict Pin Order**: Never unpin a dependency in `requirements*.txt` or `PIN_INDEX.json`. The `yt-dlp` version pin is a standing operator order.
- **Python Environment**: Always use `/home/mboyle/BulkDownloader/venv/bin/python` (`venv`, never `.venv` or system python).
- **Tools From Repo (Rule 27)**: Always invoke repo toolchain scripts as `./venv/bin/python toolchain/bin/<tool>`.

### 2.2 The 12-Step Cut Lifecycle (`CLAUDE.md` § A3)
1. **Read Contract**: Read `CLAUDE.md` + exact `project-knowledge/IMPROVEMENT_BACKLOG.md` row.
2. **Record Identity**: Record IP + hostname together, repo path, origin, branch, `HEAD`, tree SHA, clean porcelain state, and permitted paths.
3. **Enumerate Consumers**: Identify all readers, writers, tests, CI shards, generated artifacts, packaging, and deployment consumers.
4. **Write Behavioral RED-First Test**: Prove test fails for the intended behavioral defect on the unpatched base (exit code `1` assertion failure, never exit code `2` collection/SyntaxError/ImportError).
5. **Minimal Coherent Fix**: Implement the narrowest fix. Never weaken assertions, add arbitrary sleeps, or rewrite untouched code.
6. **Run Focused GREEN & Negative Controls**: Run affected test band (`bd-band-derive`), `bd-precut --gate`, and `bd-freshcheck --repo-only`.
7. **Deterministic Artifact Regeneration**:
   ```bash
   venv/bin/python toolchain/bin/bd-regen-order --work "$PWD"
   ```
8. **Freeze Candidate**: Commit only inspected paths (`git write-tree` / `PATCH-SHA256`), push, and run final lanes against that exact SHA/tree.
9. **Adversarial Review (`CUT_TIERING.md`)**:
   - `T0/T1`: One lens (`review-*`).
   - `T2`: One correctness lens that executes code + worker `bd-mutate` battery.
   - `T3`: Both **Correctness** lens (runs code) and **Shape** lens (mutates subject); `BOARD` requires both.
   - **Small-Fix Fast Track (Rule 32)**: `<= 2` files with zero public AST signature drift + passing `bd-test` bypasses LLM lens directly to pre-cut/train integration.
10. **Exact-Head CI**: Require green exact-head CI and current PR metadata.
11. **Integrator Landing (`bd-land-trio`)**: Sole writer stamps the 5-carrier version trio (`bulk_downloader/__init__.py`, `tests/test_settings_center_slice4.py`, `CHANGELOG.md`, `PIN_INDEX.json`, `project-knowledge/STATIC_KB_MANIFEST.json`).
12. **Deploy & Verify**: Deploy via `scripts/deploy.sh`, verify `/api/health` version and `GET / = 200`.

### 2.3 Train Integration Architecture
- A **Train** packs up to **16 independently reviewed patches** with **disjoint authored file paths** under one version trio, one lane, and one exact-head CI run.
- If a train lane fails, `bd-train.sh --bisect` isolates the offending patch and returns it to the worker with the lane log.

---

## 3. Canonical Testing & Verification Commands

### 3.1 Focused & Affected Band Testing
Never export `BD_INSTALL_DIR` into pytest (`env -u BD_INSTALL_DIR`), and always set `BD_DISABLE_KEEPALIVE=1`:
```bash
env -u BD_INSTALL_DIR bash -c 'BD_DISABLE_KEEPALIVE=1 venv/bin/python -m pytest tests/test_target.py -q'
```

### 3.2 Canonical Full-Suite Command
Every flag in the canonical local full-suite command is load-bearing:
```bash
env -u BD_INSTALL_DIR BD_DISABLE_KEEPALIVE=1 PYTHONUNBUFFERED=1 venv/bin/python -m pytest tests/ -n 24 --dist loadfile --timeout=240 --timeout-method=signal --max-worker-restart=0 -p no:randomly
```
- `-n 24`: Fixed 24-worker parallelism (or `-n 32` on `.82` `wrk-test04` 64-core ramdisk runner).
- `--dist loadfile`: Keeps tests within the same file on the same worker to preserve fixture scheduling contracts.
- `--timeout-method=signal`: Reports hung test by name with stack trace.
- `--max-worker-restart=0`: Aborts immediately on worker death, preventing 11.6-hour drain livelocks.

### 3.3 Browser & Site Extraction Diagnostics
- **Rendered Page Is Evidence (`CLAUDE.md` § A7)**: Candidate lists are claims about the DOM. Before theorizing about why an extractor matched wrong links (e.g. Related Videos grids), capture what the browser sees using `bd-shoot.py` or Playwright DOM inspection.
- **Playwright Teardown Parity (Rule 45)**: Always close `context.close()`, `browser.close()`, and `pw.stop()` inside nested `try...finally` blocks, and terminate spawned daemon groups via `os.killpg()`.
