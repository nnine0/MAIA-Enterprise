"""
MAIA Semantic Router - Layer 9 Client-Side Router
==============================================

This logic resides in your application edge.
It determines if a request is "Creative" (OpenAI) or "Material" (MAIA).

Materiality Matrix Logic:
- financial_bid, safety_log, legal_contract → Route to MAIA PVI Airlock
- creative, general, chat → Route to Public API (OpenAI)
"""

import os
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import Enum


class RequestType(Enum):
    """Types of requests"""
    MATERIAL = "material"     # Governance, compliance, financial
    CREATIVE = "creative"   # General, open-ended
    UNKNOWN = "unknown"


class TargetBackend(Enum):
    """Routing targets"""
    MAIA = "maia"      # MAIA PVI Airlock (local)
    OPENAI = "openai"  # Public API
    ANTHROPIC = "anthropic"


@dataclass
class RouteContext:
    """Context for routing decision"""
    request_type: RequestType
    target_backend: TargetBackend
    sector: Optional[str]
    lora_adapter: Optional[str]
    reason: str


MATERIAL_KEYWORDS = {
    "financial_bid": [
        "bid", "margin", "contract", "proposal", "loan", "credit",
        "wire", "transfer", "payment", "quote", "valuation", " underwriting"
    ],
    "safety_log": [
        "incident", "accident", "injury", "osha", "safety", "hazard",
        "violation", "audit", "compliance", "regulatory"
    ],
    "legal_contract": [
        "legal", "contract", "litigation", "settlement", "agreement",
        "liability", "indemnification", "clause", "terms"
    ],
    "healthcare": [
        "patient", "diagnosis", "prescription", "clinical", "treatment",
        "diagnosis", "medical", "health"
    ]
}


class MAIARouter:
    """
    Layer 9 Semantic Router.
    
    Routes requests between:
    - MAIA PVI Airlock (local, Governance)
    - Public APIs (OpenAI, Anthropic - Creative)
    """
    
    def __init__(
        self,
        maia_base_url: str = "http://localhost:8000/v1",
        maia_api_key: str = "MAIA_LOCAL",
        openai_api_key: Optional[str] = None,
    ):
        self.maia_base_url = maia_base_url
        self.maia_api_key = maia_api_key
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        
        # Try importing openai, fallback to mock if not available
        try:
            import openai
            self.openai = openai
            self._has_openai = bool(self.openai_api_key)
        except ImportError:
            self._has_openai = False
    
    def classify_request(self, prompt: str) -> RequestType:
        """
        Classify if request is Material or Creative.
        
        Uses keyword matching against Materiality Matrix.
        """
        prompt_lower = prompt.lower()
        
        for material_type, keywords in MATERIAL_KEYWORDS.items():
            if any(kw in prompt_lower for kw in keywords):
                return RequestType.MATERIAL
        
        return RequestType.CREATIVE
    
    def detect_sector(self, prompt: str) -> Optional[str]:
        """Detect sector from prompt keywords"""
        prompt_lower = prompt.lower()
        
        if any(kw in prompt_lower for kw in MATERIAL_KEYWORDS["financial_bid"]):
            return "finance_insurance"
        if any(kw in prompt_lower for kw in MATERIAL_KEYWORDS["safety_log"]):
            return "government_public"
        if any(kw in prompt_lower for kw in MATERIAL_KEYWORDS["legal_contract"]):
            return "legal"
        if any(kw in prompt_lower for kw in MATERIAL_KEYWORDS["healthcare"]):
            return "biotech_pharma"
        
        return "general"
    
    def get_sector_adapter(self, sector: str) -> str:
        """Get LoRA adapter name for sector"""
        adapter_map = {
            "finance_insurance": "finance_insurance_adapter",
            "government_public": "government_public_adapter", 
            "legal": "legal_adapter",
            "biotech_pharma": "biotech_pharma_adapter",
            "real_estate": "real_estate_adapter",
            "general": "general_adapter",
        }
        return adapter_map.get(sector, "general_adapter")
    
    def route(self, prompt: str) -> RouteContext:
        """
        Main routing decision.
        
        Returns RouteContext with:
        - request_type: MATERIAL or CREATIVE
        - target_backend: MAIA or OPENAI
        - sector: detected sector
        - lora_adapter: adapter to use (if MAIA)
        """
        # Classify request
        request_type = self.classify_request(prompt)
        
        if request_type == RequestType.MATERIAL:
            # Route to MAIA PVI Airlock
            sector = self.detect_sector(prompt)
            lora_adapter = self.get_sector_adapter(sector)
            
            return RouteContext(
                request_type=request_type,
                target_backend=TargetBackend.MAIA,
                sector=sector,
                lora_adapter=lora_adapter,
                reason=f"Material request detected ({sector})"
            )
        else:
            # Route to public API
            return RouteContext(
                request_type=request_type,
                target_backend=TargetBackend.OPENAI,
                sector=None,
                lora_adapter=None,
                reason="Non-material request - creative/general"
            )
    
    async def execute(self, prompt: str, backend: Optional[TargetBackend] = None) -> Dict:
        """
        Execute the routed request.
        
        If backend not specified, uses router decision.
        """
        context = self.route(prompt)
        
        if backend and backend != context.target_backend:
            # Override routing
            context.target_backend = backend
        
        result = {
            "routed_to": context.target_backend.value,
            "request_type": context.request_type.value,
            "sector": context.sector,
            "lora_adapter": context.lora_adapter,
            "reason": context.reason,
            # In real implementation, would call actual API here
            "status": "mock_response",
        }
        
        return result
    
    def get_status(self) -> Dict:
        """Get router status"""
        return {
            "maia_url": self.maia_base_url,
            "has_openai": self._has_openai,
            "material_keywords": sum(len(kw) for kw in MATERIAL_KEYWORDS.values()),
        }


# Example usage
if __name__ == "__main__":
    router = MAIARouter()
    
    print("=== MAIA Semantic Router ===")
    print()
    
    test_queries = [
        "What is the weather today?",  # Creative
        "Submit bid for Jacksonville contract at 2% margin",  # Material
        "Draft contract for merger",  # Material
        "Write a poem about AI",  # Creative
    ]
    
    for query in test_queries:
        ctx = router.route(query)
        print(f'Query: "{query[:40]}..."')
        print(f'  → {ctx.target_backend.value}')
        print(f'    Type: {ctx.request_type.value}')
        if ctx.sector:
            print(f'    Sector: {ctx.sector}')
            print(f'    LoRA: {ctx.lora_adapter}')
        print()