"""
MAIA External Evaluation API
==========================
Zero-Knowledge Governance Gateway for external testing.
Multi-tenant API that proves the Circuit Breaker works without exposing model internals.

Layer  Components
L7:    FastAPI + Kong (Rate-limiting, API Key auth, JWT)
L8:    PVI Airlock (External Auditor - intercepts before brain)
L9:    LoRAX Orchestrator (Multi-adapter kernel)
Output: Trajectory Log (Satisfactory Audit JSON)

SR 26-02: External clients test governance without seeing the model.
"""
