"""
MAIA Early-Exit Circuit Breaker
================================
Latent Space Circuit Breaker - checks speculative tokens BEFORE materialization.

The Problem: Traditional safety systems wait for AI to finish "typing" before checking.
The Solution: Early-Exit Speculation. If speculative decoder predicts high probability
of policy violation in next N tokens, kills generation BEFORE tokens are materialized.

Run: python3 -m app.early_exit_breaker
"""
