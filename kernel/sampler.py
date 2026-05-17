"""
MAIA Deterministic Sampler
==========================
Logit-level governance for SR 26-02 compliance.

This is the "Deep Tech" proof - moves safety from soft (prompt-level)
to hard (logit-level) enforcement.

The LogitsProcessor physically masks token IDs based on compliance config,
ensuring the model physically CANNOT generate prohibited tokens.
"""
