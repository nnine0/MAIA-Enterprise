# MAIA Sovereign Adapter Library

This directory contains all domain-specific LoRA adapters for the MAIA Enterprise Governance OS. Each adapter is a PEFT-compatible LoRA weight set stored in its own subdirectory.

## Architecture

```
adapters/
├── finance-expert-v4/          # Regulated sector adapters
│   ├── adapter_config.json     # PEFT LoRA configuration
│   ├── adapter_model.safetensors  # Trained weights
│   └── README.md               # Adapter metadata
├── pvi-airlock-sr2602/         # Governance validators
├── credit-expert-v4/
├── ...
└── README.md                   # This file
```

## Adapter Injection Workflow

MAIA uses a **Sovereign Adapter Registry** pattern. Adapters are not hard-coded into the application — they are **injected as data** into the LoRAX inference server at runtime.

### Local (S2S / Air-Gapped)

```yaml
# docker-compose.yml
services:
  lorax-kernel:
    volumes:
      - ./adapters:/data/adapters          # Mount the adapter library
    command: >
      --model-id google/gemma-4-26b-a4b-it
```

MAIA sends `adapter_id: "/data/adapters/finance-expert-v4"` to LoRAX, which dynamically loads the weights just-in-time.

### Runtime Verification

```bash
# Test a specific adapter through LoRAX directly
curl http://localhost:8080/generate \
  -X POST \
  -d '{
    "inputs": "Test compliance query",
    "parameters": {
      "adapter_id": "/data/adapters/pvi-airlock-sr2602",
      "adapter_source": "local",
      "max_new_tokens": 100
    }
  }'

# Test through MAIA governance layer
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $MAIA_API_KEY" \
  -d '{
    "messages": [
      {"role": "user", "content": "Approve $50M loan for subcontractor"}
    ],
    "model": "google/gemma-4-26b-a4b-it",
    "extra_body": {
      "adapter_id": "/data/adapters/finance-expert-v4",
      "adapter_source": "local"
    }
  }'
```

## Adapter Inventory (60 Adapters)

### Sector Adapters (L1 - Domain Experts)

| Adapter ID | Sector | Role | Tier |
|-----------|--------|------|------|
| `finance-expert-v4` | Finance | Analyst | 1 |
| `credit-expert-v4` | Finance | Analyst | 1 |
| `compliance-expert-v4` | Finance | Auditor | 1 |
| `fraud-aml-expert-v4` | Finance | Analyst | 1 |
| `pvi-airlock-sr2602` | Governance | Auditor | 1 |
| `terminal-expert-v4` | Logistics | Expert | 2 |
| `safety-auditor-v4` | Logistics | Auditor | 1 |

### Hub/Manager Adapters (L2 - Orchestrators)

| Adapter ID | Sector | Role | Tier |
|-----------|--------|------|------|
| `credit-risk-manager-hub` | Finance | Manager | 1 |
| `terminal-director-hub` | Logistics | Manager | 1 |
| `department-head-hub` | Legal | Manager | 1 |
| `governance-hub-v1` | Governance | Manager | 1 |

### SME Adapters (L3 - Specialists)

| Adapter ID | Sector | Role | Tier |
|-----------|--------|------|------|
| `cash-flow-sme` | Finance | SME | 2 |
| `collateral-valuator` | Finance | SME | 2 |
| `sanctions-list-sme` | Finance | SME | 1 |
| `hazmat-sme` | Logistics | SME | 2 |
| `contract-expert-v4` | Legal | Expert | 1 |
| `regulatory-expert-v4` | Legal | Expert | 1 |
| *(36 more in directory)* | | | |

See [AIBOM Registry](../app/models/aibom.py) for programmatic inventory tracking.

## Training

Adapters are trained using the `train_adapter.py` script:

```bash
# Train a single adapter from domain text data
python train_adapter.py \
  --adapter-id finance-expert-v4 \
  --data-dir ./training_data/finance

# Train all adapters from organized data directories
python train_adapter.py --all --data-dir ./training_data

# Enable self-evolving loop (continuous retraining on audit feedback)
python train_adapter.py \
  --adapter-id pvi-airlock-sr2602 \
  --data-dir ./audit_logs \
  --evolve
```

Each trained adapter produces:
- `adapter_model.safetensors` — LoRA weights
- `adapter_config.json` — PEFT configuration with MAIA metadata
- AIBOM registration — tracked in the model inventory

## AIBOM Protocol

Every adapter is cryptographically tracked in the AI Bill of Materials:

```python
from app.models.aibom import registry

entry = registry.register_adapter(
    adapter_id="finance-expert-v4",
    name="Finance Expert V4",
    version="1.0.0",
    domain="finance",
    materiality_tier=1,
    base_model="google/gemma-4-26b-a4b-it",
    description="SR 26-02 compliant finance expert LoRA",
)
print(f"Registered with hash: {entry.provenance_hash}")
```

## For Auditors

The key architectural guarantee:

> **"Adapters are data, not code."**
> 
> MAIA's kernel refuses to load any adapter that has not passed the Independent Validation pipeline. The Sovereign Adapter Registry maintains a 100% auditable AIBOM. We have decoupled the Inference Engine from the Expert Knowledge — this is the core of our Compliance-as-Code strategy.
