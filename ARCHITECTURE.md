# MAIA Architecture

## The Governance Layer for Business Intelligence

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER REQUEST                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        MATERIALITY ROUTER                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │  Tier 1: credit, wire, transfer, loan, sanction, fraud, AML, KYC      │  │
│  │  Tier 2: risk, limit, approval, policy, audit                         │  │
│  │  Tier 3: general queries                                               │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
              Tier 1 (Critical)  Tier 2 (Elevated)  Tier 3 (Benign)
                    │                 │                 │
                    ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        PARALLEL ADAPTERS                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   ACTOR      │  │   ACTOR      │  │   ACTOR      │  │   ACTOR      │       │
│  │  Finance     │  │  Compliance  │  │   Fraud      │  │  Logistics   │       │
│  │  Expert      │  │  Expert      │  │   Expert     │  │  Expert      │       │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                  │                  │                  │             │
│         ▼                  ▼                  ▼                  ▼             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   AUDITOR    │  │   AUDITOR    │  │   AUDITOR    │  │   AUDITOR    │       │
│  │ SR 26-02     │  │   GDPR       │  │   AML        │  │   Safety     │       │
│  │ Validator    │  │  Validator   │  │  Validator   │  │  Validator   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PVI AIRLOCK                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  # SR 26-02 COMPLIANCE GATE: PVI AIRLOCK INTERCEPTOR                   │   │
│  │  - Actor generates action trajectory                                   │   │
│  │  - Auditor provides Effective Challenge                                │   │
│  │  - Circuit breaker blocks non-compliant                                │   │
│  │  - Tier 1: Escalates to Human SME Review (DHITL)                      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
              PASS              BLOCKED           PENDING_SME
                                                            │
                                                            ▼
                              ┌─────────────────────────────────────────┐
                              │         KAFKA LOG (AUDIT)              │
                              │  ┌───────────────────────────────────┐  │
                              │  │ transaction_id                    │  │
                              │  │ materiality_tier                  │  │
                              │  │ policy_vetted: SR 26-02           │  │
                              │  │ latent_trace_id                   │  │
                              │  │ dhitl_session_id (if Tier 1)      │  │
                              │  │ sme_votes: [SME1, SME2, SME3]     │  │
                              │  │ trajectory_hash                   │  │
                              │  └───────────────────────────────────┘  │
                              └─────────────────────────────────────────┘
```

## Flow Summary

| Step | Component | Description |
|------|-----------|-------------|
| 1 | User Request | Query enters MAIA |
| 2 | Materiality Router | Determines risk tier (1/2/3) |
| 3 | Parallel Adapters | Expert + Auditor run concurrently |
| 4 | PVI Airlock | Effective Challenge + Circuit Breaker |
| 5 | Kafka Log | Fed-auditable proof of compliance |

## SR 26-02 Compliance Mapping

| SR 26-02 Requirement | MAIA Implementation |
|-----------------------|---------------------|
| **Effective Challenge** | PVI Airlock with dual-adapter (Actor/Auditor) |
| **Materiality Matrix** | Tier-based routing with different validation paths |
| **Continuous Monitoring** | Latent EKG telemetry + STaR self-evolution |
| **Governance Layer** | All trajectories constrained by corporate policy |
| **Human Oversight** | DHITL SME voting for Tier 1 trajectories |

## Key Terms

- **Actor**: Expert adapter that generates action trajectory
- **Auditor**: SR 26-02 adapter that validates trajectory
- **PVI Airlock**: Policy-Validation-Interrupt - the compliance gate
- **DHITL**: Decentralized Human-in-the-Loop - SME voting
- **Latent Hash**: Forensic proof of model's reasoning state
- **DPO**: Direct Preference Optimization - RLHF for adapters