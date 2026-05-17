"""
MAIA Memory Manager - VRAM/RAM/NVMe Hierarchy
Implements the "Neural OS" memory stack for sub-second adapter hot-swap.

Memory Hierarchy:
- VRAM (Live): Base LLM + PVI Airlock pinned - never moves
- CPU RAM (Warm): Top ~100 active adapters ready - <20ms push to GPU  
- NVMe/Disk (Cold): Thousands of specialized adapters

The Kernel (LoRAX) receives N requests, pulls needed adapters from RAM,
batches into SGMV pass, executes.
"""
