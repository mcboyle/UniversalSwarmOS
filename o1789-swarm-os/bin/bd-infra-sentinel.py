from __future__ import annotations
import concurrent.futures
import json
import os
import shlex
import socket
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple

LISTEN_HOST = os.environ.get("BD_SENTINEL_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("BD_SENTINEL_PORT", "4099"))
CHECK_INTERVAL_SEC = int(os.environ.get("BD_SENTINEL_INTERVAL", "60"))
CONSECUTIVE_FAIL_THRESHOLD = 2
LOG_FILE = "/var/log/bd-infra-sentinel.log"
FALLBACK_LOG_FILE = "/var/tmp/bd-infra-sentinel.log"
STATE_JSON_FILE = "/var/tmp/bd-infra-sentinel.json"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_log(line: str) -> None:
    stamp = utc_now()
    entry = f"[{stamp}] {line}\n"
    for path in (LOG_FILE, FALLBACK_LOG_FILE):
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(entry)
            break
        except OSError:
            continue


SERVICES: List[Dict[str, Any]] = [
    {
        "id": "164-systemd-cockpit",
        "name": "bd-cockpit-ui.service",
        "unit": "bd-cockpit.service",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-systemd",
        "port": 3002,
        "probe_type": "http",
        "target": "http://10.0.70.164:3002",
        "heal_type": "systemd-user",
        "heal_cmd": "XDG_RUNTIME_DIR=/run/user/1000 systemctl --user restart bd-cockpit.service",
    },
    {
        "id": "164-systemd-chat",
        "name": "bd-chat-ui.service",
        "unit": "bd-chat.service",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-systemd",
        "port": 3003,
        "probe_type": "http",
        "target": "http://10.0.70.164:3003",
        "heal_type": "systemd-user",
        "heal_cmd": "XDG_RUNTIME_DIR=/run/user/1000 systemctl --user restart bd-chat.service",
    },
    {
        "id": "164-systemd-gpu-orchestrator",
        "name": "bd-gpu-orchestrator.service",
        "unit": "bd-gpu-orchestrator.service",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-systemd",
        "port": 4010,
        "probe_type": "http",
        "target": "http://10.0.70.164:4010/health",
        "heal_type": "systemd",
        "heal_cmd": "sudo systemctl restart bd-gpu-orchestrator.service",
    },
    {
        "id": "164-systemd-opencode",
        "name": "bd-opencode-web.service",
        "unit": "bd-opencode-web.service",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-systemd",
        "port": 4096,
        "probe_type": "http",
        "target": "http://10.0.70.164:4096",
        "heal_type": "systemd",
        "heal_cmd": "sudo systemctl restart bd-opencode-web.service",
    },
    {
        "id": "164-systemd-openclaw",
        "name": "bd-openclaw-web.service",
        "unit": "bd-openclaw-web.service",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-systemd",
        "port": 4097,
        "probe_type": "http",
        "target": "http://10.0.70.164:4097",
        "heal_type": "systemd",
        "heal_cmd": "sudo systemctl restart bd-openclaw-web.service",
    },
    {
        "id": "164-systemd-multi-harness",
        "name": "bd-multi-harness-web.service",
        "unit": "bd-multi-harness-web.service",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-systemd",
        "port": 4098,
        "probe_type": "http",
        "target": "http://10.0.70.164:4098/health",
        "heal_type": "systemd",
        "heal_cmd": "sudo systemctl restart bd-multi-harness-web.service",
    },
    {
        "id": "164-systemd-sentinel",
        "name": "bd-infra-sentinel.service",
        "unit": "bd-infra-sentinel.service",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-systemd",
        "port": 4099,
        "probe_type": "self",
        "target": "http://10.0.70.164:4099/health",
        "heal_type": "systemd",
        "heal_cmd": "sudo systemctl restart bd-infra-sentinel.service",
    },
    {
        "id": "164-systemd-mcp",
        "name": "bd-mcp.service",
        "unit": "bd-mcp.service",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-systemd",
        "port": 8100,
        "probe_type": "tcp",
        "target": "10.0.70.164:8100",
        "heal_type": "systemd",
        "heal_cmd": "sudo systemctl restart bd-mcp.service",
    },
    {
        "id": "164-systemd-rag",
        "name": "bd-rag.service",
        "unit": "bd-rag.service",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-systemd",
        "port": 8099,
        "probe_type": "tcp",
        "target": "10.0.70.164:8099",
        "heal_type": "systemd",
        "heal_cmd": "sudo systemctl restart bd-rag.service",
    },
    {
        "id": "164-systemd-novnc",
        "name": "bd-novnc.service",
        "unit": "bd-novnc.service",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-systemd",
        "port": 6080,
        "probe_type": "http",
        "target": "http://10.0.70.164:6080/vnc.html",
        "heal_type": "systemd",
        "heal_cmd": "sudo systemctl restart bd-novnc.service",
    },
    {
        "id": "164-docker-dashy",
        "name": "dashy (:4080)",
        "unit": "dashy-portal",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 4080,
        "probe_type": "http",
        "target": "http://10.0.70.164:4080",
        "heal_type": "docker",
        "heal_cmd": "docker restart dashy-portal",
    },
    {
        "id": "164-docker-lobechat",
        "name": "lobechat (:4095)",
        "unit": "lobechat-studio",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 4095,
        "probe_type": "http",
        "target": "http://10.0.70.164:4095",
        "heal_type": "docker",
        "heal_cmd": "docker restart lobechat-studio",
    },
    {
        "id": "164-docker-litellm",
        "name": "litellm-proxy (:4000/health/liveliness)",
        "unit": "litellm-proxy",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 4000,
        "probe_type": "http",
        "target": "http://10.0.70.164:4000/health/liveliness",
        "heal_type": "docker",
        "heal_cmd": "docker restart litellm-proxy",
    },
    {
        "id": "164-docker-openwebui",
        "name": "open-webui (:8090)",
        "unit": "open-webui",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 8090,
        "probe_type": "http",
        "target": "http://10.0.70.164:8090",
        "heal_type": "docker",
        "heal_cmd": "docker restart open-webui",
    },
    {
        "id": "164-docker-gitea",
        "name": "gitea (:3000)",
        "unit": "forgejo",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 3000,
        "probe_type": "http",
        "target": "http://10.0.70.164:3000",
        "heal_type": "docker",
        "heal_cmd": "docker restart forgejo",
    },
    {
        "id": "164-docker-grafana",
        "name": "grafana (:3001)",
        "unit": "grafana-dashboards",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 3001,
        "probe_type": "http",
        "target": "http://10.0.70.164:3001",
        "heal_type": "docker",
        "heal_cmd": "docker restart grafana-dashboards",
    },
    {
        "id": "164-docker-prometheus",
        "name": "prometheus (:9090)",
        "unit": "prometheus",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 9090,
        "probe_type": "http",
        "target": "http://10.0.70.164:9090/-/healthy",
        "heal_type": "docker",
        "heal_cmd": "docker restart prometheus",
    },
    {
        "id": "164-docker-alertmanager",
        "name": "alertmanager (:9093)",
        "unit": "alertmanager",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 9093,
        "probe_type": "http",
        "target": "http://10.0.70.164:9093/-/healthy",
        "heal_type": "docker",
        "heal_cmd": "docker restart alertmanager",
    },
    {
        "id": "164-docker-minio",
        "name": "minio (:9001)",
        "unit": "minio",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 9001,
        "probe_type": "http",
        "target": "http://10.0.70.164:9001",
        "heal_type": "docker",
        "heal_cmd": "docker restart minio",
    },
    {
        "id": "164-docker-traefik",
        "name": "traefik-ingress (:8080)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 8080,
        "probe_type": "http",
        "target": "http://10.0.70.164:8080/dashboard/",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "164-docker-cadvisor",
        "name": "cadvisor (:8085)",
        "unit": "cadvisor-metrics",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 8085,
        "probe_type": "http",
        "target": "http://10.0.70.164:8085/containers/",
        "heal_type": "docker",
        "heal_cmd": "docker restart cadvisor-metrics",
    },
    {
        "id": "164-docker-devdocs",
        "name": "devdocs (:8088)",
        "unit": "devdocs-mirror",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 8088,
        "probe_type": "http",
        "target": "http://10.0.70.164:8088",
        "heal_type": "docker",
        "heal_cmd": "docker restart devdocs-mirror",
    },
    {
        "id": "164-docker-searxng",
        "name": "searxng (:8888)",
        "unit": "searxng-search",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 8888,
        "probe_type": "http",
        "target": "http://10.0.70.164:8888",
        "heal_type": "docker",
        "heal_cmd": "docker restart searxng-search",
    },
    {
        "id": "164-docker-codeserver",
        "name": "code-server (:8443)",
        "unit": "code-server",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 8443,
        "probe_type": "http",
        "target": "http://10.0.70.164:8443",
        "heal_type": "docker",
        "heal_cmd": "docker restart code-server",
    },
    {
        "id": "164-docker-tei-embed",
        "name": "tei-embed (:8081/health)",
        "unit": "tei-embeddings",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 8081,
        "probe_type": "http",
        "target": "http://10.0.70.164:8081/health",
        "heal_type": "docker",
        "heal_cmd": "docker restart tei-embeddings",
    },
    {
        "id": "164-docker-tei-rerank",
        "name": "tei-rerank (:8082/health)",
        "unit": "tei-reranker",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 8082,
        "probe_type": "http",
        "target": "http://10.0.70.164:8082/health",
        "heal_type": "docker",
        "heal_cmd": "docker restart tei-reranker",
    },
    {
        "id": "164-docker-treesitter",
        "name": "treesitter-ast (:8095/health)",
        "unit": "ast_server.py",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 8095,
        "probe_type": "http",
        "target": "http://10.0.70.164:8095/health",
        "heal_type": "process",
        "heal_cmd": "pkill -f '/home/mboyle/infra/support-layer/ast_server.py' || true; nohup /usr/bin/python3 /home/mboyle/infra/support-layer/ast_server.py >> /home/mboyle/infra/support-layer/ast_server.log 2>&1 &",
    },
    {
        "id": "164-docker-registry",
        "name": "docker-mirror (:5000)",
        "unit": "docker-mirror",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 5000,
        "probe_type": "http",
        "target": "http://10.0.70.164:5000/v2/_catalog",
        "heal_type": "docker",
        "heal_cmd": "docker restart docker-mirror",
    },
    {
        "id": "164-docker-verdaccio",
        "name": "verdaccio (:4873)",
        "unit": "verdaccio",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 4873,
        "probe_type": "http",
        "target": "http://10.0.70.164:4873",
        "heal_type": "docker",
        "heal_cmd": "docker restart verdaccio",
    },
    {
        "id": "164-docker-devpi",
        "name": "devpi-server (:3141)",
        "unit": "devpi-server",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 3141,
        "probe_type": "http",
        "target": "http://10.0.70.164:3141",
        "heal_type": "docker",
        "heal_cmd": "docker restart devpi-server",
    },
    {
        "id": "164-docker-acng",
        "name": "apt-cacher-ng (:3142)",
        "unit": "apt-cacher-ng",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 3142,
        "probe_type": "http",
        "target": "http://10.0.70.164:3142/acng-report.html",
        "heal_type": "docker",
        "heal_cmd": "docker restart apt-cacher-ng",
    },
    {
        "id": "164-docker-elastic",
        "name": "elasticsearch (:9200)",
        "unit": "elasticsearch",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 9200,
        "probe_type": "http",
        "target": "http://10.0.70.164:9200",
        "heal_type": "docker",
        "heal_cmd": "docker restart elasticsearch",
    },
    {
        "id": "164-docker-redis",
        "name": "redis-cache (:6379)",
        "unit": "redis-cache",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 6379,
        "probe_type": "tcp",
        "target": "10.0.70.164:6379",
        "heal_type": "docker",
        "heal_cmd": "docker restart redis-cache",
    },
    {
        "id": "164-docker-kafka",
        "name": "kafka (:9092)",
        "unit": "kafka",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 9092,
        "probe_type": "tcp",
        "target": "10.0.70.164:9092",
        "heal_type": "docker",
        "heal_cmd": "docker restart kafka",
    },
    {
        "id": "164-docker-node-exporter",
        "name": "node-exporter (:9100)",
        "unit": "node-exporter",
        "node": "10.0.70.164",
        "node_label": "Controller .164",
        "category": "controller-docker",
        "port": 9100,
        "probe_type": "http",
        "target": "http://10.0.70.164:9100/metrics",
        "heal_type": "docker",
        "heal_cmd": "docker restart node-exporter",
    },
    {
        "id": "72-rpc-worker",
        "name": ".72 llama-rpc-worker.service (:50052)",
        "unit": "llama-rpc-worker.service",
        "node": "10.0.70.72",
        "node_label": "AI Vault A .72",
        "category": "remote-gpu-satellite",
        "port": 50052,
        "probe_type": "rpc_systemd",
        "target": "10.0.70.72 (10.0.75.12:50052)",
        "heal_type": "remote-systemd",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.72 'sudo systemctl restart llama-rpc-worker.service'",
    },
    {
        "id": "72-tier1-alpha",
        "name": ".72 llama-tier1-alpha.service (:8082/health)",
        "unit": "llama-tier1-alpha.service",
        "node": "10.0.70.72",
        "node_label": "AI Vault A .72",
        "category": "remote-gpu-satellite",
        "port": 8082,
        "probe_type": "http",
        "target": "http://10.0.70.72:8082/health",
        "heal_type": "remote-systemd",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.72 'sudo systemctl restart llama-tier1-alpha.service'",
    },
    {
        "id": "72-openwebui",
        "name": ".72 OpenWebUI (:8080)",
        "unit": "open-webui (.72)",
        "node": "10.0.70.72",
        "node_label": "AI Vault A .72",
        "category": "remote-gpu-satellite",
        "port": 8080,
        "probe_type": "http",
        "target": "http://10.0.70.72:8080",
        "heal_type": "remote-docker",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.72 'docker restart open-webui'",
    },
    {
        "id": "72-ollama-bridge",
        "name": ".72 Ollama Vault A Bridge (:8081)",
        "unit": "ollama (.72)",
        "node": "10.0.70.72",
        "node_label": "AI Vault A .72",
        "category": "remote-gpu-satellite",
        "port": 8081,
        "probe_type": "http",
        "target": "http://10.0.70.72:8081",
        "heal_type": "remote-systemd",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.72 'sudo systemctl restart ollama'",
    },
    {
        "id": "72-bulkdownloader",
        "name": ".72 BulkDownloader Web UI (:5555)",
        "unit": "bulkdownloader (.72)",
        "node": "10.0.70.72",
        "node_label": "AI Vault A .72",
        "category": "remote-gpu-satellite",
        "port": 5555,
        "probe_type": "http",
        "target": "http://10.0.70.72:5555",
        "heal_type": "remote-systemd",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.72 'sudo systemctl restart bulkdownloader || true'",
    },
    {
        "id": "72-novnc",
        "name": ".72 AI Vault A noVNC (:6080)",
        "unit": "bd-novnc (.72)",
        "node": "10.0.70.72",
        "node_label": "AI Vault A .72",
        "category": "remote-gpu-satellite",
        "port": 6080,
        "probe_type": "http",
        "target": "http://10.0.70.72:6080/vnc.html",
        "heal_type": "remote-systemd",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.72 'sudo systemctl restart bd-novnc.service || true'",
    },
    {
        "id": "83-rpc-worker",
        "name": ".83 llama-rpc-worker.service (:50052)",
        "unit": "llama-rpc-worker.service",
        "node": "10.0.70.83",
        "node_label": "AI Vault B .83",
        "category": "remote-gpu-satellite",
        "port": 50052,
        "probe_type": "rpc_systemd",
        "target": "10.0.70.83 (10.0.75.11:50052)",
        "heal_type": "remote-systemd",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.83 'sudo systemctl restart llama-rpc-worker.service'",
    },
    {
        "id": "83-ssh-vaultb",
        "name": ".83 AI Vault B SSH & NFS Host (:22)",
        "unit": "sshd.service (.83)",
        "node": "10.0.70.83",
        "node_label": "AI Vault B .83",
        "category": "remote-gpu-satellite",
        "port": 22,
        "probe_type": "tcp",
        "target": "10.0.70.83:22",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "125-rpc-worker",
        "name": ".125 llama-rpc-worker.service (:50052)",
        "unit": "llama-rpc-worker.service",
        "node": "10.0.70.125",
        "node_label": "ai-infer01 .125",
        "category": "remote-gpu-satellite",
        "port": 50052,
        "probe_type": "rpc_systemd",
        "target": "10.0.70.125 (10.0.75.14:50052)",
        "heal_type": "remote-systemd",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.125 'sudo systemctl restart llama-rpc-worker.service'",
    },
    {
        "id": "125-tier1-beta",
        "name": ".125 llama-tier1-beta.service (:8081/health)",
        "unit": "llama-tier1-beta.service",
        "node": "10.0.70.125",
        "node_label": "ai-infer01 .125",
        "category": "remote-gpu-satellite",
        "port": 8081,
        "probe_type": "http",
        "target": "http://10.0.70.125:8081/health",
        "heal_type": "remote-systemd",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.125 'sudo systemctl restart llama-tier1-beta.service'",
    },
    {
        "id": "125-qdrant",
        "name": ".125 Qdrant (:6333/healthz)",
        "unit": "qdrant (.125)",
        "node": "10.0.70.125",
        "node_label": "ai-infer01 .125",
        "category": "remote-gpu-satellite",
        "port": 6333,
        "probe_type": "http",
        "target": "http://10.0.70.125:6333/healthz",
        "heal_type": "remote-docker",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.125 'docker restart qdrant || sudo systemctl restart qdrant'",
    },
    {
        "id": "125-ollama-bridge",
        "name": ".125 Ollama Infer01 Bridge (:8005)",
        "unit": "ollama (.125)",
        "node": "10.0.70.125",
        "node_label": "ai-infer01 .125",
        "category": "remote-gpu-satellite",
        "port": 8005,
        "probe_type": "http",
        "target": "http://10.0.70.125:8005",
        "heal_type": "remote-systemd",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.125 'sudo systemctl restart ollama'",
    },
    {
        "id": "228-rpc-worker",
        "name": ".228 llama-rpc-worker.service (:50052)",
        "unit": "llama-rpc-worker.service",
        "node": "10.0.70.228",
        "node_label": "ai-ollama01 .228",
        "category": "remote-gpu-satellite",
        "port": 50052,
        "probe_type": "rpc_systemd",
        "target": "10.0.70.228 (10.0.75.13:50052)",
        "heal_type": "remote-systemd",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.228 'sudo systemctl restart llama-rpc-worker.service'",
    },
    {
        "id": "228-litellm",
        "name": ".228 litellm-proxy (:4000/health/liveliness)",
        "unit": "litellm-proxy (.228)",
        "node": "10.0.70.228",
        "node_label": "ai-ollama01 .228",
        "category": "remote-gpu-satellite",
        "port": 4000,
        "probe_type": "http",
        "target": "http://10.0.70.228:4000/health/liveliness",
        "heal_type": "remote-docker",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.228 'docker restart litellm-proxy'",
    },
    {
        "id": "228-langfuse",
        "name": ".228 Langfuse (:3000)",
        "unit": "langfuse (.228)",
        "node": "10.0.70.228",
        "node_label": "ai-ollama01 .228",
        "category": "remote-gpu-satellite",
        "port": 3000,
        "probe_type": "http",
        "target": "http://10.0.70.228:3000",
        "heal_type": "remote-docker",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.228 'docker restart langfuse-web-1 || docker start langfuse-web-1'",
    },
    {
        "id": "228-ollama",
        "name": ".228 Ollama (:11434)",
        "unit": "ollama.service (.228)",
        "node": "10.0.70.228",
        "node_label": "ai-ollama01 .228",
        "category": "remote-gpu-satellite",
        "port": 11434,
        "probe_type": "http",
        "target": "http://10.0.70.228:11434/api/tags",
        "heal_type": "remote-systemd",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.228 'sudo systemctl restart ollama'",
    },
    {
        "id": "228-openwebui",
        "name": ".228 OpenWebUI Satellite (:8090)",
        "unit": "open-webui (.228)",
        "node": "10.0.70.228",
        "node_label": "ai-ollama01 .228",
        "category": "remote-gpu-satellite",
        "port": 8090,
        "probe_type": "http",
        "target": "http://10.0.70.228:8090",
        "heal_type": "remote-docker",
        "heal_cmd": "ssh -o BatchMode=yes -o ConnectTimeout=5 10.0.70.228 'docker restart open-webui || true'",
    },
    {
        "id": "137-oracle-cdp",
        "name": "BattleStation Chrome CDP (10.0.10.137:9222/json/version)",
        "unit": "chrome-cdp-137",
        "node": "10.0.10.137",
        "node_label": "BattleStation .137",
        "category": "browser-oracles",
        "port": 9222,
        "probe_type": "http",
        "target": "http://10.0.10.137:9222/json/version",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "181-oracle-cdp",
        "name": "Bittorrent Chrome CDP (10.0.70.181:9222/json/version)",
        "unit": "chrome-cdp-181",
        "node": "10.0.70.181",
        "node_label": "Bittorrent .181",
        "category": "browser-oracles",
        "port": 9222,
        "probe_type": "http",
        "target": "http://10.0.70.181:9222/json/version",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "137-ollama-2080ti",
        "name": "BattleStation RTX 2080 Ti Ollama (:11434)",
        "unit": "ollama-137",
        "node": "10.0.10.137",
        "node_label": "BattleStation .137",
        "category": "browser-oracles",
        "port": 11434,
        "probe_type": "http",
        "target": "http://10.0.10.137:11434/api/tags",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "vhost-dashy",
        "name": "VHost: dashy.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/",
        "host_header": "dashy.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-jarvis",
        "name": "VHost: jarvis.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/",
        "host_header": "jarvis.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-chat",
        "name": "VHost: chat.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/",
        "host_header": "chat.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-lobechat",
        "name": "VHost: lobechat.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/",
        "host_header": "lobechat.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-opencode",
        "name": "VHost: opencode.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/",
        "host_header": "opencode.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-openclaw",
        "name": "VHost: openclaw.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/",
        "host_header": "openclaw.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-harnesses",
        "name": "VHost: harnesses.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/health",
        "host_header": "harnesses.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-sentinel",
        "name": "VHost: sentinel.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/health",
        "host_header": "sentinel.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-openwebui",
        "name": "VHost: openwebui.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/",
        "host_header": "openwebui.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-litellm",
        "name": "VHost: litellm.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/health/liveliness",
        "host_header": "litellm.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-litellm-228",
        "name": "VHost: litellm-228.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/health/liveliness",
        "host_header": "litellm-228.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-grafana",
        "name": "VHost: grafana.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/",
        "host_header": "grafana.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-gitea",
        "name": "VHost: gitea.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/",
        "host_header": "gitea.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-codeserver",
        "name": "VHost: codeserver.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/",
        "host_header": "codeserver.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vhost-searxng",
        "name": "VHost: searxng.boylenet.themfboyles.org (:80)",
        "unit": "traefik-ingress",
        "node": "10.0.70.164",
        "node_label": "Traefik DNS :80",
        "category": "traefik-vhosts",
        "port": 80,
        "probe_type": "http_vhost",
        "target": "http://10.0.70.164/",
        "host_header": "searxng.boylenet.themfboyles.org",
        "heal_type": "docker",
        "heal_cmd": "docker restart traefik-ingress",
    },
    {
        "id": "vmware-vc04",
        "name": "vSphere Client VC04 (10.0.20.70:443)",
        "unit": "vc04",
        "node": "10.0.20.70",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 443,
        "probe_type": "tcp",
        "target": "10.0.20.70:443",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "vmware-esxi01",
        "name": "ESXi01 Hypervisor (10.0.20.41:443)",
        "unit": "esxi01",
        "node": "10.0.20.41",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 443,
        "probe_type": "tcp",
        "target": "10.0.20.41:443",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "vmware-esxi02",
        "name": "ESXi02 Hypervisor (10.0.20.42:443)",
        "unit": "esxi02",
        "node": "10.0.20.42",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 443,
        "probe_type": "tcp",
        "target": "10.0.20.42:443",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "vmware-esxi03",
        "name": "ESXi03 Hypervisor (10.0.20.43:443)",
        "unit": "esxi03",
        "node": "10.0.20.43",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 443,
        "probe_type": "tcp",
        "target": "10.0.20.43:443",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "vmware-esxi04",
        "name": "ESXi04 Hypervisor (10.0.20.44:443)",
        "unit": "esxi04",
        "node": "10.0.20.44",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 443,
        "probe_type": "tcp",
        "target": "10.0.20.44:443",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "ilo-esxi01",
        "name": "ESXi01 HPE iLO4 (10.0.10.10:443)",
        "unit": "ilom-10",
        "node": "10.0.10.10",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 443,
        "probe_type": "tcp",
        "target": "10.0.10.10:443",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "ilo-esxi02",
        "name": "ESXi02 HPE iLO4 (10.0.10.20:443)",
        "unit": "ilom-20",
        "node": "10.0.10.20",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 443,
        "probe_type": "tcp",
        "target": "10.0.10.20:443",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "ilo-esxi04",
        "name": "ESXi04 HPE iLO4 (10.0.10.40:443)",
        "unit": "ilom-40",
        "node": "10.0.10.40",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 443,
        "probe_type": "tcp",
        "target": "10.0.10.40:443",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "ilo-252",
        "name": "HPE ProLiant iLO4 .252 (10.0.10.252:443)",
        "unit": "ilom-252",
        "node": "10.0.10.252",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 443,
        "probe_type": "tcp",
        "target": "10.0.10.252:443",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "unifi-gateway-https",
        "name": "UniFi OS Gateway Console (10.0.70.1:443)",
        "unit": "udm-pro-se",
        "node": "10.0.70.1",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 443,
        "probe_type": "tcp",
        "target": "10.0.70.1:443",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "unifi-dns-resolver",
        "name": "UniFi Authoritative DNS Resolver (10.0.70.1:53)",
        "unit": "dnsmasq-unifi",
        "node": "10.0.70.1",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 53,
        "probe_type": "tcp",
        "target": "10.0.70.1:53",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "fleet-bd1",
        "name": "Builder Fleet Node bd1 (10.0.70.51:22)",
        "unit": "wrk-bd02",
        "node": "10.0.70.51",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 22,
        "probe_type": "tcp",
        "target": "10.0.70.51:22",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
    {
        "id": "fleet-test3big",
        "name": "64-Core RAG Worker test3big (10.0.70.82:22)",
        "unit": "wrk-test04",
        "node": "10.0.70.82",
        "node_label": "VMware & Network Core",
        "category": "vmware-unifi-fleet",
        "port": 22,
        "probe_type": "tcp",
        "target": "10.0.70.82:22",
        "heal_type": "monitor-only",
        "heal_cmd": "",
    },
]


class SentinelMonitor:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.started_at = utc_now()
        self.check_cycles = 0
        self.last_check_utc = ""
        self.last_sweep_duration_ms = 0.0
        self.self_heal_events: List[Dict[str, Any]] = []
        self.runtime_state: Dict[str, Dict[str, Any]] = {}
        for svc in SERVICES:
            sid = svc["id"]
            self.runtime_state[sid] = {
                **svc,
                "healthy": True,
                "status_code": "INIT",
                "latency_ms": 0.0,
                "total_checks": 0,
                "successful_checks": 0,
                "uptime_pct": 100.0,
                "consecutive_failures": 0,
                "heal_count": 0,
                "last_healed_utc": None,
                "last_checked_utc": None,
                "detail": "Initializing...",
            }
        self._load_previous_events()

    def _load_previous_events(self) -> None:
        if os.path.exists(STATE_JSON_FILE):
            try:
                with open(STATE_JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data.get("self_heal_events"), list):
                    self.self_heal_events = data["self_heal_events"][-100:]
            except Exception:
                pass

    def _probe_single(self, svc: Dict[str, Any]) -> Tuple[str, bool, str, float, str]:
        sid = svc["id"]
        ptype = svc["probe_type"]
        t0 = time.monotonic()
        if ptype == "self":
            latency = round((time.monotonic() - t0) * 1000.0, 2)
            return (
                sid,
                True,
                "HTTP 200",
                max(latency, 0.4),
                "Autonomous Sentinel Active (:4099)",
            )
        if ptype in ("http", "http_vhost"):
            url = svc["target"]
            headers = {"User-Agent": "Boylenet-Infra-Sentinel/1.0"}
            if ptype == "http_vhost" and svc.get("host_header"):
                headers["Host"] = svc["host_header"]
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=3.5, context=SSL_CTX) as resp:
                    code = resp.getcode()
                    latency = round((time.monotonic() - t0) * 1000.0, 2)
                    ok = 200 <= code < 405
                    return (sid, ok, f"HTTP {code}", latency, f"OK ({url})")
            except urllib.error.HTTPError as e:
                latency = round((time.monotonic() - t0) * 1000.0, 2)
                if e.code in (401, 403, 301, 302, 307, 308):
                    return (
                        sid,
                        True,
                        f"HTTP {e.code}",
                        latency,
                        f"Auth/Redirect Ready ({url})",
                    )
                return (sid, False, f"HTTP {e.code}", latency, str(e))
            except Exception as e:
                latency = round((time.monotonic() - t0) * 1000.0, 2)
                return (sid, False, "HTTP ERR", latency, str(e)[:120])
        if ptype == "tcp":
            host = svc["node"]
            port = int(svc["port"])
            try:
                with socket.create_connection((host, port), timeout=2.5):
                    latency = round((time.monotonic() - t0) * 1000.0, 2)
                    return (
                        sid,
                        True,
                        f"TCP :{port} OK",
                        latency,
                        f"Connected {host}:{port}",
                    )
            except Exception as e:
                latency = round((time.monotonic() - t0) * 1000.0, 2)
                return (sid, False, f"TCP :{port} ERR", latency, str(e)[:120])
        if ptype == "rpc_systemd":
            host = svc["node"]
            port = int(svc["port"])
            cmd = [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=3",
                host,
                f"systemctl is-active llama-rpc.service && ss -H -tln 'sport = :{port}' | awk '{{print $4}}'",
            ]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=4.5)
                latency = round((time.monotonic() - t0) * 1000.0, 2)
                lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
                if (
                    r.returncode == 0
                    and lines
                    and (lines[0] == "active")
                    and (len(lines) >= 2)
                ):
                    return (
                        sid,
                        True,
                        f"RPC {lines[1]}",
                        latency,
                        f"llama-rpc.service active ({lines[1]})",
                    )
                return (
                    sid,
                    False,
                    "RPC DOWN",
                    latency,
                    (r.stderr or r.stdout or "inactive").strip()[:120],
                )
            except Exception as e:
                latency = round((time.monotonic() - t0) * 1000.0, 2)
                return (sid, False, "RPC ERR", latency, str(e)[:120])
        latency = round((time.monotonic() - t0) * 1000.0, 2)
        return (sid, False, "UNKNOWN", latency, "Unsupported probe_type")

    def execute_self_heal(
        self, svc_state: Dict[str, Any], reason: str
    ) -> Dict[str, Any]:
        heal_cmd = svc_state.get("heal_cmd", "")
        sid = svc_state["id"]
        name = svc_state["name"]
        node = svc_state["node"]
        stamp = utc_now()
        if not heal_cmd:
            event = {
                "timestamp": stamp,
                "service_id": sid,
                "service_name": name,
                "node": node,
                "reason": reason,
                "action": "monitor-only (no heal_cmd configured)",
                "rc": 0,
                "output": "Monitor-only endpoint",
            }
            write_log(f"ALERT [MONITOR-ONLY] {name} ({node}) reason={reason}")
            return event
        t0 = time.monotonic()
        try:
            allowed_cmds = {
                s.get("heal_cmd", "") for s in SERVICES if s.get("heal_cmd")
            }
            if heal_cmd not in allowed_cmds:
                raise ValueError(f"Unapproved heal_cmd blocked: {heal_cmd}")
            if "ast_server.py" in heal_cmd:
                subprocess.run(
                    ["/usr/bin/pkill", "-f", "/home/mboyle/infra/support-layer/ast_server.py"],
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                with open("/home/mboyle/infra/support-layer/ast_server.log", "a", encoding="utf-8") as logf:
                    subprocess.Popen(
                        ["/usr/bin/python3", "/home/mboyle/infra/support-layer/ast_server.py"],
                        stdout=logf,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                r = subprocess.CompletedProcess(args=["ast_server_restart"], returncode=0, stdout="ast_server restarted", stderr="")
            else:
                if heal_cmd.startswith("XDG_RUNTIME_DIR="):
                    cmd_argv = ["/usr/bin/env", *shlex.split(heal_cmd)]
                else:
                    cmd_argv = shlex.split(heal_cmd)
                r = subprocess.run(
                    cmd_argv, shell=False, capture_output=True, text=True, timeout=25
                )
            elapsed_ms = round((time.monotonic() - t0) * 1000.0, 1)
            rc = r.returncode
            out = ((r.stdout or "") + " " + (r.stderr or "")).strip()[:240]
        except Exception as e:
            elapsed_ms = round((time.monotonic() - t0) * 1000.0, 1)
            rc = 1
            out = str(e)[:240]
        event = {
            "timestamp": stamp,
            "service_id": sid,
            "service_name": name,
            "node": node,
            "reason": reason,
            "heal_type": svc_state.get("heal_type", "auto"),
            "command": heal_cmd,
            "rc": rc,
            "elapsed_ms": elapsed_ms,
            "output": out or "restarted cleanly",
        }
        write_log(
            f"SELF-HEAL service={name} ({sid}) node={node} reason='{reason}' cmd='{heal_cmd}' rc={rc} elapsed_ms={elapsed_ms}"
        )
        return event

    def run_sweep(self, force_heal_service_id: Optional[str] = None) -> Dict[str, Any]:
        t_start = time.monotonic()
        results: List[Tuple[str, bool, str, float, str]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
            futs = [pool.submit(self._probe_single, svc) for svc in SERVICES]
            for fut in concurrent.futures.as_completed(futs):
                results.append(fut.result())
        stamp = utc_now()
        heals_triggered: List[Dict[str, Any]] = []
        rpc_active_by_node = {sid.split("-")[0]: ok for sid, ok, _, _, _ in results if sid.endswith("-rpc-worker")}
        with self.lock:
            self.check_cycles += 1
            self.last_check_utc = stamp
            for sid, ok, status_code, latency_ms, detail in results:
                if not ok and sid in ("72-tier1-alpha", "72-ollama-bridge", "83-ollama", "125-tier1-beta", "125-ollama-bridge", "228-ollama"):
                    node_prefix = sid.split("-")[0]
                    if rpc_active_by_node.get(node_prefix):
                        ok = True
                        status_code = "RPC-ACTIVE"
                        detail = f"VRAM yielded to active GGML_RPC ({node_prefix}-rpc-worker)"
                st = self.runtime_state[sid]
                st["total_checks"] += 1
                if ok:
                    st["successful_checks"] += 1
                    st["consecutive_failures"] = 0
                else:
                    st["consecutive_failures"] += 1
                st["healthy"] = ok
                st["status_code"] = status_code
                st["latency_ms"] = latency_ms
                st["last_checked_utc"] = stamp
                st["detail"] = detail
                st["uptime_pct"] = round(
                    st["successful_checks"] / max(1, st["total_checks"]) * 100.0, 2
                )
                should_heal = (
                    not ok
                    and st["consecutive_failures"] >= CONSECUTIVE_FAIL_THRESHOLD
                    or force_heal_service_id == sid
                )
                if should_heal and st.get("heal_cmd"):
                    reason = (
                        f"Forced self-heal verification on {sid}"
                        if force_heal_service_id == sid
                        else f"Failed {st['consecutive_failures']} consecutive checks ({status_code})"
                    )
                    ev = self.execute_self_heal(st, reason)
                    st["heal_count"] += 1
                    st["last_healed_utc"] = ev["timestamp"]
                    st["consecutive_failures"] = 0
                    self.self_heal_events.append(ev)
                    self.self_heal_events = self.self_heal_events[-100:]
                    heals_triggered.append(ev)
            self.last_sweep_duration_ms = round(
                (time.monotonic() - t_start) * 1000.0, 1
            )
            snapshot = self._build_snapshot_unlocked()
        try:
            tmp_path = STATE_JSON_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
            os.replace(tmp_path, STATE_JSON_FILE)
        except OSError:
            pass
        write_log(
            f"SWEEP cycle={self.check_cycles} healthy={snapshot['healthy_services']}/{snapshot['total_services']} "
            f"avg_latency_ms={snapshot['avg_latency_ms']} sweep_ms={self.last_sweep_duration_ms} heals={len(heals_triggered)}"
        )
        return snapshot

    def _build_snapshot_unlocked(self) -> Dict[str, Any]:
        services_list = [self.runtime_state[s["id"]] for s in SERVICES]
        total = len(services_list)
        healthy = sum((1 for s in services_list if s["healthy"]))
        unhealthy = total - healthy
        avg_lat = round(
            sum((s["latency_ms"] for s in services_list)) / max(1, total), 2
        )
        overall_uptime = round(
            sum((s["uptime_pct"] for s in services_list)) / max(1, total), 2
        )
        by_category: Dict[str, Dict[str, int]] = {}
        for s in services_list:
            cat = s["category"]
            if cat not in by_category:
                by_category[cat] = {"total": 0, "healthy": 0, "unhealthy": 0}
            by_category[cat]["total"] += 1
            if s["healthy"]:
                by_category[cat]["healthy"] += 1
            else:
                by_category[cat]["unhealthy"] += 1
        return {
            "status": "ok" if unhealthy == 0 else "degraded",
            "service": "bd-infra-sentinel",
            "port": LISTEN_PORT,
            "started_at": self.started_at,
            "last_check_utc": self.last_check_utc,
            "check_interval_sec": CHECK_INTERVAL_SEC,
            "consecutive_fail_threshold": CONSECUTIVE_FAIL_THRESHOLD,
            "check_cycles": self.check_cycles,
            "last_sweep_duration_ms": self.last_sweep_duration_ms,
            "total_services": total,
            "healthy_services": healthy,
            "unhealthy_services": unhealthy,
            "uptime_pct": overall_uptime,
            "avg_latency_ms": avg_lat,
            "total_self_heals": len(self.self_heal_events),
            "categories": by_category,
            "services": services_list,
            "self_heal_events": list(reversed(self.self_heal_events[-30:])),
        }

    def get_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return self._build_snapshot_unlocked()


MONITOR = SentinelMonitor()
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Boylenet Infra Sentinel • 83-Service Autonomous Self-Healer (:4099)</title>
  <style>
    :root {
      --bg-0: #04070f;
      --bg-1: #091122;
      --glass: rgba(13, 23, 44, 0.78);
      --glass-border: rgba(56, 189, 248, 0.24);
      --cyan: #38bdf8;
      --emerald: #10b981;
      --amber: #f59e0b;
      --rose: #f43f5e;
      --text: #f1f5f9;
      --muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: radial-gradient(circle at 15% 10%, #0f1d3a 0%, var(--bg-0) 60%, #020409 100%);
      color: var(--text);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      min-height: 100vh;
      padding: 22px 28px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      padding: 18px 24px;
      background: var(--glass);
      border: 1px solid var(--glass-border);
      border-radius: 14px;
      backdrop-filter: blur(16px);
      box-shadow: 0 10px 35px rgba(0, 0, 0, 0.5);
      margin-bottom: 20px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .pulse-orb {
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: var(--emerald);
      box-shadow: 0 0 16px var(--emerald);
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0%, 100% { transform: scale(1); opacity: 1; }
      50% { transform: scale(1.18); opacity: 0.75; }
    }
    .brand h1 {
      font-size: 1.35rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      background: linear-gradient(90deg, #fff, var(--cyan));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .brand p {
      font-size: 0.82rem;
      color: var(--muted);
      margin-top: 2px;
    }
    .actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .btn {
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.22), rgba(16, 185, 129, 0.22));
      border: 1px solid var(--cyan);
      color: var(--text);
      padding: 9px 16px;
      border-radius: 9px;
      font-weight: 600;
      font-size: 0.84rem;
      cursor: pointer;
      transition: all 0.18s ease;
    }
    .btn:hover {
      background: rgba(56, 189, 248, 0.35);
      box-shadow: 0 0 18px rgba(56, 189, 248, 0.35);
      transform: translateY(-1px);
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(195px, 1fr));
      gap: 14px;
      margin-bottom: 20px;
    }
    .kpi-card {
      background: var(--glass);
      border: 1px solid var(--glass-border);
      border-radius: 12px;
      padding: 16px 18px;
      backdrop-filter: blur(12px);
    }
    .kpi-label {
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
    }
    .kpi-val {
      font-size: 1.65rem;
      font-weight: 800;
      margin-top: 6px;
      color: var(--cyan);
    }
    .kpi-sub {
      font-size: 0.76rem;
      color: var(--muted);
      margin-top: 4px;
    }
    .controls {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 16px;
    }
    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .tab {
      background: rgba(15, 23, 42, 0.75);
      border: 1px solid rgba(148, 163, 184, 0.2);
      color: var(--muted);
      padding: 7px 13px;
      border-radius: 8px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
    }
    .tab.active, .tab:hover {
      border-color: var(--cyan);
      color: var(--text);
      background: rgba(56, 189, 248, 0.16);
    }
    .search-box {
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid var(--glass-border);
      color: var(--text);
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.84rem;
      min-width: 260px;
    }
    .panel {
      background: var(--glass);
      border: 1px solid var(--glass-border);
      border-radius: 14px;
      overflow: hidden;
      margin-bottom: 22px;
      box-shadow: 0 8px 28px rgba(0, 0, 0, 0.45);
    }
    .panel-title {
      padding: 14px 20px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.14);
      font-weight: 700;
      font-size: 0.92rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.83rem;
    }
    th, td {
      padding: 10px 14px;
      text-align: left;
      border-bottom: 1px solid rgba(148, 163, 184, 0.08);
    }
    th {
      background: rgba(4, 7, 15, 0.6);
      color: var(--muted);
      font-weight: 600;
      text-transform: uppercase;
      font-size: 0.72rem;
      letter-spacing: 0.05em;
    }
    tr:hover {
      background: rgba(56, 189, 248, 0.06);
    }
    .badge {
      display: inline-block;
      padding: 3px 9px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 0.72rem;
    }
    .badge-ok {
      background: rgba(16, 185, 129, 0.18);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .badge-err {
      background: rgba(244, 63, 94, 0.2);
      color: #fb7185;
      border: 1px solid rgba(244, 63, 94, 0.45);
    }
    .badge-node {
      background: rgba(56, 189, 248, 0.13);
      color: var(--cyan);
      border: 1px solid rgba(56, 189, 248, 0.28);
      font-family: monospace;
    }
    .mono {
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 0.78rem;
    }
    .lat-bar-wrap {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .lat-bar {
      width: 60px;
      height: 6px;
      background: rgba(148, 163, 184, 0.18);
      border-radius: 3px;
      overflow: hidden;
    }
    .lat-fill {
      height: 100%;
      background: linear-gradient(90deg, var(--emerald), var(--cyan));
    }
    .log-box {
      padding: 14px 18px;
      font-family: monospace;
      font-size: 0.78rem;
      max-height: 240px;
      overflow-y: auto;
      background: rgba(2, 4, 9, 0.65);
      color: #cbd5e1;
    }
    .log-item {
      padding: 6px 0;
      border-bottom: 1px dashed rgba(148, 163, 184, 0.12);
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="brand">
      <div class="pulse-orb" id="statusOrb"></div>
      <div>
        <h1>Boylenet Autonomous Infrastructure Sentinel (:4099)</h1>
        <p>Zero-LLM-Token 83-Service Health Matrix &amp; 2-Strike Automatic Self-Healing Daemon • <span id="lastCheckText">Loading...</span></p>
      </div>
    </div>
    <div class="actions">
      <button class="btn" onclick="triggerHealNow()">⚡ Run Full Sweep &amp; Self-Heal Now</button>
    </div>
  </div>

  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Monitored Services</div>
      <div class="kpi-val" id="kpiHealthy">-- / 83</div>
      <div class="kpi-sub" id="kpiStatusText">Checking across 7 core subnets...</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Fleet Uptime</div>
      <div class="kpi-val" id="kpiUptime" style="color: var(--emerald);">100.0%</div>
      <div class="kpi-sub" id="kpiCycles">Cycle #0 (60s interval)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Mean Probe Latency</div>
      <div class="kpi-val" id="kpiLatency">-- ms</div>
      <div class="kpi-sub" id="kpiSweepMs">32-thread concurrent sweep</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Autonomous Self-Heals</div>
      <div class="kpi-val" id="kpiHeals" style="color: var(--amber);">0</div>
      <div class="kpi-sub">2 consecutive fails → auto-restart</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">LLM Token Burn</div>
      <div class="kpi-val" style="color: var(--emerald);">0 TOKENS</div>
      <div class="kpi-sub">Rule 81 deterministic Python daemon</div>
    </div>
  </div>

  <div class="controls">
    <div class="tabs" id="categoryTabs">
      <button class="tab active" onclick="setCategory('all', this)">All Services (83)</button>
      <button class="tab" onclick="setCategory('controller-systemd', this)">Controller .164 Systemd (10)</button>
      <button class="tab" onclick="setCategory('controller-docker', this)">Controller .164 Docker (25)</button>
      <button class="tab" onclick="setCategory('remote-gpu-satellite', this)">4-GPU &amp; Satellites .72/.83/.125/.228 (17)</button>
      <button class="tab" onclick="setCategory('browser-oracles', this)">Browser Oracles .137/.181 (3)</button>
      <button class="tab" onclick="setCategory('traefik-vhosts', this)">Traefik Port 80 DNS (15)</button>
      <button class="tab" onclick="setCategory('vmware-unifi-fleet', this)">VMware / UniFi / Fleet (13)</button>
    </div>
    <input type="text" class="search-box" id="searchInput" placeholder="Filter by service, port, node IP, or unit..." oninput="renderTable()" />
  </div>

  <div class="panel">
    <div class="panel-title">
      <span>Live 83-Service Telemetry &amp; Self-Healing Matrix</span>
      <span style="font-size: 0.78rem; color: var(--muted);">Auto-refreshes every 15s • Endpoint: <code>/api/status</code></span>
    </div>
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Service / Unit</th>
          <th>Node</th>
          <th>Endpoint / Target</th>
          <th>Status</th>
          <th>Latency</th>
          <th>Uptime %</th>
          <th>Fails / Heals</th>
          <th>Self-Heal Action</th>
        </tr>
      </thead>
      <tbody id="serviceRows"></tbody>
    </table>
  </div>

  <div class="panel">
    <div class="panel-title">
      <span>Autonomous Self-Heal Event Log (<code>/var/log/bd-infra-sentinel.log</code>)</span>
      <span style="font-size: 0.76rem; color: var(--muted);">Threshold: 2 consecutive failures</span>
    </div>
    <div class="log-box" id="healLogBox">No self-heal events triggered — all watched services nominal.</div>
  </div>

  <script>
    let currentData = null;
    let activeCategory = 'all';

    function setCategory(cat, btn) {
      activeCategory = cat;
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      btn.classList.add('active');
      renderTable();
    }

    async function loadStatus() {
      try {
        const res = await fetch('/api/status');
        currentData = await res.json();
        updateSummary(currentData);
        renderTable();
      } catch (e) {
        console.error('Failed to fetch status:', e);
      }
    }

    async function triggerHealNow() {
      try {
        const res = await fetch('/api/heal-now', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({})
        });
        currentData = await res.json();
        updateSummary(currentData);
        renderTable();
      } catch (e) {
        console.error('Heal sweep error:', e);
      }
    }

    function updateSummary(d) {
      document.getElementById('kpiHealthy').textContent = `${d.healthy_services} / ${d.total_services}`;
      document.getElementById('kpiStatusText').textContent = d.unhealthy_services === 0
        ? '100% GREEN across all nodes'
        : `${d.unhealthy_services} degraded service(s) under watch`;
      document.getElementById('kpiUptime').textContent = `${d.uptime_pct}%`;
      document.getElementById('kpiCycles').textContent = `Cycle #${d.check_cycles} (${d.check_interval_sec}s loop)`;
      document.getElementById('kpiLatency').textContent = `${d.avg_latency_ms} ms`;
      document.getElementById('kpiSweepMs').textContent = `Full 83-service sweep in ${d.last_sweep_duration_ms} ms`;
      document.getElementById('kpiHeals').textContent = d.total_self_heals;
      document.getElementById('lastCheckText').textContent = `Last Sweep: ${d.last_check_utc}`;

      const logBox = document.getElementById('healLogBox');
      if (d.self_heal_events && d.self_heal_events.length > 0) {
        logBox.innerHTML = d.self_heal_events.map(ev =>
          `<div class="log-item">[${ev.timestamp}] <strong>${ev.service_name}</strong> (${ev.node}) — ${ev.reason} → <code>${ev.command}</code> (rc=${ev.rc}, ${ev.elapsed_ms || 0}ms)</div>`
        ).join('');
      } else {
        logBox.innerHTML = `<div>[${d.last_check_utc}] SWEEP #${d.check_cycles}: ${d.healthy_services}/${d.total_services} services healthy (${d.avg_latency_ms} ms avg). Zero self-heal restarts required.</div>`;
      }
    }

    function renderTable() {
      if (!currentData || !currentData.services) return;
      const q = (document.getElementById('searchInput').value || '').toLowerCase();
      const rows = currentData.services.filter(s => {
        if (activeCategory !== 'all' && s.category !== activeCategory) return false;
        if (!q) return true;
        return (
          s.name.toLowerCase().includes(q) ||
          s.node.toLowerCase().includes(q) ||
          s.node_label.toLowerCase().includes(q) ||
          String(s.port).includes(q) ||
          (s.unit || '').toLowerCase().includes(q) ||
          (s.target || '').toLowerCase().includes(q)
        );
      });

      const tbody = document.getElementById('serviceRows');
      tbody.innerHTML = rows.map((s, idx) => {
        const pct = Math.min(100, Math.max(6, (s.latency_ms / 120) * 100));
        const badgeCls = s.healthy ? 'badge-ok' : 'badge-err';
        const healInfo = s.heal_cmd ? `<code class="mono">${s.heal_cmd}</code>` : `<span style="color:var(--muted)">monitor-only</span>`;
        return `<tr>
          <td class="mono">${idx + 1}</td>
          <td><strong>${s.name}</strong></td>
          <td><span class="badge badge-node">${s.node_label} (${s.node})</span></td>
          <td class="mono">${s.host_header ? s.host_header + ' → ' : ''}${s.target}</td>
          <td><span class="badge ${badgeCls}">${s.status_code}</span></td>
          <td>
            <div class="lat-bar-wrap">
              <div class="lat-bar"><div class="lat-fill" style="width:${pct}%"></div></div>
              <span class="mono">${s.latency_ms} ms</span>
            </div>
          </td>
          <td class="mono" style="color:#34d399">${s.uptime_pct}%</td>
          <td class="mono">${s.consecutive_failures} / ${s.heal_count}</td>
          <td>${healInfo}</td>
        </tr>`;
      }).join('');
    }

    loadStatus();
    setInterval(loadStatus, 15000);
  </script>
</body>
</html>
"""


class SentinelHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(
        self, code: int, payload: Dict[str, Any], head_only: bool = False
    ) -> None:
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if not head_only:
            self.wfile.write(raw)

    def _send_html(self, code: int, html: str, head_only: bool = False) -> None:
        raw = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if not head_only:
            self.wfile.write(raw)

    def do_HEAD(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/health":
            snap = MONITOR.get_snapshot()
            self._send_json(
                200,
                {
                    "status": snap["status"],
                    "service": "bd-infra-sentinel",
                    "port": LISTEN_PORT,
                    "total_services": snap["total_services"],
                    "healthy_services": snap["healthy_services"],
                    "unhealthy_services": snap["unhealthy_services"],
                    "uptime_pct": snap["uptime_pct"],
                    "avg_latency_ms": snap["avg_latency_ms"],
                    "last_check_utc": snap["last_check_utc"],
                },
                head_only=True,
            )
        elif path == "/api/status":
            self._send_json(200, MONITOR.get_snapshot(), head_only=True)
        else:
            self._send_html(200, DASHBOARD_HTML, head_only=True)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/health":
            snap = MONITOR.get_snapshot()
            self._send_json(
                200,
                {
                    "status": snap["status"],
                    "service": "bd-infra-sentinel",
                    "port": LISTEN_PORT,
                    "total_services": snap["total_services"],
                    "healthy_services": snap["healthy_services"],
                    "unhealthy_services": snap["unhealthy_services"],
                    "uptime_pct": snap["uptime_pct"],
                    "avg_latency_ms": snap["avg_latency_ms"],
                    "check_interval_sec": CHECK_INTERVAL_SEC,
                    "last_check_utc": snap["last_check_utc"],
                },
            )
        elif path == "/api/status":
            self._send_json(200, MONITOR.get_snapshot())
        else:
            self._send_html(200, DASHBOARD_HTML)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/heal-now":
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            try:
                payload = json.loads(body) if body.strip() else {}
            except Exception:
                payload = {}
            force_sid = payload.get("force_service_id")
            snap = MONITOR.run_sweep(force_heal_service_id=force_sid)
            self._send_json(200, snap)
        else:
            self._send_json(404, {"error": "Not found", "path": path})


def background_loop() -> None:
    time.sleep(0.3)
    try:
        MONITOR.run_sweep()
    except Exception as e:
        write_log(f"ERROR in initial sweep: {e}")
    while True:
        time.sleep(CHECK_INTERVAL_SEC)
        try:
            MONITOR.run_sweep()
        except Exception as e:
            write_log(f"ERROR in background sweep: {e}")


def main() -> None:
    write_log(
        f"STARTING bd-infra-sentinel on {LISTEN_HOST}:{LISTEN_PORT} (services={len(SERVICES)}, interval={CHECK_INTERVAL_SEC}s)"
    )
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), SentinelHTTPHandler)
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    server.serve_forever()


if __name__ == "__main__":
    main()
