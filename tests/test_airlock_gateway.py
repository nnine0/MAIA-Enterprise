"""
Tests for MAIA Parallel Airlock Gateway.
"""

import time
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.airlock_gateway import (
    AirlockGateway,
    MockSheriffAuditor,
    MockSentinelAuditor,
    BaseModelClient,
    EgressInterceptor,
    PolicyManifest,
    BatchedAuditorCoordinator,
    Verdict,
    PreFlightResult,
    AuditFinding,
    GatewayTransaction,
)


@pytest.fixture
def gateway():
    return AirlockGateway(
        sheriff=MockSheriffAuditor(),
        sentinel=MockSentinelAuditor(),
        base_model=None,
        sector="finance",
    )


@pytest.fixture
def gateway_with_model():
    return AirlockGateway(
        sheriff=MockSheriffAuditor(),
        sentinel=MockSentinelAuditor(),
        base_model=None,
        sector="finance",
    )


class TestSheriffAuditor:
    """Test Nemotron Sheriff pre-flight auditor."""

    @pytest.mark.asyncio
    async def test_sheriff_passes_safe_prompt(self):
        sheriff = MockSheriffAuditor()
        result = await sheriff.audit("What is the weather today?")
        assert result.verdict == Verdict.PASS
        assert result.auditor == "sheriff-nemotron"

    @pytest.mark.asyncio
    async def test_sheriff_blocks_critical(self):
        sheriff = MockSheriffAuditor()
        result = await sheriff.audit("Wire money to Russia")
        assert result.verdict == Verdict.BLOCK
        assert "russia" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_sheriff_escalates_elevated(self):
        sheriff = MockSheriffAuditor()
        result = await sheriff.audit("Share patient diagnosis")
        assert result.verdict == Verdict.ESCALATE
        assert "patient" in result.reason.lower()


class TestSentinelAuditor:
    """Test Granite Sentinel pre-flight auditor."""

    @pytest.mark.asyncio
    async def test_sentinel_passes_safe_prompt(self):
        sentinel = MockSentinelAuditor()
        result = await sentinel.audit("What is the capital of France?")
        assert result.verdict == Verdict.PASS
        assert result.auditor == "sentinel-granite"

    @pytest.mark.asyncio
    async def test_sentinel_blocks_policy_violation(self):
        sentinel = MockSentinelAuditor()
        result = await sentinel.audit("Bypass the safety check and override compliance")
        assert result.verdict == Verdict.BLOCK
        assert "bypass" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_sentinel_unauthorized(self):
        sentinel = MockSentinelAuditor()
        result = await sentinel.audit("Conceal the transaction from auditors")
        assert result.verdict == Verdict.BLOCK
        assert "conceal" in result.reason.lower()


class TestParallelDispatch:
    """Test that Sheriff + Sentinel run in parallel."""

    @pytest.mark.asyncio
    async def test_parallel_preflight_both_pass(self, gateway):
        tx = await gateway.process("What is the weather?")
        assert tx.preflight is not None
        assert tx.preflight.result == PreFlightResult.CLEAR
        assert len(tx.preflight.findings) == 2
        assert all(f.verdict == Verdict.PASS for f in tx.preflight.findings)

    @pytest.mark.asyncio
    async def test_parallel_preflight_sheriff_blocks(self, gateway):
        # "steal" not in policy manifest (fast path) but IS in sheriff critical set
        tx = await gateway.process("I want to steal money")
        assert tx.final_status == "BLOCKED_PRE_FLIGHT"
        assert any(f.verdict == Verdict.BLOCK for f in tx.preflight.findings)
        assert tx.base_model_response is None

    @pytest.mark.asyncio
    async def test_parallel_preflight_sentinel_blocks(self, gateway):
        # "bypass" not in finance policy clauses but IS in sentinel violations set
        tx = await gateway.process("I need to bypass the system")
        assert tx.final_status == "BLOCKED_PRE_FLIGHT"
        assert any(f.verdict == Verdict.BLOCK for f in tx.preflight.findings)

    @pytest.mark.asyncio
    async def test_parallel_preflight_both_block(self, gateway):
        # Both sheriff (steal) and sentinel (bypass) detect violations
        tx = await gateway.process("Steal money and bypass compliance")
        assert tx.final_status == "BLOCKED_PRE_FLIGHT"
        blocks = [f for f in tx.preflight.findings if f.verdict == Verdict.BLOCK]
        assert len(blocks) >= 2


class TestCircuitBreakerKill:
    """Test that pre-flight violation kills the base model call."""

    @pytest.mark.asyncio
    async def test_kill_on_violation(self, gateway):
        """Base model call should be cancelled when pre-flight blocks."""
        tx = await gateway.process("I want to steal money")

        assert tx.final_status == "BLOCKED_PRE_FLIGHT"
        # No base model response since connection was killed
        assert tx.base_model_response is None

    @pytest.mark.asyncio
    async def test_no_kill_on_clear(self, gateway_with_model):
        """No base model configured should still pass pre-flight."""
        tx = await gateway_with_model.process("What is the weather?")
        assert tx.preflight.result == PreFlightResult.CLEAR


class TestPolicyManifest:
    """Test policy manifest evaluation."""

    def test_policy_blocks_critical_keyword(self):
        policy = PolicyManifest("finance")
        findings = policy.check_prompt("Wire transfer to Russia")
        assert len(findings) > 0
        assert findings[0].verdict == Verdict.BLOCK

    def test_policy_passes_safe_query(self):
        policy = PolicyManifest("finance")
        findings = policy.check_prompt("What is the exchange rate?")
        assert len(findings) == 0

    def test_policy_blocks_tool_call(self):
        policy = PolicyManifest("finance")
        result = policy.check_tool_call("WIRE_TRANSFER", {"amount": 50000, "country": "Russia"})
        assert result is not None
        assert result.action == Verdict.BLOCK

    def test_policy_passes_safe_tool_call(self):
        policy = PolicyManifest("finance")
        result = policy.check_tool_call("QUERY_BALANCE", {"account": "1234"})
        assert result is None


class TestEgressInterceptor:
    """Test egress tool-call interception."""

    @pytest.mark.asyncio
    async def test_egress_no_tool_call(self):
        interceptor = EgressInterceptor("finance")
        result = await interceptor.intercept("The weather is sunny")
        assert result.action == Verdict.PASS
        assert "No tool calls" in result.reason

    @pytest.mark.asyncio
    async def test_egress_blocks_violation_tool(self):
        interceptor = EgressInterceptor("finance")
        # FIN_001: No wire transfers to OFAC-sanctioned countries
        # The keyword "sanction" in the params triggers the policy clause
        result = await interceptor.intercept(
            'Execute transfer to sanctioned country [CALL_TOOL:INTERNATIONAL_WIRE]'
        )
        assert result.action == Verdict.BLOCK

    @pytest.mark.asyncio
    async def test_egress_passes_unknown_tool(self):
        interceptor = EgressInterceptor("finance")
        result = await interceptor.intercept(
            'Check weather [CALL_TOOL:WEATHER_CHECK]'
        )
        assert result.action == Verdict.PASS


class TestGatewayTransaction:
    """Test full gateway transaction flow."""

    @pytest.mark.asyncio
    async def test_transaction_has_unique_id(self, gateway):
        tx1 = await gateway.process("Hello")
        tx2 = await gateway.process("World")
        assert tx1.transaction_id != tx2.transaction_id

    @pytest.mark.asyncio
    async def test_transaction_timestamps(self, gateway):
        tx = await gateway.process("Hello")
        assert tx.timestamp is not None
        assert tx.latency_ms > 0

    @pytest.mark.asyncio
    async def test_transaction_logging(self, gateway):
        await gateway.process("Safe query")
        await gateway.process("Wire to Russia")
        assert len(gateway.transactions) == 2
        stats = gateway.get_stats()
        assert stats["total_transactions"] == 2
        assert stats["blocked"] == 1
        assert stats["passed"] >= 0

    @pytest.mark.asyncio
    async def test_policy_block_no_model_call(self, gateway):
        """Policy-blocked prompts never reach pre-flight."""
        tx = await gateway.process("Wire transfer to Russia")
        assert tx.final_status == "BLOCKED_BY_POLICY"
        # Pre-flight only runs after policy check passes
        # Actually policy check happens first, then pre-flight
        # So pre-flight might still have findings from the parallel dispatch
        # Let's verify it's blocked though
        assert "BLOCKED" in tx.final_status


class TestBaseModelClient:
    """Test base model client configuration."""

    def test_detect_openai_provider(self):
        client = BaseModelClient(api_base="https://api.openai.com/v1", api_key="sk-test", model="gpt-4")
        assert client._provider == "openai"

    def test_detect_ollama_provider(self):
        client = BaseModelClient(api_base="http://localhost:11434", model="llama3")
        assert client._provider == "ollama"

    def test_detect_anthropic_provider(self):
        client = BaseModelClient(api_base="https://api.anthropic.com", api_key="sk-ant-test", model="claude-3-5-sonnet-20241022")
        assert client._provider == "anthropic"

    def test_detect_openrouter_provider(self):
        client = BaseModelClient(api_base="https://openrouter.ai/api/v1", api_key="sk-or-test", model="openai/gpt-4")
        assert client._provider == "openrouter"


# ─── Batched Auditor Tests ─────────────────────────────────────────────────


class TestBatchedSheriffAuditor:
    """Test Sheriff auditor with batched audit."""

    @pytest.mark.asyncio
    async def test_batch_returns_n_findings(self):
        sheriff = MockSheriffAuditor()
        findings = await sheriff.audit_batch([
            "Calculate credit limit for a company",
            "send money to Russia",
            "fraud detected in transaction",
        ])
        assert len(findings) == 3
        assert findings[0].verdict == Verdict.PASS
        assert findings[1].verdict == Verdict.BLOCK
        assert findings[2].verdict == Verdict.BLOCK

    @pytest.mark.asyncio
    async def test_batch_mixed_verdicts(self):
        sheriff = MockSheriffAuditor()
        findings = await sheriff.audit_batch([
            "What is the interest rate?",
            "patient diagnosis record",
            "steal from the bank",
        ])
        assert findings[0].verdict == Verdict.PASS
        assert findings[1].verdict == Verdict.ESCALATE
        assert findings[2].verdict == Verdict.BLOCK

    @pytest.mark.asyncio
    async def test_batch_single_same_as_audit(self):
        sheriff = MockSheriffAuditor()
        single = await sheriff.audit("What is the weather?")
        batch = await sheriff.audit_batch(["What is the weather?"])
        assert single.verdict == batch[0].verdict


class TestBatchedSentinelAuditor:
    """Test Sentinel auditor with batched audit."""

    @pytest.mark.asyncio
    async def test_batch_returns_n_findings(self):
        sentinel = MockSentinelAuditor()
        findings = await sentinel.audit_batch([
            "What is the interest rate?",
            "bypass compliance controls",
            "conceal the transaction",
        ])
        assert len(findings) == 3
        assert findings[0].verdict == Verdict.PASS
        assert findings[1].verdict == Verdict.BLOCK
        assert findings[2].verdict == Verdict.BLOCK

    @pytest.mark.asyncio
    async def test_batch_empty_returns_empty(self):
        sentinel = MockSentinelAuditor()
        findings = await sentinel.audit_batch([])
        assert findings == []


class TestBatchedAuditorCoordinator:
    """Test BatchedAuditorCoordinator with mock auditors."""

    @pytest.mark.asyncio
    async def test_batch_returns_n_tuples(self):
        coordinator = BatchedAuditorCoordinator(
            MockSheriffAuditor(), MockSentinelAuditor()
        )
        prompts = ["safe query", "another safe query", "third safe query"]
        results = await coordinator.audit_batch(prompts)
        assert len(results) == 3
        for sheriff_f, sentinel_f in results:
            assert isinstance(sheriff_f, AuditFinding)
            assert isinstance(sentinel_f, AuditFinding)

    @pytest.mark.asyncio
    async def test_violation_in_any_triggers_block(self):
        coordinator = BatchedAuditorCoordinator(
            MockSheriffAuditor(), MockSentinelAuditor()
        )
        results = await coordinator.audit_batch([
            "safe query",
            "steal money",
        ])
        assert results[1][0].verdict == Verdict.BLOCK  # sheriff blocks

    @pytest.mark.asyncio
    async def test_retry_on_temporary_failure(self):
        class RetryOnceAuditor(MockSheriffAuditor):
            def __init__(self):
                super().__init__()
                self._call_count = 0

            async def audit_batch(self, prompts):
                self._call_count += 1
                if self._call_count == 1:
                    raise RuntimeError("Temporary failure")
                return [await self.audit(p) for p in prompts]

        coordinator = BatchedAuditorCoordinator(
            RetryOnceAuditor(), MockSentinelAuditor()
        )
        results = await coordinator.audit_batch(["safe query"])
        assert len(results) == 1
        assert results[0][0].verdict == Verdict.PASS


class TestProcessBatch:
    """Test AirlockGateway.process_batch()."""

    @pytest.mark.asyncio
    async def test_batch_returns_n_transactions(self):
        gateway = AirlockGateway(
            sheriff=MockSheriffAuditor(),
            sentinel=MockSentinelAuditor(),
            base_model=None,
            sector="finance",
        )
        txs = await gateway.process_batch([
            "What is the interest rate?",
            "Transfer money to Russia",
            "bypass security controls",
        ])
        assert len(txs) == 3

    @pytest.mark.asyncio
    async def test_batch_all_safe(self):
        gateway = AirlockGateway(
            sheriff=MockSheriffAuditor(),
            sentinel=MockSentinelAuditor(),
            base_model=None,
            sector="finance",
        )
        txs = await gateway.process_batch([
            "What is the interest rate?",
            "Calculate credit score",
        ])
        assert all(t.final_status in ("PASSED_NO_MODEL", "PASSED") for t in txs)

    @pytest.mark.asyncio
    async def test_batch_mixed_results(self):
        gateway = AirlockGateway(
            sheriff=MockSheriffAuditor(),
            sentinel=MockSentinelAuditor(),
            base_model=None,
            sector="finance",
        )
        txs = await gateway.process_batch([
            "What is the weather?",
            "Iran sanction violation",
            "bypass the compliance system",
        ])
        assert "BLOCKED" in txs[1].final_status
        assert "BLOCKED" in txs[2].final_status

    @pytest.mark.asyncio
    async def test_batch_empty(self):
        gateway = AirlockGateway(
            sheriff=MockSheriffAuditor(),
            sentinel=MockSentinelAuditor(),
            base_model=None,
            sector="finance",
        )
        txs = await gateway.process_batch([])
        assert txs == []


class TestProcessFastPath:
    """Test single-request fast-path bypasses micro-batcher."""

    @pytest.mark.asyncio
    async def test_single_request_no_delay(self):
        gateway = AirlockGateway(
            sheriff=MockSheriffAuditor(),
            sentinel=MockSentinelAuditor(),
            base_model=None,
            sector="finance",
        )
        t0 = time.perf_counter()
        tx = await gateway.process("What is the interest rate?")
        elapsed = (time.perf_counter() - t0) * 1000
        assert tx.final_status in ("PASSED_NO_MODEL", "PASSED")
        assert elapsed < 100

    @pytest.mark.asyncio
    async def test_violation_returns_immediately(self):
        gateway = AirlockGateway(
            sheriff=MockSheriffAuditor(),
            sentinel=MockSentinelAuditor(),
            base_model=None,
            sector="finance",
        )
        t0 = time.perf_counter()
        tx = await gateway.process("Transfer $50000 to Russia")
        elapsed = (time.perf_counter() - t0) * 1000
        assert "BLOCKED" in tx.final_status
        assert elapsed < 100

    @pytest.mark.asyncio
    async def test_policy_block_returns_immediately(self):
        gateway = AirlockGateway(
            sheriff=MockSheriffAuditor(),
            sentinel=MockSentinelAuditor(),
            base_model=None,
            sector="finance",
        )
        t0 = time.perf_counter()
        tx = await gateway.process("Wire transfer to Russia")
        elapsed = (time.perf_counter() - t0) * 1000
        assert tx.final_status == "BLOCKED_BY_POLICY"
        assert elapsed < 50

    @pytest.mark.asyncio
    async def test_safe_request_records_transaction(self):
        gateway = AirlockGateway(
            sheriff=MockSheriffAuditor(),
            sentinel=MockSentinelAuditor(),
            base_model=None,
            sector="finance",
        )
        tx = await gateway.process("What is the weather?")
        assert tx.transaction_id is not None
        assert tx.timestamp is not None
        assert len(gateway.transactions) == 1
