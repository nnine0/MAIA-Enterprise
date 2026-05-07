"""
MAIA Policy Registry Manager
===========================
Manages policy sets for different sectors and occupations.
Supports dynamic loading, validation, and composition.

Run: python3 -m policies.registry
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MAIA-PolicyRegistry")


class PolicyStatus(Enum):
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"
    SUSPENDED = "suspended"


class MaterialityTier(Enum):
    CRITICAL = 1
    ELEVATED = 2
    BENIGN = 3


@dataclass
class PolicyClause:
    clause_id: str
    text: str
    keywords: List[str]
    severity: str
    action: str


@dataclass
class PolicySet:
    policy_id: str
    name: str
    policy_type: str  # "sector" or "occupation"
    description: str
    status: str
    regulations: List[str] = field(default_factory=list)
    clauses: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    forensic_hash: str = ""


class PolicyRegistry:
    """
    Central registry for all policy sets.
    Supports composition: sector + occupation = effective policy.
    """
    
    def __init__(self, base_path: str = "policies"):
        self.base_path = Path(base_path)
        self.sectors_path = self.base_path / "sectors"
        self.occupations_path = self.base_path / "occupations"
        self.templates_path = self.base_path / "templates"
        
        self._policy_cache: Dict[str, PolicySet] = {}
        self._active_config: Dict[str, Any] = {}
        
    def load_all_policies(self) -> Dict[str, List[PolicySet]]:
        """Load all policies from disk"""
        sectors = self._load_policy_dir(self.sectors_path, "sector")
        occupations = self._load_policy_dir(self.occupations_path, "occupation")
        
        logger.info(f"Loaded {len(sectors)} sectors, {len(occupations)} occupations")
        return {"sectors": sectors, "occupations": occupations}
    
    def _load_policy_dir(self, path: Path, ptype: str) -> List[PolicySet]:
        """Load all JSON files in a directory"""
        policies = []
        if not path.exists():
            return policies
            
        for f in path.glob("*.json"):
            try:
                policy = self._load_policy_file(f, ptype)
                policies.append(policy)
                self._policy_cache[policy.policy_id] = policy
            except Exception as e:
                logger.error(f"Failed to load {f}: {e}")
        return policies
    
    def _load_policy_file(self, path: Path, ptype: str) -> PolicySet:
        """Load a single policy file"""
        with open(path) as f:
            data = json.load(f)
        
        policy_id = data.get("sector_id") or data.get("occupation_id") or path.stem
        
        # Generate forensic hash
        content_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()[:16]
        
        return PolicySet(
            policy_id=policy_id,
            name=data.get("sector_name") or data.get("occupation_name", policy_id),
            policy_type=ptype,
            description=data.get("description", ""),
            status="active",
            regulations=data.get("regulations", []),
            clauses=data.get("policy_clauses", []),
            metadata={
                "tier_thresholds": data.get("tier_thresholds", {}),
                "materiality_keywords": data.get("materiality_keywords", {}),
                "permissions": data.get("permissions", {}),
                "requires_dhitl": data.get("requires_dhitl", False),
                "requires_audit_trail": data.get("requires_audit_trail", False),
            },
            forensic_hash=content_hash
        )
    
    def get_policy(self, policy_id: str) -> Optional[PolicySet]:
        """Get a specific policy by ID"""
        return self._policy_cache.get(policy_id)
    
    def get_sector(self, sector_id: str) -> Optional[PolicySet]:
        """Get a sector policy"""
        return self._policy_cache.get(sector_id)
    
    def get_occupation(self, occupation_id: str) -> Optional[PolicySet]:
        """Get an occupation policy"""
        return self._policy_cache.get(occupation_id)
    
    def compose_policy(self, sector_id: str, occupation_id: str) -> Dict:
        """
        Compose effective policy from sector + occupation.
        This is the key to multi-industry support!
        """
        sector = self.get_sector(sector_id)
        occupation = self.get_occupation(occupation_id)
        
        if not sector or not occupation:
            missing = []
            if not sector: missing.append(sector_id)
            if not occupation: missing.append(occupation_id)
            raise ValueError(f"Missing policies: {missing}")
        
        # Merge clauses with occupation having priority
        clause_map = {c["clause_id"]: c for c in sector.clauses}
        for clause in occupation.clauses:
            clause_map[clause["clause_id"]] = clause
        
        # Merge metadata
        combined_metadata = {**sector.metadata, **occupation.metadata}
        
        # Determine strictest requirements
        combined_metadata["requires_dhitl"] = (
            sector.metadata.get("requires_dhitl") or 
            occupation.metadata.get("requires_dhitl")
        )
        combined_metadata["requires_audit_trail"] = (
            sector.metadata.get("requires_audit_trail") or 
            occupation.metadata.get("requires_audit_trail")
        )
        
        return {
            "effective_policy_id": f"{sector_id}+{occupation_id}",
            "sector": {
                "id": sector.policy_id,
                "name": sector.name,
                "regulations": sector.regulations
            },
            "occupation": {
                "id": occupation.policy_id,
                "name": occupation.name,
                "clearance_level": occupation.metadata.get("permissions", {}).get("clearance_level", "NONE")
            },
            "combined_clauses": list(clause_map.values()),
            "materiality_keywords": {
                "critical": list(set(
                    sector.metadata.get("materiality_keywords", {}).get("critical", []) +
                    occupation.metadata.get("materiality_keywords", {}).get("critical", [])
                )),
                "elevated": list(set(
                    sector.metadata.get("materiality_keywords", {}).get("elevated", []) +
                    occupation.metadata.get("materiality_keywords", {}).get("elevated", [])
                )),
                "benign": list(set(
                    sector.metadata.get("materiality_keywords", {}).get("benign", []) +
                    occupation.metadata.get("materiality_keywords", {}).get("benign", [])
                ))
            },
            "settings": combined_metadata,
            "composed_at": datetime.now().isoformat()
        }
    
    def add_policy(self, policy_data: Dict, policy_type: str, policy_id: str) -> PolicySet:
        """Add a new policy (SDK method)"""
        target_dir = self.sectors_path if policy_type == "sector" else self.occupations_path
        file_path = target_dir / f"{policy_id}.json"
        
        with open(file_path, "w") as f:
            json.dump(policy_data, f, indent=2)
        
        policy = self._load_policy_file(file_path, policy_type)
        self._policy_cache[policy_id] = policy
        
        logger.info(f"Added policy: {policy_id}")
        return policy
    
    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy (SDK method)"""
        policy = self._policy_cache.get(policy_id)
        if not policy:
            return False
        
        target_dir = self.sectors_path if policy.policy_type == "sector" else self.occupations_path
        file_path = target_dir / f"{policy_id}.json"
        
        if file_path.exists():
            file_path.unlink()
            del self._policy_cache[policy_id]
            logger.info(f"Removed policy: {policy_id}")
            return True
        return False
    
    def list_sectors(self) -> List[Dict]:
        """List all available sectors"""
        return [
            {"id": p.policy_id, "name": p.name, "regulations": p.regulations}
            for p in self._policy_cache.values() 
            if p.policy_type == "sector"
        ]
    
    def list_occupations(self) -> List[Dict]:
        """List all available occupations"""
        return [
            {"id": p.policy_id, "name": p.name}
            for p in self._policy_cache.values() 
            if p.policy_type == "occupation"
        ]
    
    def export_active_config(self) -> Dict:
        """Export active policy configuration"""
        return {
            "version": "2.0",
            "exported_at": datetime.now().isoformat(),
            "sectors": self.list_sectors(),
            "occupations": self.list_occupations(),
            "total_policies": len(self._policy_cache)
        }


async def demo():
    print("="*60)
    print("MAIA Policy Registry Manager")
    print("="*60)
    
    registry = PolicyRegistry()
    
    print("\n[1] Loading all policies...")
    loaded = registry.load_all_policies()
    print(f"  Sectors: {len(loaded['sectors'])}")
    print(f"  Occupations: {len(loaded['occupations'])}")
    
    print("\n[2] Available Sectors:")
    for s in registry.list_sectors():
        print(f"  - {s['id']}: {s['name']} ({', '.join(s['regulations'])})")
    
    print("\n[3] Available Occupations:")
    for o in registry.list_occupations():
        print(f"  - {o['id']}: {o['name']}")
    
    print("\n[4] Composing Finance + Trader Policy...")
    try:
        composed = registry.compose_policy("finance", "trader")
        print(f"  Effective Policy ID: {composed['effective_policy_id']}")
        print(f"  Sector: {composed['sector']['name']}")
        print(f"  Occupation: {composed['occupation']['name']}")
        print(f"  Clearance: {composed['occupation']['clearance_level']}")
        print(f"  Combined Clauses: {len(composed['combined_clauses'])}")
        print(f"  Requires DHITL: {composed['settings'].get('requires_dhitl')}")
        print(f"  Requires Audit Trail: {composed['settings'].get('requires_audit_trail')}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print("\n[5] Composing Healthcare + Physician Policy...")
    try:
        composed = registry.compose_policy("healthcare", "physician")
        print(f"  Effective Policy ID: {composed['effective_policy_id']}")
        print(f"  Sector: {composed['sector']['name']}")
        print(f"  Occupation: {composed['occupation']['name']}")
        print(f"  Requires DHITL: {composed['settings'].get('requires_dhitl')}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print("\n" + "="*60)
    print("Key Value Prop: Same kernel handles banking AND healthcare")
    print("Proof: compose_policy('finance', 'trader') vs ('healthcare', 'physician')")
    print("="*60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())