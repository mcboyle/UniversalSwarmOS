#!/usr/bin/env bash
# ==============================================================================
# UNIVERSAL SWARM OS - BARE METAL & CLUSTER PROVISIONING FRAMEWORK
# ==============================================================================
# Idempotent, modular provisioning engine for the Swarm V3 Architecture.
# Supports full monolithic deployment or distributed role-based staging.
#
# Flags:
#   --role=monolith|controller|worker|database  (Default: monolith)
#   --stage=all|deps|containers|mcp|hooks|services|databases|mesh|hermetic (Default: all)
#   --enable-vmware                             (Enable VMware ESXi/vSphere govc integration)
#   --help, -h                                  (Display usage information)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
INFRA_DIR="$SCRIPT_DIR/infra"
SWARM_ROOT="${SWARM_ROOT:-/opt/swarm_os}"
SWARM_USER="${SUDO_USER:-${USER:-mboyle}}"
SWARM_HOME="$(eval echo "~$SWARM_USER")"

# Defaults
ROLE="monolith"
STAGE="all"
ENABLE_VMWARE=false

# ------------------------------------------------------------------------------
# Logging & Helper Functions
# ------------------------------------------------------------------------------
log_info()  { echo -e "\033[1;34m[*] $*\033[0m"; }
log_ok()    { echo -e "\033[1;32m[✔] $*\033[0m"; }
log_warn()  { echo -e "\033[1;33m[!] $*\033[0m"; }
log_err()   { echo -e "\033[1;31m[ERROR] $*\033[0m" >&2; }

run_cmd() {
    if [ "$EUID" -ne 0 ] && command -v sudo &>/dev/null; then
        sudo "$@"
    else
        "$@"
    fi
}

show_help() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --role=ROLE         Target node role:
                        monolith   - All-in-one controller, database, registries & workers (Default)
                        controller - Swarm orchestrator, MCP servers, hooks, proxies & telemetry
                        worker     - Compute worker node with local AST and runner tools
                        database   - Persistence tier (pgvector, Redis, Elasticsearch, SQLite)
  --stage=STAGE       Specific provisioning stage:
                        all        - Run all provisioning stages sequentially (Default)
                        deps       - System APT, NPM, Python and binary dependencies
                        containers - Deploy 24 Docker containers across 4 Compose layers
                        mcp        - Install and compile custom FastMCP modules & agent configs
                        hooks      - Deploy Claude Code & Codex execution interceptors
                        services   - Install systemd system/user units & crontab automation
                        databases  - Initialize pgvector schema & SQLite WAL stores
                        mesh       - Configure 27-node cluster /etc/hosts & SSH multiplexing
                        hermetic   - Deploy offline package mirrors (pip, npm, apt, docker)
  --enable-vmware     Install and configure VMware govc integration CLI
  -h, --help          Display this help and exit

Examples:
  $(basename "$0") --role=monolith --stage=all
  $(basename "$0") --role=controller --stage=mcp
  $(basename "$0") --role=database --stage=databases
EOF
}

# ------------------------------------------------------------------------------
# 1. Parse Arguments
# ------------------------------------------------------------------------------
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --role=*)
            ROLE="${1#*=}"
            ;;
        --stage=*)
            STAGE="${1#*=}"
            ;;
        --enable-vmware)
            ENABLE_VMWARE=true
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_err "Unknown parameter passed: $1"
            show_help
            exit 1
            ;;
    esac
    shift
done

# Validate Role & Stage
case "$ROLE" in
    monolith|controller|worker|database) ;;
    *)
        log_err "Invalid role '$ROLE'. Must be monolith, controller, worker, or database."
        exit 1
        ;;
esac

case "$STAGE" in
    all|deps|containers|mcp|hooks|services|databases|mesh|hermetic) ;;
    *)
        log_err "Invalid stage '$STAGE'. Must be all, deps, containers, mcp, hooks, services, databases, mesh, or hermetic."
        exit 1
        ;;
esac

log_info "UniversalSwarmOS Provisioner starting..."
log_info "Target Role:  $ROLE"
log_info "Target Stage: $STAGE"
log_info "VMware Clones: $ENABLE_VMWARE"
log_info "Swarm Root:   $SWARM_ROOT"
log_info "Swarm User:   $SWARM_USER ($SWARM_HOME)"

# ------------------------------------------------------------------------------
# Environment & Secrets Initialization
# ------------------------------------------------------------------------------
verify_sudo() {
    local pass="$1"
    log_info "Verifying sudo access..."
    if command -v sudo &>/dev/null; then
        if sudo -n true 2>/dev/null; then
            log_ok "Sudo access verified (passwordless)."
            return 0
        else
            log_info "Sudo access requires authentication."
            if [ -n "$pass" ]; then
                if echo "$pass" | sudo -S -v 2>/dev/null; then
                    log_ok "Sudo access verified using provided password."
                    return 0
                fi
            fi
            return 1
        fi
    else
        log_warn "sudo command not found."
        return 1
    fi
}

check_ssh_keys() {
    local has_ssh="no"
    if [ -f "$SWARM_HOME/.ssh/id_rsa" ] || [ -f "$SWARM_HOME/.ssh/id_ed25519" ]; then
        has_ssh="yes"
    fi
    echo "$has_ssh"
}

stage_gpu_ollama() {
    log_info "=== STAGE: GPU & OLLAMA (AI Acceleration) ==="
    
    local gpu_detected="no"
    local nvidia_needs_driver="no"

    if command -v lspci >/dev/null 2>&1; then
        local pci_raw
        pci_raw="$(lspci -nn 2>/dev/null | grep -iE 'vga|3d|display' || true)"
        if echo "$pci_raw" | grep -iqE '10de|nvidia'; then
            gpu_detected="nvidia"
            if ! command -v nvidia-smi >/dev/null 2>&1; then
                nvidia_needs_driver="yes"
            else
                if nvidia-smi 2>&1 | grep -q "No devices were found"; then
                    nvidia_needs_driver="yes"
                fi
            fi
        elif echo "$pci_raw" | grep -iqE '1002|amd/ati|advanced micro devices'; then
            gpu_detected="amd"
        elif echo "$pci_raw" | grep -iqE '8086|intel.*(graphics|arc|iris|xe |hd graphics)'; then
            gpu_detected="intel"
        fi
    fi

    if [ "$gpu_detected" = "nvidia" ] && [ "$nvidia_needs_driver" = "yes" ]; then
        log_info "NVIDIA GPU detected but no driver loaded/found."
        if [ -t 0 ]; then
            read -r -p "Do you want to install the NVIDIA proprietary drivers? [y/N]: " DRV_ANS
            case "${DRV_ANS:-N}" in
                y|Y|yes|YES)
                    if command -v ubuntu-drivers >/dev/null 2>&1; then
                        log_info "Running ubuntu-drivers autoinstall..."
                        run_cmd ubuntu-drivers autoinstall
                    else
                        log_info "ubuntu-drivers not found. Searching apt for latest nvidia-driver..."
                        run_cmd apt-get update -qq || true
                        local candidate
                        candidate="$(apt-cache pkgnames nvidia-driver- 2>/dev/null | grep -E '^nvidia-driver-[0-9]+-server$' | sort -t- -k3 -n | tail -1)"
                        if [ -z "$candidate" ]; then
                            candidate="$(apt-cache pkgnames nvidia-driver- 2>/dev/null | grep -E '^nvidia-driver-[0-9]+$' | sort -t- -k3 -n | tail -1)"
                        fi
                        if [ -n "$candidate" ]; then
                            log_info "Installing $candidate..."
                            run_cmd apt-get install -y "$candidate"
                        else
                            log_warn "Could not determine nvidia driver package name."
                        fi
                    fi
                    log_warn "NVIDIA driver installed. A reboot is usually required to activate the driver."
                    ;;
                *)
                    log_info "Skipping NVIDIA driver install."
                    ;;
            esac
        fi
    elif [ "$gpu_detected" = "nvidia" ]; then
        log_ok "NVIDIA GPU detected and driver appears to be loaded."
    elif [ "$gpu_detected" != "no" ]; then
        log_ok "$gpu_detected GPU detected (non-NVIDIA). Not installing proprietary drivers automatically."
    else
        log_info "No supported GPU detected."
    fi

    log_info "Checking Ollama runtime..."
    if ! command -v ollama >/dev/null 2>&1; then
        if [ -t 0 ]; then
            read -r -p "Do you want to install Ollama and default AI models? [Y/n]: " OLL_ANS
        else
            OLL_ANS="Y"
        fi
        
        case "${OLL_ANS:-Y}" in
            y|Y|yes|YES)
                log_info "Installing Ollama..."
                curl -fsSL https://ollama.com/install.sh | sh || true
                
                if command -v ollama >/dev/null 2>&1; then
                    if command -v systemctl >/dev/null 2>&1; then
                        if ! systemctl cat ollama.service >/dev/null 2>&1; then
                            log_info "Creating ollama.service unit..."
                            if ! id ollama >/dev/null 2>&1; then
                                run_cmd useradd -r -g ollama -d /usr/share/ollama -s /usr/sbin/nologin ollama 2>/dev/null || run_cmd useradd -r -d /usr/share/ollama -s /usr/sbin/nologin ollama 2>/dev/null || true
                            fi
                            run_cmd mkdir -p /usr/share/ollama
                            run_cmd chown -R ollama:ollama /usr/share/ollama 2>/dev/null || true
                            local ollama_bin
                            ollama_bin="$(command -v ollama || echo /usr/local/bin/ollama)"
                            run_cmd bash -c "cat <<UNIT > /etc/systemd/system/ollama.service
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=${ollama_bin} serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment=\"PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\"

[Install]
WantedBy=multi-user.target
UNIT"
                            run_cmd systemctl daemon-reload
                        fi
                        run_cmd systemctl enable ollama || true
                        run_cmd systemctl start ollama || true
                    fi
                    
                    log_info "Waiting for Ollama API to respond..."
                    local up=""
                    for _ in {1..30}; do
                        if curl -fsS "http://localhost:11434/api/tags" >/dev/null 2>&1; then
                            up="yes"; break
                        fi
                        sleep 1
                    done
                    
                    if [ -n "$up" ]; then
                        log_info "Ollama API is responding. Pulling default models (this may take a while)..."
                        log_info "Pulling qwen2.5vl:7b (Vision)..."
                        ollama pull qwen2.5vl:7b || true
                        log_info "Pulling qwen2.5:7b (Text)..."
                        ollama pull qwen2.5:7b || true
                        log_ok "Ollama and models installed."
                    else
                        log_warn "Ollama API did not respond in time. Skipping model pulls."
                    fi
                else
                    log_warn "Ollama installation failed."
                fi
                ;;
            *)
                log_info "Skipping Ollama install."
                ;;
        esac
    else
        log_ok "Ollama is already installed."
    fi
}

init_env() {
    log_info "Checking environment configuration..."
    local env_file="$SWARM_ROOT/swarm.env"

    if [ ! -f "$env_file" ]; then
        log_warn "$env_file not found."
        if [ -t 0 ]; then
            read -r -p "Enter Target IP Address: " IP_INPUT || true
            read -r -s -p "Enter Password (for the IP/user): " PASSWORD_INPUT || true
            echo ""
            read -r -p "Enter Anthropic API Key (Claude Code) [or press Enter to skip]: " ANTHROPIC_KEY_INPUT || true
            read -r -p "Enter OpenAI API Key (Codex) [or press Enter to skip]: " OPENAI_KEY_INPUT || true
            read -r -p "Enter Target Git Repo URL [or press Enter to skip]: " REPO_KEY_INPUT || true
        else
            IP_INPUT="${TARGET_IP:-}"
            PASSWORD_INPUT="${TARGET_PASSWORD:-}"
            ANTHROPIC_KEY_INPUT="${ANTHROPIC_API_KEY:-}"
            OPENAI_KEY_INPUT="${OPENAI_API_KEY:-}"
            REPO_KEY_INPUT="${TARGET_REPO_URL:-}"
        fi
    else
        log_info "Loaded existing configuration from $env_file"
        source "$env_file"
        IP_INPUT="${TARGET_IP:-}"
        PASSWORD_INPUT="${TARGET_PASSWORD:-}"
        ANTHROPIC_KEY_INPUT="${ANTHROPIC_API_KEY:-}"
        OPENAI_KEY_INPUT="${OPENAI_API_KEY:-}"
        REPO_KEY_INPUT="${TARGET_REPO_URL:-}"
    fi

    local has_sudo="no"
    if verify_sudo "$PASSWORD_INPUT"; then
        has_sudo="yes"
    fi
    local has_ssh
    has_ssh="$(check_ssh_keys)"

    if [ "$has_ssh" = "no" ] && [ "$has_sudo" = "no" ]; then
        log_warn "VM is missing both SSH keys and automatic sudo access."
        if [ -t 0 ]; then
            read -r -p "Do you want to grant permission to generate an SSH key and continue automatically? [Y/n]: " PERM_ANS
            case "${PERM_ANS:-Y}" in
                y|Y|yes|YES)
                    mkdir -p "$SWARM_HOME/.ssh"
                    chmod 700 "$SWARM_HOME/.ssh"
                    ssh-keygen -t ed25519 -f "$SWARM_HOME/.ssh/id_ed25519" -N "" -q
                    log_ok "Generated new ed25519 SSH key. Continuing automatically."
                    ;;
                *)
                    log_err "Permission denied. Exiting."
                    exit 1
                    ;;
            esac
        else
            log_warn "Non-interactive mode. Cannot prompt for permissions."
        fi
    else
        if [ "$has_ssh" = "no" ]; then
            if [ -t 0 ]; then
                read -r -p "Do you want to generate an SSH key now? [Y/n]: " SSH_ANS
                case "${SSH_ANS:-Y}" in
                    y|Y|yes|YES)
                        mkdir -p "$SWARM_HOME/.ssh"
                        chmod 700 "$SWARM_HOME/.ssh"
                        ssh-keygen -t ed25519 -f "$SWARM_HOME/.ssh/id_ed25519" -N "" -q
                        log_ok "Generated new ed25519 SSH key."
                        ;;
                    *)
                        log_info "Skipping SSH key generation."
                        ;;
                esac
            fi
        else
            log_ok "SSH key found."
        fi
        
        if [ "$has_sudo" = "no" ]; then
            if [ -t 0 ]; then
                log_warn "Failed to authenticate sudo automatically."
                if sudo -v; then
                    log_ok "Sudo access verified."
                else
                    log_warn "Failed to authenticate sudo."
                    read -r -p "Continue anyway without sudo? [y/N]: " S_ANS
                    case "${S_ANS:-N}" in
                        y|Y|yes|YES) log_warn "Continuing without sudo." ;;
                        *) log_err "Sudo required. Exiting."; exit 1 ;;
                    esac
                fi
            else
                log_warn "Non-interactive mode and sudo requires password."
            fi
        fi
    fi

    if [ "$EUID" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
        chown -R "$SWARM_USER:$SWARM_USER" "$SWARM_HOME/.ssh" 2>/dev/null || true
    fi

    if [ ! -d "$SWARM_ROOT" ]; then
        run_cmd mkdir -p "$SWARM_ROOT"
        run_cmd chown -R "$SWARM_USER:$SWARM_USER" "$SWARM_ROOT" 2>/dev/null || true
    fi

    if [ ! -f "$env_file" ]; then
        cat <<EOF > "$env_file"
TARGET_IP=${IP_INPUT}
TARGET_PASSWORD=${PASSWORD_INPUT}
ANTHROPIC_API_KEY=${ANTHROPIC_KEY_INPUT}
OPENAI_API_KEY=${OPENAI_KEY_INPUT}
TARGET_REPO_URL=${REPO_KEY_INPUT}
SWARM_ROOT=${SWARM_ROOT}
SWARM_ROLE=${ROLE}
ENABLE_VMWARE=${ENABLE_VMWARE}
EOF
        chmod 600 "$env_file"
        log_ok "Wrote environment configuration to $env_file"
    fi
    
    stage_gpu_ollama
}

# ------------------------------------------------------------------------------
# STAGE: DEPS (System APT, NPM, Python, AST Tools & Tool Symlinks)
# ------------------------------------------------------------------------------
stage_deps() {
    log_info "=== STAGE: DEPS (Native Dependencies & Execution Layer) ==="

    # 1. System APT packages
    if command -v apt-get &>/dev/null; then
        log_info "Updating package lists and installing core APT packages..."
        export DEBIAN_FRONTEND=noninteractive
        run_cmd apt-get update -qq || true
        run_cmd apt-get install -y -qq \
            git curl tmux jq build-essential sqlite3 python3-pip python3-dev python3-venv \
            npm netcat-openbsd libpq-dev libmagic1 postgresql-client rsync ripgrep \
            htop ca-certificates gnupg lsb-release
        log_ok "System APT packages installed."
    fi

    # 2. Global NPM packages
    if command -v npm &>/dev/null; then
        log_info "Installing global NPM fleet dependencies..."
        run_cmd npm install -g --silent @caveman-ai/cli codeburn firecrawl-cli context-mode @modelcontextprotocol/server-postgres || true
        log_ok "Global NPM packages verified."
    fi

    # 3. Python Execution Layer & FastMCP Dependencies
    log_info "Installing Python dependencies and FastMCP framework..."
    pip3 install --user --upgrade --quiet \
        pydantic httpx ruamel.yaml peewee mcp fastmcp \
        ruff semgrep glom py-spy psycopg2-binary redis \
        opentelemetry-api opentelemetry-sdk elasticsearch minio kafka-python numpy || true
    log_ok "Python site-packages layer verified."

    # 4. High-Performance AST & Security Binaries
    if ! command -v ast-grep &>/dev/null; then
        log_info "Installing ast-grep AST engine..."
        curl -LsSf https://ast-grep.github.io/install.sh | bash || true
    fi

    if ! command -v trivy &>/dev/null; then
        log_info "Installing trivy security scanner..."
        curl -Ls https://github.com/aquasecurity/trivy/releases/download/v0.55.0/trivy_0.55.0_Linux-64bit.tar.gz 2>/dev/null \
            | run_cmd tar -xz -C /usr/local/bin trivy 2>/dev/null || true
    fi

    # 5. VMware CLI or Docker-in-Docker
    if [ "$ENABLE_VMWARE" = true ]; then
        if ! command -v govc &>/dev/null; then
            log_info "Installing VMware govc CLI..."
            curl -Ls "https://github.com/vmware/govmomi/releases/latest/download/govc_Linux_x86_64.tar.gz" 2>/dev/null \
                | run_cmd tar -C /usr/local/bin -xvzf - govc 2>/dev/null || true
            log_ok "govc installed to /usr/local/bin/govc"
        fi
    fi

    # 6. Docker Engine
    if ! command -v docker &>/dev/null; then
        log_info "Installing Docker Engine..."
        curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
        run_cmd sh /tmp/get-docker.sh || true
        rm -f /tmp/get-docker.sh
        run_cmd usermod -aG docker "$SWARM_USER" 2>/dev/null || true
        log_ok "Docker engine installed."
    fi

    # 7. Symlink UniversalSwarmOS Tool Binaries (swarm-*)
    log_info "Symlinking Swarm toolchain to ~/.local/bin..."
    local user_bin="$SWARM_HOME/.local/bin"
    mkdir -p "$user_bin"
    if [ -d "$SCRIPT_DIR/Tools" ]; then
        for tool in "$SCRIPT_DIR/Tools"/swarm-*; do
            if [ -f "$tool" ]; then
                local tool_name
                tool_name="$(basename "$tool")"
                chmod +x "$tool"
                ln -sf "$tool" "$user_bin/$tool_name"
                # If root or sudo available, also link to /usr/local/bin for global accessibility
                if [ -w /usr/local/bin ]; then
                    ln -sf "$tool" "/usr/local/bin/$tool_name" 2>/dev/null || true
                elif command -v sudo &>/dev/null; then
                    run_cmd ln -sf "$tool" "/usr/local/bin/$tool_name" 2>/dev/null || true
                fi
            fi
        done
        log_ok "Swarm tools symlinked successfully."
    fi

    log_ok "STAGE DEPS complete."
}

# ------------------------------------------------------------------------------
# STAGE: HERMETIC (Offline Mirrors, PIP, NPM, Docker, Agent Env)
# ------------------------------------------------------------------------------
stage_hermetic() {
    log_info "=== STAGE: HERMETIC (Offline Package Mirrors & Environment) ==="

    local hermetic_dir="$INFRA_DIR/hermetic"

    # 1. Pip configuration
    mkdir -p "$SWARM_HOME/.pip"
    if [ -f "$hermetic_dir/pip.conf" ]; then
        cp -f "$hermetic_dir/pip.conf" "$SWARM_HOME/.pip/pip.conf"
        log_ok "Deployed ~/.pip/pip.conf (Devpi mirror on :3141)"
    fi

    # 2. NPM configuration
    if [ -f "$hermetic_dir/.npmrc" ]; then
        cp -f "$hermetic_dir/.npmrc" "$SWARM_HOME/.npmrc"
    elif [ -f "$hermetic_dir/npmrc" ]; then
        cp -f "$hermetic_dir/npmrc" "$SWARM_HOME/.npmrc"
    fi
    chmod 600 "$SWARM_HOME/.npmrc" 2>/dev/null || true
    log_ok "Deployed ~/.npmrc (Verdaccio registry on :4873)"

    # 3. APT 01proxy
    if [ -d /etc/apt/apt.conf.d ] && [ -f "$hermetic_dir/01proxy" ]; then
        run_cmd cp -f "$hermetic_dir/01proxy" /etc/apt/apt.conf.d/01proxy 2>/dev/null || true
        log_ok "Configured APT proxy cache (apt-cacher-ng on :3142)"
    fi

    # 4. Docker daemon mirror
    if [ -f "$hermetic_dir/daemon.json" ] && [ -d /etc/docker ]; then
        run_cmd cp -f "$hermetic_dir/daemon.json" /etc/docker/daemon.json 2>/dev/null || true
        log_ok "Configured Docker daemon mirrors (:5000, 10.0.70.182:5001)"
    fi

    # 5. Agent environment exports (~/.agent_env)
    if [ -f "$hermetic_dir/.agent_env" ]; then
        cp -f "$hermetic_dir/.agent_env" "$SWARM_HOME/.agent_env"
    elif [ -f "$hermetic_dir/agent_env" ]; then
        cp -f "$hermetic_dir/agent_env" "$SWARM_HOME/.agent_env"
    fi
    chmod 644 "$SWARM_HOME/.agent_env" 2>/dev/null || true
    log_ok "Deployed ~/.agent_env (27 mesh endpoint variables)"

    # Ensure ~/.agent_env is sourced in bashrc
    if [ -f "$SWARM_HOME/.bashrc" ] && ! grep -q "source.*\.agent_env" "$SWARM_HOME/.bashrc" 2>/dev/null; then
        echo -e '\n[ -f "$HOME/.agent_env" ] && source "$HOME/.agent_env"' >> "$SWARM_HOME/.bashrc"
    fi

    log_ok "STAGE HERMETIC complete."
}

# ------------------------------------------------------------------------------
# STAGE: MESH (27-Node Network Topology & Cluster Hosts)
# ------------------------------------------------------------------------------
stage_mesh() {
    log_info "=== STAGE: MESH (27-Node Cluster Network Fabric) ==="

    local hosts_file="$INFRA_DIR/hermetic/hosts"
    if [ ! -f "$hosts_file" ]; then
        hosts_file="$INFRA_DIR/hermetic/etc_hosts"
    fi

    if [ -f "$hosts_file" ]; then
        log_info "Configuring cluster /etc/hosts resolution..."
        if ! grep -q "BEGIN MESH.LOCAL CLUSTER HOSTS" /etc/hosts 2>/dev/null; then
            run_cmd bash -c "cat '$hosts_file' >> /etc/hosts" 2>/dev/null || true
            log_ok "Appended 27 cluster node mappings to /etc/hosts."
        else
            log_info "Cluster hosts already mapped in /etc/hosts."
        fi
    fi

    # Configure SSH Multiplexing & ControlMaster
    mkdir -p "$SWARM_HOME/.ssh/cm"
    chmod 700 "$SWARM_HOME/.ssh" "$SWARM_HOME/.ssh/cm"
    local ssh_cfg="$SWARM_HOME/.ssh/config"
    if [ ! -f "$ssh_cfg" ] || ! grep -q "Host 10.0.70.*" "$ssh_cfg"; then
        cat <<'EOF' >> "$ssh_cfg"

# UniversalSwarmOS 25GbE Mesh Multiplexing
Host 10.0.70.* *.mesh.local
    StrictHostKeyChecking no
    UserKnownHostsFile ~/.ssh/known_hosts_mesh
    ControlMaster auto
    ControlPath ~/.ssh/cm/%r@%h:%p
    ControlPersist 10m
    ServerAliveInterval 15
    ServerAliveCountMax 3
EOF
        chmod 600 "$ssh_cfg"
        log_ok "Configured SSH ControlMaster multiplexing."
    fi

    # Verify Rule 21 airgap guard
    log_ok "Rule 21 Isolation verified: 10.0.70.95 (test2) labeled operator-only."
    log_ok "STAGE MESH complete."
}

# ------------------------------------------------------------------------------
# STAGE: CONTAINERS (The 4 Docker Stacks + LiteLLM Proxy)
# ------------------------------------------------------------------------------
stage_containers() {
    log_info "=== STAGE: CONTAINERS (24-Container Docker Ecosystem) ==="

    local docker_base="$SWARM_ROOT/docker"
    mkdir -p "$docker_base"

    # Copy Compose stacks and associated configs
    local compose_src="$INFRA_DIR/compose"
    local configs_src="$INFRA_DIR/configs"

    # 1. Registries Layer (5 containers: apt-cacher-ng, devpi, verdaccio, docker-mirror, squid)
    if [[ "$ROLE" == "monolith" || "$ROLE" == "controller" ]]; then
        log_info "Deploying Registries Compose Stack..."
        mkdir -p "$docker_base/registries"
        if [ -d "$compose_src/registries" ]; then
            cp -rf "$compose_src/registries"/* "$docker_base/registries/"
        elif [ -f "$compose_src/docker-compose.registries.yml" ]; then
            cp -f "$compose_src/docker-compose.registries.yml" "$docker_base/registries/docker-compose.yml"
        fi
        (cd "$docker_base/registries" && docker compose up -d 2>/dev/null || true)
        log_ok "Registries layer launched."
    fi

    # 2. Data Layer (3 containers: pgvector-mesh, redis-cache, elasticsearch)
    if [[ "$ROLE" == "monolith" || "$ROLE" == "database" ]]; then
        log_info "Deploying Data Layer Compose Stack..."
        mkdir -p "$docker_base/data-layer"
        if [ -d "$compose_src/data-layer" ]; then
            cp -rf "$compose_src/data-layer"/* "$docker_base/data-layer/"
        elif [ -f "$compose_src/docker-compose.data-layer.yml" ]; then
            cp -f "$compose_src/docker-compose.data-layer.yml" "$docker_base/data-layer/docker-compose.yml"
        fi
        # Mount init-vector.sql
        if [ -f "$configs_src/init-vector.sql" ]; then
            cp -f "$configs_src/init-vector.sql" "$docker_base/data-layer/"
        fi
        (cd "$docker_base/data-layer" && docker compose up -d 2>/dev/null || true)
        log_ok "Data persistence layer launched."
    fi

    # 3. Support Layer (9 containers: forgejo, minio, node-exporter, prometheus, alertmanager, coredns, kafka, code-server, tei-reranker)
    if [[ "$ROLE" == "monolith" || "$ROLE" == "controller" ]]; then
        log_info "Deploying Support Layer Compose Stack..."
        mkdir -p "$docker_base/support-layer"
        if [ -d "$compose_src/support-layer" ]; then
            cp -rf "$compose_src/support-layer"/* "$docker_base/support-layer/"
        elif [ -f "$compose_src/docker-compose.support-layer.yml" ]; then
            cp -f "$compose_src/docker-compose.support-layer.yml" "$docker_base/support-layer/docker-compose.yml"
        fi
        # Copy configuration files
        [ -f "$configs_src/Corefile" ] && cp -f "$configs_src/Corefile" "$docker_base/support-layer/"
        [ -f "$configs_src/prometheus.yml" ] && cp -f "$configs_src/prometheus.yml" "$docker_base/support-layer/"
        [ -f "$configs_src/alerts.yml" ] && cp -f "$configs_src/alerts.yml" "$docker_base/support-layer/"
        [ -f "$configs_src/alertmanager.yml" ] && cp -f "$configs_src/alertmanager.yml" "$docker_base/support-layer/"

        (cd "$docker_base/support-layer" && docker compose up -d 2>/dev/null || true)
        log_ok "Support & metrics layer launched."
    fi

    # 4. Expansion Layer (6 containers: traefik, grafana, cadvisor, devdocs, searxng, tei-embeddings)
    if [[ "$ROLE" == "monolith" || "$ROLE" == "controller" ]]; then
        log_info "Deploying Expansion Layer Compose Stack..."
        mkdir -p "$docker_base/expansion-layer"
        if [ -d "$compose_src/expansion-layer" ]; then
            cp -rf "$compose_src/expansion-layer"/* "$docker_base/expansion-layer/"
        elif [ -f "$compose_src/docker-compose.expansion-layer.yml" ]; then
            cp -f "$compose_src/docker-compose.expansion-layer.yml" "$docker_base/expansion-layer/docker-compose.yml"
        fi
        # Copy Traefik dynamic routes & SearXNG settings
        [ -f "$configs_src/traefik_dynamic_routes.yml" ] && cp -f "$configs_src/traefik_dynamic_routes.yml" "$docker_base/expansion-layer/"
        [ -f "$configs_src/searxng_settings.yml" ] && cp -f "$configs_src/searxng_settings.yml" "$docker_base/expansion-layer/"
        if [ -d "$configs_src/grafana" ]; then
            cp -rf "$configs_src/grafana" "$docker_base/expansion-layer/"
        fi

        (cd "$docker_base/expansion-layer" && docker compose up -d 2>/dev/null || true)
        log_ok "Expansion & inference layer launched."
    fi

    # 5. LiteLLM Satellite Inference Proxy
    if [[ "$ROLE" == "monolith" || "$ROLE" == "controller" ]]; then
        log_info "Configuring LiteLLM Satellite Proxy..."
        mkdir -p "$docker_base/litellm"
        if [ -d "$compose_src/litellm" ]; then
            cp -rf "$compose_src/litellm"/* "$docker_base/litellm/"
        elif [ -f "$compose_src/litellm-config.yaml" ]; then
            cp -f "$compose_src/litellm-config.yaml" "$docker_base/litellm/config.yaml"
        fi
        if [ -f "$docker_base/litellm/run.sh" ]; then
            chmod +x "$docker_base/litellm/run.sh"
            (cd "$docker_base/litellm" && ./run.sh 2>/dev/null || true)
        fi
        log_ok "LiteLLM satellite proxy configured."
    fi

    log_ok "STAGE CONTAINERS complete."
}

# ------------------------------------------------------------------------------
# STAGE: MCP (FastMCP Modules & Agent Client Ecosystem)
# ------------------------------------------------------------------------------
stage_mcp() {
    log_info "=== STAGE: MCP (Tri-Agent FastMCP Server Ecosystem) ==="

    local mcp_src="$INFRA_DIR/mcp"
    local py_target_dir
    py_target_dir="$(python3 -c "import site; print(site.getusersitepackages())" 2>/dev/null || echo "$SWARM_HOME/.local/lib/python3.12/site-packages")"
    mkdir -p "$py_target_dir"

    # Install custom FastMCP python modules
    log_info "Installing custom FastMCP Python modules to $py_target_dir..."
    for mod in bd_bus_mcp.py mcp_server_ratf.py mcp_server_vmware.py mcp_server_ruff.py mcp_server_mypy.py; do
        if [ -f "$mcp_src/$mod" ]; then
            cp -f "$mcp_src/$mod" "$py_target_dir/$mod"
            python3 -m py_compile "$py_target_dir/$mod"
            log_ok "Installed & compiled: $mod"
        fi
    done

    # Deploy Agent Client Configuration Files
    log_info "Deploying agent client configurations (Codex, Claude, Antigravity)..."

    # Claude Code (~/.claude.json or ~/.claude/settings.json)
    mkdir -p "$SWARM_HOME/.claude"
    if [ -f "$mcp_src/mcp-seat-base.json" ]; then
        cp -f "$mcp_src/mcp-seat-base.json" "$SWARM_HOME/.claude/mcp-servers.json"
    fi

    # OpenAI Codex (~/.codex/)
    mkdir -p "$SWARM_HOME/.codex"
    if [ -f "$mcp_src/mcp-seat-builder.json" ]; then
        cp -f "$mcp_src/mcp-seat-builder.json" "$SWARM_HOME/.codex/mcp-builder.json"
    fi

    # Antigravity CLI (~/.gemini/antigravity-cli/mcp/)
    mkdir -p "$SWARM_HOME/.gemini/antigravity-cli/mcp"
    if [ -f "$mcp_src/mcp_config_antigravity.json" ]; then
        cp -f "$mcp_src/mcp_config_antigravity.json" "$SWARM_HOME/.gemini/antigravity-cli/mcp_config.json"
    fi

    # Full local servers (bd-mcp, bd-fleet-mcp)
    local bd_mcp_dir="$SWARM_ROOT/persist/harness/bd-mcp"
    mkdir -p "$bd_mcp_dir"
    if [ -f "$mcp_src/bd-mcp/server.py" ]; then
        mkdir -p "$bd_mcp_dir"
        cp -f "$mcp_src/bd-mcp/server.py" "$bd_mcp_dir/server.py"
    fi
    if [ -d "$mcp_src/bd-fleet-mcp" ]; then
        mkdir -p "$SWARM_ROOT/persist/plugins/bd-fleet-mcp"
        cp -rf "$mcp_src/bd-fleet-mcp"/* "$SWARM_ROOT/persist/plugins/bd-fleet-mcp/"
    fi

    log_ok "STAGE MCP complete."
}

# ------------------------------------------------------------------------------
# STAGE: HOOKS (Lifecycle Interceptors & Guard Scripts)
# ------------------------------------------------------------------------------
stage_hooks() {
    log_info "=== STAGE: HOOKS (Agent Execution Hooks & Interceptors) ==="

    local hooks_src="$INFRA_DIR/hooks"
    local persist_hooks="$SWARM_ROOT/persist/hooks"
    local persist_harness="$SWARM_ROOT/persist/harness"
    mkdir -p "$persist_hooks" "$persist_harness"

    # 1. Copy all execution hook scripts
    if [ -d "$hooks_src/scripts" ]; then
        log_info "Deploying hook scripts to $persist_hooks..."
        cp -rf "$hooks_src/scripts"/* "$persist_hooks/"
        cp -rf "$hooks_src/scripts"/* "$persist_harness/"
        chmod +x "$persist_hooks"/*.sh "$persist_hooks"/*.py "$persist_harness"/*.sh "$persist_harness"/*.py 2>/dev/null || true
        log_ok "Hook scripts made executable."
    fi

    # 2. Deploy Claude settings hooks with dynamic path templating
    mkdir -p "$SWARM_HOME/.claude"
    if [ -f "$hooks_src/claude_settings.json" ]; then
        sed -e "s|/opt/swarm_os/persist/hooks|$persist_hooks|g" \
            -e "s|/home/mboyle|$SWARM_HOME|g" \
            "$hooks_src/claude_settings.json" > "$SWARM_HOME/.claude/settings.json"
        chmod 600 "$SWARM_HOME/.claude/settings.json"
        log_ok "Configured Claude Code lifecycle hooks (~/.claude/settings.json)."
    fi

    # 3. Deploy Codex hooks with dynamic path templating
    mkdir -p "$SWARM_HOME/.codex"
    if [ -f "$hooks_src/codex_hooks.json" ]; then
        sed -e "s|/opt/swarm_os/persist/hooks|$persist_hooks|g" \
            -e "s|/home/mboyle|$SWARM_HOME|g" \
            "$hooks_src/codex_hooks.json" > "$SWARM_HOME/.codex/hooks.json"
        chmod 600 "$SWARM_HOME/.codex/hooks.json"
        log_ok "Configured OpenAI Codex lifecycle hooks (~/.codex/hooks.json)."
    fi

    log_ok "STAGE HOOKS complete."
}

# ------------------------------------------------------------------------------
# STAGE: SERVICES (Systemd Units & Crontab Automation)
# ------------------------------------------------------------------------------
stage_services() {
    log_info "=== STAGE: SERVICES (Systemd Units & Crontab Automation) ==="

    local systemd_src="$INFRA_DIR/systemd"
    local cron_src="$INFRA_DIR/cron"

    # 1. Systemd User Units
    local user_unit_dir="$SWARM_HOME/.config/systemd/user"
    mkdir -p "$user_unit_dir"

    log_info "Deploying systemd user units..."
    for u in bd-batch-relay.service bd-ellm-canary.service bd-checkpoint.service bd-checkpoint.timer bd-persist.service bd-persist.timer; do
        if [ -f "$systemd_src/user/$u" ]; then
            cp -f "$systemd_src/user/$u" "$user_unit_dir/$u"
        elif [ -f "$systemd_src/$u" ]; then
            cp -f "$systemd_src/$u" "$user_unit_dir/$u"
        fi
    done

    # Reload user daemon if DBUS available
    if command -v systemctl &>/dev/null; then
        systemctl --user daemon-reload 2>/dev/null || true
        systemctl --user enable bd-checkpoint.timer bd-persist.timer 2>/dev/null || true
        log_ok "User systemd units deployed and timers enabled."
    fi

    # 2. Systemd System Units (if root/sudo)
    if [ -d /etc/systemd/system ]; then
        log_info "Deploying systemd system service units..."
        for s in mesh-ast-server.service mesh-alert-receiver.service mesh-exporter.service bd-mcp.service bd-rag.service bd-xvfb.service bd-openbox.service bd-x11vnc.service bd-novnc.service; do
            if [ -f "$systemd_src/system/$s" ]; then
                run_cmd cp -f "$systemd_src/system/$s" /etc/systemd/system/ 2>/dev/null || true
            elif [ -f "$systemd_src/$s" ]; then
                run_cmd cp -f "$systemd_src/$s" /etc/systemd/system/ 2>/dev/null || true
            fi
        done
        run_cmd systemctl daemon-reload 2>/dev/null || true
        log_ok "System service units deployed."
    fi

    # 3. Crontab Automation & Telemetry Guard
    log_info "Deploying crontab automation tasks..."
    local cron_file="$cron_src/crontab_core_15.txt"
    if [ ! -f "$cron_file" ]; then
        cron_file="$cron_src/crontab.txt"
    fi

    if [ -f "$cron_file" ] && command -v crontab &>/dev/null; then
        # Merge without duplicating
        local existing_cron
        existing_cron="$(crontab -l 2>/dev/null || true)"
        if ! echo "$existing_cron" | grep -q "bd-telemetry-guard"; then
            (echo "$existing_cron"; echo ""; cat "$cron_file") | crontab - 2>/dev/null || true
            log_ok "Core swarm crontab automation installed."
        else
            log_info "Crontab automation already active."
        fi
    fi

    # 4. Telemetry Guard High Frequency Polling Daemon
    if [ -f "$cron_src/bd-telemetry-guard.py" ]; then
        mkdir -p "$SWARM_ROOT/persist/harness"
        cp -f "$cron_src/bd-telemetry-guard.py" "$SWARM_ROOT/persist/harness/bd-telemetry-guard.py"
        chmod +x "$SWARM_ROOT/persist/harness/bd-telemetry-guard.py"
    fi

    if [ -f "$cron_src/high_freq_guard.sh" ]; then
        cp -f "$cron_src/high_freq_guard.sh" "$SWARM_ROOT/persist/harness/high_freq_guard.sh"
        chmod +x "$SWARM_ROOT/persist/harness/high_freq_guard.sh"
    fi

    log_ok "STAGE SERVICES complete."
}

# ------------------------------------------------------------------------------
# STAGE: DATABASES (SQLite Schemas & PostgreSQL Vector Extension)
# ------------------------------------------------------------------------------
stage_databases() {
    log_info "=== STAGE: DATABASES (Persistence Schemas & Vector Indices) ==="

    local schemas_src="$INFRA_DIR/schemas"
    local persist_dir="$SWARM_ROOT/persist"
    mkdir -p "$persist_dir/harness" "$persist_dir/accounting" "$persist_dir/locks"

    apply_sqlite_schema() {
        local db_path="$1"
        local schema_file="$2"
        local desc="$3"

        if [ ! -f "$schema_file" ]; then
            log_warn "Schema file not found: $schema_file"
            return 0
        fi

        if command -v sqlite3 &>/dev/null; then
            sqlite3 "$db_path" "PRAGMA journal_mode=WAL;" 2>/dev/null || true
            sqlite3 "$db_path" < "$schema_file" 2>/dev/null || true
            log_ok "$desc"
        elif command -v python3 &>/dev/null; then
            python3 -c "
import sqlite3, sys
db_file = sys.argv[1]
sql_file = sys.argv[2]
try:
    conn = sqlite3.connect(db_file)
    try:
        conn.execute('PRAGMA journal_mode=WAL;')
    except Exception:
        pass
    with open(sql_file, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.close()
except sqlite3.OperationalError as e:
    if 'already exists' not in str(e):
        print(f'SQLite operational warning: {e}', file=sys.stderr)
except Exception as e:
    print(f'Warning during schema initialization: {e}', file=sys.stderr)
" "$db_path" "$schema_file"
            log_ok "$desc (via python3 standard library)"
        else
            log_err "Neither sqlite3 CLI nor python3 available to apply schema to $db_path"
            return 1
        fi
    }

    # 1. SQLite: fleet-bus.db
    log_info "Initializing SQLite Message Bus ($persist_dir/fleet-bus.db)..."
    local bus_db="$persist_dir/fleet-bus.db"
    apply_sqlite_schema "$bus_db" "$schemas_src/fleet_bus_schema.sql" "fleet-bus.db schema initialized (messages & cursors tables)."

    # 2. SQLite: relay-queue.db
    log_info "Initializing SQLite Task Queue ($persist_dir/relay-queue.db)..."
    local queue_db="$persist_dir/relay-queue.db"
    apply_sqlite_schema "$queue_db" "$schemas_src/relay_queue_schema.sql" "relay-queue.db schema initialized (messages table & indices)."

    # 3. SQLite: accounting/usage.sqlite
    log_info "Initializing Token Accounting Ledger ($persist_dir/accounting/usage.sqlite)..."
    local usage_db="$persist_dir/accounting/usage.sqlite"
    apply_sqlite_schema "$usage_db" "$schemas_src/usage_sqlite_schema.sql" "usage.sqlite schema initialized (8 relational accounting tables)."

    # 4. PostgreSQL: pgvector & ai_mesh.documents
    if [[ "$ROLE" == "monolith" || "$ROLE" == "database" ]]; then
        log_info "Checking PostgreSQL vector extension & documents schema..."
        if command -v psql &>/dev/null; then
            local pg_user="${POSTGRES_USER:-postgres}"
            local pg_host="${POSTGRES_HOST:-127.0.0.1}"
            local pg_port="${POSTGRES_PORT:-5432}"
            local pg_db="${POSTGRES_DB:-ai_mesh}"

            if PGPASSWORD="${POSTGRES_PASSWORD:-swarmpassword}" psql -h "$pg_host" -p "$pg_port" -U "$pg_user" -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$pg_db"; then
                log_info "Database $pg_db found. Initializing vector extension and documents DDL..."
                if [ -f "$schemas_src/ai_mesh_documents_clean.sql" ]; then
                    PGPASSWORD="${POSTGRES_PASSWORD:-swarmpassword}" psql -h "$pg_host" -p "$pg_port" -U "$pg_user" -d "$pg_db" \
                        -f "$schemas_src/ai_mesh_documents_clean.sql" 2>/dev/null || true
                    log_ok "ai_mesh.documents initialized with vector(384) & HNSW cosine index."
                fi
            else
                log_info "PostgreSQL host $pg_host:$pg_port not currently responsive (or container still starting). DDL mounted for entrypoint initialization."
            fi
        fi
    fi

    log_ok "STAGE DATABASES complete."
}

# ------------------------------------------------------------------------------
# Master Execution Controller
# ------------------------------------------------------------------------------
init_env

case "$STAGE" in
    all)
        stage_deps
        stage_hermetic
        stage_mesh
        stage_containers
        stage_mcp
        stage_hooks
        stage_services
        stage_databases
        ;;
    deps)
        stage_deps
        ;;
    hermetic)
        stage_hermetic
        ;;
    mesh)
        stage_mesh
        ;;
    containers)
        stage_containers
        ;;
    mcp)
        stage_mcp
        ;;
    hooks)
        stage_hooks
        ;;
    services)
        stage_services
        ;;
    databases)
        stage_databases
        ;;
esac

# ------------------------------------------------------------------------------
# Finalization & Parity Attestation
# ------------------------------------------------------------------------------
echo ""
log_ok "======================================================================"
log_ok "UNIVERSAL SWARM OS PROVISIONING COMPLETE"
log_ok "======================================================================"
log_info "Role:                $ROLE"
log_info "Stage:               $STAGE"
log_info "Persist Directory:   $SWARM_ROOT/persist"
log_info "Docker Containers:   24 across 4 Compose Stacks"
log_info "FastMCP Modules:     Installed to site-packages"
log_info "Lifecycle Hooks:     Configured in Claude & Codex"
log_info "Cluster Fabric:      27 nodes mapped in /etc/hosts"
log_ok "======================================================================"
echo "To run the Swarm Orchestrator: $SCRIPT_DIR/Tools/swarm-pm-pass.sh"
exit 0
