#!/usr/bin/env python3
"""
MAIA PVI Airlock Dashboard

SR 26-02 Compliance Validation Dashboard with Security & DME Integration
Run: python3 app/dashboard.py
Access: http://localhost:3033
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Import from services
from app.services.metrics import metrics, create_transaction
from app.dme_engine import SectorAdapter, RoleAdapter, ToolAdapter
from app.security import security_orchestrator, get_security_orchestrator


HTML = """<!DOCTYPE html>
<html>
<head>
    <title>MAIA PVI Airlock Dashboard</title>
    <meta http-equiv="Cache-Control" content="no-cache">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0f; color: #e0e0e0; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px 40px; border-bottom: 1px solid #2a2a4a; }
        .header h1 { color: #00d4ff; font-size: 28px; }
        .header .badge { background: #00d4ff; color: #000; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }
        .header .badge.security { background: #ff6b6b; }
        .container { max-width: 1600px; margin: 0 auto; padding: 20px; }
        .compliance-banner { background: linear-gradient(90deg, #00d4ff, #0066ff); color: #000; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 20px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 15px; margin-bottom: 30px; }
        .metric-card { background: #12121a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 15px; text-align: center; }
        .metric-card.passed { border-left: 4px solid #00ff88; }
        .metric-card.blocked { border-left: 4px solid #ff4444; }
        .metric-card.security { border-left: 4px solid #ff6b6b; }
        .metric-card.dme { border-left: 4px solid #9b59b6; }
        .metric-value { font-size: 28px; font-weight: bold; margin-bottom: 5px; }
        .metric-label { color: #888; font-size: 11px; text-transform: uppercase; }
        .section-title { color: #00d4ff; font-size: 18px; margin: 20px 0 15px; padding-bottom: 8px; border-bottom: 1px solid #2a2a4a; }
        .charts-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 20px; }
        .chart-card { background: #12121a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 15px; }
        .chart-title { color: #00d4ff; font-size: 14px; margin-bottom: 12px; font-weight: 600; }
        .bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
        .bar-label { width: 70px; font-size: 12px; color: #888; }
        .bar-fill { height: 20px; border-radius: 4px; }
        .bar-value { width: 35px; text-align: right; font-size: 12px; }
        .controls-card { background: #12121a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 15px; margin-bottom: 20px; }
        .controls-title { color: #00d4ff; font-size: 14px; margin-bottom: 12px; }
        .controls-row { display: flex; gap: 30px; flex-wrap: wrap; margin-bottom: 15px; }
        .control-group { display: flex; flex-direction: column; gap: 6px; }
        .control-label { color: #888; font-size: 11px; text-transform: uppercase; }
        .select-input { background: #1a1a2e; color: #fff; border: 1px solid #2a2a4a; padding: 8px 12px; border-radius: 6px; font-size: 13px; }
        .toggle-switch { position: relative; display: inline-block; width: 48px; height: 24px; }
        .toggle-switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #444; transition: .4s; border-radius: 24px; }
        .slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background-color: #00ff88; }
        input:checked + .slider:before { transform: translateX(24px); }
        .button-group { display: flex; gap: 10px; flex-wrap: wrap; }
        .btn { padding: 10px 18px; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 12px; }
        .btn-pass { background: #00ff88; color: #000; }
        .btn-fail { background: #ff4444; color: #fff; }
        .btn-sme { background: #ffaa00; color: #000; }
        .btn-clear { background: #444; color: #fff; }
        .table-card { background: #12121a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 15px; }
        .table-title { color: #00d4ff; font-size: 14px; margin-bottom: 12px; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 10px; color: #888; font-size: 11px; text-transform: uppercase; border-bottom: 1px solid #2a2a4a; }
        td { padding: 10px; font-size: 12px; border-bottom: 1px solid #1a1a2e; }
        .status-badge { padding: 3px 8px; border-radius: 10px; font-size: 10px; }
        .status-pass { background: #00ff8833; color: #00ff88; }
        .status-blocked { background: #ff444433; color: #ff4444; }
        .status-pending { background: #ffaa0033; color: #ffaa00; }
        .security-badge { padding: 3px 8px; border-radius: 10px; font-size: 10px; }
        .security-ok { background: #00ff8833; color: #00ff88; }
        .security-threat { background: #ff444433; color: #ff4444; }
    </style>
</head>
<body>
    <div class="header">
        <h1>MAIA PVI Airlock Dashboard <span class="badge">SR 26-02</span> <span class="badge security">SECURE</span></h1>
    </div>
    <div class="container">
        <div class="compliance-banner">Federal Reserve SR 26-02 Compliance • DME Engine • Weight-Level Security</div>
        
        <!-- Core Metrics -->
        <div class="metrics-grid">
            <div class="metric-card"><div class="metric-value" id="total-tx">0</div><div class="metric-label">Total Transactions</div></div>
            <div class="metric-card passed"><div class="metric-value" id="passed-tx" style="color:#00ff88">0</div><div class="metric-label">Passed</div></div>
            <div class="metric-card blocked"><div class="metric-value" id="blocked-tx" style="color:#ff4444">0</div><div class="metric-label">Blocked</div></div>
            <div class="metric-card security"><div class="metric-value" id="security-blocked" style="color:#ff6b6b">0</div><div class="metric-label">Security Threats</div></div>
            <div class="metric-card dme"><div class="metric-value" id="t1-escalations" style="color:#ffaa00">0</div><div class="metric-label">Tier 1 Escalations</div></div>
            <div class="metric-card pending"><div class="metric-value" id="pending-tx" style="color:#ffaa00">0</div><div class="metric-label">Pending SME</div></div>
        </div>
        
        <!-- DME & Security Toggles -->
        <div class="controls-card">
            <div class="controls-title">DME Engine & Security Controls</div>
            <div class="controls-row">
                <div class="control-group">
                    <div class="control-label">DME Engine</div>
                    <label class="toggle-switch">
                        <input type="checkbox" id="dme-enabled" checked>
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="control-group">
                    <div class="control-label">Weight-Level Defense</div>
                    <label class="toggle-switch">
                        <input type="checkbox" id="weight-defense" checked>
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="control-group">
                    <div class="control-label">Latent Hash Verification</div>
                    <label class="toggle-switch">
                        <input type="checkbox" id="latent-hash" checked>
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="control-group">
                    <div class="control-label">Role Access Control</div>
                    <label class="toggle-switch">
                        <input type="checkbox" id="role-access" checked>
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="control-group">
                    <div class="control-label">DHITL MFA</div>
                    <label class="toggle-switch">
                        <input type="checkbox" id="dhitl-mfa" checked>
                        <span class="slider"></span>
                    </label>
                </div>
            </div>
        </div>
        
        <!-- Charts -->
        <div class="charts-row">
            <div class="chart-card"><div class="chart-title">Materiality Tier Distribution</div><div id="tier-chart"></div></div>
            <div class="chart-card"><div class="chart-title">Sector Detection (DME)</div><div id="sector-chart"></div></div>
            <div class="chart-card"><div class="chart-title">Security Events</div><div id="security-chart"></div></div>
        </div>
        
        <!-- Controls -->
        <div class="controls-card">
            <div class="controls-title">Test Scenarios</div>
            <div class="controls-row">
                <div class="control-group">
                    <div class="control-label">Test Cases</div>
                    <div class="button-group">
                        <button class="btn btn-pass" onclick="run('pass')">PASS (T3)</button>
                        <button class="btn btn-pass" onclick="run('elevated_pass')">PASS (T2)</button>
                        <button class="btn btn-fail" onclick="run('fail')">FAIL (T1)</button>
                        <button class="btn btn-fail" onclick="run('security')">SECURITY</button>
                        <button class="btn btn-sme" onclick="run('sme_review')">SME</button>
                        <button class="btn btn-clear" onclick="clear()">Clear</button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Transaction Log -->
        <div class="table-card">
            <div class="table-title">Transaction Log</div>
            <table>
                <thead><tr><th>Time</th><th>ID</th><th>Query</th><th>Sector</th><th>Tool</th><th>Tier</th><th>Sec</th><th>Status</th><th>Reason</th></tr></thead>
                <tbody id="tbody"></tbody>
            </table>
        </div>
    </div>
    <script>
        const tierColors = {'1': '#ff4444', '2': '#ffaa00', '3': '#00ff88'};
        async function load() {
            const r = await fetch('/api/metrics');
            const d = await r.json();
            document.getElementById('total-tx').textContent = d.summary.total_transactions;
            document.getElementById('passed-tx').textContent = d.summary.passed;
            document.getElementById('blocked-tx').textContent = d.summary.blocked;
            document.getElementById('pending-tx').textContent = d.summary.pending_sme;
            let html = '';
            for (const [t, c] of Object.entries(d.summary.tier_distribution)) {
                const pct = d.summary.total_transactions ? c/d.summary.total_transactions*100 : 0;
                html += '<div class="bar-row"><div class="bar-label">Tier '+t+'</div><div class="bar-fill" style="width:'+pct+'%;background:'+tierColors[t]+'"></div><div class="bar-value">'+c+'</div></div>';
            }
            document.getElementById('tier-chart').innerHTML = html;
            html = '';
            for (const [domain, c] of Object.entries(d.summary.domain_distribution)) {
                const pct = d.summary.total_transactions ? c/d.summary.total_transactions*100 : 0;
                html += '<div class="bar-row"><div class="bar-label">'+domain+'</div><div class="bar-fill" style="width:'+pct+'%;background:#00d4ff"></div><div class="bar-value">'+c+'</div></div>';
            }
            document.getElementById('domain-chart').innerHTML = html;
            html = '';
            for (const tx of d.transactions.slice(0, 20)) {
                let cls = tx.status=='BLOCKED'?'status-blocked':tx.status=='PENDING_SME_REVIEW'?'status-pending':'status-pass';
                html += '<tr><td>'+tx.timestamp.split('T')[1].split('.')[0]+'</td><td style="color:#00d4ff">'+tx.transaction_id+'</td><td style="max-width:200px;overflow:hidden">'+tx.query+'</td><td style="color:'+tierColors[tx.materiality_tier]+'">Tier '+tx.materiality_tier+'</td><td><span class="status-badge '+cls+'">'+tx.status+'</span></td><td>'+(tx.routing_method||'-')+'</td><td>'+tx.latency_ms+'ms</td><td style="max-width:150px;overflow:hidden">'+(tx.reason||'-')+'</td></tr>';
            }
            document.getElementById('tbody').innerHTML = html;
        }
        async function run(s) { 
            const routing = document.getElementById('routing-method').value;
            await fetch('/api/simulate?scenario='+s+'&routing='+routing); 
            load(); 
        }
        async function clear() { await fetch('/api/clear',{method:'POST'}); load(); }
        setInterval(load, 2000);
        load();
    </script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif self.path == "/api/metrics":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "summary": metrics.get_summary(),
                "transactions": metrics.get_transactions(50)
            }).encode())
        elif self.path.startswith("/api/simulate"):
            params = parse_qs(urlparse(self.path).query)
            scenario = params.get("scenario", ["pass"])[0]
            routing = params.get("routing", ["llm"])[0]
            tx = create_transaction(scenario)
            tx["routing_method"] = routing
            if scenario == "sme_review":
                tx["dhitl_session_id"] = f"dhitl-{tx['transaction_id'].split('-')[1]}"
                tx["sme_votes"] = [{"sme_id": f"sme-00{i+1}", "vote": "APPROVE" if i<2 else "REJECT"} for i in range(3)]
            metrics.add(tx)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "simulated"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path.startswith("/api/simulate"):
            scenario = parse_qs(urlparse(self.path).query).get("scenario", ["pass"])[0]
            tx = create_transaction(scenario)
            if scenario == "sme_review":
                tx["dhitl_session_id"] = f"dhitl-{tx['transaction_id'].split('-')[1]}"
                tx["sme_votes"] = [{"sme_id": f"sme-00{i+1}", "vote": "APPROVE" if i<2 else "REJECT"} for i in range(3)]
            metrics.add(tx)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "simulated"}).encode())
        elif self.path == "/api/clear":
            metrics.clear()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "cleared"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print("MAIA PVI Airlock Dashboard - http://localhost:3033")
    HTTPServer(("0.0.0.0", 3033), Handler).serve_forever()