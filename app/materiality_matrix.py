"""
Materiality Matrix Loader

Loads and validates the governed Materiality Matrix Registry.
SR 26-02 compliant risk tiering as a governed data asset.
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MaterialityTier(Enum):
    TIER_1_CRITICAL = 1
    TIER_2_ELEVATED = 2
    TIER_3_BENIGN = 3


@dataclass
class TierConfig:
    tier_id: str
    name: str
    level: int
    description: str
    domains: List[str]
    keywords: List[str]
    financial_threshold: int
    requires_dhitl: bool
    requires_audit_trail: bool
    latent_hash_logging: bool
    escalation_path: str
    vote_threshold: Optional[int]
    timeout_minutes: Optional[int]


class MaterialityMatrix:
    """
    Loads and queries the governed Materiality Matrix Registry.
    Provides auditable, version-controlled risk classification.
    """
    
    def __init__(self, registry_path: str = "policies/materiality_registry.json"):
        self.registry_path = Path(registry_path)
        self._registry: Dict = {}
        self._tiers: Dict[int, TierConfig] = {}
        self._load_registry()
    
    def _load_registry(self):
        if not self.registry_path.exists():
            raise FileNotFoundError(f"Materiality Matrix Registry not found: {self.registry_path}")
        
        with open(self.registry_path, 'r') as f:
            self._registry = json.load(f)
        
        for tier_data in self._registry.get("tiers", []):
            config = TierConfig(
                tier_id=tier_data["tier_id"],
                name=tier_data["name"],
                level=tier_data["level"],
                description=tier_data["description"],
                domains=tier_data["criteria"]["domains"],
                keywords=tier_data["criteria"]["keywords"],
                financial_threshold=tier_data["criteria"]["financial_threshold"],
                requires_dhitl=tier_data["criteria"]["requires_dhitl"],
                requires_audit_trail=tier_data["criteria"]["requires_audit_trail"],
                latent_hash_logging=tier_data["criteria"]["latent_hash_logging"],
                escalation_path=tier_data["escalation"]["path"],
                vote_threshold=tier_data["escalation"]["vote_threshold"],
                timeout_minutes=tier_data["escalation"]["timeout_minutes"]
            )
            self._tiers[tier_data["level"]] = config
    
    def classify(self, query: str, domain: Optional[str] = None) -> Tuple[MaterialityTier, TierConfig]:
        """
        Classify a query against the governed Materiality Matrix.
        Returns tier level and full configuration.
        """
        query_lower = query.lower()
        
        for level in [1, 2, 3]:
            config = self._tiers.get(level)
            if not config:
                continue
            
            if domain and domain.lower() in [d.lower() for d in config.domains]:
                return MaterialityTier(level), config
            
            for keyword in config.keywords:
                if keyword.lower() in query_lower:
                    return MaterialityTier(level), config
        
        return MaterialityTier.TIER_3_BENIGN, self._tiers[3]
    
    def get_config(self, tier: MaterialityTier) -> TierConfig:
        """Get full configuration for a tier."""
        return self._tiers[tier.value]
    
    def validate_query(self, query: str) -> Dict:
        """Validate query against registry rules and return classification."""
        tier, config = self.classify(query)
        
        return {
            "tier": tier.name,
            "tier_level": tier.value,
            "requires_dhitl": config.requires_dhitl,
            "requires_audit_trail": config.requires_audit_trail,
            "latent_hash_logging": config.latent_hash_logging,
            "escalation_path": config.escalation_path,
            "classification_reason": f"Matched keywords in TIER_{tier.value}",
            "registry_version": self._registry.get("version"),
            "registry_id": self._registry.get("registry_id"),
            "classification_timestamp": datetime.utcnow().isoformat()
        }
    
    def get_audit_hash(self, query: str, tier: MaterialityTier) -> str:
        """Generate immutable audit hash for classification decision."""
        data = f"{query}:{tier.value}:{self._registry.get('version')}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def get_registry_metadata(self) -> Dict:
        """Return registry metadata for audit purposes."""
        return {
            "registry_id": self._registry.get("registry_id"),
            "version": self._registry.get("version"),
            "status": self._registry.get("status"),
            "effective_date": self._registry.get("effective_date"),
            "owner": self._registry.get("owner"),
            "approvers": self._registry.get("approvers"),
            "last_reviewed": self._registry.get("last_reviewed"),
            "next_review": self._registry.get("next_review")
        }


def create_materiality_matrix(registry_path: str = "policies/materiality_registry.json") -> MaterialityMatrix:
    """Factory function to create Materiality Matrix."""
    return MaterialityMatrix(registry_path)


if __name__ == "__main__":
    matrix = create_materiality_matrix()
    
    print("=== Materiality Matrix Registry ===")
    metadata = matrix.get_registry_metadata()
    for k, v in metadata.items():
        print(f"  {k}: {v}")
    
    print("\n=== Test Classifications ===")
    
    test_queries = [
        "What are the tax implications of our merger?",
        "What are your office hours?",
        "Configure the VPN access for new employee",
        "Diagnose my chest pain symptoms"
    ]
    
    for query in test_queries:
        result = matrix.validate_query(query)
        print(f"\nQuery: {query[:50]}...")
        print(f"  Tier: {result['tier']} (Level {result['tier_level']})")
        print(f"  DHITL: {result['requires_dhitl']}, Audit: {result['requires_audit_trail']}")
        print(f"  Audit Hash: {matrix.get_audit_hash(query, MaterialityTier(result['tier_level']))}")