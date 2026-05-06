# GDPVal Sectors and Occupations

## Overview

The GDPVal benchmark tests AI model capability on real-world economically valuable tasks from **44 occupations** spanning **9 GDP sectors**, constructed from professionals with an average of **14 years experience**.

| Benchmark Leader | Win Rate vs Professionals |
|------------------|---------------------------|
| GPT 5.2 Thinking | 70.9% |
| Claude Opus 4.1 | 47.6% |

---

## GDP Sectors → Occupations Mapping

### 1. Finance & Insurance

| Occupation | Category | MAIA Domain Adapter |
|------------|----------|-------------------|
| Financial Analysts | Analysis | `finance-expert-v4` |
| Accountants | Accounting | `accounting-expert-v4` |
| Underwriters | Risk | `finance-expert-v4` |
| Actuaries | Risk | `finance-expert-v4` |
| Auditors | Compliance | `finance-expert-v4` |
| Credit Analysts | Credit | `credit-expert-v4` |
| Loan Officers | Credit | `credit-expert-v4` |
| Investment Bankers | Advisory | `finance-expert-v4` |
| Insurance Agents | Sales | `finance-expert-v4` |
| Claims Adjusters | Claims | `finance-expert-v4` |

### 2. Real Estate

| Occupation | Category | MAIA Domain Adapter |
|------------|----------|-------------------|
| Property Managers | Management | `real-estate-expert-v4` |
| Leasing Agents | Sales | `real-estate-expert-v4` |
| Real Estate Brokers | Sales | `real-estate-expert-v4` |
| Appraisers | Valuation | `real-estate-expert-v4` |
| Land Use Planners | Regulatory | `real-estate-expert-v4` |
| Property Accountants | Accounting | `accounting-expert-v4` |
| Mortgage Brokers | Finance | `finance-expert-v4` |
| Title Examiners | Legal | `legal-expert-v4` |

### 3. Government & Public Administration

| Occupation | Category | MAIA Domain Adapter |
|------------|----------|-------------------|
| Compliance Officers | Regulatory | `compliance-expert-v4` |
| Regulatory Analysts | Analysis | `compliance-expert-v4` |
| Policy Analysts | Analysis | `compliance-expert-v4` |
| Budget Analysts | Analysis | `finance-expert-v4` |
| Grant Administrators | Administrative | `government-expert-v4` |
| Municipal Clerks | Administrative | `government-expert-v4` |
| Public Works Managers | Management | `government-expert-v4` |
| TaxAssessors | Compliance | `compliance-expert-v4` |

### 4. Biotech & Pharmaceutical

| Occupation | Category | MAIA Domain Adapter |
|------------|----------|-------------------|
| Clinical Research Associates | Research | `biotech-expert-v4` |
| Quality Assurance (QA) | Compliance | `biotech-expert-v4` |
| Regulatory Affairs | Regulatory | `biotech-expert-v4` |
| Pharmacovigilance Specialists | Safety | `biotech-expert-v4` |
| Medical Writers | Documentation | `biotech-expert-v4` |
| Biostatisticians | Analysis | `biotech-expert-v4` |
| Lab Managers | Management | `biotech-expert-v4` |
| Clinical Data Managers | Data | `biotech-expert-v4` |

### 5. Information Technology

| Occupation | Category | MAIA Domain Adapter |
|------------|----------|-------------------|
| Software Engineers | Development | `it-expert-v4` |
| DevOps Engineers | Infrastructure | `it-expert-v4` |
| Security Analysts | Security | `it-expert-v4` |
| Database Administrators | Data | `it-expert-v4` |
| System Administrators | Infrastructure | `it-expert-v4` |
| Data Scientists | Analysis | `it-expert-v4` |
| IT Project Managers | Management | `it-expert-v4` |
| Technical Writers | Documentation | `it-expert-v4` |

### 6. Retail Trade

| Occupation | Category | MAIA Domain Adapter |
|------------|----------|-------------------|
| Merchandise Planners | Planning | `retail-expert-v4` |
| Buyers | Purchasing | `retail-expert-v4` |
| Category Managers | Management | `retail-expert-v4` |
| Store Managers | Management | `retail-expert-v4` |
| Inventory Controllers | Operations | `retail-expert-v4` |
| Visual Merchandisers | Design | `retail-expert-v4` |
| E-commerce Managers | Digital | `retail-expert-v4` |
| Loss Prevention | Security | `retail-expert-v4` |

### 7. Manufacturing

| Occupation | Category | MAIA Domain Adapter |
|------------|----------|-------------------|
| Production Managers | Operations | `manufacturing-expert-v4` |
| Quality Control (QC) | Compliance | `manufacturing-expert-v4` |
| Process Engineers | Engineering | `manufacturing-expert-v4` |
| Supply Chain Managers | Logistics | `logistics-expert-v4` |
| Plant Managers | Management | `manufacturing-expert-v4` |
| Industrial Engineers | Engineering | `manufacturing-expert-v4` |
| Maintenance Technicians | Operations | `manufacturing-expert-v4` |
| Logistics Coordinators | Operations | `logistics-expert-v4` |

### 8. Logistics & Supply Chain

| Occupation | Category | MAIA Domain Adapter |
|------------|----------|-------------------|
| Logistics Managers | Management | `logistics-expert-v4` |
| Freight Forwarders | Operations | `logistics-expert-v4` |
| Warehouse Managers | Operations | `logistics-expert-v4` |
| Supply Chain Analysts | Analysis | `logistics-expert-v4` |
| Distribution Managers | Operations | `logistics-expert-v4` |
| Procurement Specialists | Purchasing | `logistics-expert-v4` |
| Customs Brokers | Compliance | `logistics-expert-v4` |
| Transportation Planners | Planning | `logistics-expert-v4` |

### 9. Professional Services

| Occupation | Category | MAIA Domain Adapter |
|------------|----------|-------------------|
| Lawyers | Legal | `legal-expert-v4` |
| Paralegals | Legal | `legal-expert-v4` |
| Management Consultants | Advisory | `consulting-expert-v4` |
| Accountants | Accounting | `accounting-expert-v4` |
| Tax Advisors | Advisory | `consulting-expert-v4` |
| HR Specialists | HR | `hr-expert-v4` |
| Marketing Managers | Marketing | `marketing-expert-v4` |
| Business Analysts | Analysis | `consulting-expert-v4` |

---

## MAIA Domain Adapter Mapping

| GDP Sector | Primary Adapter | Validation Adapter |
|-----------|-----------------|-------------------|
| `finance_insurance` | `finance-expert-v4` | `pvi-airlock-sr2602` |
| `real_estate` | `real-estate-expert-v4` | `pvi-airlock-sr2602` |
| `government_public` | `government-expert-v4` | `compliance-auditor-v4` |
| `biotech_pharma` | `biotech-expert-v4` | `compliance-auditor-v4` |
| `information_tech` | `it-expert-v4` | `security-auditor-v4` |
| `retail_trade` | `retail-expert-v4` | `compliance-auditor-v4` |
| `manufacturing` | `manufacturing-expert-v4` | `safety-auditor-v4` |
| `logistics_supply` | `logistics-expert-v4` | `safety-auditor-v4` |
| `professional_services` | `consulting-expert-v4` | `pvi-airlock-sr2602` |

---

## Materiality Tier by Sector

| GDP Sector | Tier 1 (Critical) | Tier 2 (Elevated) | Tier 3 (Benign) |
|-----------|-----------------|-----------------|-----------------|
| `finance_insurance` | Wire transfers, Large loans, Sanctions | Policy updates, Credit decisions | Queries, Reports |
| `real_estate` | Property transactions, Leases | Property management, Zoning | Schedule requests |
| `government_public` | Regulatory filings, Permits | Policy drafts, Reports | General queries |
| `biotech_pharma` | Clinical trials, Drug approvals | SOPs, Quality reports | Literature queries |
| `information_tech` | Security incidents, Access changes | Code reviews, Deployments | Status queries |
| `retail_trade` | Vendor contracts, Large orders | Inventory, Merchandising | Schedule queries |
| `manufacturing` | Safety incidents, Quality failures | Production reports | Shift schedules |
| `logistics_supply` | Shipment issues, Claims | Tracking, Routing | Status queries |
| `professional_services` | Contracts, Legal filings | Proposals, Reports | Meeting scheduling |

---

## References

- [GDPVal Benchmark](https://github.com/amaarora/GDPVal)
- [MAIA Materiality Matrix](/policies/materiality_registry.json)
- [SR 26-02 Compliance](/SR26-02_COMPLIANCE.md)