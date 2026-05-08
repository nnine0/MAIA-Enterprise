"""
MAIA Supervisor Router - Hub and Spoke Architecture
Implements the "Neural Org-Chart" with hierarchical LoRA orchestration.

Level 1 (Executive): Identifies industry (Finance, Logistics, Legal)
Level 2 (Manager): Identifies sub-domain (e.g., Finance -> Commercial Lending)
Level 3 (Worker): Performs actual task (calculation, drafting)
Sentinel: PVI Airlock sidecar monitoring entire chain
"""

import asyncio
import json
import os
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
from openai import AsyncOpenAI
from config import LORAX_URL
from core.adapter_loader import registry


class IndustryLevel(Enum):
    """Level 1: Executive LoRA - Industry identification"""
    FINANCE = "finance"
    LOGISTICS = "logistics"
    LEGAL = "legal"
    HEALTHCARE = "healthcare"
    GOVERNMENT = "government"
    UNKNOWN = "unknown"


class SubDomainLevel(Enum):
    """Level 2: Manager LoRA - Sub-domain identification"""
    # Finance
    COMMERCIAL_CREDIT = "commercial_credit"
    RETAIL_BANKING = "retail_banking"
    WEALTH_MANAGEMENT = "wealth_management"
    FRAUD_AML = "fraud_aml"
    # Logistics
    TERMINAL_OPERATIONS = "terminal_operations"
    HAZMAT_COMPLIANCE = "hazmat_compliance"
    ROUTE_OPTIMIZATION = "route_optimization"
    # Legal
    CONTRACT_DRAFTING = "contract_drafting"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    LITIGATION = "litigation"


@dataclass
class DispatchToken:
    """Structured output from Supervisor LoRA"""
    industry: str
    sub_domain: str
    expert_adapter: str
    auditor_adapter: str
    materiality_tier: int
    execution_path: List[str]  # Ordered list of adapters to invoke


# Hub configurations - Department-in-a-Box
HUB_CONFIGS = {
    "finance": {
        "hub_adapter": "credit-risk-manager-hub",
        "spokes": {
            "commercial_credit": {
                "expert": "commercial-lending-v4",
                "auditor": "sr26-02-auditor",
                "experts": ["cash-flow-sme", "collateral-valuator", "industry-volatility-sme"]
            },
            "retail_banking": {
                "expert": "retail-banking-v4",
                "auditor": "sr26-02-auditor",
                "experts": ["mortgage-sme", "credit-card-sme"]
            },
            "fraud_aml": {
                "expert": "fraud-aml-director",
                "auditor": "sar-auditor",
                "experts": ["sanctions-list-sme", "pattern-anomaly-sme", "sar-drafting-sme"]
            }
        }
    },
    "logistics": {
        "hub_adapter": "terminal-director-hub",
        "spokes": {
            "terminal_operations": {
                "expert": "terminal-ops-v4",
                "auditor": "safety-auditor-v4",
                "experts": ["hazmat-sme", "fuel-efficiency-sme", "route-safety-sme"]
            },
            "hazmat_compliance": {
                "expert": "hazmat-compliance-v4",
                "auditor": "regulatory-auditor",
                "experts": ["dot-compliance-sme", "epa-sme"]
            }
        }
    },
    "legal": {
        "hub_adapter": "department-head-hub",
        "spokes": {
            "contract_drafting": {
                "expert": "contract-expert-v4",
                "auditor": "compliance-auditor",
                "experts": ["nda-sme", "msa-sme"]
            },
            "regulatory_compliance": {
                "expert": "regulatory-expert-v4",
                "auditor": "sec-auditor",
                "experts": ["finra-sme", "occ-sme"]
            }
        }
    }
}


class SupervisorRouter:
    """
    Supervisor LoRA Router - Neural Dispatch System.
    
    Instead of string-parsing in Python, we use a Supervisor LoRA
    that acts as the "Hub" within the kernel, performing latent-space
    materiality analysis to dispatch to the correct expert adapters.
    """
    
    def __init__(self, lorax_url: str = LORAX_URL):
        self.client = AsyncOpenAI(base_url=f"{lorax_url}/v1", api_key=os.getenv("LORAX_API_KEY", "not-needed"))
        self.default_hub = registry.get_hub("governance_hub") or "/data/adapters/governance_hub_v1"
        
    async def route(self, user_query: str) -> DispatchToken:
        """
        Execute hierarchical routing:
        1. Executive LoRA: Identify industry
        2. Manager LoRA: Identify sub-domain
        3. Generate dispatch token
        """
        # LEVEL 1: Executive routing (Industry)
        industry = await self._identify_industry(user_query)
        
        # LEVEL 2: Manager routing (Sub-domain)
        sub_domain = await self._identify_subdomain(user_query, industry)
        
        # Get hub/spoke config
        config = HUB_CONFIGS.get(industry.value, HUB_CONFIGS["finance"])
        
        # LEVEL 3: Get spoke configuration
        spoke = config["spokes"].get(sub_domain.value, config["spokes"]["commercial_credit"])
        
        # Determine materiality tier
        materiality_tier = self._assess_materiality(user_query)
        
        # Build execution path
        execution_path = [config["hub_adapter"], spoke["expert"]]
        if materiality_tier == 1:
            execution_path.append(spoke["auditor"])  # Add auditor for Tier 1
        
        return DispatchToken(
            industry=industry.value,
            sub_domain=sub_domain.value,
            expert_adapter=spoke["expert"],
            auditor_adapter=spoke["auditor"],
            materiality_tier=materiality_tier,
            execution_path=execution_path
        )
    
    async def _identify_industry(self, query: str) -> IndustryLevel:
        """Level 1: Executive LoRA identifies industry"""
        prompt = f"""Classify this query into one industry: finance, logistics, legal, healthcare, government.
Respond ONLY with the industry name.
Query: {query}"""
        
        try:
            response = await self.client.completions.create(
                model="google/gemma-4-26b-a4b-it",
                prompt=prompt,
                max_tokens=20,
                temperature=0.1,
                extra_body={
                    "adapter_id": self.default_hub,
                    "adapter_source": "local"
                }
            )
            industry = response.choices[0].text.strip().lower()
            for ind in IndustryLevel:
                if ind.value in industry:
                    return ind
        except Exception as e:
            print(f"Industry routing error: {e}")
        return IndustryLevel.FINANCE

    async def _identify_subdomain(self, query: str, industry: IndustryLevel) -> SubDomainLevel:
        """Level 2: Manager LoRA identifies sub-domain"""
        prompt = f"""Given the industry '{industry.value}', classify this query into a sub-domain.
Respond ONLY with the sub-domain name.
Query: {query}"""

        # Map industry to valid sub-domains
        subdomain_map = {
            IndustryLevel.FINANCE: ["commercial_credit", "retail_banking", "wealth_management", "fraud_aml"],
            IndustryLevel.LOGISTICS: ["terminal_operations", "hazmat_compliance", "route_optimization"],
            IndustryLevel.LEGAL: ["contract_drafting", "regulatory_compliance", "litigation"]
        }

        valid_subdomains = subdomain_map.get(industry, ["commercial_credit"])

        try:
            response = await self.client.completions.create(
                model="google/gemma-4-26b-a4b-it",
                prompt=prompt,
                max_tokens=30,
                temperature=0.1,
                extra_body={
                    "adapter_id": self.default_hub,
                    "adapter_source": "local"
                }
            )
            subdomain = response.choices[0].text.strip().lower()
            for sd in valid_subdomains:
                if sd in subdomain:
                    return SubDomainLevel(sd)
        except Exception as e:
            print(f"Sub-domain routing error: {e}")
        return SubDomainLevel.COMMERCIAL_CREDIT
    
    def _assess_materiality(self, query: str) -> int:
        """Assess materiality tier for execution path"""
        critical = ["credit", "wire", "transfer", "loan", "mortgage", "sanction", "fraud", "aml"]
        elevated = ["risk", "limit", "approval", "policy", "compliance"]
        
        query_lower = query.lower()
        if any(w in query_lower for w in critical):
            return 1
        elif any(w in query_lower for w in elevated):
            return 2
        return 3
    
    def get_dispatch_token_string(self, token: DispatchToken) -> str:
        """Convert dispatch token to readable format"""
        return f"[EXECUTE: {token.expert_adapter}, AUDIT: {token.auditor_adapter}, TIER: {token.materiality_tier}]"


# Global router instance
supervisor_router = SupervisorRouter()


async def route_query(query: str) -> DispatchToken:
    """Public API for hierarchical routing"""
    return await supervisor_router.route(query)