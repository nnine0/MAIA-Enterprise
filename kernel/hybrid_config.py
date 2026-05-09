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

from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json


class Quantization(str, Enum):
    NVFP4 = "nvfp4"  # NVIDIA 4-bit float (A100+/H100)
    INT4 = "int4"     # INT4 quantization
    FP8 = "fp8"       # Float8 (shared KV cache)
    BF16 = "bf16"     # BF16 (high precision fallback)


class ModelRole(str, Enum):
    BASE_ENGINE = "base_engine"        # L9/L7: Neural compute engine
    SPECULATOR = "speculator"          # L9: DFlash parallel drafting
    SHERIFF = "sheriff"                # L8: Nemotron safety auditor
    SENTINEL = "sentinel"              # L8: Granite compliance guardian
    GOVERNOR = "governor"              # L8: Orchestrator/controller


@dataclass
class ModelConfig:
    name: str
    role: ModelRole
    quantization: Quantization
    vram_mb: int
    max_batch_size: int = 16
    max_seq_len: int = 32768
    tensor_parallel: int = 1
    gpu_memory_utilization: float = 0.92
    speculative_tokens: int = 16
    prefix_caching: bool = True
    adapter_ids: List[str] = field(default_factory=list)
    priority: int = 0
    local_path: Optional[str] = None  # Local path override


@dataclass
class VRAMBudget:
    total_mb: int = 24576  # 24GB RTX 3090
    base_model_mb: int = 14000
    speculator_mb: int = 512
    sheriff_mb: int = 2253
    sentinel_mb: int = 1229
    kv_cache_mb: int = 2256
    speculative_buffer_mb: int = 6250  # ~6.1 GB operational runway
    
    @property
    def utilization(self) -> float:
        allocated = self.base_model_mb + self.speculator_mb + self.sheriff_mb + self.sentinel_mb + self.kv_cache_mb
        return allocated / self.total_mb
    
    @property
    def runway_mb(self) -> int:
        allocated = self.base_model_mb + self.sheriff_mb + self.sentinel_mb + self.kv_cache_mb
        return self.total_mb - allocated


@dataclass
class KernelIPCConfig:
    mode: str = "shared_memory"  # shared_memory | unix_domain_socket | tcp
    socket_path: str = "/tmp/maia_kernel.sock"
    shm_path: str = "/dev/shm/maia"
    shm_size_mb: int = 512
    zero_copy: bool = True


@dataclass
class SpeculativeConfig:
    enabled: bool = True
    dflash_blocks: int = 16
    saguaro_enabled: bool = True
    saguaro_verify_inference: bool = True
    draft_temperature: float = 0.4
    verify_temperature: float = 0.1
    max_draft_tokens: int = 32
    rejection_threshold: float = 0.8


@dataclass
class SVPMetrics:
    context_switch_latency_ms: float = 0.0
    audit_resolution_pct: float = 0.0
    vram_utilization_pct: float = 0.0
    human_machine_parity: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "context_switch_latency_ms": self.context_switch_latency_ms,
            "audit_resolution_pct": self.audit_resolution_pct,
            "vram_utilization_pct": self.vram_utilization_pct,
            "human_machine_parity": self.human_machine_parity,
            "svp_status": "OPTIMAL" if self.context_switch_latency_ms < 20 and self.audit_resolution_pct == 100 else "DEGRADED"
        }


class ModelStratifier:
    """
    VRAM-optimized model stratification.
    
    Implements the "VRAM Cheat Code" - fits complete stack into 24GB:
    - Sparse MoE (26B params, only ~4B active) via NVFP4
    - Shared KV cache for speculative drafts
    - Batched Actor + Auditor in single forward pass via SGMV
    """
    
    MODELS: Dict[str, ModelConfig] = {
        "base_engine": ModelConfig(
            name="google/gemma-4-E4B",
            role=ModelRole.BASE_ENGINE,
            quantization=Quantization.FP8,
            vram_mb=8192,
            max_batch_size=32,
            max_seq_len=131072,
            speculative_tokens=16,
            prefix_caching=True,
            adapter_ids=["governance", "finance", "safety", "legal", "health"],
            local_path="/models/base_engine"
        ),
        "speculator": ModelConfig(
            name="google/gemma-4-E4B-it-assistant",
            role=ModelRole.SPECULATOR,
            quantization=Quantization.FP8,
            vram_mb=2048,
            max_batch_size=64,
            speculative_tokens=16,
            prefix_caching=True,
            adapter_ids=["draft_head"],
            local_path="/models/speculator"
        ),
        "sheriff": ModelConfig(
            name="nvidia/Nemotron-3-8B-Safety",
            role=ModelRole.SHERIFF,
            quantization=Quantization.INT4,
            vram_mb=2253,
            max_batch_size=32,
            max_seq_len=32768,
            adapter_ids=["safety_auditor"],
            local_path="/models/sheriff"
        ),
        "sentinel": ModelConfig(
            name="ibm/granite-4.1-3b",
            role=ModelRole.SENTINEL,
            quantization=Quantization.FP8,
            vram_mb=1229,
            max_batch_size=32,
            max_seq_len=32768,
            adapter_ids=["compliance_guardian"],
            local_path="/models/sentinel"
        )
    }
    
    def __init__(self, vram_budget: Optional[VRAMBudget] = None):
        self.budget = vram_budget or VRAMBudget()
        self.models = self.MODELS.copy()
        self._validate_budget()
    
    def _validate_budget(self) -> bool:
        allocated = sum(m.vram_mb for m in self.models.values())
        overhead = allocated - self.budget.total_mb
        
        if overhead > 0:
            print(f"[WARN] VRAM over-allocated by {overhead} MB")
            return False
        return True
    
    def get_model_config(self, role: ModelRole) -> Optional[ModelConfig]:
        for model in self.models.values():
            if model.role == role:
                return model
        return None
    
    def get_speculative_config(self) -> SpeculativeConfig:
        return SpeculativeConfig(
            enabled=True,
            dflash_blocks=16,
            saguaro_enabled=True,
            saguaro_verify_inference=True
        )
    
    def get_ipc_config(self) -> KernelIPCConfig:
        return KernelIPCConfig(
            mode="shared_memory",
            shm_size_mb=512,
            zero_copy=True
        )
    
    def get_vram_breakdown(self) -> Dict:
        return {
            "total_mb": self.budget.total_mb,
            "base_engine_mb": self.models["base_engine"].vram_mb,
            "speculator_mb": self.models["speculator"].vram_mb,
            "sheriff_mb": self.models["sheriff"].vram_mb,
            "sentinel_mb": self.models["sentinel"].vram_mb,
            "allocated_mb": sum(m.vram_mb for m in self.models.values()),
            "runway_mb": self.budget.runway_mb,
            "utilization_pct": round(self.budget.utilization * 100, 1)
        }


def create_stratifier(
    vram_mb: int = 24576,
    h100_mode: bool = False
) -> ModelStratifier:
    """
    Create model stratifier with VRAM budget.
    
    Args:
        vram_mb: Total VRAM (24576 for RTX 3090, 81920 for H100)
        h100_mode: Use H100-optimized quantization (higher precision)
    """
    if h100_mode:
        budget = VRAMBudget(
            total_mb=vram_mb,
            base_model_mb=20000,
            speculator_mb=2048,
            sheriff_mb=4096,
            sentinel_mb=2048,
            kv_cache_mb=8192,
            speculative_buffer_mb=45000
        )
    else:
        budget = VRAMBudget(total_mb=vram_mb)
    
    return ModelStratifier(budget)


def get_kernel_manifest() -> Dict:
    """
    Generate SGLang + LoRAX hybrid kernel manifest.
    """
    stratifier = create_stratifier()
    
    manifest = {
        "manifest_version": "2.0.0",
        "kernel_type": "sglang_lorax_hybrid",
        "vram_budget": stratifier.get_vram_breakdown(),
        "ipc": {
            "mode": "shared_memory",
            "socket_path": "/tmp/maia_kernel.sock",
            "shm_path": "/dev/shm/maia",
            "zero_copy": True
        },
        "models": {},
        "speculative": {
            "enabled": True,
            "dflash_blocks": 16,
            "saguaro_scheduler": True,
            "verify_inference": True
        }
    }
    
    for name, config in stratifier.models.items():
        manifest["models"][name] = {
            "name": config.name,
            "role": config.role.value,
            "quantization": config.quantization.value,
            "vram_mb": config.vram_mb,
            "max_batch_size": config.max_batch_size,
            "max_seq_len": config.max_seq_len,
            "prefix_caching": config.prefix_caching,
            "adapters": config.adapter_ids
        }
    
    return manifest


if __name__ == "__main__":
    print("=== MAIA Hybrid Kernel Configuration ===\n")
    
    stratifier = create_stratifier()
    vram = stratifier.get_vram_breakdown()
    
    print("VRAM Budget (24GB RTX 3090):")
    for key, value in vram.items():
        print(f"  {key}: {value}")
    
    print(f"\nUtilization: {vram['utilization_pct']}%")
    print(f"Operational Runway: {vram['runway_mb']} MB")
    
    print("\n--- Kernel Manifest ---")
    manifest = get_kernel_manifest()
    print(json.dumps(manifest, indent=2))
