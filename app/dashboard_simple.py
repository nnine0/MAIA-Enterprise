#!/usr/bin/env python3
"""
MAIA PVI Airlock Dashboard - Simple HTTP Server
Run with: python3 dashboard_simple.py
Access at: http://localhost:3033
"""

import json
import uuid
import random
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Metrics store
class MetricsStore:
    def __init__(self):
        self.transactions = []
        self.total_passed = 0
        self.total_blocked = 0
        self.total_pending_sme = 0
        self.tier_distribution = {"1": 0, "2": 0, "3": 0}
        self.domain_distribution = {}
        self.sme_votes = []
        
    def add_transaction(self, tx):
        self.transactions.append(tx)
        if tx["status"] in ["PASS", "PASS (BYPASS)"]:
            self.total_passed += 1
        elif tx["status"] == "BLOCKED":
            self.total_blocked += 1
        elif tx["status"] == "PENDING_SME_REVIEW":
            self.total_pending_sme += 1
        tier = str(tx.get("materiality_tier", 3))
        self.tier_distribution[tier] = self.tier_distribution.get(tier, 0) + 1
        domain = tx.get("domain", "unknown")
        self.domain_distribution[domain] = self.domain_distribution.get(domain, 0) + 1
    
    def get_summary(self):
        total = len(self.transactions)
        return {
            "total_transactions": total,
            "passed": self.total_passed,
            "blocked": self.total_blocked,
            "pending_sme": self.total_pending_sme,
            "pass_rate": f"{(self.total_passed/total*100):.1f}%" if total > 0 else "0%",
            "block_rate": f"{(self.total_blocked/total*100):.1f}%" if total > 0 else "0%",
            "avg_latency_ms": "125",
            "tier_distribution": self.tier_distribution,
            "domain_distribution": self.domain_distribution
        }
    
    def get_transactions(self, limit=50):
        return sorted(self.transactions, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
    
    def clear(self):
        self.transactions = []
        self.total_passed = 0
        self.total_blocked = 0
        self.total_pending_sme = 0
        self.tier_distribution = {"1": 0, "2": 0, "3": 0}
        self.domain_distribution = {}

metrics = MetricsStore()

SCENARIOS = {
    "pass": {
        "queries": [
            "List all meeting rooms on floor 5",
            "What is the weather forecast for today?",
            "Schedule a 30min meeting with the team",
            "Update my contact information",
            "Show the company holiday calendar",
            "What time does the cafeteria close?",
            "Find the nearest parking garage",
            "Reset my password",
            "Check my PTO balance",
            "Submit an expense report for $45"
        ],
        "tier": 3, "status": "PASS (BYPASS)", "latency_ms_range": (35, 65), 
        "reasons": [
            "Low materiality - bypassed audit",
            "Benign query - no compliance risk",
            "Administrative task - auto-approved",
            "Standard lookup - no policy concerns"
        ]
    },
    "elevated_pass": {
        "queries": [
            "Update credit policy for small business loans",
            "Review quarterly risk assessment report",
            "Approve vendor contract for IT services",
            "Renew insurance policy for commercial property",
            "Generate compliance report for regulators",
            "Process payroll for 500 employees",
            "Approve budget variance over $50K",
            "Review audit findings from Q3",
            "Update anti-money laundering procedures",
            "Approve new hedging strategy"
        ],
        "tier": 2, "status": "PASS", "latency_ms_range": (150, 280),
        "reasons": [
            "AI audit passed - compliant with SR 26-02",
            "All policy checks validated successfully",
            "Risk controls verified - proceeding",
            "Materiality within acceptable thresholds",
            "Dual-control approval completed"
        ]
    },
    "fail": {
        "queries": [
            "Approve $75M loan without stress test buffer",
            "Wire $25M to sanctioned entity in Iran",
            "Execute derivative trade exceeding limit",
            "Approve credit for flagged PEP customer",
            "Settle transaction in unapproved jurisdiction",
            "Process wire to country under sanctions",
            "Approve loan missing KYC completion",
            "Execute trade without margin requirement",
            "Approve credit line exceeding authority",
            "Transfer funds to blocked list entity"
        ],
        "tier": 1, "status": "BLOCKED", "latency_ms_range": (380, 520),
        "reasons": [
            "SR 26-02 violation: Missing 2026 capital reserve calculation",
            "Sanctions compliance check failed - entity blocked",
            "Credit authority exceeded - requires board approval",
            "KYC verification incomplete - transaction held",
            "Stress test buffer below regulatory threshold",
            "AML flags triggered - transaction frozen",
            "Regulatory limit breach - immediate block",
            "Missing required documentation for approval"
        ]
    },
    "elevated_fail": {
        "queries": [
            "Increase credit limit without income verification",
            "Approve loan with incomplete credit check",
            "Waive late fees for flagged account",
            "Override risk score for high-risk client",
            "Approve transaction below minimum threshold",
            "Modify loan terms without authorization",
            "Skip required due diligence for expedited approval",
            "Approve trade with incomplete margin verification"
        ],
        "tier": 2, "status": "BLOCKED", "latency_ms_range": (190, 290),
        "reasons": [
            "AI audit failed - income verification required",
            "Credit check incomplete - transaction blocked",
            "Risk override requires senior approval",
            "Missing required documentation for processing",
            "Compliance verification failed - manual review needed",
            "Policy violation - automated block"
        ]
    },
    "sme_review": {
        "queries": [
            "Wire $10M to new international correspondent bank",
            "Approve acquisition of competitor in regulated market",
            "Issue stand-by letter of credit for $50M",
            "Process restructure for troubled commercial loan",
            "Approve derivatives exposure increase above limit",
            "Execute trade with new counterparty group",
            "Settle complex multi-currency transaction",
            "Approve credit facility for politically exposed person",
            "Process merger with pending regulatory approval",
            "Authorize exposure to new asset class"
        ],
        "tier": 1, "status": "PENDING_SME_REVIEW", "latency_ms_range": (160, 240),
        "reasons": [
            "Tier 1 requires human SME review - high materiality",
            "New counterparty requires manual approval",
            "Regulatory submission requires sign-off",
            "Complex transaction needs committee review",
            " Politically exposed person - enhanced due diligence"
        ]
    }
}

import random
import time
def get_random_scenario(scenario_key):
    s = SCENARIOS[scenario_key]
    # Generate realistic timestamps spread over last 4 hours
    offset_seconds = random.randint(0, 4*60*60)
    timestamp = datetime.now() - timedelta(seconds=offset_seconds)
    return {
        "query": random.choice(s["queries"]),
        "tier": s["tier"],
        "status": s["status"],
        "latency_ms": random.randint(*s["latency_ms_range"]),
        "reason": random.choice(s["reasons"]),
        "timestamp": timestamp.isoformat()
    }

HTML = """<!DOCTYPE html>
<html>
<head>
    <title>MAIA PVI Airlock Dashboard</title>
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0f; color: #e0e0e0; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 20px 40px; border-bottom: 1px solid #2a2a4a; }
        .header h1 { color: #00d4ff; font-size: 28px; display: flex; align-items: center; gap: 15px; }
        .header .badge { background: #00d4ff; color: #000; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
        .metric-card { background: #12121a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 20px; text-align: center; }
        .metric-card.passed { border-left: 4px solid #00ff88; }
        .metric-card.blocked { border-left: 4px solid #ff4444; }
        .metric-card.pending { border-left: 4px solid #ffaa00; }
        .metric-value { font-size: 36px; font-weight: bold; margin-bottom: 5px; }
        .metric-label { color: #888; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }
        .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
        .chart-card { background: #12121a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 20px; }
        .chart-title { color: #00d4ff; font-size: 16px; margin-bottom: 15px; font-weight: 600; }
        .bar-chart { display: flex; flex-direction: column; gap: 10px; }
        .bar-row { display: flex; align-items: center; gap: 10px; }
        .bar-label { width: 80px; font-size: 14px; color: #888; }
        .bar-container { flex: 1; background: #1a1a2e; height: 24px; border-radius: 4px; overflow: hidden; }
        .bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
        .bar-value { width: 50px; text-align: right; font-size: 14px; }
        .controls-card { background: #12121a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 20px; margin-bottom: 30px; }
        .controls-title { color: #00d4ff; font-size: 16px; margin-bottom: 15px; font-weight: 600; }
        .button-group { display: flex; gap: 15px; flex-wrap: wrap; }
        .btn { padding: 12px 24px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s; font-size: 14px; }
        .btn-pass { background: #00ff88; color: #000; }
        .btn-fail { background: #ff4444; color: #fff; }
        .btn-sme { background: #ffaa00; color: #000; }
        .btn-clear { background: #444; color: #fff; }
        .btn:active { transform: scale(0.95); }
        .table-card { background: #12121a; border: 1px solid #2a2a4a; border-radius: 12px; padding: 20px; }
        .table-title { color: #00d4ff; font-size: 16px; margin-bottom: 15px; font-weight: 600; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 12px; color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #2a2a4a; }
        td { padding: 12px; font-size: 14px; border-bottom: 1px solid #1a1a2e; }
        .status-badge { padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        .status-pass { background: #00ff8833; color: #00ff88; }
        .status-blocked { background: #ff444433; color: #ff4444; }
        .status-pending { background: #ffaa0033; color: #ffaa00; }
        .compliance-banner { background: linear-gradient(90deg, #00d4ff 0%, #0066ff 100%); color: #000; padding: 15px 20px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 20px; }
        .last-updated { color: #666; font-size: 12px; text-align: right; margin-top: 10px; }
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
            <div class="metric-card passed"><div class="metric-value" id="passed-tx" style="color: #00ff88">0</div><div class="metric-label">Passed</div></div>
            <div class="metric-card blocked"><div class="metric-value" id="blocked-tx" style="color: #ff4444">0</div><div class="metric-label">Blocked</div></div>
            <div class="metric-card pending"><div class="metric-value" id="pending-tx" style="color: #ffaa00">0</div><div class="metric-label">Pending SME Review</div></div>
        </div>
        <div class="charts-row">
            <div class="chart-card"><div class="chart-title">Materiality Tier Distribution</div><div class="bar-chart" id="tier-chart"></div></div>
            <div class="chart-card"><div class="chart-title">Domain Distribution</div><div class="bar-chart" id="domain-chart"></div></div>
        </div>
        <div class="controls-card">
            <div class="controls-title">Test Scenarios</div>
            <div class="button-group">
                <button class="btn btn-pass" onclick="runScenario('pass')">PASS (Tier 3)</button>
                <button class="btn btn-pass" onclick="runScenario('elevated_pass')">PASS (Tier 2)</button>
                <button class="btn btn-fail" onclick="runScenario('fail')">FAIL (Tier 1)</button>
                <button class="btn btn-fail" onclick="runScenario('elevated_fail')">FAIL (Tier 2)</button>
                <button class="btn btn-sme" onclick="runScenario('sme_review')">SME Review (Tier 1)</button>
                <button class="btn btn-clear" onclick="clearMetrics()">Clear All</button>
            </div>
            <div class="last-updated" id="last-updated">Last updated: --</div>
        </div>
        <div class="table-card">
            <div class="table-title">Transaction Log</div>
            <table>
                <thead><tr><th>Timestamp</th><th>Transaction ID</th><th>Query</th><th>Tier</th><th>Status</th><th>Latency</th><th>Reason</th></tr></thead>
                <tbody id="transactions-body"></tbody>
            </table>
        </div>
    </div>
    <script>
        async function refreshMetrics() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();
                document.getElementById('total-tx').textContent = data.summary.total_transactions;
                document.getElementById('passed-tx').textContent = data.summary.passed;
                document.getElementById('blocked-tx').textContent = data.summary.blocked;
                document.getElementById('pending-tx').textContent = data.summary.pending_sme;
                const tierChart = document.getElementById('tier-chart');
                const tierColors = {'1': '#ff4444', '2': '#ffaa00', '3': '#00ff88'};
                tierChart.innerHTML = '';
                for (const [tier, count] of Object.entries(data.summary.tier_distribution)) {
                    const pct = data.summary.total_transactions > 0 ? (count / data.summary.total_transactions * 100) : 0;
                    tierChart.innerHTML += '<div class="bar-row"><div class="bar-label">Tier ' + tier + '</div><div class="bar-container"><div class="bar-fill" style="width: ' + pct + '%; background: ' + tierColors[tier] + '"></div></div><div class="bar-value">' + count + '</div></div>';
                }
                const domainChart = document.getElementById('domain-chart');
                domainChart.innerHTML = '';
                for (const [domain, count] of Object.entries(data.summary.domain_distribution)) {
                    const pct = data.summary.total_transactions > 0 ? (count / data.summary.total_transactions * 100) : 0;
                    domainChart.innerHTML += '<div class="bar-row"><div class="bar-label">' + domain + '</div><div class="bar-container"><div class="bar-fill" style="width: ' + pct + '%; background: #00d4ff"></div></div><div class="bar-value">' + count + '</div></div>';
                }
                const tbody = document.getElementById('transactions-body');
                tbody.innerHTML = '';
                for (const tx of data.transactions.slice(0, 20)) {
                    let statusClass = tx.status === 'BLOCKED' ? 'status-blocked' : tx.status === 'PENDING_SME_REVIEW' ? 'status-pending' : 'status-pass';
                    tbody.innerHTML += '<tr><td>' + tx.timestamp.split('T')[1].split('.')[0] + '</td><td><code style="color: #00d4ff">' + tx.transaction_id + '</code></td><td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;">' + tx.query + '</td><td><span style="color: ' + tierColors[tx.materiality_tier] + '">Tier ' + tx.materiality_tier + '</span></td><td><span class="status-badge ' + statusClass + '">' + tx.status + '</span></td><td>' + tx.latency_ms + 'ms</td><td style="max-width: 150px; overflow: hidden; text-overflow: ellipsis;">' + (tx.reason || '-') + '</td></tr>';
                }
                document.getElementById('last-updated').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
            } catch (e) { console.error('Failed to refresh metrics:', e); }
        }
        async function runScenario(scenario) {
            try { await fetch('/api/simulate?scenario=' + scenario); await refreshMetrics(); } catch (e) { console.error('Failed to run scenario:', e); }
        }
        async function clearMetrics() { try { await fetch('/api/clear', {method: 'POST'}); await refreshMetrics(); } catch (e) { console.error('Failed to clear:', e); } }
        setInterval(refreshMetrics, 2000);
        refreshMetrics();
    </script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif parsed.path == "/api/metrics":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"summary": metrics.get_summary(), "transactions": metrics.get_transactions(50), "sme_votes": len(metrics.sme_votes)}).encode())
        elif parsed.path == "/api/simulate":
            scenario = parse_qs(parsed.query).get("scenario", ["pass"])[0]
            s = get_random_scenario(scenario)
            tx = {"transaction_id": f"maia-{uuid.uuid4().hex[:8]}", "timestamp": s["timestamp"], "query": s["query"], "domain": "finance", "materiality_tier": s["tier"], "status": s["status"], "latency_ms": s["latency_ms"], "reason": s["reason"], "policy_vetted": "SR 26-02", "latent_hash": uuid.uuid4().hex[:16]}
            if scenario == "sme_review":
                tx["dhitl_session_id"] = f"dhitl-{uuid.uuid4().hex[:8]}"
                tx["sme_votes"] = [{"sme_id": f"sme-00{i+1}", "vote": "APPROVE" if i < 2 else "REJECT", "rationale": "Compliant" if i < 2 else "Needs review"} for i in range(3)]
                tx["sme_consensus"] = "APPROVED"
                metrics.sme_votes.extend(tx["sme_votes"])
            metrics.add_transaction(tx)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "simulated", "transaction": tx}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/simulate":
            scenario = parse_qs(parsed.query).get("scenario", ["pass"])[0]
            s = get_random_scenario(scenario)
            tx = {"transaction_id": f"maia-{uuid.uuid4().hex[:8]}", "timestamp": s["timestamp"], "query": s["query"], "domain": "finance", "materiality_tier": s["tier"], "status": s["status"], "latency_ms": s["latency_ms"], "reason": s["reason"], "policy_vetted": "SR 26-02", "latent_hash": uuid.uuid4().hex[:16]}
            if scenario == "sme_review":
                tx["dhitl_session_id"] = f"dhitl-{uuid.uuid4().hex[:8]}"
                tx["sme_votes"] = [{"sme_id": f"sme-00{i+1}", "vote": "APPROVE" if i < 2 else "REJECT", "rationale": "Compliant" if i < 2 else "Needs review"} for i in range(3)]
                tx["sme_consensus"] = "APPROVED"
                metrics.sme_votes.extend(tx["sme_votes"])
            metrics.add_transaction(tx)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "simulated", "transaction": tx}).encode())
        elif parsed.path == "/api/clear":
            metrics.clear()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "cleared"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logging

if __name__ == "__main__":
    print("Starting MAIA PVI Airlock Dashboard on http://localhost:3033")
    server = HTTPServer(("0.0.0.0", 3033), Handler)
    server.serve_forever()