"""
MAIA Speculation Configuration
===============================
Configuration for speculative decoding (DFlash, Saguaro/SSD).

CIRCUIT BREAKER MODEL (v3.0):
----------------------------
Layer 9 (Agentic)     → DFlash Block Diffusion (Fast Draft Generation)
Layer 8 (Governance)   → Circuit Breaker Validates + Signs
Layer 7 (Application) → Executes SIGNED trajectories only
"""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class SpeculationConfig:
    enable_dflash: bool = True
    enable_saguaro: bool = False
    
    dflash_model: str = "z-lab/Qwen3.5-27B-DFlash"
    dflash_max_draft_tokens: int = 32
    dflash_block_size: int = 8
    
    saguaro_max_draft_tokens: int = 48
    saguaro_hypothesis_count: int = 3
    saguaro_temperature: float = 0.7
    
    enforce_circuit_breaker: bool = True
    sequential_audit: bool = True
    
    @classmethod
    def from_env(cls) -> "SpeculationConfig":
        return cls(
            enable_dflash=os.getenv("DFLASH_ENABLED", "true").lower() == "true",
            enable_saguaro=os.getenv("SAGUARO_ENABLED", "false").lower() == "true",
            dflash_model=os.getenv("DFLASH_MODEL", "z-lab/Qwen3.5-27B-DFlash"),
            dflash_max_draft_tokens=int(os.getenv("DFLASH_MAX_DRAFT", "32")),
            dflash_block_size=int(os.getenv("DFLASH_BLOCK_SIZE", "8")),
            saguaro_max_draft_tokens=int(os.getenv("SAGUARO_MAX_DRAFT", "48")),
            saguaro_hypothesis_count=int(os.getenv("SAGUARO_HYPOTHESES", "3")),
            saguaro_temperature=float(os.getenv("SAGUARO_TEMP", "0.7")),
            enforce_circuit_breaker=os.getenv("ENFORCE_CB", "true").lower() == "true",
            sequential_audit=os.getenv("SEQUENTIAL_AUDIT", "true").lower() == "true",
        )


speculation_config = SpeculationConfig.from_env()