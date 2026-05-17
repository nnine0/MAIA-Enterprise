# GDPVal Integration: Economic Task Valuation

## Overview

The GDPVal benchmark provides MAIA's empirical foundation for economic task classification. It tests AI model capability on real-world tasks from **44 occupations** spanning **9 GDP sectors**, constructed from professionals with an average of **14 years experience**.

| Benchmark | Score |
|-----------|-------|
| GPT 5.2 Thinking | 70.9% win rate vs professionals |
| Claude Opus 4.1 | 47.6% win rate |

**MAIA's Position**: Suppress catastrophic failures to zero while capturing economic efficiency gains.

---

## GDP Sectors: Materiality Matrix Alignment

MAIA integrates 9 GDP sectors for task classification:

| GDP Sector | Sample Occupations | Critical Keywords |
|-----------|----------------|-----------------|
| `finance_insurance` | Financial Analysts, Underwriters | wire, transfer, derivative, claim |
| `real_estate` | Property Managers, Leasing Agents | property, lease, tenant, zoning |
| `government_public` | Compliance Officers, Regulators | policy, regulation, permit |
| `biotech_pharma` | Clinical Researchers, QA | clinical, trial, SOP, patent |
| `information_tech` | Software Engineers, DevOps | API, database, cybersecurity |
| `retail_trade` | Merchandisers, Buyers | inventory, POS, sales |
| `manufacturing` | Production Managers, QC | assembly, production, supply chain |
| `logistics_supply` | Logisticians, Freight | shipping, warehouse, distribution |
| `professional_services` | Lawyers, Accountants, Consultants | legal, audit, LOI, proposal |

---

## Task Valuation: Risk-Based Routing

### Tier 1: CRITICAL (GDPVal Domain Expert Task)

**Triggers**: Finance, Legal, Regulatory, Clinical, Real Estate transactions
**GDPval Basis**: Dollar value >$10K where catastrophic failure = regulatory violation
**MAIA Governance**: Full Circuit Breaker + DHITL SME Review
**Execution**: Adapter hot-swap + 3-vote consensus

### Tier 2: ELEVATED (GDPVal Skilled Task)

**Triggers**: Policy updates, compliance reports, evaluations, proposals
**GDPval Basis**: Dollar value $500-$10K "Bad" outcomes cause operational drag
**MAIA Governance**: Circuit Breaker + AI Auditor
**Execution**: Automated validation

### Tier 3: BENIGN (GDPVal Routine Task)

**Triggers**: Administrative queries, scheduling, info requests
**GDPval Basis**: Dollar value <$500, negligible failure cost
**MAIA Governance**: Bypass
**Execution**: Direct LLM response

---

## Integration Points

### 1. MaterialityMatrix Auto-Detection

```python
from app.materiality_matrix import create_materiality_matrix

matrix = create_materiality_matrix()
result = matrix.validate_query("Prepare LOI for commercial property")

print(result["gdp_sector"])      # "real_estate" or "professional_services"
print(result["tier"])           # "CRITICAL" or "ELEVATED"
print(result["requires_dhitl"])  # True for Tier 1
```

### 2. Economic Valuation Export

```python
valuation = matrix.export_economic_valuation("Wire $1M to overseas supplier")
# Returns GDPVal-aligned task valuation with sector, tier, domain
```

### 3. Sector-Aware Routing

The supervisor router uses GDP sector detection to:
1. Identify domain from query keywords
2. Route to appropriate expert adapter
3. Apply sector-specific governance rules

---

## Economic Logic

| Failure Mode | GDPval Finding | MAIA Control |
|------------|-------------|-------------|
| Catastrophic (3%) | Regulatory fines, legal liability | Tier 1 + DHITL → 0% |
| Bad (26%) | Operational drag | Tier 2 + AI Audit |
| Format errors | Most common failure | Validation layer |
| Hallucinations | Secondary failure | Auditing module |

**The Thesis**: MAIA mathematically suppresses catastrophic risk while capturing the ~10x cost efficiency GDPval demonstrates.

---

## References

- [GDPVal Benchmark](https://github.com/amaarora/GDPVal)
- [GDPVal Blog Post](https://amaarora.github.io/posts/2025-12-15-gdpval-review.html)
- SR 26-02: Enterprise AI Governance Standard