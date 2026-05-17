"""
MAIA GPU Configuration for Unified Speculative Stack
======================================================
VRAM estimation and validation for MTP/DFlash/Saguaro.

Layer: GPU Kernel (Hardware Abstraction)

HARDWARE SUBSTRATE SPECS:
----------------------
| GPU              | VRAM   | Bandwidth    | FP32 TFLOPS |
|-----------------|--------|-------------|------------|
| RTX 3090         | 24GB  | 936 GB/s    | 35.6       |
| H100 (SXM5)      | 80GB  | 3,350 GB/s  | 67 / 2000* |
                  |       |             | (* FP8)     |

MAIA NEURAL OS OVERHEAD (Gemma 4 26B A4B MoE):
---------------------------------------
| Component                | VRAM   | Notes                    |
|------------------------|--------|--------------------------|
| Base Model (4-bit)        | 14.5 GB| Quantized                |
| PVI Airlock (E2B 4-bit)| 1.8 GB| Governance              |
| Kernel/Shared KV Cache  | 1.5 GB| MTP shared               |
| FIXED VRAM RENT         | 17.8 GB| No additional overhead   |

MTP KEY: Uses shared KV cache with base model - near-zero VRAM overhead.
"""
