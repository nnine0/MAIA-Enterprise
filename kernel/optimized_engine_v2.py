"""
MAIA Optimized Inference Engine v2
=================================
Fixed version with:
1. Models kept in memory (no decompress per request)
2. Sheriff audit actually runs
3. Batched processing
4. KV cache reuse

Target: <150ms end-to-end latency
"""
