# MAIA: Enterprise AI Governance OS

> The Industrial Neural Operating System for Regulated Industries
> 
> The Safety Kernel that allows any AI to be deployed in any regulated environment by simply swapping "Policy Manifests."

---

## About

MAIA (Multi-Adapter Inference Architecture) is an **enterprise AI Governance Operating System**—a neural microkernel running between the reasoning engine and the real world.

### The Problem

The Global 2000 faces an impossible choice:
- **Deploy AI** = Risk regulatory violation, audit failure, fines
- **Restrict AI** = Lose competitive advantage

### Our Vision

MAIA transforms AI from a **liability** into a **controlled industrial instrument**—the same way PLCs transformed factory floors from artisanal craft to reproducible manufacturing.

**The PLC Analogy**: Before 1968, changing a factory line required hiring an electrician to physically rewire relay panels (days of downtime). Then the PLC arrived—you could now change the entire production logic in software, in seconds. Factories went from artisanal craft to reproducible manufacturing.

MAIA does the same for AI: instead of "prompt engineering" (manually rewiring reasoning), you deploy constrained LoRA weight-sets that physically cannot reason outside their boundaries. Change the logic instantly, without breaking compliance.

### The Scope

MAIA is not a chatbot. It is a **complete governance infrastructure** that enterprises deploy to:

| Layer | Component | Purpose |
|-------|-----------|---------|
| **L9: Agentic** | Gemma 4 + MTP/DFlash | Intent generation with speculative decoding |
| **L8: Governance** | Circuit Breaker + DME Engine | 4-layer recursive escalation |
| **L7: Application** | Tool-Adapters | Constrained LoRA weight-sets |

### Key Capabilities

- **GDP-Aligned Materiality** - 9 sectors × 44 occupations mapping
- **Dynamic Materiality Escalation (DME)** - L1→L2→L3→L4 semantic analysis
- **Tool-Adapters (Neural Permissioning)** - 51 specialized business tools as constrained LoRAs
- **Unified Speculative Stack** - MTP + DFlash + SSD for zero-latency governance
- **DHITL Human Sovereignty** - 3 SME votes for Tier 1 decisions
- **AIBOM Inventory** - SR 26-02 required adapter registry
- **Neural Tool Dispatcher** - Kernel-level tool execution with governance
- **Quad-Node Deployment** - Multi-sector GPU isolation

### The Moat

> "Others give you an AI that can 'use a browser.' That is a liability. I give you a Neural microkernel where every 'hand' (tool) is a constrained mathematical subset of the brain."

MAIA replaces "Prompt Engineering" with **Neural Permissioning**—tools physically cannot reason outside their programmed boundaries.

### For Who

- **Banks** - SR 26-02 compliance for trading, lending, wire transfers
- **Pharma** - HIPAA/GCP for clinical trials, drug safety
- **Logistics** - Hazmat, real-time routing, maritime compliance
- **Legal/Real Estate** - Contract redlining, title verification
- **Construction** - OSHA safety, prevailing wage, structural integrity
- **Energy/Utilities** - NERC CIP critical infrastructure
- **Defense/Aerospace** - ITAR, classified handling

---

## Architecture

| Component | Role |
|------------|------|
| **Agentic** | Intent generation - drafts AI reasoning |
| **Governance** | Validates, signs, blocks trajectories |
| **Application** | Executes only signed trajectories |

**Zero-Trust**: Application never trusts Agentic directly. Only Governance has the signing key.

---

## Architecture

### The Neural Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    USER REQUEST                              │
└──────────────��──────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              SUPERVISOR ROUTER (Hub/Spoke)                   │
│   Executive LoRA → Industry → Manager LoRA → Sub-domain       │
│   Dispatch Token: [EXECUTE: {expert}, AUDIT: {auditor}]      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              MEMORY HIERARCHY (Neural OS Stack)              │
│   VRAM (Live): Base Model + Airlock      │ 0ms latency      │
│   RAM (Warm): Top 100 adapters           │ <20ms latency   │
│   NVMe (Cold): All adapters              │ On-demand       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              LORAX KERNEL (Unified Speculative Stack)        │
│   Base Model: Gemma 4 2B + MTP Drafter                     │
│   Hardware: RTX 3090 (24GB) → Blackwell (Enterprise)      │
│   Multi-Adapter: Hot-swappable expert adapters             │
│   VRAM Efficiency: Near-zero (Shared KV Cache)          │
│   ┌───────────────────────────────────────────────┐     │
│   │ MTP (4 tokens) → DFlash (16 blocks) → SSD   │     │
│   │ Layer 9: Agentic Engine                    │     │
│   └───────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              LAYER 8: CIRCUIT BREAKER (Governance)          │
│   # SR 26-02 COMPLIANCE GATE: Active Containment          │
│   ┌───────────────────────────────────────────────┐       │
│   │ SSD/Saguaro Async Audit (while GPU verifies) │       │
│   │ Layer 8: Governance + Latency Erasure     │       │
│   └───────────────────────────────────────────────┘       │
│   1. Layer 9 Agentic generates intent payload              │
│   2. Circuit Breaker intercepts                           │
│   3. Validates against SR 26-02 policy                   │
│   4. Signs validated trajectories (Layer 8 signature)         │
│   5. Blocks non-compliant paths                           │
│   6. [DHITL] Tier 1 escalates to Human SME Review       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              LATENT TELEMETRY (Neural EKG)                   │
│   Activation Hooks → Residual Stream at each layer          │
│   Decision Nodes → Latent hash at critical points          │
│   Audit Log → Kafka → Fed-verifiable proof                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Neural Tool System

### Kernel Components

| Component | File | Purpose |
|-----------|------|---------|
| **NeuralToolDispatcher** | `app/dispatcher.py` | CPU scheduler for tool hot-swapping |
| **KernelManifest** | `app/kernel_manifest.py` | Tool registry with JSON-RPC |
| **ToolRouter** | `app/tool_router.py` | Intent-based tool routing |
| **Kernel Server** | `server.py` | vLLM wrapper with Layer 8/9 governance |
| **Quad-Node Deploy** | `deploy_quad_node.sh` | Multi-sector deployment |

### Tool Adapter Registry (51 Specialized Adapters)

#### Construction/Site Safety
- `estimating_lora` - Margin protection (3.5% floor)
- `legal_lora` - FAR/DFARS compliance
- `safety_lora` - OSHA site safety
- `logistics_lora` - DOT HOS limits
- `machinery_safety_envelope` - Heavy equipment remote kill-switch
- `davis_bacon_wage_auditor` - Prevailing wage compliance

#### Healthcare/Pharma
- `hipaa_privacy_airlock` - PII de-identification
- `fda_protocol_adherence` - Clinical trial integrity
- `med_expert_v1` - DHITL-required diagnosis
- `insurance_policy_eval` - Fair claims

#### Regional Banking
- `fair_lending_bias_v4` - ECOA/FHAct compliance
- `anti_money_laundering` - Structuring detection
- `ofac_sanctions_v2` - SDN geofencing
- `sr26_02_validator` - Latent trace required

#### Maritime/Logistics
- `dot_imdg_safety` - Class 1 restrictions
- `defense_export_v3` - ITAR compliance
- `harmonized_tariff_law` - Tariff fraud prevention
- `predictive_safety_os` - Maintenance integrity
- `crane_stability_validator` - Maritime weight limits

#### Energy/Utilities
- `nerc_cip_compliance` - Critical infrastructure multi-sig
- `arc_flash_safety_v2` - PPE detection
- `epa_emissions_audit` - Data integrity
- `utility_rate_governance` - PSC cap compliance
- `smart_grid_scada_gateway` - Hardware token required

#### Defense/Aerospace
- `rules_of_engagement_v7` - ROE compliance
- `mil_spec_compliance` - NAVAIR integrity
- `top_secret_redaction` - Classification masking
- `rugged_hardware_diag` - Sensor integrity

#### Legal Tech
- `ethical_wall_v2` - Conflict of interest
- `privilege_redactor` - Attorney-client privilege
- `indemnification_enforcer` - LOA override
- `sec_finra_reporting` - Forensic trace

#### Insurtech
- `anti_bias_actuarial` - Proxy detection
- `siu_investigation_v1` - Pattern integrity
- `state_regulatory_filing` - OIR cap compliance
- `empathetic_compliance` - Coverage guarantees

#### Neural Tools (Tool-Adapters)
- `email_governed_workflow` - PII-locked email
- `sql_readonly_auditor` - Read-only SQL
- `erp_materiality_guard` - >$50k DHITL
- `aibom_forensic_reporter` - Self-audit
- `hazmat_route_planner` - Class 1 blocked
- `document_redactor` - Privilege redaction
- `incident_escalator` - Auto-escalation
- `safety_ppe_detector` - Vision PPE
- `eeoc_bias_detector` - Anonymization

### JSON-RPC Tool Workflow

```python
# Tool Detection in Reasoning
"Transfer $75k. [CALL_TOOL:FINANCIAL_WIRE_V1]"
  ↓
# Intent Detection
dispatcher.detect_tool_intent() → tool_id="FINANCIAL_WIRE_V1"
  ↓
# Kernel Reconfigure
dispatcher.reconfigure_kernel(tool_id) → Load LoRA adapter
  ↓
# Governance Check
dispatcher.check_governance(tool_id, text) → Block PII/structuring
  ↓
# Execute Dispatch
dispatcher.execute_dispatch(tool_id, params, context)
  ↓
# forensic_hash = sha256(tool_id+context)
{
  "success": true,
  "tool_id": "FINANCIAL_WIRE_V1",
  "forensic_hash": "d7d4f936..."
}
```

---

## Quad-Node Deployment

Single 24GB GPU can run 4 isolated nodes:

| Node | Port | Domain | VRAM |
|------|------|--------|-----|
| Estimating | 8001 | Financial | 5.4 GB |
| Legal | 8002 | FAR/Compliance | 5.4 GB |
| Safety | 8003 | OSHA | 5.4 GB |
| Logistics | 8004 | DOT | 5.4 GB |
| System | - | KV Cache | 2.2 GB |

```bash
# Deploy quad-node cluster
./deploy_quad_node.sh start

# Check status
./deploy_quad_node.sh status

# Stop cluster
./deploy_quad_node.sh stop
```

---

## Technical Exploration

### 1. The VRAM/Compliance Paradox

**Problem**: Enterprises face impossible choice:
- Deploy AI = risk regulatory violation, audit failure
- Restrict AI = lose competitive advantage

**MAIA Solution**:
- **Fixed VRAM Rent**: 17.8GB baseline (Gemma 4 + Airlock + KV Cache)
- **MTP Shared KV**: Near-zero VRAM overhead (uses base model activations)
- **Materiality-based routing**: Only high-risk triggers full audit
- **RTX 3090 compatible**: Full stack fits on 24GB

### 2. Unified Speculative Stack

- **Layer 9 (Agentic)**: MTP heads (4 tokens) → DFlash blocks (16 tokens)
- **Layer 8 (Governance)**: SSD/Saguaro async audit while GPU verifies
- **Latency Erasure**: Audit happens in speculative cycles - no time-tax for safety
- **Shared KV Cache**: Airlock and Actor share short-term memory

### 3. Model-Agnostic Governance

- Targets standard Transformer projection modules (q, k, v, o)
- Forward-compatible with Llama, DeepSeek, Gemma, etc.
- New model support in under 1 hour
- **Strategic Advantage**: Decoupled Rate of Intelligence (models) from Standard of Trust (MAIA)

### 4. Dynamic Materiality Escalation (DME) Engine

- **4-Layer Hierarchy**: Sector → Occupation → Tool → Context
- **L1 (Sector)**: Sets "Red Lines" (SR 26-02, HIPAA, SOX)
- **L2 (Role)**: Determines permissions (can propose $50M loan?)
- **L3 (Tool)**: Functional Tool-Adapters with constrained weights
- **L4 (Context)**: The Escalator - semantic intent analysis

### 5. Tool-Adapters (Neural Permissioning)

**51 Specialized Tool-Adapters as Constrained LoRA Weight-Sets**:

| Adapter | Domain | Constraint |
|---------|--------|------------|
| `email_governed_workflow` | Communication | PII blocked |
| `sql_readonly_auditor` | Data | SELECT only |
| `erp_materiality_guard` | Finance | >$50k → DHITL |
| `aibom_forensic_reporter` | Audit | Self-audit |
| `hazmat_route_planner` | Logistics | Class 1 blocked |
| `eeoc_bias_detector` | HR | Proxy blocked |
| `smart_grid_scada_gateway` | Utilities | Hardware token |
| `crane_stability_validator` | Maritime | Weight limit |
| `davis_bacon_wage_auditor` | Construction | Prevailing wage |

**The Pitch**: "An agent using our SQL-Adapter doesn't just 'promise' not to delete—it physically lacks the weights."

### 6. DHITL (Decentralized Human-in-the-Loop)

- Tier 1 (Critical) transactions require human SME review on mobile app
- 3 SME votes = consensus (APPROVED/REJECTED)
- Votes become RLHF training data for adapter fine-tuning
- **The Authority of Alignment**: SMEs as "Supreme Court"

### 7. Materiality Matrix (GDP-Aligned)

- **9 GDP Sectors** from GDPVal benchmark (44 occupations)
- **3 Risk Tiers**: Critical / Elevated / Benign
- GDP sector auto-detection from query keywords
- Domain-specific governance rules

### 8. Latent State Observability

- Intra-Inference Telemetry - Neural Flight Recorder
- Latent hashes at decision nodes provide forensic proof
- Turns "Black Box" AI into "Glass Box" for Fed auditors

---

## Key Components Reference

| Module | Purpose |
|--------|---------|
| `app/circuit_breaker.py` | Layer 8: Governance (Circuit Breaker) |
| `app/airlock.py` | Layer 7: PVI Airlock |
| `app/supervisor_router.py` | Hub/Spoke hierarchical routing |
| `app/memory_manager.py` | VRAM/RAM/NVMe hot-swapping |
| `app/latent_telemetry.py` | Neural EKG + latent hashing |
| `app/dag_orchestrator.py` | Async DAG workflow |
| `app/dispatcher.py` | Neural Tool Dispatcher |
| `app/kernel_manifest.py` | Tool registry + JSON-RPC |
| `app/tool_router.py` | Intent-based tool routing |
| `app/gemma4_thinking_airlock.py` | Layer 8 reasoning interceptor |
| `app/routing.py` | Departmental path routing |
| `app/dynamic_adapter.py` | Hot-swappable LoRA adapter manager (23+ adapters) |
| `app/governance_profiles.py` | Industry profiles with Complexity Slider |
| `app/triage_supervisor.py` | GL-1/GL-2/GL-3/GL-4 governance levels |
| `app/early_exit_breaker.py` | Latent Space Circuit Breaker |
| `app/gitops_pipeline.py` | GitOps CI/CD for adapters |
| `app/airgapped_deployment.py` | Air-gapped/offline deployment |
| `app/pvi_airlock.py` | Latent hash validation |
| `forensics/logger.py` | Immutable audit ledger |
| `maia.py` | MAIA SDK CLI |
| `app/agentic_gateway.py` | Transparent proxy (invisible governance) |
| `app/policy_compiler.py` | Policy-to-Physics Compiler |
| `app/p2w_compiler.py` | P2W Compiler (4-stage pipeline) |
| `app.forensic_sidecar.py` | Forensic Sidecar (async audit) |
| `server.py` | Kernel Server with governance |
| `deploy_quad_node.sh` | Quad-node deployment |

### Dashboards

- **Policy Manager**: `docs/policy_manager.html` - Product dashboard with drag-drop PDF → policy compilation
- **Control Center**: `docs/dashboard.html` - Real-time EKG and adapter toggles

---

## Design Patterns

### 1. Triage Supervisor (Entry Point)
Lightweight supervisor at the entry point classifies queries as simple/complex and routes accordingly.

```python
from app.triage_supervisor import TriageSupervisor, GovernanceLevel

t = TriageSupervisor()
gl = t.determine_gl("Wire $50k to Russia")
# GL-3 (Strategic) - full governance
gl = t.determine_gl("Summarize this PDF")  
# GL-1 (Transactional) - fast track
```

### 2. Deterministic Offloading
Replace agentic reasoning with symbolic scripts for predictable tasks.

```python
from app.triage_supervisor import DETERMINISTIC_SCRIPTS
# sql_query, format_json, send_email, lookup_database, validate_format
# replace_agent=True - uses script instead of LLM
```

### 3. Governor-Lite Mode
Dynamic governance levels based on task:

| Level | Mode | Use Case |
|--------|------|---------|
| GL-1 | Transactional | Fast track, single agent |
| GL-2 | Operational | Sequential pipeline |
| GL-3 | Strategic | Full multi-agent |
| GL-4 | Audit | Compliance reporting |

### 4. Early-Exit Circuit Breaker
Checks speculative tokens BEFORE materialization - kills generation before output.

```python
from app.early_exit_breaker import EarlyExitCircuitBreaker

breaker = EarlyExitCircuitBreaker()
predictions = breaker.simulate_speculative_stream(prompt, tokens, confidences)
verdict = breaker.check_speculative_tokens(predictions)
# KILL | ESCALATE | CONTINUE
```

### 5. Governance-as-Code (Manifest)
Declarative policy configuration in YAML/JSON.

```yaml
# configs/maia_kernel_manifest.json
policy: "HIPAA-Finance-Hybrid"
airlock:
  latency_threshold: 150ms
  interrupt_on: ["PII_LEAK", "UNAUTHORIZED_WIRE_TRANSFER"]
adapters:
  - id: "legal_compliance_v4"
  - id: "risk_math_v2"
```

### 6. Interceptor Pattern (Sidecar)
Model stays "pure" - governance is a transparent proxy.

```python
from app.airlock import PVIAirlock
# Intercepts trajectories before they reach the model
# Blocks non-compliant paths
# Generates forensic hash
```

### 7. Neural Componentization (Adapter Fabric)
Multi-LoRA composition with hot-swapping.

```python
from app.dynamic_adapter import DynamicAdapterManager

m = DynamicAdapterManager()
# 23+ adapters organized by role:
# Module A: Banker (domain knowledge)
# Module B: Compliance (constraint knowledge)  
# Module C: Audit (reporting)
```

### 8. Unified Audit Ledger
Immutable sidecar database for compliance.

```python
from forensics.logger import get_logger

logger = get_logger()
logger.log(query, thinking_block, tool_id, violations)
# Returns latent_hash for forensic verification
stats = logger.get_violation_stats()
```

### 9. MAIA SDK CLI
Developer tool for governance operations.

```bash
python3 maia.py init --name project --sector finance
python3 maia.py simulate --scenario sanction
python3 maia.py certify
```

### 10. Agentic Gateway (Transparent Proxy)
Makes governance "invisible" - banks don't rewrite code.

```bash
# Run gateway
python3 -m app.agentic_gateway --upstream https://api.bank.com/v1
# Bank sends traffic to localhost:8080
# MAIA handles governance transparently
```

```python
from app.agentic_gateway import AgenticGateway
# Bank AI → localhost:8080 → [Governance] → Upstream Model
```

### 11. Policy-to-Physics Compiler
Compiles legal text into neural weights.

```python
from app.policy_compiler import PolicyCompiler, PolicyType

compiler = PolicyCompiler()
compiled = compiler.compile(PolicyType.SR_26_02)
# Input: "No wire transfers to OFAC countries"
# Output: LoRA weights that PHYSICALLY cannot violate
```

**The Narrative:**
- "We don't prompt engineer safety. We compile legal text."
- Legal Text → Mathematical Constraints → Physical Impossibility

### 12. P2W (Policy-to-Weights) Compiler
4-stage automated factory for scaling from consulting to SaaS.

```python
from app.p2w_compiler import P2WCompiler

compiler = P2WCompiler()
result = await compiler.compile("sr_2602")
```

| Stage | Name | Description |
|-------|------|-------------|
| 1 | Logic Extraction | Parse PDF to Constraint Manifest |
| 2 | Synthetic Data | Generate DPO training pairs |
| 3 | Neural Factory | QLoRA training → .safetensors |
| 4 | Red-Teaming | Validate <0.01% failure → Certify |

---

## Governance Profiles

| Profile | Sector | Materiality | Features |
|---------|--------|-------------|----------|
| Retail | General | Tier 3 | Standard mode |
| Marketing | General | Tier 3 | Standard mode |
| Finance | SR 26-02 | Tier 1 | Airlock + DHITL |
| Healthcare | HIPAA | Tier 1 | Airlock + DHITL |
| Legal | Privilege | Tier 1 | Airlock + DHITL |
| Construction | OSHA | Tier 2 | Safety audit |
| Energy | NERC CIP | Tier 1 | Critical infrastructure |
| Defense | ITAR/CC | Tier 1 | Classified handling |

---

## Quick Start

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env and set MAIA_API_KEY (required, min 16 chars)

# Start the Kernel Server
cd MAIA-Enterprise
python3 server.py

# Or deploy quad-node cluster
./deploy_quad_node.sh start
```

### Testing Tool Dispatch

```bash
# Test tool dispatch
curl -X POST http://localhost:8000/tool_dispatch \
  -H "X-MAIA-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"query": "Send email. [CALL_TOOL:GOVERNED_SMTP_V1]"}'

# List tools
curl -X GET http://localhost:8000/tools \
  -H "X-MAIA-Key: your_key"
```

### Running Tests

```bash
# Install dependencies
pip install pytest pytest-asyncio

# Run test suite
MAIA_API_KEY=testing_key_placeholder pytest tests/ -v
```

---

## SR 26-02 Compliance Mapping

| Requirement | MAIA Implementation |
|-------------|---------------------|
| **Effective Challenge** | PVI Airlock with Actor/Auditor dual-adapter validation |
| **Materiality Matrix** | Domain-specific adapters with Tier 1/2/3 routing |
| **Continuous Monitoring** | STaR self-evolution loop + Latent EKG |
| **Data Sovereignty** | Insular RAG with air-gapped Ollama/ChromaDB |
| **Conceptual Soundness** | Latent hash provides forensic proof of reasoning |
| **Human Oversight** | DHITL SME voting for Tier 1 transactions |

---

## Example Transaction Log

| Time | Transaction ID | Query | Tool | Tier | Status | Latency | Reason |
|------|--------------|-------|------|------|--------|---------|--------|
| 18:03 | 8f3a2b1c | Wire $25M Russia | swift | T1 | **BLK** | 45ms | OFAC hit |
| 18:02 | 7d4c9e2f | SELECT > $1M | sql | T1 | **BLK** | 38ms | Balance |
| 18:01 | 6e5d8a1b | Redline clause | contract | T2 | **PASS** | 35ms | OK |
| 18:00 | 5f4c7b2a | Loan $75K | swift | T1 | **PEN** | 52ms | Threshold |
| 17:59 | 4a3b6c1d | Scan CVE | cyber | T2 | **PASS** | 42ms | OK |

---

## Performance Metrics

### Latency Test Results

| Component | Fast Path | Full Path | Notes |
|-----------|----------|----------|-------|
| Triage Supervisor | 0.007ms | 0.8ms* | Keyword + Neural |
| Early Exit Breaker | 0.015ms | - | Token-level |
| Agentic Gateway | 0.363ms | - | Proxy overhead |
| Dynamic Adapter | 0.011ms | - | Hash routing |

*Triage: Simple/critical queries use keyword matching (<1ms). Ambiguous/adversarial queries trigger BERT embedding (~15ms in production).

**Fed Requirement**: <150ms for critical paths

**Production Note**: Use sentence-transformers for neural embeddings in Triage Supervisor to catch sophisticated adversarial attacks.

---

## What's New (v1.1.0)

| Feature | Description |
|---------|-------------|
| **Triage Supervisor** | Entry-point classification - routes simple queries to fast track |
| **Governor-Lite** | GL-1/GL-2/GL-3/GL-4 dynamically gates complexity |
| **Early-Exit Breaker** | Checks speculative tokens BEFORE materialization |
| **GitOps Pipeline** | Adapter CI/CD with progressive rollout |
| **Air-gapped Mode** | Offline deployment with USB updates |
| **MAIA SDK** | CLI tool: `maia init`, `maia simulate`, `maia certify` |
| **8 Governance Profiles** | Retail, Marketing, Finance, Healthcare, Legal, Construction, Energy (NERC CIP), Defense (ITAR/CC) |
| **23+ Hot-swappable Adapters** | Modular - update policy without retraining |
| **Agentic Gateway** | Transparent proxy - invisible governance for existing AI |
| **Policy-to-Physics Compiler** | Compiles legal text into neural weights |
| **P2W Compiler** | 4-stage automated factory (Consulting → SaaS) |
| **Forensic Sidecar** | Async audit without inference latency |

---

## Hardware Requirements

MAIA runs locally on enterprise GPUs:
- **Minimum**: NVIDIA RTX 3090 (24GB VRAM)
- **Recommended**: NVIDIA A100 or H100 (80GB+ VRAM)

---

## Links

- **Dashboard**: http://localhost:3033
- **Kernel API**: http://localhost:8000
- **Implementation**: https://github.com/nnine0/MAIA-Enterprise