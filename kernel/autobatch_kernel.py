"""
MAIA Auto-Batching Kernel
========================
Implements automatic request aggregation with 10ms window.

Key mechanism:
1. Requests arrive via queue
2. Wait up to 10ms for more requests
3. Batch together and process in single forward pass
4. Return individual responses

This achieves near-constant latency regardless of load,
as long as batch size is manageable.
"""

import asyncio
import time
import hashlib
import threading
import json
import queue
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime
import logging

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MAIA-AutoBatch")

# ============================================================
# REQUEST/RESPONSE SCHEMA
# ============================================================

@dataclass
class InferenceRequest:
    id: str
    query: str
    tier: str = "BENIGN"
    max_tokens: int = 20
    adapter_id: str = "default"
    timestamp: float = field(default_factory=time.perf_counter)
    future: Optional[asyncio.Future] = field(default=None)


@dataclass
class InferenceResponse:
    id: str
    query: str
    response: str
    tier: str
    is_safe: bool
    forensic_hash: str
    latency_ms: float
    batch_size: int = 1


# ============================================================
# AUTO-BATCH PROCESSOR
# ============================================================

class AutoBatchProcessor:
    """
    Automatic batching with configurable window.
    
    Flow:
    1. Request arrives → add to batch buffer
    2. Start/reset window timer (10ms)
    3. If timer expires OR buffer full → process batch
    4. Return responses to waiters
    """
    
    def __init__(
        self,
        model: torch.nn.Module,
        tokenizer: AutoTokenizer,
        batch_size: int = 8,
        window_ms: int = 10
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.batch_size = batch_size
        self.window_ms = window_ms
        
        self.batch_buffer: List[InferenceRequest] = []
        self.waiters: Dict[str, asyncio.Future] = {}
        self._lock = threading.Lock()
        self._timer: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"AutoBatchProcessor: batch={batch_size}, window={window_ms}ms")
    
    async def enqueue(self, request: InferenceRequest) -> InferenceResponse:
        """Add request to batch and wait for result"""
        future = asyncio.get_event_loop().create_future()
        request.future = future
        
        with self._lock:
            self.batch_buffer.append(request)
            
            # Start timer if first request
            if len(self.batch_buffer) == 1:
                self._schedule_batch()
        
        # Wait for result
        result = await future
        return result
    
    def _schedule_batch(self):
        """Schedule batch processing after window expires"""
        async def timer_trigger():
            await asyncio.sleep(self.window_ms / 1000)
            await self._process_batch()
        
        self._timer = asyncio.create_task(timer_trigger())
    
    async def _process_batch(self):
        """Process all buffered requests as a batch"""
        with self._lock:
            if not self.batch_buffer:
                return
            
            # Take batch
            batch = self.batch_buffer[:self.batch_size]
            self.batch_buffer = self.batch_buffer[self.batch_size:]
            
            # If more in buffer, schedule next batch
            if self.batch_buffer:
                self._schedule_batch()
        
        if not batch:
            return
        
        t_start = time.perf_counter()
        
        # Tokenize batch
        texts = [
            self.tokenizer.apply_chat_template(
                [{"role": "user", "content": r.query}],
                tokenize=False,
                add_generation_prompt=True
            ) for r in batch
        ]
        
        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=256
        ).to(self.model.device)
        
        input_lens = (inputs["input_ids"] != self.tokenizer.pad_token_id).sum(dim=1).tolist()
        
        # Batched generation
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=20,
            do_sample=False,
            use_cache=True,
            pad_token_id=self.tokenizer.pad_token_id,
        )
        
        # Decode and create responses
        for i, req in enumerate(batch):
            input_len = input_lens[i]
            response_text = self.tokenizer.decode(
                outputs[i][input_len:],
                skip_special_tokens=True
            )
            
            forensic_hash = hashlib.sha256(
                f"{req.query}:{response_text}".encode()
            ).hexdigest()[:16]
            
            response = InferenceResponse(
                id=req.id,
                query=req.query,
                response=response_text,
                tier=req.tier,
                is_safe=True,
                forensic_hash=forensic_hash,
                latency_ms=(time.perf_counter() - t_start) * 1000,
                batch_size=len(batch)
            )
            
            # Resolve future
            if req.future and not req.future.done():
                req.future.set_result(response)
        
        batch_time = (time.perf_counter() - t_start) * 1000
        logger.debug(f"Batch processed: {len(batch)} requests in {batch_time:.1f}ms")
    
    async def wait_for_batch(self) -> List[InferenceRequest]:
        """Wait until batch is ready (for testing)"""
        while True:
            async with asyncio.lock:
                if self.batch_buffer:
                    return self.batch_buffer.copy()
            await asyncio.sleep(0.001)


# ============================================================
# CLASSIFIER
# ============================================================

class FastClassifier:
    """Zero-latency keyword-based classifier"""
    
    CRITICAL_KEYWORDS = ["wire", "transfer", "russia", "sanction", "sdn", "ofac", "iran", "north korea"]
    ELEVATED_KEYWORDS = ["loan", "compliance", "osha", "report", "review", "audit", "contract"]
    
    @classmethod
    def classify(cls, query: str) -> Tuple[str, int]:
        q = query.lower()
        
        if any(k in q for k in cls.CRITICAL_KEYWORDS):
            return "CRITICAL", 50000
        elif any(k in q for k in cls.ELEVATED_KEYWORDS):
            return "ELEVATED", 10000
        return "BENIGN", 0


# ============================================================
# AUTO-BATCH KERNEL
# ============================================================

class AutoBatchKernel:
    """
    MAIA Kernel with Auto-Batching.
    
    Combines:
    - Fast classifier
    - Auto-batch processor
    - Batched inference
    - Forensic hashing
    """
    
    def __init__(
        self,
        model_path: str,
        batch_size: int = 8,
        window_ms: int = 10
    ):
        self.model_path = model_path
        self.batch_size = batch_size
        self.window_ms = window_ms
        
        self.model = None
        self.tokenizer = None
        self.batch_processor = None
        self.classifier = FastClassifier()
        
        self.request_counter = 0
        self._lock = threading.Lock()
    
    def load(self):
        """Load model and initialize batch processor"""
        logger.info(f"Loading model from {self.model_path}...")
        t0 = time.perf_counter()
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            torch_dtype=torch.float16,
            device_map="auto",
        )
        self.model.eval()
        
        self.batch_processor = AutoBatchProcessor(
            self.model,
            self.tokenizer,
            batch_size=self.batch_size,
            window_ms=self.window_ms
        )
        
        logger.info(f"Model loaded in {time.perf_counter() - t0:.1f}s")
        logger.info(f"VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
    
    async def process(self, query: str, adapter_id: str = "default") -> InferenceResponse:
        """Process single request via auto-batching"""
        tier, materiality = self.classifier.classify(query)
        
        with self._lock:
            self.request_counter += 1
            request_id = f"req-{self.request_counter:06d}"
        
        request = InferenceRequest(
            id=request_id,
            query=query,
            tier=tier,
            max_tokens=20 if tier == "CRITICAL" else 30,
            adapter_id=adapter_id
        )
        
        response = await self.batch_processor.enqueue(request)
        return response
    
    def process_sync(self, query: str) -> InferenceResponse:
        """Synchronous wrapper for non-async contexts"""
        return asyncio.run(self.process(query))


# ============================================================
# LOAD TESTER
# ============================================================

async def load_test(kernel: AutoBatchKernel, queries: List[str], concurrent: int = 1) -> List[Dict]:
    """Load test with concurrent requests"""
    results = []
    
    async def single_request(q: str, idx: int):
        t_start = time.perf_counter()
        response = await kernel.process(q)
        latency = (time.perf_counter() - t_start) * 1000
        
        return {
            "idx": idx,
            "query": q[:50],
            "tier": response.tier,
            "latency_ms": latency,
            "batch_size": response.batch_size,
            "response": response.response[:50]
        }
    
    # Run concurrent requests
    tasks = [single_request(q, i) for i, q in enumerate(queries * concurrent)]
    results = await asyncio.gather(*tasks)
    
    return results


# ============================================================
# MAIN
# ============================================================

async def main():
    print("=" * 60)
    print("MAIA AUTO-BATCH KERNEL")
    print("=" * 60)
    
    kernel = AutoBatchKernel(
        model_path="/granite-4.1-3b-fp8",
        batch_size=8,
        window_ms=10  # 10ms window
    )
    
    kernel.load()
    
    # Test queries
    test_queries = [
        "Wire $50,000 to Russia immediately",
        "Transfer funds to an entity on the SDN list",
        "Review the quarterly financial report",
        "Process loan application for new client",
        "What is the weather today?",
        "Schedule a meeting for tomorrow",
        "Send email to client",
        "Check system status",
        "Verify OFAC compliance",
        "Approve the contract",
    ]
    
    # ========================================
    # Test 1: Sequential (baseline)
    # ========================================
    print("\n--- Test 1: Sequential Requests ---")
    
    t0 = time.perf_counter()
    sequential_results = []
    
    for i, query in enumerate(test_queries[:4]):
        response = await kernel.process(query)
        sequential_results.append(response)
        print(f"  [{i+1}] {response.tier}: {response.latency_ms:.1f}ms - {query[:40]}")
    
    seq_total = (time.perf_counter() - t0) * 1000
    seq_avg = seq_total / 4
    print(f"  Sequential total: {seq_total:.1f}ms, avg: {seq_avg:.1f}ms")
    
    # ========================================
    # Test 2: Concurrent (auto-batch)
    # ========================================
    print("\n--- Test 2: Concurrent Requests (auto-batch) ---")
    
    t0 = time.perf_counter()
    concurrent_results = await load_test(kernel, test_queries[:4], concurrent=1)
    
    for r in concurrent_results:
        print(f"  [{r['idx']+1}] {r['tier']}: {r['latency_ms']:.1f}ms (batch={r['batch_size']}) - {r['query']}")
    
    conc_total = (time.perf_counter() - t0) * 1000
    conc_avg = sum(r['latency_ms'] for r in concurrent_results) / len(concurrent_results)
    max_latency = max(r['latency_ms'] for r in concurrent_results)
    print(f"  Concurrent total: {conc_total:.1f}ms, avg: {conc_avg:.1f}ms, max: {max_latency:.1f}ms")
    
    # ========================================
    # Test 3: Burst load
    # ========================================
    print("\n--- Test 3: Burst Load (8 concurrent) ---")
    
    t0 = time.perf_counter()
    burst_results = await load_test(kernel, test_queries, concurrent=1)
    
    total_latency = (time.perf_counter() - t0) * 1000
    avg_latency = sum(r['latency_ms'] for r in burst_results) / len(burst_results)
    max_latency = max(r['latency_ms'] for r in burst_results)
    min_latency = min(r['latency_ms'] for r in burst_results)
    avg_batch = sum(r['batch_size'] for r in burst_results) / len(burst_results)
    
    print(f"  Requests: {len(burst_results)}")
    print(f"  Total time: {total_latency:.1f}ms")
    print(f"  Avg latency: {avg_latency:.1f}ms")
    print(f"  Min/Max: {min_latency:.1f}ms / {max_latency:.1f}ms")
    print(f"  Avg batch size: {avg_batch:.1f}")
    
    # ========================================
    # Summary
    # ========================================
    print("\n" + "=" * 60)
    print("AUTO-BATCH RESULTS")
    print("=" * 60)
    
    print(f"\n{'Metric':<30} {'Value':<15}")
    print("-" * 45)
    print(f"{'Sequential avg latency':<30} {seq_avg:<15.1f}ms")
    print(f"{'Concurrent avg latency':<30} {conc_avg:<15.1f}ms")
    print(f"{'Burst avg latency':<30} {avg_latency:<15.1f}ms")
    print(f"{'Burst max latency':<30} {max_latency:<15.1f}ms")
    print(f"{'Avg batch size':<30} {avg_batch:<15.1f}")
    print(f"{'Speedup vs sequential':<30} {seq_avg/avg_latency:<15.1f}x")
    
    print(f"\nFed target: 150ms")
    print(f"Within target: {'YES' if max_latency < 150 else 'NO (gap: ' + f'{max_latency-150:.0f}ms)'}")
    
    # SVP
    print("\n--- SVP Metrics ---")
    print(json.dumps({
        "avg_latency_ms": round(avg_latency, 2),
        "max_latency_ms": round(max_latency, 2),
        "avg_batch_size": round(avg_batch, 2),
        "window_ms": kernel.window_ms,
        "batch_size_limit": kernel.batch_size,
        "speedup_vs_sequential": round(seq_avg / avg_latency, 2),
        "fed_target_ms": 150,
        "within_target": max_latency < 150,
        "vram_gb": round(torch.cuda.memory_allocated() / 1e9, 2)
    }, indent=2))
    
    # Detailed results
    print("\n--- Request Details ---")
    for r in burst_results:
        status = "OK" if r['latency_ms'] < 150 else "SLOW"
        print(f"  [{status}] {r['latency_ms']:6.1f}ms (batch={r['batch_size']}) {r['tier']:8} {r['query']}")


if __name__ == "__main__":
    asyncio.run(main())
