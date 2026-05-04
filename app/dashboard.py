"""
MAIA PVI Airlock Dashboard
Displays metrics and test scenarios for SR 26-02 compliance validation.
Runs on http://localhost:3033
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import uuid
import random
import asyncio

app = FastAPI(title="MAIA PVI Airlock Dashboard")

# In-memory metrics store
class MetricsStore:
    def __init__(self):
        self.transactions: List[Dict] = []
        self.total_passed = 0
        self.total_blocked = 0
        self.total_pending_sme = 0
        self.tier_distribution = {"1": 0, "2": 0, "3": 0}
        self.domain_distribution = {}
        self.avg_latency_ms = 0
        self.sme_votes = []
        
    def add_transaction(self, tx: Dict):
        self.transactions.append(tx)
        # Update counters
        if tx["status"] == "PASS" or tx["status"] == "PASS (BYPASS)":
            self.total_passed += 1
        elif tx["status"] == "BLOCKED":
            self.total_blocked += 1
        elif tx["status"] == "PENDING_SME_REVIEW":
            self.total_pending_sme += 1
            
        # Tier distribution
        tier = str(tx.get("materiality_tier", 3))
        self.tier_distribution[tier] = self.tier_distribution.get(tier, 0) + 1
        
        # Domain distribution
        domain = tx.get("domain", "unknown")
        self.domain_distribution[domain] = self.domain_distribution.get(domain, 0) + 1
        
        # Calculate avg latency
        if self.transactions:
            latencies = [t.get("latency_ms", 0) for t in self.transactions]
            self.avg_latency_ms = sum(latencies) / len(latencies)
    
    def get_summary(self) -> Dict:
        total = len(self.transactions)
        return {
            "total_transactions": total,
            "passed": self.total_passed,
            "blocked": self.total_blocked,
            "pending_sme": self.total_pending_sme,
            "pass_rate": f"{(self.total_passed/total*100):.1f}%" if total > 0 else "0%",
            "block_rate": f"{(self.total_blocked/total*100):.1f}%" if total > 0 else "0%",
            "avg_latency_ms": f"{self.avg_latency_ms:.1f}",
            "tier_distribution": self.tier_distribution,
            "domain_distribution": self.domain_distribution
        }
    
    def get_transactions(self, limit: int = 50) -> List[Dict]:
        return sorted(self.transactions, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
    
    def clear(self):
        self.transactions = []
        self.total_passed = 0
        self.total_blocked = 0
        self.total_pending_sme = 0
        self.tier_distribution = {"1": 0, "2": 0, "3": 0}
        self.domain_distribution = {}
        self.avg_latency_ms = 0

metrics = MetricsStore()


class TransactionRequest(BaseModel):
    query: str
    domain: str = "finance"
    scenario: Optional[str] = None  # "pass", "fail", "sme_review"


# Simulate different scenarios
SCENARIOS = {
    "pass": {
        "query": "Summarize the IT outage log from 3 AM",
        "tier": 3,
        "status": "PASS (BYPASS)",
        "latency_ms": 45,
        "reason": "Low materiality - bypassed audit"
    },
    "fail": {
        "query": "Approve $50M commercial loan without stress test buffer",
        "tier": 1,
        "status": "BLOCKED",
        "latency_ms": 420,
        "reason": "SR 26-02 violation: Missing 2026 capital reserve calculation"
    },
    "sme_review": {
        "query": "Wire transfer $10M to sanctioned jurisdiction",
        "tier": 1,
        "status": "PENDING_SME_REVIEW",
        "latency_ms": 180,
        "reason": "Tier 1 requires human SME review"
    },
    "elevated_pass": {
        "query": "Update risk policy for credit department",
        "tier": 2,
        "status": "PASS",
        "latency_ms": 200,
        "reason": "AI audit passed - compliant with policy"
    },
    "elevated_fail": {
        "query": "Increase credit limit without verifying income",
        "tier": 2,
        "status": "BLOCKED",
        "latency_ms": 210,
        "reason": "AI audit failed - income verification required"
    }
}


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard page"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>MAIA PVI Airlock Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Segoe UI', system-ui, sans-serif; 
            background: #0a0a0f; 
            color: #e0e0e0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 20px 40px;
            border-bottom: 1px solid #2a2a4a;
        }
        .header h1 { 
            color: #00d4ff; 
            font-size: 28px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .header .badge {
            background: #00d4ff;
            color: #000;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        
        /* Metrics Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: #12121a;
            border: 1px solid #2a2a4a;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }
        .metric-card.passed { border-left: 4px solid #00ff88; }
        .metric-card.blocked { border-left: 4px solid #ff4444; }
        .metric-card.pending { border-left: 4px solid #ffaa00; }
        .metric-value { 
            font-size: 36px; 
            font-weight: bold;
            margin-bottom: 5px;
        }
        .metric-label { 
            color: #888; 
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        /* Charts Row */
        .charts-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }
        .chart-card {
            background: #12121a;
            border: 1px solid #2a2a4a;
            border-radius: 12px;
            padding: 20px;
        }
        .chart-title {
            color: #00d4ff;
            font-size: 16px;
            margin-bottom: 15px;
            font-weight: 600;
        }
        .bar-chart { display: flex; flex-direction: column; gap: 10px; }
        .bar-row { display: flex; align-items: center; gap: 10px; }
        .bar-label { width: 80px; font-size: 14px; color: #888; }
        .bar-container { flex: 1; background: #1a1a2e; height: 24px; border-radius: 4px; overflow: hidden; }
        .bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
        .bar-value { width: 50px; text-align: right; font-size: 14px; }
        
        /* Test Controls */
        .controls-card {
            background: #12121a;
            border: 1px solid #2a2a4a;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
        }
        .controls-title {
            color: #00d4ff;
            font-size: 16px;
            margin-bottom: 15px;
            font-weight: 600;
        }
        .button-group {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 14px;
        }
        .btn-pass { background: #00ff88; color: #000; }
        .btn-pass:hover { background: #00cc6a; }
        .btn-fail { background: #ff4444; color: #fff; }
        .btn-fail:hover { background: #cc3636; }
        .btn-sme { background: #ffaa00; color: #000; }
        .btn-sme:hover { background: #cc8800; }
        .btn-clear { background: #444; color: #fff; }
        .btn-clear:hover { background: #333; }
        
        .btn:active { transform: scale(0.95); }
        
        /* Transactions Table */
        .table-card {
            background: #12121a;
            border: 1px solid #2a2a4a;
            border-radius: 12px;
            padding: 20px;
        }
        .table-title {
            color: #00d4ff;
            font-size: 16px;
            margin-bottom: 15px;
            font-weight: 600;
        }
        table { width: 100%; border-collapse: collapse; }
        th { 
            text-align: left; 
            padding: 12px; 
            color: #888; 
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 1px solid #2a2a4a;
        }
        td { 
            padding: 12px; 
            font-size: 14px;
            border-bottom: 1px solid #1a1a2e;
        }
        .status-badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-pass { background: #00ff8833; color: #00ff88; }
        .status-blocked { background: #ff444433; color: #ff4444; }
        .status-pending { background: #ffaa0033; color: #ffaa00; }
        
        /* SR 26-02 Compliance Banner */
        .compliance-banner {
            background: linear-gradient(90deg, #00d4ff 0%, #0066ff 100%);
            color: #000;
            padding: 15px 20px;
            border-radius: 8px;
            text-align: center;
            font-weight: bold;
            margin-bottom: 20px;
        }
        
        /* Last Updated */
        .last-updated {
            color: #666;
            font-size: 12px;
            text-align: right;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>
            🛡️ MAIA PVI Airlock Dashboard
            <span class="badge">SR 26-02 COMPLIANT</span>
        </h1>
    </div>
    
    <div class="container">
        <div class="compliance-banner">
            Federal Reserve SR 26-02 Compliance Validation Layer
        </div>
        
        <!-- Summary Metrics -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value" id="total-tx">0</div>
                <div class="metric-label">Total Transactions</div>
            </div>
            <div class="metric-card passed">
                <div class="metric-value" id="passed-tx" style="color: #00ff88">0</div>
                <div class="metric-label">Passed</div>
            </div>
            <div class="metric-card blocked">
                <div class="metric-value" id="blocked-tx" style="color: #ff4444">0</div>
                <div class="metric-label">Blocked</div>
            </div>
            <div class="metric-card pending">
                <div class="metric-value" id="pending-tx" style="color: #ffaa00">0</div>
                <div class="metric-label">Pending SME Review</div>
            </div>
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value" id="pass-rate" style="color: #00ff88">0%</div>
                <div class="metric-label">Pass Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="block-rate" style="color: #ff4444">0%</div>
                <div class="metric-label">Block Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="avg-latency" style="color: #00d4ff">0ms</div>
                <div class="metric-label">Avg Latency</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="sme-votes-count" style="color: #ffaa00">0</div>
                <div class="metric-label">SME Votes Cast</div>
            </div>
        </div>
        
        <!-- Charts -->
        <div class="charts-row">
            <div class="chart-card">
                <div class="chart-title">Materiality Tier Distribution</div>
                <div class="bar-chart" id="tier-chart">
                    <!-- Populated by JS -->
                </div>
            </div>
            <div class="chart-card">
                <div class="chart-title">Domain Distribution</div>
                <div class="bar-chart" id="domain-chart">
                    <!-- Populated by JS -->
                </div>
            </div>
        </div>
        
        <!-- Test Controls -->
        <div class="controls-card">
            <div class="controls-title">⚡ Test Scenarios - Simulate PVI Airlock Behavior</div>
            <div class="button-group">
                <button class="btn btn-pass" onclick="runScenario('pass')">✅ PASS Scenario (Tier 3)</button>
                <button class="btn btn-pass" onclick="runScenario('elevated_pass')">✅ PASS Scenario (Tier 2)</button>
                <button class="btn btn-fail" onclick="runScenario('fail')">🚫 FAIL Scenario (Tier 1)</button>
                <button class="btn btn-fail" onclick="runScenario('elevated_fail')">🚫 FAIL Scenario (Tier 2)</button>
                <button class="btn btn-sme" onclick="runScenario('sme_review')">👥 SME Review (Tier 1)</button>
                <button class="btn btn-clear" onclick="clearMetrics()">🗑️ Clear All</button>
            </div>
            <div class="last-updated" id="last-updated">Last updated: --</div>
        </div>
        
        <!-- Transactions Table -->
        <div class="table-card">
            <div class="table-title">📋 Transaction Log</div>
            <table>
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Transaction ID</th>
                        <th>Query</th>
                        <th>Domain</th>
                        <th>Tier</th>
                        <th>Status</th>
                        <th>Latency</th>
                        <th>Reason</th>
                    </tr>
                </thead>
                <tbody id="transactions-body">
                    <!-- Populated by JS -->
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        async function refreshMetrics() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();
                
                // Update summary
                document.getElementById('total-tx').textContent = data.summary.total_transactions;
                document.getElementById('passed-tx').textContent = data.summary.passed;
                document.getElementById('blocked-tx').textContent = data.summary.blocked;
                document.getElementById('pending-tx').textContent = data.summary.pending_sme;
                document.getElementById('pass-rate').textContent = data.summary.pass_rate;
                document.getElementById('block-rate').textContent = data.summary.block_rate;
                document.getElementById('avg-latency').textContent = data.summary.avg_latency_ms + 'ms';
                document.getElementById('sme-votes-count').textContent = data.sme_votes;
                
                // Update tier chart
                const tierChart = document.getElementById('tier-chart');
                const tierData = data.summary.tier_distribution;
                const tierColors = {'1': '#ff4444', '2': '#ffaa00', '3': '#00ff88'};
                tierChart.innerHTML = '';
                for (const [tier, count] of Object.entries(tierData)) {
                    const pct = data.summary.total_transactions > 0 ? (count / data.summary.total_transactions * 100) : 0;
                    tierChart.innerHTML += `
                        <div class="bar-row">
                            <div class="bar-label">Tier ${tier}</div>
                            <div class="bar-container">
                                <div class="bar-fill" style="width: ${pct}%; background: ${tierColors[tier]}"></div>
                            </div>
                            <div class="bar-value">${count}</div>
                        </div>
                    `;
                }
                
                // Update domain chart
                const domainChart = document.getElementById('domain-chart');
                const domainData = data.summary.domain_distribution;
                domainChart.innerHTML = '';
                for (const [domain, count] of Object.entries(domainData)) {
                    const pct = data.summary.total_transactions > 0 ? (count / data.summary.total_transactions * 100) : 0;
                    domainChart.innerHTML += `
                        <div class="bar-row">
                            <div class="bar-label">${domain}</div>
                            <div class="bar-container">
                                <div class="bar-fill" style="width: ${pct}%; background: #00d4ff"></div>
                            </div>
                            <div class="bar-value">${count}</div>
                        </div>
                    `;
                }
                
                // Update transactions table
                const tbody = document.getElementById('transactions-body');
                tbody.innerHTML = '';
                for (const tx of data.transactions.slice(0, 20)) {
                    let statusClass = 'status-pass';
                    if (tx.status === 'BLOCKED') statusClass = 'status-blocked';
                    if (tx.status === 'PENDING_SME_REVIEW') statusClass = 'status-pending';
                    
                    tbody.innerHTML += `
                        <tr>
                            <td>${tx.timestamp.split('T')[1].split('.')[0]}</td>
                            <td><code style="color: #00d4ff">${tx.transaction_id}</code></td>
                            <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;">${tx.query}</td>
                            <td>${tx.domain}</td>
                            <td><span style="color: ${tierColors[tx.materiality_tier]}">Tier ${tx.materiality_tier}</span></td>
                            <td><span class="status-badge ${statusClass}">${tx.status}</span></td>
                            <td>${tx.latency_ms}ms</td>
                            <td style="max-width: 150px; overflow: hidden; text-overflow: ellipsis;">${tx.reason || '-'}</td>
                        </tr>
                    `;
                }
                
                document.getElementById('last-updated').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
            } catch (e) {
                console.error('Failed to refresh metrics:', e);
            }
        }
        
        async function runScenario(scenario) {
            try {
                await fetch('/api/simulate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({scenario: scenario})
                });
                await refreshMetrics();
            } catch (e) {
                console.error('Failed to run scenario:', e);
            }
        }
        
        async function clearMetrics() {
            try {
                await fetch('/api/clear', {method: 'POST'});
                await refreshMetrics();
            } catch (e) {
                console.error('Failed to clear:', e);
            }
        }
        
        // Refresh every 2 seconds
        setInterval(refreshMetrics, 2000);
        refreshMetrics();
    </script>
</body>
</html>
"""


@app.get("/api/metrics")
async def get_metrics():
    """Get current metrics"""
    return {
        "summary": metrics.get_summary(),
        "transactions": metrics.get_transactions(50),
        "sme_votes": len(metrics.sme_votes)
    }


@app.post("/api/simulate")
async def simulate_transaction(req: TransactionRequest):
    """Simulate a transaction with specified scenario"""
    scenario = SCENARIOS.get(req.scenario, SCENARIOS["pass"])
    
    tx = {
        "transaction_id": f"maia-{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now().isoformat(),
        "query": scenario["query"],
        "domain": req.domain,
        "materiality_tier": scenario["tier"],
        "status": scenario["status"],
        "latency_ms": scenario["latency_ms"],
        "reason": scenario["reason"],
        "policy_vetted": "SR 26-02 Section III (Effective Challenge)",
        "latent_hash": uuid.uuid4().hex[:16]
    }
    
    # If SME review scenario, add voting session
    if req.scenario == "sme_review":
        dhitl_id = f"dhitl-{uuid.uuid4().hex[:8]}"
        tx["dhitl_session_id"] = dhitl_id
        tx["sme_votes"] = []
        
        # Simulate SME votes
        for i, sme in enumerate(["sme-001", "sme-002", "sme-003"]):
            vote = {
                "sme_id": sme,
                "vote": "APPROVE" if i < 2 else "REJECT",
                "rationale": "Compliant with SR 26-02" if i < 2 else "Requires additional review",
                "timestamp": datetime.now().isoformat()
            }
            tx["sme_votes"].append(vote)
            metrics.sme_votes.append(vote)
        
        tx["sme_consensus"] = "APPROVED" if tx["sme_votes"].count(v => v["vote"] == "APPROVE") >= 2 else "REJECTED"
    
    metrics.add_transaction(tx)
    
    return {"status": "simulated", "transaction": tx}


@app.post("/api/clear")
async def clear_metrics():
    """Clear all metrics"""
    metrics.clear()
    return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn
    print("Starting MAIA PVI Airlock Dashboard on http://localhost:3033")
    uvicorn.run(app, host="0.0.0.0", port=3033)