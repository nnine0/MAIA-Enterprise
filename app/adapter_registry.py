"""
Adapter Registry Loader

Loads adapter metadata for model inventory tracking.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class AdapterMetadata:
    adapter_id: str
    name: str
    version: str
    sr26_tier: int
    domain: str
    sub_domain: str
    base_model: str
    created_date: str
    conceptual_soundness: Dict
    risk_assessment: Dict
    governance: Dict


class AdapterRegistry:
    """Registry for loading adapter metadata."""
    
    def __init__(self, council_dir: str = "council"):
        self.council_dir = Path(council_dir)
        self._adapters: Dict[str, AdapterMetadata] = {}
        self._load_all()
    
    def _load_all(self):
        if not self.council_dir.exists():
            return
        
        for adapter_path in self.council_dir.iterdir():
            if adapter_path.is_dir():
                metadata_path = adapter_path / "metadata.json"
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        data = json.load(f)
                        self._adapters[data['adapter_id']] = AdapterMetadata(**data)
    
    def get(self, adapter_id: str) -> Optional[AdapterMetadata]:
        return self._adapters.get(adapter_id)
    
    def list_all(self) -> List[AdapterMetadata]:
        return list(self._adapters.values())
    
    def list_by_tier(self, tier: int) -> List[AdapterMetadata]:
        return [a for a in self._adapters.values() if a.sr26_tier == tier]
    
    def get_inventory(self) -> Dict:
        return {
            "total_adapters": len(self._adapters),
            "by_tier": {
                "tier_1_critical": len(self.list_by_tier(1)),
                "tier_2_elevated": len(self.list_by_tier(2)),
                "tier_3_benign": len(self.list_by_tier(3))
            },
            "adapters": [
                {
                    "id": a.adapter_id,
                    "name": a.name,
                    "tier": a.sr26_tier,
                    "domain": a.domain
                }
                for a in self._adapters.values()
            ]
        }


def create_registry(council_dir: str = "council") -> AdapterRegistry:
    return AdapterRegistry(council_dir)


if __name__ == "__main__":
    registry = create_registry()
    inv = registry.get_inventory()
    print("=== Adapter Inventory ===")
    print(f"Total: {inv['total_adapters']}")
    print(f"Tier 1: {inv['by_tier']['tier_1_critical']}")
    print(f"Tier 2: {inv['by_tier']['tier_2_elevated']}")
    print(f"Tier 3: {inv['by_tier']['tier_3_benign']}")
    print("\nAdapters:")
    for a in inv['adapters']:
        print(f"  - {a['id']}: {a['name']} (Tier {a['tier']})")