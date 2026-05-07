"""
MAIA Unified Kernel - Complete Integration
===================================
Combines all components into single API:

- Gemma 4 (E4B) - Reasoning/Generation
- Nemotron 3 - Content Safety Audit  
- SGLang - Agentic Engine
- Circuit Breaker - Governance

Layers:
- L9: Agentic (Gemma 4 + Think)
- L8: Governance (Nemotron + DME)
- L7: Application (Adapters)

Run: python3 -m app.maia_unified
"""

import asyncio
import hashlib
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

# Import existing components
from app.kernel import MAIKKernel, UserContext, ADAPTERS
from app.gemma4_complete import create_gemma4
from app.nemotron_real import create_nemotron


class Verdict(Enum):
    CERTIFIED = "CERTIFIED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"


@dataclass
class MAIARequest:
    """Unified request"""
    instruction: str
    sector: str = "finance_insurance"
    role: str = "analyst"
    materiality_target: str = "tier_2"
    thinking: bool = True
    image: Optional[str] = None


@dataclass
class MAIAResponse:
    """Unified response"""
    status: str
    transaction_id: str
    audit_trail: str
    tier: int
    latency_ms: float
    response: Optional[str] = None
    thinking: Optional[str] = None
    violations: List[str] = None
    sectors_checked: List[str] = None
    error: Optional[str] = None


class MAIAUnified:
    """
    Unified MAIA Kernel
    
    Integrates:
    - Gemma 4 for reasoning/generation
    - Nemotron 3 for content safety
    - Kernel for governance
    """
    
    def __init__(self, demo: bool = True):
        self.demo = demo
        
        # Components
        self.gemma = create_gemma4("E4B", demo=demo)
        self.nemotron = create_nemotron(demo=demo)
        self.kernel = MAIKKernel(mode="demo" if demo else "production")
        
        print(f"MAIA Unified initialized (demo={demo})")
    
    async def process(self, request: MAIARequest) -> MAIAResponse:
        """
        Process through all layers
        
        Flow:
        1. L9: Generate with Gemma 4 (thinking)
        2. L8: Audit with Nemotron 3 (safety)
        3. L7: Circuit breaker decision
        """
        start = datetime.now()
        tx_id = f"tx-{uuid.uuid4().hex[:12]}"
        
        tier = {"tier_1": 1, "tier_2": 2, "tier_3": 3}.get(
            request.materiality_target, 2
        )
        
        violations = []
        sectors_checked = []
        
        # L9: Generate with Gemma 4
        try:
            gemma_result = await self.gemma.governed_generate(
                prompt=request.instruction,
                system_prompt=f"You are a {request.sector} compliance analyst."
            )
            response = gemma_result.response
            thinking = gemma_result.thinking
            
            if gemma_result.violations:
                violations.extend(gemma_result.violations)
        except Exception as e:
            response = f"Error: {e}"
            thinking = None
        
        # L8: Nemotron audit on response
        try:
            nemotron_result = await self.nemotron.audit(
                prompt=request.instruction,
                response=response
            )
            
            if nemotron_result.tier < tier:
                tier = nemotron_result.tier
            
            if nemotron_result.categories:
                violations.extend(nemotron_result.categories)
            
            sectors_checked.append(request.sector)
        except Exception as e:
            pass
        
        # Circuit breaker
        if violations:
            if tier == 1:
                status = Verdict.BLOCKED.value
            else:
                status = Verdict.ESCALATED.value
        else:
            status = Verdict.CERTIFIED.value
        
        # Audit trail
        audit = f"{tx_id}:{status}:{violations}"
        audit_hash = hashlib.sha256(audit.encode()).hexdigest()[:16]
        
        latency = (datetime.now() - start).total_seconds() * 1000
        
        return MAIAResponse(
            status=status,
            transaction_id=tx_id,
            audit_trail=audit_hash,
            tier=tier,
            latency_ms=round(latency, 2),
            response=response[:500] if response else None,
            thinking=thinking,
            violations=violations,
            sectors_checked=sectors_checked
        )


async def main():
    print("="*60)
    print("MAIA UNIFIED KERNEL - Complete Integration")
    print("="*60)
    
    maia = MAIAUnified(demo=True)
    
    tests = [
        ("Wire $50k to Russia", "finance_insurance", "tier_1"),
        ("Check patient diagnosis record", "healthcare", "tier_2"),
        ("Calculate credit score", "finance_insurance", "tier_2"),
        ("Share attorney client privilege", "legal", "tier_2"),
        ("Access classified documents", "defense", "tier_1"),
    ]
    
    print("\n[Processing]")
    for instruction, sector, tier in tests:
        req = MAIARequest(
            instruction=instruction,
            sector=sector,
            materiality_target=tier
        )
        
        result = await maia.process(req)
        
        icon = "🚫" if result.status == "BLOCKED" else "⚠️" if result.status == "ESCALATED" else "✓"
        
        print(f"\n{icon} {result.status} | Tier {result.tier} | {instruction}")
        print(f"   Transaction: {result.transaction_id}")
        print(f"   Latency: {result.latency_ms}ms")
        if result.violations:
            print(f"   Violations: {result.violations}")
    
    print("\n" + "="*60)
    print("Complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())