"""
Modular Model Cards for LoRA Adapters

SR 26-02 Conceptual Soundness compliance.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class RiskLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ModelCard:
    adapter_id: str
    name: str
    version: str
    domain: str
    sub_domain: str
    base_model: str
    materiality_tier: int
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    author: str = "MAIA Governance Team"
    description: str = ""
    training_data_sources: List[str] = field(default_factory=list)
    training_date: Optional[str] = None
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    evaluation_metrics: Dict[str, float] = field(default_factory=dict)
    use_cases: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    risk_assessment: Dict[str, Any] = field(default_factory=dict)
    governance_controls: List[str] = field(default_factory=list)
    fallback_behavior: str = ""
    audit_trail_enabled: bool = True
    dhitl_required: bool = False
    version_history: List[Dict] = field(default_factory=list)


def create_finance_card(adapter_id: str, version: str = "1.0.0") -> ModelCard:
    return ModelCard(
        adapter_id=adapter_id,
        name=f"Finance Expert {adapter_id}",
        version=version,
        domain="Finance",
        sub_domain="Financial Advisory",
        base_model="llama-3.1-70b-instruct",
        materiality_tier=1,
        description="Specialized adapter for financial analysis, compliance, and advisory tasks",
        training_data_sources=[
            "SEC Filings (2020-2024)",
            "FINRA Guidelines",
            "GAAP Standards Documentation",
            "Financial textbooks corpus"
        ],
        hyperparameters={
            "lora_r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.1,
            "learning_rate": 3e-4,
            "epochs": 5
        },
        evaluation_metrics={
            "accuracy": 0.94,
            "financial_compliance_score": 0.91,
            "factual_consistency": 0.89
        },
        use_cases=[
            "Financial statement analysis",
            "Regulatory compliance checking",
            "Risk assessment",
            "Investment advisory support"
        ],
        limitations=[
            "Cannot provide personalized investment advice",
            "Limited to publicly available financial data",
            "May not reflect real-time market conditions"
        ],
        risk_assessment={
            "level": RiskLevel.HIGH.value,
            "factors": ["Regulatory compliance", "Financial advice liability", "Data accuracy"],
            "mitigations": ["DHITL required for Tier 1", "Audit trail mandatory", "Human review for sensitive queries"]
        },
        governance_controls=[
            "PVI Airlock enforcement",
            "Latent telemetry logging",
            "DHITL voting for critical decisions",
            "Quarterly model auditing"
        ],
        fallback_behavior="Route to human financial advisor for Tier 1 queries",
        audit_trail_enabled=True,
        dhitl_required=True,
        version_history=[{"version": "1.0.0", "date": datetime.utcnow().isoformat(), "changes": "Initial release"}]
    )


def create_legal_card(adapter_id: str, version: str = "1.0.0") -> ModelCard:
    return ModelCard(
        adapter_id=adapter_id,
        name=f"Legal Expert {adapter_id}",
        version=version,
        domain="Legal",
        sub_domain="Legal Advisory",
        base_model="llama-3.1-70b-instruct",
        materiality_tier=1,
        description="Specialized adapter for legal analysis, contract review, and regulatory compliance",
        training_data_sources=[
            "Case law database (2020-2024)",
            "Statutory law corpus",
            "Contract templates library",
            "Bar association guidelines"
        ],
        hyperparameters={
            "lora_r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.1,
            "learning_rate": 3e-4,
            "epochs": 5
        },
        evaluation_metrics={
            "accuracy": 0.92,
            "legal_reasoning_score": 0.90,
            "citation_accuracy": 0.88
        },
        use_cases=[
            "Contract review and analysis",
            "Legal research assistance",
            "Regulatory compliance checking",
            "Case precedent analysis"
        ],
        limitations=[
            "Cannot provide legal advice in jurisdictions where unauthorized",
            "May not reflect most recent case law",
            "Cannot represent clients in court"
        ],
        risk_assessment={
            "level": RiskLevel.HIGH.value,
            "factors": ["Legal liability", "Unauthorized practice of law", "Confidentiality"],
            "mitigations": ["DHITL required for Tier 1", "Disclaimer required", "Escalation to licensed attorneys"]
        },
        governance_controls=[
            "PVI Airlock enforcement",
            "Client confidentiality monitoring",
            "DHITL voting for critical contracts",
            "Annual legal compliance review"
        ],
        fallback_behavior="Route to licensed attorney for Tier 1 queries",
        audit_trail_enabled=True,
        dhitl_required=True,
        version_history=[{"version": "1.0.0", "date": datetime.utcnow().isoformat(), "changes": "Initial release"}]
    )


def create_healthcare_card(adapter_id: str, version: str = "1.0.0") -> ModelCard:
    return ModelCard(
        adapter_id=adapter_id,
        name=f"Healthcare Expert {adapter_id}",
        version=version,
        domain="Healthcare",
        sub_domain="Medical Advisory",
        base_model="llama-3.1-70b-instruct",
        materiality_tier=1,
        description="Specialized adapter for healthcare domain queries, medical literature analysis",
        training_data_sources=[
            "PubMed medical literature",
            "Clinical guidelines corpus",
            "HIPAA compliance documentation",
            "Medical textbooks"
        ],
        hyperparameters={
            "lora_r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.1,
            "learning_rate": 3e-4,
            "epochs": 5
        },
        evaluation_metrics={
            "accuracy": 0.91,
            "medical_accuracy": 0.89,
            "citation_quality": 0.87
        },
        use_cases=[
            "Medical literature search assistance",
            "Clinical guideline reference",
            "Healthcare compliance checking",
            "Patient education materials"
        ],
        limitations=[
            "Cannot diagnose or treat patients",
            "Cannot replace licensed medical professionals",
            "May not reflect latest medical research"
        ],
        risk_assessment={
            "level": RiskLevel.CRITICAL.value,
            "factors": ["Patient safety", "HIPAA compliance", "Medical liability"],
            "mitigations": ["Strict Tier 1 enforcement", "No diagnostic capabilities", "Always recommend professional consultation"]
        },
        governance_controls=[
            "PVI Airlock with healthcare-specific rules",
            "HIPAA audit logging",
            "DHITL required for all medical queries",
            "Monthly medical accuracy reviews"
        ],
        fallback_behavior="Route to licensed healthcare professional for all patient-related queries",
        audit_trail_enabled=True,
        dhitl_required=True,
        version_history=[{"version": "1.0.0", "date": datetime.utcnow().isoformat(), "changes": "Initial release"}]
    )


DOMAIN_CARDS = {
    "finance": create_finance_card,
    "legal": create_legal_card,
    "healthcare": create_healthcare_card,
}


def get_model_card(domain: str, adapter_id: str, version: str = "1.0.0") -> ModelCard:
    creator = DOMAIN_CARDS.get(domain.lower())
    if creator:
        return creator(adapter_id, version)
    return ModelCard(
        adapter_id=adapter_id,
        name=f"General Expert {adapter_id}",
        version=version,
        domain="General",
        sub_domain="General Advisory",
        base_model="llama-3.1-70b-instruct",
        materiality_tier=2,
        description="General purpose advisory adapter",
        governance_controls=["PVI Airlock enforcement", "Latent telemetry logging"],
        audit_trail_enabled=True,
        dhitl_required=False,
    )