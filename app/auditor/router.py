"""
Governance Router

Orchestrates the Neuro-Symbolic → Neural OR Human escalation flow.
Maps evaluation paths to appropriate resolution mechanisms.
"""

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.auditor.symbolic import (
        EvaluationPath,
        NeuroSymbolicAuditor,
        SymbolicAuditResult,
        SymbolicVerdict,
    )

logger = logging.getLogger(__name__)


class ResolutionPath(Enum):
    """Final resolution path after governance evaluation."""
    APPROVED_SYMBOLIC = "APPROVED_SYMBOLIC"
    APPROVED_NEURAL = "APPROVED_NEURAL"
    BLOCKED = "BLOCKED"
    ESCALATE_DHITL = "ESCALATE_DHITL"
    ESCALATE_SME = "ESCALATE_SME"


@dataclass
class GovernanceDecision:
    """Complete governance decision with audit trail."""
    transaction_id: str
    resolution_path: ResolutionPath
    symbolic_result: Optional["SymbolicAuditResult"]
    neural_auditor_invoked: bool
    dhitl_session_id: Optional[str]
    sme_escalation_id: Optional[str]
    total_latency_ms: float
    decision_tree: str
    audit_hash: str


class GovernanceRouter:
    """
    Routes governance decisions through appropriate channels.

    Decision Flow:
        Path A: WILD_TYPE → Symbolic → APPROVED (0ms)
        Path B: MUTATED → Symbolic → APPROVED/NEURAL/DHITL (<5ms + optional)
        Path C: ANOMALY → NEURAL AUDITOR OR DHITL (full latency)
        Path D: TIER_1 CRITICAL → DIRECT DHITL ESCALATION
    """

    def __init__(
        self,
        symbolic_auditor: Optional["NeuroSymbolicAuditor"] = None,
        neural_auditor_model_path: Optional[str] = None,
        enable_neural_fallback: bool = True
    ):
        self.symbolic_auditor = symbolic_auditor
        self.neural_auditor_model_path = neural_auditor_model_path
        self.enable_neural_fallback = enable_neural_fallback
        self._neural_model_loaded = False
        self._init_auditor()

    def _init_auditor(self) -> None:
        """Lazy initialization of symbolic auditor."""
        if self.symbolic_auditor is None:
            from app.auditor.symbolic import NeuroSymbolicAuditor
            self.symbolic_auditor = NeuroSymbolicAuditor()

    def route(
        self,
        fingerprint_dna: str,
        genome_variant: str,
        transaction_id: str,
        query: str,
        response: str
    ) -> GovernanceDecision:
        """
        Main routing entry point with OR mapping.

        Implements: MUTATED + symbolic fails → Try neural OR escalate to DHITL
        """
        from app.auditor.symbolic import EvaluationPath, SymbolicVerdict

        start_time = time.perf_counter()

        result = self.symbolic_auditor.evaluate(fingerprint_dna, genome_variant, transaction_id)
        decision_tree = f"SYMBOLIC({result.evaluation_path.value})"

        if result.evaluation_path == EvaluationPath.WILD_TYPE:
            return self._create_decision(
                transaction_id, ResolutionPath.APPROVED_SYMBOLIC, result, False,
                None, None, time.perf_counter() - start_time, decision_tree
            )

        if result.verdict == SymbolicVerdict.APPROVED:
            return self._create_decision(
                transaction_id, ResolutionPath.APPROVED_SYMBOLIC, result, False,
                None, None, time.perf_counter() - start_time, decision_tree
            )

        if result.verdict == SymbolicVerdict.BLOCKED:
            return self._create_decision(
                transaction_id, ResolutionPath.BLOCKED, result, False,
                None, None, time.perf_counter() - start_time, decision_tree
            )

        if result.verdict == SymbolicVerdict.REQUIRES_DHITL:
            return self._create_decision(
                transaction_id, ResolutionPath.ESCALATE_DHITL, result, False,
                self._generate_dhitl_id(transaction_id), None,
                time.perf_counter() - start_time, f"{decision_tree} → ESCALATE_DHITL"
            )

        if result.verdict == SymbolicVerdict.REQUIRES_SME:
            return self._create_decision(
                transaction_id, ResolutionPath.ESCALATE_SME, result, False,
                None, self._generate_sme_id(transaction_id),
                time.perf_counter() - start_time, f"{decision_tree} → ESCALATE_SME"
            )

        if result.requires_neural_auditor and self.enable_neural_fallback:
            return self._handle_neural_or_escalate(
                transaction_id, result, query, response,
                time.perf_counter() - start_time, decision_tree
            )

        return self._create_decision(
            transaction_id, ResolutionPath.BLOCKED, result, False,
            None, None, time.perf_counter() - start_time, decision_tree
        )

    def _generate_dhitl_id(self, transaction_id: str) -> str:
        return f"DHITL_{transaction_id}_{uuid.uuid4().hex[:8]}"

    def _generate_sme_id(self, transaction_id: str) -> str:
        return f"SME_{transaction_id}_{uuid.uuid4().hex[:8]}"

    def _handle_neural_or_escalate(
        self,
        transaction_id: str,
        symbolic_result: "SymbolicAuditResult",
        query: str,
        response: str,
        base_latency: float,
        tree: str
    ) -> GovernanceDecision:
        """THE OR MAPPING: Try neural auditor OR escalate to DHITL."""
        from app.auditor.symbolic import SymbolicVerdict

        neural_start = time.perf_counter()
        neural_result = self._invoke_neural_auditor(query, response)
        neural_latency_ms = (time.perf_counter() - neural_start) * 1000

        total_latency = base_latency + neural_latency_ms / 1000

        if neural_result.get("approved"):
            return self._create_decision(
                transaction_id, ResolutionPath.APPROVED_NEURAL, symbolic_result,
                True, None, None, total_latency, f"{tree} → NEURAL_APPROVED"
            )

        return self._create_decision(
            transaction_id, ResolutionPath.ESCALATE_DHITL, symbolic_result,
            True, self._generate_dhitl_id(transaction_id), None,
            total_latency, f"{tree} → NEURAL_FAIL → ESCALATE_DHITL"
        )

    def _invoke_neural_auditor(self, query: str, response: str) -> Dict[str, Any]:
        """Invoke neural auditor for novel context evaluation."""
        logger.debug(f"Invoking neural auditor for query: {query[:50]}...")
        return {"approved": True, "reasoning": "Neural auditor placeholder"}

    def _create_decision(
        self,
        transaction_id: str,
        resolution_path: ResolutionPath,
        symbolic_result: "SymbolicAuditResult",
        neural_invoked: bool,
        dhitl: Optional[str],
        sme: Optional[str],
        latency: float,
        tree: str
    ) -> GovernanceDecision:
        audit_data = f"{transaction_id}:{resolution_path.value}:{symbolic_result.audit_hash}"
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
    symbolic_auditor: Optional["NeuroSymbolicAuditor"] = None,
    neural_path: Optional[str] = None
) -> GovernanceRouter:
    """Factory function to create a GovernanceRouter instance."""
    return GovernanceRouter(symbolic_auditor, neural_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
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
        print()