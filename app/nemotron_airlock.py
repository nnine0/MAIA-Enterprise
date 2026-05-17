"""
MAIA PVI Airlock with Nemotron Sheriff
=================================
Independent auditor using NVIDIA Nemotron-3-Content-Safety.

Architectural Independence:
- Actor: Gemma-4-E4B (reasoning-tuned)
- Auditor: Nemotron-3-4B (safety-tuned, different generation)
- Satisfies SR 26-02 "Independent Validation"

Categories Mapping:
- Tier 1 (Critical): Fraud/Deception, Illegal Activity
- Tier 2 (Elevated): PII/Privacy, Unauthorized Advice  
- Tier 3 (Benign): Profanity, Copyright

Run: python3 -m app.nemotron_airlock
"""
