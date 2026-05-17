"""
MAIA Cross-Bank Contagion Detector (Layer 8 Shared)
====================================================
Monitors latent-space trajectory intersections between banks.
If Bank A's AI agent is doing something that will cause a liquidity
crisis at Bank B, Circuit Breaker trips for BOTH banks.

Why this matters:
  - Standard governance checks ONE bank at a time
  - Cross-bank contagion requires checking TRAJECTORY INTERSECTIONS
  - A liquidity event at Bank A can cascade through the entire financial system
  - MAIA sees this in the latent space before it hits the ledger

Federal Reserve "Single Pane of Glass":
  - One dashboard showing systemic stability across all 16 banks
  - Real-time contagion risk scores
  - Circuit breaker triggers logged to Fed audit trail
"""
