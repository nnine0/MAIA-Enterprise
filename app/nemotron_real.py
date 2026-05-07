"""
MAIA Nemotron 3 Content Safety - Real Integration
============================================
Uses nvidia/Nemotron-3-Content-Safety (Gemma-3-4B-it based)

Features:
- 22 Safety Categories
- Multimodal (text + image)
- 12 languages
- vLLM or Transformers runtime

Categories (22):
- Violence, Sexual, Criminal Planning, Guns, Controlled Substances
- Suicide, Hate/Identity, PII/Privacy, Harassment, Threat
- Profanity, Needs Caution, Manipulation, Fraud/Deception
- Malware, High Risk Gov Decision, Political/Misinformation
- Copyright/Trademark, Unauthorized Advice, Illegal Activity, Immoral/Unethical

Run: python3 -m app.nemotron_real
"""

import os
import io
import base64
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

try:
    import torch
    from PIL import Image
    from transformers import AutoProcessor, Gemma3ForConditionalGeneration
    NEMOTRON_AVAILABLE = True
except ImportError:
    NEMOTRON_AVAILABLE = False
    torch = None
    Image = None


class SafetyTier(Enum):
    TIER_1_CRITICAL = 1  # Hard block
    TIER_2_ELEVATED = 2  # Escalate
    TIER_3_BENIGN = 3   # Pass


# Map 22 categories to MAIA tiers
CATEGORY_TIERS = {
    # Tier 1: Critical - Hard Block
    "Violence": SafetyTier.TIER_1_CRITICAL,
    "Criminal Planning/Confessions": SafetyTier.TIER_1_CRITICAL,
    "Guns and Illegal Weapons": SafetyTier.TIER_1_CRITICAL,
    "Controlled/Regulated Substances": SafetyTier.TIER_1_CRITICAL,
    "Hate/Identity Hate": SafetyTier.TIER_1_CRITICAL,
    "Threat": SafetyTier.TIER_1_CRITICAL,
    "Fraud/Deception": SafetyTier.TIER_1_CRITICAL,
    "Malware": SafetyTier.TIER_1_CRITICAL,
    "High Risk Gov Decision Making": SafetyTier.TIER_1_CRITICAL,
    "Illegal Activity": SafetyTier.TIER_1_CRITICAL,
    "Sexual": SafetyTier.TIER_1_CRITICAL,
    "Sexual (minor)": SafetyTier.TIER_1_CRITICAL,
    
    # Tier 2: Elevated - Escalate
    "PII/Privacy": SafetyTier.TIER_2_ELEVATED,
    "Harassment": SafetyTier.TIER_2_ELEVATED,
    "Unauthorized Advice": SafetyTier.TIER_2_ELEVATED,
    "Immoral/Unethical": SafetyTier.TIER_2_ELEVATED,
    "Manipulation": SafetyTier.TIER_2_ELEVATED,
    "Political/Misinformation/Conspiracy": SafetyTier.TIER_2_ELEVATED,
    "Suicide and Self Harm": SafetyTier.TIER_2_ELEVATED,
    
    # Tier 3: Benign - Pass
    "Profanity": SafetyTier.TIER_3_BENIGN,
    "Needs Caution": SafetyTier.TIER_3_BENIGN,
    "Copyright/Trademark/Plagiarism": SafetyTier.TIER_3_BENIGN,
    "Other": SafetyTier.TIER_3_BENIGN,
}


@dataclass
class NemotronResult:
    """Result from Nemotron"""
    user_safe: str
    response_safe: str
    categories: List[str]
    tier: int
    latency_ms: float = 0.0


def make_multimodal_messages(
    prompt: str,
    image_path: Optional[str] = None,
    response: Optional[str] = None
) -> List[Dict]:
    """Create multimodal messages for Nemotron"""
    content = [{"type": "text", "text": prompt}]
    
    if image_path:
        if os.path.exists(image_path):
            image = Image.open(image_path)
            img_bytes = io.BytesIO()
            image.save(img_bytes, format="JPEG")
            img_content = {"type": "image", "image": base64.b64encode(img_bytes.getvalue()).decode('utf-8')}
        else:
            img_content = {"type": "image", "image": image_path}
        
        content = [img_content, *content]
    
    messages = [{"role": "user", "content": content}]
    
    if response:
        messages.append({"role": "assistant", "content": [{"type": "text", "text": response}]})
    
    return messages


class Nemotron3Safety:
    """
    MAIA PVI Airlock using Nemotron 3 Content Safety
    
    Real model integration for production use.
    """
    
    def __init__(
        self,
        model_id: str = "nvidia/Nemotron-3-Content-Safety",
        use_vllm: bool = False
    ):
        self.model_id = model_id
        self.use_vllm = use_vllm
        self.model = None
        self.processor = None
        self.loaded = False
    
    def load(self, device: str = "auto"):
        """Load Nemotron model"""
        if not NEMOTRON_AVAILABLE:
            raise RuntimeError("transformers/torch required: pip install transformers torch")
        
        print(f"Loading {self.model_id}...")
        self.model = Gemma3ForConditionalGeneration.from_pretrained(
            self.model_id,
            device_map=device,
            torch_dtype=torch.bfloat16 if torch else None
        )
        self.processor = AutoProcessor.from_pretrained(self.model_id)
        self.loaded = True
        print("Nemotron 3 Content Safety loaded")
    
    async def audit(
        self,
        prompt: str,
        response: str,
        image_path: Optional[str] = None,
        get_categories: bool = True
    ) -> NemotronResult:
        """
        Audit prompt and response
        
        Returns: user_safe, response_safe, categories, tier
        """
        start = datetime.now()
        
        if not self.loaded:
            return NemotronResult(
                user_safe="unsafe",
                response_safe="unsafe",
                categories=["model_not_loaded"],
                tier=1,
                latency_ms=0
            )
        
        # Create messages
        messages = make_multimodal_messages(prompt, image_path, response)
        
        # Apply template with categories request
        cat_arg = "/categories" if get_categories else "/no_categories"
        
        try:
            inputs = self.processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
                request_categories=cat_arg
            )
        except Exception as e:
            return NemotronResult(
                user_safe="unsafe",
                response_safe="unsafe",
                categories=[f"template_error: {e}"],
                tier=1
            )
        
        if torch and hasattr(self.model, 'device'):
            inputs = inputs.to(self.model.device)
        
        # Generate
        with torch.inference_mode():
            generation = self.model.generate(**inputs, max_new_tokens=100, do_sample=False)
            input_len = inputs["input_ids"].shape[-1]
            generation = generation[0][input_len:]
        
        decoded = self.processor.decode(generation, skip_special_tokens=True)
        
        # Parse result
        return self._parse_response(decoded, (datetime.now() - start).total_seconds() * 1000)
    
    def _parse_response(self, text: str, latency_ms: float) -> NemotronResult:
        """Parse Nemotron output"""
        user_safe = "safe"
        response_safe = "safe"
        categories = []
        tier = 3
        
        text_lower = text.lower()
        
        # Parse lines
        for line in text.strip().split('\n'):
            if "user safety:" in line:
                user_safe = line.split("user safety:")[-1].strip()
            elif "response safety:" in line:
                response_safe = line.split("response safety:")[-1].strip()
            elif "safety categories:" in line or "categories:" in line:
                cat_str = line.split(":")[-1].strip()
                categories = [c.strip() for c in cat_str.split(",")]
        
        # Determine tier from categories
        for cat in categories:
            cat_clean = cat.strip()
            if cat_clean in CATEGORY_TIERS:
                cat_tier = CATEGORY_TIERS[cat_clean]
                if cat_tier.value < tier:
                    tier = cat_tier.value
        
        # Override tier if unsafe
        if user_safe == "unsafe" or response_safe == "unsafe":
            if tier > 1:
                tier = 1  # Escalate to critical
        
        return NemotronResult(
            user_safe=user_safe,
            response_safe=response_safe,
            categories=categories,
            tier=tier,
            latency_ms=latency_ms
        )


class MockNemotron3:
    """Demo mode without GPU"""
    
    def __init__(self, *args, **kwargs):
        pass
    
    async def audit(
        self,
        prompt: str,
        response: str,
        image_path: Optional[str] = None
    ) -> NemotronResult:
        """Mock audit"""
        prompt_lower = prompt.lower()
        resp_lower = response.lower() if response else ""
        
        # Critical violations
        critical = ["sanction", "russia", "iran", "terrorist", "steal", "fraud", "weapon"]
        for w in critical:
            if w in prompt_lower or w in resp_lower:
                return NemotronResult(
                    user_safe="safe",
                    response_safe="unsafe",
                    categories=["Fraud/Deception", "Illegal Activity"],
                    tier=1,
                    latency_ms=50
                )
        
        # Elevated
        elevated = ["patient", "diagnosis", "phi", "attorney", "privileged"]
        for w in elevated:
            if w in prompt_lower or w in resp_lower:
                return NemotronResult(
                    user_safe="safe",
                    response_safe="unsafe",
                    categories=["PII/Privacy"],
                    tier=2,
                    latency_ms=50
                )
        
        return NemotronResult(
            user_safe="safe",
            response_safe="safe",
            categories=[],
            tier=3,
            latency_ms=30
        )


def create_nemotron(demo: bool = False):
    """Create Nemotron instance"""
    if demo or not NEMOTRON_AVAILABLE:
        return MockNemotron3()
    return Nemotron3Safety()


if __name__ == "__main__":
    async def test():
        print("Nemotron 3 Content Safety")
        print("="*50)
        
        nemotron = create_nemotron(demo=True)
        
        tests = [
            ("How can I steal money?", "The best way is to enter as an old lady..."),
            ("Check patient record", "Patient John Doe, diagnosis: cancer"),
            ("Calculate credit", "Credit score is 750, approve"),
        ]
        
        for prompt, response in tests:
            r = await nemotron.audit(prompt, response)
            tier_status = f"Tier {r.tier}"
            print(f"{tier_status:10} | {prompt[:25]}...")
            print(f"            User: {r.user_safe}, Response: {r.response_safe}")
            if r.categories:
                print(f"            Cats: {r.categories}")
        
    asyncio.run(test())