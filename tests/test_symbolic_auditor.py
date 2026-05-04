"""
Tests for Neuro-Symbolic Auditor module.
"""

import pytest
import os
import json
from app.auditor.symbolic import (
    NeuroSymbolicAuditor,
    SymbolicVerdict,
    EvaluationPath,
    SymbolicRule,
)


class TestSymbolicRule:
    """Tests for SymbolicRule class."""

    def test_rule_creation(self):
        """Test rule creation."""
        rule = SymbolicRule(
            rule_id="TEST_001",
            condition="Intent == TRANSFER",
            action="REQUIRE_DHITL",
            fallback="BLOCK"
        )
        assert rule.rule_id == "TEST_001"
        assert rule.action == "REQUIRE_DHITL"

    def test_rule_evaluate_match(self):
        """Test rule evaluation with matching condition."""
        rule = SymbolicRule(
            rule_id="TEST_001",
            condition="Intent == TRANSFER",
            action="REQUIRE_DHITL",
            fallback="BLOCK"
        )
        result = rule.evaluate("TRANSFER", "PAYMENT", "TIER_1", "FINANCE")
        assert result is True

    def test_rule_evaluate_no_match(self):
        """Test rule evaluation with non-matching condition."""
        rule = SymbolicRule(
            rule_id="TEST_001",
            condition="Intent == TRANSFER",
            action="REQUIRE_DHITL",
            fallback="BLOCK"
        )
        result = rule.evaluate("QUERY", "NONE", "TIER_3", "GENERAL")
        assert result is False


class TestNeuroSymbolicAuditor:
    """Tests for NeuroSymbolicAuditor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auditor = NeuroSymbolicAuditor()

    def test_auditor_creation(self):
        """Test auditor creation."""
        assert self.auditor is not None
        assert isinstance(self.auditor._rules, dict)

    def test_evaluate_wild_type(self):
        """Test evaluation of WILD_TYPE trajectory."""
        result = self.auditor.evaluate(
            fingerprint_dna="QUERY_NONE_TIER_3_BENIGN_GENERAL_abc123",
            genome_variant="WILD_TYPE",
            transaction_id="tx_001"
        )
        assert result.evaluation_path == EvaluationPath.WILD_TYPE
        assert result.verdict == SymbolicVerdict.APPROVED
        assert result.latency_ms < 1.0

    def test_evaluate_mutated(self):
        """Test evaluation of MUTATED trajectory."""
        result = self.auditor.evaluate(
            fingerprint_dna="WRITE_DB_TIER_2_ELEVATED_OPERATIONS_abc123",
            genome_variant="MUTATED",
            transaction_id="tx_002"
        )
        assert result.evaluation_path == EvaluationPath.MUTATED
        assert result.transaction_id == "tx_002"

    def test_evaluate_anomaly(self):
        """Test evaluation of ANOMALY trajectory."""
        result = self.auditor.evaluate(
            fingerprint_dna="TRANSFER_PAYMENT_TIER_1_CRITICAL_FINANCE_abc123",
            genome_variant="ANOMALY",
            transaction_id="tx_003"
        )
        assert result.evaluation_path == EvaluationPath.ANOMALY
        assert result.requires_human_review is True

    def test_evaluate_critical_transfer(self):
        """Test evaluation of critical transfer."""
        result = self.auditor.evaluate(
            fingerprint_dna="TRANSFER_PAYMENT_TIER_1_CRITICAL_FINANCE_xyz789",
            genome_variant="ANOMALY",
            transaction_id="tx_004"
        )
        assert result.verdict in [
            SymbolicVerdict.REQUIRES_DHITL,
            SymbolicVerdict.REQUIRES_SME,
            SymbolicVerdict.BLOCKED
        ]
        assert result.audit_hash is not None

    def test_evaluate_delete_operation(self):
        """Test evaluation of delete operation."""
        result = self.auditor.evaluate(
            fingerprint_dna="DELETE_DB_TIER_1_CRITICAL_IT_SECURITY_del123",
            genome_variant="ANOMALY",
            transaction_id="tx_005"
        )
        assert result.evaluation_path == EvaluationPath.ANOMALY
        assert result.symbolic_proof is not None

    def test_proof_generation(self):
        """Test that proof is generated for each evaluation."""
        result = self.auditor.evaluate(
            fingerprint_dna="QUERY_NONE_TIER_2_ELEVATED_GENERAL_test123",
            genome_variant="WILD_TYPE",
            transaction_id="tx_006"
        )
        assert result.symbolic_proof is not None
        assert result.symbolic_proof.proof_id is not None
        assert result.symbolic_proof.rule_id is not None

    def test_statistics(self):
        """Test statistics tracking."""
        initial_stats = self.auditor.get_statistics()
        assert "total_evaluated" in initial_stats

        self.auditor.evaluate("QUERY_NONE_TIER_3_GENERAL_123", "WILD_TYPE", "tx_stats")

        updated_stats = self.auditor.get_statistics()
        assert updated_stats["total_evaluated"] >= 1

    def test_latency_metrics(self):
        """Test latency is measured."""
        result = self.auditor.evaluate(
            fingerprint_dna="QUERY_NONE_TIER_3_GENERAL_lat123",
            genome_variant="WILD_TYPE",
            transaction_id="tx_lat"
        )
        assert result.latency_ms >= 0
        assert result.timestamp is not None

    def test_unknown_dna_handling(self):
        """Test handling of unknown DNA format."""
        result = self.auditor.evaluate(
            fingerprint_dna="UNKNOWN",
            genome_variant="WILD_TYPE",
            transaction_id="tx_unknown"
        )
        assert result is not None

    def test_dhitl_escalation_for_critical(self):
        """Test DHITL escalation for critical operations."""
        result = self.auditor.evaluate(
            fingerprint_dna="EXECUTE_API_TIER_1_CRITICAL_COMPLIANCE_exec123",
            genome_variant="ANOMALY",
            transaction_id="tx_dhitl"
        )
        assert result.requires_human_review or result.verdict == SymbolicVerdict.REQUIRES_DHITL

    def test_audit_hash_uniqueness(self):
        """Test that audit hashes are unique."""
        result1 = self.auditor.evaluate(
            fingerprint_dna="QUERY_NONE_TIER_3_GENERAL_hash123",
            genome_variant="WILD_TYPE",
            transaction_id="tx_hash1"
        )
        result2 = self.auditor.evaluate(
            fingerprint_dna="QUERY_NONE_TIER_3_GENERAL_hash456",
            genome_variant="WILD_TYPE",
            transaction_id="tx_hash2"
        )
        assert result1.audit_hash != result2.audit_hash


class TestSymbolicAuditorIntegration:
    """Integration tests for symbolic auditor."""

    def setup_method(self):
        self.auditor = NeuroSymbolicAuditor()

    def test_multiple_evaluations(self):
        """Test multiple sequential evaluations."""
        dna_values = [
            "QUERY_NONE_TIER_3_BENIGN_GENERAL_aaa111",
            "WRITE_DB_TIER_2_ELEVATED_OPERATIONS_bbb222",
            "TRANSFER_PAYMENT_TIER_1_CRITICAL_FINANCE_ccc333",
        ]

        results = []
        for i, dna in enumerate(dna_values):
            result = self.auditor.evaluate(dna, "MUTATED", f"tx_multi_{i}")
            results.append(result)

        assert len(results) == 3
        assert all(r.audit_hash for r in results)

    def test_full_audit_trail(self):
        """Test complete audit trail generation."""
        result = self.auditor.evaluate(
            fingerprint_dna="DELETE_DB_TIER_1_CRITICAL_IT_SECURITY_del999",
            genome_variant="ANOMALY",
            transaction_id="tx_full_trail"
        )

        assert result.transaction_id == "tx_full_trail"
        assert result.fingerprint_dna is not None
        assert result.verdict is not None
        assert result.timestamp is not None