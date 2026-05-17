"""
MAIA Agentic Gateway
=====================
Transparent proxy that handles governance invisible to the client.

Problem: Banks don't want to rewrite their AI code to use MAIA.
Solution: Send traffic to localhost:8080 (MAIA Gateway), MAIA handles
Airlock and Neural Permissioning transparently.

Flow:
  Bank AI → localhost:8080 (MAIA Gateway) → [Governance] → Upstream Model
                                              ↓
                                         [Audit Ledger]

Usage:
    python3 -m app.agentic_gateway
    
Or as a reverse proxy:
    python3 -m app.agentic_gateway --upstream https://api.openai.com/v1
"""
