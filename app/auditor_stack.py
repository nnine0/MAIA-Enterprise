"""
MAIA Auditor Stack — Layer 8 Multi-Model Governance
====================================================
Three independent auditor models running as a coordinated verification layer:

  Layer 8a — Privacy Filter:    openai/privacy-filter (token classification)
  Layer 8b — Safety Sheriff:    nvidia/Nemotron-3-Content-Safety (via nemotron_real.py)
  Layer 8c — Logic Sentinel:    ibm-granite/granite-guardian-3.1-2b (RAG verification)

Each auditor runs as an independent FastAPI service behind the governance layer.
"""
