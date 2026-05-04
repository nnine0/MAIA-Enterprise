"""
PVI Airlock Service

Policy-Validation-Interrupt - The compliance gate for SR 26-02
"""

import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from app.models import MaterialityTier, AirlockVerdict, TrajectoryRecord, SMEVote
from app import config


class PVIAirlock:
    """
    PVI Airlock - Policy Validation Interrupt
    
    Coordinates Actor (Expert) and Auditor (SR 26-02) for compliance.
    """
    
    def __init__(self):
        self.critical_keywords = config.CRITICAL_KEYWORDS
        self.elevated_keywords = config.ELEVATED_KEYWORDS
        self.domain_adapters = config.DOMAIN_ADAPTERS
    
    def get_materiality_tier(self, query: str) -> MaterialityTier:
        """Determine risk tier based on query keywords"""
        q = query.lower()
        if any(w in q for w in self.critical_keywords):
            return MaterialityTier.TIER_1_CRITICAL
        elif any(w in q for w in self.elevated_keywords):
            return MaterialityTier.TIER_2_ELEVATED
        return MaterialityTier.TIER_3_BENIGN
    
    def _compute_latent_hash(self, reasoning: str) -> str:
        """Generate forensic latent hash"""
        return hashlib.sha256(reasoning.encode()).hexdigest()[:16]
    
    def get_adapters(self, domain: str) -> Dict[str, str]:
        """Get actor/auditor adapters for domain"""
        return self.domain_adapters.get(domain, self.domain_adapters["finance"])
    
    def create_transaction(
        self,
        query: str,
        domain: str,
        status: str,
        latency_ms: int,
        reason: str,
        require_sme_review: bool = True
    ) -> TrajectoryRecord:
        """Create a transaction record with audit trail"""
        tier = self.get_materiality_tier(query)
        adapters = self.get_adapters(domain)
        tx_id = f"maia-{uuid.uuid4().hex[:8]}"
        
        result = TrajectoryRecord(
            transaction_id=tx_id,
            timestamp=datetime.now().isoformat(),
            materiality_tier=tier.value,
            policy_vetted="SR 26-02 Section III (Effective Challenge)",
            actor_adapter=adapters["actor"],
            auditor_adapter=adapters["auditor"],
            status=status,
            latency_ms=latency_ms,
            reason=reason,
            latent_hash=uuid.uuid4().hex[:16]
        )
        
        # Add SME review for Tier 1
        if require_sme_review and tier == MaterialityTier.TIER_1_CRITICAL:
            result.dhitl_session_id = f"dhitl-{uuid.uuid4().hex[:8]}"
        
        return result
    
    def to_audit_log(self, record: TrajectoryRecord) -> Dict:
        """Convert to Fed-audit format"""
        return {
            "transaction_id": record.transaction_id,
            "materiality_tier": record.materiality_tier,
            "policy_vetted": record.policy_vetted,
            "status": record.status,
            "reason": record.reason,
            "latent_trace_id": record.latent_hash,
            "dhitl_session_id": record.dhitl_session_id,
            "sme_votes": record.sme_votes,
            "sme_consensus": record.sme_consensus,
            "timestamp": record.timestamp
        }


class SMEPool:
    """SME Voting Pool for DHITL"""
    
    def __init__(self):
        self.smes_by_domain = {
            "finance": [
                {"sme_id": "sme-001", "name": "Senior Risk Officer", "cert": "SR26-02"},
                {"sme_id": "sme-002", "name": "Credit Manager", "cert": "SR26-02"},
                {"sme_id": "sme-003", "name": "Compliance Officer", "cert": "SR26-02"},
            ],
            "compliance": [
                {"sme_id": "sme-004", "name": "Regulatory Counsel", "cert": "SR26-02"},
                {"sme_id": "sme-005", "name": "Audit Director", "cert": "SR26-02"},
            ],
            "fraud": [
                {"sme_id": "sme-006", "name": "AML Specialist", "cert": "AML"},
                {"sme_id": "sme-007", "name": "Fraud Investigator", "cert": "AML"},
            ]
        }
        self.sessions: Dict[str, SMEVotingSession] = {}
    
    def create_session(self, tx_id: str, trajectory: str, domain: str) -> str:
        """Create new voting session"""
        session_id = f"dhitl-{uuid.uuid4().hex[:8]}"
        self.sessions[session_id] = SMEVotingSession(
            session_id=session_id,
            transaction_id=tx_id,
            trajectory=trajectory,
            domain=domain,
            created_at=datetime.now().isoformat()
        )
        return session_id
    
    def add_vote(self, session_id: str, sme_id: str, vote: SMEVote, rationale: str) -> bool:
        """Add vote to session"""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        session.votes.append({
            "sme_id": sme_id,
            "vote": vote.value,
            "rationale": rationale,
            "timestamp": datetime.now().isoformat()
        })
        
        # Calculate consensus
        if len(session.votes) >= session.required_votes:
            approve = sum(1 for v in session.votes if v["vote"] == "APPROVE")
            reject = sum(1 for v in session.votes if v["vote"] == "REJECT")
            
            if approve >= 2:
                session.consensus = "APPROVED"
                session.status = "completed"
            elif reject >= 2:
                session.consensus = "REJECTED"
                session.status = "completed"
        
        return True
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session status"""
        if session_id in self.sessions:
            s = self.sessions[session_id]
            return {
                "session_id": s.session_id,
                "transaction_id": s.transaction_id,
                "status": s.status,
                "votes": s.votes,
                "consensus": s.consensus
            }
        return None


class RLHFTrainingData:
    """RLHF training data from SME votes"""
    
    def __init__(self):
        self.data: List[Dict] = []
    
    def add_result(self, tx_id: str, domain: str, consensus: str, votes: List[Dict]):
        """Add voting result as training data"""
        self.data.append({
            "transaction_id": tx_id,
            "domain": domain,
            "timestamp": datetime.now().isoformat(),
            "consensus": consensus,
            "votes": votes,
            "is_positive": consensus == "APPROVED",
            "is_negative": consensus == "REJECTED"
        })
    
    def get_batch(self) -> List[Dict]:
        """Get training batch"""
        return self.data
    
    def export_dpo(self) -> List[Dict]:
        """Export for Direct Preference Optimization"""
        return [
            {"prompt": d["transaction_id"], "chosen": "approved", "rejected": "rejected"}
            for d in self.data if d["is_positive"]
        ]


# Global instances
airlock = PVIAirlock()
sme_pool = SMEPool()
rlhf_data = RLHFTrainingData()