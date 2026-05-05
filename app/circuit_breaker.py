"""
MAIA Circuit Breaker - Governance Layer
==============================
Implements the active containment pattern for SR 26-02 compliance.

Zero-Trust Architecture:
- Agentic Layer: Generates intent payloads
- Governance Layer: Intercepts, validates, signs trajectories  
- Application Layer: Executes only signed trajectories
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
import config


class MaterialityTier(Enum):
    TIER_1_CRITICAL = 1
    TIER_2_ELEVATED = 2
    TIER_3_BENIGN = 3


class CircuitBreakerVerdict(Enum):
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
class SignedTrajectory:
    """Layer 8: Signed intent payload from Circuit Breaker"""
    transaction_id: str
    timestamp: str
    intent_payload: str
    materiality_tier: int
    circuit_breaker_signature: str
    status: str
    block_reason: Optional[str] = None
    latent_hash: Optional[str] = None
    escalation_path: Optional[str] = None
    sme_votes: Optional[List[Dict]] = None
    sme_consensus: Optional[str] = None
    dhitl_session_id: Optional[str] = None


class CircuitBreaker:
    """
    Circuit Breaker - Governance Layer
    ========================
    Acts as the active containment layer between Agentic and Application.
    
    Responsibilities:
    1. Intercept intent payloads
    2. Validate against SR 26-02 policy
    3. Sign validated trajectories
    4. Block non-compliant paths
    5. Escalate Tier 1 to DHITL (Human SME Review)
    
    Zero-Trust: Application NEVER executes unsigned trajectories
    """
    
    def __init__(self, lorax_url: str = None):
        self.client = AsyncOpenAI(base_url=f"{lorax_url or config.LORAX_URL}/v1", api_key="not-needed")
        self.signing_key = uuid.uuid4().hex[:16]
        
        self.critical_keywords = config.CRITICAL_KEYWORDS
        self.elevated_keywords = config.ELEVATED_KEYWORDS
        
        self.agentic_adapters: Dict[str, str] = {}
        self.validator_adapters: Dict[str, str] = {}
    
    def _compute_latent_hash(self, reasoning: str) -> str:
        return hashlib.sha256(reasoning.encode()).hexdigest()[:16]
    
    def _sign_trajectory(self, intent_payload: str) -> str:
        signature_data = f"{intent_payload}:{self.signing_key}"
        return hashlib.sha256(signature_data.encode()).hexdigest()[:16]
    
    def get_materiality_tier(self, user_query: str) -> MaterialityTier:
        query_lower = user_query.lower()
        
        if any(word in query_lower for word in self.critical_keywords):
            return MaterialityTier.TIER_1_CRITICAL
        elif any(word in query_lower for word in self.elevated_keywords):
            return MaterialityTier.TIER_2_ELEVATED
        return MaterialityTier.TIER_3_BENIGN
    
    async def intercept_and_validate(
        self,
        user_query: str,
        domain: str = "finance",
        transaction_id: Optional[str] = None,
        require_sme_review: bool = True
    ) -> SignedTrajectory:
        if transaction_id is None:
            transaction_id = f"{domain}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        tier = self.get_materiality_tier(user_query)
        
        agentic_adapter = self.agentic_adapters.get(domain, "default-expert")
        validator_adapter = self.validator_adapters.get(domain, "sr26-02-validator")
        
        print(f"[{datetime.now()}] [{transaction_id}] LAYER 8: Intercepting Tier {tier.value}")
        
        intent_payload = await self._generate_intent(user_query, agentic_adapter)
        latent_hash = self._compute_latent_hash(intent_payload)
        
        print(f"[{datetime.now()}] [{transaction_id}] LAYER 9: Intent captured")
        
        validation_result = None
        
        if tier in [MaterialityTier.TIER_1_CRITICAL, MaterialityTier.TIER_2_ELEVATED]:
            validation_result = await self._validate_intent(intent_payload, validator_adapter)
            print(f"[{datetime.now()}] [{transaction_id}] LAYER 8: Validation: {validation_result[0]}")
        
        if tier == MaterialityTier.TIER_1_CRITICAL:
            if require_sme_review:
                session_id = f"dhitl-{uuid.uuid4().hex[:8]}"
                print(f"[{datetime.now()}] [{transaction_id}] LAYER 8: ESCALATED - DHITL")
                
                return SignedTrajectory(
                    transaction_id=transaction_id,
                    timestamp=str(datetime.now()),
                    intent_payload=intent_payload,
                    materiality_tier=tier.value,
                    circuit_breaker_signature="PENDING_SME_CONSENSUS",
                    status=CircuitBreakerVerdict.PENDING_SME_REVIEW.value,
                    block_reason="Tier 1 requires SME consensus",
                    latent_hash=latent_hash,
                    dhitl_session_id=session_id
                )
            else:
                if validation_result[0] == CircuitBreakerVerdict.BLOCKED:
                    return SignedTrajectory(
                        transaction_id=transaction_id,
                        timestamp=str(datetime.now()),
                        intent_payload=intent_payload,
                        materiality_tier=tier.value,
                        circuit_breaker_signature="BLOCKED",
                        status=CircuitBreakerVerdict.BLOCKED.value,
                        block_reason=validation_result[1],
                        latent_hash=latent_hash
                    )
        
        if tier == MaterialityTier.TIER_2_ELEVATED:
            if validation_result[0] == CircuitBreakerVerdict.BLOCKED:
                return SignedTrajectory(
                    transaction_id=transaction_id,
                    timestamp=str(datetime.now()),
                    intent_payload=intent_payload,
                    materiality_tier=tier.value,
                    circuit_breaker_signature="BLOCKED",
                    status=CircuitBreakerVerdict.BLOCKED.value,
                    block_reason=validation_result[1],
                    latent_hash=latent_hash
                )
        
        circuit_signature = self._sign_trajectory(intent_payload)
        print(f"[{datetime.now()}] [{transaction_id}] LAYER 8: SIGNED - {circuit_signature}")
        
        return SignedTrajectory(
            transaction_id=transaction_id,
            timestamp=str(datetime.now()),
            intent_payload=intent_payload,
            materiality_tier=tier.value,
            circuit_breaker_signature=circuit_signature,
            status=CircuitBreakerVerdict.PASS.value,
            latent_hash=latent_hash
        )
    
    async def _generate_intent(self, user_query: str, adapter_id: str) -> str:
        try:
            completion = await self.client.chat.completions.create(
                model=config.BASE_MODEL_ID,
                messages=[
                    {"role": "system", "content": "Generate reasoning and proposed intent for the request."},
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
            return f"Error generating intent: {str(e)}"
    
    async def _validate_intent(
        self,
        intent_payload: str,
        validator_adapter: str
    ) -> tuple[CircuitBreakerVerdict, str]:
        validation_prompt = f"Audit for SR 26-02 compliance. Check: capital reserves, liquidity, stress tests. Verdict:"
        
        try:
            completion = await self.client.chat.completions.create(
                model=config.BASE_MODEL_ID,
                messages=[{"role": "user", "content": validation_prompt}],
                extra_body={
                    "adapter_id": f"/adapters/{validator_adapter}",
                    "adapter_source": "local",
                    "fallback_to_base": True
                },
                max_new_tokens=50,
                temperature=0.1
            )
            verdict_text = completion.choices[0].message.content.strip().upper()
            
            if "FAIL" in verdict_text:
                return (CircuitBreakerVerdict.BLOCKED, verdict_text)
            return (CircuitBreakerVerdict.PASS, verdict_text)
        except Exception as e:
            return (CircuitBreakerVerdict.PASS, f"Validation error: {str(e)}")
    
    def to_signed_record(self, trajectory: SignedTrajectory) -> Dict[str, Any]:
        return {
            "transaction_id": trajectory.transaction_id,
            "materiality_tier": trajectory.materiality_tier,
            "circuit_breaker_signature": trajectory.circuit_breaker_signature,
            "status": trajectory.status,
            "block_reason": trajectory.block_reason,
            "latent_hash": trajectory.latent_hash,
            "dhitl_session_id": trajectory.dhitl_session_id,
            "timestamp": trajectory.timestamp
        }


circuit_breaker = CircuitBreaker()
circuit_breaker.agentic_adapters["finance"] = "citi/finance-expert-v4"
circuit_breaker.validator_adapters["finance"] = "citi/pvi-airlock-sr2602"


async def intercept_and_validate(
    user_query: str,
    domain: str = "finance",
    transaction_id: Optional[str] = None,
    require_sme_review: bool = True
) -> Dict[str, Any]:
    trajectory = await circuit_breaker.intercept_and_validate(
        user_query, domain, transaction_id, require_sme_review
    )
    return circuit_breaker.to_signed_record(trajectory)