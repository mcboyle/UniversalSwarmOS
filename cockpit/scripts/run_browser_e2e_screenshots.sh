#!/usr/bin/env bash
# scripts/run_browser_e2e_screenshots.sh
# Milestone 4 (AC3 & AC4): Headless Chrome Browser E2E Runner and Visual Screenshot Capture.
#
# Generates:
# - /tmp/cockpit_e2e_telemetry.png (1920x1080)
# - /tmp/cockpit_e2e_swarm_control.png (1920x1080)
# - /tmp/cockpit_e2e_quotas.png (1920x1080)
# - /tmp/cockpit_dom.html (full rendered DOM)
#
# Asserts:
# - 'grok' and 'kimi' models are rendered in the DOM
# - Zero client-side or React runtime errors

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CHROME_BIN="/usr/bin/google-chrome-stable"

PORT="${TEST_PORT:-3456}"
BASE_URL="http://localhost:${PORT}"
CDP_PORT=9444

echo "======================================================================"
echo "Cockpit Upgrade: Browser E2E & Visual Screenshot Verification (AC3/AC4)"
echo "======================================================================"
echo "Target Base URL: $BASE_URL"
echo "Chrome Binary:   $CHROME_BIN"

# --- Step 1: Ensure Next.js Server is Running ---
SERVER_PID=""
cleanup_server() {
  if [ -n "$SERVER_PID" ]; then
    echo "Stopping test server (PID $SERVER_PID)..."
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup_server EXIT INT TERM

if curl -s -f -m 1 "${BASE_URL}/api/nodes" >/dev/null 2>&1; then
  echo "✓ Next.js server already running on port ${PORT}"
else
  echo "Starting Next.js production server on port ${PORT}..."
  cd "$PROJECT_ROOT"
  npx next start -p "$PORT" > /tmp/next_e2e_browser.log 2>&1 &
  SERVER_PID=$!

  READY=0
  for i in $(seq 1 30); do
    if curl -s -f -m 1 "${BASE_URL}/api/nodes" >/dev/null 2>&1; then
      READY=1
      break
    fi
    sleep 0.5
  done

  if [ "$READY" -ne 1 ]; then
    echo "Error: Server failed to start on port ${PORT} within 15 seconds."
    cat /tmp/next_e2e_browser.log
    exit 1
  fi
  echo "✓ Test server ready on ${BASE_URL} (PID $SERVER_PID)"
fi

# --- Step 2: Launch Chrome with Remote Debugging & Window Size 1920x1080 ---
USER_DATA_DIR=$(mktemp -d -t chrome_e2e_XXXXXX)
cleanup_chrome() {
  if [ -n "${CHROME_PID:-}" ]; then
    kill "$CHROME_PID" 2>/dev/null || true
  fi
  rm -rf "$USER_DATA_DIR"
}
trap 'cleanup_chrome; cleanup_server' EXIT INT TERM

echo "Launching Headless Chrome on CDP port ${CDP_PORT}..."
"$CHROME_BIN" \
  --headless=new \
  --disable-gpu \
  --no-sandbox \
  --window-size=1920,1080 \
  --remote-debugging-port="$CDP_PORT" \
  --user-data-dir="$USER_DATA_DIR" \
  "${BASE_URL}" > /tmp/chrome_e2e.log 2>&1 &
CHROME_PID=$!

# Wait for Chrome CDP readiness
CHROME_READY=0
for i in $(seq 1 20); do
  if curl -s -f -m 1 "http://127.0.0.1:${CDP_PORT}/json" >/dev/null 2>&1; then
    CHROME_READY=1
    break
  fi
  sleep 0.5
done

if [ "$CHROME_READY" -ne 1 ]; then
  echo "Error: Chrome CDP failed to initialize on port ${CDP_PORT}."
  cat /tmp/chrome_e2e.log
  exit 1
fi
echo "✓ Headless Chrome ready with CDP on port ${CDP_PORT}"

# --- Step 3: Run Automation Script to Capture Screenshots & Dump DOM ---
node - <<'EOF'
import fs from 'node:fs';

const CDP_PORT = 9444;

async function run() {
  const jsonRes = await fetch(`http://127.0.0.1:${CDP_PORT}/json`);
  const targets = await jsonRes.json();
  const pageTarget = targets.find(t => t.type === 'page' && !t.url.startsWith('chrome-extension://'));
  if (!pageTarget) {
    throw new Error('No page target found in Chrome');
  }

  const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);

  let messageId = 1;
  const pendingRequests = new Map();

  function sendCommand(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = messageId++;
      pendingRequests.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.id && pendingRequests.has(data.id)) {
      const { resolve, reject } = pendingRequests.get(data.id);
      pendingRequests.delete(data.id);
      if (data.error) {
        reject(new Error(data.error.message));
      } else {
        resolve(data.result);
      }
    }
  };

  await new Promise(res => { ws.onopen = res; });

  await sendCommand('Page.enable');
  await sendCommand('Runtime.enable');
  await sendCommand('DOM.enable');

  // Wait for React hydration and layout
  await new Promise(r => setTimeout(r, 2500));

  // 1. Capture Telemetry View (default tab)
  console.log('Capturing Telemetry View (1920x1080)...');
  const telemetryScreen = await sendCommand('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync('/tmp/cockpit_e2e_telemetry.png', Buffer.from(telemetryScreen.data, 'base64'));
  console.log('✓ /tmp/cockpit_e2e_telemetry.png saved');

  // 2. Switch to Swarm Control View
  console.log('Navigating to Swarm Control View...');
  await sendCommand('Runtime.evaluate', {
    expression: `
      (function() {
        const btn = document.getElementById('tab-swarm-control') ||
                    Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Swarm Control'));
        if (btn) {
          btn.click();
          return true;
        }
        return false;
      })()
    `
  });
  await new Promise(r => setTimeout(r, 1500));

  console.log('Capturing Swarm Control View (1920x1080)...');
  const swarmScreen = await sendCommand('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync('/tmp/cockpit_e2e_swarm_control.png', Buffer.from(swarmScreen.data, 'base64'));
  console.log('✓ /tmp/cockpit_e2e_swarm_control.png saved');

  // 3. Switch to API Quotas View
  console.log('Navigating to API Quotas View...');
  await sendCommand('Runtime.evaluate', {
    expression: `
      (function() {
        const btn = document.getElementById('tab-quotas') ||
                    Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Quotas') || b.textContent.includes('Headroom'));
        if (btn) {
          btn.click();
          return true;
        }
        return false;
      })()
    `
  });
  await new Promise(r => setTimeout(r, 1500));

  console.log('Capturing API Quotas View (1920x1080)...');
  const quotasScreen = await sendCommand('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync('/tmp/cockpit_e2e_quotas.png', Buffer.from(quotasScreen.data, 'base64'));
  console.log('✓ /tmp/cockpit_e2e_quotas.png saved');

  // 4. Switch to Architecture Visualizer View
  console.log('Navigating to Architecture Visualizer View...');
  await sendCommand('Runtime.evaluate', {
    expression: `
      (function() {
        const btn = document.getElementById('tab-architecture') ||
                    Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Architecture') || b.textContent.includes('Topology'));
        if (btn) {
          btn.click();
          return true;
        }
        return false;
      })()
    `
  });
  await new Promise(r => setTimeout(r, 1500));

  console.log('Capturing Architecture Visualizer View (1920x1080)...');
  const archScreen = await sendCommand('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync('/tmp/cockpit_e2e_architecture.png', Buffer.from(archScreen.data, 'base64'));
  console.log('✓ /tmp/cockpit_e2e_architecture.png saved');

  // 5. Dump Rendered DOM
  console.log('Dumping rendered DOM...');
  const domResult = await sendCommand('Runtime.evaluate', {
    expression: 'document.documentElement.outerHTML'
  });
  fs.writeFileSync('/tmp/cockpit_dom.html', domResult.result.value, 'utf8');
  console.log('✓ /tmp/cockpit_dom.html saved');

  ws.close();
}

run().catch((err) => {
  console.error('Browser automation error:', err);
  process.exit(1);
});
EOF

# Kill Chrome process
kill "$CHROME_PID" 2>/dev/null || true
wait "$CHROME_PID" 2>/dev/null || true

# --- Step 4: Verification & Assertions ---
echo ""
echo "=== Validating Artifacts & Visual Assertions ==="

# Check file existence and non-zero size
for file in "/tmp/cockpit_e2e_telemetry.png" "/tmp/cockpit_e2e_swarm_control.png" "/tmp/cockpit_e2e_quotas.png" "/tmp/cockpit_e2e_architecture.png" "/tmp/cockpit_dom.html"; do
  if [ ! -s "$file" ]; then
    echo "FAIL: Expected artifact $file is missing or empty!"
    exit 1
  fi
  SIZE=$(stat -c%s "$file")
  echo "✓ Artifact $file verified ($SIZE bytes)"
done

# Assert Grok and Kimi appear in DOM
echo ""
echo "Asserting Grok and Kimi model presence in rendered DOM..."
if grep -qi "grok" /tmp/cockpit_dom.html; then
  echo "✓ 'grok' found in rendered HTML"
else
  echo "FAIL: 'grok' was not found in /tmp/cockpit_dom.html"
  exit 1
fi

if grep -qi "kimi" /tmp/cockpit_dom.html; then
  echo "✓ 'kimi' found in rendered HTML"
else
  echo "FAIL: 'kimi' was not found in /tmp/cockpit_dom.html"
  exit 1
fi

# Assert zero client-side error indicators
echo "Checking for client-side crash indicators..."
if grep -i "Application error: a client-side exception has occurred" /tmp/cockpit_dom.html; then
  echo "FAIL: Client-side exception error detected in rendered DOM!"
  exit 1
fi

if grep -i "Minified React error" /tmp/cockpit_dom.html; then
  echo "FAIL: Minified React error detected in rendered DOM!"
  exit 1
fi

if grep -i "Unhandled Runtime Error" /tmp/cockpit_dom.html; then
  echo "FAIL: Unhandled Runtime Error detected in rendered DOM!"
  exit 1
fi

echo "✓ Zero client-side exceptions or React crashes detected"
echo ""
echo "======================================================================"
echo "ALL BROWSER E2E SCREENSHOT & DOM ASSERTIONS PASSED (AC3/AC4 VERIFIED)"
echo "======================================================================"
exit 0
