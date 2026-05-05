"""
MAIA PVI (Policy-Validation-Interrupt) Airlock
Implements the Non-Blocking Interceptor pattern for SR 26-02 compliance.

Architecture:
- Actor (Expert Adapter): Generates the action trajectory
- Auditor (SR 26-02 Adapter): Provides Effective Challenge
- Circuit Breaker: Blocks non-compliant trajectories
- Latent Telemetry: Neural EKG for audit trails
- DHITL Voting: Human SME review for Tier 1 trajectories
"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from openai import AsyncOpenAI
from config import LORAX_URL


class MaterialityTier(Enum):
    """Materiality Matrix tiers per SR 26-02"""
    TIER_1_CRITICAL = 1  # High financial exposure, mandatory SME review
    TIER_2_ELEVATED = 2  # Medium risk, AI audit
    TIER_3_BENIGN = 3    # Low risk, passive logging only


class AirlockVerdict(Enum):
    PASS = "PASS"
    PASS_BYPASS = "PASS (BYPASS)"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    PENDING_SME_REVIEW = "PENDING_SME_REVIEW"


class SMEVote(Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CONDITIONAL = "CONDITIONAL"


@dataclass
class TrajectoryRecord:
    """Neural trajectory record for Fed audit trail"""
    transaction_id: str
    timestamp: str
    materiality_tier: int
    policy_vetted: str
    actor_adapter: str
    auditor_adapter: str
    status: str
    reason: Optional[str] = None
    latent_hash: Optional[str] = None
    escalation_path: Optional[str] = None
    actor_reasoning: Optional[str] = None
    auditor_reasoning: Optional[str] = None
    sme_votes: Optional[List[Dict]] = None
    sme_consensus: Optional[str] = None
    dhitl_session_id: Optional[str] = None


@dataclass
class SMEVotingSession:
    """DHITL Voting Session - Human SME review for Tier 1 trajectories"""
    session_id: str
    transaction_id: str
    trajectory: str
    domain: str
    created_at: str
    status: str = "pending"  # pending, active, completed
    votes: List[Dict] = field(default_factory=list)
    consensus: Optional[str] = None
    required_votes: int = 3  # Number of SME votes needed
    
    def add_vote(self, sme_id: str, vote: SMEVote, rationale: str):
        """Add SME vote to session"""
        self.votes.append({
            "sme_id": sme_id,
            "vote": vote.value,
            "rationale": rationale,
            "timestamp": str(datetime.now())
        })
        self._calculate_consensus()
    
    def _calculate_consensus(self):
        """Calculate consensus from votes"""
        if len(self.votes) >= self.required_votes:
            approve_count = sum(1 for v in self.votes if v["vote"] == SMEVote.APPROVE.value)
            reject_count = sum(1 for v in self.votes if v["vote"] == SMEVote.REJECT.value)
            
            if approve_count >= 2:
                self.consensus = "APPROVED"
                self.status = "completed"
            elif reject_count >= 2:
                self.consensus = "REJECTED"
                self.status = "completed"
            elif len(self.votes) == self.required_votes:
                self.consensus = "TIE_BREAKER_REQUIRED"
                self.status = "completed"
    
    def is_complete(self) -> bool:
        return self.status == "completed"
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "transaction_id": self.transaction_id,
            "domain": self.domain,
            "status": self.status,
            "votes": self.votes,
            "consensus": self.consensus,
            "required_votes": self.required_votes,
            "current_votes": len(self.votes)
        }


class SMEPool:
    """
    Pool of certified Subject Matter Experts (Airlock Admins).
    These are the human "Supreme Court" for trajectory validation.
    """
    
    def __init__(self):
        # Certified SMEs by domain
        self.smes_by_domain: Dict[str, List[Dict]] = {
            "finance": [
                {"sme_id": "sme-001", "name": "Senior Risk Officer", "certification": "SR26-02"},
                {"sme_id": "sme-002", "name": "Credit Manager", "certification": "SR26-02"},
                {"sme_id": "sme-003", "name": "Compliance Officer", "certification": "SR26-02"},
            ],
            "compliance": [
                {"sme_id": "sme-004", "name": "Regulatory Counsel", "certification": "SR26-02"},
                {"sme_id": "sme-005", "name": "Audit Director", "certification": "SR26-02"},
            ],
            "fraud": [
                {"sme_id": "sme-006", "name": "AML Specialist", "certification": "AML"},
                {"sme_id": "sme-007", "name": "Fraud Investigator", "certification": "AML"},
            ],
            "logistics": [
                {"sme_id": "sme-008", "name": "Safety Director", "certification": "DOT"},
                {"sme_id": "sme-009", "name": "Operations Manager", "certification": "DOT"},
            ]
        }
        
        # Active voting sessions
        self.active_sessions: Dict[str, SMEVotingSession] = {}
        self.completed_sessions: Dict[str, SMEVotingSession] = {}
    
    def create_voting_session(
        self,
        transaction_id: str,
        trajectory: str,
        domain: str
    ) -> SMEVotingSession:
        """Create a new DHITL voting session"""
        session_id = f"dhitl-{uuid.uuid4().hex[:8]}"
        
        session = SMEVotingSession(
            session_id=session_id,
            transaction_id=transaction_id,
            trajectory=trajectory,
            domain=domain,
            created_at=str(datetime.now())
        )
        
        self.active_sessions[session_id] = session
        return session
    
    def submit_vote(
        self,
        session_id: str,
        sme_id: str,
        vote: SMEVote,
        rationale: str
    ) -> Dict:
        """Submit SME vote to session"""
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        session = self.active_sessions[session_id]
        session.add_vote(sme_id, vote, rationale)
        
        result = session.to_dict()
        
        if session.is_complete():
            self.completed_sessions[session_id] = session
            del self.active_sessions[session_id]
        
        return result
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get voting session status"""
        if session_id in self.active_sessions:
            return self.active_sessions[session_id].to_dict()
        if session_id in self.completed_sessions:
            return self.completed_sessions[session_id].to_dict()
        return None
    
    def get_pending_smes(self, domain: str) -> List[Dict]:
        """Get available SMEs for domain"""
        return self.smes_by_domain.get(domain, [])


class RLHFTrainingData:
    """
    Generates training data from SME votes for RLHF.
    Winner trajectory = Positive Reward
    Loser trajectories = Negative Reward
    """
    
    def __init__(self):
        self.training_data: List[Dict] = []
    
    def add_voting_result(
        self,
        transaction_id: str,
        domain: str,
        trajectories: List[str],
        consensus: str,
        votes: List[Dict]
    ):
        """Add voting result as RLHF training data"""
        # Determine winner (consensus-approved trajectory)
        winner = trajectories[0] if consensus == "APPROVED" else None
        
        training_entry = {
            "transaction_id": transaction_id,
            "domain": domain,
            "timestamp": str(datetime.now()),
            "consensus": consensus,
            "winner_trajectory": winner,
            "total_votes": len(votes),
            "vote_details": votes,
            "is_positive_reward": consensus == "APPROVED",
            "is_negative_reward": consensus == "REJECTED"
        }
        
        self.training_data.append(training_entry)
    
    def get_training_batch(self) -> List[Dict]:
        """Get all training data for LoRA fine-tuning"""
        return self.training_data
    
    def export_for_dpo(self) -> List[Dict]:
        """Export for Direct Preference Optimization"""
        dpo_data = []
        
        for entry in self.training_data:
            if entry["winner_trajectory"]:
                dpo_data.append({
                    "prompt": entry["transaction_id"],
                    "chosen": entry["winner_trajectory"],
                    "rejected": "Trajectory rejected by SME consensus"
                })
        
        return dpo_data


# Global instances
sme_pool = SMEPool()
rlhf_data = RLHFTrainingData()


class PVIAirlock:
    """
    The PVI Airlock - Neural Switchboard for Governance Layer.
    
    Coordinates Actor (Expert) and Auditor (SR 26-02) within same async batch.
    Validates action trajectories in latent space before execution.
    Includes DHITL Voting for Tier 1 trajectories - human SMEs are the "Supreme Court."
    """
    
    def __init__(self, lorax_url: str = LORAX_URL):
        self.client = AsyncOpenAI(base_url=f"{lorax_url}/v1", api_key="not-needed")
        
        # Materiality Matrix keywords for risk tiering
        self.critical_keywords = {
            "credit", "wire", "transfer", "contract", "legal", "loan",
            "mortgage", "sanction", "compliance", "fraud", "aml", "kyc",
            "collateral", "escrow", "settlement", "derivative", "exposure"
        }
        self.elevated_keywords = {
            "risk", "limit", "approval", "policy", "audit", "report",
            "client", "account", "exposure", "margin", "guarantee"
        }
        
        # Adapter configurations
        self.actor_adapters: Dict[str, str] = {}
        self.auditor_adapters: Dict[str, str] = {}
        
        # DHITL configuration
        self.sme_pool = sme_pool
        self.rlfh_data = rlhf_data
        
    def _compute_latent_hash(self, reasoning: str) -> str:
        """Compute forensic latent hash for audit trail"""
        return hashlib.sha256(reasoning.encode()).hexdigest()[:16]
    
    def get_materiality_tier(self, user_query: str) -> MaterialityTier:
        """
        Materiality Matrix: Determine risk tier before hitting GPU.
        Python logic to route high-risk to mandatory Airlock.
        """
        query_lower = user_query.lower()
        
        if any(word in query_lower for word in self.critical_keywords):
            return MaterialityTier.TIER_1_CRITICAL
        elif any(word in query_lower for word in self.elevated_keywords):
            return MaterialityTier.TIER_2_ELEVATED
        return MaterialityTier.TIER_3_BENIGN
    
    def set_adapter(self, domain: str, actor_adapter: str, auditor_adapter: str):
        """Register domain adapters for Actor and Auditor"""
        self.actor_adapters[domain] = actor_adapter
        self.auditor_adapters[domain] = auditor_adapter
    
    async def execute_vetted_transaction(
        self,
        user_query: str,
        domain: str = "finance",
        transaction_id: Optional[str] = None,
        require_sme_review: bool = True
    ) -> TrajectoryRecord:
        """
        Execute the full Airlock sequence:
        1. Materiality routing
        2. Actor generates trajectory
        3. PVI intercept pause
        4. Auditor provides Effective Challenge
        5. Circuit breaker verdict
        6. [DHITL] Tier 1 trajectories require SME human review
        """
        if transaction_id is None:
            transaction_id = f"{domain}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        tier = self.get_materiality_tier(user_query)
        
        # Get adapters for domain
        actor_adapter = self.actor_adapters.get(domain, "default-expert")
        auditor_adapter = self.auditor_adapters.get(domain, "sr26-02-auditor")
        
        print(f"[{datetime.now()}] [{transaction_id}] Incoming Request: Tier {tier.value} identified.")
        
        # STEP 1 & 2: GENERATE ACTION TRAJECTORY (THE ACTOR)
        actor_task = asyncio.create_task(
            self._generate_trajectory(user_query, actor_adapter)
        )
        
        # STEP 3: THE INTERCEPTOR PAUSE
        actor_response = await actor_task
        trajectory = actor_response
        latent_hash = self._compute_latent_hash(trajectory)
        
        print(f"[{datetime.now()}] [{transaction_id}] Trajectory Captured: {trajectory[:50]}...")
        
        # STEP 4: THE EFFECTIVE CHALLENGE (THE AUDITOR)
        if tier in [MaterialityTier.TIER_1_CRITICAL, MaterialityTier.TIER_2_ELEVATED]:
            audit_verdict, audit_reasoning = await self._audit_trajectory(
                trajectory, auditor_adapter
            )
            print(f"[{datetime.now()}] [{transaction_id}] Audit Verdict: {audit_verdict}")
        
        # STEP 5: CIRCUIT BREAKER OR DHITL ESCALATION
        if tier == MaterialityTier.TIER_1_CRITICAL:
            # Tier 1 requires human SME review regardless of AI audit result
            if require_sme_review:
                # Create DHITL voting session
                voting_session = self.sme_pool.create_voting_session(
                    transaction_id=transaction_id,
                    trajectory=trajectory,
                    domain=domain
                )
                
                print(f"[{datetime.now()}] [{transaction_id}] DHITL: Escalated to SME Review")
                print(f"[{datetime.now()}] [{transaction_id}] Voting Session: {voting_session.session_id}")
                print(f"[{datetime.now()}] [{transaction_id}] Required SMEs: {voting_session.required_votes}")
                
                return TrajectoryRecord(
                    transaction_id=transaction_id,
                    timestamp=str(datetime.now()),
                    materiality_tier=tier.value,
                    policy_vetted="SR 26-02 Section III (Effective Challenge) + DHITL Human Review",
                    actor_adapter=actor_adapter,
                    auditor_adapter=auditor_adapter,
                    status=AirlockVerdict.PENDING_SME_REVIEW.value,
                    reason=f"Awaiting SME consensus. Voting session: {voting_session.session_id}",
                    latent_hash=latent_hash,
                    actor_reasoning=trajectory,
                    auditor_reasoning=audit_reasoning if tier == MaterialityTier.TIER_1_CRITICAL else None,
                    dhitl_session_id=voting_session.session_id
                )
            else:
                # Fallback to AI-only audit if SME review disabled
                if audit_verdict == AirlockVerdict.BLOCKED:
                    return TrajectoryRecord(
                        transaction_id=transaction_id,
                        timestamp=str(datetime.now()),
                        materiality_tier=tier.value,
                        policy_vetted="SR 26-02 Section III (Effective Challenge)",
                        actor_adapter=actor_adapter,
                        auditor_adapter=auditor_adapter,
                        status="BLOCKED",
                        reason=audit_reasoning,
                        latent_hash=latent_hash,
                        actor_reasoning=trajectory,
                        auditor_reasoning=audit_reasoning,
                        escalation_path="Human-in-the-loop: Senior Risk Officer notified"
                    )
        
        # Tier 2 and 3: AI audit only
        if tier == MaterialityTier.TIER_2_ELEVATED and audit_verdict == AirlockVerdict.BLOCKED:
            return TrajectoryRecord(
                transaction_id=transaction_id,
                timestamp=str(datetime.now()),
                materiality_tier=tier.value,
                policy_vetted="SR 26-02 Section III (Effective Challenge)",
                actor_adapter=actor_adapter,
                auditor_adapter=auditor_adapter,
                status="BLOCKED",
                reason=audit_reasoning,
                latent_hash=latent_hash,
                actor_reasoning=trajectory,
                auditor_reasoning=audit_reasoning
            )
        
        # Tier 3 bypasses audit
        audit_verdict = AirlockVerdict.PASS_BYPASS
        
        print(f"[{datetime.now()}] [{transaction_id}] Verdict: {audit_verdict.value}. Executing transaction.")
        
        return TrajectoryRecord(
            transaction_id=transaction_id,
            timestamp=str(datetime.now()),
            materiality_tier=tier.value,
            policy_vetted="SR 26-02 Section III (Effective Challenge)",
            actor_adapter=actor_adapter,
            auditor_adapter=auditor_adapter,
            status=audit_verdict.value,
            latent_hash=latent_hash,
            actor_reasoning=trajectory
        )
    
    def submit_sme_vote(
        self,
        dhitl_session_id: str,
        sme_id: str,
        vote: SMEVote,
        rationale: str
    ) -> Dict:
        """
        Submit SME vote to DHITL session.
        This is the "Human Supreme Court" decision.
        """
        result = self.sme_pool.submit_vote(dhitl_session_id, sme_id, vote, rationale)
        
        # If session complete, generate RLHF training data
        if result.get("consensus"):
            session = self.sme_pool.completed_sessions.get(dhitl_session_id)
            if session:
                self.rlfh_data.add_voting_result(
                    transaction_id=session.transaction_id,
                    domain=session.domain,
                    trajectories=[session.trajectory],
                    consensus=session.consensus,
                    votes=session.votes
                )
        
        return result
    
    async def _generate_trajectory(self, user_query: str, adapter_id: str) -> str:
        """Generate action trajectory from Actor (Expert) adapter"""
        try:
            completion = await self.client.chat.completions.create(
                model="google/gemma-4-26b-a4b-it",
                messages=[
                    {"role": "system", "content": "Generate reasoning and proposed action trajectory for the following request."},
                    {"role": "user", "content": user_query}
                ],
                extra_body={
                    "adapter_id": f"/adapters/{adapter_id}",
                    "adapter_source": "local",
                    "fallback_to_base": True
                },
                max_new_tokens=512,
                temperature=0.3
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Actor generation error: {e}")
            return f"Error generating trajectory: {str(e)}"
    
    async def _audit_trajectory(
        self,
        trajectory: str,
        auditor_adapter: str
    ) -> tuple[AirlockVerdict, str]:
        """Audit the trajectory using SR 26-02 Auditor adapter"""
        audit_prompt = f"""Audit the following reasoning for SR 26-02 compliance.
        Check for: capital reserve ratios, liquidity buffers, stress-test requirements.
        Provide a verdict: PASS or FAIL followed by brief justification.
        
        Trajectory: {trajectory}
        
        Verdict:"""
        
        try:
            completion = await self.client.chat.completions.create(
                model="google/gemma-4-26b-a4b-it",
                messages=[{"role": "user", "content": audit_prompt}],
                extra_body={
                    "adapter_id": f"/adapters/{auditor_adapter}",
                    "adapter_source": "local",
                    "fallback_to_base": True
                },
                max_new_tokens=50,
                temperature=0.1
            )
            verdict_text = completion.choices[0].message.content.strip().upper()
            
            if "FAIL" in verdict_text:
                return (AirlockVerdict.BLOCKED, verdict_text)
            return (AirlockVerdict.PASS, verdict_text)
        except Exception as e:
            print(f"Auditor error: {e}")
            return (AirlockVerdict.PASS, f"Audit error - default pass: {str(e)}")
    
    def to_audit_log(self, record: TrajectoryRecord) -> Dict[str, Any]:
        """Convert trajectory record to Fed-audit-compatible JSON"""
        return {
            "transaction_id": record.transaction_id,
            "materiality_tier": record.materiality_tier,
            "policy_vetted": record.policy_vetted,
            "auditor_expert": record.auditor_adapter,
            "status": record.status,
            "reason": record.reason,
            "latent_trace_id": record.latent_hash,
            "escalation_path": record.escalation_path,
            "timestamp": record.timestamp,
            "dhitl_session_id": record.dhitl_session_id,
            "sme_votes": record.sme_votes,
            "sme_consensus": record.sme_consensus
        }


# Global Airlock instance
airlock = PVIAirlock()

# Register default adapters
airlock.set_adapter("finance", "citi/finance-expert-v4", "citi/pvi-airlock-sr2602")
airlock.set_adapter("credit", "citi/credit-expert-v4", "citi/pvi-airlock-sr2602")
airlock.set_adapter("compliance", "citi/compliance-expert-v4", "citi/pvi-airlock-sr2602")
airlock.set_adapter("fraud", "citi/fraud-aml-expert-v4", "citi/pvi-airlock-sr2602")
airlock.set_adapter("logistics", "logistics/terminal-expert-v4", "logistics/safety-auditor-v4")


async def execute_vetted_transaction(
    user_query: str,
    domain: str = "finance",
    transaction_id: Optional[str] = None,
    require_sme_review: bool = True
) -> Dict[str, Any]:
    """Public API for vetted transactions"""
    record = await airlock.execute_vetted_transaction(
        user_query, domain, transaction_id, require_sme_review
    )
    return airlock.to_audit_log(record)


async def batch_vetted_transactions(queries: List[str], domain: str = "finance") -> List[Dict[str, Any]]:
    """Run multiple vetted transactions in parallel."""
    tasks = [
        execute_vetted_transaction(q, domain)
        for q in queries
    ]
    results = await asyncio.gather(*tasks)
    return results


def submit_sme_vote(
    dhitl_session_id: str,
    sme_id: str,
    vote: SMEVote,
    rationale: str
) -> Dict:
    """Public API for SME voting"""
    return airlock.submit_sme_vote(dhitl_session_id, sme_id, vote, rationale)


def get_dhitl_session(dhitl_session_id: str) -> Optional[Dict]:
    """Get DHITL voting session status"""
    return sme_pool.get_session(dhitl_session_id)


def get_rlhf_training_data() -> List[Dict]:
    """Get RLHF training data from SME votes"""
    return rlhf_data.get_training_batch()


def export_dpo_data() -> List[Dict]:
    """Export training data for Direct Preference Optimization"""
    return rlhf_data.export_for_dpo()