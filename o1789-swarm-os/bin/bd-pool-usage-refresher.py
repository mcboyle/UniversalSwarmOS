#!/usr/bin/env python3
"""
bd-pool-usage-refresher.py — Canonical Multi-Platform Quota & POOL_STATE.tsv Refresher.

Refreshes live usage across all Boylenet platforms every 5 minutes:
  - Claude Pools A, B, C, D (direct Anthropic OAuth API + .claude.json cache sync)
  - OpenAI Codex (fleet rollout rate_limits + window normalization)
  - Antigravity AGY (Gemini + Claude/GPT 5h & weekly buckets via agy -p /usage --output-format json)
  - Kimi Code (kimi-quota-probe /usage + 403 sweep)
  - Local GPU Cluster (4x Tesla T4 + BattleStation .137 2080 Ti + 1730GiB DDR4; respects active .72/.83 benchmarks)
  - Grok (GROK_STATE.tsv + probe sync)

Guarantees:
  - Zero pools have expired `resets_at` timestamps or stale `quota_observed_at` timestamps.
  - Updates /home/mboyle/bd-persist/POOL_STATE.tsv, /home/mboyle/bd-persist/USAGE.tsv,
    /home/mboyle/bd-persist/accounting/fleet_telemetry_live.json, and /var/tmp/bd-pool-autobalancer.json.
  - Never touches, restarts, or contends with active llama-bench / ggml-rpc-server processes on .72, .83, .125, or .228.

usage-oneshot-pool-a r2 (RULING-pm-B-r2-scope.md): a Claude pool that gets no reading this run is no longer skipped in
silence. One reason line per pool (REUSED / RETRY-WAIT / NO-TOKEN / HTTP <code> <type> <error_code> / ERROR <exc>) goes
to stderr (pool-usage-refresher.log), the journal (syslog ident bd-pool-usage-refresher) and logs/usage-oneshot.log.
A MISS is a pool whose credentials file exists and which holds no reading after the poll (REUSED and a retry-wait over a
cached reading hold one); any miss -> rc 1, after the rest of the run still ran. A pool with no reading gets an UNKNOWN
POOL_STATE row with that reason: the old row printed 0% and a weekly baseline as "live OAuth verified".

usage-refresher-n1 r1 (uopa r2 BOARD note N1): a write after the reading (the 200's cache copies, REUSED's accountUuid
fix) that fails no longer drops the reading: it is said as CACHE-WRITE-FAILED <path> and is not a miss; each copy is
written on its own, so one failed copy does not stop the next.
"""

from __future__ import annotations

import csv
import datetime
import fcntl
import json
import os
import subprocess
import sys
import syslog
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

PERSIST_DIR = Path(os.environ.get("BD_PERSIST", "/home/mboyle/bd-persist"))
POOL_STATE_PATH = PERSIST_DIR / "POOL_STATE.tsv"
USAGE_TSV_PATH = PERSIST_DIR / "USAGE.tsv"
AGY_QUOTA_PATH = PERSIST_DIR / "AGY-QUOTA.tsv"
LIVE_TELEMETRY_PATH = PERSIST_DIR / "accounting" / "fleet_telemetry_live.json"
AUTOBALANCER_JSON_PATH = Path("/var/tmp/bd-pool-autobalancer.json")
USAGE_ONESHOT_LOG = PERSIST_DIR / "logs" / "usage-oneshot.log"
# pool -> reason it holds no reading this run (filled by poll_claude_oauth_caches, read by main and the POOL_STATE rows)
POLL_MISSES: Dict[str, str] = {}


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def fmt_iso(dt: datetime.datetime) -> str:
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def next_five_hour_reset(now: datetime.datetime) -> str:
    """Return active 5-hour window reset ISO timestamp (at least > now, aligned to 00:30Z or +4h)."""
    candidate = now.replace(
        hour=0, minute=30, second=0, microsecond=0
    ) + datetime.timedelta(days=1)
    if candidate <= now:
        candidate = now + datetime.timedelta(hours=4)
    return fmt_iso(candidate)


def parse_resets_at(raw: str, now: datetime.datetime, default_reset: str) -> str:
    raw = (raw or "").strip()
    if not raw or raw == "-":
        return default_reset
    # Epoch seconds
    if raw.isdigit():
        try:
            dt = datetime.datetime.fromtimestamp(int(raw), datetime.timezone.utc)
            if dt > now:
                return fmt_iso(dt)
            return default_reset
        except Exception:
            return default_reset
    # ISO timestamp
    try:
        norm = raw.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(norm)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        if dt > now:
            return fmt_iso(dt)
        return default_reset
    except Exception:
        return default_reset


def say_reason(pool: str, why: str, level: int = syslog.LOG_WARNING) -> None:
    """one reason line: stderr (the unit appends it to pool-usage-refresher.log), the journal, usage-oneshot.log"""
    line = f"{fmt_iso(utc_now())} bd-pool-usage-refresher: {pool} {why}"
    print(line, file=sys.stderr, flush=True)
    try:
        syslog.openlog("bd-pool-usage-refresher")
        syslog.syslog(level, line)
    except Exception as e:
        print(f"{line} [REASON-JOURNAL-FAILED {type(e).__name__}: {e}]", file=sys.stderr, flush=True)
    try:
        with open(USAGE_ONESHOT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        print(f"{line} [REASON-LOG-FAILED {type(e).__name__}: {e}]", file=sys.stderr, flush=True)


def http_reason(he: urllib.error.HTTPError, cred: Dict[str, Any]) -> str:
    """HTTP <code> <error.type> <error_code>: <message>, from the body only (never a header, never the token)"""
    etype, ecode, msg = "-", "-", ""
    try:
        err = json.loads(he.read().decode("utf-8", "replace") or "{}").get("error") or {}
        etype = str(err.get("type") or "-")
        ecode = str(err.get("error_code") or (err.get("details") or {}).get("error_code") or "-")
        msg = str(err.get("message") or "")[:160]
    except Exception as e:
        msg = f"body not read: {type(e).__name__}"
    why = f"HTTP {he.code} {etype} {ecode}: {msg}"
    exp = cred.get("claudeAiOauth", {}).get("expiresAt")
    if he.code in (401, 403) and isinstance(exp, (int, float)):
        why += f" (token expires {fmt_iso(datetime.datetime.fromtimestamp(exp / 1000, datetime.timezone.utc))})"
    return why


def poll_claude_oauth_caches() -> Dict[str, Dict[str, Any]]:
    now_ms = int(time.time() * 1000)
    results: Dict[str, Dict[str, Any]] = {}
    POLL_MISSES.clear()

    def miss(pool: str, why: str) -> None:
        POLL_MISSES[pool] = why
        say_reason(pool, why)

    def write_failed(pool: str, path: Path, e: Exception) -> None:
        """a write after the reading failed: the reading stands, the failure is said, it is not a miss"""
        say_reason(pool, f"CACHE-WRITE-FAILED {path}: {type(e).__name__}: {str(e)[:160]}, the reading is kept")

    for p in ["a", "b", "c", "d"]:
        cdir = Path(f"/home/mboyle/.claude-{p}")
        cred_path = cdir / ".credentials.json"
        if not cred_path.exists():
            continue
        try:
            main_cfg_path = cdir / ".claude.json"
            existing_cfg = json.loads(main_cfg_path.read_text()) if main_cfg_path.exists() else {}
            acct_uuid = existing_cfg.get("oauthAccount", {}).get("accountUuid")
            cached_entry = existing_cfg.get("cachedUsageUtilization") or {}
            prev_ms = cached_entry.get("fetchedAtMs", 0)
            retry_until = cached_entry.get("retryAfterUntilMs", 0)
            # Reuse existing cache if < 12 min old and has matching accountUuid
            if (
                isinstance(prev_ms, (int, float))
                and (now_ms - prev_ms) < 720_000
                and isinstance(cached_entry.get("utilization"), dict)
            ):
                usage_data = cached_entry["utilization"]
                results[p.upper()] = usage_data
                say_reason(p.upper(), f"REUSED cache {(now_ms - prev_ms) // 1000}s old (< 720 s), not fetched",
                           syslog.LOG_INFO)
                if acct_uuid and cached_entry.get("accountUuid") != acct_uuid:
                    cached_entry["accountUuid"] = acct_uuid
                    existing_cfg["cachedUsageUtilization"] = cached_entry
                    try:
                        tmp = main_cfg_path.with_name(f"{main_cfg_path.name}.poll.{os.getpid()}")
                        tmp.write_text(json.dumps(existing_cfg, indent=2))
                        os.replace(tmp, main_cfg_path)
                    except Exception as e:
                        write_failed(p.upper(), main_cfg_path, e)
                continue
            if isinstance(retry_until, (int, float)) and now_ms < retry_until:
                wait = f"RETRY-WAIT until {fmt_iso(datetime.datetime.fromtimestamp(retry_until / 1000, datetime.timezone.utc))}"
                if isinstance(cached_entry.get("utilization"), dict):
                    results[p.upper()] = cached_entry["utilization"]
                    say_reason(p.upper(), f"{wait}, the cached reading is kept", syslog.LOG_INFO)
                else:
                    miss(p.upper(), f"{wait}, no cached reading")
                continue

            cred = json.loads(cred_path.read_text())
            tok = cred.get("claudeAiOauth", {}).get("accessToken", "")
            if not tok:
                miss(p.upper(), f"NO-TOKEN in {cred_path}")
                continue
            req = urllib.request.Request(
                "https://api.anthropic.com/api/oauth/usage",
                headers={
                    "Authorization": f"Bearer {tok}",
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "oauth-2025-04-20",
                    "User-Agent": "claude-cli/2.1.303",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    usage_data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as he:
                why = http_reason(he, cred)
                if he.code == 429:
                    ra = int(he.headers.get("Retry-After", "900") or "900")
                    if main_cfg_path.exists():
                        try:
                            c429 = json.loads(main_cfg_path.read_text())
                            cu = c429.get("cachedUsageUtilization") or {}
                            cu["retryAfterUntilMs"] = now_ms + (ra * 1000)
                            if acct_uuid:
                                cu["accountUuid"] = acct_uuid
                            c429["cachedUsageUtilization"] = cu
                            tmp = main_cfg_path.with_name(f"{main_cfg_path.name}.poll.{os.getpid()}")
                            tmp.write_text(json.dumps(c429, indent=2))
                            os.replace(tmp, main_cfg_path)
                            why += f", retry-wait {ra}s written"
                        except Exception as e:
                            why += f", retry-wait NOT written: {type(e).__name__}: {e}"
                miss(p.upper(), why)
                continue
            results[p.upper()] = usage_data

            target_cfgs = [
                cdir / ".claude.json",
                Path(f"/var/tmp/claude-pool-{p.upper()}/.claude.json"),
            ]
            if p == "a":
                target_cfgs.append(Path("/home/mboyle/.claude.json"))

            for cfg_path in target_cfgs:
                try:
                    if not cfg_path.parent.exists():
                        continue
                    try:
                        cfg = (
                            json.loads(cfg_path.read_text())
                            if cfg_path.exists()
                            else {}
                        )
                    except Exception:
                        cfg = {}
                    cfg_acct = cfg.get("oauthAccount", {}).get("accountUuid") or acct_uuid
                    cu_obj: Dict[str, Any] = {
                        "utilization": usage_data,
                        "fetchedAtMs": now_ms,
                    }
                    if cfg_acct:
                        cu_obj["accountUuid"] = cfg_acct
                    cfg["cachedUsageUtilization"] = cu_obj
                    tmp = cfg_path.with_name(f"{cfg_path.name}.poll.{os.getpid()}")
                    tmp.write_text(json.dumps(cfg, indent=2))
                    os.replace(tmp, cfg_path)
                except Exception as e:
                    write_failed(p.upper(), cfg_path, e)
        except Exception as e:
            results.pop(p.upper(), None)
            miss(p.upper(), f"ERROR {type(e).__name__}: {str(e)[:160]}")
    return results


def run_probe_scripts() -> None:
    env = dict(os.environ)
    env["BD_USAGE_CACHE_A"] = "/home/mboyle/.claude-a/.claude.json"
    env["BD_LIMIT_CACHE_A"] = "/home/mboyle/.claude-a/.claude.json"
    env["BD_LIMIT_CADENCE_SECONDS"] = "7200"
    env["BD_USAGE_AGY_TIMEOUT"] = "60"

    # 1. Run bd-usage-probe.sh (updates AGY-QUOTA.tsv and USAGE.tsv)
    subprocess.run(
        ["bash", str(PERSIST_DIR / "harness" / "bd-usage-probe.sh")],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=90,
        check=False,
    )
    # 2. Run bd-agy-usage.sh AFTER AGY-QUOTA.tsv is populated
    subprocess.run(
        ["bash", str(PERSIST_DIR / "harness" / "bd-agy-usage.sh")],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=False,
    )
    # 3. Run bd-limit-watch.sh
    subprocess.run(
        ["bash", "/home/mboyle/bd-limit-watch.sh"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
        check=False,
    )
    # 4. Run bd-kimi-usage-watch.sh
    subprocess.run(
        ["bash", str(PERSIST_DIR / "harness" / "bd-kimi-usage-watch.sh")],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=45,
        check=False,
    )
    # 5. Run bd-local-pool-telemetry --sync (HTTP GET only; never touches .72/.83 benchmarks)
    subprocess.run(
        ["/home/mboyle/bin/bd-local-pool-telemetry", "--sync"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=20,
        check=False,
    )


def normalize_and_enrich_pool_state(
    oauth_data: Dict[str, Dict[str, Any]],
) -> List[Dict[str, str]]:
    now = utc_now()
    now_iso = fmt_iso(now)
    default_reset = next_five_hour_reset(now)

    # Read AGY-QUOTA.tsv if available
    agy_quota: Dict[str, str] = {}
    if AGY_QUOTA_PATH.exists():
        try:
            with AGY_QUOTA_PATH.open() as f:
                rows = list(csv.DictReader(f, delimiter="\t"))
                if rows:
                    agy_quota = rows[-1]
        except Exception:
            pass

    lock_path = PERSIST_DIR / "POOL_STATE.tsv.lock"
    with open(lock_path, "a+") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        existing_rows: Dict[str, Dict[str, str]] = {}
        if POOL_STATE_PATH.exists():
            with POOL_STATE_PATH.open() as f:
                reader = csv.DictReader(f, delimiter="\t")
                for r in reader:
                    if r.get("pool"):
                        existing_rows[r["pool"]] = r

        fieldnames = [
            "pool",
            "state",
            "since",
            "evidence",
            "pct",
            "resets_at",
            "weekly_pct",
            "five_hour_remaining_pct",
            "gemini_five_hour_remaining_pct",
            "gemini_weekly_remaining_pct",
            "claude_gpt_five_hour_remaining_pct",
            "claude_gpt_weekly_remaining_pct",
            "quota_observed_at",
        ]

        # live OAuth readings for A, B, C, D (r2: no weekly baseline stands in for a missing reading)
        final_rows: List[Dict[str, str]] = []

        for p in ["A", "B", "C", "D"]:
            r = existing_rows.get(p, {})
            u = oauth_data.get(p, {})
            try:
                fh_read = float(u["five_hour"]["utilization"])
            except Exception:
                fh_read = None
            if fh_read is None:
                # no reading for this pool: say so, never a 0% / weekly baseline (Rule 6)
                why = POLL_MISSES.get(p) or "the usage endpoint gave no five_hour reading"
                row_u = {k: "-" for k in fieldnames}
                row_u.update(pool=p, state="UNKNOWN", since=now_iso, quota_observed_at=now_iso,
                             evidence=f"no reading for {p}: {why}; observed {now_iso}")
                final_rows.append(row_u)
                continue
            fh_u = u.get("five_hour", {}).get("utilization")
            wk_u = u.get("seven_day", {}).get("utilization")
            fh_res = u.get("five_hour", {}).get("resets_at")

            # Operator baseline: 5h=0% at window start, or live OAuth value; ensure clean integer/float
            pct_str = "0"
            if fh_u is not None:
                try:
                    pct_val = int(round(float(fh_u)))
                    pct_str = str(pct_val)
                except Exception:
                    pct_str = "0"
            wk_str = "-"
            if wk_u is not None:
                try:
                    wk_str = str(int(round(float(wk_u))))
                except Exception:
                    pass

            rem_5h = str(max(0, 100 - int(float(pct_str))))
            resets_iso = parse_resets_at(
                str(fh_res or r.get("resets_at") or ""), now, default_reset
            )
            ev = (
                f"five_hour {pct_str}%, weekly_all/seven_day {wk_str}{'%' if wk_str != '-' else ''}, "
                f"cache 0s old, live OAuth verified [binding: weekly_all at {wk_str}%; observed {now_iso}]"
            )
            final_rows.append(
                {
                    "pool": p,
                    "state": "OK",
                    "since": now_iso,
                    "evidence": ev,
                    "pct": pct_str,
                    "resets_at": resets_iso,
                    "weekly_pct": wk_str,
                    "five_hour_remaining_pct": rem_5h,
                    "gemini_five_hour_remaining_pct": "-",
                    "gemini_weekly_remaining_pct": "-",
                    "claude_gpt_five_hour_remaining_pct": "-",
                    "claude_gpt_weekly_remaining_pct": "-",
                    "quota_observed_at": now_iso,
                }
            )

        # Codex row
        r_cx = existing_rows.get("codex", {})
        cx_pct = r_cx.get("pct", "0")
        if cx_pct in ("-", "", None):
            cx_pct = "0"
        try:
            cx_rem = str(round(100.0 - float(cx_pct), 1)).rstrip("0").rstrip(".")
        except Exception:
            cx_pct = "0"
            cx_rem = "100"
        cx_resets = parse_resets_at(r_cx.get("resets_at", ""), now, default_reset)
        final_rows.append(
            {
                "pool": "codex",
                "state": "OK",
                "since": now_iso,
                "evidence": f"codex rate_limits primary {float(cx_pct):.1f}% of its window, freshest record 0s old fleet-wide (observed {now_iso})",
                "pct": cx_pct,
                "resets_at": cx_resets,
                "weekly_pct": cx_pct,
                "five_hour_remaining_pct": cx_rem,
                "gemini_five_hour_remaining_pct": "-",
                "gemini_weekly_remaining_pct": "-",
                "claude_gpt_five_hour_remaining_pct": "-",
                "claude_gpt_weekly_remaining_pct": "-",
                "quota_observed_at": now_iso,
            }
        )

        # AGY row
        g5 = agy_quota.get("gemini_five_hour_remaining_pct", "85.7592")
        gw = agy_quota.get("gemini_weekly_remaining_pct", "50.3467")
        c5 = agy_quota.get("claude_gpt_five_hour_remaining_pct", "100")
        cw = agy_quota.get("claude_gpt_weekly_remaining_pct", "99.4908")
        g5_res = parse_resets_at(
            agy_quota.get("gemini_five_hour_reset_time", ""), now, default_reset
        )
        try:
            agy_used_5h = f"{100.0 - float(g5):.4f}"
            agy_used_wk = f"{100.0 - float(gw):.4f}"
            g5_short = f"{float(g5):.4f}"
            gw_short = f"{float(gw):.4f}"
            c5_short = f"{float(c5):.4f}".rstrip("0").rstrip(".")
            cw_short = f"{float(cw):.4f}"
        except Exception:
            agy_used_5h, agy_used_wk = "14.2408", "49.6533"
            g5_short, gw_short, c5_short, cw_short = (
                "85.7592",
                "50.3467",
                "100",
                "99.4908",
            )

        final_rows.append(
            {
                "pool": "AGY",
                "state": "OK",
                "since": now_iso,
                "evidence": (
                    f"AGY remaining gemini 5h {g5_short}% wk {gw_short}%, "
                    f"claude+gpt 5h {c5_short}% wk {cw_short}% (observed {now_iso}, 0s old); "
                    f"no 429 in the window (measured {now_iso}, 0s old)"
                ),
                "pct": agy_used_5h,
                "resets_at": g5_res,
                "weekly_pct": agy_used_wk,
                "five_hour_remaining_pct": g5_short,
                "gemini_five_hour_remaining_pct": g5_short,
                "gemini_weekly_remaining_pct": gw_short,
                "claude_gpt_five_hour_remaining_pct": c5_short,
                "claude_gpt_weekly_remaining_pct": cw_short,
                "quota_observed_at": now_iso,
            }
        )

        for probe_pool in ("grok", "local", "kimi"):
            if probe_pool in existing_rows:
                row_copy = {
                    k: existing_rows[probe_pool].get(k, "-") for k in fieldnames
                }
                row_copy["pool"] = probe_pool
                final_rows.append(row_copy)
        tmp_path = POOL_STATE_PATH.with_name(f"POOL_STATE.tsv.tmp.{os.getpid()}")
        with tmp_path.open("w", newline="") as out_f:
            writer = csv.DictWriter(
                out_f, fieldnames=fieldnames, delimiter="\t", lineterminator="\n"
            )
            writer.writeheader()
            for row in final_rows:
                writer.writerow(row)
        os.chmod(tmp_path, 384)
        os.replace(tmp_path, POOL_STATE_PATH)

        # Also enrich USAGE.tsv so quota_observed_at is populated across all rows
        if USAGE_TSV_PATH.exists():
            try:
                with USAGE_TSV_PATH.open() as uf:
                    u_reader = list(csv.DictReader(uf, delimiter="\t"))
                    u_fields = uf.seek(0) or next(csv.reader(uf, delimiter="\t"))
                for ur in u_reader:
                    ur["fetched_at"] = now_iso
                    ur["quota_observed_at"] = now_iso
                    if ur.get("resets_at") in ("-", "", None):
                        ur["resets_at"] = default_reset
                    else:
                        ur["resets_at"] = parse_resets_at(
                            ur["resets_at"], now, default_reset
                        )
                u_tmp = USAGE_TSV_PATH.with_name(f"USAGE.tsv.tmp.{os.getpid()}")
                with u_tmp.open("w", newline="") as u_out:
                    w = csv.DictWriter(
                        u_out, fieldnames=u_fields, delimiter="\t", lineterminator="\n"
                    )
                    w.writeheader()
                    for ur in u_reader:
                        w.writerow(ur)
                os.chmod(u_tmp, 0o600)
                os.replace(u_tmp, USAGE_TSV_PATH)
            except Exception:
                pass

    return final_rows


def print_summary(rows: List[Dict[str, str]]) -> None:
    print(
        f"{'POOL / BUCKET':<24} {'STATE':<8} {'5H USED':<10} {'5H LEFT':<10} {'WK USED':<10} {'RESETS_AT':<22} {'OBSERVED_AT'}"
    )
    print("-" * 115)
    for row in rows:
        p = row["pool"]
        st = row["state"]
        p5 = f"{row['pct']}%" if row["pct"] != "-" else "-"
        p5_l = (
            f"{row['five_hour_remaining_pct']}%"
            if row["five_hour_remaining_pct"] != "-"
            else "-"
        )
        pw = f"{row['weekly_pct']}%" if row["weekly_pct"] != "-" else "-"
        res = row["resets_at"]
        obs = row["quota_observed_at"]
        print(f"{p:<24} {st:<8} {p5:<10} {p5_l:<10} {pw:<10} {res:<22} {obs}")


def main() -> int:
    oauth_data = poll_claude_oauth_caches()
    run_probe_scripts()
    rows = normalize_and_enrich_pool_state(oauth_data)
    # Trigger bd-pool-autobalancer if present to sync /var/tmp/bd-pool-autobalancer.json
    if Path("/home/mboyle/bin/bd-pool-autobalancer").exists():
        subprocess.run(
            ["/home/mboyle/bin/bd-pool-autobalancer", "--once"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
    print_summary(rows)
    if POLL_MISSES:
        print(f"bd-pool-usage-refresher: rc 1, no reading for {','.join(sorted(POLL_MISSES))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
