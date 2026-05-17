"""
MAIA Airlock Speculative Loop
=========================
Implements the Proposer/Verifier architecture for speculative decoding.

The Airlock Loop:
1. MTP Proposer (Adapter-Agnostic) drafts tokens using base model only
2. MTP Verifier (Adapter-Strict) validates against loaded adapter
3. Policy check detects non-physical trajectories
4. Auto-correct, DHITL escalation, or block
"""
