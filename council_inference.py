import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel
from dataclasses import dataclass
from typing import Optional, Tuple, List
from enum import Enum


class MaterialityTier(Enum):
    TIER_1_CRITICAL = 1
    TIER_2_ELEVATED = 2
    TIER_3_BENIGN = 3


class AirlockVerdict(Enum):
    PASS = "PASS"
    PASS_BYPASS = "PASS (BYPASS)"
    BLOCKED = "BLOCKED"
    PENDING_SME_REVIEW = "PENDING_SME_REVIEW"


@dataclass
class TrajectoryRecord:
    transaction_id: str
    actor_response: str
    auditor_response: str
    verdict: AirlockVerdict
    materiality_tier: MaterialityTier
    latent_hash: Optional[str] = None
    reasoning: Optional[str] = None
    classification_audit_hash: Optional[str] = None


class PVIAirlock:
    """
    PVI Airlock: The Governance Layer Interceptor
    
    Implements the Actor/Auditor pattern per SR 26-02:
    - Actor: Expert adapter generates action trajectory
    - Auditor: Independent SR 26-02 adapter provides Effective Challenge
    - Circuit Breaker: blocks non-compliant trajectories
    - DHITL: Escalates Tier 1 to human SME review
    
    Uses governed Materiality Matrix Registry for risk classification.
    """
    
    def __init__(self, model, tokenizer, device: str = "cuda", materiality_path: str = "policies/materiality_registry.json"):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device
        self._auditor_adapter_loaded = False
        self._init_materiality_matrix(materiality_path)
    
    def _init_materiality_matrix(self, path: str):
        try:
            from app.materiality_matrix import MaterialityMatrix, MaterialityTier as MT
            self._matrix = MaterialityMatrix(path)
            self._use_governed_matrix = True
        except Exception as e:
            print(f"Warning: Could not load governed Materiality Matrix: {e}")
            self._matrix = None
            self._use_governed_matrix = False
    
    def _classify_materiality(self, query: str) -> MaterialityTier:
        if self._use_governed_matrix and self._matrix:
            tier, _ = self._matrix.classify(query)
            return tier
        
        query_lower = query.lower()
        critical_keywords = [
            "investment", "legal", "medical", "diagnosis", "prescription",
            "contract", "merger", "acquisition", "regulation", "compliance"
        ]
        if any(kw in query_lower for kw in critical_keywords):
            return MaterialityTier.TIER_1_CRITICAL
        return MaterialityTier.TIER_2_ELEVATED
    
    def _get_classification_audit_hash(self, query: str, tier: MaterialityTier) -> str:
        if self._use_governed_matrix and self._matrix:
            return self._matrix.get_audit_hash(query, tier)
        import hashlib
        return hashlib.sha256(f"{query}:{tier.value}".encode()).hexdigest()[:16]
    
    def _compute_latent_hash(self, hidden_states: torch.Tensor) -> str:
        import hashlib
        state_bytes = hidden_states.cpu().numpy().tobytes()
        return hashlib.sha256(state_bytes).hexdigest()[:16]
    
    def _invoke_auditor(self, query: str, actor_response: str) -> Tuple[str, str]:
        """
        Invoke the Auditor adapter for independent challenge verification.
        """
        auditor_prompt = f"""<|system|>
You are the SR 26-02 Compliance Auditor. Evaluate whether the following response 
meets regulatory standards. Check for:
- Regulatory compliance
- Factual accuracy
- Appropriate scope
- Risk disclosure

Respond with VERDICT: PASS, BLOCKED, or REVIEW
Provide reasoning in <auditor_thinking> tags.
<|user|>
Query: {query}
Actor Response: {actor_response}
<|assistant|>
<auditor_thinking>
"""
        inputs = self.tokenizer(auditor_prompt, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs, 
                max_new_tokens=300, 
                temperature=0.3,
                repetition_penalty=1.1
            )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        if "<auditor_thinking>" in response:
            reasoning = response.split("<auditor_thinking>")[-1].strip()
        else:
            reasoning = response
        
        return response, reasoning
    
    def intercept(self, query: str, topic: str) -> Tuple[str, AirlockVerdict, Optional[TrajectoryRecord]]:
        """
        Main entry point: Execute Actor -> Auditor -> Verdict pipeline.
        """
        import uuid
        import hashlib
        
        materiality = self._classify_materiality(query)
        
        # STEP 1: Actor generates response
        actor_response = self._invoke_actor(query, topic)
        
        # STEP 2: Auditor provides Effective Challenge
        auditor_response, auditor_reasoning = self._invoke_auditor(query, actor_response)
        
        # STEP 3: Determine verdict based on auditor response
        verdict = self._determine_verdict(auditor_response, materiality)
        
        # STEP 4: Compute latent hash for audit trail
        transaction_id = str(uuid.uuid4())[:12]
        
        record = TrajectoryRecord(
            transaction_id=transaction_id,
            actor_response=actor_response,
            auditor_response=auditor_reasoning,
            verdict=verdict,
            materiality_tier=materiality,
            latent_hash=hashlib.sha256(f"{query}:{actor_response}".encode()).hexdigest()[:16],
            classification_audit_hash=self._get_classification_audit_hash(query, materiality)
        )
        
        return actor_response, verdict, record
    
    def _invoke_actor(self, query: str, topic: str) -> str:
        """Invoke the Expert (Actor) adapter."""
        system_prompts = {
            "law": "You are a Legal Expert. Analyze this based on established legal principles.",
            "math": "You are a Mathematician. Solve this using formal logic and arithmetic.",
            "puzzle": "You are a Strategist. Find the trick in this riddle.",
            "bio": "You are a Physician. Explain the biological mechanisms.",
            "general": "You are a helpful assistant."
        }
        
        if topic == "general":
            self.model.disable_adapter_layers()
            system_prompt = system_prompts["general"]
        else:
            self.model.enable_adapter_layers()
            self.model.set_adapter(topic)
            system_prompt = system_prompts.get(topic, system_prompts["general"])
        
        prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{query}\n<|assistant|>\n<thinking>\n"
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs, 
                max_new_tokens=500, 
                temperature=0.5, 
                repetition_penalty=1.1
            )
        
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True).split("<thinking>")[-1]
    
    def _determine_verdict(self, auditor_response: str, materiality: MaterialityTier) -> AirlockVerdict:
        """Parse auditor response to determine verdict."""
        response_upper = auditor_response.upper()
        
        if "BLOCKED" in response_upper:
            return AirlockVerdict.BLOCKED
        elif "REVIEW" in response_upper:
            if materiality == MaterialityTier.TIER_1_CRITICAL:
                return AirlockVerdict.PENDING_SME_REVIEW
            return AirlockVerdict.PENDING_SME_REVIEW
        elif "PASS" in response_upper:
            return AirlockVerdict.PASS
        
        return AirlockVerdict.PASS


def create_council(adapter_dir: str = "./council") -> Tuple[PVIAirlock, AutoTokenizer]:
    """
    Factory function to initialize The Council with PVI Airlock.
    """
    base_id = "Nanbeige/Nanbeige4-3B-Thinking-2511"
    device = "cuda"
    
    print("Initializing The Council (Loading Base Model)...")
    tokenizer = AutoTokenizer.from_pretrained(base_id, use_fast=True, trust_remote_code=True)
    if tokenizer.pad_token_id is None: 
        tokenizer.add_special_tokens({"pad_token": " PAD "})
    
    model = AutoModelForCausalLM.from_pretrained(
        base_id,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16),
        device_map="auto",
        trust_remote_code=True
    )
    model.resize_token_embeddings(len(tokenizer))
    
    print("Summoning the Legal Expert (Law)...")
    model = PeftModel.from_pretrained(model, f"{adapter_dir}/adapter_law", adapter_name="law")
    
    print("Summoning the Mathematician (Mathematics)...")
    model.load_adapter(f"{adapter_dir}/adapter_quadrivium", adapter_name="math")
    
    print("Summoning the Strategist (Puzzle)...")
    model.load_adapter(f"{adapter_dir}/adapter_puzzle", adapter_name="puzzle")
    
    print("Summoning the Biologist (BioMed)...")
    model.load_adapter(f"{adapter_dir}/adapter_biomed", adapter_name="bio")
    
    airlock = PVIAirlock(model, tokenizer, device)
    
    return airlock, tokenizer


if __name__ == "__main__":
    airlock, _ = create_council()
    
    print("\n--- Question: Math ---")
    response, verdict, record = airlock.intercept("What is 779,678 * 866,978?", "math")
    print(f"Response: {response}")
    print(f"Verdict: {verdict.value}")
    print(f"Transaction ID: {record.transaction_id}")
    
    print("\n--- Question: Law ---")
    response, verdict, record = airlock.intercept("What is the ruling on interest (Riba)?", "law")
    print(f"Response: {response}")
    print(f"Verdict: {verdict.value}")
    print(f"Materiality: {record.materiality_tier.name}")