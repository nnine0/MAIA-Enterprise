"""
Compliance Logger

Intercepts governance decisions and writes structured JSON to audit log.
Implements the "Paper Trail" for SR 26-02 Effective Challenge verification.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum


class AuditEventType(Enum):
    AIRLOCK_INTERCEPT = "AIRLOCK_INTERCEPT"
    MATERIALITY_CLASSIFY = "MATERIALITY_CLASSIFY"
    AUDITOR_VERDICT = "AUDITOR_VERDICT"
    DHITL_ESCALATION = "DHITL_ESCALATION"
    ADAPTER_LOAD = "ADAPTER_LOAD"
    TRAJECTORY_LOG = "TRAJECTORY_LOG"


class VerdictType(Enum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    PENDING_REVIEW = "PENDING_REVIEW"


@dataclass
class AuditEvent:
    event_id: str
    timestamp: str
    event_type: str
    transaction_id: str
    adapter_id: Optional[str] = None
    materiality_tier: Optional[int] = None
    query_hash: Optional[str] = None
    verdict: Optional[str] = None
    actor_response: Optional[str] = None
    auditor_response: Optional[str] = None
    latent_hash: Optional[str] = None
    classification_audit_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ComplianceLogger:
    """
    Structured audit logger for SR 26-02 compliance.
    
    Writes JSON events to immutable audit log file.
    Provides verifiable paper trail for regulatory review.
    """
    
    def __init__(self, log_path: str = "audit_logs/compliance.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._event_buffer: List[AuditEvent] = []
        self._buffer_size = 10
    
    def _generate_id(self) -> str:
        return str(uuid.uuid4())[:12]
    
    def _hash_query(self, query: str) -> str:
        import hashlib
        return hashlib.sha256(query.encode()).hexdigest()[:16]
    
    def log_airlock_intercept(
        self,
        transaction_id: str,
        query: str,
        adapter_id: str,
        materiality_tier: int,
        actor_response: str,
        auditor_response: str,
        verdict: str,
        latent_hash: Optional[str] = None,
        classification_audit_hash: Optional[str] = None
    ) -> AuditEvent:
        """Log PVI Airlock intercept event."""
        event = AuditEvent(
            event_id=self._generate_id(),
            timestamp=datetime.utcnow().isoformat(),
            event_type=AuditEventType.AIRLOCK_INTERCEPT.value,
            transaction_id=transaction_id,
            adapter_id=adapter_id,
            materiality_tier=materiality_tier,
            query_hash=self._hash_query(query),
            verdict=verdict,
            actor_response=actor_response[:200] if actor_response else None,
            auditor_response=auditor_response[:200] if auditor_response else None,
            latent_hash=latent_hash,
            classification_audit_hash=classification_audit_hash,
            metadata={
                "query_preview": query[:100],
                "response_length": len(actor_response) if actor_response else 0
            }
        )
        self._emit(event)
        return event
    
    def log_materiality_classify(
        self,
        transaction_id: str,
        query: str,
        tier: int,
        matched_keywords: List[str],
        registry_version: str
    ) -> AuditEvent:
        """Log Materiality Matrix classification event."""
        event = AuditEvent(
            event_id=self._generate_id(),
            timestamp=datetime.utcnow().isoformat(),
            event_type=AuditEventType.MATERIALITY_CLASSIFY.value,
            transaction_id=transaction_id,
            query_hash=self._hash_query(query),
            materiality_tier=tier,
            metadata={
                "matched_keywords": matched_keywords,
                "registry_version": registry_version
            }
        )
        self._emit(event)
        return event
    
    def log_auditor_verdict(
        self,
        transaction_id: str,
        adapter_id: str,
        verdict: str,
        reasoning: str,
        requires_dhitl: bool
    ) -> AuditEvent:
        """Log Auditor verdict event."""
        event = AuditEvent(
            event_id=self._generate_id(),
            timestamp=datetime.utcnow().isoformat(),
            event_type=AuditEventType.AUDITOR_VERDICT.value,
            transaction_id=transaction_id,
            adapter_id=adapter_id,
            verdict=verdict,
            auditor_response=reasoning[:200] if reasoning else None,
            metadata={
                "requires_dhitl": requires_dhitl,
                "reasoning_length": len(reasoning) if reasoning else 0
            }
        )
        self._emit(event)
        return event
    
    def log_dhitl_escalation(
        self,
        transaction_id: str,
        adapter_id: str,
        sme_pool_session_id: str,
        vote_threshold: int,
        current_votes: int
    ) -> AuditEvent:
        """Log DHITL escalation event."""
        event = AuditEvent(
            event_id=self._generate_id(),
            timestamp=datetime.utcnow().isoformat(),
            event_type=AuditEventType.DHITL_ESCALATION.value,
            transaction_id=transaction_id,
            adapter_id=adapter_id,
            verdict=VerdictType.PENDING_REVIEW.value,
            metadata={
                "sme_pool_session_id": sme_pool_session_id,
                "vote_threshold": vote_threshold,
                "current_votes": current_votes,
                "status": "awaiting_consensus"
            }
        )
        self._emit(event)
        return event
    
    def log_adapter_load(
        self,
        adapter_id: str,
        adapter_version: str,
        sr26_tier: int,
        conceptual_soundness_version: str
    ) -> AuditEvent:
        """Log adapter load event."""
        event = AuditEvent(
            event_id=self._generate_id(),
            timestamp=datetime.utcnow().isoformat(),
            event_type=AuditEventType.ADAPTER_LOAD.value,
            transaction_id="N/A",
            adapter_id=adapter_id,
            materiality_tier=sr26_tier,
            metadata={
                "adapter_version": adapter_version,
                "conceptual_soundness_version": conceptual_soundness_version,
                "governance_controls": ["PVI Airlock", "Latent Telemetry"]
            }
        )
        self._emit(event)
        return event
    
    def log_trajectory(
        self,
        transaction_id: str,
        query: str,
        adapter_id: str,
        trajectory_steps: List[Dict],
        final_verdict: str
    ) -> AuditEvent:
        """Log full trajectory event."""
        event = AuditEvent(
            event_id=self._generate_id(),
            timestamp=datetime.utcnow().isoformat(),
            event_type=AuditEventType.TRAJECTORY_LOG.value,
            transaction_id=transaction_id,
            adapter_id=adapter_id,
            query_hash=self._hash_query(query),
            verdict=final_verdict,
            metadata={
                "trajectory_steps": trajectory_steps,
                "step_count": len(trajectory_steps)
            }
        )
        self._emit(event)
        return event
    
    def _emit(self, event: AuditEvent):
        """Write event to log file."""
        self._event_buffer.append(event)
        
        if len(self._event_buffer) >= self._buffer_size:
            self._flush()
    
    def _flush(self):
        """Flush buffer to disk."""
        with open(self.log_path, 'a') as f:
            for event in self._event_buffer:
                f.write(json.dumps(asdict(event)) + "\n")
        self._event_buffer.clear()
    
    def flush(self):
        """Explicit flush."""
        if self._event_buffer:
            self._flush()
    
    def get_recent_events(self, count: int = 10) -> List[Dict]:
        """Retrieve recent audit events."""
        if not self.log_path.exists():
            return []
        
        events = []
        with open(self.log_path, 'r') as f:
            for line in f:
                events.append(json.loads(line))
        
        return events[-count:]
    
    def get_transaction_log(self, transaction_id: str) -> List[Dict]:
        """Retrieve all events for a specific transaction."""
        if not self.log_path.exists():
            return []
        
        events = []
        with open(self.log_path, 'r') as f:
            for line in f:
                event = json.loads(line)
                if event.get('transaction_id') == transaction_id:
                    events.append(event)
        
        return events
    
    def generate_audit_report(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
        """Generate summary audit report."""
        if not self.log_path.exists():
            return {"total_events": 0}
        
        events = []
        with open(self.log_path, 'r') as f:
            for line in f:
                events.append(json.loads(line))
        
        event_counts = {}
        tier_counts = {1: 0, 2: 0, 3: 0}
        verdict_counts = {}
        
        for event in events:
            event_type = event.get('event_type', 'UNKNOWN')
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            tier = event.get('materiality_tier')
            if tier:
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
            
            verdict = event.get('verdict')
            if verdict:
                verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        
        return {
            "total_events": len(events),
            "event_types": event_counts,
            "by_materiality_tier": tier_counts,
            "by_verdict": verdict_counts,
            "report_generated": datetime.utcnow().isoformat()
        }


def create_logger(log_path: str = "audit_logs/compliance.jsonl") -> ComplianceLogger:
    """Factory function to create compliance logger."""
    return ComplianceLogger(log_path)


if __name__ == "__main__":
    logger = create_logger()
    
    print("=== Compliance Logger Test ===\n")
    
    event1 = logger.log_materiality_classify(
        transaction_id="tx_001",
        query="What are the tax implications of our merger?",
        tier=1,
        matched_keywords=["merger", "tax"],
        registry_version="1.0.0"
    )
    print(f"Logged materiality: {event1.event_id}")
    
    event2 = logger.log_airlock_intercept(
        transaction_id="tx_001",
        query="What are the tax implications of our merger?",
        adapter_id="law",
        materiality_tier=1,
        actor_response="The tax implications involve...",
        auditor_response="VERDICT: PASS - Complies with regulations",
        verdict="PASS",
        latent_hash="a1b2c3d4e5f6",
        classification_audit_hash="x1y2z3w4v5u6"
    )
    print(f"Logged airlock: {event2.event_id}")
    
    logger.flush()
    
    report = logger.generate_audit_report()
    print("\n=== Audit Report ===")
    for k, v in report.items():
        print(f"  {k}: {v}")