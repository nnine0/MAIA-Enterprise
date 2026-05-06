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

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import Enum


class ModelSize(Enum):
    """Model size classifications"""
    E2B = "E2B"      # Efficient 2B
    E4B = "E4B"      # Efficient 4B (Gemma 4)
    E8B = "E8B"      # Efficient 8B


@dataclass
class ModelBundle:
    """The MAIA Microkernel Bundle - Gemma 4 version"""
    # Target model (Verifier) - Gemma 4 E4B
    target_model: str = "google/gemma-4-E4B-it"
    target_size_gb: float = 4.2  # INT4
    
    # Drafter model (Proposer) - Google's native speculative
    drafter_model: str = "google/gemma-4-E4B-it-assistant"
    drafter_size_gb: float = 0.6
    
    # Embedding model (for latent hashing)
    embedding_model: str = "google/gemma-4-embedding-2b"
    embedding_size_gb: float = 0.8
    
    @property
    def total_vram_gb(self) -> float:
        """Total VRAM for the bundle"""
        return self.target_size_gb + self.drafter_size_gb + self.embedding_size_gb
    
    @property
    def is_thinking_capable(self) -> bool:
        """Gemma 4 native thinking"""
        return True


@dataclass
class ThinkingConfig:
    """Gemma 4 thinking/reasoning configuration"""
    enabled: bool = True
    max_thinking_tokens: int = 8192
    thinking_tag_start: str = "<|channel>thought"
    thinking_tag_end: str = "<|channel|>"
    
    # Deceptive alignment detection
    detect_internal_reasoning: bool = True
    scan_for_policy_violations: bool = True


@dataclass
class MultiModalConfig:
    """Vision/multimodal configuration"""
    enabled: bool = True
    max_resolution: int = 2048
    supported_formats: List[str] = field(default_factory=lambda: ["jpeg", "png", "webp"])
    
    # OSHA-style hazard detection
    safety_hazard_detection: bool = True
    attention_map_monitoring: bool = True


@dataclass
class LoRAConfig:
    """Multi-LoRA configuration - Gemma 4 optimized"""
    enabled: bool = True
    max_loras: int = 10
    max_lora_rank: int = 64
    lora_dtype: str = "float16"
    
    # Gemma 4 hybrid attention modules
    target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ])


@dataclass
class SpeculationConfig:
    """Speculative decoding configuration"""
    enabled: bool = True
    drafter_model: str = "google/gemma-4-E4B-it-assistant"
    num_speculative_tokens: int = 16  # Higher for Gemma 4
    
    @property
    def vram_overhead_gb(self) -> float:
        """VRAM needed for speculative decoding"""
        return 0.6  # Drafter is small


@dataclass
class VRAMReservation:
    """VRAM reservation for various components"""
    kernel_utilization: float = 0.95  # 95% for Gemma 4
    thinking_pool: float = 0.02     # 2% for thinking tokens
    vision_pool: float = 0.03     # 3% for multimodal
    
    @property
    def total_reserved(self) -> float:
        return self.kernel_utilization + self.thinking_pool + self.vision_pool


@dataclass
class MAIAKernelConfig:
    """Complete MAIA Kernel configuration - Gemma 4 version"""
    # Model bundle
    models: ModelBundle = field(default_factory=ModelBundle)
    
    # Thinking configuration
    thinking: ThinkingConfig = field(default_factory=ThinkingConfig)
    
    # Multimodal configuration
    multimodal: MultiModalConfig = field(default_factory=MultiModalConfig)
    
    # Speculative decoding
    speculation: SpeculationConfig = field(default_factory=SpeculationConfig)
    
    # Multi-LoRA
    lora: LoRAConfig = field(default_factory=LoRAConfig)
    
    # VRAM management  
    vram: VRAMReservation = field(default_factory=VRAMReservation)
    
    # Context
    max_context_len: int = 32768  # Gemma 4 supports 128K
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
            "--enable-thinking" if self.thinking.enabled else "",
            "--enable-lora" if self.lora.enabled else "",
            "--max-loras", str(self.lora.max_loras),
            "--max-lora-rank", str(self.lora.max_lora_rank),
            "--gpu-memory-utilization", str(self.vram.kernel_utilization),
            "--max-model-len", str(self.max_context_len),
            "--trust-remote-code" if self.trust_remote_code else "",
        ]
        return [a for a in args if a]  # Filter empty strings


# Factory function for Gemma 4
def create_gemma4_kernel(
    target_model: str = "google/gemma-4-E4B-it",
    drafter_model: str = "google/gemma-4-E4B-it-assistant",
    max_loras: int = 10,
    vram_utilization: float = 0.95
) -> MAIAKernelConfig:
    """Create a configured Gemma 4 MAIA Kernel"""
    return MAIAKernelConfig(
        models=ModelBundle(
            target_model=target_model,
            drafter_model=drafter_model,
        ),
        thinking=ThinkingConfig(
            enabled=True,
            max_thinking_tokens=8192,
        ),
        speculation=SpeculationConfig(
            drafter_model=drafter_model,
        ),
        lora=LoRAConfig(
            max_loras=max_loras,
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj"
            ],
        ),
        vram=VRAMReservation(
            kernel_utilization=vram_utilization,
        ),
    )


# Example usage
if __name__ == "__main__":
    config = create_gemma4_kernel()
    
    print("=== MAIA Kernel Configuration (Gemma 4) ===")
    print(f"Target Model: {config.models.target_model}")
    print(f"Drafter Model: {config.models.drafter_model}")
    print(f"Total VRAM: {config.total_vram_gb}GB")
    print()
    print(f"Thinking: {config.thinking.enabled}")
    print(f"  Max tokens: {config.thinking.max_thinking_tokens}")
    print()
    print(f"Speculation: {config.speculation.num_speculative_tokens} tokens")
    print(f"Max LoRAs: {config.lora.max_loras}")
    print(f"Target modules: {config.lora.target_modules}")
    print(f"GPU Utilization: {config.vram.kernel_utilization}")
    print()
    print("=== vLLM Launch Command ===")
    print(" ".join(config.get_vllm_args()))