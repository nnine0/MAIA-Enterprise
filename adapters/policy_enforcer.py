"""
MAIA Policy Enforcer
====================
Core enforcement: classify operations, check policy, block + alert.
"""

from typing import Dict, List, Optional

from adapter_policy_registry import AdapterPolicyRegistry
from operation_classifier import OperationClassifier
from alert_handler import AlertHandler


class EnforcementResult:
    def __init__(self):
        self.allowed: bool = True
        self.blocked: bool = False
        self.violations: List[Dict] = []
        self.alerts_sent: int = 0

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "blocked": self.blocked,
            "violations": self.violations,
            "alerts_sent": self.alerts_sent,
        }


class PolicyEnforcer:
    def __init__(self, registry: AdapterPolicyRegistry = None, alert_handler: AlertHandler = None):
        self.registry = registry or AdapterPolicyRegistry()
        self.classifier = OperationClassifier()
        self.alert_handler = alert_handler or AlertHandler()

    def enforce(self, adapter_id: str, text: str) -> EnforcementResult:
        result = EnforcementResult()
        policy = self.registry.get(adapter_id)
        if not policy:
            return result

        ops = self.classifier.classify(text)
        for op in ops:
            if not policy.allowed(op.category, op.operation):
                violation = {
                    "adapter_id": adapter_id,
                    "category": op.category,
                    "operation": op.operation,
                    "blocked": True,
                }
                result.violations.append(violation)
                self.alert_handler.send(violation)
                result.alerts_sent += 1

        if result.violations:
            result.allowed = False
            result.blocked = True

        return result