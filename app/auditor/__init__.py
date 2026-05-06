"""
MAIA Neuro-Symbolic Auditor Package
==================================
Alternative governance routing using neuro-symbolic approach.

This is an optional alternative to the main Circuit Breaker.
Use either auditor/ OR circuit_breaker, not both.

- Circuit Breaker (app/circuit_breaker.py): MTP/SSP-based governance
- Neuro-Symbolic (app/auditor/): Rule-based + neural fallback
"""

from app.auditor.symbolic import (
    NeuroSymbolicAuditor,
    SymbolicVerdict,
    EvaluationPath,
    SymbolicAuditResult,
    SymbolicProof
)

from app.auditor.router import (
    GovernanceRouter,
    GovernanceDecision,
    ResolutionPath
)

__all__ = [
    "NeuroSymbolicAuditor",
    "SymbolicVerdict", 
    "EvaluationPath",
    "SymbolicAuditResult",
    "SymbolicProof",
    "GovernanceRouter",
    "GovernanceDecision",
    "ResolutionPath"
]