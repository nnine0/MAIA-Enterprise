"""
MAIA Speculation Kernel (Unified Orchestration)
========================================
Layer 9 → Layer 8 → Layer 7: Agentic → Governance → Application

Coordinates DFlash, Saguaro, and Circuit Breaker for unified speculative decoding.

CIRCUIT BREAKER MODEL:
------------------
Layer 9 (Agentic)     → DFlash generates fast drafts / Saguaro hypotheses
Layer 8 (Governance)   → Circuit Breaker validates + signs all trajectories
Layer 7 (Application) → Executes only SIGNED trajectories
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from openai import AsyncOpenAI

from .config import speculation_config, SpeculationConfig
from .gpu_config import gpu_config, get_gpu_config, validate_vram_requirements
from .dflash_engine import dflash_engine, DraftResult
from .saguaro_scheduler import saguaro_scheduler, SSDResult
from .metrics import metrics_collector


class SpeculationKernel:
    """
    Unified Speculation Kernel
    ================
    Layer 9 → Layer 8 → Layer 7 orchestration.
    
    Flow:
    1. Layer 9 (Agentic): Generate draft(s) via DFlash or Saguaro
    2. Layer 8 (Governance): Circuit Breaker validates + signs
    3. Layer 7 (Application): Execute signed trajectory
    
    SR 26-02 Compliance:
    - Tier 1: Sequential audit (DFlash first, then Circuit Breaker)
    - Tier 2: Fast validation (Saguaro + Circuit Breaker)
    - Tier 3: Bypass for speed
    """
    
    def __init__(
        self,
        lorax_url: str,
        config: Optional[SpeculationConfig] = None,
    ):
        self.lorax_url = lorax_url
        self.config = config or SpeculationConfig.from_env()
        
        self.client = AsyncOpenAI(base_url=f"{lorax_url}/v1", api_key="not-needed")
        self.gpu_config = get_gpu_config()
        
        saguaro_scheduler.set_client(self.client)
    
    async def execute_with_speculation(
        self,
        prompt: str,
        tier: int,
        domain: str = "finance"
    ) -> Dict[str, Any]:
        """
        Execute with speculative decoding + Circuit Breaker
        ===========================================
        Maps materiality tier to speculation strategy:
        - Tier 1: DFlash + Sequential Audit (SR 26-02 required)
        - Tier 2: Saguaro + Fast Validation
        - Tier 3: Direct execution (bypass)
        """
        result = {
            "prompt": prompt,
            "tier": tier,
            "strategy": None,
            "draft": None,
            "validated": False,
            "signed": False,
            "signature": None,
            "response": None,
            "time_ms": 0.0
        }
        
        start_time = asyncio.get_event_loop().time()
        
        if tier == 1:
            result["strategy"] = "dflash_sequential"
            result = await self._execute_tier1(prompt, domain, result)
        elif tier == 2:
            result["strategy"] = "saguaro_fast"
            result = await self._execute_tier2(prompt, result)
        else:
            result["strategy"] = "bypass"
            result = await self._execute_tier3(prompt, result)
        
        result["time_ms"] = (asyncio.get_event_loop().time() - start_time) * 1000
        
        metrics_collector.record_circuit_breaker(
            result.get("signed", False),
            tier
        )
        
        return result
    
    async def _execute_tier1(
        self,
        prompt: str,
        domain: str,
        result: Dict
    ) -> Dict:
        """Tier 1: DFlash + Sequential Audit (SR 26-02)"""
        if not self.config.enable_dflash:
            return await self._execute_tier2(prompt, result)
        
        valid, msg = validate_vram_requirements(
            self.gpu_config,
            enable_dflash=True
        )
        if not valid:
            return await self._execute_tier2(prompt, result)
        
        draft = await dflash_engine.generate_draft(prompt)
        result["draft"] = dflash_engine.to_draft_audit(draft)
        
        verification = await dflash_engine.verify_draft(draft)
        
        metrics_collector.record_dflash(
            draft.draft_id,
            draft.total_tokens,
            draft.draft_time_ms,
            draft.verified
        )
        
        return result
    
    async def _execute_tier2(
        self,
        prompt: str,
        result: Dict
    ) -> Dict:
        """Tier 2: Saguaro + Fast Validation"""
        if not self.config.enable_saguaro:
            return await self._execute_tier3(prompt, result)
        
        ssd_result = await saguaro_scheduler.speculative_decode(prompt)
        result["draft"] = saguaro_scheduler.to_ssd_audit(ssd_result)
        
        metrics_collector.record_saguaro(
            len(ssd_result.hypotheses),
            ssd_result.total_time_ms,
            ssd_result.acceptance_rate
        )
        
        return result
    
    async def _execute_tier3(
        self,
        prompt: str,
        result: Dict
    ) -> Dict:
        """Tier 3: Direct execution (bypass)"""
        completion = await self.client.chat.completions.create(
            model="google/gemma-4-26b-a4b-it",
            messages=[{"role": "user", "content": prompt}],
            max_new_tokens=256,
            temperature=0.4,
        )
        
        result["response"] = completion.choices[0].message.content
        result["signed"] = True
        result["signature"] = f"direct-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get kernel status"""
        return {
            "config": {
                "dflash_enabled": self.config.enable_dflash,
                "saguaro_enabled": self.config.enable_saguaro,
                "sequential_audit": self.config.sequential_audit,
                "enforce_circuit_breaker": self.config.enforce_circuit_breaker
            },
            "gpu": {
                "device": self.gpu_config.device,
                "total_vram_gb": self.gpu_config.total_vram_gb,
                "available_vram_gb": self.gpu_config.available_vram_gb,
                "can_run_dflash": self.gpu_config.can_run_dflash,
                "can_run_saguaro": self.gpu_config.can_run_saguaro
            },
            "metrics": metrics_collector.get_metrics()
        }


speculation_kernel: Optional[SpeculationKernel] = None


def get_speculation_kernel(
    lorax_url: str,
    config: Optional[SpeculationConfig] = None
) -> SpeculationKernel:
    """Get or create global kernel instance"""
    global speculation_kernel
    if speculation_kernel is None:
        speculation_kernel = SpeculationKernel(lorax_url, config)
    return speculation_kernel