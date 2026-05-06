"""
MAIA Speculation Configuration
==============================
Configuration for Unified Speculative Stack (MTP + DFlash + Saguaro/SSD).

MTP PROPOSER/VERIFIER ARCHITECTURE (v4.0):
-----------------------------------
The key innovation: Proposer and Verifier have DIFFERENT adapter relationships.

Layer 9 - MTP Proposer (Adapter-Agnostic):
  - Uses base model ONLY (no adapter loading)
  - Drafts based on general language patterns
  - Near-zero VRAM overhead (shared KV cache from base)
  - Can be small/fast (fewer heads, no weight dependencies)

Layer 8 - MTP Verifier (Adapter-Strict):
  - MUST validate against loaded adapter weights  
  - Enforces physical constraints (SR 26-02, sector rules)
  - Rejects adapter-incompatible drafts
  - Uses adapter's LoRA weights for validation

CIRCUIT BREAKER MODEL (v3.0):
----------------------------
Layer 8 (Governance)   → SSD/Saguaro Async Audit + Circuit Breaker Validates + Signs
Layer 7 (Application) → Executes SIGNED trajectories only
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum
import os


class ProposerMode(Enum):
    """MTP Proposer modes"""
    BASE_ONLY = "base_only"  # Adapter-agnostic, uses base model
    ADAPTER_AWARE = "adapter_aware"  # Has adapter awareness (larger)


class VerifierMode(Enum):
    """MTP Verifier modes"""
    STRICT = "strict"  # Full adapter weight validation
    LAX = "lax"  # Faster, less accurate
    NONE = "none"  # Disabled


@dataclass
class MTPConfig:
    """Multi-Token Prediction configuration"""
    
    enable: bool = True
    draft_tokens: int = 4
    
    # Proposer configuration (Adapter-Agnostic)
    proposer_mode: ProposerMode = ProposerMode.BASE_ONLY
    proposer_size: str = "small"  # small, medium, large
    
    # Verifier configuration (Adapter-Strict)
    verifier_mode: VerifierMode = VerifierMode.STRICT
    enforce_weight_constraints: bool = True
    
    # Shared KV cache (no additional VRAM)
    use_shared_kv: bool = True
    
    # VRAM calculation
    @property
    def vram_overhead_mb(self) -> int:
        """Additional VRAM needed for MTP (proposer only, verifier uses adapter)"""
        if self.use_shared_kv:
            return 0  # Uses base model KV cache
        # Proposer heads only
        sizes = {"small": 512, "medium": 1024, "large": 2048}
        return sizes.get(self.proposer_size, 512)


@dataclass
class DFlashConfig:
    """Block Diffusion configuration"""
    
    enable: bool = True
    model: str = "z-lab/Qwen3.5-27B-DFlash"
    max_draft_tokens: int = 32
    block_size: int = 8


@dataclass
class SaguaroConfig:
    """Tree-based speculative decoding"""
    
    enable: bool = False
    max_draft_tokens: int = 48
    hypothesis_count: int = 3
    temperature: float = 0.7


@dataclass  
class SpeculationConfig:
    """Unified speculation configuration"""
    
    enable_mtp: bool = True
    mtp_config: MTPConfig = field(default_factory=MTPConfig)
    
    enable_dflash: bool = True
    dflash_config: DFlashConfig = field(default_factory=DFlashConfig)
    
    enable_saguaro: bool = False
    saguaro_config: SaguaroConfig = field(default_factory=SaguaroConfig)
    
    # Circuit breaker
    enforce_circuit_breaker: bool = True
    sequential_audit: bool = True
    
    # VRAM summary
    @property
    def total_vram_overhead_mb(self) -> int:
        """Total additional VRAM for speculation"""
        total = self.mtp_config.vram_overhead_mb
        if self.enable_dflash:
            total += 8192  # DFlash model
        return total
    
    @classmethod
    def from_env(cls) -> "SpeculationConfig":
        return cls(
            enable_mtp=os.getenv("MTP_ENABLED", "true").lower() == "true",
            mtp_config=MTPConfig(
                enable=os.getenv("MTP_ENABLED", "true").lower() == "true",
                draft_tokens=int(os.getenv("MTP_DRAFT_TOKENS", "4")),
            ),
            enable_dflash=os.getenv("DFLASH_ENABLED", "true").lower() == "true",
            dflash_config=DFlashConfig(
                model=os.getenv("DFLASH_MODEL", "z-lab/Qwen3.5-27B-DFlash"),
            ),
            enable_saguaro=os.getenv("SAGUARO_ENABLED", "false").lower() == "true",
            enforce_circuit_breaker=os.getenv("ENFORCE_CB", "true").lower() == "true",
            sequential_audit=os.getenv("SEQUENTIAL_AUDIT", "true").lower() == "true",
        )


speculation_config = SpeculationConfig.from_env()


# Example usage
if __name__ == "__main__":
    config = speculation_config
    
    print("=== MTP Proposer/Verifier Configuration ===")
    print(f"Proposer Mode: {config.mtp_config.proposer_mode.value}")
    print(f"  Adapter-Agnostic: {config.mtp_config.proposer_mode == ProposerMode.BASE_ONLY}")
    print(f"  Proposer Size: {config.mtp_config.proposer_size}")
    print(f"  Shared KV: {config.mtp_config.use_shared_kv}")
    print(f"  VRAM Overhead: {config.mtp_config.vram_overhead_mb}MB")
    print()
    print(f"Verifier Mode: {config.mtp_config.verifier_mode.value}")
    print(f"  Adapter-Strict: {config.mtp_config.verifier_mode == VerifierMode.STRICT}")
    print(f"  Enforce Weight Constraints: {config.mtp_config.enforce_weight_constraints}")
    print()
    print(f"Total VRAM Overhead: {config.total_vram_overhead_mb}MB")
    print()
    print("Key Insight:")
    print("- Proposer: Uses base model ONLY (near-zero VRAM)")
    print("- Verifier: Validates against loaded adapter weights")
    print("- Result: MTP is effectively 'free' for VRAM")