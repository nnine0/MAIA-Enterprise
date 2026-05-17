"""
MAIA Semantic Router - Layer 9 Client-Side Router
==============================================

This logic resides in your application edge.
It determines if a request is "Creative" (OpenAI) or "Material" (MAIA).

Materiality Matrix Logic:
- financial_bid, safety_log, legal_contract → Route to MAIA PVI Airlock
- creative, general, chat → Route to Public API (OpenAI)
"""
