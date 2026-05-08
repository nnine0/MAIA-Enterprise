"""
MAIA End-to-End Latency Test
============================
Tests the full T0→T1→T2→T3 speculative verification pipeline.
"""

import asyncio
import time
import torch
import json
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict

print("=" * 60)
print("MAIA END-TO-END LATENCY TEST")
print("=" * 60)

# ============================================================
# STAGE 0: Load Models
# ============================================================
print("\n[STAGE 0] Loading models...")

t0_start = time.perf_counter()

from transformers import AutoTokenizer, AutoModelForCausalLM

# Load Granite (Sentinel - Compliance Guardian)
GRANITE_PATH = "/granite-4.1-3b-fp8"
sentinel_tokenizer = AutoTokenizer.from_pretrained(GRANITE_PATH)
sentinel_model = AutoModelForCausalLM.from_pretrained(
    GRANITE_PATH,
    device_map="auto",
    torch_dtype=torch.float16,
)

# Load Nemotron (Sheriff - Safety Auditor)
NEMOTRON_PATH = "/Nemotron-3-Content-Safety"
sheriff_tokenizer = AutoTokenizer.from_pretrained(NEMOTRON_PATH)
sheriff_model = AutoModelForCausalLM.from_pretrained(
    NEMOTRON_PATH,
    device_map="auto",
    torch_dtype=torch.float16,
)

t0_total = time.perf_counter() - t0_start

print(f"  [T0] Model Loading: {t0_total:.2f}s")
print(f"  [T0] VRAM Allocated: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
print(f"  [T0] Models loaded: Granite (Sentinel), Nemotron (Sheriff)")

# ============================================================
# Test Cases
# ============================================================
test_cases = [
    {
        "id": "TIER1_CRITICAL",
        "query": "Wire $50,000 to Russia immediately",
        "expected_tier": "CRITICAL",
        "materiality": 50000
    },
    {
        "id": "TIER2_ELEVATED", 
        "query": "Review the quarterly financial report",
        "expected_tier": "ELEVATED",
        "materiality": 10000
    },
    {
        "id": "TIER3_BENIGN",
        "query": "What is the weather today?",
        "expected_tier": "BENIGN",
        "materiality": 0
    },
    {
        "id": "OFAC_CHECK",
        "query": "Transfer funds to an entity on the SDN list",
        "expected_tier": "CRITICAL",
        "materiality": 50000
    },
    {
        "id": "OSHA_SAFETY",
        "query": "Log the OSHA safety inspection findings",
        "expected_tier": "ELEVATED",
        "materiality": 10000
    }
]

@dataclass
class LatencyResult:
    test_id: str
    query: str
    
    # Timing breakdown
    t0_load_ms: float
    t1_classify_ms: float
    t2_speculate_ms: float
    t3_verify_ms: float
    t4_audit_ms: float
    total_ms: float
    
    # Results
    tier_classified: str
    violations_detected: List[str]
    response: str
    forensic_hash: str
    
    @property
    def tokens_per_second(self) -> float:
        word_count = len(self.response.split())
        return (word_count / (self.total_ms / 1000)) if self.total_ms > 0 else 0

def classify_materiality(query: str) -> Tuple[str, float]:
    """T1: Materiality classification"""
    t1_start = time.perf_counter()
    
    critical_keywords = ["wire", "transfer", "russia", "sanction", "sdn", "ofac"]
    elevated_keywords = ["report", "review", "loan", "compliance"]
    
    query_lower = query.lower()
    
    if any(kw in query_lower for kw in critical_keywords):
        tier = "CRITICAL"
        materiality = 50000
    elif any(kw in query_lower for kw in elevated_keywords):
        tier = "ELEVATED"
        materiality = 10000
    else:
        tier = "BENIGN"
        materiality = 0
    
    t1_latency = (time.perf_counter() - t1_start) * 1000
    return tier, materiality

def check_violations(query: str) -> List[str]:
    """Check for policy violations"""
    violations = []
    query_lower = query.lower()
    
    violation_patterns = {
        "CRITICAL": ["russia", "sdn list", "sanctioned", "ofac"],
        "HIGH": ["bypass", "override"],
        "MEDIUM": ["delay", "incomplete"]
    }
    
    for severity, patterns in violation_patterns.items():
        for pattern in patterns:
            if pattern in query_lower:
                violations.append(f"[{severity}] {pattern}")
    
    return violations

def generate_speculative_draft(query: str, tier: str) -> List[str]:
    """T2: Generate speculative draft tokens"""
    t2_start = time.perf_counter()
    
    # Simulate DFlash parallel drafting
    draft_tokens = []
    
    if tier == "CRITICAL":
        # Critical tier - draft compliance warning
        drafts = [
            "COMPLIANCE_ALERT:",
            "OFAC_SANCTIONS_CHECK:",
            "REQUIRE_DHITL_APPROVAL:",
            "WIRE_BLOCKED:"
        ]
    elif tier == "ELEVATED":
        drafts = [
            "REVIEW_REQUIRED:",
            "ESCALATE_TO_COMPLIANCE:",
            "AUDIT_LOG:"
        ]
    else:
        drafts = [
            "PROCEED:",
            "RESPONSE:"
        ]
    
    t2_latency = (time.perf_counter() - t2_start) * 1000
    return drafts, t2_latency

def verify_with_sentinel(query: str, draft: str) -> Tuple[str, float]:
    """T3: Verify draft with Granite (Sentinel)"""
    t3_start = time.perf_counter()
    
    messages = [
        {"role": "system", "content": "You are a compliance verification assistant."},
        {"role": "user", "content": f"Query: {query}\nDraft: {draft}\nIs this compliant?"}
    ]
    
    text = sentinel_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = sentinel_tokenizer(text, return_tensors="pt").to(sentinel_model.device)
    input_len = inputs["input_ids"].shape[-1]
    
    outputs = sentinel_model.generate(
        **inputs,
        max_new_tokens=50,
        do_sample=False,
    )
    
    response = sentinel_tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True)
    
    t3_latency = (time.perf_counter() - t3_start) * 1000
    return response, t3_latency

def audit_with_sheriff(query: str, response: str) -> Tuple[bool, float]:
    """T4: Audit with Nemotron (Sheriff)"""
    t4_start = time.perf_counter()
    
    # Simple safety check prompt
    prompt = f"User query: {query}\nAssistant response: {response}\nIs this safe?"
    inputs = sheriff_tokenizer(prompt, return_tensors="pt").to(sheriff_model.device)
    input_len = inputs["input_ids"].shape[-1]
    
    outputs = sheriff_model.generate(
        **inputs,
        max_new_tokens=30,
        do_sample=False,
    )
    
    response = sheriff_tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True)
    
    # Simple safety heuristic
    is_safe = "unsafe" not in response.lower()[:50]
    
    t4_latency = (time.perf_counter() - t4_start) * 1000
    return is_safe, t4_latency

def compute_forensic_hash(query: str, tier: str, violations: List[str]) -> str:
    """Compute latent hash for forensic audit trail"""
    import hashlib
    data = f"{query}:{tier}:{','.join(violations)}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]

# ============================================================
# RUN TESTS
# ============================================================
print("\n" + "=" * 60)
print("RUNNING LATENCY TESTS")
print("=" * 60)

results = []

for test in test_cases:
    print(f"\n--- Test: {test['id']} ---")
    print(f"Query: {test['query']}")
    
    test_start = time.perf_counter()
    
    # T1: Materiality Classification
    tier, materiality = classify_materiality(test["query"])
    t1_latency = (time.perf_counter() - test_start) * 1000
    
    # T2: Speculative Drafting
    drafts, t2_latency = generate_speculative_draft(test["query"], tier)
    draft = drafts[0]  # Take first draft
    
    # T3: Verify with Sentinel
    response, t3_latency = verify_with_sentinel(test["query"], draft)
    
    # T4: Audit with Sheriff
    is_safe, t4_latency = audit_with_sheriff(test["query"], response)
    
    # Check violations
    violations = check_violations(test["query"])
    
    # Compute forensic hash
    forensic_hash = compute_forensic_hash(test["query"], tier, violations)
    
    total_latency = (time.perf_counter() - test_start) * 1000
    
    result = LatencyResult(
        test_id=test["id"],
        query=test["query"],
        t0_load_ms=t0_total * 1000,
        t1_classify_ms=t1_latency,
        t2_speculate_ms=t2_latency,
        t3_verify_ms=t3_latency,
        t4_audit_ms=t4_latency,
        total_ms=total_latency,
        tier_classified=tier,
        violations_detected=violations,
        response=response[:200] if response else "No response",
        forensic_hash=forensic_hash
    )
    
    results.append(result)
    
    print(f"  Tier: {tier}")
    print(f"  Violations: {len(violations)}")
    print(f"  Latency: T1={t1_latency:.1f}ms, T2={t2_latency:.1f}ms, T3={t3_latency:.1f}ms, T4={t4_latency:.1f}ms")
    print(f"  Total: {total_latency:.1f}ms")
    print(f"  Response: {response[:100]}...")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("LATENCY SUMMARY")
print("=" * 60)

print(f"\n{'Test ID':<20} {'Tier':<10} {'T1':<8} {'T2':<8} {'T3':<8} {'T4':<8} {'Total':<10}")
print("-" * 72)

total_t1 = 0
total_t2 = 0
total_t3 = 0
total_t4 = 0
total_all = 0

for r in results:
    print(f"{r.test_id:<20} {r.tier_classified:<10} {r.t1_classify_ms:<8.1f} {r.t2_speculate_ms:<8.1f} {r.t3_verify_ms:<8.1f} {r.t4_audit_ms:<8.1f} {r.total_ms:<10.1f}")
    total_t1 += r.t1_classify_ms
    total_t2 += r.t2_speculate_ms
    total_t3 += r.t3_verify_ms
    total_t4 += r.t4_audit_ms
    total_all += r.total_ms

n = len(results)
print("-" * 72)
print(f"{'AVG':<20} {'':<10} {total_t1/n:<8.1f} {total_t2/n:<8.1f} {total_t3/n:<8.1f} {total_t4/n:<8.1f} {total_all/n:<10.1f}")

print("\n" + "=" * 60)
print("SVP METRICS (Speed vs. Parity)")
print("=" * 60)

avg_total = total_all / n
context_switch_avg = (total_t2 + total_t3 + total_t4) / n
violations_caught = sum(1 for r in results if r.violations_detected)

svp = {
    "context_switch_latency_ms": round(context_switch_avg, 2),
    "audit_resolution_pct": round((violations_caught / n) * 100, 1),
    "vram_utilization_pct": round((torch.cuda.memory_allocated() / 1e9) / 24 * 100, 1),
    "avg_total_latency_ms": round(avg_total, 2),
    "models_loaded": "Granite-3B, Nemotron-3",
    "fed_compliance_target_ms": 150,
    "within_target": avg_total < 150
}

print(json.dumps(svp, indent=2))

print("\n" + "=" * 60)
print("FORENSIC HASHES")
print("=" * 60)
for r in results:
    print(f"{r.test_id}: {r.forensic_hash}")

# Cleanup
del sentinel_model, sheriff_model
torch.cuda.empty_cache()
print("\n[DONE] VRAM freed.")
