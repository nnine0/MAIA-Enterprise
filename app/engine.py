"""
MAIA Model Engine
==================
Unified model management — loads and orchestrates Granite Sentinel + Gemma4 text.

This is the central entry point for all model inference in the MAIA system.

Architecture:
  ModelEngine
  ├── GraniteSentinel (3.4B) — governance fast-pass / full audit
  │   ├── fast_pass()     single forward pass, logit comparison → PASS/BLOCK
  │   └── audit()         full 10-token generate → PASS/BLOCK/ESCALATE
  └── Gemma4TextModel (4.66B) — text generation
      ├── forward()       single forward pass
      └── generate()      autoregressive decode
"""

import asyncio
import logging
from typing import Optional, Dict, List

import torch

from app.airlock_gateway import _GraniteSentinel, AuditFinding, Verdict

logger = logging.getLogger("MAIA-Engine")


class LocalGemmaClient:
    """Wraps Gemma4TextModel into the BaseModelClient interface for AirlockGateway.

    Allows the gateway to use the local Gemma4 model as its base model
    instead of an external API (OpenAI, Anthropic, etc.).
    """

    def __init__(self, engine: "ModelEngine"):
        self._engine = engine
        self._model_name = "gemma-4-E4B-it"

    async def chat_completion(
        self,
        messages: List[Dict],
        stream: bool = False,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> Dict:
        # Extract the last user message as the prompt
        prompt = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                prompt = content if isinstance(content, str) else str(content)
                break

        response = await self._engine.gemma_generate(
            prompt, max_tokens=max_tokens, temperature=temperature
        )
        return {
            "content": response,
            "tool_calls": [],
            "finish_reason": "stop",
        }

    async def stream_with_breaker(self, messages, egress, **kwargs):
        """Not implemented — streaming through local model."""
        response = await self.chat_completion(messages, **kwargs)
        yield (response["content"], True)


class ModelEngine:
    """Central model engine — loads and manages Granite + Gemma4.

    Usage:
        engine = ModelEngine()
        engine.load_all()
        await engine.granite_fast_pass("What is the weather?")
        await engine.gemma_generate("Tell me a story")
    """

    def __init__(
        self,
        sentinel_path: str = "/models/sentinel",
        gemma_path: str = "/models/speculator",
        tokenizer_path: str = "/models/sentinel",
    ):
        self._sentinel_path = sentinel_path
        self._gemma_path = gemma_path
        self._tokenizer_path = tokenizer_path

        self.granite: Optional[_GraniteSentinel] = None
        self.gemma: Optional["Gemma4TextModel"] = None
        self.gemma_tokenizer = None

        self._loaded = False

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def load_granite(self) -> None:
        """Load Granite Sentinel from /models/sentinel."""
        logger.info("Loading Granite Sentinel...")
        self.granite = _GraniteSentinel(model_id=self._sentinel_path)
        logger.info(
            f"Granite loaded: {type(self.granite.model).__name__}, "
            f"VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB"
        )

    def load_gemma(self) -> None:
        """Load Gemma4 text model (random weights — placeholder)."""
        from app.models.gemma4 import Gemma4TextModel
        from transformers import AutoTokenizer

        logger.info("Loading Gemma4 text model...")
        self.gemma = Gemma4TextModel.materialize(device="cuda")
        self.gemma_tokenizer = AutoTokenizer.from_pretrained(
            self._tokenizer_path, use_fast=True
        )
        if self.gemma_tokenizer.pad_token_id is None:
            self.gemma_tokenizer.pad_token_id = 0
        n_params = sum(p.numel() for p in self.gemma.parameters())
        logger.info(
            f"Gemma4 loaded: {n_params / 1e9:.2f}B params, "
            f"{self.gemma.hidden_size} hidden, "
            f"{len(self.gemma.layers)} layers, "
            f"VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB"
        )

    def load_all(self) -> None:
        """Load both Granite Sentinel and Gemma4 text model."""
        self.load_granite()
        self.load_gemma()
        self._loaded = True
        logger.info(
            f"Engine loaded — total VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB"
        )

    @property
    def loaded(self) -> bool:
        return self._loaded

    # ── Granite Sentinel API ───────────────────────────────────────────────

    async def granite_fast_pass(self, prompt: str) -> AuditFinding:
        """Zero-generation governance check via logit comparison."""
        return await self.granite.fast_pass(prompt)

    async def granite_audit(self, prompt: str) -> AuditFinding:
        """Full governance audit with 10-token generation fallback."""
        return await self.granite.audit(prompt)

    async def granite_audit_batch(self, prompts: list[str]) -> list[AuditFinding]:
        """Batch governance audit."""
        return await self.granite.audit_batch(prompts)

    # ── Gemma4 Generation API ──────────────────────────────────────────────

    async def gemma_forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        """Single forward pass through Gemma4."""
        with torch.inference_mode():
            return self.gemma(input_ids)

    async def gemma_generate(
        self, prompt: str, max_tokens: int = 64, temperature: float = 0.0
    ) -> str:
        """Generate text using Gemma4."""
        inputs = self.gemma_tokenizer(prompt, return_tensors="pt")
        input_ids = inputs["input_ids"].to(self.gemma.device)
        output_ids = self.gemma.generate(
            input_ids, max_new_tokens=max_tokens, temperature=temperature
        )
        return self.gemma_tokenizer.decode(output_ids[0], skip_special_tokens=True)

    # ── Coordinate pipeline ────────────────────────────────────────────────

    async def govern_and_generate(
        self, prompt: str, max_tokens: int = 64
    ) -> dict:
        """Granite governance check → if PASS, Gemma4 generates.

        Returns dict with 'verdict', 'finding', and optionally 'response'.
        """
        finding = await self.granite_fast_pass(prompt)
        if finding.verdict == Verdict.BLOCK:
            return {"verdict": "BLOCK", "finding": finding, "response": None}
        response = await self.gemma_generate(prompt, max_tokens=max_tokens)
        return {"verdict": "PASS", "finding": finding, "response": response}

    # ── Resource info ──────────────────────────────────────────────────────

    def get_vram_info(self) -> dict:
        return {
            "allocated_gb": torch.cuda.memory_allocated() / 1e9,
            "peak_gb": torch.cuda.max_memory_allocated() / 1e9,
            "granite_loaded": self.granite is not None,
            "gemma_loaded": self.gemma is not None,
        }

    def __repr__(self) -> str:
        return (
            f"ModelEngine(granite={'loaded' if self.granite else 'not loaded'}, "
            f"gemma={'loaded' if self.gemma else 'not loaded'}, "
            f"VRAM={torch.cuda.memory_allocated() / 1e9:.2f}GB)"
        )
