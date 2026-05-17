"""
MAIA Parallel Airlock Gateway
==============================
Implements the governance gateway pattern with parallel dispatch:

  Ingress:  Prompt → { Base Model (cloud API), Sheriff (Nemotron), Sentinel (Granite) } in parallel
  Circuit:  Sheriff/Sentinel pre-flight → kill cloud call if violated
  Egress:   Tool-call interception → policy check → deliver to data

Supports any upstream base model: OpenAI, Anthropic, OpenRouter, Ollama, etc.

Flow:
  User Prompt
      │
      ├──→ Sheriff (Nemotron-3)  ──→ Pre-flight safety audit
      ├──→ Sentinel (Granite-3B) ──→ Pre-flight policy/logic audit
      └──→ Base Model (cloud)    ──→ (cancellable task)
                                      │
                                 if VIOLATION → cancel cloud → 403
                                      │
                                 if CLEAR → stream → Egress Interceptor
                                                      │
                                                 tool call? → policy manifest → BLOCK/REWRITE
                                                      │
                                                 text → deliver to user
"""
