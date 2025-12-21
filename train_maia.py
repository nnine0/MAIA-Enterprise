"""
MAIA Training Script - Adapted for MAIA project environment.
Ensures compatibility with Docker GPU setup and MAIA configurations.
"""

import json
import os
import warnings
import gc
from pathlib import Path
from typing import List, Dict, Any

import torch
from sklearn.model_selection import train_test_split
from datasets import Dataset, DatasetDict
from transformers import (
    AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig,
    TrainingArguments, Trainer, DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
import evaluate

# Import MAIA config
import config

# Suppress warnings
warnings.filterwarnings("ignore", message="MatMul8bitLt")
warnings.filterwarnings("ignore", category=FutureWarning, module="torch.utils.checkpoint")

# Memory optimization
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

def clean_memory():
    """Force Python to release memory it isn't using."""
    gc.collect()
    torch.cuda.empty_cache()

def load_examples(path: str) -> List[Dict[str, Any]]:
    """Load examples from JSON file or JSONL."""
    s = Path(path).read_text(encoding="utf-8").strip()
    if s.startswith("["):
        data = json.loads(s)
    else:
        data = [json.loads(line) for line in s.splitlines() if line.strip()]
    return data

def make_example(item: Dict[str, Any]) -> Dict[str, str]:
    """Build training pairs with prompt and target."""
    q = item.get("question", "").strip()
    # Prefer explicit response; fallback to complex_CoT if available
    if item.get("response"):
        a = item["response"].strip()
    else:
        a = item.get("complex_CoT", "").strip()
    prompt = f"Question: {q}\nAnswer:"
    return {"prompt": prompt, "response": a}

def preprocess(batch: Dict[str, List[str]], tokenizer, max_length: int) -> Dict[str, List[List[int]]]:
    """Preprocess batch for training."""
    prompts = batch["prompt"]
    responses = batch["response"]
    inputs = []

    for p, r in zip(prompts, responses):
        full = p + " " + r
        tokenized = tokenizer(full, truncation=True, max_length=max_length, padding="max_length")
        input_ids = tokenized["input_ids"]
        att = tokenized["attention_mask"]

        # Create labels where prompt tokens are masked to -100
        prompt_ids = tokenizer(p, truncation=True, max_length=max_length)["input_ids"]
        labels_ids = input_ids.copy()
        prefix_len = len(prompt_ids)
        for i in range(min(prefix_len, len(labels_ids))):
            labels_ids[i] = -100

        inputs.append({"input_ids": input_ids, "attention_mask": att, "labels": labels_ids})

    # Return dict of lists
    return {k: [d[k] for d in inputs] for k in inputs[0]}

def compute_metrics(eval_pred):
    """Compute metrics for evaluation."""
    # Placeholder for perplexity or other metrics
    return {}

def main():
    # Clean memory at start
    clean_memory()

    # Configuration - adapt paths as needed
    input_path = os.getenv("TRAIN_DATA_PATH", "/data/MAIA-v5.json")  # Mount your data
    model_name = config.BASE_MODEL_ID  # Use MAIA base model
    output_dir = os.getenv("OUTPUT_DIR", "/adapters/maia_finetuned")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # Load and prepare data
    data = load_examples(input_path)
    examples = [make_example(x) for x in data if x.get("question")]
    print(f"Total examples: {len(examples)}")

    train_exs, val_exs = train_test_split(examples, test_size=0.05, random_state=42)
    ds = DatasetDict({
        "train": Dataset.from_list(train_exs),
        "validation": Dataset.from_list(val_exs)
    })

    # Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
    if tokenizer.pad_token_id is None:
        tokenizer.add_special_tokens({"pad_token": config.PAD_TOKEN})

    # Model configuration
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        attn_implementation="eager"
    )

    model.resize_token_embeddings(len(tokenizer))

    # LoRA configuration
    model = prepare_model_for_kbit_training(model)
    lora_config = LoraConfig(
        r=config.LORA_R,
        lora_alpha=config.LORA_ALPHA,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "fc1", "fc2"],  # Adapt to model
        lora_dropout=config.LORA_DROPOUT,
        bias="none",
        task_type="CAUSAL_LM"
    )

    model = get_peft_model(model, lora_config)
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.print_trainable_parameters()

    # Preprocessing
    max_length = 512
    tokenized_ds = ds.map(
        lambda batch: preprocess(batch, tokenizer, max_length),
        batched=True,
        remove_columns=["prompt", "response"],
        keep_in_memory=False,
        load_from_cache_file=True,
        num_proc=1,
        desc="Tokenizing on Disk"
    )
    tokenized_ds.set_format(type="torch")

    # Training arguments - optimized for GPU memory
    training_args = TrainingArguments(
        output_dir=output_dir,
        max_steps=160,
        num_train_epochs=config.NUM_TRAIN_EPOCHS,
        per_device_train_batch_size=config.PER_DEVICE_TRAIN_BATCH_SIZE,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=config.GRADIENT_ACCUMULATION_STEPS,
        eval_accumulation_steps=1,
        optim="paged_adamw_8bit",
        learning_rate=config.LEARNING_RATE,
        fp16=False,
        bf16=True,
        max_grad_norm=0.3,
        warmup_ratio=0.03,
        lr_scheduler_type="constant",
        logging_steps=1,
        save_steps=10,
        eval_steps=10,
        eval_strategy="steps",
        load_best_model_at_end=True,
        ddp_find_unused_parameters=False,
        group_by_length=True,
        greater_is_better=False,
        save_total_limit=2,
        report_to="none"
    )

    data_collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)

    # Load metric
    try:
        metric = evaluate.load("perplexity")
    except:
        metric = None

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_ds["train"],
        eval_dataset=tokenized_ds["validation"],
        data_collator=data_collator,
        compute_metrics=compute_metrics
    )

    # Train
    trainer.train()

    # Save model
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"Model saved to {output_dir}")

if __name__ == "__main__":
    main()