"""
MAIA Forensic Sidecar
====================
Asynchronous forensic hashing without inference latency.

Architecture:
1. Latent Tap (Non-Blocking IO) - streams tensors via CUDA stream
2. Merkle-Latent Tree - dimensional reduction + merkle tree
3. Audit Worker (Sidecar) - async signing in background

The Flow:
  Inference → [Stream tensors] → [Queue] → [Sign] → [Receipt]
                      (async)              (background)

Run: python3 -m app.forensic_sidecar
"""
