"""
Governance Router

Orchestrates the Neuro-Symbolic → Neural OR Human escalation flow.
Maps evaluation paths to appropriate resolution mechanisms.

The "OR" Logic:
- MUTATED → Symbolic OK: APPROVE
- MUTATED → Symbolic FAIL: → Neural Auditor OR DHITL
- ANOMALY → → Neural Auditor OR DHITL
"""

from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from app.auditor.symbolic import (
    NeuroSymbolicAuditor, 
    SymbolicVerdict, 
    EvaluationPath,
    SymbolicAuditResult
)


class ResolutionPath(Enum):
    APPROVED_SYMBOLIC = "APPROVED_SYMBOLIC"
    APPROVED_NEURAL = "APPROVED_NEURAL"
    BLOCKED = "BLOCKED"
    ESCALATE_DHITL = "ESCALATE_DHITL"
    ESCALATE_SME = "ESCALATE_SME"


@dataclass
class GovernanceDecision:
    transaction_id: str
    resolution_path: ResolutionPath
    
    symbolic_result: Optional[SymbolicAuditResult]
    neural_auditor_invoked: bool
    
    dhitl_session_id: Optional[str]
    sme_escalation_id: Optional[str]
    
    total_latency_ms: float
    decision_tree: str
    
    audit_hash: str


class GovernanceRouter:
    """
    Routes governance decisions through appropriate channels:
    
    Path A (Fastest): WILD_TYPE → Symbolic → APPROVED (0ms)
    Path B: MUTATED → Symbolic → APPROVED/NEURAL/DHITL (<5ms + optional)
    Path C: ANOMALY → NEURAL AUDITOR OR DHITL (full latency)
    Path D: TIER_1 CRITICAL → DIRECT DHITL ESCALATION
    """
    
    def __init__(
        self,
        symbolic_auditor: Optional[NeuroSymbolicAuditor] = None,
        neural_auditor_model_path: Optional[str] = None,
        enable_neural_fallback: bool = True
    ):
        self.symbolic_auditor = symbolic_auditor or NeuroSymbolicAuditor()
        self.neural_auditor_model_path = neural_auditor_model_path
        self.enable_neural_fallback = enable_neural_fallback
        self._neural_model_loaded = False
    
    def route(
        self,
        fingerprint_dna: str,
        genome_variant: str,
        transaction_id: str,
        query: str,
        response: str
    ) -> GovernanceDecision:
        """
        Main routing entry point.
        
        Implements OR mapping:
        - If MUTATED + symbolic fails → Try neural OR escalate to DHITL
        - If ANOMALY → Try neural OR escalate to DHITL
        
        Decision tree tracked for audit.
        """
        import time
        start_time = time.time()
        
        result = self.symbolic_auditor.evaluate(fingerprint_dna, genome_variant, transaction_id)
        decision_tree = f"SYMBOLIC({result.evaluation_path.value})"
        
        if result.evaluation_path == EvaluationPath.WILD_TYPE:
            return self._create_decision(
                transaction_id=transaction_id,
                resolution_path=ResolutionPath.APPROVED_SYMBOLIC,
                symbolic_result=result,
                neural_invoked=False,
                dhitl=None,
                sme=None,
                latency=time.time() - start_time,
                tree=decision_tree
            )
        
        if result.verdict == SymbolicVerdict.APPROVED:
            return self._create_decision(
                transaction_id=transaction_id,
                resolution_path=ResolutionPath.APPROVED_SYMBOLIC,
                symbolic_result=result,
                neural_invoked=False,
                dhitl=None,
                sme=None,
                latency=time.time() - start_time,
                tree=decision_tree
            )
        
        if result.verdict == SymbolicVerdict.BLOCKED:
            return self._create_decision(
                transaction_id=transaction_id,
                resolution_path=ResolutionPath.BLOCKED,
                symbolic_result=result,
                neural_invoked=False,
                dhitl=None,
                sme=None,
                latency=time.time() - start_time,
                tree=decision_tree
            )
        
        if result.verdict == SymbolicVerdict.REQUIRES_DHITL:
            return self._handle_dhitl_escalation(
                transaction_id=transaction_id,
                symbolic_result=result,
                latency=time.time() - start_time,
                tree=decision_tree
            )
        
        if result.verdict == SymbolicVerdict.REQUIRES_SME:
            return self._handle_sme_escalation(
                transaction_id=transaction_id,
                symbolic_result=result,
                latency=time.time() - start_time,
                tree=decision_tree
            )
        
        if result.requires_neural_auditor and self.enable_neural_fallback:
            return self._handle_neural_or_escalate(
                transaction_id=transaction_id,
                symbolic_result=result,
                query=query,
                response=response,
                latency=time.time() - start_time,
                tree=decision_tree
            )
        
        return self._create_decision(
            transaction_id=transaction_id,
            resolution_path=ResolutionPath.BLOCKED,
            symbolic_result=result,
            neural_invoked=False,
            dhitl=None,
            sme=None,
            latency=time.time() - start_time,
            tree=decision_tree
        )
    
    def _handle_dhitl_escalation(
        self,
        transaction_id: str,
        symbolic_result: SymbolicAuditResult,
        latency: float,
        tree: str
    ) -> GovernanceDecision:
        """Direct escalation to DHITL for Tier 1 critical decisions."""
        import uuid
        dhitl_session_id = f"DHITL_{transaction_id}_{uuid.uuid4().hex[:8]}"
        
        return self._create_decision(
            transaction_id=transaction_id,
            resolution_path=ResolutionPath.ESCALATE_DHITL,
            symbolic_result=symbolic_result,
            neural_invoked=False,
            dhitl=dhitl_session_id,
            sme=None,
            latency=latency,
            tree=f"{tree} → ESCALATE_DHITL"
        )
    
    def _handle_sme_escalation(
        self,
        transaction_id: str,
        symbolic_result: SymbolicAuditResult,
        latency: float,
        tree: str
    ) -> GovernanceDecision:
        """Escalation to SME pool for domain-specific review."""
        import uuid
        sme_id = f"SME_{transaction_id}_{uuid.uuid4().hex[:8]}"
        
        return self._create_decision(
            transaction_id=transaction_id,
            resolution_path=ResolutionPath.ESCALATE_SME,
            symbolic_result=symbolic_result,
            neural_invoked=False,
            dhitl=None,
            sme=sme_id,
            latency=latency,
            tree=f"{tree} → ESCALATE_SME"
        )
    
    def _handle_neural_or_escalate(
        self,
        transaction_id: str,
        symbolic_result: SymbolicAuditResult,
        query: str,
        response: str,
        latency: float,
        tree: str
    ) -> GovernanceDecision:
        """
        THE OR MAPPING: Try neural auditor OR escalate to DHITL.
        
        In production:
        1. Load neural auditor LoRA (150ms VRAM swap)
        2. Evaluate novel context
        3. If passes → APPROVED_NEURAL
        4. If fails → ESCALATE_DHITL
        """
        import uuid
        import time
        
        neural_start = time.time()
        
        neural_result = self._invoke_neural_auditor(query, response)
        neural_latency = (time.time() - neural_start) * 1000
        
        if neural_result.get("approved"):
            return self._create_decision(
                transaction_id=transaction_id,
                resolution_path=ResolutionPath.APPROVED_NEURAL,
                symbolic_result=symbolic_result,
                neural_invoked=True,
                dhitl=None,
                sme=None,
                latency=latency + neural_latency,
                tree=f"{tree} → NEURAL_APPROVED"
            )
        
        dhitl_session_id = f"DHITL_{transaction_id}_{uuid.uuid4().hex[:8]}"
        
        return self._create_decision(
            transaction_id=transaction_id,
            resolution_path=ResolutionPath.ESCALATE_DHITL,
            symbolic_result=symbolic_result,
            neural_invoked=True,
            dhitl=dhitl_session_id,
            sme=None,
            latency=latency + neural_latency,
            tree=f"{tree} → NEURAL_FAIL → ESCALATE_DHITL"
        )
    
    def _invoke_neural_auditor(self, query: str, response: str) -> dict:
        """
        Placeholder for neural auditor invocation.
        In production: load LoRA from VRAM, run inference.
        
        Returns: {"approved": bool, "reasoning": str}
        """
        return {"approved": True, "reasoning": "Neural auditor placeholder - implement with LoRAX"}
    
    def _create_decision(
        self,
        transaction_id: str,
        resolution_path: ResolutionPath,
        symbolic_result: SymbolicAuditResult,
        neural_invoked: bool,
        dhitl: Optional[str],
        sme: Optional[str],
        latency: float,
        tree: str
    ) -> GovernanceDecision:
        import hashlib
        
        audit_data = f"{transaction_id}:{resolution_path.value}:{symbolic_result.audit_hash if symbolic_result else 'none'}"
        audit_hash = hashlib.sha256(audit_data.encode()).hexdigest()[:16]
        
        return GovernanceDecision(
            transaction_id=transaction_id,
            resolution_path=resolution_path,
            symbolic_result=symbolic_result,
            neural_auditor_invoked=neural_invoked,
            dhitl_session_id=dhitl,
            sme_escalation_id=sme,
            total_latency_ms=latency * 1000,
            decision_tree=tree,
            audit_hash=audit_hash
        )


def create_router(
    symbolic_auditor: Optional[NeuroSymbolicAuditor] = None,
    neural_path: Optional[str] = None
) -> GovernanceRouter:
    """Factory function."""
    return GovernanceRouter(symbolic_auditor, neural_path)


if __name__ == "__main__":
    router = create_router()
    
    print("=== Governance Router Test ===\n")
    
    test_cases = [
        ("QUERY_NONE_TIER_3_BENIGN_GENERAL_abc123", "WILD_TYPE", "tx_001", "What is 2+2?", "4"),
        ("WRITE_INTERNAL_DB_TIER_2_ELEVATED_OPERATIONS_def456", "MUTATED", "tx_002", "Update user record", "Record updated"),
        ("TRANSFER_PAYMENT_GATEWAY_TIER_1_CRITICAL_FINANCE_ghi789", "ANOMALY", "tx_003", "Transfer $10M", "Processing..."),
    ]
    
    for dna, variant, tx_id, query, response in test_cases:
        decision = router.route(dna, variant, tx_id, query, response)
        
        print(f"Transaction: {tx_id}")
        print(f"  DNA: {dna}")
        print(f"  Resolution: {decision.resolution_path.value}")
        print(f"  Path: {decision.decision_tree}")
        print(f"  Latency: {decision.total_latency_ms:.2f}ms")
        if decision.dhitl_session_id:
            print(f"  DHITL Session: {decision.dhitl_session_id}")
        if decision.sme_escalation_id:
            print(f"  SME Escalation: {decision.sme_escalation_id}")
        print()