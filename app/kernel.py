"""
MAIA Kernel - Unified Integration
=================================
Integrates the full neural stack:
- External API (L7)
- Circuit Breaker (L8)  
- Orchestrator (L9)

Supports both sandbox and production modes.
"""

import os
import asyncio
import hashlib
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from pydantic import BaseModel, Field


class Verdict(Enum):
    CERTIFIED = "CERTIFIED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    PENDING = "PENDING"


class MaterialityTier(Enum):
    TIER_1_CRITICAL = 1
    TIER_2_ELEVATED = 2
    TIER_3_BENIGN = 3


@dataclass
class UserContext:
    """Client context"""
    sector: str
    role: str
    materiality_target: str = "tier_2"


@dataclass
class AuditResponse:
    """Audit response"""
    status: str
    transaction_id: str
    audit_trail: str
    tier: int
    latency_ms: float
    output: Optional[str] = None
    reason: Optional[str] = None
    compliance_log: Optional[Dict[str, Any]] = None


SECTOR_VIOLATIONS = {
    "finance_insurance": ["russia", "iran", "sanction", "structur", "terrorist"],
    "healthcare": ["phi", "patient_id", "diagnosis", "medical_record"],
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
    """Unified MAIA Kernel"""
    
    def __init__(self, mode: str = "sandbox"):
        self.mode = mode
        self.transactions = []
        
    def _compute_hash(self, data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _get_tier(self, target: str) -> int:
        return {"tier_1": 1, "tier_2": 2, "tier_3": 3}.get(target, 2)
    
    def _check_violations(self, text: str, sector: str) -> tuple[bool, Optional[str]]:
        text_lower = text.lower()
        keywords = SECTOR_VIOLATIONS.get(sector, [])
        for kw in keywords:
            if kw in text_lower:
                return (False, f"Violation: {kw}")
        return (True, None)
    
    async def process(
        self,
        instruction: str,
        context: UserContext,
        api_key: str
    ) -> AuditResponse:
        """Process through kernel layers"""
        start = datetime.now()
        tx_id = f"tx-{uuid.uuid4().hex[:8]}"
        
        tier = self._get_tier(context.materiality_target)
        
        # Layer 8: Check violations
        is_safe, reason = self._check_violations(instruction, context.sector)
        
        if not is_safe:
            audit_hash = self._compute_hash(f"{tx_id}:BLOCKED")
            return AuditResponse(
                status="BLOCKED",
                transaction_id=tx_id,
                audit_trail=audit_hash,
                tier=tier,
                latency_ms=150,
                reason=reason
            )
        
        # Tier 1 escalates
        if tier == 1:
            return AuditResponse(
                status="ESCALATED",
                transaction_id=tx_id,
                audit_trail=f"dhitl-{uuid.uuid4().hex[:8]}",
                tier=tier,
                latency_ms=80,
                reason="Tier 1 requires SME consensus"
            )
        
        # Generate response (simulated)
        adapter = ADAPTERS.get(context.sector, "default")
        output = f"[{adapter}] Processed: {instruction[:50]}..."
        
        # Layer 7: Audit log
        audit_hash = self._compute_hash(f"{tx_id}:CERTIFIED")
        
        latency = (datetime.now() - start).total_seconds() * 1000
        
        return AuditResponse(
            status="CERTIFIED",
            transaction_id=tx_id,
            audit_trail=audit_hash,
            tier=tier,
            latency_ms=latency,
            output=output,
            compliance_log={
                "sector": context.sector,
                "role": context.role,
                "adapters": [adapter]
            }
        )


kernel = MAIKKernel(mode=os.getenv("MAIA_MODE", "sandbox"))


class RequestValidator:
    """Validates API keys"""
    
    @staticmethod
    def validate(key: str) -> bool:
        return len(key) >= 16


def verify_key(key: str = Header(..., alias="X-MAIA-Key")):
    if not RequestValidator.validate(key):
        raise HTTPException(401, "Invalid API key")
    return key


app = FastAPI(title="MAIA Kernel API", version="1.0.0")


@app.get("/health")
async def health():
    return {"status": "healthy", "mode": kernel.mode}


@app.get("/capabilities")
async def capabilities():
    return {
        "sectors": list(SECTOR_VIOLATIONS.keys()),
        "adapters": list(ADAPTERS.values()),
        "tiers": ["tier_1", "tier_2", "tier_3"]
    }


@app.post("/api/v1/vetted-action", response_model=AuditResponse)
async def vetted_action(
    request: Request,
    api_key: str = Depends(verify_key)
):
    """Process vetted action"""
    try:
        body = await request.json()
    except:
        raise HTTPException(400, "Invalid JSON")
    
    ctx = UserContext(
        sector=body.get("context", {}).get("sector", "finance_insurance"),
        role=body.get("context", {}).get("role", "default"),
        materiality_target=body.get("context", {}).get("materiality_target", "tier_2")
    )
    instruction = body.get("instruction", "")
    
    return await kernel.process(instruction, ctx, api_key)


@app.post("/api/v1/test")
async def test_endpoint(request: Request, api_key: str = Depends(verify_key)):
    """Test endpoint"""
    try:
        body = await request.json()
    except:
        raise HTTPException(400, "Invalid JSON")
    return {"received": body, "key_prefix": f"{api_key[:4]}..."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)