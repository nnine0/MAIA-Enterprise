"""
MAIA Data Models

Core data structures for the governance layer.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict
from datetime import datetime


class MaterialityTier(Enum):
    """Materiality Matrix tiers per SR 26-02"""
    TIER_1_CRITICAL = 1
    TIER_2_ELEVATED = 2
    TIER_3_BENIGN = 3


class AirlockVerdict(Enum):
    PASS = "PASS"
    PASS_BYPASS = "PASS (BYPASS)"
    BLOCKED = "BLOCKED"
    PENDING_SME_REVIEW = "PENDING_SME_REVIEW"


class SMEVote(Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CONDITIONAL = "CONDITIONAL"


@dataclass
class TrajectoryRecord:
    """Neural trajectory record for Fed audit trail"""
    transaction_id: str
    timestamp: str
    materiality_tier: int
    policy_vetted: str
    actor_adapter: str
    auditor_adapter: str
    status: str
    reason: Optional[str] = None
    latent_hash: Optional[str] = None
    escalation_path: Optional[str] = None
    dhitl_session_id: Optional[str] = None
    sme_votes: Optional[List[Dict]] = None
    sme_consensus: Optional[str] = None


@dataclass
class SMEVotingSession:
    """DHITL Voting Session"""
    session_id: str
    transaction_id: str
    trajectory: str
    domain: str
    created_at: str
    status: str = "pending"
    votes: List[Dict] = field(default_factory=list)
    consensus: Optional[str] = None
    required_votes: int = 3


@dataclass
class TransactionMetrics:
    """Metrics for a single transaction"""
    transaction_id: str
    timestamp: datetime
    query: str
    domain: str
    materiality_tier: int
    status: str
    latency_ms: int
    reason: str
    latent_hash: Optional[str] = None
    dhitl_session_id: Optional[str] = None
    sme_votes: Optional[List[Dict]] = None
    sme_consensus: Optional[str] = None


@dataclass 
class DispatchToken:
    """Supervisor routing dispatch token"""
    industry: str
    sub_domain: str
    expert_adapter: str
    auditor_adapter: str
    materiality_tier: int
    execution_path: List[str]


@dataclass
class LatentSignature:
    """Latent state at model layer"""
    timestamp: str
    layer: int
    adapter_id: str
    latent_hash: str
    reasoning_type: str