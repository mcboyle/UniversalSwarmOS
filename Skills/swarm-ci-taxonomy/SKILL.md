---
name: swarm-ci-taxonomy
description: Comprehensive CI failure taxonomy, error signature diagnostic tree, step-by-step resolution playbooks, prevention invariants (Fleet Rules 41-47), and verification commands for ${TARGET_REPO_PATH} CI shard and precut failures. Use when diagnosing CI failures, runner timeouts, flaky test runs, dirty working tree gates, or non-hermetic execution.
---

# BD CI Failure Taxonomy & Resolution Playbooks

An authoritative operational reference and diagnostic guide for recurring CI shard failures, precut gate refusals, execution timeouts, and flake patterns in `mcboyle/BD`. Encapsulates historical failure classes discovered across PRs #856 through #901, standing Fleet Rules 41–47, automated detectors, and proven remediation procedures.

---

## 1. Overview & Architectural Taxonomy

${TARGET_REPO_PATH}'s CI pipeline (`.github/workflows/ci.yml`) enforces a fail-closed, highly optimized testing contract with two foundational architectural tenets:

1. **Explicit Enumerated Pytest Denominator**: CI does **never** run a generic directory glob (`pytest tests/`). Instead, `.github/workflows/ci.yml` explicitly enumerates test file basenames for every matrix shard under `gate-suites`. Unlisted test files are never run in CI unless registered. The gate `tests/test_v3_66_939_ci_gate_shards_cover_every_gate.py` validates that all tests declaring `SWARM_GATE_SCOPE` belong to exactly one shard.
2. **Strict Environmental Sharding**: Runner VMs are heterogeneously provisioned to maximize parallel throughput:
   - **Pure-Python Shards** (`application-safety`, `toolchain`, `artifacts-pins`, `regen-idempotence`): Fast boot; do NOT install Chromium, Playwright browser binaries, or Node runtimes.
   - **Browser-Provisioned Shards** (`download-chain`, `template-selectors`): Execute `python -m playwright install --with-deps chromium` (line 978 of `ci.yml`).
   - **Node-Provisioned Shards** (`frontend-vitest`, `parity-graph`, `parity-vitest-b`): Provision Node 20 and execute `npm ci`.
   - **PostgreSQL Service Shards** (`postgres-integration`): Bind to a live `postgres:16-alpine` service container.

Violations of this topology or ambient runner assumptions fall into **seven fundamental failure classes**:

| Class ID | Failure Class Name | Affected Subsystems | Root Cause Mechanism | Canonical Fix & Rule |
| :--- | :--- | :--- | :--- | :--- |
| **BD-CI-01** | Hermetic Git Committer Identity | Subprocess execution, Git porcelain, Test fixtures | Running `git commit` with `--author` on clean ephemeral CI runners without setting committer identity | Pass explicit `-c user.name=... -c user.email=...` argv flags (`FLEET_RULE 41`) |
| **BD-CI-02** | AST / Token Parse Bottlenecks & Static Sweep False Positives | Static code analyzers, Whole-tree census gates | Full-repo AST parsing over 2,100+ files without substring pre-filters; literal matching inside mock files | Blob-SHA content-addressed cache (`bdtools_cache.py`); cheap substring guard (`FLEET_RULE 42`); literal disjointing |
| **BD-CI-03** | Subshell, Socket, Process Tree & Descriptor Leaks | OS process table, Linux file descriptors, Asyncio event loops | Unclosed Playwright contexts on persistent xdist workers; orphan `Xvfb` processes; FD leaks in logging | Mandatory `try...finally` teardown (`close()`, `stop()`); process group kill (`os.killpg`); context managers |
| **BD-CI-04** | Fixture Contamination, Shared Globals & Ambient Leakage | Module globals, Custom runners, Git working tree | Incomplete monkeypatch harnesses; un-reset `_SITE_RUNTIME_*` globals; unignored test screenshots | `@classmethod context(cls)` with guaranteed restore; teardown resets globals; `.gitignore` ignores artifacts (`FLEET_RULE 47`) |
| **BD-CI-05** | Asynchronous Marker File Synchronization Races | IPC, Filesystem polling, Wall-clock boundaries | 0-byte file race (inode created before process flushes PID data); dynamic timestamps crossing midnight | Poll for non-empty content ending with newline (`endswith('\n')`); fixed-noon deterministic timestamps (`FLEET_RULE 44`) |
| **BD-CI-06** | CI Matrix Shard Environment & Capability Mismatches | GitHub Actions workflow, Runner matrix configuration | Scheduling browser-dependent tests in pure-Python shards lacking Chromium; missing node_modules | Relocate tests to browser-provisioned shards; decouple unit checks using offline mocks (`FLEET_RULE 46`) |
| **BD-CI-07** | Generated Artifact Drift & In-Sync Gate Violations | Toolchain generators, Metadata indices, Pin gates | Code changes shifting line numbers or pins without running `toolchain/bin/swarm-regen-order` | Execute `venv/bin/python toolchain/bin/swarm-regen-order --work "$PWD"` before committing (`CLAUDE.md` § A3, Rule 47) |
| **BD-CI-08** | Collection-Phase vs Call-Phase Import Abort | Pytest collection, Base replay gates, Contract tests | Top-level imports of unmerged symbols aborting collection on clean base with `ModuleNotFoundError` | Call-phase symbol resolution (`_get_symbol()` / `try...except ImportError` fallback) (`FLEET_RULE 44`, `CLAUDE.md` § A3) |
| **BD-CI-09** | Subprocess Inline Script String Literal Escaping | Subprocess execution, Shell pipes, Test fixtures | Unescaped raw newlines in multi-line python `-c` command strings raising `SyntaxError` in child processes | Use raw string literals (`r"""..."""`) or double-escaped newlines (`READY\\n`) |


---

## 2. Failure Signatures & Rapid Diagnostic Tree

When a CI run or local precut fails, match the verbatim error string against this diagnostic decision tree to identify the root cause and required playbook:

```text
[FAILURE OBSERVED]
│
├── Contains "Committer identity unknown" OR "fatal: empty ident name (for <runner@...>) not allowed"?
│   └──> BD-CI-01: Hermetic Git Committer Identity
│        Subprocess `git commit` invoked on ephemeral CI runner without explicit committer configuration.
│
├── Contains "TimeoutExpired" (>900s) during static analysis OR "runner import hazard detected"?
│   └──> BD-CI-02: AST / Token Parse Bottlenecks & Static Sweep False Positives
│        Whole-tree static scanner lacking substring guard, or string constant collision in test fixture.
│
├── Contains "Playwright Sync API inside the asyncio loop" OR "_owned_process_alive" OR "Too many open files"?
│   └──> BD-CI-03: Subshell, Socket, Process Tree & Descriptor Leaks
│        Persistent xdist worker contaminated by unclosed browser context, zombie display, or leaked file handle.
│
├── Contains "'_MonkeyPatch' has no attribute 'context'" OR "sites configuration path changed after runtime activation"?
│   ├──> BD-CI-04: Fixture Contamination, Shared Globals & Ambient Leakage
│   └──> Module-level singletons or custom runner monkeypatching leaked across tests.
│
├── Contains `?? <untracked_directory>/` in `git status --porcelain` during CI "Generated artifacts in sync" step?
│   └──> BD-CI-04: Ambient Environment Leakage (Missing .gitignore rule for test-generated evidence).
│
├── Contains "ValueError: invalid literal for int() with base 10: ''" during marker polling?
│   └──> BD-CI-05: Asynchronous Marker File Synchronization Races
│        Parent thread read 0-byte marker file before worker process flushed buffered child PID.
│
├── Contains "AssertionError: quota window expiration ... != ... (traversed midnight boundary)"?
│   └──> BD-CI-05: Wall-Clock Boundary Flake (Dynamic time.time() + delta crossed midnight UTC).
│
├── Contains "Failed: chromium not launchable here: Executable doesn't exist at /home/runner/.cache/ms-playwright/..."?
│   └──> BD-CI-06: CI Matrix Shard Environment & Capability Mismatches
│        Browser-dependent test placed on pure-Python shard (e.g., `application-safety`).
│
├── Contains "AssertionError: FUNCTION_INDEX.md is out of sync" OR `M PIN_INDEX.json` / `M STATIC_KB_MANIFEST.json`?
│   └──> BD-CI-07: Generated Artifact Drift & In-Sync Gate Violations
│        Source code modified without running `swarm-regen-order --work "$PWD"`.
│
├── Contains "ERROR collecting tests/test_*.py" with "ModuleNotFoundError" (0 collected, exit 2)?
│   └──> BD-CI-08: Collection-Phase vs Call-Phase Import Abort
│        Top-level import of unmerged symbol fails on unpatched base during collection instead of behavioral assertion.
│
├── Contains "SyntaxError: unterminated string literal" in child subprocess execution?
│   └──> BD-CI-09: Subprocess Inline Script String Literal Escaping
│        Unescaped newline in multi-line python `-c` command string inside triple quotes.
```


---

## 3. Step-by-Step Resolution Playbooks

### Playbook BD-CI-01: Hermetic Git Committer Identity

**Symptom**: `fatal: empty ident name (for <runner@...>) not allowed` (Exit 128).  
**Root Cause**: Local workstations have `~/.gitconfig` with `user.name` and `user.email`. Ephemeral CI runners lack global git configuration. Invoking `git commit --author="..."` sets author only, leaving committer identity blank.

**Resolution Steps**:
1. Locate the `subprocess.run(["git", "commit", ...])` or `_git("commit", ...)` call in the test or script.
2. Replace bare invocation or `--author` parameter with explicit in-line git config flags:
   ```python
   # Correct hermetic invocation
   subprocess.run([
       "git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
       "commit", "-q", "-m", "init"
   ], cwd=str(dest), check=True)
   ```
   Alternatively, provide an explicit environment dictionary:
   ```python
   env = dict(os.environ, GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.com")
   subprocess.run(["git", "commit", "-m", "init"], cwd=str(dest), env=env, check=True)
   ```
3. Run the automated detector to verify compliance:
   ```bash
   python3 toolchain/bin/swarm-git-hermetic-check <affected_file.py>
   ```
4. Re-run the affected test suite to confirm zero regressions.

---

### Playbook BD-CI-02: AST & Token Parse Bottlenecks and False Positives

**Symptom**: Test execution exceeds 40s (or runner job times out at 900s); or `runner_import_hazard` demotes parallel tests to serial queue due to string literal collisions.  
**Root Cause**: Full-repo AST parsing over 2,000+ files without substring filtering; or static regex inspecting `ast.Constant` string literals in mock generators.

**Resolution Steps**:
1. **Apply Cheap Substring Guards (Rule 42)**:
   In any static scanner iterating over files, read raw text and verify substring presence before invoking `ast.parse()`:
   ```python
   raw = path.read_text(encoding="utf-8", errors="ignore")
   if "needle_symbol" not in raw:
       continue
   tree = ast.parse(raw, filename=str(path))
   ```
2. **Utilize Content-Addressed Blob-SHA Caching**:
   For repository-wide scanners, query `git ls-tree -r HEAD` and use `toolchain/bin/bdtools_cache.py` to memoize parse results by git blob SHA:
   ```python
   from toolchain.bin.bdtools_cache import get_cache
   cache = get_cache()
   result = cache.get_or_compute_sha(blob_sha, lambda: compute_expensive_ast(raw))
   ```
3. **Disjoint Sensitive Literals in Mocks**:
   If a test writes a mock script named `run_tests.py` that triggers an AST hazard detector, split the literal:
   ```python
   (dest / ("run_" + "tests.py")).write_text(content, encoding="utf-8")
   ```
4. Benchmark the test runtime:
   ```bash
   venv/bin/python -m pytest <test_file.py> --durations=10
   ```

---

### Playbook BD-CI-03: Subshell, Socket, Process Tree & Descriptor Leaks

**Symptom**: `Error: It looks like you are using Playwright Sync API inside the asyncio loop`; orphan process assertion failures (`_owned_process_alive`); or `OSError: [Errno 24] Too many open files`.  
**Root Cause**: Playwright browser contexts or background processes (`Xvfb`) not torn down on test exit/failure; persistent pytest-xdist worker inherits polluted thread state or exhausted file descriptors.

**Resolution Steps**:
1. **Enforce Playwright Teardown Parity (Rule 45)**:
   Ensure all Playwright acquisitions are wrapped in `try...finally`:
   ```python
   pw = sync_api.playwright().start()
   try:
       browser = pw.chromium.launch()
       try:
           context = browser.new_context()
           try:
               yield context
           finally:
               context.close()
       finally:
           browser.close()
   finally:
       pw.stop()
   ```
2. **Terminate Process Groups Recursively**:
   For spawned background processes, launch with `preexec_fn=os.setsid` and kill the process group in teardown:
   ```python
   proc = subprocess.Popen(cmd, preexec_fn=os.setsid)
   try:
       yield proc
   finally:
       try:
           os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
       except ProcessLookupError:
           pass
   ```
3. **Strict Descriptor Scoping**:
   Ensure all telemetry, loggers, and test breadcrumb hooks use context managers (`with open(...) as f:`) and flush immediately.
4. Verify teardown with regression suite:
   ```bash
   venv/bin/python -m pytest tests/test_row816_astra_teardown.py -q
   ```

---

### Playbook BD-CI-04: Fixture Contamination, Shared Globals & Ambient Leakage

**Symptom**: `AttributeError: type object '_MonkeyPatch' has no attribute 'context'`; `RuntimeError: sites configuration path changed after runtime activation`; or unignored files in `git status --porcelain`.  
**Root Cause**: Custom runner test harness lacked pytest feature parity; module globals (`bulk_downloader.app._SITE_RUNTIME_*`) persisted across test runs; test screenshots captured to unignored directories.

**Resolution Steps**:
1. **Guarantee Module Global Purge (Rule 47)**:
   In test runner teardowns and custom test harnesses, reset application singletons in a `finally` block:
   ```python
   finally:
       import bulk_downloader.app as app
       app._SITE_RUNTIME_PATH = None
       app._SITE_RUNTIME_READY = False
       app._BOOTED_PATHS.clear()
   ```
2. **Complete MonkeyPatch Emulation**:
   When implementing lightweight runners, implement `@classmethod context(cls)` with automatic `undo()` execution.
3. **Hermetic Artifact Ignore Rules**:
   Add test evidence directories (e.g. `login_evidence/`, `test_tmp/`) to `.gitignore` so CI porcelain checks remain clean.
4. Verify with:
   ```bash
   git status --porcelain
   ```

---

### Playbook BD-CI-05: Asynchronous Marker File Synchronization Races

**Symptom**: `ValueError: invalid literal for int() with base 10: ''`; or midnight quota window assertion failures.  
**Root Cause**: Inode creation on Linux exposes a 0-byte window before process write buffers are flushed; dynamic `time.time()` calls cross the UTC midnight boundary during 23:50–23:59 CI runs.

**Resolution Steps**:
1. **Hardened Polling Predicate (Rule 44)**:
   Never check `marker.is_file()` alone. Require non-empty content and an expected terminal delimiter (newline):
   ```python
   _await_predicate(
       lambda: marker.is_file()
       and marker.read_text(encoding="ascii").endswith("\n")
   )
   child_pid = int(marker.read_text(encoding="ascii").strip())
   ```
2. **Atomic Write Replacement**:
   When authoring subprocess markers, write to a temporary file in the same filesystem and replace atomically:
   ```python
   tmp = marker.with_suffix(".tmp")
   tmp.write_text(f"{os.getpid()}\n", encoding="ascii")
   os.replace(tmp, marker)
   ```
3. **Deterministic Epoch Timestamps**:
   Replace dynamic timestamps with fixed-noon UTC timestamps (e.g., `2026-09-19T12:00:00Z` or `1726747200`) in test fixtures.

---

### Playbook BD-CI-06: CI Matrix Shard Environment & Capability Mismatches

**Symptom**: `Failed: chromium not launchable here: Executable doesn't exist at /home/runner/.cache/ms-playwright/...` (Exit 1).  
**Root Cause**: Test requires Playwright / Chromium, but was assigned to a pure-Python shard (`application-safety`, `toolchain`, `artifacts-pins`) where `python -m playwright install` is not executed.

**Resolution Steps**:
1. Inspect `.github/workflows/ci.yml` and locate the test file in the matrix `suites` list.
2. Relocate the test to an appropriately provisioned shard:
   - Live browser automation -> `download-chain` or `template-selectors`.
   - Node / Vitest tests -> `frontend-vitest` or `parity-graph`.
3. If the test only requires DOM parsing or selector matching, decouple the test from live browser automation by utilizing recorded HTML snapshots or `_FakeLocator` mocks.
4. Verify shard coverage gate:
   ```bash
   venv/bin/python -m pytest tests/test_v3_66_939_ci_gate_shards_cover_every_gate.py -q
   ```

---

### Playbook BD-CI-07: Generated Artifact Drift & In-Sync Gate Violations

**Symptom**: CI `gates` job fails with `Generated artifacts are in sync` diff; or `AssertionError: FUNCTION_INDEX.md is out of sync with source`.  
**Root Cause**: Modifying Python functions changes line numbers in `FUNCTION_INDEX.md`; updating version trios changes `PIN_INDEX.json`; adding knowledge files changes `STATIC_KB_MANIFEST.json`. Committing without running the deterministic generator cascade causes gate failure.

**Resolution Steps**:
1. Run the authoritative deterministic generation cascade:
   ```bash
   venv/bin/python toolchain/bin/swarm-regen-order --work "$PWD"
   ```
2. If KB files were added or modified, sync KB manifest:
   ```bash
   venv/bin/python toolchain/bin/swarm-kb-sync seed project-knowledge
   ```
3. If persistence records were updated, regenerate index:
   ```bash
   python3 ${SWARM_PERSIST_DIR}/harness/swarm-persist-index.py
   python3 ${SWARM_PERSIST_DIR}/harness/swarm-persist-index.py --check
   ```
4. Verify working tree is clean:
   ```bash
   git status --porcelain
   ```
5. Run the manifest verification gate:
   ```bash
   env -u SWARM_INSTALL_DIR bash -c 'SWARM_DISABLE_KEEPALIVE=1 venv/bin/python -m pytest tests/test_v3_66_944_static_kb_manifest_describes_the_tree.py -q'
   ```

---

### Playbook BD-CI-08: Call-Phase Test Symbol Resolution (Behavioral RED on Base Replay)

**Symptom**: `ERROR collecting tests/test_*.py` with `ModuleNotFoundError` on clean base replay (0 collected, exit 2).  
**Root Cause**: Top-level module imports of new, unmerged functions or fixtures (`from bulk_downloader.new_mod import func` or `from conftest import NEW_FIXTURE`) execute during pytest's collection phase. On an unpatched base tree, collection crashes before tests run. This fails CLAUDE.md § A3 and Fleet Rule 44 because it yields collection `ERROR` instead of an intended behavioral `FAILED` assertion.

**Resolution Steps**:
1. Remove the unmerged symbol from top-level imports in `tests/test_*.py`.
2. Defer resolution to the test function or call-phase helper with a safe fallback:
   ```python
   # Correct: Defer import to helper with assertion fallback
   def _get_target_func():
       try:
           from bulk_downloader.new_mod import target_func
           return target_func
       except ImportError:
           return None

   def test_behavioral_red():
       func = _get_target_func()
       assert func is not None, "BEHAVIORAL RED: target_func is not implemented"
       assert func() == "expected"
   ```
3. Verify on clean base archive:
   ```bash
   git -C /path/to/wt archive <base_sha> | tar -x -C /tmp/clean_base
   cp tests/test_*.py /tmp/clean_base/tests/
   venv/bin/python -m pytest /tmp/clean_base/tests/test_*.py -q
   ```
   Must produce `N failed` (behavioral assertion error), NOT collection `ERROR` (exit code 1, not exit code 2).

---

### Playbook BD-CI-09: Child Process Inline Script String Literal Escapes

**Symptom**: `SyntaxError: unterminated string literal (detected at line N)` in subprocess execution.  
**Root Cause**: Multi-line Python scripts passed to `subprocess.Popen([sys.executable, "-c", script])` containing raw newlines (e.g. `sys.stdout.write("READY\n")`) inside triple-quoted strings (`"""..."""`) parse the `\n` as an actual newline character, breaking string literal termination.

**Resolution Steps**:
1. Locate the multi-line script string passed to `-c`.
2. Convert the script to a raw string literal (`r"""..."""`) or double-escape embedded newlines:
   ```python
   # Correct: Use raw string literal or double escape
   script = r"""
   import sys
   sys.stdout.write("READY\n")
   sys.stdout.flush()
   """
   # OR:
   script = """
   import sys
   sys.stdout.write("READY\\n")
   sys.stdout.flush()
   """
   ```
3. Re-run the test to verify that the child process exits 0 without `SyntaxError`.

---

## 4. Prevention Invariants & Standing Fleet Rules (Rules 41–47)


The following standing rules from `${SWARM_PERSIST_DIR}/FLEET_RULE.md` bind all agents, workers, and CI pipelines:

### Fleet Rule 41: Hermetic Git Fixtures
> **HERMETIC GIT FIXTURES**: Any test or tool creating scratch git commits must pass explicit config flags (`git -c user.name=Test -c user.email=test@example.com commit ...`) or set `GIT_COMMITTER_*` env vars; never assume ambient global git config on CI runners or sandboxes.
- **Rationale**: GitHub Actions runners lack a preconfigured `~/.gitconfig`. Using `--author` alone leaves committer identity empty, aborting `git commit` with exit code 128.

### Fleet Rule 42: Static Census Substring Guards
> **STATIC CENSUS SUBSTRING GUARDS**: Any static sweep over `tests/test_*.py` (1,700+ files) must apply cheap raw-text substring guards (`if needle not in raw: continue`) before invoking expensive parsers (`ast.parse()`, `tokenize.tokenize()`, or heavy regex passes).
- **Rationale**: Full-repo AST parsing takes 45–140 seconds without filters, blowing past timeout thresholds. Cheap substring pre-filtering reduces execution times by >50–90%.

### Fleet Rule 43: Claude RC Endpoint Invariant
> **CLAUDE RC ENDPOINT INVARIANT**: Remote Control (`--remote-control`) is strictly refused by Claude Code unless `ANTHROPIC_BASE_URL` resolves directly to `https://api.anthropic.com`. Because `settings.json` env values outrank shell environment variables and `env -u`, any launch of `--remote-control` MUST explicitly pass `--settings '{"env":{"ANTHROPIC_BASE_URL":"https://api.anthropic.com","ENABLE_TOOL_SEARCH":"true"}}'` to guarantee the bridge binds to the operator's mobile and web app.
- **Rationale**: Prevents internal sandbox proxy endpoints from interfering with direct operator bridge control.

### Fleet Rule 44: Asynchronous Marker Flush Synchronization
> **ASYNCHRONOUS MARKER FLUSH SYNCHRONIZATION**: Reading a filesystem synchronization marker written by another process must never rely solely on `marker.exists()` or `marker.is_file()`. Inode creation is non-atomic with data flush, exposing 0-byte windows. The reader MUST poll until the file is non-empty and terminates with an expected delimiter (`marker.read_text().endswith('\n')`), or use atomic filesystem replacement (`os.replace`). Dynamic timestamps must use static fixed-noon epochs to prevent midnight calendar traversal flakes.
- **Rationale**: Eliminates intermittent `ValueError: invalid literal for int() with base 10: ''` races in CI under heavy thread scheduling.

### Fleet Rule 45: Playwright Async/Sync Teardown Parity
> **PLAYWRIGHT ASYNC/SYNC TEARDOWN PARITY**: Any fixture or test helper that initializes an external OS daemon (`Xvfb`), subshell process group, database connection pool, or asynchronous driver (`playwright`, `asyncio`) MUST guarantee cleanup in a `try...finally` block. Subprocesses must terminate via `os.killpg()`, and Playwright contexts must execute both `context.close()` and `pw.stop()` before returning control to pytest to prevent event loop leaks across persistent workers.
- **Rationale**: With `--max-worker-restart=0`, persistent pytest workers carry leaked event loops into subsequent test files, causing fatal runtime exceptions.

### Fleet Rule 46: CI Matrix Capability Parity
> **CI MATRIX CAPABILITY PARITY**: Every test file enumerated in `.github/workflows/ci.yml` must align with the capability boundary of its assigned shard. Browser tests (`playwright`, Chromium) belong exclusively to `download-chain` or `template-selectors`; Node tests belong to `frontend-vitest` or `parity-graph`. Placing a browser-dependent test on a pure-Python shard lacking Chromium is an architectural defect; missing dependencies must fail closed rather than skip.
- **Rationale**: Pure-Python runners do not provision Chromium to maintain fast shard execution. Missing binary causes immediate fail-closed exit.

### Fleet Rule 47: Monkeypatch Global Purge Contract
> **MONKEYPATCH GLOBAL PURGE CONTRACT**: Any test runner harness, fixture, or patch mechanism that modifies module-level singletons or ambient global state (such as `_MonkeyPatch`, `bulk_downloader.app._SITE_RUNTIME_*`, `_BOOTED_PATHS`) MUST implement an isolated context manager (`with monkeypatch.context() as m:`) and guarantee complete restoration in a `finally:` block. Un-reset module globals cause inter-test contamination, boot path collisions, and dirty working tree gate refusals.
- **Rationale**: Prevents cascading inter-test state contamination across the 12,500-test battery.

---

## 5. Verification Commands & Toolchain Detectors

### Automated Git Hermeticity Detector (`toolchain/bin/swarm-git-hermetic-check`)

Enforces Fleet Rule 41 and Fleet Rule 42 programmatically:
- **Rule 42 Compliance**: Implements raw-text substring guard (`if "commit" not in text: continue`) before initiating AST parsing.
- **AST Scope Tracking**: Employs `HermeticCommitVisitor` with lexical `ScopeInfo` tracking to detect command lists, variables, and `env` parameters.
- **Detection Criteria**: Flags any subprocess invocation executing `git commit` that lacks `-c user.name=` / `-c user.email=` flags or `GIT_COMMITTER_*` environment configuration. Specifically catches `--author` used without committer identity.

#### CLI Invocations:
```bash
# 1. Run internal self-tests (validates 6 positive controls and negative mutants)
python3 toolchain/bin/swarm-git-hermetic-check --selftest

# 2. Scan entire test directory for non-hermetic commit invocations
python3 toolchain/bin/swarm-git-hermetic-check tests/

# 3. Scan specific file or directory tree with verbose output
python3 toolchain/bin/swarm-git-hermetic-check -v tests/test_desandbox_tool_verifiers.py
```

### Comprehensive Suite Verification Gates

Execute these authoritative commands to verify codebase health and index alignment:

```bash
# 1. Detector Regression Test Suite
venv/bin/python -m pytest tests/test_git_hermetic_commit_detector.py -q

# 2. Playwright Teardown Regression Gate
venv/bin/python -m pytest tests/test_row816_astra_teardown.py -q

# 3. CI Matrix Shard Coverage Gate
venv/bin/python -m pytest tests/test_v3_66_939_ci_gate_shards_cover_every_gate.py -q

# 4. Static KB Manifest Tree Coverage Gate
env -u SWARM_INSTALL_DIR bash -c 'SWARM_DISABLE_KEEPALIVE=1 venv/bin/python -m pytest tests/test_v3_66_944_static_kb_manifest_describes_the_tree.py -q'

# 5. Persistence Index Check
python3 ${SWARM_PERSIST_DIR}/harness/swarm-persist-index.py --check

# 6. Full Tracked Artifact Regeneration Cascade
venv/bin/python toolchain/bin/swarm-regen-order --work "$PWD"
```
