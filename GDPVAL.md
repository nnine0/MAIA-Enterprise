# GDPval Framework: MAIA's Empirical Foundation

## The Economic Imperative

The GDPval research (May 2026) provides the empirical foundation for MAIA's architecture. It quantifies the "Capability vs. Risk" dilemma facing the Global 2000:

| Metric | Finding | MAIA Implication |
|--------|---------|------------------|
| **Cost Efficiency** | Models achieve parity with human experts at 1/10th the cost | Massive economic upside available |
| **Catastrophic Failures** | ~3% of outputs are harmful/dangerously wrong | Unacceptable in regulated industries |
| **Bad Failures** | ~26% are subpar but recoverable | Operational drag |
| **Failure Types** | Format errors, hallucinations most common (Figure 8) | Automated checkpoint targets |

**The Core Problem**: In unregulated industries, 3% catastrophic failure is acceptable. In banking/healthcare, it means billions in fines, SR 26-02 violations, and lost licenses.

**MAIA's Solution**: Capture the economic upside while mathematically suppressing catastrophic risk to zero.

---

## Materiality Matrix: Derived from GDPval Economics

MAIA tiers governance based on the **Cost of Catastrophic Failure**:

### Tier 1: High Risk / High Value (SR 26-02 Covered)

**GDPval Basis**: Tasks with dollar values exceeding wire transfer limits ($10K+) where catastrophic failure = regulatory violation, legal liability, or physical harm.

**MAIA Implementation**:
- Trigger: Wire transfers, loans >$10M, legal filings, sanctions compliance
- Governance: Full PVI Airlock + DHITL Human SME Review
- Adapter: Domain-specific expert (Finance/Legal/Compliance) + SR 26-02 Auditor
- Latency: ~420ms (includes human review cycle)

**Economic Logic**: The cost of a single catastrophic failure ($millions in fines) far exceeds the operational cost of governance ($thousands).

### Tier 2: Moderate Risk / Moderate Value

**GDPval Basis**: Tasks with dollar values from $500-$10K where "Bad" outcomes cause operational drag but aren't catastrophic.

**MAIA Implementation**:
- Trigger: Credit decisions, policy updates, compliance reports, contract reviews
- Governance: PVI Airlock with AI Auditor (no human-in-the-loop unless flagged)
- Adapter: Domain expert + formatting/validation auditor
- Latency: ~200ms

**Economic Logic**: Automated AI audit catches formatting errors and hallucinations (most common failures) at 1/10th the cost of human review.

### Tier 3: Low Risk / Low Value

**GDPval Basis**: Tasks with dollar values <$500 where "Bad" outcomes have negligible cost.

**MAIA Implementation**:
- Trigger: Internal summaries, scheduling, administrative queries
- Governance: Bypass PVI Airlock (PASS BYPASS)
- Adapter: Base model only (no expert adapter needed)
- Latency: ~50ms

**Economic Logic**: Matches GDPval's "Naive ratio" - maximum cost savings by skipping governance overhead.

---

## Adapter Configuration: Productizing O*NET Task Specialization

### The O*NET Connection

GDPval breaks the US economy into **44 distinct occupations** (Accountants, Lawyers, Compliance Officers, Financial Analysts, etc.). MAIA maps this to LoRA adapters:

| O*NET Occupation | MAIA Adapter | Primary Function |
|-----------------|--------------|-------------------|
| Financial Analysts | `finance-expert-v4` | Valuation, risk modeling |
| Accountants | `accounting-expert-v4` | Audit, reconciliation |
| Lawyers | `legal-expert-v4` | Contract review, compliance |
| Compliance Officers | `compliance-auditor-v4` | SR 26-02 validation |
| HR Specialists | `hr-expert-v4` | Policy, payroll |
| Logisticians | `logistics-expert-v4` | Supply chain, routing |

### Hot-Swap Architecture

When a task enters MAIA:

1. **Supervisor Router** identifies the O*NET occupation category
2. **LoRAX** hot-swaps the corresponding expert adapter into VRAM
3. **PVI Airlock** evaluates based on task materiality
4. **STaR Loop** uses rejection feedback to retrain specific adapter

This mirrors GDPval's finding that specialized models outperform generalized ones—the adapter for "Financial Analysts" outperforms a general-purpose model on financial tasks.

---

## DHITL: Productizing GDPval's Grading Protocol

### The GDPval Reference

GDPval's grading setup uses "pairwise comparisons" with industry professionals (avg 14 years experience) taking ~109 minutes to review outputs.

### MAIA's Implementation

MAIA automates this exact workflow for Tier 1 events:

| GDPval Grading | MAIA Production |
|----------------|-----------------|
| Industry professionals | SME Pool (Certified Airlock Admins) |
| 14 years avg experience | Domain-specific certifications |
| 109 min review time | Real-time consensus (<30 sec) |
| Pairwise comparison | 3-vote consensus (2 of 3) |
| Win-rate calculation | RLHF training data generation |

**The Loop**:
1. AI outputs action trajectory
2. SME votes APPROVE/REJECT with rationale
3. Winning trajectory becomes "Positive Reward" for adapter retraining
4. Losing trajectories become "Negative Reward"
5. STaR loop triggers automated retraining

---

## Solving "Under-Contextualized" Tasks

GDPval (Appendix A.2.7) notes models fail on ambiguous tasks lacking necessary context.

**MAIA Solution**: The PVI Airlock's secondary auditor evaluates context sufficiency:

```
If prompt.is_under_contextualized:
    BLOCK
    RETURN "Insufficient regulatory context. Route to user for clarification."
```

This prevents execution of actions where the AI would navigate ambiguity without proper grounding—exactly the failure mode GDPval identifies.

---

## Summary: Theory to Practice

| GDPval Finding | MAIA Implementation |
|-----------------|---------------------|
| 3% catastrophic failure rate | Tier 1 + DHITL (human-in-the-loop) |
| 26% "Bad" failure rate | Tier 2 + AI Auditor (automated) |
| Format errors / hallucinations | PVI Airlock validation |
| O*NET task specialization | LoRA adapter hot-swap |
| Human expert grading | SME consensus voting |
| Under-contextualized failures | Context sufficiency check |

**The Thesis**: If GDPval proves AI can replace human workflows economically, MAIA is the enterprise software that executes that transition safely.