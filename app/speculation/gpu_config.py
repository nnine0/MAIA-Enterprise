"""
MAIA GPU Configuration for Speculative Decoding
================================================
VRAM estimation and validation for DFlash/Saguaro.

Layer: GPU Kernel (Hardware Abstraction)
"""

from dataclasses import dataclass
from typing import Optional, Dict, Tuple
import torch


@dataclass
class GPUConfig:
    device: str = "cuda"
    total_vram_gb: float = 80.0
    reserved_vram_gb: float = 8.0
    available_vram_gb: float = 72.0
    
    base_model_vram_gb: float = 52.0
    dflash_model_vram_gb: float = 54.0
    
    dflash_overhead_gb: float = 2.0
    saguaro_overhead_gb: float = 4.0
    
    block_size: int = 8
    max_draft_tokens: int = 32
    
    @property
    def can_run_dflash(self) -> bool:
        return self.available_vram_gb >= (self.base_model_vram_gb + self.dflash_overhead_gb)
    
    @property
    def can_run_saguaro(self) -> bool:
        return self.available_vram_gb >= (self.base_model_vram_gb + self.saguaro_overhead_gb)


def get_gpu_config() -> GPUConfig:
    """Auto-detect GPU configuration"""
    if not torch.cuda.is_available():
        return GPUConfig(device="cpu", total_vram_gb=0, available_vram_gb=0)
    
    device_props = torch.cuda.get_device_properties(0)
    total_vram = device_props.total_memory / (1024**3)
    
    return GPUConfig(
        device="cuda",
        total_vram_gb=total_vram,
        available_vram_gb=total_vram - 8.0,
        base_model_vram_gb=min(52.0, total_vram * 0.6),
        dflash_model_vram_gb=min(54.0, total_vram * 0.65),
    )


def validate_vram_requirements(
    config: GPUConfig,
    enable_dflash: bool = False,
    enable_saguaro: bool = False
) -> Tuple[bool, str]:
    """Validate VRAM meets requirements"""
    if enable_dflash and not config.can_run_dflash:
        return False, f"Insufficient VRAM for DFlash: {config.available_vram_gb:.1f}GB available"
    
    if enable_saguaro and not config.can_run_saguaro:
        return False, f"Insufficient VRAM for Saguaro: {config.available_vram_gb:.1f}GB available"
    
    return True, "OK"


gpu_config = get_gpu_config()