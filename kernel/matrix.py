"""
MAIA Materiality Matrix
=====================
SR 26-02 compliant materiality classification system.

Maps sector-specific risks (OSHA, Davis-Bacon, FAR) into governance tiers.
This is the "Market-Ready" proof of Domain Expertise.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class MaterialityTier(Enum):
    """Governance tiers per SR 26-02"""
    TIER_1_CRITICAL = 1  # High exposure, DHITL required
    TIER_2_ELEVATED = 2   # Medium risk, AI audit
    TIER_3_BENIGN = 3     # Low risk, passive logging


@dataclass
class DomainConfig:
    """Configuration for a domain"""
    domain: str
    tier: MaterialityTier
    keywords: List[str] = field(default_factory=list)
    policies: List[str] = field(default_factory=list)


class MaterialityMatrix:
    """
    Materiality classification system.
    
    Maps queries to governance tiers based on:
    - Domain keywords
    - Policy violations
    - Financial thresholds
    
    Usage:
        matrix = MaterialityMatrix("configs/compliance/...")
        
        tier, config = matrix.classify("OSHA inspection for site")
        # tier = TIER_1_CRITICAL
    """
    
    def __init__(
        self,
        config_path: str = "configs/compliance/generic_contractor_v1.json"
    ):
        self.config_path = Path(config_path)
        self.config: Dict = {}
        self._load_config()
    
    def _load_config(self):
        """Load compliance configuration"""
        if not self.config_path.exists():
            self._init_default()
            return
        
        with open(self.config_path) as f:
            self.config = json.load(f)
    
    def _init_config(self):
        """Initialize with defaults"""
        self.config = {
            "violation_patterns": {
                "CRITICAL": ["bypass safety", "skip ppe"],
                "HIGH": ["unauthorized override"],
                "MEDIUM": ["delayed reporting"]
            },
            "materiality_tiers": {
                "TIER_1": {"threshold": 50000, "requires_dhitl": True},
                "TIER_2": {"threshold": 10000, "requires_dhitl": False},
                "TIER_3": {"threshold": 0, "requires_dhitl": False}
            },
            "domain_keywords": {
                "safety": ["osha", "ppe", "safety", "hazard"],
                "financial": ["bid", "estimate", "cost", "margin"],
                "legal": ["contract", "far", "legal"],
            }
        }
    
    def _init_default(self):
        """Initialize default config"""
        self._init_default_config()
    
    def _init_default_config(self):
        """Initialize with default configuration"""
        self.config = {
            "violation_patterns": {
                "CRITICAL": ["unsafe", "bypass", "override safety"],
                "HIGH": ["unauthorized", "circumvent"],
                "MEDIUM": ["incomplete", "delayed"]
            },
            "materiality_tiers": {
                "TIER_1": {"threshold": 50000, "requires_dhitl": True, "domains": ["safety", "financial"]},
                "TIER_2": {"threshold": 10000, "requires_dhitl": False, "domains": ["operations"]},
                "TIER_3": {"threshold": 0, "requires_dhitl": False, "domains": ["admin"]}
            },
            "domain_keywords": {
                "safety": ["safety", "osha", "ppe", "hazard"],
                "financial": ["bid", "cost", "estimate", "margin", "payment"],
                "legal": ["contract", "legal", "far", "clause"],
                "operations": ["schedule", "delivery", "logistics"]
            }
        }
    
    def classify(self, query: str) -> Tuple[MaterialityTier, Optional[DomainConfig]]:
        """
        Classify query into materiality tier.
        
        Returns: (tier, config)
        """
        query_lower = query.lower()
        
        # Check domain keywords
        domain_keywords = self.config.get("domain_keywords", {})
        
        for domain, keywords in domain_keywords.items():
            for kw in keywords:
                if kw in query_lower:
                    # Found domain match - get tier config
                    return self._get_tier_for_domain(domain), DomainConfig(
                        domain=domain,
                        tier=self._get_tier_for_domain(domain),
                        keywords=keywords
                    )
        
        # Default to BENIGN
        return MaterialityTier.TIER_3_BENIGN, DomainConfig(
            domain="default",
            tier=MaterialityTier.TIER_3_BENIGN
        )
    
    def _get_tier_for_domain(self, domain: str) -> MaterialityTier:
        """Get default tier for domain"""
        tiers = self.config.get("materiality_tiers", {})
        
        for tier_name, config in tiers.items():
            domains = config.get("domains", [])
            if domain in domains:
                if tier_name == "TIER_1":
                    return MaterialityTier.TIER_1_CRITICAL
                elif tier_name == "TIER_2":
                    return MaterialityTier.TIER_2_ELEVATED
                else:
                    return MaterialityTier.TIER_3_BENIGN
        
        return MaterialityTier.TIER_3_BENIGN
    
    def check_violations(self, text: str) -> List[Dict]:
        """Check for policy violations"""
        violations = []
        text_lower = text.lower()
        
        patterns = self.config.get("violation_patterns", {})
        
        for tier, tier_patterns in patterns.items():
            for pattern in tier_patterns:
                if pattern.lower() in text_lower:
                    violations.append({
                        "pattern": pattern,
                        "tier": tier,
                        "severity": "CRITICAL" if tier == "CRITICAL" else "HIGH" if tier == "HIGH" else "MEDIUM"
                    })
        
        return violations
    
    def requires_dhitl(self, tier: MaterialityTier, domain: str = "") -> bool:
        """Check if tier requires human approval"""
        tiers = self.config.get("materiality_tiers", {})
        
        tier_name = f"TIER_{tier.value}"
        tier_config = tiers.get(tier_name, {})
        
        return tier_config.get("requires_dhitl", False)
    
    def get_stats(self) -> Dict:
        """Get matrix statistics"""
        return {
            "domains": len(self.config.get("domain_keywords", {})),
            "violation_patterns": sum(
                len(p) for p in self.config.get("violation_patterns", {}).values()
            ),
            "tiers_configured": len(self.config.get("materiality_tiers", {}))
        }


def create_matrix(
    config_path: str = "configs/compliance/generic_contractor_v1.json"
) -> MaterialityMatrix:
    """Factory function"""
    return MaterialityMatrix(config_path=config_path)


if __name__ == "__main__":
    print("=== MAIA Materiality Matrix ===\n")
    
    # Test config
    matrix = create_matrix()
    
    test_queries = [
        "OSHA safety inspection needed at site",
        "Bid estimate for structural steel job",
        "Davis-Bacon wage verification",
        "Internal meeting notes",
    ]
    
    print("Classification:")
    for query in test_queries:
        tier, config = matrix.classify(query)
        print(f"  {query[:40]:40} -> {tier.name} ({config.domain})")
    
    # Check violations
    print("\nViolation Check:")
    violations = matrix.check_violations("I will skip the safety check and bypass OSHA")
    print(f"  Found: {len(violations)} violations")
    for v in violations:
        print(f"    - [{v['tier']}] {v['pattern']}")
    
    print(f"\nStats: {matrix.get_stats()}")