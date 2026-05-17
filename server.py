"""
MAIA Enterprise Hybrid Server
=============================
Refactored server using SGLang + LoRAX hybrid kernel with Airlock Gateway.

Key changes from original:
1. Uses HybridInferenceKernel instead of standalone components
2. Implements T0/T1/T2/T3 speculative verification pipeline
3. Exposes SVP metrics at /stats endpoint
4. Shared memory IPC for <1ms inter-process handoff
5. Parallel Airlock Gateway (Sheriff/Sentinel/Basemodel dispatch)

SR 26-02: Turn all stubs into functional API.
"""
