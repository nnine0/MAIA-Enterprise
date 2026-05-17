"""
MAIA GPU Scheduler - Inference Queue & VRAM Management

Manages GPU scheduling across concurrent requests:
- VRAM allocation per request
- Request queuing when GPUs are saturated
- Multi-GPU load balancing
- Priority-aware scheduling (TIER_1 > TIER_2 > TIER_3)
"""
