# MAIA Speculation Technical Specification

## Overview

This document covers the **Unified Speculative Stack** - integrating Google's Multi-Token Prediction (MTP) with DFlash block diffusion and Saguaro (SSD) asynchronous scheduling for the Circuit Breaker governance model.

**The Hyper-Factory**: Layer 9 (Agentic) → Layer 8 (Governance) → Layer 7 (Application)

---

## The Unified Speculative Stack

```
┌──────────────────────────────────────────────────────────────────────┐
│                    UNIFIED STACK                          │
├──────────────────────────────────────────────────────────────┤
│  Layer 9: AGENTIC ENGINE                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  MTP Heads (Gemma 4 Native)    →  Shared KV Cache       │ │
│  │  └─ Internal lookahead (4 tokens)                       │ │
│  │  DFlash Block Expansion       →  Parallel Diffusion    │ │
│  │  └─ Seeds → 16-token blocks                           │ │
│  └────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│  Layer 8: GOVERNANCE/AIRLOCK                                │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  SSD (Saguaro) Scheduler       →  Async Audit          │ │
│  │  └─ Pre-audit while GPU verifies                      │ │
│  │  PVI Airlock                  →  Validation + Sign   │ │
│  └────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│  Layer 7: APPLICATION (Execution)                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Executes SIGNED trajectories only                     │ │
│  │  Zero-Trust: Never trusts Layer 9 directly           │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Multi-Token Prediction (MTP)

**Release**: Google, May 2026  
**Documentation**: [Gemma 4 MTP Drafter](https://ai.google.dev/p/gemma/mtp)  
**Models**: `google/gemma-4-26b-a4b-it` (with MTP heads)

### How MTP Works

1. **Internal Lookahead**: Gemma 4's MTP heads predict next 4 tokens using shared KV cache
2. **Near-Zero VRAM**: Draft uses target model's activations - no separate model loading
3. **Parallel Verification**: Target model verifies all 4 tokens in single forward pass

### MTP + MAIA Integration

```python
# MTP is native to Gemma 4 - no additional config needed
BASE_MODEL_ID = "google/gemma-4-26b-a4b-it"  # Includes MTP drafter

# LoRAX handles MTP automatically via --enable-mtp flag
command: --model-id google/gemma-4-26b-a4b-it --enable-mtp
```

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MTP_ENABLED` | true | Enable MTP (native to Gemma 4) |
| `mtp_draft_tokens` | 4 | Tokens predicted by MTP heads |

---

## DFlash Integration (Block Diffusion)

**Paper**: [arXiv:2602.06036](https://arxiv.org/abs/2602.06036)  
**GitHub**: [z-lab/dflash](https://github.com/z-lab/dflash)  
**Model**: `z-lab/Qwen3.5-27B-DFlash`

### Block Diffusion Process

1. **Seed Tokens**: MTP provides 4 seed tokens
2. **Block Expansion**: DFlash expands seeds → 16-token block via parallel diffusion
3. **Verification**: Each block verified against base model
4. **Governance**: Blocked passed to Layer 8 for audit

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DFLASH_ENABLED` | true | Enable DFlash |
| `DFLASH_MODEL` | z-lab/Qwen3.5-27B-DFlash | Model name |
| `DFLASH_BLOCK_SIZE` | 8 | Tokens per block |
| `DFLASH_MAX_DRAFT` | 32 | Max draft tokens |

---

## Saguaro/SSD Integration (Async Scheduling)

**Paper**: [arXiv:2603.03251](https://arxiv.org/abs/2603.03251)  
**Architecture**: Asynchronous Speculative Sampling with Decoding

### SSD Process

1. **Background Audit**: While GPU verifies current block, SSD predicts next outcome
2. **Pre-Audit**: PVI Airlock pre-validates next trajectory in speculative cycles
3. **Latency Erasure**: Audit happens "while you wait" - effectively negative latency

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SAGUARO_ENABLED` | false | Enable Saguaro |
| `SAGUARO_HYPOTHESES` | 3 | Number of hypotheses |
| `SAGUARO_MAX_DRAFT` | 48 | Max tokens per hypothesis |
| `SAGUARO_TEMP` | 0.7 | Sampling temperature |

---

## Performance Comparison

| Feature | Standard (2023) | SSD (Mar '26) | DFlash (Feb '26) | **MAIA Unified** |
|---------|-----------------|---------------|-----------------|------------------|
| Drafting Method | Sequential (1-by-1) | Sequential (overlapped) | Parallel (Block Diffusion) | **Parallel (MTP Seeds + DFlash Blocks)** |
| Verification | Synchronous (Wait) | Asynchronous (Concurrent) | Synchronous (Wait) | **Asynchronous (Multi-Outcome)** |
| VRAM Overhead | High (2nd model) | High | Moderate (Adapter) | **Near-Zero (Shared MTP KV)** |
| Governance | Post-generation | Text check on outcomes | Trajectory validation | **Speculative Latent Audit** |
| End-to-End Speed | 2x - 3x | 4x - 5x | 6x | **8x - 10x (est.)** |

---

## SR 26-02 Compliance Strategy

| Tier | Strategy | Audit |
|------|----------|-------|
| **Tier 1** | MTP + DFlash + Sequential | Full Circuit Breaker + DHITL |
| **Tier 2** | MTP + Saguaro + Fast | Quick validation |
| **Tier 3** | MTP direct | Bypass |

### Tier 1 (Critical) - Full Pipeline

```
1. Layer 9: MTP heads predict 4 seed tokens (near-zero latency)
2. Layer 9: DFlash expands seeds → 16-token block (parallel)
3. Layer 9: Verify each block against Gemma 4
4. Layer 8: SSD pre-audits next trajectory (async)
5. Layer 8: Circuit Breaker validates + signs
6. Layer 7: Execute signed trajectory
7. Tier 1: DHITL SME Review
```

### Tier 2 (Elevated) - Fast Path

```
1. Layer 9: MTP provides seed tokens
2. Layer 9: Saguaro generates hypotheses (async)
3. Layer 8: SSD pre-validates
4. Layer 8: Circuit Breaker signs
5. Layer 7: Execute
```

### Tier 3 (Benign) - Bypass

```
1. MTP directly generates (no speculation overhead)
2. Logging only
```

---

## VRAM Requirements (The "Free Lunch")

| Mode | VRAM Required | Notes |
|------|---------------|-------|
| **FIXED VRAM RENT** | **17.8 GB** | Base + Airlock + KV Cache |
| Gemma 4 26B Base (4-bit) | 14.5 GB | Quantized |
| PVI Airlock (E2B) | 1.8 GB | Governance |
| Kernel/Shared KV | 1.5 GB | MTP shared |
| MTP Drafter | +0.1 GB | Near-zero (shared KV) |
| DFlash Adapter | +2.0 GB | Optional |
| Saguaro Hypotheses | +4.0 GB | Optional |
| **Full Stack Max** | **~24 GB** | Fits on RTX 3090 |

### The Airlock Speculative Loop

The core governance innovation: **Proposer is Adapter-Agnostic, Verifier is Adapter-Strict**.

```
┌─────────────────────────────────────────────────────────────────────┐
│                  AIRLOCK SPECULATIVE LOOP                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Request: "Adjust project margin for the Navy bid."                     │
│                                                                     │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │  LAYER 9: MTP PROPOSER (Adapter-Agnostic)                  │   │
│   │  - Uses base model ONLY (no adapter weights loaded)           │   │
│   │  - Proposes: [SET] [MARGIN] [TO] [2%]                  │   │
│   │  - Near-zero VRAM (shared KV cache)                     │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                             ↓                                  │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │  LAYER 8: MTP VERIFIER (Adapter-Strict)                  │   │
│   │  - Validates against MATERIALITY MATRIX                  │   │
│   │  - Checks [2%] against loaded adapter weights           │   │
│   │  - Checks Navy sector policy constraints                │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                             ↓                                  │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │  POLICY HIT: "Minimum margin for Navy bids is 5%"            │   │
│   │  - Proposer suggested 2% (outside LoRA weight space)         │   │
│   │  - Verifier detects NON-PHYSICAL TRAJECTORY          │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                             ↓                                  │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │  OUTCOME OPTIONS:                                      │   │
│   │  A) AUTO-CORRECT: Rewrite [2%] → [5%] (if within policy) │   │
│   │  B) DHITL ESCALATION: Trigger human review            │   │
│   │  C) BLOCK: Reject entire draft                       │   │
│   └───────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Proposer vs Verifier: Key Differences

| Aspect | Proposer (Layer 9) | Verifier (Layer 8) |
|--------|-------------------|-------------------|
| **Adapter** | Adapter-Agnostic | Adapter-Strict |
| **Model** | Base model only | Loaded LoRA adapter |
| **VRAM** | ~0MB (shared KV) | Uses adapter weights |
| **Speed** | Fast (<10ms) | Depends on adapter |
| **Purpose** | Draft tokens | Validate against policy |

### Non-Physical Trajectories

The Verifier detects when proposals fall outside the loaded adapter's weight space:

1. **Value Violation**: Proposer suggests 2%, policy minimum is 5%
2. **Sector Violation**: Proposer uses general language, but Navy adapter expects formal bidding terminology
3. **Compliance Violation**: Proposer ignores regulatory constraints built into adapter

### Hardware Substrate Specs

| GPU | VRAM | Bandwidth | FP32 TFLOPS | Can Run MAIA? |
|-----|-----|----------|------------|--------------|
| RTX 3090 | 24 GB | 936 GB/s | 35.6 | ✅ Full stack |
| H100 SXM5 | 80 GB | 3,350 GB/s | 67 / 2000* | ✅ Oversized |

---

## Configuration Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_MODEL_ID` | google/gemma-4-26b-a4b-it | Base model (includes MTP) |
| `DFLASH_ENABLED` | true | Enable DFlash |
| `DFLASH_MODEL` | z-lab/Qwen3.5-27B-DFlash | DFlash model |
| `DFLASH_MAX_DRAFT` | 32 | Max draft tokens |
| `DFLASH_BLOCK_SIZE` | 8 | Block size |
| `SAGUARO_ENABLED` | false | Enable Saguaro |
| `SAGUARO_HYPOTHESES` | 3 | Hypothesis count |
| `SAGUARO_MAX_DRAFT` | 48 | Max draft tokens |
| `SAGUARO_TEMP` | 0.7 | Temperature |
| `ENFORCE_CB` | true | Enforce Circuit Breaker |
| `SEQUENTIAL_AUDIT` | true | Sequential audit for Tier 1 |

---

## API Endpoints

### Unified Kernel

```python
from app.speculation import get_speculation_kernel

kernel = get_speculation_kernel(lorax_url)
result = await kernel.execute_with_speculation(prompt, tier=1)
```

### DFlash Draft Generation

```python
from app.speculation import dflash_engine

draft = await dflash_engine.generate_draft(prompt)
verification = await dflash_engine.verify_draft(draft)
```

### Saguaro SSD

```python
from app.speculation import saguaro_scheduler

result = await saguaro_scheduler.speculative_decode(prompt)
```

### Metrics

```python
from app.speculation import metrics_collector

metrics = metrics_collector.get_metrics()
```

---

## The "Trillion-Dollar" Value Proposition

### A. Latency Erasure (Layer 8)

> "We have achieved 'Hidden Compliance.' The bank no longer pays a time-tax for safety because the audit happens in the speculative cycles provided by MTP and SSD."

### B. Shared KV Cache: Hardware "Free Lunch"

> "The Airlock and Actor share the same short-term memory via MTP's shared KV cache. This solves the VRAM/Compliance Paradox permanently."

### C. Enterprise Ready

> "A single RTX 3090 (24GB) can run full SR 26-02 governance because MTP collapses the drafting memory footprint."

---

## References

- [Gemma 4 MTP Drafter](https://ai.google.dev/p/gemma/mtp)
- [Gemma 4 MTP Technical Explainers](https://arxiv.org)
- [DFlash Paper](https://arxiv.org/abs/2602.06036)
- [Saguaro/SSD Paper](https://arxiv.org/abs/2603.03251)
- [DFlash GitHub](https://github.com/z-lab/dflash)
- [SR 26-02 Compliance](/SR26-02_COMPLIANCE.md)