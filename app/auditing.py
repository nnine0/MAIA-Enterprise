"""
Auditing module for response validation and sanitization.
"""

import re
from openai import AsyncOpenAI
from config import LORAX_URL

client = AsyncOpenAI(base_url=f"{LORAX_URL}/v1", api_key="not-needed")

def extract_response(text: str) -> str:
    """
    Remove thinking tags from response.
    """
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
    text = re.sub(r'<thinking>.*', '', text, flags=re.DOTALL)
    return text.strip()

async def audit_response(draft_response: str, general_adapter: str) -> str:
    """
    Audit the response for consistency.
    """
    audit_prompt = f"Review this response for logical inconsistencies or formatting errors. If valid, repeat it. If invalid, correct it.\n\nResponse: {draft_response}"

    audit_completion = await client.chat.completions.create(
        model="google/gemma-4-26b-a4b-it",
        messages=[{"role": "user", "content": audit_prompt}],
        extra_body={"adapter_id": f"/adapters/{general_adapter}", "adapter_source": "local", "fallback_to_base": True}
    )

    response = audit_completion.choices[0].message.content
    return extract_response(response)