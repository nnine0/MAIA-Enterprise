# MAIA: The Governance Layer for Business Intelligence

> "If TCP/IP is the stack, AI is the 8th layer, MAIA is the 9th—the Governance layer."

MAIA (Multi-Adapter Inference Architecture) is an enterprise AI Governance Operating System. It solves the existential conflict between rapid AI innovation and strict regulatory constraints—transforming compliance from a bottleneck into a competitive advantage.

## The Layer Thesis

| Layer | Component |
|-------|-----------|
| 9 | **MAIA** - Governance Layer |
| 8 | AI - The new application layer |
| 7 | TCP/IP Application Layer (historical user domain) |

## SR 26-02 Compliance

MAIA natively satisfies the Federal Reserve's SR 26-02 mandates:

- **Effective Challenge**: PVI Airlock with dual-adapter validation
- **Materiality Matrix**: Domain-specific expert adapters with Tier 1/2/3 routing
- **Continuous Monitoring**: STaR self-evolution loop + Latent EKG
- **Conceptual Soundness**: Forensic proof of reasoning path via latent hashes

## Architecture

MAIA implements a layered governance architecture:

### Layer 1: Supervisor Router (Hub/Spoke)
- **Executive LoRA**: Industry identification (Finance, Logistics, Legal)
- **Manager LoRA**: Sub-domain identification (Commercial Credit, Fraud/AML)
- **Dispatch Token**: `[EXECUTE: {expert}, AUDIT: {auditor}, TIER: {materiality}]`

### Layer 2: Memory Manager (Neural OS Stack)
| Tier | Location | Contents | Latency |
|------|----------|----------|---------|
| VRAM (Live) | GPU | Base LLM + PVI Airlock | 0ms |
| RAM (Warm) | CPU | Top 100 active adapters | <20ms |
| NVMe (Cold) | Disk | Thousands of specialized adapters | On-demand |

### Layer 3: LoRAX Kernel (SGMV Batching)
- **Base Model**: Gemma 4 26B A4B MoE (reference)
- **Multi-Adapter**: Hot-swappable expert adapters
- **VRAM Efficiency**: 70% reduction vs. monolithic models

### Layer 4: PVI Airlock (Effective Challenge)
Non-Blocking Interceptor pattern:
1. **Actor** → Expert adapter generates action trajectory
2. **Interceptor Pause** → 150ms pause before execution
3. **Auditor** → SR 26-02 adapter validates trajectory
4. **Circuit Breaker** → Blocks non-compliant trajectories

### Layer 5: Latent Telemetry (Neural EKG)
- **Activation Hooks**: Tap Residual Stream at each layer
- **Decision Nodes**: Latent hashing at critical points
- **Audit Log**: Fed-auditable trajectory proof

### Layer 6: DAG Orchestrator (Async Workflow)
- **Parallel Streams**: Identity + Financials run concurrently
- **Convergence Points**: Wait for dependencies
- **Speculative Execution**: Draft while waiting
- **GPU Never Blocked**: Yield and park workflows

## Module Reference

| Module | Location | Purpose |
|--------|----------|---------|
| Airlock | `app/airlock.py` | PVI Non-Blocking Interceptor |
| Supervisor | `app/supervisor_router.py` | Hub/Spoke hierarchical routing |
| Memory | `app/memory_manager.py` | VRAM/RAM/NVMe hot-swapping |
| Telemetry | `app/latent_telemetry.py` | Neural EKG + latent hashing |
| Orchestrator | `app/dag_orchestrator.py` | Async DAG workflow |
| Controller | `app/main.py` | FastAPI integration |

## Materiality Matrix

| Tier | Triggers | Airlock | Latency |
|------|----------|---------|---------|
| 1 - Critical | credit, wire, transfer, loan, sanction | Full audit | ~420ms |
| 2 - Elevated | risk, limit, approval, policy | Conditional | ~200ms |
| 3 - Benign | general queries | Bypass | ~50ms |

## API Usage

### Governance Query (with PVI Airlock)
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -H "x-maia-key: your-api-key" \
  -d '{"query": "Increase credit limit for client 992 by 20%"}'
```

### Batch Query (parallel execution)
```bash
curl -X POST "http://localhost:8000/query_batch" \
  -H "Content-Type: application/json" \
  -H "x-maia-key: your-api-key" \
  -d '{"queries": ["query1", "query2"]}'
```

### Workflow (DAG orchestration)
```bash
curl -X POST "http://localhost:8000/workflow" \
  -H "Content-Type: application/json" \
  -H "x-maia-key: your-api-key" \
  -d '{"workflow_type": "credit", "initial_data": {...}}'
```

### Telemetry (Audit Log)
```bash
curl -X GET "http://localhost:8000/telemetry/{session_id}" \
  -H "x-maia-key: your-api-key"
```

### Memory Status
```bash
curl -X GET "http://localhost:8000/memory" \
  -H "x-maia-key: your-api-key"
```

## Prerequisites

- Docker and Docker Compose
- NVIDIA GPU (24GB VRAM recommended)
- LoRAX inference server

## Quick Start

```bash
# Clone and configure
git clone https://github.com/nnine0/MAIA-Enterprise.git
cd MAIA-Enterprise

# Start services
docker compose up --build

# API available at http://localhost:8000
```

## Security

- API key authentication
- Prompt injection detection via LLM-Guard
- Latent telemetry for forensic audit trails
- PVI Airlock circuit breaker

## The VRAM/Compliance Paradox Solved

MAIA resolves the fundamental enterprise tension:
- **Deploy AI** = risk regulatory violation
- **Restrict AI** = lose competitive advantage

Through:
1. Memory hierarchy (VRAM reserved for Airlock)
2. SGMV batching (multiple adapters per GPU pass)
3. Materiality-based routing (only high-risk triggers audit)

## Links

- **Technical Standard**: See `STANDARD.md` for complete architecture
- **Implementation**: https://github.com/nnine0/MAIA-Enterprise