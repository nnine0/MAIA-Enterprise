"""
MAIA Sovereign Adapter Loader
==============================
Resolves business sector IDs to local filesystem paths using the Neural Registry.

SR 26-02 Requirement: All model assets must be tracked in an immutable inventory.
This registry IS that inventory — a single source of truth for every adapter in production.

Usage:
    from core.adapter_loader import registry

    path = registry.get_agentic("finance")
    # Returns: "/data/adapters/finance_expert_v4"

    validator_path = registry.get_validator("finance")
    # Returns: "/data/adapters/pvi_airlock_sr2602"
"""
