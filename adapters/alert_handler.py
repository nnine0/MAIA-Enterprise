"""
MAIA Alert Handler
==================
Simple alert dispatch for policy violations.
Logs to console + optional file + production audit logger.
"""

import json
import logging
import os
import hashlib
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger("maia.alert")


class AlertHandler:
    def __init__(self, log_path: str = None, audit_logger=None):
        self.log_path = log_path
        self.audit_logger = audit_logger
        self._alerts: list = []

    def send(self, alert: Dict) -> None:
        alert["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._alerts.append(alert)

        msg = (f"BLOCKED | adapter={alert.get('adapter_id','?')} "
               f"op={alert.get('operation','?')} cat={alert.get('category','?')}")
        logger.warning(msg)

        if self.log_path:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "a") as f:
                f.write(json.dumps(alert) + "\n")

        if self.audit_logger:
            audit_entry = {
                "event_type": "adapter_policy_violation",
                "adapter_id": alert.get("adapter_id"),
                "category": alert.get("category"),
                "operation": alert.get("operation"),
                "blocked": alert.get("blocked", True),
                "tenant_id": alert.get("tenant_id", "system"),
                "user_id": alert.get("user_id", "system"),
                "query_hash": hashlib.sha256(alert.get("operation", "").encode()).hexdigest()[:16],
                "timestamp": alert["timestamp"],
            }
            self.audit_logger.log(audit_entry)

    def recent(self, n: int = 10) -> list:
        return self._alerts[-n:]

    def count(self) -> int:
        return len(self._alerts)