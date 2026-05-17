"""
MAIA Policy SDK
===============
Client SDK for managing policies programmatically.
Allows clients to add, remove, and compose policies.

Usage:
    from policies.sdk import PolicySDK
    
    sdk = PolicySDK()
    sdk.add_sector_policy(...)
    sdk.add_occupation_policy(...)
    config = sdk.compose("finance", "trader")
"""
