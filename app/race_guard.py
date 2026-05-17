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
