"""
MAIA Kernel - Core Logic (Standalone)
===================================
"""

import hashlib
import uuid
from datetime import datetime
from typing import Optional, Dict, Any


class Verdict:
    CERTIFIED = "CERTIFIED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    PENDING = "PENDING"


class MaterialityTier:
    TIER_1_CRITICAL = 1
    TIER_2_ELEVATED = 2
    TIER_3_BENIGN = 3


class UserContext:
    def __init__(self, sector: str, role: str, materiality_target: str = "tier_2"):
        self.sector = sector
        self.role = role
        self.materiality_target = materiality_target


class AuditResponse:
    def __init__(self, status: str, transaction_id: str, audit_trail: str, tier: int, latency_ms: float,
               output: Optional[str] = None, reason: Optional[str] = None, compliance_log: Optional[Dict[str, Any]] = None):
        self.status = status
        self.transaction_id = transaction_id
        self.audit_trail = audit_trail
        self.tier = tier
        self.latency_ms = latency_ms
        self.output = output
        self.reason = reason
        self.compliance_log = compliance_log


SECTOR_VIOLATIONS = {
    "finance_insurance": ["russia", "iran", "sanction", "structur", "terrorist"],
    "healthcare": ["phi", "patient id", "diagnosis", "medical record"],
    "legal": ["attorney", "privileged", "confidential"],
    "construction": ["fake", "fraud", "bribe", "osha"],
    "energy": ["nerc", "unauthorized", "bypass"],
    "defense": ["classified", "secret", "itar"],
    "logistics": ["hazmat", "explosive", "dot"]
}

ADAPTERS = {
    "finance_insurance": "citi-finance-expert-v4",
    "healthcare": "hipaa-airlock-v1",
    "legal": "legal-contract-redline-v1",
    "construction": "construction-safety-v1",
    "energy": "nerc-cip-compliance",
    "defense": "itars-compliant",
    "logistics": "dot-hazmat-router"
}


class MAIKKernel:
    def __init__(self, mode: str = "sandbox"):
        self.mode = mode
        self.transactions = []
        
    def _compute_hash(self, data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _get_tier(self, target: str) -> int:
        return {"tier_1": 1, "tier_2": 2, "tier_3": 3}.get(target, 2)
    
    def _check_violations(self, text: str, sector: str) -> tuple:
        text_lower = text.lower()
        keywords = SECTOR_VIOLATIONS.get(sector, [])
        for kw in keywords:
            if kw in text_lower:
                return (False, f"Violation: {kw}")
        return (True, None)
    
    async def process(self, instruction: str, context: UserContext, api_key: str) -> AuditResponse:
        start = datetime.now()
        tx_id = f"tx-{uuid.uuid4().hex[:8]}"
        tier = self._get_tier(context.materiality_target)
        
        is_safe, reason = self._check_violations(instruction, context.sector)
        
        if not is_safe:
            return AuditResponse(
                status="BLOCKED",
                transaction_id=tx_id,
                audit_trail=self._compute_hash(f"{tx_id}:BLOCKED"),
                tier=tier,
                latency_ms=150,
                reason=reason
            )
        
        if tier == 1:
            return AuditResponse(
                status="ESCALATED",
                transaction_id=tx_id,
                audit_trail=f"dhitl-{uuid.uuid4().hex[:8]}",
                tier=tier,
                latency_ms=80,
                reason="Tier 1 requires SME consensus"
            )
        
        adapter = ADAPTERS.get(context.sector, "default")
        latency = (datetime.now() - start).total_seconds() * 1000
        
        return AuditResponse(
            status="CERTIFIED",
            transaction_id=tx_id,
            audit_trail=self._compute_hash(f"{tx_id}:CERTIFIED"),
            tier=tier,
            latency_ms=latency,
            output=f"[{adapter}] Processed: {instruction[:50]}...",
            compliance_log={"sector": context.sector, "role": context.role, "adapters": [adapter]}
        )


kernel = MAIKKernel(mode="sandbox")


class RequestValidator:
    @staticmethod
    def validate(key: str) -> bool:
        return len(key) >= 16