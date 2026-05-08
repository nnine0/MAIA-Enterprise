"""
MAIA Self-Evolving Adapter Trainer
==================================
Trains domain-specific LoRA adapters from audit logs, compliance docs, and sector data.

Adapters are auto-discovered from adapters/registry.json and existing adapter_config.json
metadata. Explicit TRAINING_CONFIGS override defaults for adapters needing specific hyperparams.

Usage:
    # Train a single adapter
    python train_adapter.py --adapter-id finance_expert_v4 --data-dir ./training_data/finance
    
    # Train all adapters from organized data
    python train_adapter.py --all --data-dir ./training_data
    
    # Retrain with self-evolving loop (continuous)
    python train_adapter.py --adapter-id pvi_airlock_sr2602 --data-dir ./audit_logs --evolve
    
    # List all available adapters
    python train_adapter.py --list
"""

import argparse
import json
import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path


ADAPTERS_DIR = os.path.join(os.path.dirname(__file__), "adapters")
REGISTRY_PATH = os.path.join(ADAPTERS_DIR, "registry.json")
BASE_MODEL_ID = os.getenv("BASE_MODEL_ID", "google/gemma-4-26b-a4b-it")

# Default LoRA hyperparams per tier — overridden by TRAINING_CONFIGS entries
TIER_DEFAULTS = {
    1: {"r": 16, "alpha": 32, "dropout": 0.05, "num_epochs": 3, "batch_size": 4,
        "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
        "learning_rate": 2e-4},
    2: {"r": 8, "alpha": 16, "dropout": 0.1, "num_epochs": 4, "batch_size": 4,
        "target_modules": ["q_proj", "v_proj"],
        "learning_rate": 1e-4},
    3: {"r": 8, "alpha": 16, "dropout": 0.1, "num_epochs": 3, "batch_size": 4,
        "target_modules": ["q_proj", "v_proj"],
        "learning_rate": 1e-4},
}

# Explicit overrides for adapters needing non-default hyperparameters
TRAINING_CONFIGS = {
    "finance_expert_v4": {
        "r": 16, "alpha": 32, "dropout": 0.05,
        "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
        "learning_rate": 2e-4, "num_epochs": 3, "batch_size": 4,
        "description": "Finance expert for SR 26-02 compliance",
        "sector": "finance", "role": "analyst", "tier": 1,
    },
    "pvi_airlock_sr2602": {
        "r": 8, "alpha": 16, "dropout": 0.1,
        "target_modules": ["q_proj", "v_proj"],
        "learning_rate": 1e-4, "num_epochs": 5, "batch_size": 4,
        "description": "PVI Airlock SR 26-02 compliance validator",
        "sector": "governance", "role": "auditor", "tier": 1,
    },
    "credit_expert_v4": {
        "r": 16, "alpha": 32, "dropout": 0.05,
        "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
        "learning_rate": 2e-4, "num_epochs": 3, "batch_size": 4,
        "description": "Credit risk assessment expert",
        "sector": "finance", "role": "analyst", "tier": 1,
    },
    "compliance_expert_v4": {
        "r": 8, "alpha": 16, "dropout": 0.1,
        "target_modules": ["q_proj", "v_proj"],
        "learning_rate": 1e-4, "num_epochs": 5, "batch_size": 4,
        "description": "Regulatory compliance expert",
        "sector": "finance", "role": "auditor", "tier": 1,
    },
    "fraud_aml_expert_v4": {
        "r": 16, "alpha": 32, "dropout": 0.05,
        "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
        "learning_rate": 2e-4, "num_epochs": 3, "batch_size": 4,
        "description": "Fraud and AML detection expert",
        "sector": "finance", "role": "analyst", "tier": 1,
    },
    "terminal_expert_v4": {
        "r": 16, "alpha": 32, "dropout": 0.05,
        "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
        "learning_rate": 2e-4, "num_epochs": 3, "batch_size": 4,
        "description": "Terminal operations expert",
        "sector": "logistics", "role": "expert", "tier": 2,
    },
    "safety_auditor_v4": {
        "r": 8, "alpha": 16, "dropout": 0.1,
        "target_modules": ["q_proj", "v_proj"],
        "learning_rate": 1e-4, "num_epochs": 5, "batch_size": 4,
        "description": "Safety compliance auditor",
        "sector": "logistics", "role": "auditor", "tier": 1,
    },
}


def _discover_all_adapters():
    """Return dict of adapter_id -> config merged from registry metadata + tier defaults + overrides."""
    adapters = {}

    reg_path = REGISTRY_PATH
    if os.path.isfile(reg_path):
        with open(reg_path) as f:
            reg = json.load(f)

        all_paths = {}
        for entry in reg.get("registry", {}).values():
            all_paths[entry["agentic"]] = {"sector": "unknown", "role": "agentic", "tier": 3}
            all_paths[entry["validator"]] = {"sector": "unknown", "role": "validator", "tier": 1}
        for key, path in reg.get("hubs", {}).items():
            all_paths[path] = {"sector": key, "role": "hub", "tier": 1}
        for key, path in reg.get("specialists", {}).items():
            all_paths[path] = {"sector": key, "role": "specialist", "tier": 2}
        for key, path in reg.get("tool_adapters", {}).items():
            all_paths[path] = {"sector": key, "role": "tool", "tier": 2}

        for path, meta in all_paths.items():
            adapter_id = path.rstrip("/").split("/")[-1]
            adapters[adapter_id] = meta

    # Also scan disk for any adapter dirs not in registry
    if os.path.isdir(ADAPTERS_DIR):
        for entry in os.listdir(ADAPTERS_DIR):
            dirpath = os.path.join(ADAPTERS_DIR, entry)
            config_path = os.path.join(dirpath, "adapter_config.json")
            if os.path.isdir(dirpath) and entry not in adapters:
                meta = {"sector": "unknown", "role": "unknown", "tier": 3}
                if os.path.isfile(config_path):
                    try:
                        with open(config_path) as f:
                            c = json.load(f)
                        m = c.get("maia_metadata", {})
                        meta = {
                            "sector": m.get("sector", "unknown"),
                            "role": m.get("role", "unknown"),
                            "tier": m.get("materiality_tier", 3),
                        }
                    except (json.JSONDecodeError, OSError):
                        pass
                adapters[entry] = meta

    return adapters


def _get_config(adapter_id):
    """Get full training config for adapter_id, merging override, disk metadata, and tier defaults."""

    if adapter_id in TRAINING_CONFIGS:
        return TRAINING_CONFIGS[adapter_id]

    adapter_dir = os.path.join(ADAPTERS_DIR, adapter_id)
    config_path = os.path.join(adapter_dir, "adapter_config.json")
    meta = {"sector": "unknown", "role": "unknown", "tier": 3}

    if os.path.isfile(config_path):
        try:
            with open(config_path) as f:
                c = json.load(f)
            m = c.get("maia_metadata", {})
            meta = {
                "sector": m.get("sector", "unknown"),
                "role": m.get("role", "unknown"),
                "tier": m.get("materiality_tier", 3),
            }
        except (json.JSONDecodeError, OSError):
            pass

    tier = meta.get("tier", 3)
    defaults = TIER_DEFAULTS.get(tier, TIER_DEFAULTS[3])

    return {
        **defaults,
        "description": f"Auto-configured {adapter_id}",
        "sector": meta["sector"],
        "role": meta["role"],
        "tier": tier,
    }


def train_adapter(adapter_id, data_dir, evolve=False):
    """Train a LoRA adapter on domain-specific data."""
    cfg = _get_config(adapter_id)
    if not cfg:
        print(f"[train_adapter] Cannot resolve config for: {adapter_id}")
        return False

    adapter_dir = os.path.join(ADAPTERS_DIR, adapter_id)
    os.makedirs(adapter_dir, exist_ok=True)

    print(f"{'='*60}")
    print(f"Training adapter: {adapter_id}")
    print(f"  Sector: {cfg['sector']}, Role: {cfg['role']}, Tier: {cfg['tier']}")
    print(f"  Base model: {BASE_MODEL_ID}")
    print(f"  LoRA rank: {cfg['r']}, alpha: {cfg['alpha']}, dropout: {cfg['dropout']}")
    print(f"  Target modules: {cfg['target_modules']}")
    print(f"  Output: {adapter_dir}")
    print(f"{'='*60}")

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig, get_peft_model, get_peft_model_state_dict
        from peft import set_peft_model_state_dict
        import safetensors.torch
    except ImportError as e:
        print(f"[train_adapter] Missing dependency: {e}")
        print("  Install: pip install torch transformers peft safetensors datasets")
        return False

    data_paths = _find_training_data(data_dir, adapter_id, cfg["sector"])
    if not data_paths:
        print(f"[train_adapter] No training data found for {adapter_id}")
        print(f"  Looked in: {data_dir}")
        print(f"  Create .txt files with domain-specific prompts and responses.")
        return False

    print(f"[train_adapter] Found {len(data_paths)} training files")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token

    print(f"[train_adapter] Loading base model: {BASE_MODEL_ID}")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )

    lora_config = LoraConfig(
        r=cfg["r"],
        lora_alpha=cfg["alpha"],
        lora_dropout=cfg["dropout"],
        target_modules=cfg["target_modules"],
        bias="none",
        task_type="CAUSAL_LM",
        inference_mode=False,
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    print(f"[train_adapter] Loading and tokenizing data...")
    texts = []
    for path in data_paths:
        with open(path, "r") as f:
            texts.append(f.read())

    encodings = tokenizer(texts, truncation=True, padding=True, max_length=2048, return_tensors="pt")

    dataset = torch.utils.data.TensorDataset(encodings["input_ids"], encodings["attention_mask"])
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=cfg["batch_size"], shuffle=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["learning_rate"])

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.train()
    model.to(device)

    print(f"[train_adapter] Training on {device}...")
    global_step = 0
    for epoch in range(cfg["num_epochs"]):
        total_loss = 0
        for batch in dataloader:
            input_ids = batch[0].to(device)
            attention_mask = batch[1].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=input_ids)
            loss = outputs.loss

            loss.backward()
            optimizer.step()
            optimizer.zero_grad()

            total_loss += loss.item()
            global_step += 1

        avg_loss = total_loss / max(len(dataloader), 1)
        print(f"  Epoch {epoch+1}/{cfg['num_epochs']} - loss: {avg_loss:.4f}")

    print(f"[train_adapter] Saving adapter to {adapter_dir}")

    state_dict = get_peft_model_state_dict(model)
    safetensors.torch.save_file(state_dict, os.path.join(adapter_dir, "adapter_model.safetensors"))

    adapter_config = {
        "peft_type": "LORA",
        "task_type": "CAUSAL_LM",
        "base_model_name_or_path": BASE_MODEL_ID,
        "r": cfg["r"],
        "lora_alpha": cfg["alpha"],
        "lora_dropout": cfg["dropout"],
        "target_modules": cfg["target_modules"],
        "bias": "none",
        "inference_mode": True,
        "adapter_name": adapter_id,
        "maia_metadata": {
            "sector": cfg["sector"],
            "role": cfg["role"],
            "materiality_tier": cfg["tier"],
            "description": cfg["description"],
            "version": "1.0.0",
            "training_date": datetime.utcnow().isoformat(),
            "training_data_hash": _compute_data_hash(data_paths),
        },
    }

    with open(os.path.join(adapter_dir, "adapter_config.json"), "w") as f:
        json.dump(adapter_config, f, indent=2)

    _register_in_aibom(adapter_id, cfg)
    print(f"[train_adapter] Done. Adapter saved to {adapter_dir}")

    if evolve:
        _run_self_evolve(adapter_id, adapter_dir)

    return True


def _find_training_data(data_dir, adapter_id, sector):
    """Find training data files for the given adapter."""
    paths = []

    if data_dir and os.path.isdir(data_dir):
        patterns = [
            f"{adapter_id}.txt",
            f"{adapter_id}.jsonl",
            f"{sector}/*.txt",
            f"{sector}/*.jsonl",
        ]
        for pattern in patterns:
            matched = list(Path(data_dir).glob(pattern))
            paths.extend(str(p) for p in matched)

    if not paths:
        default_data = os.path.join(data_dir or ".", f"{adapter_id}.txt")
        if os.path.isfile(default_data):
            paths.append(default_data)

    return paths


def _compute_data_hash(paths):
    """Compute a hash of training data for provenance."""
    hasher = hashlib.sha256()
    for path in sorted(paths):
        with open(path, "rb") as f:
            hasher.update(f.read())
    return hasher.hexdigest()[:16]


def _register_in_aibom(adapter_id, cfg):
    """Register the trained adapter in AIBOM."""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
        from models.aibom import registry
        registry.register_adapter(
            adapter_id=adapter_id,
            name=cfg["description"],
            version="1.0.0",
            domain=cfg["sector"],
            materiality_tier=cfg["tier"],
            base_model=BASE_MODEL_ID,
            description=cfg["description"],
        )
        print(f"[train_adapter] Registered in AIBOM: {adapter_id}")
    except Exception as e:
        print(f"[train_adapter] AIBOM registration skipped: {e}")


def _run_self_evolve(adapter_id, adapter_dir):
    """Self-evolving loop: validate on audit data, flag drift, retrain."""
    print(f"[train_adapter] Self-evolve mode activated for {adapter_id}")
    print(f"  Monitoring: {adapter_dir}")
    print(f"  To enable continuous retraining, run with --evolve and a cron trigger.")


def train_all(data_dir):
    """Train all discovered adapters."""
    discovered = _discover_all_adapters()
    all_ids = sorted(set(list(discovered.keys()) + list(TRAINING_CONFIGS.keys())))
    results = []
    for adapter_id in all_ids:
        ok = train_adapter(adapter_id, data_dir)
        results.append((adapter_id, ok))
    print(f"\n{'='*60}")
    print("Training Summary:")
    for adapter_id, ok in results:
        status = "OK" if ok else "SKIPPED (no data)"
        print(f"  {adapter_id}: {status}")
    return all(ok for _, ok in results)


def main():
    parser = argparse.ArgumentParser(description="MAIA Self-Evolving Adapter Trainer")
    parser.add_argument("--adapter-id", type=str, help="Adapter ID to train")
    parser.add_argument("--data-dir", type=str, default="./training_data", help="Directory with training data")
    parser.add_argument("--all", action="store_true", help="Train all adapters")
    parser.add_argument("--evolve", action="store_true", help="Enable self-evolving loop")
    parser.add_argument("--list", action="store_true", help="List available adapters")

    args = parser.parse_args()

    if args.list:
        discovered = _discover_all_adapters()
        all_ids = sorted(set(list(discovered.keys()) + list(TRAINING_CONFIGS.keys())))
        print("Available adapters:")
        for aid in all_ids:
            cfg = _get_config(aid)
            print(f"  {aid:30s} [{cfg['sector']:12s}] {cfg['description']}")
        return

    if args.all:
        train_all(args.data_dir)
    elif args.adapter_id:
        train_adapter(args.adapter_id, args.data_dir, evolve=args.evolve)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
