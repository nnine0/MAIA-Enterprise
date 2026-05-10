"""
Gemma 4 E4B-it Text Benchmark Model
====================================
Random-weight PyTorch model matching Gemma4 text architecture for
latency benchmarking. No safetensors loading needed.

Architecture:
  - 42 transformer layers
  - hidden_size=2560, intermediate_size=10240
  - 8 attention heads, 2 KV heads (GQA)
  - SwiGLU MLP, RMSNorm, RoPE
  - bfloat16 on CUDA
"""

import logging
import math
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger("MAIA-Gemma4Bench")


class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(dim))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = torch.sqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)
        return x / rms * self.weight


def precompute_rope_frequencies(dim: int, max_len: int, theta: float = 10000.0) -> torch.Tensor:
    freqs = 1.0 / (theta ** (torch.arange(0, dim, 2, dtype=torch.float32) / dim))
    t = torch.arange(max_len, dtype=torch.float32)
    return torch.outer(t, freqs)


def apply_rope(x: torch.Tensor, freqs: torch.Tensor) -> torch.Tensor:
    # x: [B, H, T, D] or [T, B, H, D]
    # freqs: [T, D/2]
    T = x.shape[-3] if x.dim() == 4 else x.shape[0]
    cos = freqs[:T].cos()
    sin = freqs[:T].sin()
    x1 = x[..., :x.shape[-1] // 2]
    x2 = x[..., x.shape[-1] // 2:]
    cos = cos.unsqueeze(0).unsqueeze(2) if x.dim() == 4 else cos.unsqueeze(1)
    sin = sin.unsqueeze(0).unsqueeze(2) if x.dim() == 4 else sin.unsqueeze(1)
    return torch.cat([x1 * cos - x2 * sin, x1 * sin + x2 * cos], dim=-1)


class Attention(nn.Module):
    def __init__(self, hidden_size: int, num_heads: int, num_kv_heads: int):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.num_kv_heads = num_kv_heads
        self.head_dim = hidden_size // num_heads

        self.q_proj = nn.Linear(hidden_size, num_heads * self.head_dim, bias=False)
        self.k_proj = nn.Linear(hidden_size, num_kv_heads * self.head_dim, bias=False)
        self.v_proj = nn.Linear(hidden_size, num_kv_heads * self.head_dim, bias=False)
        self.o_proj = nn.Linear(num_heads * self.head_dim, hidden_size, bias=False)

    def forward(self, x: torch.Tensor, freqs: torch.Tensor) -> torch.Tensor:
        B, T, D = x.shape
        q = self.q_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.num_kv_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.num_kv_heads, self.head_dim).transpose(1, 2)

        q, k = apply_rope(q, freqs), apply_rope(k, freqs)

        # GQA: expand KV heads
        if self.num_kv_heads < self.num_heads:
            n_rep = self.num_heads // self.num_kv_heads
            k = k[:, :, None].expand(-1, -1, n_rep, -1, -1).reshape(B, self.num_heads, T, self.head_dim)
            v = v[:, :, None].expand(-1, -1, n_rep, -1, -1).reshape(B, self.num_heads, T, self.head_dim)

        attn = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        attn = attn.transpose(1, 2).reshape(B, T, -1)
        return self.o_proj(attn)


class MLP(nn.Module):
    def __init__(self, hidden_size: int, intermediate_size: int):
        super().__init__()
        self.gate_proj = nn.Linear(hidden_size, intermediate_size, bias=False)
        self.up_proj = nn.Linear(hidden_size, intermediate_size, bias=False)
        self.down_proj = nn.Linear(intermediate_size, hidden_size, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.down_proj(F.gelu(self.gate_proj(x)) * self.up_proj(x))


class TransformerLayer(nn.Module):
    def __init__(self, hidden_size: int, intermediate_size: int, num_heads: int, num_kv_heads: int):
        super().__init__()
        self.input_layernorm = RMSNorm(hidden_size)
        self.post_attention_layernorm = RMSNorm(hidden_size)
        self.self_attn = Attention(hidden_size, num_heads, num_kv_heads)
        self.mlp = MLP(hidden_size, intermediate_size)

    def forward(self, x: torch.Tensor, freqs: torch.Tensor) -> torch.Tensor:
        x = x + self.self_attn(self.input_layernorm(x), freqs)
        x = x + self.mlp(self.post_attention_layernorm(x))
        return x


class Gemma4TextModel(nn.Module):
    """Random-weight model matching Gemma4 E4B-it text architecture."""

    def __init__(
        self,
        vocab_size: int = 262144,
        hidden_size: int = 2560,
        intermediate_size: int = 10240,
        num_layers: int = 42,
        num_heads: int = 8,
        num_kv_heads: int = 2,
        max_seq_len: int = 131072,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.max_seq_len = max_seq_len
        self.vocab_size = vocab_size

        # Create on meta device to avoid CPU OOM, then materialize on GPU
        with torch.device("meta"):
            self.embed_tokens = nn.Embedding(vocab_size, hidden_size)
            self.layers = nn.ModuleList([
                TransformerLayer(hidden_size, intermediate_size, num_heads, num_kv_heads)
                for _ in range(num_layers)
            ])
            self.norm = RMSNorm(hidden_size)

        # Precompute RoPE frequencies (small, create normally)
        head_dim = hidden_size // num_heads
        rope_freqs = precompute_rope_frequencies(head_dim, max_seq_len)
        self.register_buffer("rope_freqs", rope_freqs)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        x = self.embed_tokens(input_ids)
        for layer in self.layers:
            x = layer(x, self.rope_freqs)
        x = self.norm(x)
        return F.linear(x, self.embed_tokens.weight)

    @torch.no_grad()
    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 64,
        temperature: float = 0.0,
    ) -> torch.Tensor:
        self.eval()
        for _ in range(max_new_tokens):
            logits = self.forward(input_ids[:, -self.max_seq_len:])
            next_logit = logits[:, -1, :]
            if temperature > 0:
                probs = F.softmax(next_logit / temperature, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
            else:
                next_token = next_logit.argmax(dim=-1, keepdim=True)
            input_ids = torch.cat([input_ids, next_token], dim=-1)
        return input_ids


class Gemma4BenchModel:
    """Benchmark wrapper for Gemma4 text model."""

    def __init__(
        self,
        model_path: str = "/models/speculator",
        tokenizer_path: str = "/models/sentinel",
    ):
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.model: Optional[Gemma4TextModel] = None
        self.tokenizer = None
        self.device = None

    def load(self):
        import torch

        logger.info("Building Gemma4 text benchmark model (random weights)...")
        self.model = Gemma4TextModel()
        self.model.to_empty(device="cuda")
        for param in self.model.parameters():
            param.data.uniform_(-0.02, 0.02)
        self.model = self.model.to(dtype=torch.bfloat16)
        self.model.eval()
        self.device = torch.device("cuda")

        from transformers import AutoTokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_path, use_fast=True)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = 0

        n_params = sum(p.numel() for p in self.model.parameters())
        logger.info(
            f"Gemma4BenchModel loaded on {self.device} — "
            f"{n_params/1e9:.2f}B params, {self.model.hidden_size} hidden, "
            f"{len(self.model.layers)} layers"
        )

    async def generate(self, prompt: str, max_tokens: int = 64, temperature: float = 0.0) -> str:
        inputs = self.tokenizer(prompt, return_tensors="pt")
        input_ids = inputs["input_ids"].to(self.device)
        output_ids = self.model.generate(input_ids, max_new_tokens=max_tokens, temperature=temperature)
        return self.tokenizer.decode(output_ids[0], skip_special_tokens=True)

    async def forward_pass(self, input_ids: torch.Tensor) -> torch.Tensor:
        with torch.inference_mode():
            return self.model(input_ids)

    def get_device(self):
        return self.device
