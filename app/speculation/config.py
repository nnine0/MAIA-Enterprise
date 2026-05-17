"""
MAIA Speculation Configuration
==============================
Configuration for Unified Speculative Stack (MTP + DFlash + Saguaro/SSD).

MTP PROPOSER/VERIFIER ARCHITECTURE (v4.0):
-----------------------------------
The key innovation: Proposer and Verifier have DIFFERENT adapter relationships.

Layer 9 - MTP Proposer (Adapter-Agnostic):
  - Uses base model ONLY (no adapter loading)
  - Drafts based on general language patterns
  - Near-zero VRAM overhead (shared KV cache from base)
  - Can be small/fast (fewer heads, no weight dependencies)

Layer 8 - MTP Verifier (Adapter-Strict):
  - MUST validate against loaded adapter weights  
  - Enforces physical constraints (SR 26-02, sector rules)
  - Rejects adapter-incompatible drafts
  - Uses adapter's LoRA weights for validation

CIRCUIT BREAKER MODEL (v3.0):
----------------------------
Layer 8 (Governance)   → SSD/Saguaro Async Audit + Circuit Breaker Validates + Signs
Layer 7 (Application) → Executes SIGNED trajectories only
"""
