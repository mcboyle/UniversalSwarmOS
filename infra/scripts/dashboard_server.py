import http.server
import socketserver
import json
import sqlite3
import time
import os
import urllib.parse
import threading

PORT = 9998

def get_data():
    conn = sqlite3.connect('/home/mboyle/bd-persist/accounting/usage.sqlite', timeout=10.0)
    c = conn.cursor()
    rates = {'claude-fable-5-1': {'in': 3.0, 'out': 15.0, 'cache': 0.3}, 'claude-opus-5-5': {'in': 15.0, 'out': 75.0, 'cache': 1.5}}
    
    q = """
    SELECT r.model, o.thread,
           SUM(json_extract(r.usage, '$.input_tokens')) - SUM(COALESCE(json_extract(r.usage, '$.cache_read_input_tokens'),0)) as base_input,
           SUM(COALESCE(json_extract(r.usage, '$.cache_read_input_tokens'),0)) as cache_read,
           SUM(json_extract(r.usage, '$.output_tokens')) as total_output, COUNT(*) as turns
    FROM usage_occurrences o JOIN usage_responses r ON o.provider = r.provider AND o.response_id = r.response_id
    WHERE r.timestamp >= '2026-09-22T21:00:00Z' GROUP BY o.thread, r.model;
    """
    total_cost = 0; total_in = 0; total_cache = 0; total_turns = 0
    agents = []
    
    for row in c.execute(q).fetchall():
        model, thread, base_in, cache_in, out, turns = row
        base_in = base_in or 0; cache_in = cache_in or 0; out = out or 0
        total_in += base_in + cache_in; total_cache += cache_in; total_turns += turns
        r = rates.get(model, {'in': 3.0, 'out': 15.0, 'cache': 0.3})
        cost = (base_in / 1e6 * r['in']) + (cache_in / 1e6 * r['cache']) + (out / 1e6 * r['out'])
        total_cost += cost
        agents.append({
            "name": thread[:16],
            "model": model,
            "turns": turns,
            "tokens": f"{(base_in + cache_in)/1e6:.1f}M",
            "cost": f"${cost:.2f}"
        })
    
    # Ledger
    ledger = []
    active_workers = set()
    try:
        with open('/home/mboyle/bd-persist/DISPATCH-LEDGER.tsv') as f:
            lines = [l for l in f.readlines() if l.strip()]
            for line in reversed(lines[-15:]):
                parts = line.strip().split('\t')
                if len(parts) >= 4:
                    status = parts[3]
                    worker = parts[1]
                    if status in ['dispatched', 'started']:
                        active_workers.add(worker)
                    ledger.append({"time": parts[0][-9:-1], "agent": worker, "row": parts[2], "status": status.upper()})
    except:
        pass
        
    try:
        with open('/home/mboyle/project-knowledge/IMPROVEMENT_BACKLOG.md') as f:
            lines = f.readlines()
        open_rows = sum(1 for line in lines if '| OPEN |' in line)
    except:
        open_rows = 0

    hit_rate = (total_cache / total_in * 100) if total_in > 0 else 0
    
    
    # Historical Savings (Last 10 Hours)
    historical = []
    q_hist = '''
    SELECT strftime('%Y-%m-%dT%H:00:00Z', r.timestamp) as hour,
           SUM(COALESCE(json_extract(r.usage, '$.cache_read_input_tokens'),0)) as cache_read
    FROM usage_occurrences o JOIN usage_responses r ON o.provider = r.provider AND o.response_id = r.response_id
    WHERE r.timestamp >= datetime('now', '-10 hours')
    GROUP BY hour ORDER BY hour;
    '''
    for row in c.execute(q_hist).fetchall():
        historical.append({"hour": row[0][-14:-1], "savings": (row[1] / 1e6) * 15.0}) # Assuming $15/1M Opus tokens saved

    return {
        "historical": historical,
        "metrics": {
            "active_agents": len(active_workers),
            "total_turns": total_turns,
            "hit_rate": f"{hit_rate:.1f}%",
            "total_cost": f"${total_cost:.2f}",
            "backlog": open_rows
        },
        "agents": sorted(agents, key=lambda x: x['turns'], reverse=True)[:10],
        "ledger": ledger
    }

html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fleet Operations Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #0f1115; color: #e2e8f0; font-family: 'Inter', sans-serif; }
        .card { background-color: #1a1d24; border: 1px solid #2d313a; border-radius: 0.75rem; }
        .text-neon { color: #34d399; }
    </style>
</head>
<body class="p-6">
    <div class="max-w-7xl mx-auto">
        <header class="flex justify-between items-center mb-8">
            <h1 class="text-2xl md:text-3xl font-bold flex items-center gap-3">
                <span class="text-neon">⚡</span> Fleet Operations
            </h1>
            <div class="text-sm text-gray-400" id="last-updated">Updating...</div>
        </header>

        <!-- Top Metrics -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
            <div class="card p-5">
                <div class="text-gray-400 text-sm mb-1 font-semibold tracking-wider">ACTIVE AGENTS</div>
                <div class="text-3xl font-bold text-white" id="m-agents">-</div>
            </div>
            <div class="card p-5">
                <div class="text-gray-400 text-sm mb-1 font-semibold tracking-wider">TOTAL OPS (TURNS)</div>
                <div class="text-3xl font-bold text-white" id="m-turns">-</div>
            </div>
            <div class="card p-5">
                <div class="text-gray-400 text-sm mb-1 font-semibold tracking-wider">CACHE HIT RATE</div>
                <div class="text-3xl font-bold text-neon" id="m-hit">-</div>
            </div>
            <div class="card p-5">
                <div class="text-gray-400 text-sm mb-1 font-semibold tracking-wider">ROWS REMAINING</div>
                <div class="text-3xl font-bold text-white" id="m-backlog">-</div>
            </div>
            <div class="card p-5 border-l-4 border-neon">
                <div class="text-gray-400 text-sm mb-1 font-semibold tracking-wider">FLEET COST</div>
                <div class="text-3xl font-bold text-neon" id="m-cost">-</div>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            <!-- Left: Chart & Agents -->
            <div class="col-span-2 space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="card p-5">
                        <h2 class="text-sm font-semibold text-gray-400 mb-4 tracking-wider">OPERATIONS OVERVIEW</h2>
                        <canvas id="opsChart" height="150"></canvas>
                    </div>
                    <div class="card p-5">
                        <h2 class="text-sm font-semibold text-gray-400 mb-4 tracking-wider">CUMULATIVE CACHE SAVINGS (USD)</h2>
                        <canvas id="savingsChart" height="150"></canvas>
                    </div>
                </div>

                
                <div class="card p-5">
                    <h2 class="text-sm font-semibold text-gray-400 mb-4 tracking-wider">AGENT HEALTH & USAGE</h2>
                    <div class="overflow-x-auto"><table class="w-full text-left text-sm min-w-[500px]">
                        <thead class="text-gray-500 border-b border-gray-700">
                            <tr>
                                <th class="pb-3 font-medium">AGENT SESSION</th>
                                <th class="pb-3 font-medium">MODEL</th>
                                <th class="pb-3 font-medium">OPS</th>
                                <th class="pb-3 font-medium">TOKENS</th>
                                <th class="pb-3 font-medium">COST</th>
                            </tr>
                        </thead>
                        <tbody id="agent-list" class="divide-y divide-gray-800">
                        </tbody>
                    </table></div>
                </div>
            </div>

            <!-- Right: Queue -->
            <div class="space-y-6">
                <div class="card p-5">
                    <h2 class="text-sm font-semibold text-gray-400 mb-4 tracking-wider">LIVE DISPATCH QUEUE</h2>
                    <div class="space-y-3" id="ledger-list">
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let chart = null;

        function updateDashboard() {
            fetch('/api/data')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('m-agents').innerText = data.metrics.active_agents;
                    document.getElementById('m-turns').innerText = data.metrics.total_turns;
                    document.getElementById('m-hit').innerText = data.metrics.hit_rate;
                    document.getElementById('m-cost').innerText = data.metrics.total_cost;
                    document.getElementById('m-backlog').innerText = data.metrics.backlog;
                    document.getElementById('last-updated').innerText = "Live • " + new Date().toLocaleTimeString();

                    // Update Chart
                    const labels = data.agents.map(a => a.name);
                    const turns = data.agents.map(a => a.turns);
                    
                    if (!chart) {
                        const ctx = document.getElementById('opsChart').getContext('2d');
                        chart = new Chart(ctx, {
                            type: 'bar',
                            data: {
                                labels: labels,
                                datasets: [{
                                    label: 'Operations (Turns)',
                                    data: turns,
                                    backgroundColor: '#ef4444',
                                    borderRadius: 4
                                }]
                            },
                            options: {
                                responsive: true,
                                indexAxis: 'y',
                                plugins: { legend: { display: false } },
                                scales: { 
                                    x: { grid: { color: '#2d313a' }, ticks: { color: '#9ca3af' } },
                                    y: { grid: { display: false }, ticks: { color: '#e2e8f0' } }
                                }
                            }
                        });
                    } else {
                        chart.data.labels = labels;
                        chart.data.datasets[0].data = turns;
                        chart.update();
                    }

                    // Update Savings Chart
                    const histLabels = data.historical.map(h => h.hour);
                    const histSavings = data.historical.map(h => h.savings);
                    
                    if (!window.savingsChart) {
                        const ctx2 = document.getElementById('savingsChart').getContext('2d');
                        window.savingsChart = new Chart(ctx2, {
                            type: 'line',
                            data: {
                                labels: histLabels,
                                datasets: [{
                                    label: 'Saved USD ($)',
                                    data: histSavings,
                                    borderColor: '#34d399',
                                    backgroundColor: 'rgba(52, 211, 153, 0.1)',
                                    fill: true,
                                    tension: 0.4
                                }]
                            },
                            options: {
                                responsive: true,
                                plugins: { legend: { display: false } },
                                scales: { 
                                    x: { grid: { display: false }, ticks: { color: '#9ca3af' } },
                                    y: { grid: { color: '#2d313a' }, ticks: { color: '#e2e8f0', callback: function(v){return '$'+v} } }
                                }
                            }
                        });
                    } else {
                        window.savingsChart.data.labels = histLabels;
                        window.savingsChart.data.datasets[0].data = histSavings;
                        window.savingsChart.update();
                    }


                    // Update Agents
                    const agentHtml = data.agents.map(a => `
                        <tr>
                            <td class="py-3 flex items-center gap-2">
                                <div class="w-2 h-2 rounded-full bg-green-400"></div>
                                ${a.name}
                            </td>
                            <td class="py-3 text-gray-400">${a.model}</td>
                            <td class="py-3">${a.turns}</td>
                            <td class="py-3 text-gray-400">${a.tokens}</td>
                            <td class="py-3 font-mono">${a.cost}</td>
                        </tr>
                    `).join('');
                    document.getElementById('agent-list').innerHTML = agentHtml;

                    // Update Ledger
                    const ledgerHtml = data.ledger.map(l => {
                        const color = l.status === 'DONE' ? 'text-green-400' : 'text-blue-400';
                        return `
                            <div class="bg-[#1e222a] p-3 rounded-lg border border-gray-800">
                                <div class="flex justify-between items-center mb-1">
                                    <span class="font-medium text-sm">${l.agent}</span>
                                    <span class="text-xs ${color} bg-gray-800 px-2 py-0.5 rounded border border-gray-700">${l.status}</span>
                                </div>
                                <div class="text-xs text-gray-400 flex justify-between">
                                    <span>Row ${l.row}</span>
                                    <span>${l.time}</span>
                                </div>
                            </div>
                        `;
                    }).join('');
                    document.getElementById('ledger-list').innerHTML = ledgerHtml;
                });
        }

        setInterval(updateDashboard, 2000);
        updateDashboard();
    </script>
</body>
</html>
"""

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(html_template.encode('utf-8'))
        elif self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_data()).encode('utf-8'))
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass # Suppress logging

if __name__ == '__main__':
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), DashboardHandler) as httpd:
        print(f"Serving dashboard at http://localhost:{PORT}")
        httpd.serve_forever()
