"""
PVI Airlock Service - Re-exports from canonical app modules
=================================================
Deprecated: Import from app.airlock instead.

This module exists for backward compatibility.
"""

# Re-export from canonical source
from app.airlock import (
    PVIAirlock,
    SMEPool,
    RLHFTrainingData,
    AirlockVerdict,
    MaterialityTier,
)
from app.airlock import execute_vetted_transaction, batch_vetted_transactions

__all__ = [
    "PVIAirlock",
    "SMEPool",
    "RLHFTrainingData",
    "AirlockVerdict",
    "MaterialityTier",
    "execute_vetted_transaction",
    "batch_vetted_transactions",
]