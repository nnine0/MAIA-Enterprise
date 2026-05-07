"""
MAIA Testing Dashboard - Client Governance Telemetry
=================================================
Visual dashboard for external API clients to observe Circuit Breaker in action.

Components:
- Reasoning Tube: 3D visualization of latent space paths vs compliance boundaries
- Latent EKG: Real-time graph of logical curvature (PVI Airlock status)
- SME Portal: Mockup of National Oracle app for Tier 1 voting

Run: python3 -m app.testing_dashboard
Access: http://localhost:3034
"""

import json
import uuid
import time
import random
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestingDashboard:
    """Client-facing governance telemetry"""
    
    def __init__(self):
        self.sessions = {}
        self.events = []
        self.current_session = None
        
    def create_session(self, sector: str, role: str) -> str:
        session_id = f"session-{uuid.uuid4().hex[:8]}"
        self.sessions[session_id] = {
            "id": session_id,
            "sector": sector,
            "role": role,
            "created": datetime.now().isoformat(),
            "transactions": [],
            "airlock_status": "GREEN",
            "logical_curvature": [],
            "reasoning_path": [],
            "sme_pending": []
        }
        return session_id
    
    def add_transaction(self, session_id: str, tx: dict):
        if session_id in self.sessions:
            self.sessions[session_id]["transactions"].append(tx)
            self.events.append({
                "session": session_id,
                "timestamp": datetime.now().isoformat(),
                "event": tx
            })
    
    def update_airlock(self, session_id: str, status: str, curvature: float):
        if session_id in self.sessions:
            self.sessions[session_id]["airlock_status"] = status
            self.sessions[session_id]["logical_curvature"].append({
                "time": time.time(),
                "curvature": curvature,
                "status": status
            })
            if len(self.sessions[session_id]["logical_curvature"]) > 100:
                self.sessions[session_id]["logical_curvature"].pop(0)
    
    def add_reasoning_node(self, session_id: str, node: dict):
        if session_id in self.sessions:
            self.sessions[session_id]["reasoning_path"].append(node)
    
    def add_sme_vote(self, session_id: str, tx_id: str, sme_id: str, vote: str):
        if session_id in self.sessions:
            self.sessions[session_id]["sme_pending"].append({
                "tx_id": tx_id,
                "sme_id": sme_id,
                "vote": vote,
                "timestamp": datetime.now().isoformat()
            })
    
    def get_session(self, session_id: str) -> dict:
        return self.sessions.get(session_id)
    
    def get_all_sessions(self) -> list:
        return list(self.sessions.values())


dashboard = TestingDashboard()


DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>MAIA Testing Dashboard - Governance Telemetry</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', system-ui, sans-serif; 
            background: #0a0e14;
            color: #e6edf3;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(90deg, #1a2332 0%, #0d1117 100%);
            padding: 20px 30px;
            border-bottom: 1px solid #30363d;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 24px;
            color: #58a6ff;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .header-badge {
            background: #238636;
            color: #fff;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 20px;
            max-width: 1600px;
            margin: 0 auto;
        }
        .card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            overflow: hidden;
        }
        .card-full {
            grid-column: 1 / -1;
        }
        .card-header {
            background: #21262d;
            padding: 12px 20px;
            border-bottom: 1px solid #30363d;
            font-weight: 600;
            font-size: 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-body {
            padding: 20px;
            min-height: 250px;
        }
        .airlock-status {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 14px;
        }
        .airlock-green {
            background: rgba(35, 134, 54, 0.2);
            color: #3fb950;
            border: 1px solid #238636;
        }
        .airlock-yellow {
            background: rgba(187, 128, 9, 0.2);
            color: #d29922;
            border: 1px solid #bb8009;
        }
        .airlock-red {
            background: rgba(218, 54, 51, 0.2);
            color: #f85149;
            border: 1px solid #da3633;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        .reasoning-node {
            display: inline-block;
            padding: 6px 14px;
            margin: 4px;
            border-radius: 4px;
            font-size: 12px;
            background: #21262d;
            border: 1px solid #30363d;
            color: #8b949e;
        }
        .reasoning-node.active {
            background: rgba(88, 166, 255, 0.15);
            border-color: #58a6ff;
            color: #58a6ff;
        }
        .reasoning-node.blocked {
            background: rgba(248, 81, 73, 0.15);
            border-color: #f85149;
            color: #f85149;
        }
        .boundaries {
            position: absolute;
            right: 20px;
            top: 20px;
            font-size: 11px;
            color: #8b949e;
        }
        .reasoning-tube {
            position: relative;
            height: 200px;
            background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
            border-radius: 8px;
            overflow: hidden;
        }
        .compliance-boundary {
            position: absolute;
            left: 0;
            right: 0;
            height: 2px;
            background: repeating-linear-gradient(
                90deg,
                #f85149 0px,
                #f85149 10px,
                transparent 10px,
                transparent 20px
            );
        }
        .compliance-boundary.top { top: 30%; }
        .compliance-boundary.bottom { bottom: 30%; }
        .reasoning-path {
            position: absolute;
            left: 10px;
            right: 10px;
            height: calc(100% - 60px);
            top: 30px;
        }
        .path-point {
            position: absolute;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #58a6ff;
            border: 2px solid #0d1117;
            transform: translate(-50%, -50%);
            transition: all 0.3s ease;
        }
        .path-point.blocked {
            background: #f85149;
            box-shadow: 0 0 10px #f85149;
        }
        .path-line {
            position: absolute;
            background: #58a6ff;
            height: 2px;
            transform-origin: left center;
            opacity: 0.6;
        }
        .sme-card {
            background: #21262d;
            border-radius: 6px;
            padding: 16px;
            margin: 8px 0;
            border: 1px solid #30363d;
        }
        .sme-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        .sme-id {
            font-weight: 600;
            color: #58a6ff;
        }
        .sme-tx {
            font-size: 12px;
            color: #8b949e;
        }
        .sme-vote {
            display: flex;
            gap: 10px;
        }
        .vote-btn {
            padding: 8px 20px;
            border-radius: 6px;
            border: none;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .vote-approve {
            background: #238636;
            color: #fff;
        }
        .vote-approve:hover { background: #2ea043; }
        .vote-reject {
            background: #da3633;
            color: #fff;
        }
        .vote-reject:hover { background: #f85149; }
        .vote-pending {
            background: #30363d;
            color: #8b949e;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
        }
        .stat-box {
            background: #21262d;
            border-radius: 8px;
            padding: 16px;
            text-align: center;
        }
        .stat-value {
            font-size: 28px;
            font-weight: 700;
            color: #58a6ff;
        }
        .stat-label {
            font-size: 12px;
            color: #8b949e;
            margin-top: 4px;
        }
        .log-entry {
            font-family: 'Consolas', monospace;
            font-size: 12px;
            padding: 8px 12px;
            border-bottom: 1px solid #21262d;
            display: flex;
            gap: 16px;
        }
        .log-time { color: #8b949e; }
        .log-status { font-weight: 600; }
        .log-status.passed { color: #3fb950; }
        .log-status.blocked { color: #f85149; }
        .log-status.certified { color: #58a6ff; }
        .log-status.escalated { color: #d29922; }
        canvas {
            width: 100% !important;
            height: 200px !important;
        }
        .form-group {
            margin-bottom: 16px;
        }
        .form-group label {
            display: block;
            margin-bottom: 6px;
            font-size: 13px;
            color: #8b949e;
        }
        .form-group select,
        .form-group input {
            width: 100%;
            padding: 10px 14px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #e6edf3;
            font-size: 14px;
        }
        .form-group select:focus,
        .form-group input:focus {
            outline: none;
            border-color: #58a6ff;
        }
        .btn {
            padding: 10px 24px;
            background: #238636;
            color: #fff;
            border: none;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            font-size: 14px;
        }
        .btn:hover { background: #2ea043; }
    </style>
</head>
<body>
    <div class="header">
        <h1>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            MAIA Testing Dashboard
            <span class="header-badge">SANDBOX</span>
        </h1>
        <div id="session-info"></div>
    </div>
    
    <div class="grid">
        <div class="card">
            <div class="card-header">
                <span>The Reasoning Tube</span>
                <span style="font-size:11px;color:#8b949e">Latent Space Visualization</span>
            </div>
            <div class="card-body">
                <div class="reasoning-tube" id="reasoning-tube">
                    <div class="compliance-boundary top"></div>
                    <div class="compliance-boundary bottom"></div>
                    <div class="reasoning-path" id="path-canvas"></div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <span>The Latent EKG</span>
                <span style="font-size:11px;color:#8b949e">Logical Curvature</span>
            </div>
            <div class="card-body">
                <canvas id="ekg-chart"></canvas>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <span>PVI Airlock Status</span>
                <div id="airlock-badge" class="airlock-status airlock-green">
                    <span id="airlock-icon">●</span>
                    <span id="airlock-text">SECURE</span>
                </div>
            </div>
            <div class="card-body">
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="stat-value" id="stat-passed">0</div>
                        <div class="stat-label">Passed</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" id="stat-blocked">0</div>
                        <div class="stat-label">Blocked</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" id="stat-escalated">0</div>
                        <div class="stat-label">Escalated</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" id="stat-pending">0</div>
                        <div class="stat-label">SME Pending</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <span>The SME Portal</span>
                <span style="font-size:11px;color:#8b949e">National Oracle</span>
            </div>
            <div class="card-body" id="sme-portal">
                <div class="sme-card vote-pending">
                    <div class="sme-header">
                        <span class="sme-id">No pending votes</span>
                    </div>
                    <div style="color:#8b949e;font-size:12px">
                        Tier 1 transactions requiring SME consensus will appear here
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card card-full">
            <div class="card-header">
                <span>Transaction Log</span>
                <span style="font-size:11px;color:#8b949e">Real-time</span>
            </div>
            <div class="card-body" id="tx-log" style="max-height: 250px; overflow-y: auto;">
            </div>
        </div>
    </div>
    
    <script>
        let currentSession = null;
        let ekgChart = null;
        let txCount = { passed: 0, blocked: 0, escalated: 0 };
        
        // Initialize session
        function initSession() {
            currentSession = 'session-' + Math.random().toString(36).substr(2, 8);
            document.getElementById('session-info').innerHTML = 
                '<span style="color:#8b949e;font-size:12px">Session: </span>' + 
                '<span style="color:#58a6ff">' + currentSession + '</span>';
            initChart();
        }
        
        // Initialize EKG chart
        function initChart() {
            const ctx = document.getElementById('ekg-chart').getContext('2d');
            ekgChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Logical Curvature',
                        data: [],
                        borderColor: '#58a6ff',
                        backgroundColor: 'rgba(88, 166, 255, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { display: false },
                        y: { 
                            min: 0, 
                            max: 100,
                            grid: { color: '#21262d' },
                            ticks: { color: '#8b949e' }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }
        
        // Simulate test transaction
        async function runTestTransaction() {
            const instructions = [
                "Evaluate $50k credit line risk",
                "Check OFAC compliance for wire transfer",
                "Verify OSHA safety for construction site",
                "Assess HIPAA privacy for patient record",
                "Process insurance claim over $10k"
            ];
            
            const instruction = instructions[Math.floor(Math.random() * instructions.length)];
            const sector = document.getElementById('sector-select')?.value || 'finance_insurance';
            const role = document.getElementById('role-select')?.value || 'loan_officer';
            
            // Show reasoning path forming
            updateReasoningPath(instruction, 'active');
            
            // Simulate 150ms Airlock check
            await sleep(150);
            
            // Random outcome (weighted)
            const rand = Math.random();
            let status, statusText, statusClass;
            
            if (rand < 0.6) {
                status = 'CERTIFIED';
                statusText = 'CERTIFIED';
                statusClass = 'certified';
                txCount.passed++;
                updateAirlock('GREEN', 20 + Math.random() * 30);
            } else if (rand < 0.8) {
                status = 'BLOCKED';
                statusText = 'BLOCKED';
                statusClass = 'blocked';
                txCount.blocked++;
                updateAirlock('RED', 80 + Math.random() * 20);
            } else {
                status = 'ESCALATED';
                statusText = 'SME REVIEW';
                statusClass = 'escalated';
                txCount.escalated++;
                updateAirlock('YELLOW', 50 + Math.random() * 20);
                addSMEVote(instruction);
            }
            
            // Update EKG
            const curvature = status === 'BLOCKED' ? 85 + Math.random() * 15 : 
                           status === 'ESCALATED' ? 50 + Math.random() * 20 : 
                           20 + Math.random() * 30;
            ekgChart.data.labels.push(new Date().toLocaleTimeString());
            ekgChart.data.datasets[0].data.push(curvature);
            if (ekgChart.data.labels.length > 20) {
                ekgChart.data.labels.shift();
                ekgChart.data.datasets[0].data.shift();
            }
            ekgChart.update();
            
            // Update stats
            document.getElementById('stat-passed').textContent = txCount.passed;
            document.getElementById('stat-blocked').textContent = txCount.blocked;
            document.getElementById('stat-escalated').textContent = txCount.escalated;
            
            // Add log entry
            addLogEntry(instruction, statusText, statusClass);
            
            // Show final path node
            updateReasoningPath(instruction, status === 'BLOCKED' ? 'blocked' : 'completed');
        }
        
        function updateReasoningPath(instruction, state) {
            const container = document.getElementById('path-canvas');
            const node = document.createElement('div');
            node.className = 'path-point ' + (state === 'blocked' ? 'blocked' : '');
            node.style.left = (20 + Math.random() * 60) + '%';
            node.style.top = (20 + Math.random() * 60) + '%';
            container.appendChild(node);
            
            if (container.children.length > 15) {
                container.removeChild(container.firstChild);
            }
        }
        
        function updateAirlock(status, curvature) {
            const badge = document.getElementById('airlock-badge');
            const icon = document.getElementById('airlock-icon');
            const text = document.getElementById('airlock-text');
            
            badge.className = 'airlock-status airlock-' + 
                (status === 'GREEN' ? 'green' : status === 'YELLOW' ? 'yellow' : 'red');
            text.textContent = status === 'GREEN' ? 'SECURE' : status === 'YELLOW' ? 'WARNING' : 'TRIPPED';
        }
        
        function addSMEVote(instruction) {
            const portal = document.getElementById('sme-portal');
            const card = document.createElement('div');
            card.className = 'sme-card';
            card.innerHTML = `
                <div class="sme-header">
                    <span class="sme-id">SME-${Math.floor(Math.random() * 900) + 100}</span>
                    <span style="color:#d29922">PENDING</span>
                </div>
                <div class="sme-tx">${instruction.substring(0, 50)}...</div>
                <div class="sme-vote" style="margin-top:12px">
                    <button class="vote-btn vote-approve" onclick="this.parentElement.parentElement.remove()">APPROVE</button>
                    <button class="vote-btn vote-reject" onclick="this.parentElement.parentElement.remove()">REJECT</button>
                </div>
            `;
            portal.insertBefore(card, portal.firstChild);
            document.getElementById('stat-pending').textContent = portal.children.length;
        }
        
        function addLogEntry(instruction, status, statusClass) {
            const log = document.getElementById('tx-log');
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.innerHTML = `
                <span class="log-time">${new Date().toLocaleTimeString()}</span>
                <span class="log-status ${statusClass}">${status}</span>
                <span>${instruction.substring(0, 60)}...</span>
            `;
            log.insertBefore(entry, log.firstChild);
            if (log.children.length > 20) {
                log.removeChild(log.lastChild);
            }
        }
        
        function sleep(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
        
        // Auto-run transactions
        function startAutoRun() {
            initSession();
            setInterval(runTestTransaction, 2000);
        }
        
        startAutoRun();
    </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/" or parsed.path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        elif parsed.path == "/api/session":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            session = dashboard.create_session(
                parsed.query.get("sector", "finance_insurance"),
                parsed.query.get("role", "loan_officer")
            )
            self.wfile.write(json.dumps({"session": session}).encode())
        elif parsed.path == "/api/events":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(dashboard.events[-50:]).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass


def run_dashboard(port=3034):
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"MAIA Testing Dashboard: http://localhost:{port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3034)
    args = parser.parse_args()
    run_dashboard(args.port)