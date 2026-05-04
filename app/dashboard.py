#!/usr/bin/env python3
"""
MAIA PVI Airlock Dashboard

SR 26-02 Compliance Validation Dashboard
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
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .compliance-banner { background: linear-gradient(90deg, #00d4ff, #0066ff); color: #000; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 20px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
        .metric-card { background: #12121a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 20px; text-align: center; }
        .metric-card.passed { border-left: 4px solid #00ff88; }
        .metric-card.blocked { border-left: 4px solid #ff4444; }
        .metric-card.pending { border-left: 4px solid #ffaa00; }
        .metric-value { font-size: 36px; font-weight: bold; margin-bottom: 5px; }
        .metric-label { color: #888; font-size: 14px; text-transform: uppercase; }
        .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
        .chart-card { background: #12121a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 20px; }
        .chart-title { color: #00d4ff; font-size: 16px; margin-bottom: 15px; font-weight: 600; }
        .bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
        .bar-label { width: 80px; font-size: 14px; color: #888; }
        .bar-fill { height: 24px; border-radius: 4px; }
        .bar-value { width: 40px; text-align: right; font-size: 14px; }
        .controls-card { background: #12121a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 20px; margin-bottom: 30px; }
        .controls-title { color: #00d4ff; font-size: 16px; margin-bottom: 15px; }
        .button-group { display: flex; gap: 15px; flex-wrap: wrap; }
        .btn { padding: 12px 24px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px; }
        .btn-pass { background: #00ff88; color: #000; }
        .btn-fail { background: #ff4444; color: #fff; }
        .btn-sme { background: #ffaa00; color: #000; }
        .btn-clear { background: #444; color: #fff; }
        .table-card { background: #12121a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 20px; }
        .table-title { color: #00d4ff; font-size: 16px; margin-bottom: 15px; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 12px; color: #888; font-size: 12px; text-transform: uppercase; border-bottom: 1px solid #2a2a4a; }
        td { padding: 12px; font-size: 14px; border-bottom: 1px solid #1a1a2e; }
        .status-badge { padding: 4px 10px; border-radius: 12px; font-size: 12px; }
        .status-pass { background: #00ff8833; color: #00ff88; }
        .status-blocked { background: #ff444433; color: #ff4444; }
        .status-pending { background: #ffaa0033; color: #ffaa00; }
    </style>
</head>
<body>
    <div class="header">
        <h1>MAIA PVI Airlock Dashboard <span class="badge">SR 26-02 COMPLIANT</span></h1>
    </div>
    <div class="container">
        <div class="compliance-banner">Federal Reserve SR 26-02 Compliance Validation Layer</div>
        <div class="metrics-grid">
            <div class="metric-card"><div class="metric-value" id="total-tx">0</div><div class="metric-label">Total Transactions</div></div>
            <div class="metric-card passed"><div class="metric-value" id="passed-tx" style="color:#00ff88">0</div><div class="metric-label">Passed</div></div>
            <div class="metric-card blocked"><div class="metric-value" id="blocked-tx" style="color:#ff4444">0</div><div class="metric-label">Blocked</div></div>
            <div class="metric-card pending"><div class="metric-value" id="pending-tx" style="color:#ffaa00">0</div><div class="metric-label">Pending SME Review</div></div>
        </div>
        <div class="charts-row">
            <div class="chart-card"><div class="chart-title">Materiality Tier Distribution</div><div id="tier-chart"></div></div>
            <div class="chart-card"><div class="chart-title">Domain Distribution</div><div id="domain-chart"></div></div>
        </div>
        <div class="controls-card">
            <div class="controls-title">Test Scenarios</div>
            <div class="button-group">
                <button class="btn btn-pass" onclick="run('pass')">PASS (Tier 3)</button>
                <button class="btn btn-pass" onclick="run('elevated_pass')">PASS (Tier 2)</button>
                <button class="btn btn-fail" onclick="run('fail')">FAIL (Tier 1)</button>
                <button class="btn btn-fail" onclick="run('elevated_fail')">FAIL (Tier 2)</button>
                <button class="btn btn-sme" onclick="run('sme_review')">SME Review (Tier 1)</button>
                <button class="btn btn-clear" onclick="clear()">Clear All</button>
            </div>
        </div>
        <div class="table-card">
            <div class="table-title">Transaction Log</div>
            <table>
                <thead><tr><th>Time</th><th>ID</th><th>Query</th><th>Tier</th><th>Status</th><th>Latency</th><th>Reason</th></tr></thead>
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
                html += '<tr><td>'+tx.timestamp.split('T')[1].split('.')[0]+'</td><td style="color:#00d4ff">'+tx.transaction_id+'</td><td style="max-width:200px;overflow:hidden">'+tx.query+'</td><td style="color:'+tierColors[tx.materiality_tier]+'">Tier '+tx.materiality_tier+'</td><td><span class="status-badge '+cls+'">'+tx.status+'</span></td><td>'+tx.latency_ms+'ms</td><td style="max-width:150px;overflow:hidden">'+(tx.reason||'-')+'</td></tr>';
            }
            document.getElementById('tbody').innerHTML = html;
        }
        async function run(s) { await fetch('/api/simulate?scenario='+s); load(); }
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