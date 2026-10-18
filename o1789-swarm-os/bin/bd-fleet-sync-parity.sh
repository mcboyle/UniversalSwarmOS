#!/bin/bash
set -uo pipefail

TARGET_HOST="${1:-}"
if [ -z "$TARGET_HOST" ]; then
  echo "Usage: $0 <target_host_ip>"
  exit 1
fi

SSH_OPTS="-o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o ControlMaster=no -o ControlPath=none"
RSYNC_SSH="ssh $SSH_OPTS"

echo "=== Syncing parity to $TARGET_HOST ==="

# 1. Directories & remove any old gemini symlink before copying wrapper
ssh -n $SSH_OPTS "mboyle@$TARGET_HOST" \
  "mkdir -p /home/mboyle/.gemini/config /home/mboyle/.codex/packages/standalone/releases /home/mboyle/.claude /home/mboyle/.agents/skills /home/mboyle/.agents/plugins /home/mboyle/.local/bin /home/mboyle/.local/share/claude/versions /home/mboyle/.local/lib/node_modules/@google /home/mboyle/.local/lib/node_modules/@caveman-ai /home/mboyle/bin /home/mboyle/.grok/downloads /home/mboyle/.grok/bin /home/mboyle/.kimi-code/bin /home/mboyle/.caveman/bin && rm -f /home/mboyle/.local/bin/gemini" || exit 1

# 2. Hooks & Configs
scp $SSH_OPTS /home/mboyle/.gemini/config/hooks.json /home/mboyle/.gemini/config/shield.py "mboyle@$TARGET_HOST:/home/mboyle/.gemini/config/"
scp $SSH_OPTS /home/mboyle/.gemini/direct_gemini_trustedFolders.json "mboyle@$TARGET_HOST:/home/mboyle/.gemini/direct_gemini_trustedFolders.json"
scp $SSH_OPTS /home/mboyle/.codex/hooks.json "mboyle@$TARGET_HOST:/home/mboyle/.codex/hooks.json"
scp $SSH_OPTS /home/mboyle/.claude/settings.json "mboyle@$TARGET_HOST:/home/mboyle/.claude/settings.json"
scp $SSH_OPTS /home/mboyle/.kimi-code/config.toml /home/mboyle/.kimi-code/mcp.json "mboyle@$TARGET_HOST:/home/mboyle/.kimi-code/" 2>/dev/null || true
scp $SSH_OPTS /home/mboyle/.grok/config.toml /home/mboyle/.grok/version.json "mboyle@$TARGET_HOST:/home/mboyle/.grok/" 2>/dev/null || true

# 3. Skills & Plugins
rsync -az --delete -e "$RSYNC_SSH" /home/mboyle/.agents/skills/ "mboyle@$TARGET_HOST:/home/mboyle/.agents/skills/" >/dev/null
rsync -az --delete -e "$RSYNC_SSH" /home/mboyle/.agents/plugins/ "mboyle@$TARGET_HOST:/home/mboyle/.agents/plugins/" >/dev/null

# 4. Standalone AI CLI binaries (atomic rsync)
rsync -az -e "$RSYNC_SSH" /home/mboyle/.local/bin/agy-real /home/mboyle/.local/bin/opencode-real /home/mboyle/.local/bin/gemini "mboyle@$TARGET_HOST:/home/mboyle/.local/bin/"
rsync -az -e "$RSYNC_SSH" /home/mboyle/.local/share/claude/versions/2.1.302 "mboyle@$TARGET_HOST:/home/mboyle/.local/share/claude/versions/"
rsync -az --delete -e "$RSYNC_SSH" /home/mboyle/.codex/packages/standalone/releases/0.163.0-x86_64-unknown-linux-musl/ "mboyle@$TARGET_HOST:/home/mboyle/.codex/packages/standalone/releases/0.163.0-x86_64-unknown-linux-musl/"
rsync -az -e "$RSYNC_SSH" /home/mboyle/.kimi-code/bin/ "mboyle@$TARGET_HOST:/home/mboyle/.kimi-code/bin/"
rsync -az -e "$RSYNC_SSH" /home/mboyle/.grok/downloads/grok-1.0.62-linux-x86_64 "mboyle@$TARGET_HOST:/home/mboyle/.grok/downloads/"
rsync -az -e "$RSYNC_SSH" /home/mboyle/.caveman/bin/ "mboyle@$TARGET_HOST:/home/mboyle/.caveman/bin/"

# 5. Node-based AI CLIs (gemini, caveman, codeburn, firecrawl) + node v22 if missing/old
rsync -az --delete -e "$RSYNC_SSH" /home/mboyle/.local/lib/node_modules/ "mboyle@$TARGET_HOST:/home/mboyle/.local/lib/node_modules/"
REMOTE_NODE_VER=$(ssh -n $SSH_OPTS "mboyle@$TARGET_HOST" "export PATH=/home/mboyle/.local/bin:/usr/local/bin:/usr/bin:/bin:\$PATH; node --version 2>/dev/null || echo none")
case "$REMOTE_NODE_VER" in
  v22.*|v23.*|v24.*|v25.*|v26.*) ;;
  *)
    rsync -az -e "$RSYNC_SSH" /usr/bin/node "mboyle@$TARGET_HOST:/home/mboyle/.local/bin/node"
    ;;
esac

# 6. Local harness & fleet scripts
rsync -az -e "$RSYNC_SSH" \
  /home/mboyle/bin/bd-ai-harness \
  /home/mboyle/bin/bd-*-local \
  /home/mboyle/bin/bd-local-* \
  /home/mboyle/bin/bd_local_mcp_bridge.py \
  /home/mboyle/bin/bd-spawn-local-seat \
  /home/mboyle/bin/bd-inbox-watcher.py \
  /home/mboyle/bin/bd-realtime-stall-sentinel.py \
  /home/mboyle/bin/bd-token-guard.py \
  /home/mboyle/bin/bd-mesh-bus.py \
  "mboyle@$TARGET_HOST:/home/mboyle/bin/"

# 7. Symlinks & permissions
ssh -n $SSH_OPTS "mboyle@$TARGET_HOST" '
export PATH=/home/mboyle/.local/bin:/usr/local/bin:/home/mboyle/bin:$PATH
grep -q "/home/mboyle/.local/bin" ~/.bashrc 2>/dev/null || echo "export PATH=/home/mboyle/.local/bin:/usr/local/bin:/home/mboyle/bin:\$PATH" >> ~/.bashrc
grep -q "GEMINI_CLI_TRUSTED_FOLDERS_PATH" ~/.bashrc 2>/dev/null || echo "export GEMINI_CLI_TRUSTED_FOLDERS_PATH=/home/mboyle/.gemini/direct_gemini_trustedFolders.json" >> ~/.bashrc
chmod +x /home/mboyle/.local/bin/agy-real /home/mboyle/.local/bin/opencode-real /home/mboyle/.local/bin/gemini /home/mboyle/.local/lib/node_modules/@google/gemini-cli/bundle/gemini.js /home/mboyle/.local/share/claude/versions/2.1.302 /home/mboyle/.kimi-code/bin/kimi /home/mboyle/.grok/downloads/grok-1.0.62-linux-x86_64 /home/mboyle/bin/bd-* 2>/dev/null || true
ln -sf /home/mboyle/.local/bin/agy-real /home/mboyle/.local/bin/agy
ln -sf /home/mboyle/.local/bin/opencode-real /home/mboyle/.local/bin/opencode
ln -sf /home/mboyle/.local/share/claude/versions/2.1.302 /home/mboyle/.local/bin/claude
if [ -e /usr/local/bin/claude ] || [ -L /usr/local/bin/claude ]; then
  sudo -n ln -sf /home/mboyle/.local/share/claude/versions/2.1.302 /usr/local/bin/claude 2>/dev/null || true
fi
ln -sfn /home/mboyle/.codex/packages/standalone/releases/0.163.0-x86_64-unknown-linux-musl /home/mboyle/.codex/packages/standalone/current
ln -sf /home/mboyle/.codex/packages/standalone/current/bin/codex /home/mboyle/.local/bin/codex
ln -sf /home/mboyle/.kimi-code/bin/kimi /home/mboyle/.local/bin/kimi-real
ln -sf /home/mboyle/.local/bin/kimi-real /home/mboyle/.local/bin/kimi
ln -sf ../downloads/grok-1.0.62-linux-x86_64 /home/mboyle/.grok/bin/grok
ln -sf ../downloads/grok-1.0.62-linux-x86_64 /home/mboyle/.grok/bin/agent
ln -sf /home/mboyle/.grok/bin/grok /home/mboyle/.local/bin/grok-real
ln -sf /home/mboyle/.local/bin/grok-real /home/mboyle/.local/bin/grok
ln -sf /home/mboyle/.local/lib/node_modules/@caveman-ai/cli/dist/index.js /home/mboyle/.local/bin/caveman
ln -sf /home/mboyle/.local/lib/node_modules/codeburn/dist/cli.js /home/mboyle/.local/bin/codeburn
ln -sf /home/mboyle/.local/lib/node_modules/firecrawl-cli/dist/index.js /home/mboyle/.local/bin/firecrawl
'

echo "=== Sync complete for $TARGET_HOST ==="
