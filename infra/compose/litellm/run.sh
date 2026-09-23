#!/usr/bin/env bash
# Recreate the LiteLLM proxy container WITH its config (the 2026-09-19 04:00 instance was started bare -> "Model list not initialized").
set -eu
D=/home/mboyle/infra/support-layer/litellm
sudo docker rm -f litellm-proxy >/dev/null 2>&1 || true
sudo docker run -d --name litellm-proxy --restart unless-stopped -p 4000:4000 \
  -e LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-sk-fleet-local}" \
  -e LANGFUSE_PUBLIC_KEY="pk-lf-1234" \
  -e LANGFUSE_SECRET_KEY="sk-lf-5678" \
  -e LANGFUSE_HOST="http://10.0.70.162:3002" \
  -v "$D/config.yaml:/app/config.yaml:ro" \
  ghcr.io/berriai/litellm:main-latest --config /app/config.yaml --port 4000 >/dev/null
echo "litellm-proxy recreated $(date -u +%FT%TZ)"
