"""
MAIA GPU Configuration for Unified Speculative Stack
======================================================
VRAM estimation and validation for MTP/DFlash/Saguaro.

Layer: GPU Kernel (Hardware Abstraction)

HARDWARE SUBSTRATE SPECS:
----------------------
| GPU              | VRAM   | Bandwidth    | FP32 TFLOPS |
|-----------------|--------|-------------|------------|
| RTX 3090         | 24GB  | 936 GB/s    | 35.6       |
| H100 (SXM5)      | 80GB  | 3,350 GB/s  | 67 / 2000* |
                  |       |             | (* FP8)     |

MAIA NEURAL OS OVERHEAD (Gemma 4 26B A4B MoE):
---------------------------------------
| Component                | VRAM   | Notes                    |
|------------------------|--------|--------------------------|
| Base Model (4-bit)        | 14.5 GB| Quantized                |
| PVI Airlock (E2B 4-bit)| 1.8 GB| Governance              |
| Kernel/Shared KV Cache  | 1.5 GB| MTP shared               |
| FIXED VRAM RENT         | 17.8 GB| No additional overhead   |

MTP KEY: Uses shared KV cache with base model - near-zero VRAM overhead.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Tuple
import os

# Try importing torch, but allow fallback for testing
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


@dataclass
class GPUConfig:
    device: str = "cuda"
    total_vram_gb: float = 80.0
    reserved_vram_gb: float = 8.0
    available_vram_gb: float = 72.0
    
    # Gemma 4 26B (4-bit quantized)
    base_model_vram_gb: float = 14.5
    
    # PVI Airlock (E2B 4-bit)
    airlock_vram_gb: float = 1.8
    
    # Kernel + Shared KV Cache
    kernel_vram_gb: float = 1.5
    
    # Fixed VRAM Rent (total baseline)
    fixed_vram_rent_gb: float = 17.8
    
    # MTP: Near-zero overhead (shared KV cache)
    mtp_overhead_gb: float = 0.1
    
    # DFlash adapter
    dflash_overhead_gb: float = 2.0
    
    # Saguaro/SSD hypotheses
    saguaro_overhead_gb: float = 4.0
    
    block_size: int = 8
    max_draft_tokens: int = 32
    mtp_draft_tokens: int = 4
    
    @property
    def can_run_mtp(self) -> bool:
        """MTP uses shared KV - near-zero overhead"""
        return self.available_vram_gb >= (self.fixed_vram_rent_gb + self.mtp_overhead_gb)
    
    @property
    def can_run_dflash(self) -> bool:
        """DFlash adds adapter overhead"""
        return self.available_vram_gb >= (self.fixed_vram_rent_gb + self.dflash_overhead_gb)
    
    @property
    def can_run_saguaro(self) -> bool:
        """Saguaro adds hypothesis overhead"""
        return self.available_vram_gb >= (self.fixed_vram_rent_gb + self.saguaro_overhead_gb)
    
    @property
    def can_run_full_stack(self) -> bool:
        """Full MTP + DFlash + Saguaro stack"""
        return self.available_vram_gb >= (self.fixed_vram_rent_gb + self.dflash_overhead_gb + self.saguaro_overhead_gb)


def get_gpu_config() -> GPUConfig:
    """Auto-detect GPU configuration"""
    if not torch.cuda.is_available():
        return GPUConfig(device="cpu", total_vram_gb=0, available_vram_gb=0)
    
    device_props = torch.cuda.get_device_properties(0)
    total_vram = device_props.total_memory / (1024**3)
    
    # Estimate fixed VRAM rent (constant regardless of GPU)
    fixed_rent = 17.8
    
    return GPUConfig(
        device="cuda",
        total_vram_gb=total_vram,
        available_vram_gb=total_vram - 8.0,
        fixed_vram_rent_gb=fixed_rent,
    )


def validate_vram_requirements(
    config: GPUConfig,
    enable_mtp: bool = True,
    enable_dflash: bool = False,
    enable_saguaro: bool = False
) -> Tuple[bool, str]:
    """Validate VRAM meets requirements"""
    if enable_mtp and not config.can_run_mtp:
        return False, f"Insufficient VRAM for MTP: {config.available_vram_gb:.1f}GB available"
    
    if enable_dflash and not config.can_run_dflash:
        return False, f"Insufficient VRAM for DFlash: {config.available_vram_gb:.1f}GB available"
    
    if enable_saguaro and not config.can_run_saguaro:
        return False, f"Insufficient VRAM for Saguaro: {config.available_vram_gb:.1f}GB available"
    
    return True, "OK"


gpu_config = get_gpu_config()