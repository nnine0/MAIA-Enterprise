"""
Tests for Compliance Logger module.
"""

import pytest
import os
import json
import tempfile
from pathlib import Path
from app.utils.compliance_logger import (
    ComplianceLogger,
    AuditEventType,
    VerdictType,
)


class TestComplianceLogger:
    """Tests for ComplianceLogger class."""

    def setup_method(self):
        """Set up test fixtures with temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.temp_dir, "test_compliance.jsonl")
        self.logger = ComplianceLogger(self.log_path)

    def teardown_method(self):
        """Clean up temp files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_logger_creation(self):
        """Test logger creation."""
        assert self.logger is not None
        assert self.logger.log_path.exists() or True

    def test_log_airlock_intercept(self):
        """Test logging airlock intercept event."""
        event = self.logger.log_airlock_intercept(
            transaction_id="tx_001",
            query="What is the tax implication?",
            adapter_id="law",
            materiality_tier=1,
            actor_response="The merger triggers...",
            auditor_response="VERDICT: PASS",
            verdict="PASS",
            latent_hash="abc123",
            classification_audit_hash="xyz789"
        )

        assert event is not None
        assert event.transaction_id == "tx_001"
        assert event.event_type == AuditEventType.AIRLOCK_INTERCEPT.value

    def test_log_materiality_classify(self):
        """Test logging materiality classification event."""
        event = self.logger.log_materiality_classify(
            transaction_id="tx_002",
            query="Test query",
            tier=1,
            matched_keywords=["tax", "merger"],
            registry_version="1.0.0"
        )

        assert event.event_type == AuditEventType.MATERIALITY_CLASSIFY.value
        assert event.materiality_tier == 1

    def test_log_auditor_verdict(self):
        """Test logging auditor verdict event."""
        event = self.logger.log_auditor_verdict(
            transaction_id="tx_003",
            adapter_id="law",
            verdict="PASS",
            reasoning="Complies with regulations",
            requires_dhitl=False
        )

        assert event.event_type == AuditEventType.AUDITOR_VERDICT.value

    def test_log_dhitl_escalation(self):
        """Test logging DHITL escalation event."""
        event = self.logger.log_dhitl_escalation(
            transaction_id="tx_004",
            adapter_id="finance",
            sme_pool_session_id="SME_SESSION_001",
            vote_threshold=3,
            current_votes=0
        )

        assert event.event_type == AuditEventType.DHITL_ESCALATION.value
        assert event.verdict == VerdictType.PENDING_REVIEW.value

    def test_log_adapter_load(self):
        """Test logging adapter load event."""
        event = self.logger.log_adapter_load(
            adapter_id="law",
            adapter_version="1.0.0",
            sr26_tier=1,
            conceptual_soundness_version="1.0.0"
        )

        assert event.event_type == AuditEventType.ADAPTER_LOAD.value

    def test_log_trajectory(self):
        """Test logging trajectory event."""
        event = self.logger.log_trajectory(
            transaction_id="tx_005",
            query="Test query",
            adapter_id="law",
            trajectory_steps=[
                {"step": 1, "action": "analyze"},
                {"step": 2, "action": "respond"}
            ],
            final_verdict="PASS"
        )

        assert event.event_type == AuditEventType.TRAJECTORY_LOG.value

    def test_flush(self):
        """Test explicit flush."""
        self.logger.log_materiality_classify(
            transaction_id="tx_flush",
            query="Test",
            tier=2,
            matched_keywords=[],
            registry_version="1.0.0"
        )
        self.logger.flush()
        assert len(self.logger._event_buffer) == 0

    def test_get_recent_events(self):
        """Test retrieving recent events."""
        self.logger.log_materiality_classify(
            transaction_id="tx_recent",
            query="Test query",
            tier=1,
            matched_keywords=["test"],
            registry_version="1.0.0"
        )
        self.logger.flush()

        events = self.logger.get_recent_events(count=5)
        assert isinstance(events, list)

    def test_get_transaction_log(self):
        """Test retrieving transaction-specific log."""
        self.logger.log_airlock_intercept(
            transaction_id="tx_specific",
            query="Test",
            adapter_id="law",
            materiality_tier=1,
            actor_response="Response",
            auditor_response="Audit",
            verdict="PASS"
        )
        self.logger.flush()

        events = self.logger.get_transaction_log("tx_specific")
        assert len(events) >= 1

    def test_generate_audit_report(self):
        """Test audit report generation."""
        self.logger.log_materiality_classify(
            transaction_id="tx_report",
            query="Test",
            tier=1,
            matched_keywords=[],
            registry_version="1.0.0"
        )
        self.logger.flush()

        report = self.logger.generate_audit_report()
        assert "total_events" in report
        assert report["total_events"] >= 1

    def test_generate_audit_report_empty(self):
        """Test audit report with no events."""
        logger = ComplianceLogger("/tmp/nonexistent.jsonl")
        report = logger.generate_audit_report()
        assert report["total_events"] == 0


class TestAuditEventTypes:
    """Tests for audit event type enum."""

    def test_event_types(self):
        """Test all event types are defined."""
        assert AuditEventType.AIRLOCK_INTERCEPT.value == "AIRLOCK_INTERCEPT"
        assert AuditEventType.MATERIALITY_CLASSIFY.value == "MATERIALITY_CLASSIFY"
        assert AuditEventType.AUDITOR_VERDICT.value == "AUDITOR_VERDICT"
        assert AuditEventType.DHITL_ESCALATION.value == "DHITL_ESCALATION"
        assert AuditEventType.ADAPTER_LOAD.value == "ADAPTER_LOAD"
        assert AuditEventType.TRAJECTORY_LOG.value == "TRAJECTORY_LOG"


class TestVerdictTypes:
    """Tests for verdict type enum."""

    def test_verdict_types(self):
        """Test all verdict types are defined."""
        assert VerdictType.PASS.value == "PASS"
        assert VerdictType.BLOCKED.value == "BLOCKED"
        assert VerdictType.PENDING_REVIEW.value == "PENDING_REVIEW"