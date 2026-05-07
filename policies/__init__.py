"""
MAIA Policy System
==================

Stratified policy management for multiple sectors and occupations.

Structure:
- policies/sectors/     - Sector-specific policy sets (finance, healthcare, etc.)
- policies/occupations/ - Occupation-specific policies (trader, compliance officer, etc.)
- policies/templates/   - Policy templates for SDK
- policies/registry.py  - Policy registry manager
- policies/sdk.py       - Client SDK for policy management

Usage:
    from policies.registry import PolicyRegistry
    registry = PolicyRegistry()
    registry.load_all_policies()
    
    # Compose sector + occupation
    policy = registry.compose_policy("finance", "trader")
    
    # Or use the SDK
    from policies.sdk import PolicySDK
    sdk = PolicySDK()
    sdk.add_sector_policy(...)
"""

from .registry import PolicyRegistry, PolicySet, PolicyClause
from .sdk import PolicySDK, SectorPolicyInput, OccupationPolicyInput

__all__ = [
    "PolicyRegistry",
    "PolicySet", 
    "PolicyClause",
    "PolicySDK",
    "SectorPolicyInput",
    "OccupationPolicyInput",
]