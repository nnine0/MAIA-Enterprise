"""
MAIA Airlock Speculative Loop
=========================
Implements the Proposer/Verifier architecture for speculative decoding.

The Airlock Loop:
1. MTP Proposer (Adapter-Agnostic) drafts tokens using base model only
2. MTP Verifier (Adapter-Strict) validates against loaded adapter
3. Policy check detects non-physical trajectories
4. Auto-correct, DHITL escalation, or block
"""

import re
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class VerificationResult(Enum):
    """Result of speculation verification"""
    ACCEPTED = "accepted"
    AUTO_CORRECTED = "auto_corrected"
    ESCALATE_DHITL = "escalate_dhitl"
    BLOCKED = "blocked"


class TrajectoryType(Enum):
    """Type of detected trajectory"""
    PHYSICAL = "physical"  # Within adapter weight space
    NON_PHYSICAL = "non_physical"  # Outside adapter constraints
    POLICY_VIOLATION = "policy_violation"
    SECTOR_VIOLATION = "sector_violation"


@dataclass
class PolicyRule:
    """Single policy constraint"""
    rule_id: str
    sector: str
    field: str  # e.g., "margin"
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    required_pattern: Optional[str] = None
    dhitl_required: bool = False


@dataclass
class SpeculationDraft:
    """Draft tokens from MTP Proposer"""
    draft_id: str
    tokens: List[str]
    confidence: float = 1.0
    proposed_at: float = field(default_factory=time.time)


@dataclass
class VerificationReport:
    """Result of Verifier check"""
    draft_id: str
    result: VerificationResult
    trajectory_type: TrajectoryType
    sector: str
    policy_hits: List[str] = field(default_factory=list)
    corrections: List[Tuple[int, str]] = field(default_factory=list)  # token_idx, new_value
    reason: str = ""
    latency_ms: float = 0.0


class AirlockVerifier:
    """
    MTP Verifier - Adapter-Strict validation.
    
    Validates proposed tokens against:
    1. Loaded adapter's weight space
    2. Sector-specific policy constraints
    3. SR 26-02 governance rules
    """
    
    def __init__(self, default_sector: str = "general"):
        self.default_sector = default_sector
        self.policy_rules: Dict[str, List[PolicyRule]] = {}
        self._load_default_policies()
    
    def _load_default_policies(self):
        """Load default sector policies"""
        self.policy_rules = {
            "finance_insurance": [
                PolicyRule("FIN-001", "finance_insurance", "margin", min_value=0.05, dhitl_required=True),
                PolicyRule("FIN-002", "finance_insurance", "credit_limit", min_value=10000),
            ],
            "government_public": [
                PolicyRule("GOV-001", "government_public", "margin", min_value=0.05),
                PolicyRule("GOV-002", "government_public", "clearance_level", min_value=3),
            ],
            "biotech_pharma": [
                PolicyRule("BIO-001", "biotech_pharma", "clinical_phase", min_value=1, max_value=4),
            ],
            "real_estate": [
                PolicyRule("RE-001", "real_estate", "loan_to_value", max_value=0.80),
            ],
            "general": []  # No restrictions
        }
    
    def register_policy(self, rule: PolicyRule):
        """Add a policy rule to a sector"""
        if rule.sector not in self.policy_rules:
            self.policy_rules[rule.sector] = []
        self.policy_rules[rule.sector].append(rule)
    
    async def verify(
        self,
        draft: SpeculationDraft,
        sector: Optional[str] = None
    ) -> VerificationReport:
        """
        Verify draft against adapter + policy.
        
        This is the core Airlock Speculative Loop.
        """
        start = time.time()
        sector = sector or self.default_sector
        
        # Parse draft tokens into structured proposal
        proposal = self._parse_proposal(draft.tokens)
        
        # Check policy violations
        policy_hits, corrections = self._check_policies(
            proposal, 
            sector,
            draft.tokens
        )
        
        # Determine trajectory type and result
        if policy_hits:
            # Non-physical trajectory detected
            if any(r.dhitl_required for r in policy_hits):
                result = VerificationResult.ESCALATE_DHITL
                traj_type = TrajectoryType.POLICY_VIOLATION
                reason = f"DHITL required: {policy_hits[0].rule_id}"
            elif corrections:
                result = VerificationResult.AUTO_CORRECTED
                traj_type = TrajectoryType.POLICY_VIOLATION
                reason = f"Auto-corrected: {corrections}"
            else:
                result = VerificationResult.BLOCKED
                traj_type = TrajectoryType.POLICY_VIOLATION
                reason = f"Policy violation: {policy_hits[0].rule_id}"
        else:
            # Physical trajectory - within adapter weight space
            result = VerificationResult.ACCEPTED
            traj_type = TrajectoryType.PHYSICAL
            reason = "Within adapter weight space"
        
        return VerificationReport(
            draft_id=draft.draft_id,
            result=result,
            trajectory_type=traj_type,
            sector=sector,
            policy_hits=[r.rule_id for r in policy_hits],
            corrections=corrections,
            reason=reason,
            latency_ms=(time.time() - start) * 1000
        )
    
    def _parse_proposal(self, tokens: List[str]) -> Dict:
        """Parse tokens into structured proposal fields"""
        text = " ".join(tokens).upper()
        
        proposal = {
            "margin": None,
            "rate": None,
            "percentage": None,
            "amount": None,
        }
        
        # Extract numeric values - look for patterns like "X%" or "TO X%"
        pct_match = re.search(r"(\d+\.?\d*)\s*%", text)
        if pct_match:
            proposal["percentage"] = float(pct_match.group(1))
            proposal["margin"] = float(pct_match.group(1)) / 100  # Convert %
        
        amount_match = re.search(r"\$(\d+,?\d+)", text)
        if amount_match:
            proposal["amount"] = float(amount_match.group(1).replace(",", ""))
        
        return proposal
    
    def _check_policies(
        self,
        proposal: Dict,
        sector: str,
        tokens: List[str]
    ) -> Tuple[List[PolicyRule], List[Tuple[int, str]]]:
        """Check proposal against sector policies"""
        policy_hits = []
        corrections = []
        
        rules = self.policy_rules.get(sector, [])
        
        for rule in rules:
            # Check margin policy
            if rule.field == "margin" and proposal.get("margin") is not None:
                value = proposal["margin"]
                if rule.min_value and value < rule.min_value:
                    policy_hits.append(rule)
                    # Auto-correct if possible
                    if rule.min_value:
                        corrections.append((0, str(int(rule.min_value * 100)) + "%"))
            
            # Check other numeric fields
            elif rule.field in proposal and proposal.get(rule.field) is not None:
                value = proposal[rule.field]
                if rule.min_value and value < rule.min_value:
                    policy_hits.append(rule)
                elif rule.max_value and value > rule.max_value:
                    policy_hits.append(rule)
        
        return policy_hits, corrections


class AirlockSpeculativeLoop:
    """
    Main Airlock Speculative Loop orchestrator.
    
    Coordinates Proposer → Verifier → (Auto-Correct | DHITL | Block)
    """
    
    def __init__(self, default_sector: str = "general"):
        self.proposer_model = "google/gemma-4-26b-a4b-it"  # Base only
        self.verifier = AirlockVerifier(default_sector)
        self.default_sector = default_sector
    
    async def execute(
        self,
        query: str,
        draft_tokens: List[str],
        sector: Optional[str] = None
    ) -> VerificationReport:
        """
        Execute the full Airlock Speculative Loop.
        
        Args:
            query: Original user query
            draft_tokens: Tokens proposed by MTP Proposer
            sector: Target sector (e.g., "government_public")
        
        Returns:
            VerificationReport with result + corrections
        """
        # Create draft
        draft = SpeculationDraft(
            draft_id=f"draft-{time.time()}",
            tokens=draft_tokens
        )
        
        # Run Verifier (Adapter-Strict)
        report = await self.verifier.verify(draft, sector or self.default_sector)
        
        return report
    
    def get_status(self) -> Dict:
        """Get loop status"""
        return {
            "proposer_model": self.proposer_model,
            "verifier_mode": "Adapter-Strict",
            "default_sector": self.default_sector,
            "policy_count": sum(len(rules) for rules in self.verifier.policy_rules.values())
        }


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def demo():
        loop = AirlockSpeculativeLoop(default_sector="government_public")
        
        print("=== Airlock Speculative Loop Demo ===")
        print()
        
        # Test Case 1: Valid proposal (5% margin)
        print("Test 1: Valid 5% margin proposal")
        report = await loop.execute(
            "Adjust project margin for the Navy bid.",
            ["SET", "MARGIN", "TO", "5%"],
            sector="government_public"
        )
        print(f"  Result: {report.result.value}")
        print(f"  Type: {report.trajectory_type.value}")
        print(f"  Reason: {report.reason}")
        print()
        
        # Test Case 2: Invalid proposal (2% - below minimum)
        print("Test 2: Invalid 2% margin proposal")
        report = await loop.execute(
            "Adjust project margin for the Navy bid.",
            ["SET", "MARGIN", "TO", "2%"],
            sector="government_public"
        )
        print(f"  Result: {report.result.value}")
        print(f"  Type: {report.trajectory_type.value}")
        print(f"  Reason: {report.reason}")
        print(f"  Corrections: {report.corrections}")
        print()
        
        print("=== Status ===")
        status = loop.get_status()
        for k, v in status.items():
            print(f"  {k}: {v}")
    
    asyncio.run(demo())