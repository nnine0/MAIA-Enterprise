"""
MAIA Policy SDK
===============
Client SDK for managing policies programmatically.
Allows clients to add, remove, and compose policies.

Usage:
    from policies.sdk import PolicySDK
    
    sdk = PolicySDK()
    sdk.add_sector_policy(...)
    sdk.add_occupation_policy(...)
    config = sdk.compose("finance", "trader")
"""

import json
import hashlib
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MAIA-PolicySDK")


@dataclass
class PolicyClauseInput:
    clause_id: str
    text: str
    keywords: List[str]
    severity: str  # CRITICAL, HIGH, MEDIUM
    action: str    # BLOCK, ESCALATE, LOG


@dataclass 
class SectorPolicyInput:
    sector_id: str
    sector_name: str
    description: str
    regulations: List[str]
    tier_thresholds: Dict[str, int]
    materiality_keywords: Dict[str, List[str]]
    policy_clauses: List[PolicyClauseInput]
    requires_dhitl: bool = True
    requires_audit_trail: bool = True


@dataclass
class OccupationPolicyInput:
    occupation_id: str
    occupation_name: str
    description: str
    sector_contexts: List[str]
    clearance_level: str  # HIGH, MEDIUM, LOW
    permissions: Dict[str, bool]
    materiality_keywords: Dict[str, List[str]]
    policy_clauses: List[PolicyClauseInput]
    dhitl_eligible: bool = False
    requires_dual_authorization: bool = False


class PolicySDK:
    """
    Client SDK for MAIA Policy Management.
    
    Supports:
    - Adding custom sector policies
    - Adding custom occupation policies  
    - Composing sector + occupation policies
    - Exporting policy configurations
    """
    
    def __init__(self, base_path: str = "policies"):
        self.base_path = Path(base_path)
        self.sectors_path = self.base_path / "sectors"
        self.occupations_path = self.base_path / "templates"
        
        self._ensure_directories()
        
    def _ensure_directories(self):
        """Ensure policy directories exist"""
        self.sectors_path.mkdir(parents=True, exist_ok=True)
        self.occupations_path.mkdir(parents=True, exist_ok=True)
    
    def _generate_forensic_hash(self, data: Dict) -> str:
        """Generate forensic hash for policy"""
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()[:16]
    
    def add_sector_policy(self, policy: SectorPolicyInput) -> Dict:
        """
        Add a new sector policy.
        
        Args:
            policy: SectorPolicyInput with sector configuration
            
        Returns:
            Dict with policy_id and forensic_hash
        """
        policy_data = {
            "sector_id": policy.sector_id,
            "sector_name": policy.sector_name,
            "description": policy.description,
            "regulations": policy.regulations,
            "tier_thresholds": policy.tier_thresholds,
            "materiality_keywords": policy.materiality_keywords,
            "policy_clauses": [
                {
                    "clause_id": c.clause_id,
                    "text": c.text,
                    "keywords": c.keywords,
                    "severity": c.severity,
                    "action": c.action
                }
                for c in policy.policy_clauses
            ],
            "requires_dhitl": policy.requires_dhitl,
            "requires_audit_trail": policy.requires_audit_trail
        }
        
        file_path = self.sectors_path / f"{policy.sector_id}.json"
        
        with open(file_path, "w") as f:
            json.dump(policy_data, f, indent=2)
        
        forensic_hash = self._generate_forensic_hash(policy_data)
        
        logger.info(f"Added sector policy: {policy.sector_id}")
        
        return {
            "policy_id": policy.sector_id,
            "policy_type": "sector",
            "forensic_hash": forensic_hash,
            "created_at": datetime.now().isoformat(),
            "file_path": str(file_path)
        }
    
    def add_occupation_policy(self, policy: OccupationPolicyInput) -> Dict:
        """
        Add a new occupation policy.
        
        Args:
            policy: OccupationPolicyInput with occupation configuration
            
        Returns:
            Dict with policy_id and forensic_hash
        """
        policy_data = {
            "occupation_id": policy.occupation_id,
            "occupation_name": policy.occupation_name,
            "description": policy.description,
            "sector_contexts": policy.sector_contexts,
            "clearance_level": policy.clearance_level,
            "permissions": policy.permissions,
            "materiality_keywords": policy.materiality_keywords,
            "policy_clauses": [
                {
                    "clause_id": c.clause_id,
                    "text": c.text,
                    "keywords": c.keywords,
                    "severity": c.severity,
                    "action": c.action
                }
                for c in policy.policy_clauses
            ],
            "dhitl_eligible": policy.dhitl_eligible,
            "requires_dual_authorization": policy.requires_dual_authorization
        }
        
        file_path = self.occupations_path / f"{policy.occupation_id}.json"
        
        with open(file_path, "w") as f:
            json.dump(policy_data, f, indent=2)
        
        forensic_hash = self._generate_forensic_hash(policy_data)
        
        logger.info(f"Added occupation policy: {policy.occupation_id}")
        
        return {
            "policy_id": policy.occupation_id,
            "policy_type": "occupation",
            "forensic_hash": forensic_hash,
            "created_at": datetime.now().isoformat(),
            "file_path": str(file_path)
        }
    
    def remove_policy(self, policy_id: str, policy_type: str = "sector") -> bool:
        """
        Remove a policy.
        
        Args:
            policy_id: ID of policy to remove
            policy_type: "sector" or "occupation"
            
        Returns:
            bool: True if removed successfully
        """
        target_path = self.sectors_path if policy_type == "sector" else self.occupations_path
        file_path = target_path / f"{policy_id}.json"
        
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Removed {policy_type} policy: {policy_id}")
            return True
        return False
    
    def list_policies(self, policy_type: Optional[str] = None) -> List[Dict]:
        """
        List all policies.
        
        Args:
            policy_type: Filter by "sector" or "occupation"
            
        Returns:
            List of policy metadata
        """
        policies = []
        
        if policy_type is None or policy_type == "sector":
            for f in self.sectors_path.glob("*.json"):
                with open(f) as fp:
                    data = json.load(fp)
                    policies.append({
                        "policy_id": data.get("sector_id", f.stem),
                        "policy_type": "sector",
                        "name": data.get("sector_name", f.stem),
                        "regulations": data.get("regulations", [])
                    })
        
        if policy_type is None or policy_type == "occupation":
            for f in self.occupations_path.glob("*.json"):
                with open(f) as fp:
                    data = json.load(fp)
                    policies.append({
                        "policy_id": data.get("occupation_id", f.stem),
                        "policy_type": "occupation",
                        "name": data.get("occupation_name", f.stem),
                        "clearance_level": data.get("clearance_level", "NONE")
                    })
        
        return policies
    
    def export_configuration(self, output_path: Optional[str] = None) -> Dict:
        """
        Export full policy configuration.
        
        Args:
            output_path: Optional path to save JSON config
            
        Returns:
            Full configuration dict
        """
        config = {
            "version": "2.0",
            "exported_at": datetime.now().isoformat(),
            "sectors": [],
            "occupations": []
        }
        
        for f in self.sectors_path.glob("*.json"):
            with open(f) as fp:
                config["sectors"].append(json.load(fp))
        
        for f in self.occupations_path.glob("*.json"):
            with open(f) as fp:
                config["occupations"].append(json.load(fp))
        
        if output_path:
            with open(output_path, "w") as f:
                json.dump(config, f, indent=2)
            logger.info(f"Exported config to: {output_path}")
        
        return config
    
    def import_configuration(self, config_path: str) -> Dict:
        """
        Import policy configuration from JSON file.
        
        Args:
            config_path: Path to configuration JSON
            
        Returns:
            Import summary
        """
        with open(config_path) as f:
            config = json.load(f)
        
        imported = {"sectors": 0, "occupations": 0}
        
        for sector in config.get("sectors", []):
            sector_id = sector.get("sector_id", "unknown")
            file_path = self.sectors_path / f"{sector_id}.json"
            with open(file_path, "w") as fp:
                json.dump(sector, fp, indent=2)
            imported["sectors"] += 1
        
        for occupation in config.get("occupations", []):
            occupation_id = occupation.get("occupation_id", "unknown")
            file_path = self.occupations_path / f"{occupation_id}.json"
            with open(file_path, "w") as fp:
                json.dump(occupation, fp, indent=2)
            imported["occupations"] += 1
        
        logger.info(f"Imported {imported}")
        return imported


def demo():
    print("="*60)
    print("MAIA Policy SDK Demo")
    print("="*60)
    
    sdk = PolicySDK()
    
    print("\n[1] Adding custom sector policy...")
    custom_sector = SectorPolicyInput(
        sector_id="energy",
        sector_name="Energy & Utilities",
        description="Oil, gas, electric utilities, renewable energy",
        regulations=["FERC", "NERC", "EPA"],
        tier_thresholds={"critical": 50000, "elevated": 5000, "benign": 0},
        materiality_keywords={
            "critical": ["pipeline", "grid", "outage", "generation", "transmission"],
            "elevated": ["compliance", "report", "audit"],
            "benign": ["query", "info"]
        },
        policy_clauses=[
            PolicyClauseInput(
                clause_id="ENERGY_001",
                text="Report grid outages within 5 minutes",
                keywords=["outage", "grid", "down", "failure"],
                severity="CRITICAL",
                action="ESCALATE"
            ),
            PolicyClauseInput(
                clause_id="ENERGY_002",
                text="Follow EPA emissions reporting",
                keywords=["emissions", "epa", "report", "carbon"],
                severity="HIGH",
                action="LOG"
            )
        ],
        requires_dhitl=True,
        requires_audit_trail=True
    )
    result = sdk.add_sector_policy(custom_sector)
    print(f"  Added: {result['policy_id']} (hash: {result['forensic_hash']})")
    
    print("\n[2] Listing all policies...")
    all_policies = sdk.list_policies()
    print(f"  Total policies: {len(all_policies)}")
    for p in all_policies:
        print(f"    - {p['policy_type']}: {p['policy_id']}")
    
    print("\n[3] Exporting configuration...")
    config = sdk.export_configuration()
    print(f"  Sectors: {len(config['sectors'])}, Occupations: {len(config['occupations'])}")
    
    print("\n" + "="*60)
    print("SDK ready for client integration!")
    print("="*60)


if __name__ == "__main__":
    demo()