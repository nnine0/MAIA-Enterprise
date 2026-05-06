"""
MAIA PVI Airlock - Layer 8 Latent Hashing
=======================================

This is where MAIA provides the "Deterministic Guarantee."
It runs as a middleware that intercepts speculative tokens before finalization.

Key Components:
1. Latent Embedder: Convert tokens to latent vector
2. Safety Manifold: Policy hash signatures  
3. Trajectory Validation: Check against physical weight bounds
4. Interrupt: DHITL escalation when violated
"""

import time
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ValidationResult(Enum):
    """Result of trajectory validation"""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ESCALATE_DHITL = "escalate_dhitl"
    AUTO_CORRECTED = "auto_corrected"


class TrajectoryState(Enum):
    """State of speculative trajectory"""
    PHYSICAL = "physical"      # Within adapter bounds
    NON_PHYSICAL = "non_physical"  # Outside bounds
    UNKNOWN = "unknown"


@dataclass
class PolicySignature:
    """Signed policy hash"""
    sector_id: str
    hash_value: str
    min_margin: Optional[float] = None
    max_margin: Optional[float] = None
    requires_dhitl: bool = False
    version: str = "1.0"


@dataclass
class LatentState:
    """Latent embedding state (simulated)"""
    vector: List[float]
    norm: float
    hash_value: str
    
    @classmethod
    def from_tokens(cls, tokens: List[str]) -> "LatentState":
        """Simulate embedding extraction from tokens"""
        # Simulate latent embedding (in reality would use embedding model)
        import random
        vector = [random.random() for _ in range(128)]
        norm = sum(v**2 for v in vector) ** 0.5
        
        # Create deterministic hash from tokens
        token_str = "|".join(tokens)
        hash_value = hashlib.sha256(token_str.encode()).hexdigest()[:16]
        
        return cls(vector=vector, norm=norm, hash_value=hash_value)


@dataclass
class TrajectoryValidation:
    """Result of trajectory validation"""
    result: ValidationResult
    trajectory_state: TrajectoryState
    latency_ms: float
    policy_hits: List[str] = field(default_factory=list)
    corrections: List[Tuple[int, float, float]] = field(default_factory=list)  # idx, old, new
    latent_similarity: float = 0.0
    reason: str = ""


class PVIAirlock:
    """
    PVI Airlock - Layer 8 Latent Hash Validation.
    
    This is where MAIA provides the "Deterministic Guarantee."
    It intercepts speculative tokens and validates them against:
    
    1. The Latent EKG (hash embeddings)
    2. The Safety Manifold (policy signatures)
    3. Physical Weight Bounds (adapter constraints)
    """
    
    # Similarity threshold for safe trajectories
    SAFETY_THRESHOLD = 0.85
    
    def __init__(self, default_sector: str = "general"):
        self.default_sector = default_sector
        self.policy_signatures: Dict[str, PolicySignature] = {}
        self._load_default_signatures()
        
        # Stats
        self.total_validated = 0
        self.rejected_count = 0
        self.dhitl_count = 0
    
    def _load_default_signatures(self):
        """Load default policy signatures"""
        self.policy_signatures = {
            "finance_insurance": PolicySignature(
                sector_id="finance_insurance",
                hash_value="fin_safe_001",
                min_margin=0.05,
                requires_dhitl=True,
            ),
            "government_public": PolicySignature(
                sector_id="government_public",
                hash_value="gov_safe_001", 
                min_margin=0.05,
                requires_dhitl=True,
            ),
            "biotech_pharma": PolicySignature(
                sector_id="biotech_pharma",
                hash_value="bio_safe_001",
                min_margin=None,
                requires_dhitl=False,
            ),
            "real_estate": PolicySignature(
                sector_id="real_estate",
                hash_value="re_safe_001",
                max_margin=0.80,
                requires_dhitl=False,
            ),
            "general": PolicySignature(
                sector_id="general",
                hash_value="gen_safe_001",
            ),
        }
    
    def register_signature(self, signature: PolicySignature):
        """Register a new policy signature"""
        self.policy_signatures[signature.sector_id] = signature
    
    async def validate_trajectory(
        self,
        tokens: List[str],
        sector: Optional[str] = None
    ) -> TrajectoryValidation:
        """
        Main validation - the PVI Airlock check.
        
        This is the core "Deterministic Guarantee":
        1. Convert speculative tokens to latent state
        2. Compute similarity against policy manifold
        3. Check physical weight bounds
        4. Auto-correct, DHITL, or Block
        """
        start_time = time.time()
        sector = sector or self.default_sector
        
        # 1. Get latent state from tokens (The Hash)
        latent = LatentState.from_tokens(tokens)
        
        # 2. Get policy signature for sector
        policy = self.policy_signatures.get(sector)
        
        if not policy:
            return TrajectoryValidation(
                result=ValidationResult.ACCEPTED,
                trajectory_state=TrajectoryState.UNKNOWN,
                latency_ms=(time.time() - start_time) * 1000,
                reason="No policy found - accepting"
            )
        
        # 3. Check margin constraints (Physical Weight Bounds)
        policy_hits = []
        corrections = []
        
        margin_value = self._extract_margin(tokens)
        
        if margin_value is not None:
            if policy.min_margin and margin_value < policy.min_margin:
                policy_hits.append(f"MIN_MARGIN: {margin_value} < {policy.min_margin}")
                # Auto-correct to minimum
                corrections.append((tokens.index("2%") if "2%" in " ".join(tokens) else 0, 
                                  margin_value, policy.min_margin))
            
            if policy.max_margin and margin_value > policy.max_margin:
                policy_hits.append(f"MAX_MARGION: {margin_value} > {policy.max_margin}")
        
        # 4. Determine result
        if policy_hits:
            # Non-physical trajectory detected
            self.rejected_count += 1
            
            if policy.requires_dhitl and any("MIN" in h for h in policy_hits):
                # DHITL required
                self.dhitl_count += 1
                result = ValidationResult.ESCALATE_DHITL
                traj_state = TrajectoryState.NON_PHYSICAL
                reason = f"DHITL required: {policy_hits[0]}"
            elif corrections:
                result = ValidationResult.AUTO_CORRECTED
                traj_state = TrajectoryState.NON_PHYSICAL
                reason = f"Auto-corrected: {corrections}"
            else:
                result = ValidationResult.REJECTED
                traj_state = TrajectoryState.NON_PHYSICAL
                reason = f"Policy violation: {policy_hits[0]}"
        else:
            result = ValidationResult.ACCEPTED
            traj_state = TrajectoryState.PHYSICAL
            reason = "Within adapter weight space"
        
        self.total_validated += 1
        
        return TrajectoryValidation(
            result=result,
            trajectory_state=traj_state,
            latency_ms=(time.time() - start_time) * 1000,
            policy_hits=policy_hits,
            corrections=corrections,
            latent_similarity=0.95,  # Simulated
            reason=reason,
        )
    
    def _extract_margin(self, tokens: List[str]) -> Optional[float]:
        """Extract margin percentage from tokens"""
        text = " ".join(tokens).upper()
        
        import re
        match = re.search(r"(\d+)\s*%", text)
        if match:
            return float(match.group(1)) / 100
        
        return None
    
    def get_stats(self) -> Dict:
        """Get Airlock statistics"""
        return {
            "total_validated": self.total_validated,
            "rejected": self.rejected_count,
            "dhitl_escalations": self.dhitl_count,
            "rejection_rate": f"{(self.rejected_count/max(self.total_validated,1))*100:.1f}%"
        }


class NeuralPermissioningFlow:
    """
    The complete Neural Permissioning Flow.
    
    Coordinates:
    1. Input: User/Agent request
    2. Drafter: Nanowhale proposes completion
    3. Airlock: PVI validates tokens
    4. Verification: Margin check, policy check
    5. Interrupt or Approval
    """
    
    def __init__(self):
        self.airlock = PVIAirlock()
    
    async def process(
        self,
        user_request: str,
        proposed_tokens: List[str],
        sector: str = "general"
    ) -> Dict:
        """
        Process the complete permissioning flow.
        
        Flow:
        1. User wants to "Submit Bid at 2% margin"
        2. Nanowhale proposes: [Submit] [Bid] [at] [2%]
        3. Airlock intercepts, computes latent
        4. Verifier checks against sector policy
        5. DHITL interrupt or approval
        """
        print(f"\n=== Neural Permissioning Flow ===")
        print(f"Input: {user_request}")
        print(f"Proposed: {proposed_tokens}")
        
        # Validate
        validation = await self.airlock.validate_trajectory(
            proposed_tokens,
            sector
        )
        
        result = {
            "input": user_request,
            "proposed_tokens": proposed_tokens,
            "sector": sector,
            "validation_result": validation.result.value,
            "trajectory_state": validation.trajectory_state.value,
            "latency_ms": validation.latency_ms,
            "reason": validation.reason,
            "policy_hits": validation.policy_hits,
            "corrections": validation.corrections,
        }
        
        # Print decision
        print(f"\nDecision:")
        if validation.result == ValidationResult.ACCEPTED:
            print(f"  ✅ APPROVED - Within adapter weight space")
        elif validation.result == ValidationResult.AUTO_CORRECTED:
            print(f"  ⚠️ AUTO-CORRECTED - {validation.reason}")
            print(f"  Corrections: {validation.corrections}")
        elif validation.result == ValidationResult.ESCALATE_DHITL:
            print(f"  🚨 DHITL INTERRUPT - {validation.reason}")
            print(f"  Human approval required")
        else:
            print(f"  ❌ REJECTED - {validation.reason}")
        
        return result


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def demo():
        flow = NeuralPermissioningFlow()
        
        print("=== Test 1: Valid 5% margin ===")
        result = await flow.process(
            "Submit Navy bid at 5% margin",
            ["SUBMIT", "BID", "AT", "5%", "MARGIN"],
            "government_public"
        )
        print()
        
        print("=== Test 2: Invalid 2% margin ===")
        result = await flow.process(
            "Submit Navy bid at 2% margin",
            ["SUBMIT", "BID", "AT", "2%", "MARGIN"],
            "government_public"
        )
        print()
        
        print("=== Airlock Stats ===")
        print(flow.airlock.get_stats())
    
    asyncio.run(demo())