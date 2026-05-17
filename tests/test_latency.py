"""
MAIA End-to-End Latency Test
============================
Measures full inference pipeline latency across all four model components.

Usage:
    # Mock mode (tests code paths, no GPU needed):
    python3 -m tests.test_latency --mock

    # Real mode (requires downloaded models + GPU):
    python3 -m tests.test_latency
    HF_TOKEN=hf_xxx python3 -m tests.test_latency

Output:
    Layer 9  Gemma-4-E4B-it        xxx ms  │  xx tok/s
    Layer 9  E4B-it-assistant       xx ms  │  speculative
    Layer 8a Privacy Filter         xx ms  │  PII scan
    Layer 8b Nemotron Sheriff       xx ms  │  safety audit
    Layer 8c Granite Sentinel       xx ms  │  RAG check
           ───────────────────────────────────────────
           Total                    xxx ms
"""
