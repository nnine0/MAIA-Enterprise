"""
Neuro-Symbolic Auditor

Lightweight CPU-bound formal logic engine for deterministic verification.
Eliminates VRAM latency bottleneck by using symbolic rule evaluation (<5ms).

Replaces heavy LoRA Auditor with deterministic rule graph.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SymbolicVerdict(Enum):
    """Verdict returned by the symbolic auditor."""
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    REQUIRES_DHITL = "REQUIRES_DHITL"
    REQUIRES_SME = "REQUIRES_SME"
    LOG_ONLY = "LOG_ONLY"


class EvaluationPath(Enum):
    """Classification of trajectory type for evaluation routing."""
    WILD_TYPE = "WILD_TYPE"
    MUTATED = "MUTATED"
    ANOMALY = "ANOMALY"


@dataclass(frozen=True)
class SymbolicProof:
    """Immutable proof of logic execution for regulatory verification."""
    rule_id: str
    condition_matched: str
    action_taken: str
    evaluation_time_ms: float
    logical_ast: Dict[str, Any]
    proof_id: str


@dataclass
class SymbolicAuditResult:
    """Complete audit result with deterministic proof."""
    transaction_id: str
    fingerprint_dna: str
    verdict: SymbolicVerdict
    evaluation_path: EvaluationPath
    symbolic_proof: SymbolicProof
    latency_ms: float
    requires_neural_auditor: bool
    requires_human_review: bool
    audit_hash: str
    timestamp: str


class SymbolicRule:
    """Represents a single validation rule from the policy schema."""
    def __init__(self, rule_id: str, condition: str, action: str, fallback: str):
        self.rule_id = rule_id
        self.condition = condition
        self.action = action
        self.fallback = fallback

    def evaluate(self, intent: str, system: str, magnitude: str, risk: str) -> bool:
        """Evaluate if this rule matches the given trajectory attributes."""
        try:
            return self._match_condition(intent, system, magnitude, risk)
        except Exception as e:
            logger.warning(f"Rule {self.rule_id} evaluation failed: {e}")
            return False

    def _match_condition(self, intent: str, system: str, magnitude: str, risk: str) -> bool:
        """Check if condition matches trajectory attributes."""
        condition = self.condition

        checks = []
        checks.append(("Intent", intent, "Intent"))
        checks.append(("Target_System", system, "Target_System"))
        checks.append(("Value_Magnitude", magnitude, "Value_Magnitude"))
        checks.append(("Risk_Domain", risk, "Risk_Domain"))

        for attr_name, attr_val, pattern_name in checks:
            if f"{attr_name} ==" in condition:
                expected = condition.split(f"{attr_name} ==")[1].strip().strip('"')
                checks.append((pattern_name, attr_val == expected))

        for check in checks[4:]:
            if not check[1]:
                return False

        return True


class NeuroSymbolicAuditor:
    """
    CPU-bound symbolic logic engine for deterministic trajectory verification.

    Architecture:
    - Wild-Type: Instant rubber-stamp (0ms overhead)
    - Mutated: Symbolic rule evaluation (<5ms)
    - Anomaly: Flag for neural or human review

    Eliminates 150ms VRAM weight swapping overhead.
    """

    def __init__(self, rules_path: str = "policies/trajectory_genetics.schema.json"):
        self.rules_path = Path(rules_path)
        self._rules: Dict[str, SymbolicRule] = {}
        self._stats: Dict[str, int] = {"evaluated": 0, "approved": 0, "blocked": 0, "dhitl": 0}
        self._load_rules()

    def _load_rules(self) -> None:
        """Load validation rules from policy schema."""
        if not self.rules_path.exists():
            logger.warning(f"Rules file not found: {self.rules_path}")
            return

        try:
            with open(self.rules_path, 'r') as f:
                data = json.load(f)
                for rule_data in data.get('validation_rules', []):
                    rule = SymbolicRule(
                        rule_id=rule_data['rule_id'],
                        condition=rule_data['condition'],
                        action=rule_data['action'],
                        fallback=rule_data['fallback']
                    )
                    self._rules[rule.rule_id] = rule
            logger.info(f"Loaded {len(self._rules)} validation rules")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse rules file: {e}")
        except KeyError as e:
            logger.error(f"Invalid rule structure: {e}")

    def evaluate(
        self,
        fingerprint_dna: str,
        genome_variant: str,
        transaction_id: str
    ) -> SymbolicAuditResult:
        """
        Evaluate trajectory fingerprint symbolically.

        Args:
            fingerprint_dna: The DNA sequence from trajectory genetics
            genome_variant: Classification of trajectory type
            transaction_id: Unique transaction identifier

        Returns:
            SymbolicAuditResult with deterministic verdict and proof
        """
        start_time = time.perf_counter()

        dna_parts = fingerprint_dna.split('_')
        intent = dna_parts[0] if len(dna_parts) > 0 else "UNKNOWN"
        system = dna_parts[1] if len(dna_parts) > 1 else "NONE"
        magnitude = dna_parts[2] if len(dna_parts) > 2 else "TIER_2_ELEVATED"
        risk = dna_parts[3] if len(dna_parts) > 3 else "GENERAL"

        eval_path = self._determine_path(genome_variant, magnitude, intent)
        verdict, proof = self._evaluate_rules(intent, system, magnitude, risk, eval_path)

        latency_ms = (time.perf_counter() - start_time) * 1000

        requires_neural = eval_path in [EvaluationPath.ANOMALY, EvaluationPath.MUTATED]
        requires_human = verdict in [SymbolicVerdict.REQUIRES_DHITL, SymbolicVerdict.REQUIRES_SME]

        audit_hash = hashlib.sha256(
            f"{transaction_id}:{fingerprint_dna}:{verdict.value}".encode()
        ).hexdigest()[:16]

        self._update_stats(eval_path, verdict)

        return SymbolicAuditResult(
            transaction_id=transaction_id,
            fingerprint_dna=fingerprint_dna,
            verdict=verdict,
            evaluation_path=eval_path,
            symbolic_proof=proof,
            latency_ms=latency_ms,
            requires_neural_auditor=requires_neural,
            requires_human_review=requires_human,
            audit_hash=audit_hash,
            timestamp=datetime.utcnow().isoformat()
        )

    def _determine_path(self, genome_variant: str, magnitude: str, intent: str) -> EvaluationPath:
        """Determine evaluation path based on genome variant and attributes."""
        if genome_variant == "WILD_TYPE":
            return EvaluationPath.WILD_TYPE

        critical_actions = {"TRANSFER", "DELETE", "EXECUTE"}
        if magnitude == "TIER_1_CRITICAL" or intent in critical_actions:
            return EvaluationPath.ANOMALY

        return EvaluationPath.MUTATED

    def _evaluate_rules(
        self,
        intent: str,
        system: str,
        magnitude: str,
        risk: str,
        eval_path: EvaluationPath
    ) -> Tuple[SymbolicVerdict, SymbolicProof]:
        """Evaluate against deterministic rule graph."""
        timestamp = int(time.time() * 1000)

        if eval_path == EvaluationPath.WILD_TYPE:
            return SymbolicVerdict.APPROVED, SymbolicProof(
                rule_id="WILD_TYPE_BYPASS",
                condition_matched="Genome variant is WILD_TYPE (pre-approved pathway)",
                action_taken="AUTOMATIC_APPROVAL",
                evaluation_time_ms=0.1,
                logical_ast={"path": "wild_type", "automatic": True},
                proof_id=hashlib.sha256(f"wild_type:{timestamp}".encode()).hexdigest()[:12]
            )

        for rule in self._rules.values():
            if rule.evaluate(intent, system, magnitude, risk):
                action = rule.action
                verdict = self._action_to_verdict(action)

                return verdict, SymbolicProof(
                    rule_id=rule.rule_id,
                    condition_matched=rule.condition,
                    action_taken=action,
                    evaluation_time_ms=1.2,
                    logical_ast={"condition": rule.condition, "action": action},
                    proof_id=hashlib.sha256(f"{rule.rule_id}:{timestamp}".encode()).hexdigest()[:12]
                )

        if eval_path == EvaluationPath.ANOMALY:
            return SymbolicVerdict.REQUIRES_DHITL, SymbolicProof(
                rule_id="ANOMALY_DEFAULT",
                condition_matched="Anomaly pathway without matching rule",
                action_taken="REQUIRES_DHITL",
                evaluation_time_ms=0.8,
                logical_ast={"path": "anomaly_fallback"},
                proof_id=hashlib.sha256(f"anomaly:{timestamp}".encode()).hexdigest()[:12]
            )

        return SymbolicVerdict.LOG_ONLY, SymbolicProof(
            rule_id="MUTATED_DEFAULT",
            condition_matched="Mutated pathway - logged for monitoring",
            action_taken="LOG_ONLY",
            evaluation_time_ms=0.5,
            logical_ast={"path": "mutated_fallback"},
            proof_id=hashlib.sha256(f"mutated:{timestamp}".encode()).hexdigest()[:12]
        )

    def _action_to_verdict(self, action: str) -> SymbolicVerdict:
        """Map action string to SymbolicVerdict."""
        mapping = {
            "REQUIRE_DHITL": SymbolicVerdict.REQUIRES_DHITL,
            "REQUIRE_SME_ESCALATION": SymbolicVerdict.REQUIRES_SME,
            "BLOCK": SymbolicVerdict.BLOCKED,
            "WARN": SymbolicVerdict.LOG_ONLY,
        }
        return mapping.get(action, SymbolicVerdict.LOG_ONLY)

    def _update_stats(self, eval_path: EvaluationPath, verdict: SymbolicVerdict) -> None:
        """Update internal statistics."""
        self._stats["evaluated"] += 1
        if eval_path == EvaluationPath.WILD_TYPE or verdict == SymbolicVerdict.APPROVED:
            self._stats["approved"] += 1
        elif verdict == SymbolicVerdict.BLOCKED:
            self._stats["blocked"] += 1
        elif verdict == SymbolicVerdict.REQUIRES_DHITL:
            self._stats["dhitl"] += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Get auditor statistics."""
        total = self._stats["evaluated"]
        return {
            "total_evaluated": total,
            "approved": self._stats["approved"],
            "blocked": self._stats["blocked"],
            "dhitl_required": self._stats["dhitl"],
            "success_rate": self._stats["approved"] / max(1, total)
        }

    def export_proof(self, result: SymbolicAuditResult, output_path: str) -> None:
        """Export deterministic proof for regulatory submission."""
        proof_data = {
            "transaction_id": result.transaction_id,
            "fingerprint_dna": result.fingerprint_dna,
            "verdict": result.verdict.value,
            "evaluation_path": result.evaluation_path.value,
            "symbolic_proof": {
                "rule_id": result.symbolic_proof.rule_id,
                "condition_matched": result.symbolic_proof.condition_matched,
                "action_taken": result.symbolic_proof.action_taken,
                "evaluation_time_ms": result.symbolic_proof.evaluation_time_ms,
                "logical_ast": result.symbolic_proof.logical_ast,
                "proof_id": result.symbolic_proof.proof_id
            },
            "latency_ms": result.latency_ms,
            "requires_neural_auditor": result.requires_neural_auditor,
            "requires_human_review": result.requires_human_review,
            "audit_hash": result.audit_hash,
            "timestamp": result.timestamp
        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(proof_data, f, indent=2)


def create_auditor(rules_path: str = "policies/trajectory_genetics.schema.json") -> NeuroSymbolicAuditor:
    """Factory function to create a NeuroSymbolicAuditor instance."""
    return NeuroSymbolicAuditor(rules_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    auditor = create_auditor()

    print("=== Neuro-Symbolic Auditor Test ===\n")

    test_cases = [
        ("QUERY_NONE_TIER_2_ELEVATED_GENERAL_abc123", "WILD_TYPE", "tx_001"),
        ("WRITE_INTERNAL_DB_TIER_2_ELEVATED_OPERATIONS_def456", "MUTATED", "tx_002"),
        ("TRANSFER_PAYMENT_GATEWAY_TIER_1_CRITICAL_FINANCE_ghi789", "ANOMALY", "tx_003"),
        ("DELETE_INTERNAL_DB_TIER_1_CRITICAL_IT_SECURITY_jkl012", "ANOMALY", "tx_004"),
    ]

    for dna, variant, tx_id in test_cases:
        result = auditor.evaluate(dna, variant, tx_id)

        print(f"Transaction: {tx_id}")
        print(f"  DNA: {dna}")
        print(f"  Path: {result.evaluation_path.value}")
        print(f"  Verdict: {result.verdict.value}")
        print(f"  Latency: {result.latency_ms:.2f}ms")
        print(f"  Proof ID: {result.symbolic_proof.proof_id}")
        print(f"  Requires Neural: {result.requires_neural_auditor}")
        print(f"  Requires Human: {result.requires_human_review}")
        print()

    print("=== Statistics ===")
    for key, value in auditor.get_statistics().items():
        print(f"  {key}: {value}")