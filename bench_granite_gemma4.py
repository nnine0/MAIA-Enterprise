"""
Benchmark: Granite Sentinel + Gemma4 Base Model
================================================
Measures per-component latency with:
  - Granite Sentinel (real, /models/sentinel) — fast_pass / full generation
  - Gemma4 E4B-it (random-weight benchmark) — forward pass / generation per-token
  - No Nemotron Sheriff (mocked)
"""
