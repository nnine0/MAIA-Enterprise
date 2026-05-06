"""
MAIA Kernel - vLLM Speculative Decoding Configuration
========================================

Model Selection (Microkernel Bundle):
- Target (Verifier): ibm-granite/granite-4.1-3b (~3.2GB INT4)
- Drafter (Proposer): HuggingFaceTB/nanowhale-100m (~400MB)
- Embedding (Latent Hash): ibm-granite/granite-embedding-97m (~200MB)

The MAIA Kernel uses vLLM's superior speculative decoding + Multi-LoRA support.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import Enum


class ModelSize(Enum):
    """Model size classifications"""
    SMALL = "small"      # < 3B params
    MEDIUM = "medium"  # 3-10B params  
    LARGE = "large"    # > 10B params


@dataclass
class ModelBundle:
    """The MAIA Microkernel Bundle"""
    # Target model (Verifier) - granite-4.1-3b
    target_model: str = "ibm-granite/granite-4.1-3b"
    target_size_gb: float = 3.2  # INT4/AWQ
    
    # Drafter model (Proposer) - nanowhale-100m  
    drafter_model: str = "HuggingFaceTB/nanowhale-100m"
    drafter_size_gb: float = 0.4
    
    # Embedding model (Latent Hash)
    embedding_model: str = "ibm-granite/granite-embedding-97m"
    embedding_size_gb: float = 0.2
    
    @property
    def total_vram_gb(self) -> float:
        """Total VRAM for the bundle"""
        return self.target_size_gb + self.drafter_size_gb + self.embedding_size_gb


@dataclass
class LoRAConfig:
    """Multi-LoRA configuration"""
    enabled: bool = True
    max_loras: int = 20
    max_lora_rank: int = 64
    lora_dtype: str = "float16"


@dataclass
class SpeculationConfig:
    """Speculative decoding configuration"""
    enabled: bool = True
    drafter_model: str = "HuggingFaceTB/nanowhale-100m"
    num_speculative_tokens: int = 5
    
    @property
    def vram_overhead_gb(self) -> float:
        """VRAM needed for speculative decoding (minimal)"""
        return 0.4  # Nanowhale is small


@dataclass
class VRAMReservation:
    """VRAM reservation for various components"""
    kernel_utilization: float = 0.90  # 90% for inference
    latent_hash_reserved: float = 0.05  # 5% for latent hashing
    adapter_pool_reserved: float = 0.05  # 5% for dynamic adapters
    
    @property
    def total_reserved(self) -> float:
        return self.kernel_utilization + self.latent_hash_reserved + self.adapter_pool_reserved


@dataclass
class MAIAKernelConfig:
    """Complete MAIA Kernel configuration"""
    # Model bundle
    models: ModelBundle = field(default_factory=ModelBundle)
    
    # Speculative decoding
    speculation: SpeculationConfig = field(default_factory=SpeculationConfig)
    
    # Multi-LoRA
    lora: LoRAConfig = field(default_factory=LoRAConfig)
    
    # VRAM management  
    vram: VRAMReservation = field(default_factory=VRAMReservation)
    
    # Context
    max_context_len: int = 8192
    trust_remote_code: bool = True
    
    @property
    def total_vram_gb(self) -> float:
        """Total VRAM footprint"""
        return self.models.total_vram_gb
    
    def get_vllm_args(self) -> List[str]:
        """Generate vLLM command arguments"""
        args = [
            "vllm", "serve", self.models.target_model,
            "--speculative-model", self.speculation.drafter_model,
            "--num-speculative-tokens", str(self.speculation.num_speculative_tokens),
            "--enable-lora",
            "--max-loras", str(self.lora.max_loras),
            "--max-lora-rank", str(self.lora.max_lora_rank),
            "--gpu-memory-utilization", str(self.vram.kernel_utilization),
            "--max-model-len", str(self.max_context_len),
            "--trust-remote-code" if self.trust_remote_code else "",
        ]
        return [a for a in args if a]  # Filter empty strings


@dataclass  
class SectorAdapter:
    """Sector-specific LoRA adapter"""
    sector_id: str
    sector_name: str
    lora_name: str
    min_margin: Optional[float] = None
    max_margin: Optional[float] = None
    requires_dhitl: bool = False
    policy_hashes: Optional[Dict] = None  # Latent hash signatures


# Default sector adapters
DEFAULT_ADAPTERS = [
    SectorAdapter(
        sector_id="finance_insurance",
        sector_name="Finance & Insurance",
        lora_name="finance_insurance_adapter",
        min_margin=0.05,
        requires_dhitl=True,
    ),
    SectorAdapter(
        sector_id="government_public", 
        sector_name="Government & Public Sector",
        lora_name="government_public_adapter",
        min_margin=0.05,
        requires_dhitl=True,
    ),
    SectorAdapter(
        sector_id="biotech_pharma",
        sector_name="Biotech & Pharma", 
        lora_name="biotech_pharma_adapter",
        min_margin=None,
        requires_dhitl=False,
    ),
    SectorAdapter(
        sector_id="real_estate",
        sector_name="Real Estate",
        lora_name="real_estate_adapter",
        max_margin=0.80,
        requires_dhitl=False,
    ),
    SectorAdapter(
        sector_id="general",
        sector_name="General",
        lora_name="general_adapter", 
        min_margin=None,
        requires_dhitl=False,
    ),
]


# Factory function
def create_kernel_config(
    target_model: str = "ibm-granite/granite-4.1-3b",
    drafter_model: str = "HuggingFaceTB/nanowhale-100m",
    max_loras: int = 20,
    vram_utilization: float = 0.90
) -> MAIAKernelConfig:
    """Create a configured MAIA Kernel"""
    return MAIAKernelConfig(
        models=ModelBundle(
            target_model=target_model,
            drafter_model=drafter_model,
        ),
        speculation=SpeculationConfig(
            drafter_model=drafter_model,
        ),
        lora=LoRAConfig(
            max_loras=max_loras,
        ),
        vram=VRAMReservation(
            kernel_utilization=vram_utilization,
        ),
    )


# Example usage
if __name__ == "__main__":
    config = create_kernel_config()
    
    print("=== MAIA Kernel Configuration ===")
    print(f"Target Model: {config.models.target_model}")
    print(f"Drafter Model: {config.models.drafter_model}")
    print(f"Embedding Model: {config.models.embedding_model}")
    print(f"Total VRAM: {config.total_vram_gb}GB")
    print()
    print(f"Speculation: {config.speculation.num_speculative_tokens} tokens")
    print(f"Max LoRAs: {config.lora.max_loras}")
    print(f"GPU Utilization: {config.vram.kernel_utilization}")
    print()
    print("=== vLLM Launch Command ===")
    print(" ".join(config.get_vllm_args()))
    print()
    print("=== Sector Adapters ===")
    for adapter in DEFAULT_ADAPTERS:
        print(f"  {adapter.sector_id}: {adapter.lora_name}")
        if adapter.min_margin:
            print(f"    Min margin: {adapter.min_margin:.0%}")
        if adapter.requires_dhitl:
            print(f"    DHITL required")