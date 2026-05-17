"""
MAIA Speculation Module
=====================
Speculative decoding modules: DFlash, Saguaro/SSD, GPU config, metrics.

CIRCUIT BREAKER MODEL:
--------------------
Layer 9 (Agentic)     → DFlash block diffusion / Saguaro hypotheses
Layer 8 (Governance)   → Circuit Breaker: validates + signs
Layer 7 (Application) → Executes only SIGNED trajectories

Modules:
- config.py: Configuration with environment overrides
- gpu_config.py: VRAM estimation and validation
- dflash_engine.py: Block diffusion drafting (DFlash)
- saguaro_scheduler.py: Async SSD (Saguaro)
- metrics.py: Thread-safe statistics
- kernel.py: Unified orchestration

DFlash Paper: arXiv:2602.06036
SSD/Saguaro Paper: arXiv:2603.03251
"""
