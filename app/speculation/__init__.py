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

from .config import SpeculationConfig, speculation_config
from .gpu_config import GPUConfig, gpu_config, get_gpu_config, validate_vram_requirements
from .dflash_engine import DFlashEngine, DraftResult, dflash_engine
from .saguaro_scheduler import SaguaroScheduler, SSDResult, saguaro_scheduler
from .metrics import metrics_collector, SpeculationMetrics
from .kernel import SpeculationKernel, speculation_kernel, get_speculation_kernel

__all__ = [
    "SpeculationConfig",
    "speculation_config",
    "GPUConfig",
    "gpu_config",
    "get_gpu_config",
    "validate_vram_requirements",
    "DFlashEngine",
    "DraftResult",
    "dflash_engine",
    "SaguaroScheduler",
    "SSDResult",
    "saguaro_scheduler",
    "metrics_collector",
    "SpeculationMetrics",
    "SpeculationKernel",
    "speculation_kernel",
    "get_speculation_kernel",
]