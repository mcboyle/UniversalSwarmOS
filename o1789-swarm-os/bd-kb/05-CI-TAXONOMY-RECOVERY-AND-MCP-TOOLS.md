# 🩺 BD-KB 5: Boylenet CI Failure Taxonomy, Gridlock Recovery, 14 MCP Servers & 50 OpenWebUI Toolkits

- **Document ID**: `bd-kb-05-ci-and-uis`
- **Canonical Path**: `/home/mboyle/bd-persist/bd-kb/05-CI-TAXONOMY-RECOVERY-AND-MCP-TOOLS.md`
- **Source Authority**: `/home/mboyle/.agents/skills/bd-ci-taxonomy/SKILL.md`, `/home/mboyle/bin/bd-openwebui-tool-gateway.py`, `/home/mboyle/bin/bd-openwebui-sync-tools-skills-mcp.py`

---

## 1. BulkDownloader CI Failure Taxonomy (`BD-CI-01` through `BD-CI-09`)

| Class ID | Failure Class | Error Signature | Canonical Remediation |
|---|---|---|---|
| **`BD-CI-01`** | **Hermetic Git Committer Identity** | `fatal: empty ident name (for <runner@...>) not allowed` (exit 128) | Pass explicit `-c user.name=Test -c user.email=test@example.com` to `git commit` (`Rule 41`); verify with `bd-git-hermetic-check` |
| **`BD-CI-02`** | **AST / Token Parse Bottlenecks** | `TimeoutExpired` (>900s) or `runner import hazard detected` | Add raw-text substring guard (`if "needle" not in raw: continue`) before `ast.parse()` (`Rule 42`); use `bdtools_cache.py` blob-SHA cache |
| **`BD-CI-03`** | **Subshell, Socket & Playwright Leaks** | `Playwright Sync API inside the asyncio loop` or `Too many open files` | Wrap Playwright in nested `try...finally` (`context.close()`, `browser.close()`, `pw.stop()`) and kill child process groups via `os.killpg()` (`Rule 45`) |
| **`BD-CI-04`** | **Fixture & Global State Contamination** | `sites configuration path changed after runtime activation` or dirty porcelain | Reset `bulk_downloader.app._SITE_RUNTIME_*` globals in `finally:` (`Rule 47`); add scratch dirs to `.gitignore` |
| **`BD-CI-05`** | **Async Marker File Races** | `ValueError: invalid literal for int() with base 10: ''` | Poll until `marker.is_file() and marker.read_text().endswith('\n')` or write `.tmp` + `os.replace()` (`Rule 44`) |
| **`BD-CI-06`** | **CI Matrix Shard Mismatch** | `Executable doesn't exist at /home/runner/.cache/ms-playwright/...` | Move browser tests to `download-chain` or `template-selectors` shards; keep `application-safety` pure-Python (`Rule 46`) |
| **`BD-CI-07`** | **Generated Artifact Drift** | `FUNCTION_INDEX.md is out of sync` or dirty `PIN_INDEX.json` / `STATIC_KB_MANIFEST.json` | Run `venv/bin/python toolchain/bin/bd-regen-order --work "$PWD"` before committing |
| **`BD-CI-08`** | **Collection-Phase Import Abort** | `ERROR collecting tests/test_*.py` with `ModuleNotFoundError` (exit 2) | Defer import of new symbols to call-phase helper `_get_symbol()` so base replay yields behavioral `FAILED` (exit 1), never collection `ERROR` (exit 2) |
| **`BD-CI-09`** | **Subprocess Inline String Escaping** | `SyntaxError: unterminated string literal` in `python -c` | Use raw string `r"""..."""` or double-escape `\\n` in inline scripts |

---

## 2. All 14 Boylenet MCP Servers (`99` Tools Bridged via `:4079`)

| # | MCP Server | Transport / Endpoint | Key Tools |
|---:|---|---|---|
| 1 | `bd` | HTTP `http://10.0.70.164:8100/mcp` | `ask`, `brief`, `claims`, `collect_gate`, `cut_status`, `evidence`, `fleet_hosts`, `gitea_ci`, `landed`, `lane_status`, `law`, `limits`, `log_slice`, `more`, `queue_rows`, `role_state_get`, `role_state_set`, `row`, `say`, `tool_doc`, `usage`, `who_all` |
| 2 | `bd-bus` | stdio `python3 -m bd_bus_mcp` | `bus_publish`, `bus_read`, `bus_summarize`, `bus_record_assertion`, `smt_verify_invariant`, `bus_check_quorum`, `smt_evaluate_consensus` |
| 3 | `bd-fleet` | stdio `bd-fleet-mcp/server.py` | `invoke_subagent`, `landed_by_content`, `mcp_discover`, `mcp_hydrate`, `premise_verify`, `role_state_get`, `role_state_set`, `say_validate` |
| 4 | `bd-fleet-mcp_bd-fleet` | stdio `bd-fleet-mcp/server.py` | Fleet premise and role state validation mirror |
| 5 | `caveman` | stdio `/home/mboyle/.caveman/bin/caveman-mcp` | `caveman_compress`, `caveman_retrieve`, `caveman_stats`, `caveman_toon_encode`, `caveman_toon_decode` |
| 6 | `context-mode` | stdio `npx -y context-mode` | `ctx_execute`, `ctx_execute_file`, `ctx_index`, `ctx_search`, `ctx_fetch_and_index`, `ctx_batch_execute`, `ctx_stats`, `ctx_doctor`, `ctx_upgrade`, `ctx_purge`, `ctx_insight` |
| 7 | `fleet-sync` | stdio `fleet_sync_mcp.py` | `publish_lesson` |
| 8 | `hivemind-memory` | stdio `hivemind-memory/server.py` | `memory_recall`, `memory_store`, `memory_status` |
| 9 | `pg-local` | PostgreSQL `127.0.0.1:5432/ai_mesh` | `query` |
| 10 | `python-linter` | stdio `mcp_server_ruff` | `ruff_check`, `ruff_format` |
| 11 | `ratf` | stdio `mcp_server_ratf` | `ctx_slice`, `ctx_deref`, `ctx_resolve` |
| 12 | `serena` | stdio `uvx serena` | `find_symbol`, `find_referencing_symbols`, `get_symbols_overview`, `replace_symbol_body`, `insert_after_symbol`, `insert_before_symbol`, `rename_symbol` |
| 13 | `type-enforcer` | stdio `mcp_server_mypy` | `mypy_check` |
| 14 | `vmware-clones` | stdio `mcp_server_vmware` (`10.0.70.1`) | `vm_list`, `vm_info`, `vm_clone`, `vm_destroy` |

---

## 3. All 8 OpenWebUI Pipelines on `http://10.0.70.164:4079/v1`

1. `bd_kb_auto_grounding_pipeline` (`filter`): Automatically retrieves top matching `BD KB` chunks and injects grounded citations when prompts mention Boylenet, BulkDownloader, Fleet Law, or cluster services.
2. `bd_smart_o1740_intent_router_pipeline` (`pipe`): Classifies prompt intent (coding, offensive security, vision, math/reasoning, architecture) and routes to the #1 benchmarked local model (`Qwen3-Coder-30B-A3B` at `77.62 tok/s`, `CyberStrike-35B` at `66.47 tok/s`, `Qwythos-9B` at `1,005.86 tok/s`, etc.).
3. `bd_deep_research_multi_engine_pipeline` (`pipe`): Autonomous multi-source research combining SearXNG (`:8888`), ArXiv, Wikipedia, `BD KB`, and Qdrant (`:6333`) into a cited synthesis report.
4. `bd_4model_consensus_council_pipeline` (`pipe`): Queries multiple local models in parallel and synthesizes a consensus ruling with agreement scoring.
5. `bd_airgap_and_rule22_shield_pipeline` (`filter`): Audits prompts/commands against `bd-airgap` WAN status and Rule 22 destructive-git prevention.
6. `bd_code_quality_ruff_mypy_pytest_pipeline` (`filter`): Automatically lints Python code blocks in responses using `ruff` and `mypy`.
7. `bd_multimodal_flux_vision_voice_pipeline` (`pipe`): Generates 1080p/1024px images, HUD diagrams, vision OCR breakdowns, and synthesized WAV speech audio.
8. `bd_token_telemetry_langfuse_pipeline` (`filter`): Appends live `tok/s` decode speed, `[LOCAL]`/`[CLOUD]` provenance badge, and logs episodic trace metadata.

---

## 4. All 50 Native OpenWebUI Toolkits (`Toolkits #01`–`#50`)

- **Toolkits `#01`–`#30` (Core Fleet & Developer Super-Suite)**: Web Search (`SearXNG`), URL Markdown Reader, Chrome CDP Browser Oracles (`.137`/`.181`), Git Clone/Pull/Diff/Log, Gitea REST API, File Read/Write/Grep/Glob, Sandboxed Shell & Python Runner, `.82` 64-Core Ramdisk Pytest Runner, Ruff & Mypy Enforcer, RATF & Serena AST Slicer, Qdrant Vector RAG, Hivemind PostgreSQL Memory, 14-Server MCP Bridge, 128 Skills Loader, 4-GPU Orchestrator (`:4010`), `bd-airgap` Switcher, `bd-raw-ai` Bridge, VMware ESXi/vSAN Inspector, 25GbE & 398-DNS Probe, 4-Model Consensus Council, `llama-bench` Query, CyberStrike Security Auditor, ArXiv/Wiki Research, CSV/SQL Data Analyst, Mermaid/SVG Diagrammer, Caveman Compressor, Boylenet 165-View Portal Navigator.
- **Toolkits `#31`–`#50` (High-ROI Specialist & Infrastructure Suite)**:
  - `31_bd_knowledge_base_oracle`: Sub-20ms full-text & semantic search across all 6 `BD KB` volumes (`00`–`05`) + Qdrant `bd_master_kb`.
  - `32_playwright_live_web_scraper`: Headless Playwright DOM scraper, table extractor & screenshotter.
  - `33_deep_research_multi_engine`: Parallel SearXNG + ArXiv + Wikipedia + GitHub + `BD KB` deep research synthesizer.
  - `34_bulkdownloader_cli_and_ytdlp_inspector`: BulkDownloader (`bd`) extractor, route catalog, `PIN_INDEX.json`, and `yt-dlp` inspector.
  - `35_postgres_pgvector_memory_vault`: PostgreSQL `ai_mesh` & `pgvector` SQL analytics and long-term memory store.
  - `36_redis_minio_s3_object_storage`: MinIO S3 (`:9000`) bucket inspector & Redis (`:6379`) cache diagnostics.
  - `37_prometheus_grafana_loki_telemetry`: Prometheus (`:9090`) PromQL query tool & Grafana (`:3001`) dashboard inspector.
  - `38_langfuse_litellm_spend_analytics`: LiteLLM (`:4000`) & Langfuse (`.228:3000`) token spend, cache hit, and latency analyzer.
  - `39_ssh_27node_parallel_fleet_runner`: 27-Node parallel SSH diagnostic & health probe runner.
  - `40_ilo4_ipmi_physical_rack_sensors`: HPE DL380 Gen10 iLO 4 thermal (`79.5°F`), fan RPM, PSU wattage & 12U rack sensor reader (`:4091`).
  - `41_searxng_news_rss_feed_monitor`: Live tech/security news, CVE & RSS threat-intel aggregator.
  - `42_python_jupyter_notebook_generator`: Automated Jupyter Notebook (`.ipynb`) & self-contained interactive HTML report builder.
  - `43_regex_cron_jwt_crypto_swiss_army`: Developer Swiss-Army Knife (Regex tester, JWT decoder, Cron parser, SHA256/Base64/UUID).
  - `44_openapi_rest_graphql_webhook_tester`: HTTP/REST/GraphQL API client & latency benchmark tool.
  - `45_git_worktree_and_patch_auditor`: Git `PATCH-SHA256` verifier (`Rule 16`), diff stat analyzer & worktree census (`:4071`).
  - `46_huggingface_gguf_quant_calculator`: GGUF quantization VRAM/RAM calculator & `.72`/`.83` vault shard inspector (`:4076`).
  - `47_ocr_vision_pdf_table_extractor`: Local Vision VQA, image OCR & PDF/HTML table-to-Markdown extractor.
  - `48_audio_whisper_tts_music_studio`: Local Whisper STT transcription, Neural TTS WAV synthesis & audio analyzer.
  - `49_flux_1080p_image_and_hud_generator`: Local Flux / 1080p architecture diagram, HUD mockup & PNG image generator.
  - `50_boylenet_doctor_and_self_healer`: 1-Click Boylenet 31-Service Sentinel Doctor (`:4081` / `:4099`) & auto-healer.
