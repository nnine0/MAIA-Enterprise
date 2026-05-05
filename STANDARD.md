# MAIA: Technical Standard

## Executive Summary

MAIA (Multi-Adapter Inference Architecture) is an enterprise standard for AI Governance. It reconciles the fundamental tension between rapid AI deployment and regulatory compliance—transforming compliance from a bottleneck into a competitive advantage.

---

## Architecture

### Zero-Trust Model

| Component | Role |
|----------|------|
| **Agentic** | Generates intent payloads |
| **Governance** | Validates and signs trajectories |
| **Application** | Executes only signed trajectories |

The model can think whatever it wants, but it can only act within very specific action trajectories that have been validated and signed by the Governance layer.

---

## Technical Standard

### 1. Memory Hierarchy

| Tier | Location | Contents | Latency |
|------|----------|----------|---------|
| VRAM (Live) | GPU | Base LLM + PVI Airlock | 0ms |
| RAM (Warm) | CPU | Top 100 active adapters | <20ms |
| NVMe (Cold) | SSD | All adapters | On-demand |

### 2. Multi-Adapter Orchestration

- **Supervisor LoRA**: Neural dispatch within latent space
- **Hub/Spoke**: Executive → Manager → Worker adapter hierarchy
- **DAG Orchestrator**: Parallel streams with convergence points

### 3. SR 26-02 Compliance

- **Effective Challenge**: Dual-adapter validation (Actor + Auditor)
- **Materiality Matrix**: Risk-tiered routing (Tier 1/2/3)
- **Continuous Monitoring**: Latent telemetry + audit logs
- **Conceptual Soundness**: Latent hash forensic trails

---

## Module Reference

| Module | Purpose |
|--------|---------|
| `app/circuit_breaker.py` | Governance layer - validation and signing |
| `app/supervisor_router.py` | Hub/Spoke routing |
| `app/memory_manager.py` | VRAM/RAM/NVMe hot-swapping |
| `app/latent_telemetry.py` | Neural EKG + latent hashing |
| `app/dashboard.py` | Governance Dashboard |

---

## SR 26-02 Compliance Mapping

| Requirement | MAIA Implementation |
|-------------|----------------|
| Effective Challenge | Dual-adapter validation |
| Materiality Matrix | Risk-tiered routing |
| Continuous Monitoring | Latent EKG |
| Conceptual Soundness | Latent hash trails |
| Human Oversight | DHITL SME voting |