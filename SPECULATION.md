# MAIA Speculation Technical Specification

## Overview

This document covers speculative decoding integration (DFlash/Saguaro) with the Circuit Breaker model for SR 26-02 compliance.

---

## Circuit Breaker Model (v3.0) - Layer Mapping

```
Layer 9: AGENTIC → DFlash/Saguaro generates intent payloads
Layer 8: GOVERNANCE → Circuit Breaker validates + signs
Layer 7: APPLICATION → Executes only SIGNED trajectories
```

---

## DFlash Integration

**Paper**: [arXiv:2602.06036](https://arxiv.org/abs/2602.06036)  
**GitHub**: [z-lab/dflash](https://github.com/z-lab/dflash)  
**Model**: `z-lab/Qwen3.5-27B-DFlash`

### Block Diffusion Process

1. **Prompt Encoding**: Input prompt encoded to token IDs
2. **Block Generation**: Generate `block_size` tokens (default: 8) per block
3. **Parallel Diffusion**: All blocks generated in parallel
4. **Verification**: Each block verified against base model

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `dflash_model` | z-lab/Qwen3.5-27B-DFlash | Model name |
| `dflash_block_size` | 8 | Tokens per block |
| `dflash_max_draft_tokens` | 32 | Max draft tokens |

---

## Saguaro/SSD Integration

**Paper**: [arXiv:2603.03251](https://arxiv.org/abs/2603.03251)  
**Architecture**: Async Speculative Sampling with Decoding

### SSD Process

1. **Hypothesis Generation**: Generate N hypotheses (default: 3)
2. **Parallel Drafting**: All hypotheses generated in parallel
3. **Verification**: Each hypothesis scored against base model
4. **Selection**: Best hypothesis selected for execution

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `saguaro_hypothesis_count` | 3 | Number of hypotheses |
| `saguaro_max_draft_tokens` | 48 | Max tokens per hypothesis |
| `saguaro_temperature` | 0.7 | Sampling temperature |

---

## SR 26-02 Compliance Strategy

| Tier | Strategy | Audit |
|------|----------|-------|
| **Tier 1** | DFlash + Sequential | Full Circuit Breaker validation |
| **Tier 2** | Saguaro + Fast | Quick validation |
| **Tier 3** | Direct execution | Bypass |

### Tier 1 (Critical) - DFlash + Sequential Audit

```
1. Layer 9: DFlash generates block diffusion draft
2. Layer 9: Verify each block against base model
3. Layer 8: Circuit Breaker validates
4. Layer 8: Signs if compliant
5. Layer 7: Execute signed trajectory
6. Tier 1: Always escalate to DHITL SME Review
```

### Tier 2 (Elevated) - Saguaro + Fast Validation

```
1. Layer 9: Saguaro generates multiple hypotheses
2. Layer 9: Select best hypothesis
3. Layer 8: Circuit Breaker validates
4. Layer 7: Execute
```

### Tier 3 (Benign) - Bypass

```
1. Direct execution (no speculation)
2. Logging only
```

---

## VRAM Requirements

| Mode | VRAM Required | GPU |
|------|---------------|-----|
| Base model | 52GB | A100/H100 |
| DFlash | +2GB overhead | A100/H100 |
| Saguaro | +4GB overhead | A100/H100 |

---

## API Endpoints

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

### Unified Kernel

```python
from app.speculation import get_speculation_kernel

kernel = get_speculation_kernel(lorax_url)
result = await kernel.execute_with_speculation(prompt, tier=1)
```

### Metrics

```python
from app.speculation import metrics_collector

metrics = metrics_collector.get_metrics()
```

---

## Configuration Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
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

## Zero-Trust Flow Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                  USER REQUEST                             │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│              MATERIALITY ROUTER                            │
│              Tier 1/2/3 classification                      │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│           LAYER 9: AGENTIC (DFlash/Saguaro)               │
│  ┌──────────────────┐   ┌──────────────────┐             │
│  │ DFlash blocks   │   │ Saguaro hypos    │             │
│  │ (Tier 1)        │   │ (Tier 2)        │             │
│  └──────────────────┘   └──────────────────┘             │
└────────────────────────────────────────────────────────────────────┘
                              │
                    ════════════════════
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│           LAYER 8: GOVERNANCE (Circuit Breaker)            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ • Intercept intent payload                           │ │
│  │ • Validate against SR 26-02                       │ │
│  │ • Sign validated trajectories                       │ │
│  │ • Block non-compliant                             │ │
│  │ • DHITL escalation for Tier 1                     │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────���──────────────────────────────┘
                              │
                    ════════════════════
                    SIGNED TRAJECTORIES ONLY
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│           LAYER 7: APPLICATION (Execution)                 │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ • Executes ONLY signed trajectories                 │ │
│  │ • Never trusts Layer 9 directly                 │ │
│  │ • Requires Layer 8 signature                   │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                    RESPONSE                               │
└────────────────────────────────────────────────────────────────────┘
```

---

## References

- [DFlash Paper](https://arxiv.org/abs/2602.06036)
- [Saguaro/SSD Paper](https://arxiv.org/abs/2603.03251)
- [DFlash GitHub](https://github.com/z-lab/dflash)
- [SR 26-02 Compliance](/SR26-02_COMPLIANCE.md)