"""
MAIA Sovereign Adapter Loader
==============================
Resolves business sector IDs to local filesystem paths using the Neural Registry.

SR 26-02 Requirement: All model assets must be tracked in an immutable inventory.
This registry IS that inventory — a single source of truth for every adapter in production.

Usage:
    from core.adapter_loader import registry

    path = registry.get_agentic("finance")
    # Returns: "/data/adapters/finance_expert_v4"

    validator_path = registry.get_validator("finance")
    # Returns: "/data/adapters/pvi_airlock_sr2602"
"""

import json
import os
from typing import Optional, Dict


REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "adapters", "registry.json")


class MAIARegistry:
    """
    Neural Registry — resolves sector keys to local adapter paths.

    This is the single source of truth for all active adapters.
    No code in this project should hard-code an adapter path.
    Everything must resolve through this registry.
    """

    def __init__(self, registry_path: str = REGISTRY_PATH):
        self._path = registry_path
        self._data: Dict = {}
        self._load()

    def _load(self):
        resolved = os.path.abspath(self._path)
        if not os.path.isfile(resolved):
            raise FileNotFoundError(
                f"Adapter registry not found: {resolved}\n"
                f"Run 'python train_adapter.py --init-registry' to create it, "
                f"or ensure adapters/registry.json exists."
            )
        with open(resolved, "r") as f:
            self._data = json.load(f)

    @property
    def base_model(self) -> str:
        return self._data.get("base_model", "unknown")

    @property
    def inventory_version(self) -> str:
        return self._data.get("inventory_version", "unknown")

    def get_agentic(self, sector: str) -> str:
        """Resolve sector to agentic (expert) adapter path."""
        entry = self._data.get("registry", {}).get(sector)
        if entry:
            return entry["agentic"]
        return self._data.get("defaults", {}).get("agentic", "/data/adapters/default_expert")

    def get_validator(self, sector: str) -> str:
        """Resolve sector to validator (auditor) adapter path."""
        entry = self._data.get("registry", {}).get(sector)
        if entry:
            return entry["validator"]
        return self._data.get("defaults", {}).get("validator", "/data/adapters/pvi_airlock_sr2602")

    def get_materiality_tier(self, sector: str) -> int:
        """Get materiality tier for a sector."""
        entry = self._data.get("registry", {}).get(sector)
        if entry:
            return entry.get("materiality_tier", 3)
        return 3

    def get_hub(self, hub_key: str) -> Optional[str]:
        """Resolve a named hub to its adapter path."""
        return self._data.get("hubs", {}).get(hub_key)

    def get_specialist(self, specialist_key: str) -> Optional[str]:
        """Resolve a specialist/SME adapter."""
        return self._data.get("specialists", {}).get(specialist_key)

    def get_adapter_path(self, sector_key: str) -> str:
        """Alias for get_agentic — generic sector-to-path resolution."""
        return self.get_agentic(sector_key)

    def list_sectors(self) -> list:
        """List all registered sectors."""
        return list(self._data.get("registry", {}).keys())

    def get_inventory(self) -> Dict:
        """Full inventory summary for audit/SR 26-02."""
        sectors = self._data.get("registry", {})
        return {
            "inventory_version": self.inventory_version,
            "base_model": self.base_model,
            "active_sectors": list(sectors.keys()),
            "total_adapters": len(self._data.get("registry", {}))
                             + len(self._data.get("hubs", {}))
                             + len(self._data.get("specialists", {})),
            "audit_protocols": list({
                v["audit_protocol"]
                for v in sectors.values()
                if "audit_protocol" in v
            }),
        }

    def reload(self):
        """Reload registry from disk (useful after hot-update)."""
        self._load()


# Global singleton — import this from anywhere
registry = MAIARegistry()
