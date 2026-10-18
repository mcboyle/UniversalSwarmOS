#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.error
import urllib.request

HEALTH_TSV = "/home/mboyle/bd-persist/state/LOCAL_LLM_HEALTH.tsv"
LITELLM_URL = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000/v1")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-fleet-local")


def probe_endpoint(url: str, timeout: float = 3.0) -> tuple[bool, float, str]:
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "bd-local-watch"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.perf_counter() - t0
            return (resp.status == 200, elapsed, f"HTTP {resp.status}")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        elapsed = time.perf_counter() - t0
        return (False, elapsed, str(e))


def probe_model(
    model: str, test_prompt: str, expected_key: str | None = None
) -> tuple[bool, float, str]:
    url = f"{LITELLM_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": test_prompt}],
        "max_tokens": 64,
        "temperature": 0.0,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LITELLM_KEY}",
    }
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed = time.perf_counter() - t0
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            if expected_key and expected_key.lower() not in content.lower():
                return (False, elapsed, f"Unexpected response: {content[:40]}")
            return (
                True,
                elapsed,
                f"OK ({data.get('usage', {}).get('completion_tokens', 0)} tok)",
            )
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        KeyError,
        json.JSONDecodeError,
        OSError,
    ) as e:
        elapsed = time.perf_counter() - t0
        return (False, elapsed, str(e))


def run_watchdog() -> dict:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results = {}
    proxy_ok, proxy_lat, proxy_msg = probe_endpoint(
        "http://127.0.0.1:4000/health/liveliness"
    )
    results["litellm_proxy"] = {
        "status": "OK" if proxy_ok else "FAIL",
        "latency_s": round(proxy_lat, 3),
        "detail": proxy_msg,
    }
    triv_ok, triv_lat, triv_msg = probe_model(
        "trivial", "Reply with strictly the word: PONG", expected_key="PONG"
    )
    results["model_trivial"] = {
        "status": "OK" if triv_ok else "FAIL",
        "latency_s": round(triv_lat, 3),
        "detail": triv_msg,
    }
    ci_ok, ci_lat, ci_msg = probe_model(
        "ci-summary",
        "Summarize test failure: FAILED test_sample.py::test_one - AssertionError",
        expected_key="AssertionError",
    )
    results["model_ci_summary"] = {
        "status": "OK" if ci_ok else "FAIL",
        "latency_s": round(ci_lat, 3),
        "detail": ci_msg,
    }
    os.makedirs(os.path.dirname(HEALTH_TSV), exist_ok=True)
    all_ok = all(v["status"] == "OK" for v in results.values())
    overall_status = "HEALTHY" if all_ok else "DEGRADED"
    header_needed = not os.path.exists(HEALTH_TSV)
    with open(HEALTH_TSV, "a") as f:
        if header_needed:
            f.write(
                "timestamp\toverall\tproxy_lat\ttrivial_lat\tci_summary_lat\tdetails\n"
            )
        f.write(
            f"{ts}\t{overall_status}\t{proxy_lat:.3f}s\t{triv_lat:.3f}s\t{ci_lat:.3f}s\t"
            f"proxy={proxy_ok},triv={triv_ok},ci={ci_ok}\n"
        )
    fallback_flag = "/home/mboyle/bd-persist/state/LOCAL_LLM_FALLBACK_ACTIVE"
    if not all_ok:
        with open(fallback_flag, "w") as f:
            f.write(f"DEGRADED at {ts}: {results}\n")
    elif os.path.exists(fallback_flag):
        try:
            os.remove(fallback_flag)
        except OSError:
            pass
    return {"timestamp": ts, "status": overall_status, "components": results}


def main():
    res = run_watchdog()
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["status"] == "HEALTHY" else 1)


if __name__ == "__main__":
    main()
