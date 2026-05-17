"""
Gemma 4 E4B-it Text Model
==========================
PyTorch module matching Gemma4 E4B-it text architecture for inference.

Architecture:
  - 42 transformer layers, hidden_size=2560, intermediate_size=10240
  - 8 attention heads, 2 KV heads (GQA), head_dim=320
  - SwiGLU MLP, RMSNorm, RoPE
  - bfloat16 on CUDA

Created on meta device then materialized to avoid host OOM.
Random weights for now — safetensors loading can be swapped in when
transformers >= 5.5.0 supports the gemma4 model type.
"""
