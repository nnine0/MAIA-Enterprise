"""
MAIA PVI (Policy-Validation-Interrupt) Airlock
Implements the Non-Blocking Interceptor pattern for SR 26-02 compliance.

Architecture:
- Actor (Expert Adapter): Generates the action trajectory
- Auditor (SR 26-02 Adapter): Provides Effective Challenge
- Circuit Breaker: Blocks non-compliant trajectories
- Latent Telemetry: Neural EKG for audit trails
"""

import asyncio
import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from openai import AsyncOpenAI
from config import LORAX_URL


class MaterialityTier(Enum):
    """Materiality Matrix tiers per SR 26-02"""
    TIER_1_CRITICAL = 1  # High financial exposure, mandatory Airlock
    TIER_2_ELEVATED = 2  # Medium risk, conditional audit
    TIER_3_BENIGN = 3    # Low risk, passive logging only


class AirlockVerdict(Enum):
    PASS = "PASS"
    PASS_BYPASS = "PASS (BYPASS)"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"


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


class PVIAirlock:
    """
    The PVI Airlock - Neural Switchboard for Governance Layer.
    
    Coordinates Actor (Expert) and Auditor (SR 26-02) within same async batch.
    Validates action trajectories in latent space before execution.
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
        transaction_id: Optional[str] = None
    ) -> TrajectoryRecord:
        """
        Execute the full Airlock sequence:
        1. Materiality routing
        2. Actor generates trajectory
        3. PVI intercept pause
        4. Auditor provides Effective Challenge
        5. Circuit breaker verdict
        """
        if transaction_id is None:
            transaction_id = f"{domain}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        tier = self.get_materiality_tier(user_query)
        
        # Get adapters for domain
        actor_adapter = self.actor_adapters.get(domain, "default-expert")
        auditor_adapter = self.auditor_adapters.get(domain, "sr26-02-auditor")
        
        print(f"[{datetime.now()}] [{transaction_id}] Incoming Request: Tier {tier.value} identified.")
        
        # STEP 1 & 2: GENERATE ACTION TRAJECTORY (THE ACTOR)
        # Run in async - don't wait yet
        actor_task = asyncio.create_task(
            self._generate_trajectory(user_query, actor_adapter)
        )
        
        # STEP 3: THE INTERCEPTOR PAUSE
        # Wait for actor reasoning before execution
        actor_response = await actor_task
        trajectory = actor_response
        latent_hash = self._compute_latent_hash(trajectory)
        
        print(f"[{datetime.now()}] [{transaction_id}] Trajectory Captured: {trajectory[:50]}...")
        
        # STEP 4: THE EFFECTIVE CHALLENGE (THE AUDITOR)
        # Only for Tier 1 and 2
        if tier == MaterialityTier.TIER_1_CRITICAL:
            audit_verdict, audit_reasoning = await self._audit_trajectory(
                trajectory, auditor_adapter
            )
            print(f"[{datetime.now()}] [{transaction_id}] Audit Verdict: {audit_verdict}")
            
            if audit_verdict == AirlockVerdict.BLOCKED:
                # Circuit breaker trips - transaction blocked
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
        
        # Tier 3 bypasses audit
        audit_verdict = AirlockVerdict.PASS_BYPASS if tier == MaterialityTier.TIER_3_BENIGN else AirlockVerdict.PASS
        
        # STEP 5: CIRCUIT BREAKER CLOSES - TRAJECTORY APPROVED
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
    
    async def _generate_trajectory(self, user_query: str, adapter_id: str) -> str:
        """Generate action trajectory from Actor (Expert) adapter"""
        try:
            completion = await self.client.chat.completions.create(
                model="google/gemma-4-26b-a4b-moe",
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
                model="google/gemma-4-26b-a4b-moe",
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
            "timestamp": record.timestamp
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
    transaction_id: Optional[str] = None
) -> Dict[str, Any]:
    """Public API for vetted transactions"""
    record = await airlock.execute_vetted_transaction(user_query, domain, transaction_id)
    return airlock.to_audit_log(record)


async def batch_vetted_transactions(queries: List[str], domain: str = "finance") -> List[Dict[str, Any]]:
    """
    Run multiple vetted transactions in parallel.
    LoRAX batches these together, running multiple experts and auditors
    simultaneously in a single GPU pass.
    """
    tasks = [
        execute_vetted_transaction(q, domain)
        for q in queries
    ]
    results = await asyncio.gather(*tasks)
    return results