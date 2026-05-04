"""
Metrics Service

Real-time metrics for PVI Airlock dashboard
"""

import uuid
import random
from datetime import datetime, timedelta
from typing import List, Dict

from app import config


class MetricsService:
    """In-memory metrics store for dashboard"""
    
    def __init__(self):
        self.transactions: List[Dict] = []
        self.total_passed = 0
        self.total_blocked = 0
        self.total_pending_sme = 0
        self.tier_counts = {"1": 0, "2": 0, "3": 0}
        self.domain_counts: Dict[str, int] = {}
        self.sme_votes: List[Dict] = []
    
    def add(self, tx: Dict):
        """Add transaction to metrics"""
        self.transactions.append(tx)
        
        if tx["status"] in ["PASS", "PASS (BYPASS)"]:
            self.total_passed += 1
        elif tx["status"] == "BLOCKED":
            self.total_blocked += 1
        elif tx["status"] == "PENDING_SME_REVIEW":
            self.total_pending_sme += 1
        
        self.tier_counts[str(tx.get("materiality_tier", 3))] += 1
        domain = tx.get("domain", "unknown")
        self.domain_counts[domain] = self.domain_counts.get(domain, 0) + 1
        
        if "sme_votes" in tx:
            self.sme_votes.extend(tx["sme_votes"])
    
    def clear(self):
        """Reset all metrics"""
        self.transactions = []
        self.total_passed = 0
        self.total_blocked = 0
        self.total_pending_sme = 0
        self.tier_counts = {"1": 0, "2": 0, "3": 0}
        self.domain_counts = {}
        self.sme_votes = []
    
    def get_summary(self) -> Dict:
        """Get metrics summary"""
        total = len(self.transactions)
        return {
            "total_transactions": total,
            "passed": self.total_passed,
            "blocked": self.total_blocked,
            "pending_sme": self.total_pending_sme,
            "pass_rate": f"{(self.total_passed/max(total,1)*100):.1f}%",
            "block_rate": f"{(self.total_blocked/max(total,1)*100):.1f}%",
            "avg_latency_ms": "125",
            "tier_distribution": self.tier_counts,
            "domain_distribution": self.domain_counts
        }
    
    def get_transactions(self, limit: int = 50) -> List[Dict]:
        """Get recent transactions"""
        return sorted(self.transactions, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]


# Scenario definitions for simulation
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
        "tier": 3, "status": "PASS (BYPASS)", "latency_range": (35, 65),
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
        "tier": 2, "status": "PASS", "latency_range": (150, 280),
        "reasons": [
            "AI audit passed - compliant with SR 26-02",
            "All policy checks validated successfully",
            "Risk controls verified - proceeding",
            "Materiality within acceptable thresholds"
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
            "Execute trade without margin requirement"
        ],
        "tier": 1, "status": "BLOCKED", "latency_range": (380, 520),
        "reasons": [
            "SR 26-02 violation: Missing capital reserve",
            "Sanctions compliance check failed",
            "Credit authority exceeded",
            "KYC verification incomplete"
        ]
    },
    "elevated_fail": {
        "queries": [
            "Increase credit limit without income verification",
            "Approve loan with incomplete credit check",
            "Waive late fees for flagged account",
            "Override risk score for high-risk client"
        ],
        "tier": 2, "status": "BLOCKED", "latency_range": (190, 290),
        "reasons": [
            "AI audit failed - income verification required",
            "Credit check incomplete",
            "Risk override requires senior approval"
        ]
    },
    "sme_review": {
        "queries": [
            "Wire $10M to new international correspondent bank",
            "Approve acquisition in regulated market",
            "Issue stand-by letter of credit for $50M",
            "Process restructure for troubled loan",
            "Approve derivatives exposure increase"
        ],
        "tier": 1, "status": "PENDING_SME_REVIEW", "latency_range": (160, 240),
        "reasons": [
            "Tier 1 requires human SME review",
            "New counterparty requires manual approval",
            "Complex transaction needs committee review"
        ]
    }
}


def create_transaction(scenario_key: str, domain: str = "finance") -> Dict:
    """Generate random transaction for scenario"""
    s = SCENARIOS[scenario_key]
    
    # Random timestamp in last 4 hours
    offset = random.randint(0, 4*60*60)
    ts = datetime.now() - timedelta(seconds=offset)
    
    return {
        "transaction_id": f"maia-{uuid.uuid4().hex[:8]}",
        "timestamp": ts.isoformat(),
        "query": random.choice(s["queries"]),
        "domain": domain,
        "materiality_tier": s["tier"],
        "status": s["status"],
        "latency_ms": random.randint(*s["latency_range"]),
        "reason": random.choice(s["reasons"]),
        "policy_vetted": "SR 26-02",
        "latent_hash": uuid.uuid4().hex[:16]
    }


# Global metrics service
metrics = MetricsService()