"""
Routing module for expert selection.
"""

import os
from typing import Optional
from openai import AsyncOpenAI
from config import LORAX_URL, EXPERT_LIST

client = AsyncOpenAI(base_url=f"{LORAX_URL}/v1", api_key="not-needed")

def route_to_expert_keyword(user_query: str) -> str:
    """
    Simple keyword-based routing to experts.
    """
    query_lower = user_query.lower()
    if "real estate" in query_lower or "leasing" in query_lower or "property" in query_lower:
        return "real_estate_leasing"
    if "manufacturing" in query_lower or "engineering" in query_lower or "factory" in query_lower:
        return "manufacturing"
    if "law" in query_lower or "legal" in query_lower or "professional" in query_lower or "accounting" in query_lower:
        return "professional_services"
    if "government" in query_lower or "public" in query_lower or "policy" in query_lower:
        return "government"
    if "health" in query_lower or "medical" in query_lower or "care" in query_lower:
        return "health_care"
    if "finance" in query_lower or "insurance" in query_lower or "money" in query_lower:
        return "finance_insurance"
    if "retail" in query_lower or "trade" in query_lower or "sales" in query_lower:
        return "retail_trade"
    if "wholesale" in query_lower or "distribution" in query_lower:
        return "wholesale_trade"
    if "information" in query_lower or "media" in query_lower or "tech" in query_lower:
        return "information"
    return "trivium"

async def route_to_expert_semantic(user_query: str) -> str:
    """
    Semantic routing using the base model.
    """
    classification_prompt = f"""<|system|>
Classify this query into one category: {', '.join(EXPERT_LIST)}. Respond ONLY with the category name.
<|user|>
{user_query}
<|assistant|>"""

    try:
        response = await client.completions.create(
            model="Nanbeige/Nanbeige4-3B-Thinking-2511",
            prompt=classification_prompt,
            max_tokens=10,
            temperature=0.1
        )
        category = response.choices[0].text.strip().lower()
        for expert in EXPERT_LIST:
            if expert in category:
                return expert
        return "trivium"
    except Exception as e:
        print(f"Routing Error: {e}")
        return "trivium"