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
