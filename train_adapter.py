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
