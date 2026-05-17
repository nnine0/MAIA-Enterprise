"""
MAIA Kernel - vLLM Speculative Decoding Configuration
========================================

Updated for Gemma 4 E4B Stack (24GB Footprint)

Model Selection (Quad-Node Configuration):
- Target (Verifier): google/gemma-4-E4B-it (~4.2GB INT4)
- Drafter (Proposer): google/gemma-4-E4B-it-assistant (~0.6GB)
- System/KV Cache: vLLM PagedAttention (~1.2GB)
- Total: ~6.0GB - Perfect Quad-Node Fit

Key Features:
- Native Thinking/Reasoning support
- Hybrid attention for Gemma 4
- Multimodal compliance (vision)
- Thinking Airlock: scans internal reasoning
"""
