"""
MAIA Race Guard Tests — DFlash/Sentinel Race Condition Scenarios
================================================================
Tests the BlockSynchronizer against real-world race conditions:
1. Sequential emission without decision yet (blocks hold in buffer)
2. Decision arrives out of order (stale decision dropped)
3. Sentinel timeout (rollback triggered)
4. Multiple blocks in flight simultaneously
5. Rapid emission before decisions (buffer growth)
6. Rollback to safe checkpoint
7. Governed block context manager lifecycle
"""

import pytest
import asyncio
import time
import threading
from collections import deque

from app.race_guard import (
    BlockSynchronizer, DFlashBlockRecord, SentinelDecision,
    SequenceMonitor, BlockBuffer, BlockStatus,
    governed_block_context, get_synchronizer, reset_synchronizer
)


def make_block(block_id: int, tokens: int = 16) -> DFlashBlockRecord:
    return DFlashBlockRecord(
        block_id=block_id,
        tokens=[f"t{block_id}_{i}" for i in range(tokens)],
        trajectory_text=f"reasoning block {block_id}",
        block_hash=f"hash_{block_id}",
        seq_number=block_id,
        emitted_at=time.time()
    )


# ============================================================
# Sequence Monitor Tests
# ============================================================

class TestSequenceMonitor:
    def test_sequential_emission(self):
        monitor = SequenceMonitor(max_gap=2)
        assert monitor.record_emission(0)
        assert monitor.record_emission(1)
        assert monitor.record_emission(2)
        assert monitor.highest_emitted == 2

    def test_gap_detection(self):
        monitor = SequenceMonitor(max_gap=2)
        assert monitor.record_emission(0)
        assert not monitor.record_emission(5)

    def test_sequential_decision(self):
        monitor = SequenceMonitor(max_gap=2)
        monitor.record_emission(0)
        monitor.record_emission(1)
        assert monitor.record_decision(0)
        assert monitor.record_decision(1)
        assert monitor.highest_decided == 1

    def test_approval_tracking(self):
        monitor = SequenceMonitor(max_gap=2)
        monitor.record_emission(0)
        monitor.record_emission(1)
        monitor.record_decision(0)
        monitor.record_decision(1)
        monitor.record_approval(0)
        monitor.record_approval(1)
        assert monitor.get_safe_block_id() == 1

    def test_can_emit_block(self):
        monitor = SequenceMonitor(max_gap=2)
        monitor.record_emission(0)
        monitor.record_decision(0)
        monitor.record_approval(0)
        assert monitor.can_emit_block(1)
        assert not monitor.can_emit_block(3)


# ============================================================
# Block Buffer Tests
# ============================================================

class TestBlockBuffer:
    def test_put_and_get(self):
        buf = BlockBuffer(max_size=16)
        block = make_block(0)
        event = buf.put(block)

        assert buf.get(0) is not None
        assert buf.get(0).block_id == 0
        assert buf.get(999) is None

    def test_resolve_unblocks(self):
        buf = BlockBuffer(max_size=16)
        block = make_block(0)
        event = buf.put(block)

        buf.resolve(0, "APPROVED", "sentinel_hash_0")
        assert block.status == BlockStatus.AUDIT_APPROVED
        assert event.is_set()

    def test_timeout_unblocks(self):
        buf = BlockBuffer(max_size=16)
        block = make_block(0)
        event = buf.put(block)

        buf.timeout(0, "audit_timeout")
        assert block.status == BlockStatus.AUDIT_TIMEOUT
        assert event.is_set()

    def test_stale_eviction(self):
        buf = BlockBuffer(max_size=16)
        for i in range(5):
            buf.put(make_block(i))

        buf.resolve(0, "APPROVED", "")
        buf.resolve(1, "REJECTED", "")
        buf.resolve(2, "APPROVED", "")
        buf._evict_stale()

        assert 0 not in buf._blocks
        assert 1 in buf._blocks
        assert 2 in buf._blocks
        assert 3 in buf._blocks

    def test_stale_eviction_oldest_removed(self):
        buf = BlockBuffer(max_size=16)
        for i in range(5):
            buf.put(make_block(i))

        for i in range(4):
            buf.resolve(i, "APPROVED", "")
        buf._evict_stale()

        assert 0 not in buf._blocks
        assert 1 not in buf._blocks
        assert 2 in buf._blocks
        assert 3 in buf._blocks

    def test_max_size_eviction(self):
        buf = BlockBuffer(max_size=4)
        for i in range(8):
            buf.put(make_block(i))

        assert len(buf._blocks) <= 4

    def test_stats(self):
        buf = BlockBuffer(max_size=16)
        buf.put(make_block(0))
        buf.put(make_block(1))
        buf.put(make_block(2))
        buf.resolve(0, "APPROVED", "")

        stats = buf.get_stats()
        assert stats["buffer_size"] == 3
        assert stats["pending"] == 2
        assert stats["resolved"] == 1


# ============================================================
# BlockSynchronizer Tests
# ============================================================

class TestBlockSynchronizer:
    def test_emit_and_record_sequential(self):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=2.0, max_buffered_blocks=16)

        block = make_block(0)
        sync.emit_block(block)

        decision = SentinelDecision(
            block_id=0,
            seq_number=0,
            decision="APPROVED",
            violations=[],
            latent_hash="lh_0",
            confidence=0.99
        )
        sync.record_decision(decision)

        assert sync._total_blocks == 1
        assert sync._total_approved == 1
        assert sync._total_rejected == 0

    def test_stale_decision_dropped(self):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=2.0)

        block0 = make_block(0)
        block2 = make_block(2)
        sync.emit_block(block0)
        sync.emit_block(block2)

        decision = SentinelDecision(
            block_id=0,
            seq_number=0,
            decision="APPROVED",
            violations=[],
            latent_hash="lh_0",
            confidence=0.99
        )
        sync.record_decision(decision)

        decision_stale = SentinelDecision(
            block_id=0,
            seq_number=0,
            decision="REJECTED",
            violations=["stale"],
            latent_hash="lh_0_stale",
            confidence=0.5
        )
        sync.record_decision(decision_stale)

        assert sync._total_approved == 1

    def test_rejection(self):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=2.0)

        block = make_block(0)
        sync.emit_block(block)

        decision = SentinelDecision(
            block_id=0,
            seq_number=0,
            decision="REJECTED",
            violations=["sanctions_violation"],
            latent_hash="lh_0",
            confidence=0.95
        )
        sync.record_decision(decision)

        assert sync._total_rejected == 1

    def test_rollback(self):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=2.0, enable_rollback=True)

        sync.emit_block(make_block(0))
        sync.emit_block(make_block(1))
        sync.emit_block(make_block(2))

        sync.rollback_to(1)

        assert sync._rollback_to_id == 1
        assert sync.get_safe_output_point() == 1

    def test_rollback_disabled(self, caplog):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=2.0, enable_rollback=False)

        sync.rollback_to(1)
        assert sync._rollback_to_id == -1

    def test_stats(self):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=2.0)

        for i in range(3):
            sync.emit_block(make_block(i))
            sync.record_decision(SentinelDecision(
                block_id=i,
                seq_number=i,
                decision="APPROVED",
                violations=[],
                latent_hash=f"lh_{i}",
                confidence=0.99
            ))

        stats = sync.get_stats()
        assert stats["total_blocks"] == 3
        assert stats["approved"] == 3
        assert stats["rejected"] == 0
        assert stats["approval_rate"] == 1.0


# ============================================================
# Async Tests
# ============================================================

@pytest.mark.asyncio
class TestBlockSynchronizerAsync:
    async def test_wait_for_block_approved(self):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=5.0)

        block = make_block(0)

        async def do_audit():
            await asyncio.sleep(0.05)
            sync.record_decision(SentinelDecision(
                block_id=0,
                seq_number=0,
                decision="APPROVED",
                violations=[],
                latent_hash="lh_0",
                confidence=0.99
            ))

        audit_task = asyncio.create_task(do_audit())
        result = await sync.wait_for_block(block)
        await audit_task

        assert result.status == BlockStatus.AUDIT_APPROVED
        assert result.decision == "APPROVED"

    async def test_wait_for_block_timeout(self):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=0.1)

        block = make_block(0)
        result = await sync.wait_for_block(block)

        assert result.status == BlockStatus.AUDIT_TIMEOUT

    async def test_governed_block_context_approval(self):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=5.0)

        block = make_block(0)

        async def do_decide():
            await asyncio.sleep(0.05)
            sync.record_decision(SentinelDecision(
                block_id=0, seq_number=0, decision="APPROVED",
                violations=[], latent_hash="lh_0", confidence=0.99
            ))

        task = asyncio.create_task(do_decide())
        async with governed_block_context(sync, block) as result:
            assert result.decision == "APPROVED"
        await task

    async def test_governed_block_context_rejection(self):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=5.0)

        block = make_block(0)

        async def do_decide():
            await asyncio.sleep(0.05)
            sync.record_decision(SentinelDecision(
                block_id=0, seq_number=0, decision="REJECTED",
                violations=["policy_violation"], latent_hash="lh_0", confidence=0.95
            ))

        task = asyncio.create_task(do_decide())
        async with governed_block_context(sync, block) as result:
            assert result.decision == "REJECTED"
        await task

    async def test_concurrent_blocks(self):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=5.0)

        blocks = [make_block(i) for i in range(3)]

        async def audit_and_decide(block_id: int, delay: float, approved: bool):
            await asyncio.sleep(delay)
            sync.record_decision(SentinelDecision(
                block_id=block_id,
                seq_number=block_id,
                decision="APPROVED" if approved else "REJECTED",
                violations=[],
                latent_hash=f"lh_{block_id}",
                confidence=0.99
            ))

        tasks = []
        for i, block in enumerate(blocks):
            delay = 0.1 if i == 2 else 0.01
            tasks.append(asyncio.create_task(audit_and_decide(i, delay, True)))

        results = await asyncio.gather(*[sync.wait_for_block(b) for b in blocks])

        assert all(r.status == BlockStatus.AUDIT_APPROVED for r in results)
        await asyncio.gather(*tasks)

    async def test_multiple_blocks_sequential_wait(self):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=5.0)

        for i in range(5):
            block = make_block(i)
            sync.emit_block(block)
            await asyncio.sleep(0.01)
            sync.record_decision(SentinelDecision(
                block_id=i, seq_number=i, decision="APPROVED",
                violations=[], latent_hash=f"lh_{i}", confidence=0.99
            ))

        stats = sync.get_stats()
        assert stats["total_blocks"] == 5
        assert stats["approved"] == 5

    async def test_safe_output_point_under_rollback(self):
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=5.0, enable_rollback=True)

        for i in range(4):
            sync.emit_block(make_block(i))

        sync.record_decision(SentinelDecision(
            block_id=0, seq_number=0, decision="APPROVED",
            violations=[], latent_hash="lh_0", confidence=0.99
        ))
        sync.record_decision(SentinelDecision(
            block_id=1, seq_number=1, decision="APPROVED",
            violations=[], latent_hash="lh_1", confidence=0.99
        ))

        sync.rollback_to(1)

        assert sync.get_safe_output_point() <= 1


# ============================================================
# Integration: Race Condition Scenarios
# ============================================================

@pytest.mark.asyncio
class TestRaceConditionScenarios:
    async def test_rapid_emission_before_decisions(self):
        """
        Base model emits blocks rapidly before Sentinel has decided on earlier ones.
        This is the primary real-world race condition.
        """
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=5.0, max_buffered_blocks=64)

        blocks = [make_block(i) for i in range(8)]

        for block in blocks:
            sync.emit_block(block)

        stats = sync.block_buffer.get_stats()
        assert stats["pending"] == 8

        for i in range(8):
            await asyncio.sleep(0.01)
            sync.record_decision(SentinelDecision(
                block_id=i, seq_number=i, decision="APPROVED",
                violations=[], latent_hash=f"lh_{i}", confidence=0.99
            ))

        stats = sync.get_stats()
        assert stats["approved"] == 8
        assert stats["timeouts"] == 0

    async def test_out_of_order_decisions(self):
        """
        Sentinel decisions arrive out of order (e.g., block 3 before block 2).
        All should be recorded; the buffer handles sequencing.
        """
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=5.0, max_seq_gap=5)

        sync.emit_block(make_block(0))
        sync.emit_block(make_block(1))
        sync.emit_block(make_block(2))

        sync.record_decision(SentinelDecision(
            block_id=2, seq_number=2, decision="APPROVED",
            violations=[], latent_hash="lh_2", confidence=0.99
        ))
        sync.record_decision(SentinelDecision(
            block_id=1, seq_number=1, decision="APPROVED",
            violations=[], latent_hash="lh_1", confidence=0.99
        ))
        sync.record_decision(SentinelDecision(
            block_id=0, seq_number=0, decision="APPROVED",
            violations=[], latent_hash="lh_0", confidence=0.99
        ))

        stats = sync.get_stats()
        assert stats["approved"] == 3

    async def test_timeout_triggers_rollback(self):
        """
        Sentinel times out on block 2. Rollback to last safe checkpoint (block 1).
        """
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=0.05, enable_rollback=True)

        for i in range(4):
            sync.emit_block(make_block(i))

        sync.record_decision(SentinelDecision(
            block_id=0, seq_number=0, decision="APPROVED",
            violations=[], latent_hash="lh_0", confidence=0.99
        ))
        sync.record_decision(SentinelDecision(
            block_id=1, seq_number=1, decision="APPROVED",
            violations=[], latent_hash="lh_1", confidence=0.99
        ))

        await asyncio.sleep(0.1)

        assert sync._total_timeouts >= 1

    async def test_buffer_prevents_sequence_inversion(self):
        """
        Block 0 approval unblocks pipeline for subsequent block 1.
        No block in buffer blocks another's processing.
        """
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=5.0)

        block0 = make_block(0)
        block1 = make_block(1)

        sync.emit_block(block0)
        sync.emit_block(block1)

        sync.record_decision(SentinelDecision(
            block_id=0, seq_number=0, decision="APPROVED",
            violations=[], latent_hash="lh_0", confidence=0.99
        ))

        assert sync.block_buffer.get(0).status == BlockStatus.AUDIT_APPROVED
        assert sync.block_buffer.get(1).status == BlockStatus.PENDING_AUDIT

    async def test_high_throughput_sustained(self):
        """
        Sustained high throughput with concurrent block emissions and decisions.
        Simulates real-world AI factory workload.
        """
        reset_synchronizer()
        sync = BlockSynchronizer(audit_timeout=5.0, max_buffered_blocks=128)

        total_blocks = 50

        async def emit_blocks():
            for i in range(total_blocks):
                sync.emit_block(make_block(i))
                await asyncio.sleep(0.001)

        async def decide_blocks():
            for i in range(total_blocks):
                await asyncio.sleep(0.002)
                decision = "APPROVED" if i % 10 != 0 else "REJECTED"
                sync.record_decision(SentinelDecision(
                    block_id=i, seq_number=i, decision=decision,
                    violations=["test"] if decision == "REJECTED" else [],
                    latent_hash=f"lh_{i}", confidence=0.99
                ))

        await asyncio.gather(emit_blocks(), decide_blocks())

        await asyncio.sleep(0.1)

        stats = sync.get_stats()
        assert stats["total_blocks"] == total_blocks
        assert stats["approved"] + stats["rejected"] == total_blocks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])