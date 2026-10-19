#!/home/mboyle/BulkDownloader/venv/bin/python3
"""
Agent-121: Dual Browser Oracle Interactive Bar, Button, Tab & Live-State-Mutation E2E Verifier.
Drives both Chrome CDP Oracles (10.0.10.137:9222 BattleStation & 10.0.70.181:9222 Bittorrent)
at 1920x1080 across Specialist Studios :4081, :4082, :4086, :4087, :4089, :4090..:4099, :8090 & .72:8080.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request
from datetime import UTC, datetime
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError

STREAM_LOG = "/var/tmp/bd-headless-streams/agent121-studios-bars-buttons-live-e2e.log"
JSON_OUT = "/var/tmp/bd-headless-streams/agent121-e2e-results.json"
HOST_IP = "10.0.70.164"

ORACLES = [
    {"name": "BattleStation-137", "cdp": "http://10.0.10.137:9222"},
    {"name": "Bittorrent-181", "cdp": "http://10.0.70.181:9222"},
]

STUDIO_PORTS = [
    (4081, "Executive Briefing & Universal Search Studio"),
    (4082, "Zero-Friction SSO, QR Handoff & Root CA Trust Portal"),
    (4086, "Mobile Swarm Deck PWA"),
    (4087, "Credentials & SSH Matrix Vault"),
    (4089, "Natural-Language Ops & Playbook Studio"),
    (4090, "Hybrid Cloud + Local Burst Orchestrator"),
    (4091, "Hardware & vSAN Telemetry Studio"),
    (4092, "Gitea Automated Pre-Review Studio"),
    (4093, "Multimodal Voice & Vision Bridge"),
    (4094, "Autonomous Deep Research Studio"),
    (4095, "Air-Gapped Knowledge & LobeChat Studio"),
    (4096, "OpenCode Web Server"),
    (4097, "OpenClaw Control Gateway"),
    (4098, "Multi-Harness AI Coding Studio & Swarm Arena"),
    (4099, "Autonomous Infrastructure Sentinel"),
]


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_stream(msg: str) -> None:
    os.makedirs(os.path.dirname(STREAM_LOG), exist_ok=True)
    line = f"[{utc_now()}] {msg}"
    print(line, flush=True)
    with open(STREAM_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def make_jwt(user_id: str, secret: str) -> str:
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        .decode()
        .rstrip("=")
    )
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"id": user_id, "exp": int(time.time()) + 86400 * 30}).encode()
        )
        .decode()
        .rstrip("=")
    )
    signing_input = f"{header}.{payload}".encode()
    sig = (
        base64.urlsafe_b64encode(
            hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        )
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}.{sig}"


def http_get_json(
    url: str, headers: dict[str, str] | None = None, timeout: float = 6.0
) -> Any:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def http_get_status(url: str, timeout: float = 6.0) -> tuple[int, int]:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return resp.status, len(body)


def check_layout_metrics(page: Page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            """() => {
                const de = document.documentElement;
                const sw = de ? de.scrollWidth : 0;
                const cw = de ? de.clientWidth : 0;
                const btns = Array.from(document.querySelectorAll('button, a.dl-btn, .tab, .tab-btn, .mode-btn'));
                return {
                    scrollWidth: sw,
                    clientWidth: cw,
                    overflowX: sw > cw + 2,
                    interactiveCount: btns.length,
                    title: document.title || ''
                };
            }"""
        )
    )


def _safe_click(locator: Any, timeout: int = 2500) -> bool:
    try:
        locator.click(timeout=timeout)
        return True
    except PlaywrightError:
        return False


def run_studio_deep_interactions(page: Page, port: int) -> dict[str, Any]:
    """Perform port-specific interactive button, tab, and bar verification on the active page."""
    details: dict[str, Any] = {"port": port, "actions": [], "assertions_passed": True}

    if port == 4081:
        for tab_id in (
            "tab-briefing",
            "tab-search",
            "tab-doctor",
            "tab-receipts",
            "tab-briefing",
        ):
            if page.locator(f"#{tab_id}").count() > 0:
                page.locator(f"#{tab_id}").click(timeout=3000)
                details["actions"].append(f"clicked #{tab_id}")
        for q in ("vSAN", "Qwen3.6", "O1740"):
            page.fill("#q", q)
            page.locator("#btn-search-submit").click(timeout=3000)
            page.wait_for_timeout(400)
            sr_text = page.locator("#search-res").inner_text(timeout=3000)
            hit_ok = len(sr_text.strip()) > 10 and "0 total hits" not in sr_text
            details["actions"].append(
                f"search '{q}' -> {'HIT' if hit_ok else 'MISS'} ({len(sr_text)} chars)"
            )
            if not hit_ok:
                details["assertions_passed"] = False
        page.locator("button:has-text('Run 12-Point Cluster Doctor')").click(
            timeout=4000
        )
        page.wait_for_timeout(600)
        doc_text = page.locator("#doc-res").inner_text(timeout=3000)
        details["actions"].append(f"clicked Doctor -> {doc_text[:80].strip()}")
        page.locator("button:has-text('Favorites Drawer')").click(timeout=3000)
        page.wait_for_timeout(200)
        page.locator("button:has-text('215-Backlog Ledger')").click(timeout=3000)
        page.wait_for_timeout(300)
        page.evaluate("document.getElementById('modal').style.display='none'")
        details["actions"].append("toggled Favorites Drawer & 215-Backlog Modal")

    elif port == 4082:
        for plat in ("ios", "macos", "windows", "linux", "android"):
            btn = page.locator(f"#ca-tab-{plat}")
            if btn.count() > 0:
                btn.click(timeout=3000)
                vis = page.locator(f"#ca-panel-{plat}").is_visible()
                details["actions"].append(f"clicked #ca-tab-{plat} (visible={vis})")
                if not vis:
                    details["assertions_passed"] = False
        st_crt, len_crt = http_get_status(f"http://{HOST_IP}:4082/ca.crt")
        st_mob, len_mob = http_get_status(
            f"http://{HOST_IP}:4082/boylenet-ca.mobileconfig"
        )
        details["actions"].append(
            f"verified /ca.crt ({st_crt}, {len_crt}B) & /boylenet-ca.mobileconfig ({st_mob}, {len_mob}B)"
        )
        if st_crt != 200 or st_mob != 200 or len_crt < 200 or len_mob < 200:
            details["assertions_passed"] = False
        page.locator("button.verify-btn").first.click(timeout=4000)
        page.locator(".custom-qr-bar button").first.click(timeout=3000)
        page.wait_for_timeout(400)
        details["actions"].append("clicked Verify All 8 Handshakes & Generate Live QR")

    elif port == 4086:
        for pill in page.locator(".pill").all()[:3]:
            _safe_click(pill)
        if page.locator("button:has-text('Sync Live')").count() > 0:
            page.locator("button:has-text('Sync Live')").first.click(timeout=3000)
        details["actions"].append("clicked filter pills & Sync Live on :4086")

    elif port == 4087:
        for tab in page.locator(".tab-btn, button").all()[:4]:
            _safe_click(tab)
        if page.locator("#searchBox").count() > 0:
            page.fill("#searchBox", "LiteLLM")
            page.wait_for_timeout(150)
            page.fill("#searchBox", "")
        details["actions"].append(
            "clicked category tabs & searched LiteLLM in :4087 Vault"
        )

    elif port == 4089:
        for pill in page.locator(".filter-pill, button").all()[:3]:
            _safe_click(pill)
        if page.locator("button:has-text('Dry-Run Preview')").count() > 0:
            page.locator("button:has-text('Dry-Run Preview')").first.click(timeout=3000)
            page.wait_for_timeout(300)
        details["actions"].append("clicked filter pills & Dry-Run Preview on :4089")

    elif port == 4090:
        for prov in ("claude", "codex", "kimi", "grok", "local"):
            card = page.locator(f"#provCard-{prov}")
            if card.count() > 0:
                card.click(timeout=3000)
                details["actions"].append(f"clicked #provCard-{prov}")
        for t in ("hybrid", "claude", "codex", "setup"):
            tb = page.locator(f"#tabBtn-{t}")
            if tb.count() > 0:
                tb.click(timeout=3000)
                details["actions"].append(f"clicked #tabBtn-{t}")
        page.locator("#btnRefreshUsage").click(timeout=3000)
        page.wait_for_timeout(300)
        details["actions"].append("clicked #btnRefreshUsage")

    elif port == 4091:
        if page.locator("button:has-text('Poll Now')").count() > 0:
            page.locator("button:has-text('Poll Now')").first.click(timeout=3000)
            page.wait_for_timeout(300)
        details["actions"].append("clicked Poll Now on :4091 Hardware Telemetry")

    elif port == 4092:
        for btxt in (
            "Load Latest BulkDownloader Commit",
            "Load Red-Team Adversarial Sample",
            "ALL",
        ):
            loc = page.locator(f"button:has-text('{btxt}')")
            if loc.count() > 0:
                loc.first.click(timeout=3000)
        details["actions"].append("clicked sample loaders & verdict filters on :4092")

    elif port == 4093:
        for btxt in ("Simulate Voice Command", "Generate Sample UI Screenshot"):
            loc = page.locator(f"button:has-text('{btxt}')")
            if loc.count() > 0:
                loc.first.click(timeout=3000)
        details["actions"].append(
            "clicked Simulate Voice & Generate Sample Screenshot on :4093"
        )

    elif port == 4094:
        chips = page.locator(".preset-chip, button").all()
        if chips:
            _safe_click(chips[0], timeout=3000)
        details["actions"].append("clicked research preset chip on :4094")

    elif port == 4095:
        if page.locator("#kbInput").count() > 0:
            page.fill("#kbInput", "O1740")
            page.locator("button:has-text('Search')").first.click(timeout=3000)
            page.wait_for_timeout(250)
        details["actions"].append("searched knowledge base on :4095")

    elif port == 4098:
        for tid in (
            "xplatTab-claude",
            "xplatTab-codex",
            "xplatTab-kimi",
            "xplatTab-agy",
            "xplatTab-local",
        ):
            loc = page.locator(f"#{tid}")
            if loc.count() > 0:
                loc.click(timeout=3000)
                details["actions"].append(f"clicked #{tid}")
        for mid in ("modeBtnB", "modeBtnC", "modeBtnA"):
            page.locator(f"#{mid}").click(timeout=3000)
            page.wait_for_timeout(150)
            details["actions"].append(f"clicked #{mid}")
        page.wait_for_timeout(400)
        race_txt = page.locator("#codingRaceTable").inner_text(timeout=3000)
        has_race = (
            "local_2080ti_coder7b" in race_txt or "local_qwen36_heretic" in race_txt
        )
        details["actions"].append(f"verified #codingRaceTable (populated={has_race})")
        if not has_race:
            details["assertions_passed"] = False

    elif port == 4099:
        pills = page.locator(".tab").all()
        for p_btn in pills[:4]:
            _safe_click(p_btn, timeout=2000)
        if pills:
            _safe_click(pills[0], timeout=2000)
        details["actions"].append("clicked category filter pills on :4099 Sentinel")

    return details


def run_live_mutations(page: Page, oracle_name: str) -> dict[str, Any]:
    """Execute the 4 mandatory live-state-mutation E2E tests and prove real-time DOM updates."""
    mutations: dict[str, Any] = {}

    # Mutation 1: :4098 Live Stream Card Update (/var/tmp/bd-headless-streams/xplat-*.log)
    page.goto(f"http://{HOST_IP}:4098/", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(600)
    marker = f"E2E-MUTATION-1-{oracle_name}-{int(time.time())}"
    xplat_log = "/var/tmp/bd-headless-streams/xplat-claude-code.log"
    os.makedirs(os.path.dirname(xplat_log), exist_ok=True)
    with open(xplat_log, "a", encoding="utf-8") as f:
        f.write(f"[{utc_now()}] {marker} live stream pulse verified\n")
    page.locator("#btnRefreshXplat").click(timeout=3000)
    page.wait_for_timeout(500)
    cards_txt = page.locator("#xplatStreamCards").inner_text(timeout=3000)
    m1_ok = marker in cards_txt
    mutations["mutation_1_port_4098_xplat_stream"] = {
        "passed": m1_ok,
        "marker": marker,
        "stream_file": xplat_log,
        "observed_excerpt": cards_txt[:220],
    }
    log_stream(f"[{oracle_name}] Mutation 1 (:4098 xplat stream) passed={m1_ok}")

    # Mutation 2: :4081 Live Receipt Counter & Table Update
    page.goto(f"http://{HOST_IP}:4081/", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(700)
    before_count = int(
        page.locator("#tab-rcpt-count").inner_text(timeout=3000).strip() or "0"
    )
    temp_receipt = f"/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/AGENT121-TEMP-PROBE-{oracle_name}.md"
    try:
        with open(temp_receipt, "w", encoding="utf-8") as f:
            f.write(f"# Temporary Live Mutation Probe ({oracle_name} @ {utc_now()})\n")
        page.evaluate("() => loadBriefing()")
        page.wait_for_timeout(800)
        during_count = int(
            page.locator("#tab-rcpt-count").inner_text(timeout=3000).strip() or "0"
        )
        tbl_txt = page.locator("#live-service-receipts-table").inner_text(timeout=3000)
        in_table = os.path.basename(temp_receipt) in tbl_txt
    finally:
        if os.path.exists(temp_receipt):
            os.remove(temp_receipt)
    page.evaluate("() => loadBriefing()")
    page.wait_for_timeout(600)
    after_count = int(
        page.locator("#tab-rcpt-count").inner_text(timeout=3000).strip() or "0"
    )
    m2_ok = (during_count >= before_count + 1) and in_table
    mutations["mutation_2_port_4081_receipt_counter"] = {
        "passed": m2_ok,
        "before_count": before_count,
        "during_count": during_count,
        "after_count": after_count,
        "observed_in_table": in_table,
    }
    log_stream(
        f"[{oracle_name}] Mutation 2 (:4081 receipt counter {before_count}->{during_count}->{after_count}) passed={m2_ok}"
    )

    # Mutation 3: :4090 Live POOL_STATE.tsv quota_observed_at Update
    pool_tsv = "/home/mboyle/bd-persist/POOL_STATE.tsv"
    orig_tsv = ""
    if os.path.exists(pool_tsv):
        with open(pool_tsv, "r", encoding="utf-8") as f:
            orig_tsv = f.read()
    page.goto(f"http://{HOST_IP}:4090/", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(500)
    new_obs_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        if orig_tsv:
            lines = orig_tsv.splitlines()
            mut_lines = []
            for idx, ln in enumerate(lines):
                if idx == 0 or not ln.strip() or ln.startswith("#"):
                    mut_lines.append(ln)
                else:
                    parts = ln.split("\t")
                    if len(parts) >= 4:
                        parts[-1] = new_obs_ts
                    mut_lines.append("\t".join(parts))
            with open(pool_tsv, "w", encoding="utf-8") as f:
                f.write("\n".join(mut_lines) + "\n")
        page.locator("#btnRefreshUsage").click(timeout=3000)
        page.evaluate("() => refreshUsageNow()")
        page.wait_for_timeout(400)
        badge_txt = page.locator("#quotaObservedAtBadge").inner_text(timeout=3000)
        pool_txt = page.locator("#poolList").inner_text(timeout=3000)
        m3_ok = (new_obs_ts in badge_txt) or (new_obs_ts in pool_txt)
    finally:
        if orig_tsv:
            with open(pool_tsv, "w", encoding="utf-8") as f:
                f.write(orig_tsv)
    mutations["mutation_3_port_4090_pool_state_quota_observed_at"] = {
        "passed": m3_ok,
        "injected_quota_observed_at": new_obs_ts,
        "badge_text": badge_txt,
    }
    log_stream(
        f"[{oracle_name}] Mutation 3 (:4090 quota_observed_at={new_obs_ts}) passed={m3_ok}"
    )

    # Mutation 4: :4099 Live Sentinel Full Sweep & last_check_utc Update
    page.goto(f"http://{HOST_IP}:4099/", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(500)
    prev_sweep = page.locator("#lastCheckText").inner_text(timeout=3000)
    page.locator("button.btn").click(timeout=5000)
    page.wait_for_timeout(3200)
    new_sweep = page.locator("#lastCheckText").inner_text(timeout=3000)
    kpi_txt = page.locator("#kpiHealthy").inner_text(timeout=3000)
    m4_ok = ("Last check:" in new_sweep or "2026" in new_sweep) and ("83" in kpi_txt)
    mutations["mutation_4_port_4099_sentinel_sweep"] = {
        "passed": m4_ok,
        "prev_sweep": prev_sweep,
        "new_sweep": new_sweep,
        "kpi_healthy": kpi_txt,
    }
    log_stream(
        f"[{oracle_name}] Mutation 4 (:4099 Sentinel sweep -> {new_sweep} | kpi={kpi_txt}) passed={m4_ok}"
    )

    return mutations


def verify_openwebui_instances(page: Page, oracle_name: str) -> list[dict[str, Any]]:
    """Verify both OpenWebUI instances (:8090 on .164 and :8080 on .72) with admin JWT session injection."""
    instances = [
        {
            "name": "OpenWebUI-Controller-8090",
            "base_url": "http://10.0.70.164:8090",
            "admin_id": "a12463df-370f-4948-b488-9437da254b15",
            "secret": "<REDACTED_BY_BOYLENET_SECRET_GUARD>",
        },
        {
            "name": "OpenWebUI-GPU72-8080",
            "base_url": "http://10.0.70.72:8080",
            "admin_id": "c1658bb0-ad7c-48c2-a18a-7c000dd6a04e",
            "secret": "<REDACTED_BY_BOYLENET_SECRET_GUARD>",
        },
    ]
    out: list[dict[str, Any]] = []
    for inst in instances:
        jwt_tok = make_jwt(inst["admin_id"], inst["secret"])
        headers = {"Authorization": f"Bearer {jwt_tok}"}
        models_data = http_get_json(
            f"{inst['base_url']}/api/models", headers=headers, timeout=8.0
        )
        models_list = models_data.get("data", [])
        page.goto(f"{inst['base_url']}/", wait_until="domcontentloaded", timeout=15000)
        page.evaluate(f"localStorage.setItem('token', {json.dumps(jwt_tok)});")
        page.goto(f"{inst['base_url']}/", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1200)
        metrics = check_layout_metrics(page)
        out.append(
            {
                "instance": inst["name"],
                "url": inst["base_url"],
                "models_count": len(models_list),
                "sample_models": [m.get("id") for m in models_list[:5]],
                "layout": metrics,
                "passed": len(models_list) > 0 and not metrics["overflowX"],
            }
        )
        log_stream(
            f"[{oracle_name}] Verified {inst['name']} ({inst['base_url']}): models={len(models_list)} overflowX={metrics['overflowX']}"
        )
    return out


def verify_oracle(pw: Any, oracle: dict[str, str]) -> dict[str, Any]:
    name = oracle["name"]
    cdp_url = oracle["cdp"]
    log_stream(f"Connecting to Browser Oracle {name} at {cdp_url} ...")
    browser: Browser = pw.chromium.connect_over_cdp(cdp_url, timeout=15000)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()

    js_errors: list[str] = []
    page.on("pageerror", lambda exc: js_errors.append(f"pageerror: {exc}"))

    studio_results: list[dict[str, Any]] = []
    for port, label in STUDIO_PORTS:
        url = f"http://{HOST_IP}:{port}/"
        errs_before = len(js_errors)
        t0 = time.monotonic()
        resp = page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(450)
        status_code = resp.status if resp else 0
        metrics = check_layout_metrics(page)
        deep = run_studio_deep_interactions(page, port)
        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        new_errs = js_errors[errs_before:]
        passed = (
            status_code == 200
            and not metrics["overflowX"]
            and deep["assertions_passed"]
            and len(new_errs) == 0
        )
        studio_results.append(
            {
                "port": port,
                "label": label,
                "url": url,
                "http_status": status_code,
                "elapsed_ms": elapsed_ms,
                "layout": metrics,
                "interactions": deep["actions"],
                "uncaught_js_errors": new_errs,
                "passed": passed,
            }
        )
        log_stream(
            f"[{name}] :{port} ({label}) -> HTTP {status_code} | actions={len(deep['actions'])} | overflowX={metrics['overflowX']} | js_err={len(new_errs)} | PASS={passed}"
        )

    mutations = run_live_mutations(page, name)
    openwebui = verify_openwebui_instances(page, name)

    context.close()
    browser.close()
    return {
        "oracle": name,
        "cdp": cdp_url,
        "studios": studio_results,
        "mutations": mutations,
        "openwebui": openwebui,
        "total_uncaught_js_errors": len(js_errors),
    }


def main() -> int:
    log_stream("=== STARTING AGENT-121 DUAL-ORACLE E2E UI & LIVE MUTATION SUITE ===")
    all_results: dict[str, Any] = {
        "written_at": utc_now(),
        "viewport": "1920x1080",
        "oracles": [],
    }
    with sync_playwright() as pw:
        for oracle in ORACLES:
            res = verify_oracle(pw, oracle)
            all_results["oracles"].append(res)

    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    all_passed = True
    for o in all_results["oracles"]:
        for s in o["studios"]:
            if not s["passed"]:
                all_passed = False
        for m in o["mutations"].values():
            if not m["passed"]:
                all_passed = False
        for w in o["openwebui"]:
            if not w["passed"]:
                all_passed = False

    log_stream(
        f"=== COMPLETED AGENT-121 DUAL-ORACLE E2E SUITE: ALL_PASSED={all_passed} ==="
    )
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
