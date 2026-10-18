import asyncio
import concurrent.futures
import json
import sys
import time
import urllib.request
from typing import Any, Dict, List
AGENT_WORKLOADS: List[Dict[str, Any]] = [{"agent_id": "Agent-A1", "pool": "Pool-Alpha (.72+.83)", "endpoint": "http://10.0.70.72:8082/v1/chat/completions", "model": "qwen3-coder-30b-a3b", "prompt": "Write a lock-free ring buffer in C11 using stdatomic.h with acquire-release memory ordering. Provide compact production code only."}, {"agent_id": "Agent-A2", "pool": "Pool-Alpha (.72+.83)", "endpoint": "http://10.0.70.72:8082/v1/chat/completions", "model": "qwen3-coder-30b-a3b", "prompt": "Write a Python asyncio token-bucket rate limiter class with async context manager support. Provide compact production code only."}, {"agent_id": "Agent-A3", "pool": "Pool-Alpha (.72+.83)", "endpoint": "http://10.0.70.72:8082/v1/chat/completions", "model": "qwen3-coder-30b-a3b", "prompt": "Write a Linux eBPF XDP packet counter program in C that drops UDP packets on port 9999. Provide compact production code only."}, {"agent_id": "Agent-A4", "pool": "Pool-Alpha (.72+.83)", "endpoint": "http://10.0.70.72:8082/v1/chat/completions", "model": "qwen3-coder-30b-a3b", "prompt": "Write a Rust SIMD-friendly CRC32C checksum function and unit test without external crates. Provide compact production code only."}, {"agent_id": "Agent-B1", "pool": "Pool-Beta (.125+.228)", "endpoint": "http://10.0.70.125:8081/v1/chat/completions", "model": "qwen2.5-coder-32b-distributed", "prompt": "Write a Python SQLite WAL connection pool manager with thread-local cursors and retry on SQLITE_BUSY. Compact code only."}, {"agent_id": "Agent-B2", "pool": "Pool-Beta (.125+.228)", "endpoint": "http://10.0.70.125:8081/v1/chat/completions", "model": "qwen2.5-coder-32b-distributed", "prompt": "Write a Go worker pool with context cancellation, bounded job channel, and graceful WaitGroup shutdown. Compact code only."}, {"agent_id": "Agent-B3", "pool": "Pool-Beta (.125+.228)", "endpoint": "http://10.0.70.125:8081/v1/chat/completions", "model": "qwen2.5-coder-32b-distributed", "prompt": "Write a Bash function that parses /proc/net/dev to compute 1-second RX/TX MiB/s throughput on a network interface. Compact code only."}, {"agent_id": "Agent-B4", "pool": "Pool-Beta (.125+.228)", "endpoint": "http://10.0.70.125:8081/v1/chat/completions", "model": "qwen2.5-coder-32b-distributed", "prompt": "Write a C++20 coroutine generator<uint64_t> that yields Fibonacci numbers with zero heap allocation hints. Compact code only."}]

def run_single_request(task: Dict[str, Any], max_tokens: int=128) -> Dict[str, Any]:
    payload = {"model": task["model"], "messages": [{"role": "system", "content": "Output concise, high-performance code only."}, {"role": "user", "content": task["prompt"]}], "max_tokens": max_tokens, "temperature": 0.0, "stream": False}
    raw_body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(task["endpoint"], data=raw_body, headers={"Content-Type": "application/json"}, method="POST")
    t_start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            status_code = resp.status
            resp_bytes = resp.read()
        t_end = time.perf_counter()
        wall_s = t_end - t_start
        data = json.loads(resp_bytes.decode("utf-8"))
        usage = data.get("usage", {})
        timings = data.get("timings", {})
        prompt_tokens = int(usage.get("prompt_tokens", timings.get("prompt_n", 0)))
        completion_tokens = int(usage.get("completion_tokens", timings.get("predicted_n", 0)))
        slot_ps = float(timings.get("predicted_per_second", 0.0))
        prompt_ps = float(timings.get("prompt_per_second", 0.0))
        wall_tok_s = completion_tokens / wall_s if wall_s > 0 else 0.0
        return {"agent_id": task["agent_id"], "pool": task["pool"], "endpoint": task["endpoint"], "model": task["model"], "http_status": status_code, "error": None, "wall_s": round(wall_s, 3), "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "slot_predicted_tok_s": round(slot_ps, 2), "slot_prompt_tok_s": round(prompt_ps, 2), "wall_tok_s": round(wall_tok_s, 2)}
    except Exception as exc:
        t_end = time.perf_counter()
        return {"agent_id": task["agent_id"], "pool": task["pool"], "endpoint": task["endpoint"], "model": task["model"], "http_status": 0, "error": str(exc), "wall_s": round(t_end - t_start, 3), "prompt_tokens": 0, "completion_tokens": 0, "slot_predicted_tok_s": 0.0, "slot_prompt_tok_s": 0.0, "wall_tok_s": 0.0}

async def run_benchmark() -> int:
    loop = asyncio.get_running_loop()
    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [loop.run_in_executor(executor, run_single_request, task, 128) for task in AGENT_WORKLOADS]
        results = await asyncio.gather(*futures)
    t1 = time.perf_counter()
    total_wall_s = t1 - t0
    alpha_res = [r for r in results if "Alpha" in r["pool"]]
    beta_res = [r for r in results if "Beta" in r["pool"]]
    errors = [r for r in results if r["http_status"] != 200 or r["error"] is not None]
    alpha_wall_s = max((r["wall_s"] for r in alpha_res), default=0.0)
    beta_wall_s = max((r["wall_s"] for r in beta_res), default=0.0)
    alpha_comp_tokens = sum((r["completion_tokens"] for r in alpha_res))
    beta_comp_tokens = sum((r["completion_tokens"] for r in beta_res))
    total_comp_tokens = alpha_comp_tokens + beta_comp_tokens
    alpha_prompt_tokens = sum((r["prompt_tokens"] for r in alpha_res))
    beta_prompt_tokens = sum((r["prompt_tokens"] for r in beta_res))
    total_prompt_tokens = alpha_prompt_tokens + beta_prompt_tokens
    alpha_agg_tok_s = alpha_comp_tokens / alpha_wall_s if alpha_wall_s > 0 else 0.0
    beta_agg_tok_s = beta_comp_tokens / beta_wall_s if beta_wall_s > 0 else 0.0
    cluster_combined_pool_tok_s = alpha_agg_tok_s + beta_agg_tok_s
    cluster_wall_tok_s = total_comp_tokens / total_wall_s if total_wall_s > 0 else 0.0
    summary = {"benchmark": "8-Agent Simultaneous Parallel Continuous Batching (4 Alpha + 4 Beta)", "total_agents": len(results), "http_errors": len(errors), "rc": 0 if len(errors) == 0 else 1, "total_wall_clock_s": round(total_wall_s, 3), "alpha_pool_4stream": {"endpoint": "http://10.0.70.72:8082", "model": "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M", "wall_clock_s": round(alpha_wall_s, 3), "prompt_tokens": alpha_prompt_tokens, "completion_tokens": alpha_comp_tokens, "aggregate_tok_s": round(alpha_agg_tok_s, 2), "per_agent_avg_wall_tok_s": round(sum((r["wall_tok_s"] for r in alpha_res)) / len(alpha_res), 2), "per_agent_avg_slot_tok_s": round(sum((r["slot_predicted_tok_s"] for r in alpha_res)) / len(alpha_res), 2)}, "beta_pool_4stream": {"endpoint": "http://10.0.70.125:8081", "model": "Qwen2.5-Coder-32B-Instruct-Q4_K_M", "wall_clock_s": round(beta_wall_s, 3), "prompt_tokens": beta_prompt_tokens, "completion_tokens": beta_comp_tokens, "aggregate_tok_s": round(beta_agg_tok_s, 2), "per_agent_avg_wall_tok_s": round(sum((r["wall_tok_s"] for r in beta_res)) / len(beta_res), 2), "per_agent_avg_slot_tok_s": round(sum((r["slot_predicted_tok_s"] for r in beta_res)) / len(beta_res), 2)}, "cluster_totals": {"total_prompt_tokens": total_prompt_tokens, "total_completion_tokens": total_comp_tokens, "combined_dual_pool_throughput_tok_s": round(cluster_combined_pool_tok_s, 2), "end_to_end_wall_tok_s": round(cluster_wall_tok_s, 2)}, "streams": results}
    print(json.dumps(summary, indent=2))
    return summary["rc"]
if __name__ == "__main__":
    sys.exit(asyncio.run(run_benchmark()))
