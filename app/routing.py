"""
Routing module for expert selection.
Supports both department path routing and query-based routing.
"""

import logging
import re
from typing import Optional
from dataclasses import dataclass
import config

logger = logging.getLogger(__name__)


def _get_client():
    from openai import AsyncOpenAI
    return AsyncOpenAI(base_url=f"{config.LORAX_URL}/v1", api_key=config.LORAX_API_KEY)


client = None  # Lazy init


@dataclass
class RouteResult:
    expert: str
    confidence: float = 1.0
    method: str = "keyword"
    department: Optional[str] = None
    node_port: Optional[int] = None


DEPARTMENT_MAP = {
    "/estimating": {
        "department": "estimating",
        "node_port": 8001,
        "keywords": ["bid", "estimate", "margin", "cost", "pricing", "quote", "job", "project"],
    },
    "/legal": {
        "department": "legal",
        "node_port": 8002,
        "keywords": ["contract", "legal", "far", "dfars", "compliance", "clause", "indemnification", "liability"],
    },
    "/safety": {
        "department": "safety",
        "node_port": 8003,
        "keywords": ["safety", "osha", "hazard", "inspection", "site", "work order", "stop work"],
    },
    "/logistics": {
        "department": "logistics",
        "node_port": 8004,
        "keywords": ["logistics", "fleet", "delivery", "driver", "dot", "hazmat", "shipping", "transport"],
    },
}


def route_by_path(path: str) -> Optional[RouteResult]:
    """
    Route by URL path prefix.
    E.g., /estimating/* -> Node 1 (port 8001)
    """
    path_lower = path.lower().rstrip("/")
    
    for path_prefix, info in DEPARTMENT_MAP.items():
        if path_lower.startswith(path_prefix):
            return RouteResult(
                expert=info["department"],
                confidence=1.0,
                method="path",
                department=info["department"],
                node_port=info["node_port"]
            )
    
    return None


def route_to_expert_keyword(user_query: str) -> RouteResult:
    """
    Keyword-based fallback routing.
    """
    query_lower = user_query.lower()
    
    keywords_map = {
        "estimating": ["bid", "estimate", "margin", "cost", "pricing", "quote", "job", "project", "structural", "rebar", "contingency"],
        "legal": ["contract", "legal", "far", "dfars", "compliance", "clause", "indemnification", "liability", "davis-bacon"],
        "safety": ["safety", "osha", "hazard", "inspection", "site", "work order", "stop work", "fall protection", "scaffold"],
        "logistics": ["logistics", "fleet", "delivery", "driver", "dot", "hazmat", "shipping", "transport", "hours of service"],
        "real_estate_leasing": ["real estate", "leasing", "property", "mortgage"],
        "manufacturing": ["manufacturing", "engineering", "factory", "production"],
        "government": ["government", "public policy", "regulatory"],
        "health_care": ["health", "medical", "care", "hospital"],
        "finance_insurance": ["finance", "insurance", "investment", "banking"],
        "retail_trade": ["retail", "sales", "commerce", "store"],
        "wholesale_trade": ["wholesale", "distribution", "supply chain"],
        "information": ["information", "media", "tech", "software"],
    }
    
    for expert, keywords in keywords_map.items():
        if any(kw in query_lower for kw in keywords):
            info = DEPARTMENT_MAP.get(f"/{expert}")
            if info:
                return RouteResult(
                    expert=expert,
                    confidence=0.8,
                    method="keyword",
                    department=info["department"],
                    node_port=info["node_port"]
                )
            return RouteResult(expert=expert, confidence=0.7, method="keyword")
    
    return RouteResult(expert="general", confidence=0.5, method="keyword")


async def route_to_expert_llm(user_query: str) -> RouteResult:
    global client
    if client is None:
        client = _get_client()
    """
    LLM-based classification routing.
    Uses the base model's natural language understanding - not embeddings.
    More flexible than keyword matching but requires GPU.
    """
    classification_prompt = f"""Classify this query into one category: {', '.join(config.EXPERT_LIST)}. Respond ONLY with the category name.
Query: {user_query}
Category:"""

    try:
        response = await client.completions.create(
            model=config.BASE_MODEL_ID,
            messages=[{"role": "user", "content": classification_prompt}],
            max_tokens=20,
            temperature=0.1,
        )
        
        category = response.choices[0].message.content.strip().lower()
        
        for expert in config.EXPERT_LIST:
            if expert.lower() in category:
                return RouteResult(expert=expert, confidence=0.9, method="llm")
        
        logger.warning(f"LLM routing fell through, category: {category}")
        return RouteResult(expert="general", confidence=0.3, method="llm")
        
    except Exception as e:
        logger.error(f"LLM routing failed: {e}")
        return RouteResult(expert="general", confidence=0.1, method="error")


async def route_query(user_query: str, use_llm: bool = True) -> RouteResult:
    """
    Unified routing: LLM with keyword fallback.
    
    Flow:
    1. Try LLM classification (higher accuracy, requires GPU)
    2. Fall back to keyword matching if LLM fails or confidence low
    """
    if use_llm:
        result = await route_to_expert_llm(user_query)
        if result.confidence >= 0.5:
            return result
    
    return route_to_expert_keyword(user_query)