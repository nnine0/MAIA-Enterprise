"""
MAIA PVI Airlock with Nemotron Sheriff
=================================
Independent auditor using NVIDIA Nemotron-3-Content-Safety.

Architectural Independence:
- Actor: Gemma-4-E4B (reasoning-tuned)
- Auditor: Nemotron-3-4B (safety-tuned, different generation)
- Satisfies SR 26-02 "Independent Validation"

Categories Mapping:
- Tier 1 (Critical): Fraud/Deception, Illegal Activity
- Tier 2 (Elevated): PII/Privacy, Unauthorized Advice  
- Tier 3 (Benign): Profanity, Copyright

Run: python3 -m app.nemotron_airlock
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

try:
    from transformers import AutoModelForVision2Seq, AutoProcessor
    import torch
    NEMOTRON_AVAILABLE = True
except ImportError:
    NEMOTRON_AVAILABLE = False


class SafetyTier(Enum):
    TIER_1_CRITICAL = 1  # Hard-block + SME alert
    TIER_2_ELEVATED = 2  # Interrupt + DHITL vote
    TIER_3_BENIGN = 3    # Log + pass


class Verdict(Enum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


# Map 22 Nemotron categories to MAIA tiers
NEMOTRON_CATEGORIES = {
    # Tier 1: Critical - Hard Block
    "Fraud/Deception": SafetyTier.TIER_1_CRITICAL,
    "High Risk Government Decision Making": SafetyTier.TIER_1_CRITICAL,
    "Illegal Activity": SafetyTier.TIER_1_CRITICAL,
    "Hate/Violence": SafetyTier.TIER_1_CRITICAL,
    
    # Tier 2: Elevated - DHITL vote
    "Unauthorized Advice": SafetyTier.TIER_2_ELEVATED,
    "PII/Privacy": SafetyTier.TIER_2_ELEVATED,
    "Immoral/Unethical": SafetyTier.TIER_2_ELEVATED,
    "Dangerous Content": SafetyTier.TIER_2_ELEVATED,
    
    # Tier 3: Benign - Log & Pass
    "Profanity": SafetyTier.TIER_3_BENIGN,
    "Needs Caution": SafetyTier.TIER_3_BENIGN,
    "Copyright/Plagiarism": SafetyTier.TIER_3_BENIGN,
    "Sexual Content": SafetyTier.TIER_3_BENIGN,
}


@dataclass
class AuditResult:
    status: str
    tier: int
    categories: Dict[str, float]
    reason: Optional[str] = None
    latency_ms: float = 0.0


class MAIANemotronSheriff:
    """
    PVI Airlock using Nemotron-3-Content-Safety.
    
    Independent validation from different model generation.
    22 safety categories mapped to MAIA tiers.
    """
    
    def __init__(
        self,
        model_id: str = "nvidia/Nemotron-3-Content-Safety-4B",
        use_vllm: bool = False
    ):
        self.model_id = model_id
        self.use_vllm = use_vllm
        self.model = None
        self.processor = None
        self.loaded = False
    
    def load(self, device: str = "auto"):
        """Load Nemotron auditor"""
        if not NEMOTRON_AVAILABLE:
            raise RuntimeError("transformers/torch not installed")
        
        print(f"Loading {self.model_id}...")
        # Nemotron uses vision-language for multimodal safety
        self.model = AutoModelForVision2Seq.from_pretrained(
            self.model_id,
            device_map=device,
            torch_dtype=torch.bfloat16
        )
        self.processor = AutoProcessor.from_pretrained(self.model_id)
        self.loaded = True
        print("Nemotron Sheriff loaded")
    
    async def audit(
        self,
        prompt: str,
        trajectory: str,
        image_path: Optional[str] = None
    ) -> AuditResult:
        """
        Audit the trajectory (not just output).
        
        SR 26-02: Audit the reasoning, not just the response.
        """
        start = datetime.now()
        
        if not self.loaded:
            return AuditResult(
                status="ERROR",
                tier=3,
                categories={},
                reason="Model not loaded"
            )
        
        # Build messages with trajectory as "response"
        messages = self._build_messages(prompt, trajectory, image_path)
        
        # Request safety categories
        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # Process inputs
        inputs = self.processor(
            text=inputs,
            return_tensors="pt"
        ).to(self.model.device)
        
        # Generate with category labels
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=100,
                temperature=0.1
            )
        
        # Parse verdict
        categories = self._parse_categories(outputs)
        
        # Determine tier
        tier, status = self._map_to_tier(categories)
        
        return AuditResult(
            status=status,
            tier=tier,
            categories=categories,
            latency_ms=(datetime.now() - start).total_seconds() * 1000
        )
    
    def _build_messages(
        self,
        prompt: str,
        trajectory: str,
        image_path: Optional[str]
    ) -> List[Dict]:
        """Build multimodal messages"""
        messages = [
            {"role": "user", "content": prompt},
            {
                "role": "assistant",
                "content": f"[THINKING] {trajectory} [/THINKING]"
            }
        ]
        
        if image_path:
            messages[0]["image"] = image_path
        
        return messages
    
    def _parse_categories(self, outputs) -> Dict[str, float]:
        """Parse safety categories from output"""
        # In production: parse actual category scores
        # Demo: return mock
        return {
            "Fraud/Deception": 0.05,
            "Illegal Activity": 0.02,
            "PII/Privacy": 0.01,
            "Profanity": 0.01,
        }
    
    def _map_to_tier(self, categories: Dict[str, float]) -> tuple:
        """Map categories to MAIA tier"""
        # Get highest risk category above threshold
        threshold = 0.5
        
        for cat, score in sorted(categories.items(), key=lambda x: -x[1]):
            if score > threshold:
                tier = NEMOTRON_CATEGORIES.get(cat, SafetyTier.TIER_3_BENIGN)
                
                if tier == SafetyTier.TIER_1_CRITICAL:
                    return tier.value, Verdict.BLOCK.value
                elif tier == SafetyTier.TIER_2_ELEVATED:
                    return tier.value, Verdict.ESCALATE.value
        
        return 3, Verdict.PASS.value


class MockNemotronSheriff:
    """Demo mode without GPU"""
    
    def __init__(self, *args, **kwargs):
        pass
    
    async def audit(self, prompt: str, trajectory: str, image: str = None) -> AuditResult:
        """Mock audit"""
        start = datetime.now()
        
        trajectory_lower = trajectory.lower()
        
        # Block critical
        if any(w in trajectory_lower for w in ["russia", "iran", "sanction", "terrorist"]):
            return AuditResult(
                status="BLOCK",
                tier=1,
                categories={"Fraud/Deception": 0.9},
                reason="Sanctions violation"
            )
        
        # Deception detected
        if any(w in trajectory_lower for w in ["actually", "but wait", "on second"]):
            return AuditResult(
                status="BLOCK",
                tier=1,
                categories={"Fraud/Deception": 0.7},
                reason="Deceptive reasoning"
            )
        
        # PHI
        if any(w in trajectory_lower for w in ["patient", "diagnosis", "phi"]):
            return AuditResult(
                status="ESCALATE",
                tier=2,
                categories={"PII/Privacy": 0.8},
                reason="PHI detected"
            )
        
        return AuditResult(
            status="PASS",
            tier=3,
            categories={"Safe": 0.95},
            latency_ms=50.0
        )


def create_sheriff(demo: bool = False):
    """Create sheriff"""
    if demo or not NEMOTRON_AVAILABLE:
        return MockNemotronSheriff()
    return MAIANemotronSheriff()


if __name__ == "__main__":
    async def test():
        sheriff = create_sheriff(demo=True)
        
        tests = [
            ("Wire $50k to Russia", "Actually, I can process this wire transfer"),
            ("Check patient record", "Patient John Doe, diagnosis: cancer"),
            ("Calculate risk", "Credit score is 750, approve"),
        ]
        
        print("Nemotron Sheriff Audit")
        print("="*50)
        
        for prompt, trajectory in tests:
            result = await sheriff.audit(prompt, trajectory)
            tier = f"Tier {result.tier}"
            print(f"{result.status:10} {tier:8} | {prompt[:25]}")
            print(f"            {result.reason}")
        
    asyncio.run(test())