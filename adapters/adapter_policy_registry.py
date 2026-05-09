"""
MAIA Adapter Policy Registry
============================
Loads and looks up adapter policies from policy_config.json.
"""

import json
import os
from typing import Dict, List, Optional, Any


class AdapterPolicy:
    def __init__(self, adapter_id: str, data: dict):
        self.adapter_id = adapter_id
        self.description = data.get("description", "")
        self.operation_mode = data.get("operation_mode", "unrestricted")
        self.sql = AdapterPolicy._constraint(data.get("sql_constraints"))
        self.file = AdapterPolicy._constraint(data.get("file_constraints"))
        self.api = AdapterPolicy._constraint(data.get("api_constraints"))
        self.alert_config = data.get("alert_config", {})

    @staticmethod
    def _constraint(data: Optional[dict]) -> dict:
        if not data:
            return {"allowed": [], "forbidden": []}
        return {
            "allowed": [o.lower() for o in data.get("allowed_operations", [])],
            "forbidden": [o.lower() for o in data.get("forbidden_operations", [])],
        }

    def allowed(self, category: str, operation: str) -> bool:
        op = operation.lower()
        constraints = getattr(self, category, {})
        if op in constraints.get("forbidden", []):
            return False
        allowed_list = constraints.get("allowed", [])
        if allowed_list and op not in allowed_list:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "adapter_id": self.adapter_id,
            "description": self.description,
            "operation_mode": self.operation_mode,
            "sql": self.sql,
            "file": self.file,
            "api": self.api,
            "alert_config": self.alert_config,
        }


class AdapterPolicyRegistry:
    DEFAULTS = {"config_path": os.path.join(os.path.dirname(__file__), "policy_config.json")}

    def __init__(self, config_path: str = None):
        self.config_path = config_path or self.DEFAULTS["config_path"]
        self._policies: Dict[str, AdapterPolicy] = {}
        self._load()

    def _load(self):
        with open(self.config_path) as f:
            data = json.load(f)
        for aid, cfg in data.get("adapter_policies", {}).items():
            self._policies[aid] = AdapterPolicy(aid, cfg)

    def get(self, adapter_id: str) -> Optional[AdapterPolicy]:
        return self._policies.get(adapter_id)

    def list_adapter_ids(self) -> List[str]:
        return list(self._policies.keys())

    def is_operation_allowed(self, adapter_id: str, category: str, operation: str) -> bool:
        policy = self.get(adapter_id)
        if not policy:
            return True
        return policy.allowed(category, operation)

    def count(self) -> int:
        return len(self._policies)