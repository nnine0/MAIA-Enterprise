"""
Tests for Governance Router module.
"""

import pytest
from app.auditor.router import (
    GovernanceRouter,
    ResolutionPath,
)


class TestGovernanceRouter:
    """Tests for GovernanceRouter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.router = GovernanceRouter()

    def test_router_creation(self):
        """Test router creation."""
        assert self.router is not None
        assert self.router.symbolic_auditor is not None

    def test_route_wild_type_approved(self):
        """Test routing for WILD_TYPE trajectory."""
        decision = self.router.route(
            fingerprint_dna="QUERY_NONE_TIER_3_BENIGN_GENERAL_abc123",
            genome_variant="WILD_TYPE",
            transaction_id="tx_001",
            query="What is 2+2?",
            response="4"
        )

        assert decision.resolution_path == ResolutionPath.APPROVED_SYMBOLIC
        assert decision.symbolic_result is not None
        assert decision.neural_auditor_invoked is False
        assert decision.dhitl_session_id is None
        assert decision.sme_escalation_id is None

    def test_route_mutated_approved(self):
        """Test routing for MUTATED trajectory that passes."""
        decision = self.router.route(
            fingerprint_dna="WRITE_DB_TIER_2_ELEVATED_OPERATIONS_def456",
            genome_variant="MUTATED",
            transaction_id="tx_002",
            query="Update user record",
            response="Record updated"
        )

        assert decision.resolution_path in [
            ResolutionPath.APPROVED_SYMBOLIC,
            ResolutionPath.APPROVED_NEURAL,
            ResolutionPath.ESCALATE_DHITL,
            ResolutionPath.ESCALATE_SME
        ]

    def test_route_anomaly_escalates(self):
        """Test routing for ANOMALY trajectory."""
        decision = self.router.route(
            fingerprint_dna="TRANSFER_PAYMENT_TIER_1_CRITICAL_FINANCE_ghi789",
            genome_variant="ANOMALY",
            transaction_id="tx_003",
            query="Transfer $10M",
            response="Processing..."
        )

        assert decision.resolution_path in [
            ResolutionPath.ESCALATE_DHITL,
            ResolutionPath.ESCALATE_SME,
            ResolutionPath.APPROVED_NEURAL
        ]

    def test_route_critical_transfer_dhitl(self):
        """Test routing for critical transfer escalates to DHITL."""
        decision = self.router.route(
            fingerprint_dna="TRANSFER_PAYMENT_TIER_1_CRITICAL_FINANCE_crit123",
            genome_variant="ANOMALY",
            transaction_id="tx_004",
            query="Transfer $25M to offshore account",
            response="Processing wire transfer..."
        )

        assert decision.dhitl_session_id is not None
        assert decision.resolution_path == ResolutionPath.ESCALATE_DHITL

    def test_route_delete_critical_dhitl(self):
        """Test routing for critical delete operation."""
        decision = self.router.route(
            fingerprint_dna="DELETE_DB_TIER_1_CRITICAL_IT_SECURITY_del123",
            genome_variant="ANOMALY",
            transaction_id="tx_005",
            query="Delete all user records",
            response="Deleting..."
        )

        assert decision.resolution_path in [
            ResolutionPath.ESCALATE_DHITL,
            ResolutionPath.BLOCKED
        ]

    def test_decision_tree_tracking(self):
        """Test decision tree is tracked."""
        decision = self.router.route(
            fingerprint_dna="QUERY_NONE_TIER_3_GENERAL_tree123",
            genome_variant="WILD_TYPE",
            transaction_id="tx_tree",
            query="Test query",
            response="Test response"
        )

        assert decision.decision_tree is not None
        assert "SYMBOLIC" in decision.decision_tree

    def test_audit_hash_generation(self):
        """Test audit hash is generated."""
        decision = self.router.route(
            fingerprint_dna="QUERY_NONE_TIER_3_GENERAL_hash123",
            genome_variant="WILD_TYPE",
            transaction_id="tx_hash",
            query="Test",
            response="Result"
        )

        assert decision.audit_hash is not None
        assert len(decision.audit_hash) == 16

    def test_latency_tracking(self):
        """Test latency is tracked."""
        decision = self.router.route(
            fingerprint_dna="QUERY_NONE_TIER_3_GENERAL_lat123",
            genome_variant="WILD_TYPE",
            transaction_id="tx_lat",
            query="Test",
            response="Result"
        )

        assert decision.total_latency_ms >= 0


class TestResolutionPaths:
    """Tests for resolution path mapping."""

    def setup_method(self):
        self.router = GovernanceRouter()

    def test_wild_type_path(self):
        """Test WILD_TYPE maps to APPROVED_SYMBOLIC."""
        decision = self.router.route(
            fingerprint_dna="QUERY_PUBLIC_TIER_3_BENIGN_GENERAL_pub123",
            genome_variant="WILD_TYPE",
            transaction_id="tx_wild",
            query="What is weather?",
            response="Sunny"
        )
        assert decision.resolution_path == ResolutionPath.APPROVED_SYMBOLIC

    def test_neural_fallback_on_mutation(self):
        """Test MUTATED may trigger neural fallback."""
        self.router.enable_neural_fallback = True

        decision = self.router.route(
            fingerprint_dna="WRITE_API_TIER_2_ELEVATED_OPERATIONS_api123",
            genome_variant="MUTATED",
            transaction_id="tx_neural",
            query="Call API",
            response="API called"
        )

        assert decision.symbolic_result is not None

    def test_dhitl_escalation_format(self):
        """Test DHITL session ID format."""
        decision = self.router.route(
            fingerprint_dna="TRANSFER_SWIFT_TIER_1_CRITICAL_FINANCE_dhitl123",
            genome_variant="ANOMALY",
            transaction_id="tx_dhitl_fmt",
            query="Wire transfer",
            response="Processing"
        )

        if decision.dhitl_session_id:
            assert decision.dhitl_session_id.startswith("DHITL_")


class TestGovernanceRouterEdgeCases:
    """Edge case tests for governance router."""

    def setup_method(self):
        self.router = GovernanceRouter()

    def test_empty_query(self):
        """Test handling of empty query."""
        decision = self.router.route(
            fingerprint_dna="QUERY_NONE_TIER_3_GENERAL_empty123",
            genome_variant="WILD_TYPE",
            transaction_id="tx_empty",
            query="",
            response=""
        )
        assert decision is not None
        assert decision.transaction_id == "tx_empty"

    def test_unknown_genome_variant(self):
        """Test handling of unknown genome variant."""
        decision = self.router.route(
            fingerprint_dna="QUERY_NONE_TIER_3_GENERAL_unknown123",
            genome_variant="UNKNOWN_VARIANT",
            transaction_id="tx_unknown",
            query="Test",
            response="Result"
        )
        assert decision is not None

    def test_multiple_transactions(self):
        """Test multiple transactions don't interfere."""
        dna = "QUERY_NONE_TIER_3_GENERAL_multi123"

        d1 = self.router.route(dna, "WILD_TYPE", "tx_1", "Q1", "R1")
        d2 = self.router.route(dna, "WILD_TYPE", "tx_2", "Q2", "R2")

        assert d1.transaction_id != d2.transaction_id
        assert d1.audit_hash != d2.audit_hash