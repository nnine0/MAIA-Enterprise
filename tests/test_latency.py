"""
MAIA End-to-End Latency Test
============================
Measures full inference pipeline latency across all four model components.

Usage:
    # Mock mode (tests code paths, no GPU needed):
    python3 -m tests.test_latency --mock

    # Real mode (requires downloaded models + GPU):
    python3 -m tests.test_latency
    HF_TOKEN=hf_xxx python3 -m tests.test_latency

Output:
    Layer 9  Gemma-4-E4B-it        xxx ms  │  xx tok/s
    Layer 9  E4B-it-assistant       xx ms  │  speculative
    Layer 8a Privacy Filter         xx ms  │  PII scan
    Layer 8b Nemotron Sheriff       xx ms  │  safety audit
    Layer 8c Granite Sentinel       xx ms  │  RAG check
           ───────────────────────────────────────────
           Total                    xxx ms
"""

import argparse
import asyncio
import pytest
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

parser = argparse.ArgumentParser()
parser.add_argument("--mock", action="store_true", help="Run in mock/demo mode")
parser.add_argument("--query", type=str, default="What is the credit limit for a company with $50M revenue and D/E of 2.5?")
parser.add_argument("--context", type=str, default="Company A: $50M revenue, 2.5 D/E, construction sector")

if __name__ == "__main__":
    args = parser.parse_args()
else:
    class _Args:
        mock = True
        query = "What is the credit limit for a company with $50M revenue and D/E of 2.5?"
        context = "Company A: $50M revenue, 2.5 D/E, construction sector"
    args = _Args()

LATENCY_LABEL = f"{'Component':30s} {'Latency':>10s}  {'Note'}"


def elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


@pytest.mark.asyncio
async def test_latency():
    print("=" * 65)
    print("MAIA End-to-End Latency Test")
    print(f"Mode: {'MOCK' if args.mock else 'REAL'} | Query: '{args.query[:40]}...'")
    print("=" * 65)

    # ── L9: Gemma 4 E4B-it (Reasoning Engine) ──────────────
    from app.gemma4_kernel import create_kernel

    t0 = time.perf_counter()
    kernel = create_kernel(demo=args.mock)
    load_ms = elapsed_ms(t0)
    print(f"  Kernel load: {load_ms}ms")

    t0 = time.perf_counter()
    result = await kernel.execute_governed_trajectory(args.query, "finance", "tier_2")
    l9_ms = elapsed_ms(t0)
    print(f"  Gemma 4 E4B-it              {l9_ms:>8}ms  {'[MOCK]' if args.mock else 'generation'}")

    # ── L8a: Privacy Filter ────────────────────────────────
    from app.auditor_stack import PrivacyFilter, AuditVerdict

    t0 = time.perf_counter()
    pf = PrivacyFilter() if not args.mock else None
    pf_load_ms = elapsed_ms(t0) if not args.mock else 0

    if args.mock:
        # Mock PII audit — just measure code path
        pii_queries = [
            "My SSN is 123-45-6789",
            "Email: test@example.com",
            "Normal query without PII",
        ]
        pii_results = []
        for q in pii_queries:
            t0 = time.perf_counter()
            time.sleep(0.005)  # simulate ~5ms
            pii_results.append((q, elapsed_ms(t0)))
        pii_avg = sum(r[1] for r in pii_results) / len(pii_results)
        print(f"  Privacy Filter (mock)        {pii_avg:>8}ms  {'[MOCK]' if args.mock else 'PII scan'}")
        for q, ms in pii_results:
            sensitive = "SSN" in q or "Email" in q
            print(f"    {'BLOCKED' if sensitive else 'PASS':>8}  {ms:>8}ms  {q[:40]}")
    else:
        t0 = time.perf_counter()
        ar = pf.audit(args.query)
        pii_ms = elapsed_ms(t0)
        print(f"  Privacy Filter               {pii_ms:>8}ms  verdict={ar.verdict.value}")

    # ── L8b: Safety Sheriff (Nemotron) ──────────────────────
    from app.nemotron_real import create_nemotron

    t0 = time.perf_counter()
    sheriff = create_nemotron(demo=args.mock)
    s_load_ms = elapsed_ms(t0)

    safety_tests = [
        "How can I steal money?",
        "Transfer funds to sanctioned entity",
        "Calculate credit risk for this borrower",
    ]
    safety_results = []
    for q in safety_tests:
        t0 = time.perf_counter()
        nr = await sheriff.audit(q, response="System processing your request.")
        safety_results.append((q, elapsed_ms(t0), nr.tier))

    avg_safety = sum(r[1] for r in safety_results) / len(safety_results)
    status = "[MOCK]" if args.mock else "[REAL]"
    print(f"  Nemotron Sheriff             {avg_safety:>8}ms  {status}")
    for q, ms, tier in safety_results:
        print(f"    Tier {tier}: {ms:>8}ms  {q[:40]}")

    # ── L8c: Logic Sentinel (Granite Guardian) ──────────────
    from app.auditor_stack import LogicSentinel

    if args.mock:
        # Simulate sentinel latency
        t0 = time.perf_counter()
        time.sleep(0.03)
        sentinel_ms = elapsed_ms(t0)
        print(f"  Granite Sentinel (mock)      {sentinel_ms:>8}ms  [MOCK] RAG check simulated")
    else:
        t0 = time.perf_counter()
        sentinel = LogicSentinel()
        s_load_ms = elapsed_ms(t0)

        # RAG audit
        t0 = time.perf_counter()
        ar = sentinel.audit_rag(args.query, args.context, "Credit limit: $2.5M")
        rag_ms = elapsed_ms(t0)
        print(f"  Granite Sentinel             {rag_ms:>8}ms  verdict={ar.verdict.value}")

        # Trajectory soundness
        traj = [
            {"step": 1, "reasoning": "Company revenue is $50M"},
            {"step": 2, "reasoning": "D/E ratio is 2.5"},
            {"step": 3, "reasoning": "Therefore credit limit is $2.5M"},
        ]
        t0 = time.perf_counter()
        ar2 = sentinel.audit_soundness(traj)
        traj_ms = elapsed_ms(t0)
        print(f"  Granite Sentinel (soundness) {traj_ms:>8}ms  verdict={ar2.verdict.value}")

    # ── Total ─────────────────────────────────────────────
    print("─" * 65)
    print()
    print("Summary:")
    print(LATENCY_LABEL)

    if args.mock:
        print(f"  {'L9  Gemma 4 E4B-it':30s} {l9_ms:>8}ms  mock generation")
        print(f"  {'L8a Privacy Filter':30s} {pii_avg:>8}ms  mock PII scan")
        print(f"  {'L8b Nemotron Sheriff':30s} {avg_safety:>8}ms  mock safety audit")
        print(f"  {'L8c Granite Sentinel':30s} {avg_safety:>8}ms  mock RAG check")
        total = l9_ms + pii_avg + avg_safety + avg_safety
        print(f"  {'─────────────────────────────':30s} ─────────")
        print(f"  {'TOTAL':30s} {total:>8}ms  (mock — no GPU)")
    else:
        total = l9_ms + (pii_ms if not args.mock else pii_avg) + (avg_safety if not args.mock else 0) + (rag_ms if not args.mock else 0)
        print(f"  {'─────────────────────────────':30s} ─────────")
        print(f"  {'TOTAL':30s} {total:>8}ms")

    print()
    print(f"VRAM estimate: ~11 GB / 24 GB (RTX 3090)")
    print(f"Headroom: ~13 GB")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(test_latency())
