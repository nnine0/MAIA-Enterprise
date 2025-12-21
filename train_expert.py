import sys
import os
import argparse
import torch
from datasets import load_dataset, concatenate_datasets
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, TrainingArguments, Trainer, DataCollatorForSeq2Seq
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
import config

def parse_args():
    parser = argparse.ArgumentParser(description="Train LoRA adapter for expert.")
    parser.add_argument("adapter_name", help="Name of the adapter, e.g., adapter_math")
    parser.add_argument("dataset_path", help="Path to dataset, JSON or HF name")
    parser.add_argument("--expert_data_path", default=config.DEFAULT_EXPERT_DATA_PATH, help="Path to expert data for oversampling")
    parser.add_argument("--oversample_factor", type=int, default=config.DEFAULT_OVERSAMPLE_FACTOR, help="Oversample factor")
    parser.add_argument("--output_dir", default=None, help="Output directory")
    return parser.parse_args()

args = parse_args()
ADAPTER_NAME = args.adapter_name
DATASET_PATH = args.dataset_path
EXPERT_DATA_PATH = args.expert_data_path
OVERSAMPLE_FACTOR = args.oversample_factor
OUTPUT_DIR = args.output_dir or f"{config.DEFAULT_OUTPUT_DIR}/{ADAPTER_NAME}"

# 1. Load Base Model (Always the same)
base_model_id = config.BASE_MODEL_ID

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.bfloat16
)

model = AutoModelForCausalLM.from_pretrained(
    base_model_id,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True
)
tokenizer = AutoTokenizer.from_pretrained(base_model_id, use_fast=True, trust_remote_code=True)
if tokenizer.pad_token_id is None:
    tokenizer.add_special_tokens({"pad_token": "<|pad|>"})
model.resize_token_embeddings(len(tokenizer))

# 2. Prepare LoRA (The "Empty Cartridge")
model = prepare_model_for_kbit_training(model)
lora_config = LoraConfig(
    r=config.LORA_R,
    lora_alpha=config.LORA_ALPHA,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_dropout=config.LORA_DROPOUT,
    bias="none",
    task_type="CAUSAL_LM"
)
model = get_peft_model(model, lora_config)

# 3. Load & Format Data
# (You will need to tweak this formatter based on the dataset you are loading)
def format_data(example):
    # GENERIC FORMATTER - Adjust for your specific JSON structure
    # For MAIAdeen: uses 'question' and 'response'
    # For GSM8K: uses 'question' and 'answer'
    q = example.get('question') or example.get('instruction') or ""
    a = example.get('response') or example.get('answer') or example.get('output') or ""
    
    return {
        "input_ids": tokenizer(f"<|user|>\n{q}\n<|assistant|>\n{a}", truncation=True, max_length=1024)["input_ids"],
        "labels": tokenizer(f"<|user|>\n{q}\n<|assistant|>\n{a}", truncation=True, max_length=1024)["input_ids"]
    }

# Load primary dataset (Local JSON or HuggingFace)
if ".json" in DATASET_PATH:
    raw_data = load_dataset("json", data_files=DATASET_PATH, split="train")
else:
    raw_data = load_dataset(DATASET_PATH, "main", split="train") # Adjust config for HF datasets

# Load and oversample expert data (MAIAdeen)
if EXPERT_DATA_PATH and os.path.exists(EXPERT_DATA_PATH):
    expert_data = load_dataset("json", data_files=EXPERT_DATA_PATH, split="train")
    # Combine datasets with oversampling
    datasets_to_concat = [raw_data] + [expert_data] * OVERSAMPLE_FACTOR
    raw_data = concatenate_datasets(datasets_to_concat)

tokenized_data = raw_data.map(format_data, remove_columns=raw_data.column_names)

# 4. Train
trainer = Trainer(
    model=model,
    train_dataset=tokenized_data,
    args=TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=config.NUM_TRAIN_EPOCHS,
        per_device_train_batch_size=config.PER_DEVICE_TRAIN_BATCH_SIZE,
        gradient_accumulation_steps=config.GRADIENT_ACCUMULATION_STEPS,
        learning_rate=config.LEARNING_RATE,
        fp16=False,
        bf16=True,
        logging_steps=10,
        save_strategy="no",     # Just save at end
        report_to="none"
    ),
    data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8, padding=True)
)

print(f"Training Expert: {ADAPTER_NAME}...")
trainer.train()
model.save_pretrained(OUTPUT_DIR)
print(f"Expert Saved to {OUTPUT_DIR}")