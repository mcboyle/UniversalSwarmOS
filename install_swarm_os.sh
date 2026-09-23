#!/bin/bash
set -e

# ==============================================================================
# UNIVERSAL SWARM OS - BARE METAL PROVISIONING SCRIPT
# ==============================================================================
# This script configures a bare Ubuntu VM with the Swarm V3 Architecture.
# It defaults to a monolithic "Swarm-in-a-Box" but can be distributed via flags.

REPO_URL="https://github.com/your-org/UniversalSwarmOS.git" # Update with actual remote
SWARM_ROOT="/opt/swarm_os"

# Default configuration
ROLE="monolith"
ENABLE_VMWARE=false

# 1. Parse Arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --role=*) ROLE="${1#*=}" ;;
        --enable-vmware) ENABLE_VMWARE=true ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

echo "[*] Provisioning Swarm OS with role: $ROLE"

# 2. Gather Configuration & Secrets
ENV_FILE="$SWARM_ROOT/swarm.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "[!] $ENV_FILE not found. Dropping to interactive prompt..."
    read -p "Enter Anthropic API Key (Claude Pro): " ANTHROPIC_API_KEY
    read -p "Enter OpenAI API Key (Codex): " OPENAI_API_KEY
    read -p "Enter Target Git Repo URL (Project to work on): " TARGET_REPO_URL
    
    mkdir -p $SWARM_ROOT
    cat <<EOF > $ENV_FILE
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
OPENAI_API_KEY=$OPENAI_API_KEY
TARGET_REPO_URL=$TARGET_REPO_URL
EOF
else
    echo "[*] Reading secrets from $ENV_FILE..."
    source $ENV_FILE
fi

# 3. System Dependencies (Git & Docker)
echo "[*] Installing native dependencies..."
sudo apt-get update && sudo apt-get install -y git curl tmux jq build-essential sqlite3

if ! command -v docker &> /dev/null; then
    echo "[*] Installing Docker Engine..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
fi

# 4. Pull Swarm Framework
if [ ! -d "$SWARM_ROOT/core" ]; then
    echo "[*] Cloning UniversalSwarmOS..."
    git clone $REPO_URL $SWARM_ROOT/core
fi

# 5. Provisioning by Role
mkdir -p $SWARM_ROOT/docker

if [[ "$ROLE" == "monolith" || "$ROLE" == "database" || "$ROLE" == "proxy" ]]; then
    echo "[*] Writing Docker Compose Stack for heavy services..."
    cat <<EOF > $SWARM_ROOT/docker/docker-compose.yml
version: '3.8'
services:
  # Vector DB for Infinite Context Memory
  pgvector:
    image: ankane/pgvector:latest
    environment:
      POSTGRES_DB: ai_mesh
      POSTGRES_PASSWORD: swarmpassword
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
  
  # LiteLLM Proxy for Pre-emptive Prefix Caching
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    environment:
      - ANTHROPIC_API_KEY=\${ANTHROPIC_API_KEY}
    ports:
      - "4000:4000"
    command: [ "--config", "/app/config.yaml" ]

  # Local Satellite Inference (Ollama)
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama:/root/.ollama
volumes:
  pgdata:
  ollama:
EOF
    echo "[*] Spinning up Docker Compose stack..."
    cd $SWARM_ROOT/docker && docker compose up -d
fi

if [[ "$ROLE" == "monolith" || "$ROLE" == "controller" || "$ROLE" == "worker" ]]; then
    echo "[*] Provisioning Worker / Controller Environment..."
    mkdir -p $SWARM_ROOT/persist/harness
    mkdir -p $SWARM_ROOT/persist/accounting
    
    # Initialize SQLite WAL Bus
    sqlite3 $SWARM_ROOT/persist/fleet-bus.db "PRAGMA journal_mode=WAL;"
    
    if [ "$ENABLE_VMWARE" = true ]; then
        echo "[*] VMware integration enabled. Installing govc CLI..."
        curl -L -o - "https://github.com/vmware/govmomi/releases/latest/download/govc_Linux_x86_64.tar.gz" | tar -C /usr/local/bin -xvzf - govc
    else
        echo "[*] VMware integration disabled. Setting up Docker-in-Docker for CI sandboxing..."
        docker pull docker:dind
    fi
fi

# 6. Finalization
echo "[========================================================]"
echo "[✔] UNIVERSAL SWARM OS PROVISIONING COMPLETE"
echo "[*] Role: $ROLE"
echo "[*] Persistence Directory: $SWARM_ROOT/persist"
echo "[*] Proxy Endpoint: http://localhost:4000"
echo "[========================================================]"
echo "To launch the Swarm Controller, run: $SWARM_ROOT/core/Tools/swarm-pm-pass.sh"
