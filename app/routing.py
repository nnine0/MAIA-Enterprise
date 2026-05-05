"""
Routing module for expert selection.
"""

import logging
from typing import Optional
from dataclasses import dataclass
from openai import AsyncOpenAI
import config

logger = logging.getLogger(__name__)

client = AsyncOpenAI(base_url=f"{config.LORAX_URL}/v1", api_key="not-needed")


@dataclass
class RouteResult:
    expert: str
    confidence: float = 1.0
    method: str = "keyword"


def route_to_expert_keyword(user_query: str) -> RouteResult:
    """
    Keyword-based fallback routing.
    """
    query_lower = user_query.lower()
    
    keywords_map = {
        "real_estate_leasing": ["real estate", "leasing", "property", "mortgage"],
        "manufacturing": ["manufacturing", "engineering", "factory", "production"],
        "professional_services": ["law", "legal", "accounting", "consulting"],
        "government": ["government", "public policy", "regulatory"],
        "health_care": ["health", "medical", "care", "hospital"],
        "finance_insurance": ["finance", "insurance", "investment", "banking"],
        "retail_trade": ["retail", "sales", "commerce", "store"],
        "wholesale_trade": ["wholesale", "distribution", "supply chain"],
        "information": ["information", "media", "tech", "software"],
    }
    
    for expert, keywords in keywords_map.items():
        if any(kw in query_lower for kw in keywords):
            return RouteResult(expert=expert, confidence=0.7, method="keyword")
    
    return RouteResult(expert="general", confidence=0.5, method="keyword")


async def route_to_expert_llm(user_query: str) -> RouteResult:
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