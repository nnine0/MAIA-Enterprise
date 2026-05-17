"""
MAIA Hybrid Kernel Configuration
================================
Model stratification for optimal VRAM utilization.

VRAM Budget (24GB RTX 3090):
- Base Model (gemma-4-26B-A4B): NVFP4 ~14.0 GB (sparse, only ~4B active)
- L9 Speculator: FP8 shared KV ~0.5 GB  
- L8 Sheriff (Nemotron-3): INT4 ~2.2 GB
- L8 Sentinel (Granite-Guardian-2B): INT4 ~1.2 GB
- KV Cache: ~2.2 GB
- Operational Runway: ~6.1 GB (speculative buffers)

Target: <150ms Fed compliance latency with 1ms internal handoff.
"""
