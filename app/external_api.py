"""
MAIA External Evaluation API
==========================
Zero-Knowledge Governance Gateway for external testing.
Multi-tenant API that proves the Circuit Breaker works without exposing model internals.

Layer  Components
L7:    FastAPI + Kong (Rate-limiting, API Key auth, JWT)
L8:    PVI Airlock (External Auditor - intercepts before brain)
L9:    LoRAX Orchestrator (Multi-adapter kernel)
Output: Trajectory Log (Satisfactory Audit JSON)

SR 26-02: External clients test governance without seeing the model.
"""

import asyncio
import hashlib
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from pydantic import BaseModel, Field

from app.circuit_breaker import CircuitBreaker, MaterialityTier, CircuitBreakerVerdict
from app.dispatcher import NeuralToolDispatcher, DispatchRequest


class RequestContext(BaseModel):
    """Client context defining sector, role, and materiality target"""
    sector: str = Field(..., description="GDP sector: finance_insurance, healthcare, legal, construction, energy, defense, logistics")
    role: str = Field(..., description="Role: loan_officer_junior, safety_engineer, etc")
    materiality_target: str = Field(default="tier_2", description="Expected materiality: tier_1, tier_2, tier_3")


class UserRequest(BaseModel):
    """External API request payload"""
    context: RequestContext
    instruction: str = Field(..., description="Task instruction to evaluate")
    adapters: List[str] = Field(default_factory=list, description="Optional adapter list")
    stream: bool = Field(default=False, description="Enable streaming")


class AuditResult(BaseModel):
    """Audit result returned to client"""
    status: str  # BLOCKED, CERTIFIED, PENDING
    audit_trail: str  # forensic hash
    reason: Optional[str] = None
    output: Optional[str] = None
    compliance_log: Optional[Dict[str, Any]] = None
    tier: int
    latency_ms: float


class APIKeyValidator:
    """Simple API key validation (production: integrate with Kong/JWT)"""
    
    def __init__(self):
        self.valid_keys: set = set()
    
    def validate(self, api_key: str) -> bool:
        # In production: validate against Kong JWT or stored keys
        # For sandbox: accept any key with minimum length
        return len(api_key) >= 16
    
    def add_key(self, key: str):
        self.valid_keys.add(key)


api_validator = APIKeyValidator()


async def verify_api_key(x_maia_key: str = Header(..., alias="X-MAIA-Key")):
    """Dependency to verify API key"""
    if not api_validator.validate(x_maia_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_maia_key


class LoRAXOrchestrator(BaseModel):
    """
    Layer 9: Multi-Adapter Kernel
    
    Wraps the LoRAX speculative stack:
    - Generates trajectory candidates via MTP/DFlash
    - Routes to appropriate expert adapters
    """
    
    base_model: str = "gemma-4-26b-a4b"
    lorax_url: str = "http://localhost:8000"
    
    async def speculate_trajectory(
        self,
        instruction: str,
        adapter: str = "default-expert"
    ) -> str:
        """
        Generate reasoning trajectory via speculative decoding.
        
        In production: wraps actual LoRAX/MTP generation
        For sandbox: simulate trajectory generation
        """
        # Simulate MTP speculative drafting
        await asyncio.sleep(0.05)  # ~50ms for speculation
        
        trajectory = f"[SPECULATED] {instruction[:100]}... "
        trajectory += f"[ADAPTER:{adapter}] "
        trajectory += "Reasoning path: "
        
        # Simulate reasoning chain
        if "risk" in instruction.lower():
            trajectory += "assess_materiality -> check_reserves -> stress_test -> "
        elif "credit" in instruction.lower():
            trajectory += "verify_identity -> check_credit_score -> calculate_dti -> "
        elif "safety" in instruction.lower():
            trajectory += "check_osha -> verify_ppe -> validate_load -> "
        else:
            trajectory += "parse_intent -> route_domain -> execute -> "
        
        return trajectory
    
    async def generate_response(
        self,
        trajectory: str,
        adapter: str = "default-expert"
    ) -> str:
        """Generate final response from signed trajectory"""
        await asyncio.sleep(0.05)
        
        if "BLOCKED" in trajectory:
            return "[GOVERNANCE] Action not approved"
        
        # Extract intent and respond
        return f"[CERTIFIED] Processed: {trajectory[:80]}..."


class PVIAirlockExternal(BaseModel):
    """
    Layer 8: PVI Airlock (External Auditor)
    
    External-facing governance interceptor.
    Validates trajectories before they reach the brain.
    """
    
    sector_policies: Dict[str, List[str]] = {
        "finance_insurance": ["SR26-02", "ECOAf", "FHAct"],
        "healthcare": ["HIPAA", "GCP"],
        "legal": ["ATTORNEY_CLIENT", "PRIVILEGE"],
        "construction": ["OSHA", "DAVIS_BACON"],
        "energy": ["NERC_CIP", "EPA"],
        "defense": ["ITAR", "DFARS"],
        "logistics": ["DOT", "HAZMAT"]
    }
    
    async def validate_trajectory(
        self,
        trajectory: str,
        sector: str = "finance_insurance"
    ) -> tuple[CircuitBreakerVerdict, str]:
        """
        Validate trajectory against sector policies.
        
        Returns: (verdict, forensic_hash)
        """
        await asyncio.sleep(0.15)  # 150ms intercept pause
        
        trajectory_lower = trajectory.lower()
        sector_policies = self.sector_policies.get(sector, [])
        
        # Check for violations
        violation_keywords = {
            "finance_insurance": ["russia", "iran", "sanction", "structur"],
            "healthcare": ["phi", "patient_id", "diagnosis"],
            "legal": ["attorney", "privileged", "confidential"],
            "construction": ["fake", "fraud", "bribe"],
            "energy": ["unauthorized", "bypass", "override"],
            "defense": ["classified", "secret", "top_secret"],
            "logistics": ["hazmat", "explosive", "dangerous"]
        }
        
        keywords = violation_keywords.get(sector, [])
        for keyword in keywords:
            if keyword in trajectory_lower:
                return (
                    CircuitBreakerVerdict.BLOCKED,
                    f"Violation: {keyword} detected - {sector_policies}"
                )
        
        # Compute forensic hash
        forensic_hash = hashlib.sha256(
            f"{trajectory}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        return (CircuitBreakerVerdict.PASS, forensic_hash)


class ExternalEvaluationAPI:
    """
    Main orchestrator for External Evaluation API.
    
    Coordinates: L7 -> L8 -> L9 -> L8 -> Output
    """
    
    def __init__(self):
        # Layer 9: Brain
        self.orchestrator = LoRAXOrchestrator()
        
        # Layer 8: Shield
        self.airlock = PVIAirlockExternal()
        
        # Layer 7: Tool Dispatch (for completeness)
        self.dispatcher = NeuralToolDispatcher()
    
    async def execute(
        self,
        request: UserRequest,
        api_key: str
    ) -> AuditResult:
        """Execute the full governance pipeline"""
        start_time = datetime.now()
        
        # Determine materiality tier from context
        tier_map = {"tier_1": 1, "tier_2": 2, "tier_3": 3}
        tier = tier_map.get(request.context.materiality_target, 2)
        
        # Layer 9: DFlash Parallel Drafting
        adapter = request.context.role.replace("_", "-")
        trajectory_candidate = await self.orchestrator.speculate_trajectory(
            request.instruction,
            adapter=adapter
        )
        
        # Layer 8: Latent Space Verification (Interceptor Pause: 150ms)
        verdict, forensic_hash = await self.airlock.validate_trajectory(
            trajectory_candidate,
            sector=request.context.sector
        )
        
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Circuit Breaker Decision
        if verdict == CircuitBreakerVerdict.BLOCKED:
            return AuditResult(
                status="BLOCKED",
                audit_trail=forensic_hash,
                reason="Trajectory drifted into non-compliant logic",
                tier=tier,
                latency_ms=latent_ms
            )
        
        # Generate response
        response = await self.orchestrator.generate_response(
            trajectory_candidate,
            adapter=adapter
        )
        
        return AuditResult(
            status="CERTIFIED",
            audit_trail=forensic_hash,
            output=response,
            compliance_log={
                "sector": request.context.sector,
                "role": request.context.role,
                "adapters": request.adapters or [adapter],
                "policies": self.airlock.sector_policies.get(request.context.sector, [])
            },
            tier=tier,
            latency_ms=latent_ms
        )


# Global API instance
external_api = ExternalEvaluationAPI()


# Create FastAPI app
external_app = FastAPI(
    title="MAIA External Evaluation API",
    description="Zero-Knowledge Governance Gateway - Test the Circuit Breaker",
    version="1.0.0"
)


@external_app.post("/api/v1/vetted-action", response_model=AuditResult)
async def vetted_action(
    request: UserRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Execute vetted action through governance layers.
    
    L9: Generate trajectory via MTP/DFlash
    L8: Validate via PVI Airlock
    L7: Return audit trail + result
    
    Returns Satisfactory Audit JSON with certification status.
    """
    return await external_api.execute(request, api_key)


@external_app.get("/api/v1/health")
async def api_health():
    """Health check"""
    return {"status": "healthy", "api": "external-evaluation"}


@external_app.get("/api/v1/capabilities")
async def capabilities():
    """List available sectors and adapters"""
    return {
        "sectors": [
            "finance_insurance",
            "healthcare", 
            "legal",
            "construction",
            "energy",
            "defense",
            "logistics"
        ],
        "adapters": [
            "credit-analyst-v4",
            "ledger-audit-sql",
            "hipaa-airlock",
            "osha-safety",
            "nerc-cip",
            "itars-compliant"
        ],
        "materiality_tiers": ["tier_1", "tier_2", "tier_3"]
    }


# Example request handler for debugging
@external_app.post("/api/v1/test")
async def test_endpoint(
    request: UserRequest,
    api_key: str = Depends(verify_api_key)
):
    """Test endpoint - returns request info for debugging"""
    return {
        "received": request.dict(),
        "api_key_prefix": f"{api_key[:4]}..."
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(external_app, host="0.0.0.0", port=8001)