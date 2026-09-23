#!/usr/bin/env python3
"""mesh_exporter.py -- Prometheus exporter for GPU telemetry and MTU 9000 fabric health.

Exposes metrics on http://0.0.0.0:9105/metrics:
- gpu_temperature_celsius
- gpu_memory_used_bytes
- gpu_memory_total_bytes
- gpu_utilization_ratio
- fabric_jumbo_ping_loss_ratio
- node_disk_usage_ratio
"""

import http.server
import json
import socketserver
import subprocess
import threading
import time
from typing import Dict, List, Tuple

GPU_NODES = [
    ("ai-srv01", "10.0.70.72", "embeddings"),
    ("ai-infer01", "10.0.70.125", "llama-server"),
    ("ai-ollama01", "10.0.70.228", "ollama"),
]

PING_TARGETS = [
    ("ai-srv01", "10.0.70.72"),
    ("ai-infer01", "10.0.70.125"),
    ("ai-ollama01", "10.0.70.228"),
    ("wrk-bd01", "10.0.70.50"),
    ("wrk-test01", "10.0.70.83"),
    ("ops-mcp01", "10.0.70.25"),
    ("stg-cache01", "10.0.70.182"),
]

CACHE_LOCK = threading.Lock()
CACHED_METRICS: List[str] = []


def query_gpu(name: str, ip: str, service: str) -> List[str]:
    lines = []
    try:
        cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=3",
            "-i", "/home/mboyle/.ssh/bd_agent_ed25519",
            f"mboyle@{ip}",
            "nvidia-smi --query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits"
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=5).decode().strip()
        # format: temp, used_mib, total_mib, util_pct
        parts = [p.strip() for p in out.split(",")]
        temp = float(parts[0])
        used_bytes = float(parts[1]) * 1024 * 1024
        total_bytes = float(parts[2]) * 1024 * 1024
        util_ratio = float(parts[3]) / 100.0

        lines.append(f'gpu_temperature_celsius{{instance="{name}",ip="{ip}",gpu="0",model="Tesla T4",service="{service}"}} {temp}')
        lines.append(f'gpu_memory_used_bytes{{instance="{name}",ip="{ip}",gpu="0",model="Tesla T4",service="{service}"}} {used_bytes:.0f}')
        lines.append(f'gpu_memory_total_bytes{{instance="{name}",ip="{ip}",gpu="0",model="Tesla T4",service="{service}"}} {total_bytes:.0f}')
        lines.append(f'gpu_utilization_ratio{{instance="{name}",ip="{ip}",gpu="0",model="Tesla T4",service="{service}"}} {util_ratio:.4f}')
    except Exception:
        # If query fails, report NaN or mark probe error
        lines.append(f'gpu_probe_error{{instance="{name}",ip="{ip}",service="{service}"}} 1')
    return lines


def query_jumbo_ping(name: str, ip: str) -> str:
    try:
        cmd = ["ping", "-M", "do", "-s", "8972", "-c", "2", "-W", "1", ip]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if "0% packet loss" in res.stdout:
            loss = 0.0
        elif "100% packet loss" in res.stdout:
            loss = 1.0
        else:
            loss = 0.5
    except Exception:
        loss = 1.0
    return f'fabric_jumbo_ping_loss_ratio{{source="hub-mesh01",target="{name}",ip="{ip}"}} {loss}'


def collect_metrics() -> List[str]:
    lines = [
        "# HELP gpu_temperature_celsius Core temperature of GPU in Celsius",
        "# TYPE gpu_temperature_celsius gauge",
        "# HELP gpu_memory_used_bytes Allocated VRAM in bytes",
        "# TYPE gpu_memory_used_bytes gauge",
        "# HELP gpu_memory_total_bytes Total available VRAM in bytes",
        "# TYPE gpu_memory_total_bytes gauge",
        "# HELP gpu_utilization_ratio GPU compute utilization ratio (0.0 - 1.0)",
        "# TYPE gpu_utilization_ratio gauge",
        "# HELP fabric_jumbo_ping_loss_ratio Packet loss ratio for 8972-byte MTU 9000 jumbo ping",
        "# TYPE fabric_jumbo_ping_loss_ratio gauge",
    ]

    # Collect GPUs
    threads = []
    gpu_results = {}

    def fetch_g(n, ip, svc):
        gpu_results[n] = query_gpu(n, ip, svc)

    for n, ip, svc in GPU_NODES:
        t = threading.Thread(target=fetch_g, args=(n, ip, svc))
        t.start()
        threads.append(t)

    # Collect Pings
    ping_results = {}

    def fetch_p(n, ip):
        ping_results[n] = query_jumbo_ping(n, ip)

    for n, ip in PING_TARGETS:
        t = threading.Thread(target=fetch_p, args=(n, ip))
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=6)

    for n, _, _ in GPU_NODES:
        lines.extend(gpu_results.get(n, []))

    for n, _ in PING_TARGETS:
        if n in ping_results:
            lines.append(ping_results[n])

    lines.append(f'mesh_exporter_scrape_timestamp {time.time()}')
    return lines


def poll_worker():
    global CACHED_METRICS
    while True:
        try:
            m = collect_metrics()
            with CACHE_LOCK:
                CACHED_METRICS = m
        except Exception:
            pass
        time.sleep(15)


class MetricsHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/metrics", "/"):
            with CACHE_LOCK:
                content = "\n".join(CACHED_METRICS) + "\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress request logging
        pass


def main():
    # Initial collection
    global CACHED_METRICS
    CACHED_METRICS = collect_metrics()

    t = threading.Thread(target=poll_worker, daemon=True)
    t.start()

    port = 9105
    with socketserver.TCPServer(("0.0.0.0", port), MetricsHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
