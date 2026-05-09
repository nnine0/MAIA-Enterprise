"""
MAIA Inference Test - Granite 3B FP8 (HuggingFace)
==================================================
"""

import torch
import time
from transformers import AutoTokenizer, AutoModelForCausalLM

print("=== MAIA Inference Test - Granite 3B ===\n")

MODEL_PATH = "/granite-4.1-3b-fp8"

print(f"Loading model from {MODEL_PATH}...")
t0 = time.perf_counter()

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
print(f"Tokenizer loaded in {time.perf_counter() - t0:.1f}s")

model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    device_map="auto",
    torch_dtype=torch.float16,
)
print(f"Model loaded in {time.perf_counter() - t0:.1f}s")

print(f"VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

# Test
messages = [
    {"role": "system", "content": "You are a compliance assistant."},
    {"role": "user", "content": "Is it safe to wire $50,000 to Russia?"}
]

text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
print(f"\n--- Prompt ---")
print(text[:300])
print("---")

inputs = tokenizer(text, return_tensors="pt").to(model.device)
input_len = inputs["input_ids"].shape[-1]

print(f"Input tokens: {input_len}")
print("Generating...")

t_start = time.perf_counter()

outputs = model.generate(
    **inputs,
    max_new_tokens=100,
    do_sample=False,
)
gen_time = time.perf_counter() - t_start

tokens_generated = len(outputs[0]) - input_len
response = tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True)

print(f"\n--- Response ({gen_time:.2f}s, {tokens_generated} tokens, {tokens_generated/max(0.01,gen_time):.1f} tok/s) ---")
print(response)

del model
torch.cuda.empty_cache()
print("\nDone.")
