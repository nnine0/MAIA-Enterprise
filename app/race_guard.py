"""
MAIA DFlash/Sentinel Race Guard
================================
Handles the primary technical hurdle of real-world deployment:
race conditions between the base model's output stream and the
Sentinel model's block signal.

Problem:
  DFlash generates 16-token reasoning blocks in ONE GPU forward pass.
  Sentinel (Granite/Nemotron) audits each block. These are independent
  GPU streams sharing a CUDA context. Because:

  1. DFlash block emission is bounded by the transformer forward pass
     completion, not by a separate signal
  2. Sentinel audit decision is bounded by its own forward pass
  3. Block IDs flow through both streams with different latencies
  4. The base model (Gemma) may emit the next block before Sentinel
     has decided on the previous one
  5. In flight, tokens may be partially in base model output while
     Sentinel is still processing the previous block

Failure modes without this guard:
  - Phantom blocks: Base model emits block N+1 before Sentinel decides on N
  - Sequence inversion: Block N decision arrives after N+1 decision
  - Stale decisions: Sentinel decision for block N arrives after N+2 is active
  - Unresolved blocks: Sentinel times out on block but base model expects audit

The guard ensures:
  - Strict sequence ordering of audit decisions per block ID
  - Buffered base-model blocks await Sentinel decisions in order
  - Stale decisions are evicted (decisions older than current block)
  - Timeouts trigger rollback to last known safe checkpoint
  - Sentinel and base-model streams stay synchronized via sequence numbering

Architecture:
  Base Model Stream (DFlash):
    Block N emitted → buffered in BlockBuffer
    Block N+1 emitted → also buffered (waiting)
    Blocks held until Sentinel decision arrives

  Sentinel Audit Stream:
    Audit(N) started
    Audit(N) decision → DecisionBuffer
    Decision(N) must arrive before Block(N+1) can proceed
    Stale decisions evicted when gap > 1

  Synchronization:
    Shared sequence counter + asyncio Event per block
    Producer (DFlash) writes block, waits for decision
    Consumer (base model output) unblocks after decision
"""

import asyncio
import time
import threading
import logging
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from contextlib import asynccontextmanager

logger = logging.getLogger("maia.raceguard")


class BlockStatus(Enum):
    PENDING_AUDIT = "pending_audit"
    AUDIT_IN_PROGRESS = "audit_in_progress"
    AUDIT_APPROVED = "audit_approved"
    AUDIT_REJECTED = "audit_rejected"
    AUDIT_TIMEOUT = "audit_timeout"
    ROLLED_BACK = "rolled_back"


@dataclass
class DFlashBlockRecord:
    """Record for a DFlash block in the synchronization pipeline"""
    block_id: int
    tokens: List[str]
    trajectory_text: str
    block_hash: str
    seq_number: int
    emitted_at: float
    audit_started_at: Optional[float] = None
    audit_decided_at: Optional[float] = None
    status: BlockStatus = BlockStatus.PENDING_AUDIT
    decision: Optional[str] = None
    sentinel_hash: Optional[str] = None
    error: Optional[str] = None


@dataclass
class SentinelDecision:
    """Sentinel audit decision for a block"""
    block_id: int
    seq_number: int
    decision: str
    violations: List[str]
    latent_hash: str
    confidence: float
    decided_at: float = field(default_factory=time.time)


class SequenceMonitor:
    """Monitors sequence integrity and detects gaps"""

    def __init__(self, max_gap: int = 2):
        self.max_gap = max_gap
        self.highest_emitted: int = -1
        self.highest_approved: int = -1
        self.highest_decided: int = -1
        self._lock = threading.Lock()

    def record_emission(self, block_id: int) -> bool:
        """Record a block emission. Returns False if gap detected."""
        with self._lock:
            if block_id > self.highest_emitted + 1:
                logger.warning(f"Block emission gap: expected {self.highest_emitted + 1}, got {block_id}")
                return False
            self.highest_emitted = max(self.highest_emitted, block_id)
            return True

    def record_decision(self, block_id: int) -> bool:
        """Record a Sentinel decision. Returns False if gap detected."""
        with self._lock:
            gap = block_id - self.highest_decided
            if gap > self.max_gap:
                logger.warning(f"Sentinel decision gap: expected <= {self.highest_decided + self.max_gap}, got {block_id}")
                return False
            if gap > 1:
                logger.warning(f"Sentinel decision gap: expected {self.highest_decided + 1}, got {block_id}")
            self.highest_decided = max(self.highest_decided, block_id)
            return True

    def record_approval(self, block_id: int):
        """Record a block approval."""
        with self._lock:
            self.highest_approved = max(self.highest_approved, block_id)

    def can_emit_block(self, block_id: int) -> bool:
        """Check if block can be emitted (previous block approved)."""
        with self._lock:
            return block_id <= self.highest_approved + self.max_gap

    def get_safe_block_id(self) -> int:
        """Get the highest safely approved block ID."""
        with self._lock:
            return self.highest_approved


class BlockBuffer:
    """
    Thread-safe buffer for DFlash blocks awaiting Sentinel decisions.

    Design decisions:
    - Bounded buffer with max_size to prevent memory bloat
    - Evicts stale blocks (gaps > 1 from highest decided) automatically
    - Per-block asyncio.Event for efficient waiting (no polling)
    - Automatic stale eviction on new decision arrival
    """

    def __init__(self, max_size: int = 64):
        self.max_size = max_size
        self._blocks: Dict[int, DFlashBlockRecord] = {}
        self._events: Dict[int, asyncio.Event] = {}
        self._lock = threading.Lock()
        self._highest_block_id: int = -1

    def put(self, block: DFlashBlockRecord) -> asyncio.Event:
        """Add block to buffer, return event for caller to await."""
        with self._lock:
            self._blocks[block.block_id] = block
            self._highest_block_id = max(self._highest_block_id, block.block_id)

            if block.block_id not in self._events:
                self._events[block.block_id] = asyncio.Event()

            if len(self._blocks) > self.max_size:
                self._evict_stale()
                if len(self._blocks) > self.max_size:
                    pending = sorted(
                        [bid for bid, rec in self._blocks.items()
                         if rec.status == BlockStatus.PENDING_AUDIT]
                    )
                    for bid in pending[:len(self._blocks) - self.max_size]:
                        self._blocks.pop(bid, None)
                        self._events.pop(bid, None)

        return self._events[block.block_id]

    def get(self, block_id: int) -> Optional[DFlashBlockRecord]:
        """Get block record, None if not buffered."""
        with self._lock:
            return self._blocks.get(block_id)

    def resolve(self, block_id: int, decision: str, sentinel_hash: str = "", error: str = ""):
        """Resolve a block — unblocks the producer."""
        with self._lock:
            record = self._blocks.get(block_id)
            if record:
                record.audit_decided_at = time.time()
                record.decision = decision
                record.sentinel_hash = sentinel_hash
                record.error = error
                record.status = (
                    BlockStatus.AUDIT_APPROVED if decision == "APPROVED"
                    else BlockStatus.AUDIT_REJECTED
                )
                self._evict_stale()

        if block_id in self._events:
            self._events[block_id].set()

    def timeout(self, block_id: int, error: str = "audit_timeout"):
        """Mark block as timed out — unblocks producer."""
        with self._lock:
            record = self._blocks.get(block_id)
            if record:
                record.status = BlockStatus.AUDIT_TIMEOUT
                record.error = error
                record.audit_decided_at = time.time()

        if block_id in self._events:
            self._events[block_id].set()

    async def wait_for_decision(self, block_id: int, timeout: float) -> Optional[DFlashBlockRecord]:
        """
        Await Sentinel decision for a specific block.
        Returns record with decision, or None on timeout.
        """
        event = self._events.get(block_id)
        if not event:
            return None

        try:
            await asyncio.wait_for(asyncio.shield(event.wait()), timeout=timeout)
        except asyncio.TimeoutError:
            self.timeout(block_id, "decision_timeout")
            return self._blocks.get(block_id)

        return self._blocks.get(block_id)

    def _evict_stale(self):
        """Remove resolved blocks, keeping at most 2 recent resolved."""
        if not self._blocks:
            return

        resolved = sorted(
            (bid for bid, rec in self._blocks.items()
             if rec.status in (BlockStatus.AUDIT_APPROVED, BlockStatus.AUDIT_REJECTED)),
            reverse=True
        )
        if len(resolved) <= 2:
            return

        for bid in resolved[2:]:
            self._blocks.pop(bid, None)
            self._events.pop(bid, None)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "buffer_size": len(self._blocks),
                "pending": sum(1 for r in self._blocks.values()
                               if r.status == BlockStatus.PENDING_AUDIT),
                "in_progress": sum(1 for r in self._blocks.values()
                                  if r.status == BlockStatus.AUDIT_IN_PROGRESS),
                "resolved": sum(1 for r in self._blocks.values()
                               if r.status in (BlockStatus.AUDIT_APPROVED, BlockStatus.AUDIT_REJECTED)),
                "highest_block_id": self._highest_block_id,
            }


class SentinelTimeoutTracker:
    """Tracks per-block Sentinel audit timeouts"""

    def __init__(self, default_timeout: float = 5.0):
        self.default_timeout = default_timeout
        self._timers: Dict[int, asyncio.Task] = {}
        self._thread_timers: Dict[int, threading.Timer] = {}
        self._lock = threading.Lock()
        self._on_timeout: Optional[callable] = None

    def set_timeout_handler(self, handler: callable):
        """Set callback for timeout events."""
        self._on_timeout = handler

    def start_timer(self, block_id: int, custom_timeout: Optional[float] = None):
        """Start timeout timer for a block."""
        timeout = custom_timeout or self.default_timeout

        def do_timeout():
            with self._lock:
                self._thread_timers.pop(block_id, None)
            if self._on_timeout:
                self._on_timeout(block_id, f"Sentinel audit exceeded {timeout}s")

        timer = threading.Timer(timeout, do_timeout)
        with self._lock:
            self._thread_timers[block_id] = timer
        timer.start()

    def cancel_timer(self, block_id: int):
        """Cancel timeout timer when decision arrives."""
        with self._lock:
            if block_id in self._timers:
                self._timers[block_id].cancel()
                del self._timers[block_id]
            if block_id in self._thread_timers:
                self._thread_timers[block_id].cancel()
                del self._thread_timers[block_id]

    def cancel_all(self):
        """Cancel all pending timers."""
        with self._lock:
            for task in self._timers.values():
                task.cancel()
            self._timers.clear()
            for timer in self._thread_timers.values():
                timer.cancel()
            self._thread_timers.clear()


# ─── Tape-Replay Rollback (dflash-mlx pattern) ─────────────────────────────

@dataclass
class TapeReplayRecord:
    """A single record on the governance tape — like dflash-mlx tape entries.

    Each record captures the audit decision and block identity at one step
    of the trajectory. Used by TapeReplayRollback to reconstruct state on
    rollback without re-auditing previously accepted blocks.
    """
    block_id: int
    seq_number: int
    decision: str  # APPROVED or REJECTED
    block_hash: str
    latent_hash: str
    violations: List[str] = field(default_factory=list)
    confidence: float = 0.0


class TapeReplayRollback:
    """Governance tape recorder with checkpoint/rollback (dflash-mlx pattern).

    Inspired by dflash-mlx RecurrentRollbackCache which records tape
    activations during draft generation and replays the accepted prefix
    through the recurrent state on rollback. Here we apply the same
    pattern to governance state:

      checkpoint()  → snapshot current synchronizer state
      record_tape() → append a block decision to the tape
      rollback(n)   → restore snapshot + replay first n tape entries

    This ensures that when a block is rejected mid-trajectory, previously
    accepted blocks' decisions are preserved without re-auditing.
    """

    def __init__(self):
        self._snapshot: Optional[Dict[str, Any]] = None
        self._tape: List[TapeReplayRecord] = []
        self._checkpoint_seq: int = -1

    def checkpoint(self, state: Dict[str, Any]):
        """Snapshot current governance state for potential rollback."""
        self._snapshot = dict(state)
        self._checkpoint_seq = state.get("highest_approved", -1)
        self._tape = []

    def record_tape(self, record: TapeReplayRecord):
        """Append a block decision to the tape."""
        self._tape.append(record)

    def rollback(self, n_accepted: int) -> Dict[str, Any]:
        """Rollback governance state, replay accepted tape entries.

        Args:
            n_accepted: Number of accepted blocks to preserve (replay
                        tape entries 0..n_accepted, drop the rest).

        Returns:
            Restored state dict with highest_approved etc. correctly set.
        """
        state = dict(self._snapshot) if self._snapshot else {}
        if not self._tape:
            return state

        # Replay accepted entries up to n_accepted
        replay = self._tape[:n_accepted]
        for rec in replay:
            state["highest_approved"] = max(
                state.get("highest_approved", -1), rec.block_id
            )
            state["highest_decided"] = max(
                state.get("highest_decided", -1), rec.block_id
            )

        # Purge tape entries beyond accepted
        self._tape = replay

        return state

    @property
    def tape_length(self) -> int:
        return len(self._tape)

    def clear(self):
        self._snapshot = None
        self._tape = []
        self._checkpoint_seq = -1


class BlockSynchronizer:
    """
    Primary synchronization layer between DFlash block stream and Sentinel decisions.

    Coordinates the three streams:
    1. DFlash Block Emission Stream
    2. Base Model Output Stream (post-audit)
    3. Sentinel Audit Decision Stream

    Guarantees:
    - No block proceeds to base model output without Sentinel approval
    - Stale decisions (arriving after newer blocks are active) are dropped
    - Sequence gaps are logged and handled gracefully
    - Timeouts trigger rollback to last known safe state

    Usage:
        synchronizer = BlockSynchronizer(
            audit_timeout=5.0,
            max_buffered_blocks=64,
            enable_rollback=True
        )

        # DFlash side: emit block, await decision
        block_event = synchronizer.emit_block(block_record)
        await block_event.wait()  # blocks until Sentinel decides
        decision = synchronizer.get_decision(block_id)

        # Sentinel side: record audit result
        synchronizer.record_decision(SentinelDecision(...))

        # Recovery: rollback on timeout
        synchronizer.rollback_to(block_id - 1)
    """

    def __init__(
        self,
        audit_timeout: float = 5.0,
        max_buffered_blocks: int = 64,
        enable_rollback: bool = True,
        max_seq_gap: int = 2
    ):
        self.audit_timeout = audit_timeout
        self.enable_rollback = enable_rollback
        self.max_seq_gap = max_seq_gap

        self.block_buffer = BlockBuffer(max_size=max_buffered_blocks)
        self.sequence_monitor = SequenceMonitor(max_gap=max_seq_gap)
        self.timeout_tracker = SentinelTimeoutTracker(default_timeout=audit_timeout)
        self.tape_replay = TapeReplayRollback()

        self._rollback_to_id: int = -1
        self._lock = threading.Lock()
        self._total_blocks: int = 0
        self._total_approved: int = 0
        self._total_rejected: int = 0
        self._total_timeouts: int = 0

        self.timeout_tracker.set_timeout_handler(self._handle_timeout)

        logger.info(f"BlockSynchronizer initialized (timeout={audit_timeout}s, "
                    f"max_buffer={max_buffered_blocks}, rollback={enable_rollback})")

    def emit_block(self, block: DFlashBlockRecord) -> asyncio.Event:
        """
        Emit a DFlash block for Sentinel audit.
        Returns an Event that callers await for the decision.
        Blocks are held in buffer until Sentinel decides.
        """
        if not self.sequence_monitor.record_emission(block.block_id):
            logger.warning(f"Block emission out of sequence: {block.block_id}")

        # Record tape-replay checkpoint on first block
        self._take_checkpoint()

        self._total_blocks += 1
        self.timeout_tracker.start_timer(block.block_id, self.audit_timeout)

        event = self.block_buffer.put(block)
        logger.debug(f"Block {block.block_id} emitted, awaiting Sentinel decision "
                     f"(seq={block.seq_number}, tokens={len(block.tokens)})")

        return event

    def _take_checkpoint(self):
        """Snapshot governance state for tape-replay rollback."""
        self.tape_replay.checkpoint(self._get_state_snapshot())

    def _get_state_snapshot(self) -> Dict[str, Any]:
        return {
            "highest_emitted": self.sequence_monitor.highest_emitted,
            "highest_approved": self.sequence_monitor.highest_approved,
            "highest_decided": self.sequence_monitor.highest_decided,
        }

    def record_decision(self, decision: SentinelDecision):
        """
        Record a Sentinel audit decision.
        Called by the governance layer when Sentinel completes audit.
        Records tape entry for tape-replay rollback.
        """
        if not self.sequence_monitor.record_decision(decision.block_id):
            logger.warning(f"Stale decision for block {decision.block_id} "
                           f"(highest decided: {self.sequence_monitor.highest_decided})")
            return

        self.timeout_tracker.cancel_timer(decision.block_id)

        # Record on tape before resolving (for rollback replay)
        self.tape_replay.record_tape(TapeReplayRecord(
            block_id=decision.block_id,
            seq_number=decision.seq_number,
            decision=decision.decision,
            block_hash="",
            latent_hash=decision.latent_hash,
            violations=decision.violations,
            confidence=decision.confidence,
        ))

        self.block_buffer.resolve(
            decision.block_id,
            decision.decision,
            decision.latent_hash
        )

        if decision.decision == "APPROVED":
            self.sequence_monitor.record_approval(decision.block_id)
            self._total_approved += 1
            logger.info(f"Block {decision.block_id} APPROVED by Sentinel "
                        f"(seq={decision.seq_number}, {len(decision.violations)} violations)")
        else:
            self._total_rejected += 1
            logger.warning(f"Block {decision.block_id} REJECTED by Sentinel "
                           f"(seq={decision.seq_number}, violations: {decision.violations})")

    def get_decision(self, block_id: int) -> Optional[DFlashBlockRecord]:
        """Get decision record for a block."""
        return self.block_buffer.get(block_id)

    async def wait_for_block(self, block: DFlashBlockRecord) -> DFlashBlockRecord:
        """
        Emit block and wait for Sentinel decision.
        Primary entry point for the DFlash → Sentinel pipeline.
        """
        event = self.emit_block(block)

        result = await self.block_buffer.wait_for_decision(
            block.block_id,
            timeout=self.audit_timeout * 2
        )

        return result or block

    def rollback_to(self, block_id: int):
        """
        Rollback to a safe block ID using tape-replay state reconstruction.

        dflash-mlx pattern: restore checkpoint snapshot and replay accepted
        tape entries up to block_id, avoiding full re-audit of previously
        accepted blocks.

        Used when timeout or cascade failure requires recovery.
        """
        if not self.enable_rollback:
            logger.warning("Rollback disabled, ignoring request")
            return

        with self._lock:
            if block_id <= self._rollback_to_id:
                logger.warning(f"Rollback to {block_id} ignored (already at {self._rollback_to_id})")
                return

            self._rollback_to_id = block_id
            logger.warning(f"Rollback initiated to block {block_id}")

            # Tape-replay: restore snapshot + replay accepted entries
            n_accepted = max(0, block_id - self.tape_replay._checkpoint_seq)
            restored = self.tape_replay.rollback(n_accepted)
            self.sequence_monitor.highest_approved = restored.get("highest_approved", -1)
            self.sequence_monitor.highest_decided = restored.get("highest_decided", -1)
            self.sequence_monitor.highest_emitted = restored.get("highest_emitted", -1)

            safe_id = self.sequence_monitor.get_safe_block_id()
            if safe_id > block_id:
                block_id = safe_id

            self._total_timeouts += 1

    def get_safe_output_point(self) -> int:
        """Get the highest block ID safe for base model output."""
        with self._lock:
            safe_seq = self.sequence_monitor.get_safe_block_id()
            rollback = self._rollback_to_id if self._rollback_to_id >= 0 else safe_seq
            if safe_seq < 0:
                return rollback
            return min(rollback, safe_seq)

    def _handle_timeout(self, block_id: int, reason: str):
        """Handle Sentinel timeout for a block."""
        logger.warning(f"Block {block_id} Sentinel timeout: {reason}")

        self.block_buffer.timeout(block_id, reason)

        if self.enable_rollback:
            self.rollback_to(block_id - 1)

    def get_stats(self) -> Dict[str, Any]:
        """Get synchronizer statistics."""
        return {
            "total_blocks": self._total_blocks,
            "approved": self._total_approved,
            "rejected": self._total_rejected,
            "timeouts": self._total_timeouts,
            "approval_rate": round(self._total_approved / max(1, self._total_blocks), 3),
            "buffer": self.block_buffer.get_stats(),
            "rollback_to": self._rollback_to_id,
            "safe_output_point": self.get_safe_output_point(),
            "tape_length": self.tape_replay.tape_length,
        }


_global_synchronizer: Optional[BlockSynchronizer] = None


def get_synchronizer(
    audit_timeout: float = 5.0,
    max_buffered_blocks: int = 64,
    enable_rollback: bool = True
) -> BlockSynchronizer:
    """Get or create global BlockSynchronizer."""
    global _global_synchronizer
    if _global_synchronizer is None:
        _global_synchronizer = BlockSynchronizer(
            audit_timeout=audit_timeout,
            max_buffered_blocks=max_buffered_blocks,
            enable_rollback=enable_rollback
        )
    return _global_synchronizer


def reset_synchronizer():
    """Reset global synchronizer (for testing)."""
    global _global_synchronizer
    if _global_synchronizer:
        _global_synchronizer.timeout_tracker.cancel_all()
    _global_synchronizer = None


@asynccontextmanager
async def governed_block_context(
    synchronizer: BlockSynchronizer,
    block: DFlashBlockRecord,
    timeout: Optional[float] = None
):
    """
    Async context manager for a single DFlash block's governance lifecycle.

    Usage:
        async with governed_block_context(synchronizer, block) as result:
            # block is held until Sentinel decides
            # result is the DFlashBlockRecord with decision
            if result.decision == "APPROVED":
                # proceed to base model output
            else:
                # handle rejection

    Guarantees:
    - Block is always removed from buffer (success or failure)
    - Timeout always triggers rollback
    - No orphan blocks in buffer
    """
    try:
        result = await synchronizer.wait_for_block(block)
        yield result
    except Exception as e:
        logger.error(f"Block {block.block_id} error: {e}")
        synchronizer.rollback_to(block.block_id - 1)
        yield block
    finally:
        pass


if __name__ == "__main__":
    async def test_synchronizer():
        print("=== BlockSynchronizer Test ===\n")

        sync = BlockSynchronizer(audit_timeout=2.0, max_buffered_blocks=16)

        for i in range(5):
            block = DFlashBlockRecord(
                block_id=i,
                tokens=[f"token_{i}_{j}" for j in range(16)],
                trajectory_text=f"reasoning block {i}",
                block_hash=f"hash_{i}",
                seq_number=i
            )

            async with governed_block_context(sync, block) as result:
                print(f"Block {i}: {result.status.value}, decision={result.decision}")
                await asyncio.sleep(0.1)

        print(f"\nStats: {sync.get_stats()}")

        print("\n--- Testing sequence gap handling ---")
        sync2 = BlockSynchronizer(audit_timeout=2.0)
        block_gap = DFlashBlockRecord(block_id=100, tokens=["t1"], trajectory_text="gap",
                                      block_hash="h", seq_number=100)
        sync2.emit_block(block_gap)

        print(f"Buffer stats: {sync2.block_buffer.get_stats()}")

    asyncio.run(test_synchronizer())