"""
MAIA End-to-End Latency Test v4
================================
Measures MAIA governance overhead, NOT base model speed.

Architecture:
┌─────────────────────────────────────────────────────┐
│  BASE MODEL (Gemma) generates response              │
│  ↓ FAST (~50-100ms for short response)             │
└──────────────────┬────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  MAIA GOVERNANCE (parallel, non-blocking)          │
│  - Materiality classification                       │
│  - Violation check                                 │
│  - Forensic hash                                   │
│  - Adapter routing                                │
│  ↓ TYPICALLY <5ms overhead                        │
└─────────────────────────────────────────────────────┘

End-to-end = max(BaseModel, MAIA) = Base model speed
MAIA overhead = negligible (runs in parallel)
"""
