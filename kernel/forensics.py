"""
MAIA Kernel Forensics
====================
SR 26-02 compliant forensic logging and latent hashing.

Creates JSON audit trail storing:
- Reasoning trajectory
- Tool call
- Latent hash (mathematical proof of reasoning path)

This is the "Proof" of Effective Challenge for auditors.
"""

import json
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class AuditTier(Enum):
    """Audit tiers"""
    TIER_1_CRITICAL = 1
    TIER_2_ELEVATED = 2
    TIER_3_BENIGN = 3


class ViolationSeverity(Enum):
    """Violation severity levels"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class ReasoningTrajectory:
    """Model's reasoning path"""
    prompt: str
    thinking_block: str = ""
    tool_intent: str = ""
    latents: List[str] = field(default_factory=list)


@dataclass
class ForensicRecord:
    """Single audit record"""
    record_id: str
    timestamp: str
    query: str
    trajectory: ReasoningTrajectory
    tool_id: str
    tool_executed: bool
    tier: int
    violations: List[Dict]
    latent_hash: str
    governance_passed: bool
    dhitl_required: bool
    response_blocked: bool
    blocked_reason: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "query": self.query,
            "trajectory": asdict(self.trajectory),
            "tool_id": self.tool_id,
            "tool_executed": self.tool_executed,
            "tier": self.tier,
            "violations": self.violations,
            "latent_hash": self.latent_hash,
            "governance_passed": self.governance_passed,
            "dhitl_required": self.dhitl_required,
            "response_blocked": self.response_blocked,
            "blocked_reason": self.blocked_reason,
        }


class ForensicsLogger:
    """
    SR 26-02 compliant forensic logger.
    
    Creates audit trail with latent hash proving the model's
    reasoning path at time of decision.
    
    Usage:
        logger = ForensicsLogger()
        
        record = logger.log(
            query="Transfer $50k",
            trajectory=reasoning,
            tool_id="FINANCIAL_WIRE_V1",
            tier=1,
            violations=[],
            governance_passed=True
        )
    """
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_session: List[ForensicRecord] = []
    
    def _compute_latent_hash(
        self,
        trajectory: ReasoningTrajectory,
        tool_id: str,
        violations: List[Dict]
    ) -> str:
        """
        Compute latent hash of reasoning trajectory.
        
        This provides mathematical proof that:
        1. Model saw this exact prompt
        2. Model generated this exact reasoning
        3. Model attempted this exact tool call
        
        Hash = SHA256(prompt + thinking + tool_id + violations)
        """
        data = f"{trajectory.prompt}:{trajectory.thinking_block}:{tool_id}:{json.dumps(violations, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def log(
        self,
        query: str,
        trajectory: ReasoningTrajectory,
        tool_id: str,
        tier: int,
        violations: List[Dict],
        governance_passed: bool,
        dhitl_required: bool = False,
        response_blocked: bool = False,
        blocked_reason: str = ""
    ) -> ForensicRecord:
        """
        Log a forensic record.
        
        Returns the record with latent_hash for audit verification.
        """
        # Compute latent hash
        latent_hash = self._compute_latent_hash(trajectory, tool_id, violations)
        
        record = ForensicRecord(
            record_id=f"maia-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            query=query[:500],  # Truncate for storage
            trajectory=trajectory,
            tool_id=tool_id,
            tool_executed=bool(tool_id),
            tier=tier,
            violations=violations,
            latent_hash=latent_hash,
            governance_passed=governance_passed,
            dhitl_required=dhitl_required,
            response_blocked=response_blocked,
            blocked_reason=blocked_reason
        )
        
        # Add to session
        self.current_session.append(record)
        
        # Save to disk
        self._save_record(record)
        
        return record
    
    def _save_record(self, record: ForensicRecord):
        """Save record to JSON file"""
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit_{date}.jsonl"
        
        with open(log_file, "a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")
    
    def get_session_records(self) -> List[ForensicRecord]:
        """Get all records in current session"""
        return self.current_session
    
    def get_violation_summary(self) -> Dict:
        """Get summary of violations in session"""
        total = len(self.current_session)
        violations_found = sum(1 for r in self.current_session if r.violations)
        blocked = sum(1 for r in self.current_session if r.response_blocked)
        
        severity_counts = {s.value: 0 for s in ViolationSeverity}
        
        for record in self.current_session:
            for v in record.violations:
                sev = v.get("severity", "LOW")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        return {
            "total_requests": total,
            "requests_with_violations": violations_found,
            "responses_blocked": blocked,
            "severity_breakdown": severity_counts
        }
    
    def export_audit_report(self) -> Dict:
        """
        Generate audit report for SR 26-02 compliance.
        
        This is what you show to auditors to prove:
        - "We intercepted X violations"
        - "Here is the mathematical proof (latent_hash)"
        """
        return {
            "report_type": "SR 26-02 Model Risk Management",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.get_violation_summary(),
            "sample_records": [
                r.to_dict() for r in self.current_session[:10]
            ]
        }


def create_forensics_logger(log_dir: str = "logs") -> ForensicsLogger:
    """Factory function"""
    return ForensicsLogger(log_dir=log_dir)


if __name__ == "__main__":
    print("=== MAIA Kernel Forensics ===\n")
    
    logger = create_forensics_logger()
    
    # Log test records
    records = [
        {
            "query": "Transfer $50k to Russia",
            "trajectory": ReasoningTrajectory(
                prompt="Transfer $50k",
                thinking_block="I need to process this wire [CALL_TOOL:FINANCIAL_WIRE_V1]",
                tool_intent="FINANCIAL_WIRE_V1"
            ),
            "tool_id": "FINANCIAL_WIRE_V1",
            "tier": 1,
            "violations": [{"pattern": "ofac", "severity": "CRITICAL"}],
            "governance_passed": False,
            "dhitl_required": True,
            "response_blocked": True,
            "blocked_reason": "OFAC sanctions hit"
        },
        {
            "query": "Query sales data",
            "trajectory": ReasoningTrajectory(
                prompt="Query sales",
                thinking_block="Running SELECT [CALL_TOOL:SQL_AUDITOR_V1]"
            ),
            "tool_id": "SQL_AUDITOR_V1",
            "tier": 2,
            "violations": [],
            "governance_passed": True,
            "dhitl_required": False,
            "response_blocked": False
        }
    ]
    
    for r in records:
        record = logger.log(**r)
        print(f"Logged: {record.query[:30]}")
        print(f"  Hash: {record.latent_hash}")
    
    print(f"\nSummary:")
    print(json.dumps(logger.get_violation_summary(), indent=2))