"""
MAIA PVI Airlock Tests - SR 26-02 Compliance Validation

These tests simulate the PVI Airlock behavior to demonstrate:
- Effective Challenge: Actor/Auditor separation
- Materiality Matrix: Tier 1/2/3 routing
- Latent Telemetry: Audit trail for Fed verification

Since no actual model is available, we simulate model behavior.
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.airlock import (
    PVIAirlock,
    MaterialityTier,
    AirlockVerdict,
    TrajectoryRecord,
    execute_vetted_transaction,
    batch_vetted_transactions
)
from app.supervisor_router import SupervisorRouter, DispatchToken, IndustryLevel, SubDomainLevel
from app.latent_telemetry import LatentTelemetry, TrajectoryNode
from app.memory_manager import MemoryManager, MemoryTier


class MockActorResponse:
    """Simulates Actor (Expert) adapter response"""
    def __init__(self, reasoning: str):
        self.generated_text = reasoning
        self.details = MagicMock()
        self.details.finish_reason = "length"


class MockAuditResponse:
    """Simulates Auditor adapter response"""
    def __init__(self, verdict: str):
        self.generated_text = verdict


@pytest.fixture
def airlock():
    """Create PVI Airlock instance"""
    return PVIAirlock()


@pytest.fixture
def supervisor():
    """Create Supervisor Router instance"""
    return SupervisorRouter()


@pytest.fixture
def telemetry():
    """Create Latent Telemetry instance"""
    return LatentTelemetry()


@pytest.fixture
def memory():
    """Create Memory Manager instance"""
    return MemoryManager()


class TestMaterialityMatrix:
    """Test Materiality Matrix tiering - SR 26-02 Materiality requirement"""

    def test_tier_1_critical_keywords(self, airlock):
        """Tier 1: High financial exposure triggers mandatory Airlock"""
        test_queries = [
            "Increase credit limit for client 992 by 20%",
            "Wire transfer $50,000 to account 12345",
            "Approve loan application for $2M commercial property",
            "Process contract for legal services",
        ]
        for query in test_queries:
            tier = airlock.get_materiality_tier(query)
            assert tier == MaterialityTier.TIER_1_CRITICAL, f"Query: {query}"

    def test_tier_2_elevated_keywords(self, airlock):
        """Tier 2: Medium risk triggers conditional audit"""
        test_queries = [
            "Update risk policy for credit department",
            "Check approval status for client 445",
            "Generate compliance report for Q4",
        ]
        for query in test_queries:
            tier = airlock.get_materiality_tier(query)
            assert tier == MaterialityTier.TIER_2_ELEVATED, f"Query: {query}"

    def test_tier_3_benign_queries(self, airlock):
        """Tier 3: Low risk bypasses Airlock"""
        test_queries = [
            "Summarize the IT outage log from 3 AM",
            "What is the weather forecast?",
            "List all meeting rooms on floor 5",
        ]
        for query in test_queries:
            tier = airlock.get_materiality_tier(query)
            assert tier == MaterialityTier.TIER_3_BENIGN, f"Query: {query}"


@pytest.mark.asyncio
class TestEffectiveChallenge:
    """Test Effective Challenge - SR 26-02 core requirement"""

    async def test_actor_generates_trajectory(self, airlock):
        """Step 1: Actor (Expert) generates action trajectory"""
        user_query = "Increase credit limit for client 992 by 20%"
        
        # Mock LoRAX client response
        with patch.object(airlock.client, 'chat') as mock_chat:
            mock_chat.completions.create = AsyncMock(return_value=MockActorResponse(
                "Client 992 has DTI ratio of 0.35, credit score 750, requesting 20% increase from $100k to $120k. Recommend approval pending verification of income."
            ))
            
            trajectory = await airlock._generate_trajectory(user_query, "citi/finance-expert-v4")
            
            assert "credit" in trajectory.lower() or "DTI" in trajectory
            assert len(trajectory) > 0

    async def test_auditor_validates_trajectory(self, airlock):
        """Step 3: Auditor validates trajectory for SR 26-02 compliance"""
        trajectory = "Client 992 has DTI ratio of 0.35. Recommend approval."
        
        with patch.object(airlock.client, 'chat') as mock_chat:
            # Scenario 1: Pass
            mock_chat.completions.create = AsyncMock(return_value=MockAuditResponse(
                "PASS: Capital reserve ratio meets SR 26-02 requirements."
            ))
            verdict, reasoning = await airlock._audit_trajectory(trajectory, "citi/pvi-airlock-sr2602")
            assert verdict == AirlockVerdict.PASS

            # Scenario 2: Fail
            mock_chat.completions.create = AsyncMock(return_value=MockAuditResponse(
                "FAIL: Missing 2026 stress-test buffer calculation required by SR 26-02."
            ))
            verdict, reasoning = await airlock._audit_trajectory(trajectory, "citi/pvi-airlock-sr2602")
            assert verdict == AirlockVerdict.BLOCKED


@pytest.mark.asyncio
class TestCircuitBreaker:
    """Test Circuit Breaker - Blocks non-compliant trajectories"""

    async def test_circuit_breaker_passes_compliant(self, airlock):
        """Circuit breaker closes for PASS verdict - transaction proceeds"""
        user_query = "Summarize the IT outage log from 3 AM"  # Tier 3
        
        with patch.object(airlock.client, 'chat') as mock_chat:
            mock_chat.completions.create = AsyncMock(side_effect=[
                MockActorResponse("The IT outage was caused by..."),
            ])
            
            record = await airlock.execute_vetted_transaction(user_query, "finance", "test-001")
            
            assert record.status == "PASS (BYPASS)"
            assert record.materiality_tier == 3

    async def test_circuit_breaker_blocks_non_compliant(self, airlock):
        """Circuit breaker trips for FAIL verdict - transaction blocked"""
        user_query = "Approve $50M credit request"  # Tier 1
        
        with patch.object(airlock.client, 'chat') as mock_chat:
            mock_chat.completions.create = AsyncMock(side_effect=[
                MockActorResponse("Recommending approval of $50M credit..."),
                MockAuditResponse("FAIL: Does not include April 2026 capital reserve ratios."),
            ])
            
            record = await airlock.execute_vetted_transaction(user_query, "finance", "test-002")
            
            assert record.status == "BLOCKED"
            assert record.materiality_tier == 1
            assert record.reason is not None
            assert record.escalation_path is not None


@pytest.mark.asyncio
class TestLatentTelemetry:
    """Test Latent Telemetry - Neural EKG for audit trail"""

    async def test_session_tracking(self, telemetry):
        """Session tracks trajectory through all layers"""
        session_id = "test-session-001"
        
        await telemetry.start_session(session_id, "Increase credit limit for client 992")
        
        # Emit signatures at different layers
        await telemetry.emit_signature(session_id, 1, "supervisor-hub", "Industry: Finance", ["query"], ["dispatch"])
        await telemetry.emit_signature(session_id, 2, "finance-expert", "DTI calculation...", ["dispatch"], ["trajectory"])
        await telemetry.emit_signature(session_id, 3, "sr26-auditor", "PASS", ["trajectory"], ["verdict"])
        
        audit_log = telemetry.get_audit_log(session_id)
        
        assert audit_log["session_id"] == session_id
        assert audit_log["trajectory_length"] == 4  # root + 3 signatures
        assert audit_log["trajectory_hash"] is not None

    async def test_decision_node_detection(self, telemetry):
        """Decision nodes (wire transfer, credit approval) are detected"""
        session_id = "test-session-002"
        
        await telemetry.start_session(session_id, "Wire transfer")
        
        # Emit decision node
        await telemetry.emit_signature(
            session_id, 2, "finance-expert",
            "Initiating wire transfer for $50,000 to account 12345",
            ["query"], ["action"]
        )
        
        audit_log = telemetry.get_audit_log(session_id)
        
        assert len(audit_log["decision_nodes"]) > 0
        # Check for wire transfer decision type
        decision_types = [dn["decision_type"] for dn in audit_log["decision_nodes"]]
        assert "wire_transfer" in decision_types or "tool_call" in decision_types


@pytest.mark.asyncio
class TestSupervisorRouting:
    """Test Supervisor LoRA - Hub/Spoke architecture"""

    async def test_hierarchical_routing(self, supervisor):
        """Test: Executive → Manager → Expert routing"""
        # Test Finance → Commercial Credit
        query = "Evaluate this commercial loan application and adjust credit limit"
        
        token = await supervisor.route(query)
        
        assert token.industry == "finance"
        assert token.sub_domain in ["commercial_credit", "retail_banking", "fraud_aml"]
        assert token.expert_adapter is not None
        assert token.auditor_adapter is not None

    async def test_dispatch_token_generation(self, supervisor):
        """Test dispatch token format"""
        token = DispatchToken(
            industry="finance",
            sub_domain="commercial_credit",
            expert_adapter="citi/commercial-lending-v4",
            auditor_adapter="citi/pvi-airlock-sr2602",
            materiality_tier=1,
            execution_path=["hub", "expert", "auditor"]
        )
        
        token_str = supervisor.get_dispatch_token_string(token)
        
        assert "EXECUTE" in token_str
        assert "AUDIT" in token_str
        assert "TIER" in token_str
        assert "commercial-lending" in token_str


class TestMemoryManager:
    """Test Memory Hierarchy - VRAM/RAM/NVMe"""

    def test_adapter_tier_assignment(self, memory):
        """Adapters are assigned to correct tiers"""
        # VRAM pinned components
        assert memory.is_pinned("base-model-gemma-4-26b-a4b-moe")
        assert memory.is_pinned("pvi-airlock-auditor")
        
        # Non-pinned adapter
        assert not memory.is_pinned("citi/finance-expert-v4")

    def test_load_to_ram(self, memory):
        """Adapters can be loaded from NVMe to RAM"""
        result = memory.load_to_ram("citi/finance-expert-v4")
        
        assert result is True
        assert "citi/finance-expert-v4" in memory.ram_cache
        assert memory.adapters["citi/finance-expert-v4"].tier == MemoryTier.RAM

    def test_vram_slack_calculation(self, memory):
        """VRAM slack is calculated correctly"""
        slack = memory.get_vram_slack()
        
        assert slack == memory.vram_total_mb - memory.vram_used_mb
        assert slack > 0


@pytest.mark.asyncio
class TestBatchExecution:
    """Test batch execution - parallel vetted transactions"""

    async def test_parallel_vetting(self, airlock):
        """Multiple queries processed in parallel"""
        queries = [
            "Increase credit limit for client 992 by 20%",  # Tier 1
            "Summarize the IT outage log from 3 AM",        # Tier 3
        ]
        
        with patch.object(airlock.client, 'chat') as mock_chat:
            mock_chat.completions.create = AsyncMock(return_value=MockActorResponse("Response"))
            
            results = await batch_vetted_transactions(queries, "finance")
            
            assert len(results) == 2
            # First query should be Tier 1, second Tier 3


class TestAuditLogCompliance:
    """Test audit log format - Fed-verifiable format"""

    def test_fed_audit_log_format(self, airlock):
        """Audit log matches Fed SR 26-02 requirements"""
        record = TrajectoryRecord(
            transaction_id="citi-9982-x",
            timestamp="2026-05-04T10:42:00",
            materiality_tier=1,
            policy_vetted="SR 26-02 Section III (Effective Challenge)",
            actor_adapter="citi/finance-expert-v4",
            auditor_adapter="citi/pvi-airlock-sr2602",
            status="BLOCKED",
            reason="Actor reasoning trajectory failed to account for April 2026 capital reserve ratios.",
            latent_hash="0x7b2f9a",
            actor_reasoning="Recommending approval...",
            auditor_reasoning="FAIL: Missing capital reserve...",
            escalation_path="Human-in-the-loop: Senior Risk Officer notified."
        )
        
        audit_log = airlock.to_audit_log(record)
        
        # Verify required fields per SR 26-02
        assert "transaction_id" in audit_log
        assert "materiality_tier" in audit_log
        assert "policy_vetted" in audit_log
        assert "status" in audit_log
        assert "latent_trace_id" in audit_log
        assert "escalation_path" in audit_log


@pytest.mark.asyncio
class TestEndToEndCompliance:
    """End-to-end test: Full compliance flow for Fed audit"""

    async def test_full_compliance_flow(self, airlock, telemetry):
        """Complete flow: Query → Materiality → Actor → Auditor → Audit Log"""
        session_id = "fed-audit-test-001"
        user_query = "Approve $50M commercial loan"
        
        # Step 1: Start telemetry session
        await telemetry.start_session(session_id, user_query)
        
        # Step 2: Determine materiality
        tier = airlock.get_materiality_tier(user_query)
        assert tier == MaterialityTier.TIER_1_CRITICAL
        
        # Step 3: Execute with mocked model
        with patch.object(airlock.client, 'chat') as mock_chat:
            mock_chat.completions.create = AsyncMock(side_effect=[
                MockActorResponse("$50M commercial loan for client 887. DTI 0.32, revenue $15M. Recommend approval."),
                MockAuditResponse("FAIL: Does not include new 2026 stress-test buffer."),
            ])
            
            record = await airlock.execute_vetted_transaction(user_query, "finance", session_id)
            
            # Verify audit log
            audit_log = airlock.to_audit_log(record)
            
            assert audit_log["status"] == "BLOCKED"
            assert audit_log["materiality_tier"] == 1
            assert audit_log["policy_vetted"] == "SR 26-02 Section III (Effective Challenge)"
            assert audit_log["latent_trace_id"] is not None
            assert audit_log["reason"] is not None
        
        # Step 4: Verify telemetry captured full trajectory
        full_audit = telemetry.get_audit_log(session_id)
        assert full_audit["trajectory_length"] > 0
        assert full_audit["trajectory_hash"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])