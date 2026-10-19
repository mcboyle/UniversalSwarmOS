#!/home/mboyle/BulkDownloader/venv/bin/python3
from __future__ import annotations
import base64
import datetime
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request
from typing import Any
from playwright.sync_api import Browser, Page, sync_playwright
STREAM_LOG = "/var/tmp/bd-headless-streams/agent139-multiviewport-and-4098-230swarm-ui.log"
RESULTS_JSON = "/var/tmp/bd-headless-streams/agent139-3viewport-e2e-results.json"
HOST_IP = "10.0.70.164"
ORACLES = [{"name": "BattleStation-137", "cdp": "http://10.0.10.137:9222"}, {"name": "Bittorrent-181", "cdp": "http://10.0.70.181:9222"}]
VIEWPORTS = [{"label": "Mobile", "key": "390x844", "width": 390, "height": 844}, {"label": "Desktop-1080p", "key": "1920x1080", "width": 1920, "height": 1080}, {"label": "4K-Wallboard", "key": "3840x2160", "width": 3840, "height": 2160}]
PORTALS = [(4081, "Executive Briefing, Universal Search & Cluster Doctor"), (4082, "Zero-Friction SSO, QR Handoff & Root CA Trust Portal"), (4083, "Multi-Node Terminal & Live Agent TV Wall"), (4084, "86-Model AI Vault Storefront"), (4085, "Unified OS Shell & Split-Screen Workspace"), (4088, "3D WebGL 165-View Topology Visualizer"), (4090, "Hybrid Cloud + Local Burst Orchestrator"), (4098, "Multi-Harness AI Coding Studio & Swarm Arena"), (4099, "Autonomous Infrastructure Sentinel"), (8090, "OpenWebUI Supersuite Controller")]
OPENWEBUI_ADMIN_ID = "a12463df-370f-4948-b488-9437da254b15"
OPENWEBUI_SECRET = "<REDACTED_BY_BOYLENET_SECRET_GUARD>"

def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def log_stream(msg: str) -> None:
    os.makedirs(os.path.dirname(STREAM_LOG), exist_ok=True)
    line = f"[{utc_now()}] [AGENT-139] {msg}"
    print(line, flush=True)
    with open(STREAM_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def make_jwt(user_id: str, secret: str) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8")).decode("utf-8").rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"id": user_id, "exp": int(time.time()) + 86400 * 30}).encode("utf-8")).decode("utf-8").rstrip("=")
    signing_input = f"{header}.{payload}".encode("utf-8")
    sig = base64.urlsafe_b64encode(hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()).decode("utf-8").rstrip("=")
    return f"{header}.{payload}.{sig}"

def http_get_json(url: str, timeout: float=6.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))

def measure_layout(page: Page) -> dict[str, Any]:
    return dict(page.evaluate("""() => {
                const de = document.documentElement;
                const sw = de ? de.scrollWidth : 0;
                const cw = de ? de.clientWidth : 0;
                const vw = window.innerWidth;
                const vh = window.innerHeight;
                const btns = document.querySelectorAll('button, a.btn, .tab, .tab-btn, .mode-btn, .nav-tab, .filter-pill, .dock-item').length;
                return {
                    scrollWidth: sw,
                    clientWidth: cw,
                    innerWidth: vw,
                    innerHeight: vh,
                    overflowX: sw > cw,
                    deltaPx: sw - cw,
                    interactiveElements: btns,
                    title: document.title || ''
                };
            }"""))

def interact_with_portal(page: Page, port: int, vp_key: str) -> dict[str, Any]:
    actions: list[str] = []
    passed = True
    extra: dict[str, Any] = {}
    try:
        if port == 4081:
            for tid in ("tab-briefing", "tab-search", "tab-receipts", "tab-briefing"):
                loc = page.locator(f"#{tid}")
                if loc.count() > 0:
                    loc.click(timeout=3000)
                    actions.append(f"click #{tid}")
            s230 = page.locator("#swarm230HeaderBadge").inner_text(timeout=3000)
            h443 = page.locator("#https443HeaderBadge").inner_text(timeout=3000)
            b215 = page.locator("#backlog215HeaderBadge").inner_text(timeout=3000)
            badge_ok = "230 Approved Swarm Units Active/Verified" in s230 and "HTTPS :443 NGINX + Let's Encrypt Cloudflare Wildcard Ready" in h443 and ("215 / 215 (100%) Backlog Accounted" in b215)
            extra["header_badges_verified"] = badge_ok
            actions.append(f"verified 230-Swarm + HTTPS :443 + 215-Backlog badges ({badge_ok})")
            if not badge_ok:
                passed = False
            if vp_key == "1920x1080":
                page.fill("#q", "vSAN")
                page.locator("#btn-search-submit").click(timeout=3000)
                page.wait_for_timeout(250)
                actions.append("executed search 'vSAN'")
        elif port == 4082:
            for plat in ("ios", "macos", "windows", "linux", "android"):
                loc = page.locator(f"#ca-tab-{plat}")
                if loc.count() > 0:
                    loc.click(timeout=3000)
                    actions.append(f"click #ca-tab-{plat}")
        elif port == 4083:
            for flt in ("all", "agent"):
                loc = page.locator(f'.filter-pill[data-filter="{flt}"]')
                if loc.count() > 0:
                    loc.first.click(timeout=3000)
                    actions.append(f"click filter {flt}")
            for gm in ("2x2", "3x3", "all"):
                loc = page.locator(f'button[onclick="setGridMode(\'{gm}\')"]')
                if loc.count() > 0:
                    loc.first.click(timeout=3000)
                    actions.append(f"setGridMode({gm})")
        elif port == 4084:
            tabs = page.locator("#category-tabs .tab-btn")
            cnt = min(tabs.count(), 4)
            for i in range(cnt):
                tabs.nth(i).click(timeout=3000)
                actions.append(f"click category tab {i}")
            all_tab = page.locator('#category-tabs .tab-btn[data-cat="all"]')
            if all_tab.count() > 0:
                all_tab.click(timeout=3000)
        elif port == 4085:
            docks = page.locator("#dock-list .dock-item")
            cnt = min(docks.count(), 4)
            for i in range(cnt):
                docks.nth(i).click(timeout=3000)
                actions.append(f"click dock-item {i}")
            if docks.count() > 0:
                docks.first.click(timeout=3000)
            for bid in ("btn-m2", "btn-m1"):
                loc = page.locator(f"#{bid}")
                if loc.count() > 0:
                    loc.click(timeout=3000)
                    actions.append(f"click #{bid}")
        elif port == 4088:
            for wid in ("wb-quad", "wb-single"):
                loc = page.locator(f"#{wid}")
                if loc.count() > 0:
                    loc.click(timeout=3000)
                    actions.append(f"click #{wid}")
            pills = page.locator(".legend-group .leg-pill")
            if pills.count() > 0:
                pills.first.click(timeout=3000)
                actions.append("click legend pill 0")
        elif port == 4090:
            for prov in ("claude", "codex", "kimi", "local"):
                loc = page.locator(f"#provCard-{prov}")
                if loc.count() > 0:
                    loc.click(timeout=3000)
                    actions.append(f"click #provCard-{prov}")
            for t in ("claude", "hybrid"):
                loc = page.locator(f"#tabBtn-{t}")
                if loc.count() > 0:
                    loc.click(timeout=3000)
                    actions.append(f"click #tabBtn-{t}")
        elif port == 4098:
            for tid in ("xplatTab-claude", "xplatTab-codex", "xplatTab-kimi", "xplatTab-agy", "xplatTab-local"):
                loc = page.locator(f"#{tid}")
                if loc.count() > 0:
                    loc.click(timeout=3000)
                    actions.append(f"click #{tid}")
            for mid in ("modeBtnB", "modeBtnC", "modeBtnA"):
                loc = page.locator(f"#{mid}")
                if loc.count() > 0:
                    loc.click(timeout=3000)
                    actions.append(f"click #{mid}")
            s230 = page.locator("#swarm230HeaderBadge").inner_text(timeout=3000)
            h443 = page.locator("#https443HeaderBadge").inner_text(timeout=3000)
            b215 = page.locator("#backlog215HeaderBadge").inner_text(timeout=3000)
            badge_ok = "230 Approved Swarm Units Active/Verified" in s230 and "HTTPS :443 NGINX + Let's Encrypt Cloudflare Wildcard Ready" in h443 and ("215 / 215 (100%) Backlog Accounted" in b215)
            extra["header_badges_verified"] = badge_ok
            actions.append(f"verified 230-Swarm + HTTPS :443 + 215-Backlog badges ({badge_ok})")
            if not badge_ok:
                passed = False
            drawer_btn = page.locator("#btnToggleBacklog215")
            if drawer_btn.count() > 0:
                drawer_btn.click(timeout=3000)
                page.wait_for_timeout(300)
                drawer_txt = page.locator("#backlog215Drawer").inner_text(timeout=3000)
                drawer_ok = "230 Approved Swarm Units" in drawer_txt and "215" in drawer_txt
                extra["drawer_telemetry_verified"] = drawer_ok
                actions.append(f"toggled #backlog215Drawer ({drawer_ok})")
                drawer_btn.click(timeout=3000)
        elif port == 4099:
            tabs = page.locator(".tab")
            cnt = min(tabs.count(), 3)
            for i in range(cnt):
                tabs.nth(i).click(timeout=3000)
                actions.append(f"click sentinel tab {i}")
            if tabs.count() > 0:
                tabs.first.click(timeout=3000)
        elif port == 8090:
            btns = page.locator("button")
            actions.append(f"verified OpenWebUI DOM ({btns.count()} buttons)")
    except Exception as exc:
        actions.append(f"interaction error: {exc}")
        passed = False
    return {"actions": actions, "interactions_passed": passed, "extra": extra}

def verify_5platform_status_apis() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for port in (4081, 4098):
        url = f"http://{HOST_IP}:{port}/api/5platform-status"
        data = http_get_json(url)
        s230 = data.get("swarm_230_headline", "")
        h443 = data.get("https_443_status", "")
        b215 = data.get("backlog_215_headline", "")
        ok = data.get("approved_swarm_units_total") == 230 and "230 Approved Swarm Units Active/Verified" in s230 and ("60 AGY" in s230) and ("110 Cross-Platform" in s230) and ("30 Remote Command Squad & 25-Node Cluster" in s230) and ("30 HTTPS/Cutover" in s230) and (h443 == "HTTPS :443 NGINX + Let's Encrypt Cloudflare Wildcard Ready") and (b215 == "215 / 215 (100%) Backlog Accounted")
        out[f":{port}"] = {"url": url, "ok": ok, "approved_swarm_units_total": data.get("approved_swarm_units_total"), "swarm_230_headline": s230, "https_443_status": h443, "backlog_215_headline": b215}
        log_stream(f"[SWARM-014 API] :{port}/api/5platform-status -> ok={ok} | {s230} | {h443} | {b215}")
    return out

def run_oracle_3viewport_audit(pw: Any, oracle: dict[str, str], jwt_8090: str) -> dict[str, Any]:
    oname = oracle["name"]
    cdp_url = oracle["cdp"]
    log_stream(f"Connecting to Browser Oracle {oname} ({cdp_url})...")
    browser: Browser = pw.chromium.connect_over_cdp(cdp_url, timeout=15000)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    js_errors: list[str] = []
    page.on("pageerror", lambda exc: js_errors.append(str(exc)))
    try:
        page.goto(f"http://{HOST_IP}:8090/", wait_until="domcontentloaded", timeout=15000)
        page.evaluate(f"localStorage.setItem('token', {json.dumps(jwt_8090)});")
    except Exception as exc:
        log_stream(f"[{oname}] Warning seeding :8090 token: {exc}")
    portal_matrix: list[dict[str, Any]] = []
    for port, label in PORTALS:
        url = f"http://{HOST_IP}:{port}/"
        vp_results: dict[str, Any] = {}
        for vp in VIEWPORTS:
            vp_key = vp["key"]
            page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
            errs_before = len(js_errors)
            t0 = time.monotonic()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(450 if port != 8090 else 900)
            http_status = resp.status if resp else 0
            inter = interact_with_portal(page, port, vp_key)
            layout = measure_layout(page)
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            new_errs = js_errors[errs_before:]
            overflow_gate_ok = layout["scrollWidth"] <= layout["clientWidth"] if vp_key in ("1920x1080", "3840x2160") else True
            vp_pass = http_status == 200 and len(new_errs) == 0 and inter["interactions_passed"] and overflow_gate_ok
            vp_results[vp_key] = {"viewport": vp_key, "label": vp["label"], "http_status": http_status, "elapsed_ms": elapsed_ms, "scrollWidth": layout["scrollWidth"], "clientWidth": layout["clientWidth"], "overflowX": layout["overflowX"], "interactiveElements": layout["interactiveElements"], "actions_count": len(inter["actions"]), "actions": inter["actions"], "extra": inter["extra"], "uncaught_js_errors": new_errs, "passed": vp_pass}
            log_stream(f"[{oname}] :{port} @ {vp_key} ({vp['label']}) -> HTTP {http_status} | "
                f"sw={layout['scrollWidth']}/cw={layout['clientWidth']} (overflow={layout['overflowX']}) | "
                f"actions={len(inter['actions'])} | js_err={len(new_errs)} | PASS={vp_pass}")
        all_vp_passed = all((v["passed"] for v in vp_results.values()))
        portal_matrix.append({"port": port, "label": label, "url": url, "viewports": vp_results, "all_viewports_passed": all_vp_passed})
    context.close()
    browser.close()
    return {"oracle": oname, "cdp": cdp_url, "portals_tested": len(portal_matrix), "total_uncaught_js_errors": len(js_errors), "portals": portal_matrix}

def main() -> int:
    log_stream("=== STARTING AGENT-139 3-VIEWPORT (390x844 / 1920x1080 / 3840x2160) & 230-SWARM TELEMETRY E2E AUDIT ===")
    api_status = verify_5platform_status_apis()
    jwt_8090 = make_jwt(OPENWEBUI_ADMIN_ID, OPENWEBUI_SECRET)
    oracle_reports: list[dict[str, Any]] = []
    with sync_playwright() as pw:
        for oracle in ORACLES:
            oracle_reports.append(run_oracle_3viewport_audit(pw, oracle, jwt_8090))
    all_apis_ok = all((v["ok"] for v in api_status.values()))
    all_oracles_ok = all((p["all_viewports_passed"] and o["total_uncaught_js_errors"] == 0 for o in oracle_reports for p in o["portals"]))
    overall_pass = all_apis_ok and all_oracles_ok
    summary = {"agent": "Agent-139", "swarms": ["#009", "#010", "#011", "#012", "#013", "#014", "#015", "#016"], "written_at": utc_now(), "viewports_tested": [v["key"] for v in VIEWPORTS], "portals_tested": [p[0] for p in PORTALS], "api_5platform_status": api_status, "oracles": oracle_reports, "overall_pass": overall_pass}
    os.makedirs(os.path.dirname(RESULTS_JSON), exist_ok=True)
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    log_stream(f"=== COMPLETED AGENT-139 3-VIEWPORT & 230-SWARM E2E AUDIT: OVERALL_PASS={overall_pass} (Saved {RESULTS_JSON}) ===")
    return 0 if overall_pass else 1
if __name__ == "__main__":
    sys.exit(main())
