"""
MAIA Inference Test - Nemotron-3 Content Safety
===============================================
"""

import torch
import time
from transformers import AutoTokenizer, AutoModelForCausalLM

print("=== MAIA Inference Test ===\n")

MODEL_PATH = "/Nemotron-3-Content-Safety"

print(f"Loading model from {MODEL_PATH}...")
t0 = time.perf_counter()

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
print(f"Tokenizer loaded in {time.perf_counter() - t0:.1f}s")

model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    torch_dtype=torch.float16,
    device_map="auto",
)
print(f"Model loaded in {time.perf_counter() - t0:.1f}s")

print(f"VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

# Simple text completion prompt
prompt = "Is it safe to wire $50,000 to Russia?"
print(f"\n--- Prompt ---\n{prompt}\n---")

inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
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

print("\n=== Now testing Granite ===\n")

# Test Granite
MODEL_PATH2 = "/granite-4.1-3b-fp8"
tokenizer2 = AutoTokenizer.from_pretrained(MODEL_PATH2)
print(f"Granite loaded")

model2 = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH2,
    torch_dtype=torch.float16,
    device_map="auto",
    load_in_8bit=True,
)
print(f"VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

text2 = tokenizer2.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs2 = tokenizer2(text2, return_tensors="pt").to(model2.device)
input_len2 = inputs2["input_ids"].shape[-1]

t_start2 = time.perf_counter()
outputs2 = model2.generate(**inputs2, max_new_tokens=100, do_sample=False)
gen_time2 = time.perf_counter() - t_start2

tokens2 = len(outputs2[0]) - input_len2
response2 = tokenizer2.decode(outputs2[0][input_len2:], skip_special_tokens=True)

print(f"\n--- Granite Response ({gen_time2:.2f}s, {tokens2} tokens) ---")
print(response2)

del model2
torch.cuda.empty_cache()
print("\nDone.")
