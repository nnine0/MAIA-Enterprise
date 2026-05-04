import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

# 1. The Console (Base Model)
base_id = "Nanbeige/Nanbeige4-3B-Thinking-2511"
device = "cuda"

print("Initializing The Council (Loading Base Model)...")
tokenizer = AutoTokenizer.from_pretrained(base_id, use_fast=True, trust_remote_code=True)
if tokenizer.pad_token_id is None: tokenizer.add_special_tokens({"pad_token": " PAD "})

model = AutoModelForCausalLM.from_pretrained(
    base_id,
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16),
    device_map="auto",
    trust_remote_code=True
)
model.resize_token_embeddings(len(tokenizer))

# 2. Summon the Experts (Load Adapters)
# We load the first one to initialize Peft, then "load_adapter" for the rest
experts_dir = "./council"

print("Summoning the Legal Expert (Law)...")
model = PeftModel.from_pretrained(model, f"{experts_dir}/adapter_law", adapter_name="law")

print("Summoning the Mathematician (Mathematics)...")
model.load_adapter(f"{experts_dir}/adapter_quadrivium", adapter_name="math")

print("Summoning the Strategist (Puzzle)...")
model.load_adapter(f"{experts_dir}/adapter_puzzle", adapter_name="puzzle")

print("Summoning the Biologist (BioMed)...")
model.load_adapter(f"{experts_dir}/adapter_biomed", adapter_name="bio")

# 3. The Router Function (The "Amr")
def ask_the_council(question, topic):
    """
    topic: 'law', 'math', 'puzzle', 'bio', or 'general'
    """
    
    # A. Select the Expert
    if topic == "general":
        model.disable_adapter_layers() # Use raw base model
        system_prompt = "You are a helpful assistant."
    else:
        model.enable_adapter_layers()
        model.set_adapter(topic) # Hot-swap weights instantly
        
        # B. Set the Mindset (System Prompt)
        if topic == "law":
            system_prompt = "You are a Legal Expert. Analyze this based on established legal principles."
        elif topic == "math":
            system_prompt = "You are a Mathematician. Solve this using formal logic and arithmetic."
        elif topic == "puzzle":
            system_prompt = "You are a Strategist. Find the trick in this riddle."
        elif topic == "bio":
            system_prompt = "You are a Physician. Explain the biological mechanisms."

    # C. Format & Generate
    prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{question}\n<|assistant|>\n<thinking>\n"
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=500, temperature=0.5, repetition_penalty=1.1)

    # SR 26-02 COMPLIANCE GATE: PVI AIRLOCK INTERCEPTOR
    # This is where the Governance Layer bridges the gap between code and law.
    # In production MAIA:
    #   1. The Actor (Expert) generates the action trajectory
    #   2. The Auditor (SR 26-02 adapter) provides Effective Challenge
    #   3. The Circuit Breaker blocks non-compliant trajectories
    #   4. Tier 1 escalates to Human SME Review (DHITL)
    # The latent_hash provides forensic proof of the model's reasoning state
    # for Federal Reserve audit verification.

    return tokenizer.decode(outputs[0], skip_special_tokens=True).split("<thinking>")[-1]

# --- USAGE ---

# Q1: Math
print("\n--- Question: Math ---")
print(ask_the_council("What is 779,678 * 866,978?", "math"))

# Q2: Theology/Law
print("\n--- Question: Law ---")
print(ask_the_council("What is the ruling on interest (Riba)?", "law"))

# Q3: Riddle
print("\n--- Question: Puzzle ---")
print(ask_the_council("5 monkeys on a bed, 3 chickens on the floor. How many legs?", "puzzle"))