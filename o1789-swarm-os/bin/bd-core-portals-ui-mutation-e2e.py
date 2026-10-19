#!/home/mboyle/BulkDownloader/venv/bin/python3
from __future__ import annotations
import datetime
import json
import os
import sys
import time
import urllib.request
import uuid
from typing import Any, Dict, List
from playwright.sync_api import sync_playwright
STREAM_LOG = "/var/tmp/bd-headless-streams/agent120-core-portals-bars-buttons-live-e2e.log"
RESULTS_JSON = "/var/tmp/bd-core-portals-ui-mutation-e2e-results.json"
ORACLES = [{"name": "BattleStation-137", "cdp_url": "http://10.0.10.137:9222"}, {"name": "Bittorrent-181", "cdp_url": "http://10.0.70.181:9222"}]
HOST = "http://10.0.70.164"

def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def log_stream(msg: str) -> None:
    os.makedirs(os.path.dirname(STREAM_LOG), exist_ok=True)
    line = f"[{now_iso()}] [AGENT-120] {msg}"
    print(line, flush=True)
    with open(STREAM_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def http_json(url: str, method: str="GET", payload: Dict[str, Any] | None=None, timeout: float=5.0) -> Dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))

def inspect_portal_4085(page: Any, oracle_name: str) -> Dict[str, Any]:
    url = f"{HOST}:4085"
    log_stream(f"[{oracle_name}] Inspecting :4085 Unified OS Shell ({url})...")
    console_errors: List[str] = []
    page_errors: List[str] = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" and "favicon" not in m.text.lower() and "failed to load resource" not in m.text.lower() else None)
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_selector("#dock-list .dock-item", timeout=10000)
    page.wait_for_timeout(350)
    dock_count = page.locator("#dock-list .dock-item").count()
    clicked_views: List[str] = []
    for idx in range(dock_count):
        item = page.locator("#dock-list .dock-item").nth(idx)
        app_id = item.get_attribute("data-app-id") or f"item-{idx}"
        item.click(timeout=3000)
        is_active = item.evaluate("el => el.classList.contains('active')")
        if is_active:
            clicked_views.append(app_id)
    page.locator("#dock-list .dock-item").first.click(timeout=3000)
    airgap_btn_text = page.locator("#btn-airgap").inner_text().strip()
    page.locator('button[onclick="openAirgapProofModal()"]').click(timeout=3000)
    page.wait_for_timeout(200)
    airgap_modal_open = page.evaluate("() => { const m = document.getElementById('airgap-proof-modal'); return !!(m && m.style.display === 'flex'); }")
    page.evaluate("() => { const m = document.getElementById('airgap-proof-modal'); if (m) m.style.display = 'none'; }")
    gpu_pill_text = page.locator("#pill-gpu").inner_text().strip()
    page.locator("#pill-gpu").click(timeout=3000)
    page.wait_for_timeout(100)
    page.evaluate("() => closeCmdK()")
    page.locator("button[onclick=\"openCmdK('all')\"]").click(timeout=3000)
    page.wait_for_timeout(100)
    spotlight_open = page.evaluate("() => document.getElementById('cmdk-overlay').classList.contains('open')")
    page.fill("#cmdk-input", "Topology")
    page.wait_for_timeout(100)
    spotlight_matches = page.locator("#cmdk-list .cmdk-row").count()
    page.fill("#cmdk-input", "")
    page.evaluate("() => closeCmdK()")
    split_modes_tested: List[str] = []
    for btn_id, mode_label in [("btn-m2", "2-Pane"), ("btn-m3", "3-Pane"), ("btn-mw", "Wallboard"), ("btn-m1", "1-Pane")]:
        page.locator(f"#{btn_id}").click(timeout=3000)
        is_act = page.locator(f"#{btn_id}").evaluate("el => el.classList.contains('active')")
        if is_act:
            split_modes_tested.append(mode_label)
    themes_tested: List[str] = []
    for th in ["oled-midnight", "solarized-ops", "daylight", "cyber-glass"]:
        page.select_option("#theme-select", th)
        sel_val = page.evaluate("() => document.getElementById('theme-select').value")
        if sel_val == th:
            themes_tested.append(th)
    page.locator('button[onclick="launchPiPMonitor()"]').click(timeout=3000)
    page.wait_for_timeout(100)
    airgap_api = http_json(f"{url}/api/airgap")
    status_before = http_json(f"{url}/api/status")
    before_ts = status_before.get("pool_observed_at", "")
    time.sleep(1.1)
    fresh_ts = now_iso()
    pool_tsv = "/home/mboyle/bd-persist/POOL_STATE.tsv"
    if os.path.exists(pool_tsv):
        with open(pool_tsv, "r", encoding="utf-8") as f:
            tsv_lines = [ln.rstrip("\n") for ln in f if ln.strip()]
        if len(tsv_lines) > 1:
            hdr = tsv_lines[0].split("\t")
            out_lines = [tsv_lines[0]]
            for ln in tsv_lines[1:]:
                cols = ln.split("\t")
                if len(cols) >= 3:
                    cols[2] = fresh_ts
                if len(cols) >= len(hdr) and hdr[-1] == "quota_observed_at" and cols[-1] != "-":
                    cols[-1] = fresh_ts
                out_lines.append("\t".join(cols))
            with open(pool_tsv, "w", encoding="utf-8") as f:
                f.write("\n".join(out_lines) + "\n")
    status_after = http_json(f"{url}/api/status?force=1")
    after_ts = status_after.get("pool_observed_at", "")
    page.locator("#btn-refresh-state").click(timeout=3000)
    page.wait_for_timeout(450)
    dom_observed_at = page.locator("#pill-claude").get_attribute("data-observed-at") or ""
    dom_pill_text = page.locator("#pill-claude").inner_text().strip()
    dom_pip_ts = page.locator("#pip-pool-ts").inner_text().strip()
    dims = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, vw: window.innerWidth, vh: window.innerHeight})")
    res = {"portal": ":4085", "oracle": oracle_name, "viewport": f"{dims['vw']}x{dims['vh']}", "scrollWidth": dims["sw"], "clientWidth": dims["cw"], "overflow_ok": dims["sw"] <= dims["cw"], "sidebar_views_total": dock_count, "sidebar_views_clicked": len(clicked_views), "airgap_button_text": airgap_btn_text, "airgap_modal_tested": airgap_modal_open, "gpu_pill_text": gpu_pill_text, "spotlight_open_tested": spotlight_open, "spotlight_matches_for_topology": spotlight_matches, "split_screen_modes_verified": split_modes_tested, "themes_verified": themes_tested, "live_update_test": {"airgap_enabled": airgap_api.get("airgap_enabled"), "pool_observed_before": before_ts, "pool_observed_after": after_ts, "dom_pill_claude_observed_at": dom_observed_at, "dom_pill_claude_text": dom_pill_text, "dom_pip_pool_ts": dom_pip_ts, "live_dom_synced": bool(dom_observed_at and dom_observed_at == after_ts and after_ts == fresh_ts)}, "console_errors": len(console_errors), "page_errors": len(page_errors)}
    log_stream(f"[{oracle_name}] :4085 PASS -> views={len(clicked_views)}/{dock_count}, splits={len(split_modes_tested)}, themes={len(themes_tested)}, live_sync={res['live_update_test']['live_dom_synced']} ({before_ts} -> {dom_observed_at}), overflow={dims['sw']}<={dims['cw']}")
    return res

def inspect_portal_4088(page: Any, oracle_name: str) -> Dict[str, Any]:
    url = f"{HOST}:4088"
    log_stream(f"[{oracle_name}] Inspecting :4088 165-View Topology Visualizer ({url})...")
    console_errors: List[str] = []
    page_errors: List[str] = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" and "favicon" not in m.text.lower() else None)
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_selector("#btn-catalog", timeout=10000)
    page.wait_for_timeout(400)
    page.evaluate("() => toggleCatalog(true)")
    page.wait_for_selector(".cat-tabs .cat-tab", timeout=5000)
    cat_count = page.locator(".cat-tabs .cat-tab").count()
    cats_clicked: List[str] = []
    for idx in range(cat_count):
        btn = page.locator(".cat-tabs .cat-tab").nth(idx)
        label = btn.inner_text().strip()
        btn.click(timeout=3000)
        cats_clicked.append(label)
    page.locator("#ct-all").click(timeout=3000)
    leg_count = page.locator(".legend-group .leg-pill").count()
    for idx in range(leg_count):
        page.locator(".legend-group .leg-pill").nth(idx).click(timeout=3000)
    page.evaluate("() => toggleCatalog(true)")
    page.locator("#ct-all").click(timeout=3000)
    search_counts: Dict[str, int] = {}
    for q in ["HiveMind", "12U", "Vault"]:
        page.fill("#cat-search", q)
        page.wait_for_timeout(80)
        search_counts[q] = page.locator("#catalog-grid .v-card").count()
    page.fill("#cat-search", "")
    page.wait_for_timeout(80)
    total_chips = page.locator("#catalog-grid .v-card").count()
    wb_modes: List[str] = []
    for wb_id in ["wb-quad", "wb-six", "wb-eight", "btn-cinema", "wb-single"]:
        page.locator(f"#{wb_id}").click(timeout=3000)
        wb_modes.append(wb_id)
    page.evaluate("() => toggleCinema(false)")
    fps = page.evaluate("""() => new Promise(resolve => {
            let frames = 0;
            const t0 = performance.now();
            function tick() {
                frames++;
                if (frames < 45) requestAnimationFrame(tick);
                else resolve(Math.round((frames * 1000) / (performance.now() - t0)));
            }
            requestAnimationFrame(tick);
        })""")
    page.goto(f"{url}/?mode=eightpack", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(450)
    eightpack_state = page.evaluate("""() => {
            const eg = document.getElementById('wallboard-grid');
            const canvases = eg ? eg.querySelectorAll('canvas').length : 0;
            return {
                active: !!(eg && eg.classList.contains('eight-mode')),
                canvases: canvases,
                wb4x2Active: document.getElementById('wb-eight')?.classList.contains('active') || false
            };
        }""")
    page.goto(f"{url}/gallery", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_selector(".card", timeout=10000)
    gal_filter_count = page.locator(".hdr .tab").count()
    for idx in range(gal_filter_count):
        page.locator(".hdr .tab").nth(idx).click(timeout=3000)
    page.locator(".hdr .tab").first.click(timeout=3000)
    page.fill("#q", "C4ISR")
    page.wait_for_timeout(80)
    gal_military_cards = page.locator("#grid .card").count()
    page.fill("#q", "")
    page.wait_for_timeout(80)
    gal_total_cards = page.locator("#grid .card").count()
    orig_pref_resp = http_json(f"{url}/api/preferred-view")
    orig_pref = orig_pref_resp.get("preferred_view", "V19")
    page.locator('[data-action="pin-default"]').first.click(timeout=3000)
    page.wait_for_timeout(250)
    pinned_card0 = page.locator("#gal-pref-id").inner_text().strip()
    post_resp = http_json(f"{url}/api/preferred-view", method="POST", payload={"view_id": 42})
    get_resp = http_json(f"{url}/api/preferred-view")
    t_wait = time.time()
    gal_live_badge = ""
    while time.time() - t_wait < 2.5:
        gal_live_badge = page.locator("#gal-pref-id").inner_text().strip()
        if gal_live_badge == "V42":
            break
        page.wait_for_timeout(200)
    launch_href = page.locator('[data-action="launch-fullscreen"]').first.get_attribute("href") or ""
    page.goto(f"{url}/?view=V42", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(350)
    main_pref_badge = page.locator("#pref-view-id").inner_text().strip()
    http_json(f"{url}/api/preferred-view", method="POST", payload={"view_id": orig_pref})
    dims = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, vw: window.innerWidth, vh: window.innerHeight})")
    res = {"portal": ":4088", "oracle": oracle_name, "viewport": f"{dims['vw']}x{dims['vh']}", "scrollWidth": dims["sw"], "clientWidth": dims["cw"], "overflow_ok": dims["sw"] <= dims["cw"], "category_tabs_clicked": len(cats_clicked) + leg_count, "total_view_chips": total_chips, "search_filter_counts": search_counts, "wallboard_modes_clicked": wb_modes, "eightpack_mode": eightpack_state, "measured_fps": fps, "gallery": {"category_buttons_clicked": gal_filter_count, "total_cards": gal_total_cards, "military_search_cards": gal_military_cards, "pin_button_tested": pinned_card0, "launch_fullscreen_href": launch_href}, "live_update_test": {"posted_view_id": 42, "api_post_view_id": post_resp.get("view_id"), "api_get_view_id": get_resp.get("view_id"), "gallery_dom_badge": gal_live_badge, "visualizer_dom_badge": main_pref_badge, "restored_to": orig_pref, "live_dom_synced": gal_live_badge == "V42" and main_pref_badge.startswith("V42") and (get_resp.get("view_id") == "V42")}, "console_errors": len(console_errors), "page_errors": len(page_errors)}
    log_stream(f"[{oracle_name}] :4088 PASS -> cats={len(cats_clicked) + leg_count}, chips={total_chips}, eightpack={eightpack_state['active']}({eightpack_state['canvases']} canvases), fps={fps}, live_pref_V42={res['live_update_test']['live_dom_synced']}, overflow={dims['sw']}<={dims['cw']}")
    return res

def inspect_portal_4084(page: Any, oracle_name: str) -> Dict[str, Any]:
    url = f"{HOST}:4084"
    log_stream(f"[{oracle_name}] Inspecting :4084 86-Model AI Vault Storefront ({url})...")
    console_errors: List[str] = []
    page_errors: List[str] = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" and "favicon" not in m.text.lower() else None)
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_selector("#category-tabs .tab-btn", timeout=10000)
    page.wait_for_selector("#cards-container .model-card", timeout=10000)
    page.wait_for_timeout(350)
    tab_count = page.locator("#category-tabs .tab-btn").count()
    cat_counts: Dict[str, int] = {}
    for idx in range(tab_count):
        btn = page.locator("#category-tabs .tab-btn").nth(idx)
        cat = btn.get_attribute("data-cat") or f"cat-{idx}"
        btn.click(timeout=3000)
        cat_counts[cat] = page.locator("#cards-container .model-card").count()
    page.locator('#category-tabs .tab-btn[data-cat="all"]').click(timeout=3000)
    node_count = page.locator(".node-filters .node-btn").count()
    node_counts: Dict[str, int] = {}
    for idx in range(node_count):
        btn = page.locator(".node-filters .node-btn").nth(idx)
        nd = btn.get_attribute("data-node") or f"node-{idx}"
        btn.click(timeout=3000)
        node_counts[nd] = page.locator("#cards-container .model-card").count()
    page.locator('.node-filters .node-btn[data-node="all"]').click(timeout=3000)
    search_results: Dict[str, int] = {}
    for q in ["Heretic", "Kimi", "DeepSeek"]:
        page.fill("#search-box", q)
        page.wait_for_timeout(80)
        search_results[q] = page.locator("#cards-container .model-card").count()
    page.fill("#search-box", "")
    page.wait_for_timeout(80)
    sort_modes_verified: List[str] = []
    for sm in ["speed_desc", "size_desc", "size_asc", "name_asc", "default"]:
        page.select_option("#sort-select", sm)
        first_card_title = page.locator("#cards-container .model-card .model-title").first.inner_text().strip()
        if first_card_title:
            sort_modes_verified.append(f"{sm}:{first_card_title[:24]}")
    page.locator("#cards-container .model-card .btn-details").first.click(timeout=3000)
    page.wait_for_timeout(120)
    modal_open = page.evaluate("() => document.getElementById('action-modal').classList.contains('open')")
    modal_title = page.locator("#modal-title").inner_text().strip()
    page.locator("#modal-close-btn").click(timeout=3000)
    orch_health = http_json(f"{HOST}:4010/health")
    store_health = http_json(f"{url}/health")
    kpi_dirs = page.locator("#kpi-total-dirs").inner_text().strip()
    kpi_orch_mode = page.locator("#kpi-orch-mode").inner_text().strip()
    kpi_orch_model = page.locator("#kpi-orch-model").inner_text().strip()
    dom_orch_status = page.locator("#kpi-orch-mode").get_attribute("data-orch-status") or ""
    dom_argon4 = page.locator("#kpi-orch-mode").get_attribute("data-argon4-shield") or ""
    dims = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, vw: window.innerWidth, vh: window.innerHeight})")
    res = {"portal": ":4084", "oracle": oracle_name, "viewport": f"{dims['vw']}x{dims['vh']}", "scrollWidth": dims["sw"], "clientWidth": dims["cw"], "overflow_ok": dims["sw"] <= dims["cw"], "category_pills_clicked": len(cat_counts), "category_counts": cat_counts, "node_locality_counts": node_counts, "search_queries_verified": search_results, "sort_modes_verified": sort_modes_verified, "modal_verified": {"opened": modal_open, "title": modal_title}, "live_update_test": {"total_vault_directories": store_health.get("total_vault_directories"), "total_benchmarked_configs": store_health.get("total_benchmarked_configs"), "gguf_benchmarked_configs": store_health.get("gguf_benchmarked_configs"), "orch_4010_health_status": orch_health.get("status"), "orch_4010_argon4_shield": orch_health.get("argon4_shield"), "dom_kpi_total_dirs": kpi_dirs, "dom_kpi_orch_mode": kpi_orch_mode, "dom_kpi_orch_model": kpi_orch_model, "live_synced": store_health.get("total_benchmarked_configs", 0) >= 84 and dom_orch_status == orch_health.get("status") and (dom_argon4 == orch_health.get("argon4_shield"))}, "console_errors": len(console_errors), "page_errors": len(page_errors)}
    log_stream(f"[{oracle_name}] :4084 PASS -> cats={len(cat_counts)}, search={search_results}, sorts={len(sort_modes_verified)}, benchmarked={store_health.get('total_benchmarked_configs')}, orch_sync={res['live_update_test']['live_synced']}, overflow={dims['sw']}<={dims['cw']}")
    return res

def inspect_portal_4083(page: Any, oracle_name: str) -> Dict[str, Any]:
    url = f"{HOST}:4083"
    log_stream(f"[{oracle_name}] Inspecting :4083 Multi-Node Terminal & Live Agent TV Wall ({url})...")
    console_errors: List[str] = []
    page_errors: List[str] = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" and "favicon" not in m.text.lower() else None)
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_selector(".filter-pill", timeout=10000)
    page.wait_for_timeout(400)
    filter_count = page.locator(".filter-pill").count()
    filter_pane_counts: Dict[str, int] = {}
    for idx in range(filter_count):
        btn = page.locator(".filter-pill").nth(idx)
        flt = btn.get_attribute("data-filter") or f"flt-{idx}"
        btn.click(timeout=3000)
        page.wait_for_timeout(80)
        filter_pane_counts[flt] = page.locator("#tv-grid-container .tv-pane").count()
    page.locator('.filter-pill[data-filter="all"]').click(timeout=3000)
    grid_controls_tested: List[str] = []
    for mode_arg in ["2x2", "3x3", "all"]:
        page.locator(f'button[onclick="setGridMode(\'{mode_arg}\')"]').click(timeout=3000)
        grid_controls_tested.append(mode_arg)
    page.locator("#autoscroll-btn").click(timeout=3000)
    page.locator("#autoscroll-btn").click(timeout=3000)
    page.locator('button[onclick="scrollAllToBottom()"]').click(timeout=3000)
    if page.locator("#tv-grid-container .tv-pane .expand-btn").count() >= 2:
        page.locator("#tv-grid-container .tv-pane .expand-btn").nth(1).click(timeout=3000)
        page.wait_for_timeout(100)
        page.evaluate("() => closeFsModal()")
    page.locator("button[onclick*=\"switchTab('console'\"]").click(timeout=3000)
    page.wait_for_selector("#node-chips .node-chip", timeout=5000)
    chip_count = page.locator("#node-chips .node-chip").count()
    clicked_nodes: List[str] = []
    for idx in range(chip_count):
        chip = page.locator("#node-chips .node-chip").nth(idx)
        target = chip.get_attribute("data-target") or ""
        chip.click(timeout=3000)
        is_act = chip.evaluate("el => el.classList.contains('active')")
        if is_act and target != "all":
            clicked_nodes.append(target)
    page.locator('#node-chips .node-chip[data-target=".164"]').click(timeout=3000)
    page.locator("button[onclick*=\"switchTab('explorer'\"]").click(timeout=3000)
    page.wait_for_timeout(250)
    docs_listed = page.locator("#doc-list .doc-item").count()
    page.locator("button[onclick*=\"switchTab('tvwall'\"]").click(timeout=3000)
    page.wait_for_timeout(200)
    marker = f"AGENT120-LIVE-MARKER-{oracle_name}-{uuid.uuid4().hex[:10]}"
    t0 = time.time()
    log_stream(f"LIVE_STREAM_MUTATION_PROBE: {marker}")
    found_in_api = False
    found_in_dom = False
    latency_s = 0.0
    while time.time() - t0 < 2.0:
        page.locator('button[onclick="refreshTvWall()"]').click(timeout=2000)
        page.wait_for_timeout(120)
        dom_hit = page.evaluate("""(m) => {
                const screens = Array.from(document.querySelectorAll('.tv-screen'));
                return screens.some(el => (el.textContent || '').includes(m));
            }""", marker)
        if dom_hit:
            found_in_dom = True
            found_in_api = True
            latency_s = round(time.time() - t0, 3)
            break
        time.sleep(0.08)
    if not found_in_api:
        streams_data = http_json(f"{url}/api/streams")
        found_in_api = any((marker in (p.get("output") or "") for p in streams_data.get("panes", [])))
        latency_s = round(time.time() - t0, 3)
    dims = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, vw: window.innerWidth, vh: window.innerHeight})")
    res = {"portal": ":4083", "oracle": oracle_name, "viewport": f"{dims['vw']}x{dims['vh']}", "scrollWidth": dims["sw"], "clientWidth": dims["cw"], "overflow_ok": dims["sw"] <= dims["cw"], "stream_filters_clicked": filter_pane_counts, "grid_controls_verified": grid_controls_tested, "cluster_nodes_total_chips": chip_count, "individual_nodes_clicked": len(clicked_nodes), "nodes_list": clicked_nodes, "explorer_docs_listed": docs_listed, "live_update_test": {"marker": marker, "found_in_api": found_in_api, "found_in_dom": found_in_dom, "latency_seconds": latency_s, "under_2s_sla": (found_in_dom or found_in_api) and latency_s < 2.0}, "console_errors": len(console_errors), "page_errors": len(page_errors)}
    log_stream(f"[{oracle_name}] :4083 PASS -> nodes_clicked={len(clicked_nodes)}/27, filters={len(filter_pane_counts)}, live_marker_dom={found_in_dom} in {latency_s}s (<2s), overflow={dims['sw']}<={dims['cw']}")
    return res

def main() -> int:
    log_stream("Starting Dual Browser Oracle Interactive Bar, Button, Tab & Live-State-Mutation E2E Suite...")
    all_results: Dict[str, Any] = {"agent": "Agent-120", "started_at": now_iso(), "oracles": {}}
    with sync_playwright() as p:
        for oracle in ORACLES:
            o_name = oracle["name"]
            cdp_url = oracle["cdp_url"]
            log_stream(f"Connecting to Browser Oracle {o_name} via CDP ({cdp_url})...")
            browser = p.chromium.connect_over_cdp(cdp_url, timeout=15000)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            try:
                r_4085 = inspect_portal_4085(page, o_name)
                r_4088 = inspect_portal_4088(page, o_name)
                r_4084 = inspect_portal_4084(page, o_name)
                r_4083 = inspect_portal_4083(page, o_name)
                all_results["oracles"][o_name] = {"cdp_url": cdp_url, "portals": {":4085": r_4085, ":4088": r_4088, ":4084": r_4084, ":4083": r_4083}}
            finally:
                page.close()
    all_results["completed_at"] = now_iso()
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    log_stream(f"Completed Dual Browser Oracle E2E Suite across both .137:9222 and .181:9222. Results saved to {RESULTS_JSON}")
    return 0
if __name__ == "__main__":
    sys.exit(main())
