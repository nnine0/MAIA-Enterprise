"""
Benchmark: Granite Sentinel + Gemma4 Base Model
================================================
Measures per-component latency with:
  - Granite Sentinel (real, /models/sentinel) — fast_pass / full generation
  - Gemma4 E4B-it (random-weight benchmark) — forward pass / generation per-token
  - No Nemotron Sheriff (mocked)
"""

import asyncio
import time
import torch
import statistics

# ─── Helpers ────────────────────────────────────────────────────────────────

def _device(m):
    return next(m.parameters()).device

def elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000

def fmt(label: str, times: list) -> str:
    avg = statistics.mean(times)
    mn = min(times)
    mx = max(times)
    return f"  {label:45s} {avg:>8.1f} ms  (min={mn:.1f}, max={mx:.1f})"

# ─── Main Benchmark ─────────────────────────────────────────────────────────

async def main():
    print("=" * 75)
    print("  Granite Sentinel + Gemma4 E4B-it — Per-Component Latency")
    print("=" * 75)

    # ── 1. Load via ModelEngine ────────────────────────────────────────────
    print("\n[1/5] Loading via ModelEngine...")
    from app.engine import ModelEngine
    from app.airlock_gateway import Verdict

    engine = ModelEngine()
    engine.load_all()
    granite = engine.granite
    gemma4 = engine.gemma
    tokenizer = engine.gemma_tokenizer

    vram_granite = torch.cuda.memory_allocated() / 1e9
    print(f"  VRAM after loading: {vram_granite:.2f} GB")

    # ── 3. Warmup ───────────────────────────────────────────────────────────
    print("\n[3/5] Warmup (5 iterations each)...")
    prompt = "What is the weather today?"

    # Warmup Granite
    for _ in range(5):
        await granite.fast_pass(prompt)
        await granite.audit(prompt)

    # Warmup Gemma4
    inputs = tokenizer(prompt, return_tensors="pt")
    input_ids = inputs["input_ids"].to(_device(gemma4))
    for _ in range(5):
        await engine.gemma_forward(input_ids)
    print("  Warmup complete")

    # ── 4. Component Benchmarks ─────────────────────────────────────────────
    print("\n[4/5] Benchmarking (10 runs each with CUDA sync)...")
    print()

    # 4a. Granite fast_pass (single forward pass, no generation)
    fp_times = []
    for _ in range(10):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        await granite.fast_pass(prompt)
        torch.cuda.synchronize()
        fp_times.append(elapsed_ms(t0))
    print(fmt("Granite Sentinel — fast_pass (logit only)", fp_times))

    # 4b. Granite full audit (forward + 10 token generation)
    ga_times = []
    for _ in range(10):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        await granite.audit(prompt)
        torch.cuda.synchronize()
        ga_times.append(elapsed_ms(t0))
    print(fmt("Granite Sentinel — full audit (10 token gen)", ga_times))

    # 4c. Gemma4 forward pass (single token)
    gf_times = []
    for _ in range(10):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        await engine.gemma_forward(input_ids)
        torch.cuda.synchronize()
        gf_times.append(elapsed_ms(t0))
    print(fmt("Gemma4 — forward pass (10 tokens)", gf_times))

    # 4d. Gemma4 forward pass with larger prompt (64 tokens for prefill comparison)
    inputs_64 = tokenizer(
        "This is a longer prompt to test prefill latency. " * 4,
        return_tensors="pt",
    )
    input_ids_64 = inputs_64["input_ids"].to(_device(gemma4))
    n_tok_64 = input_ids_64.shape[-1]

    gf64_times = []
    for _ in range(10):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        await engine.gemma_forward(input_ids_64)
        torch.cuda.synchronize()
        gf64_times.append(elapsed_ms(t0))
    print(fmt(f"Gemma4 — forward pass ({n_tok_64} tokens)", gf64_times))

    # 4e. Gemma4 per-token generation (single autoregressive step simulate)
    # Measure: one forward pass with a single new token + KV reuse
    # Without KV cache: just measure forward pass time for 1 token
    single_token = torch.randint(0, 100, (1, 1), device=_device(gemma4))
    g_gen_times = []
    for _ in range(10):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        with torch.inference_mode():
            gemma4(single_token)
        torch.cuda.synchronize()
        g_gen_times.append(elapsed_ms(t0))
    print(fmt("Gemma4 — per-token step (1 token)", g_gen_times))

    # 4f. Sequential pipeline: Granite fast_pass → if PASS, Gemma4 forward
    pipe_times = []
    for _ in range(10):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        fp = await granite.fast_pass(prompt)
        if fp is not None and fp.verdict == Verdict.PASS:
            await engine.gemma_forward(input_ids)
        torch.cuda.synchronize()
        pipe_times.append(elapsed_ms(t0))
    print(fmt("Sequential pipeline: Granite FP → Gemma4 fwd", pipe_times))

    # 4g. Parallel: Granite fast_pass + Gemma4 forward pass concurrently
    par_times = []
    for _ in range(10):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        fp_task = asyncio.create_task(granite.fast_pass(prompt))
        gf_task = asyncio.create_task(engine.gemma_forward(input_ids))
        await asyncio.gather(fp_task, gf_task)
        torch.cuda.synchronize()
        par_times.append(elapsed_ms(t0))
    print(fmt("Parallel: Granite FP ∥ Gemma4 fwd", par_times))

    # 4h. Full generate: 64 tokens on Gemma4 (estimate from per-token cost × 64)
    n_gen_tokens = 64
    gen_64_estimate = statistics.mean(g_gen_times) * n_gen_tokens
    print(f"  {'Gemma4 — estimated 64-token generate':45s} {gen_64_estimate:>8.1f} ms  "
          f"(={statistics.mean(g_gen_times):.1f}ms × {n_gen_tokens})")

    # ── 5. Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 75)
    print("  LATENCY BREAKDOWN (Granite + Gemma4, no Sheriff)")
    print("=" * 75)
    print()

    # Key numbers
    fp_avg = statistics.mean(fp_times)
    ga_avg = statistics.mean(ga_times)
    gf_avg = statistics.mean(gf_times)
    gt_avg = statistics.mean(g_gen_times)
    par_avg = statistics.mean(par_times)
    pipe_avg = statistics.mean(pipe_times)
    gen64 = gt_avg * 64

    print(f"  {'Component':45s} {'Latency':>10s}  {'Note'}")
    print(f"  {'─'*45}  {'─'*10}  {'─'*20}")
    print(f"  {'Granite Sentinel — fast_pass':45s} {fp_avg:>8.1f}ms  single forward pass, zero gen")
    print(f"  {'Granite Sentinel — full audit':45s} {ga_avg:>8.1f}ms  10-token generation (fallback)")
    print(f"  {'Gemma4 E4B-it — forward pass (10 tok)':45s} {gf_avg:>8.1f}ms  42 layers, GQA, SwiGLU")
    print(f"  {'Gemma4 E4B-it — per-token step':45s} {gt_avg:>8.1f}ms  autoregressive decode")
    print(f"  {'Gemma4 E4B-it — 64-token generate':45s} {gen64:>8.1f}ms  estimated (per-token × 64)")
    print(f"  {'Sequential pipeline (FP → Gen)':45s} {pipe_avg:>8.1f}ms  Granite FP → Gemma4 fwd")
    print(f"  {'Parallel pipeline (FP ∥ Gen)':45s} {par_avg:>8.1f}ms  both concurrently")
    print()
    vram_info = engine.get_vram_info()
    print(f"  {'VRAM peak':45s} {vram_info['peak_gb']:>7.2f} GB  (of 24 GB)")
    print(f"  {'VRAM model params':45s} {vram_info['allocated_gb']:>7.2f} GB  (Granite + Gemma4)")
    print(f"  {'Headroom':45s} {24 - vram_info['peak_gb']:>7.2f} GB")
    print()
    print("=" * 75)

if __name__ == "__main__":
    asyncio.run(main())
