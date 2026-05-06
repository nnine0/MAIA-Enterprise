"""
MAIA Neural Tool Router
=====================
Routes requests to specialized Tool-Adapters based on intent detection.
Supports hot-swapping via LoRAX for millisecond-level tool switching.
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class ToolCategory(Enum):
    COMMUNICATION = "communication"
    DATA_OPERATIONS = "data_operations"
    FINANCE = "finance"
    AUDIT = "audit"
    LOGISTICS = "logistics"
    LEGAL = "legal"
    SAFETY = "safety"
    OPERATIONS = "operations"


@dataclass
class ToolSpec:
    adapter_id: str
    tool_function: str
    category: ToolCategory
    description: str
    governance: Dict[str, Any]
    requires_approval: bool = False
    materiality_ceiling: Optional[int] = None


class NeuralToolRouter:
    """
    Routes user intents to specialized Tool-Adapters.
    
    Workflow:
    1. Parse user intent
    2. Match to tool category
    3. Load tool adapter (via LoRAX)
    4. Execute with governance constraints
    """
    
    TOOL_REGISTRY = {
        "email": ToolSpec(
            adapter_id="email_governed_workflow",
            tool_function="send_governed_email(recipient, body)",
            category=ToolCategory.COMMUNICATION,
            description="PII-locked email tool",
            governance={"airlock": "pii_mask_airlock", "pii_blocked": True}
        ),
        "sql": ToolSpec(
            adapter_id="sql_readonly_auditor",
            tool_function="query_business_intelligence(sql_query)",
            category=ToolCategory.DATA_OPERATIONS,
            description="Read-only SQL",
            governance={"airlock": "sql_guard_airlock", "read_only": True}
        ),
        "invoice": ToolSpec(
            adapter_id="erp_materiality_guard",
            tool_function="reconcile_invoice(vendor_id, amount)",
            category=ToolCategory.FINANCE,
            description="ERP invoice reconciliation",
            governance={"airlock": "materiality_airlock", "materiality_ceiling": 50000},
            requires_approval=True,
            materiality_ceiling=50000
        ),
        "forensic": ToolSpec(
            adapter_id="aibom_forensic_reporter",
            tool_function="generate_forensic_hash(transaction_id)",
            category=ToolCategory.AUDIT,
            description="SR 26-02 AIBOM reporter",
            governance={"airlock": "aibom_airlock", "self_audit": True}
        ),
        "route": ToolSpec(
            adapter_id="hazmat_route_planner",
            tool_function="optimize_hazmat_route(cargo_type, destination)",
            category=ToolCategory.LOGISTICS,
            description="HAZMAT route planning",
            governance={"airlock": "hazmat_neural_airlock", "geospatial_safety": True}
        ),
        "redact": ToolSpec(
            adapter_id="document_redactor",
            tool_function="redact_document(content)",
            category=ToolCategory.LEGAL,
            description="Document redaction",
            governance={"airlock": "redact_airlock", "automatic_redact": True}
        ),
        "clause": ToolSpec(
            adapter_id="contract_clause_analyzer",
            tool_function="analyze_contract_clauses(text)",
            category=ToolCategory.LEGAL,
            description="Contract clause analyzer",
            governance={"airlock": "clause_airlock", "requires_review": True}
        ),
        "escalate": ToolSpec(
            adapter_id="incident_escalator",
            tool_function="escalate_incident(details)",
            category=ToolCategory.SAFETY,
            description="Incident escalation",
            governance={"airlock": "incident_airlock", "auto_escalate": ["safety", "injury"]}
        ),
        "ppe": ToolSpec(
            adapter_id="safety_ppe_detector",
            tool_function="detect_ppe(image)",
            category=ToolCategory.SAFETY,
            description="PPE vision detector",
            governance={"airlock": "ppe_airlock", "block_without": True}
        ),
    }
    
    INTENT_PATTERNS = {
        "email": ["email", "send", "notify", "message", "communicate"],
        "sql": ["query", "select", "report", "business intelligence", "analytics"],
        "invoice": ["invoice", "reconcile", "payment", "vendor", "bill"],
        "forensic": ["audit", "forensic", "compliance", "proof", "hash"],
        "route": ["route", "logistics", "delivery", "hazmat", "shipping"],
        "redact": ["redact", "confidential", "sensitive", "mask"],
        "clause": ["contract", "clause", "liability", "terms"],
        "escalate": ["incident", "accident", "injury", "safety"],
        "ppe": ["ppe", "safety gear", "detection", "image"],
    }
    
    def __init__(self, adapters_dir: str = "adapters"):
        self.adapters_dir = Path(adapters_dir)
        self._loaded_tools: Dict[str, ToolSpec] = {}
        self._load_tool_configs()
    
    def _load_tool_configs(self):
        """Load tool configs from adapters directory"""
        for path in self.adapters_dir.glob("*_workflow.json"):
            if path.stem in self.TOOL_REGISTRY:
                tool_id = path.stem
                pattern_key = tool_id.replace("_workflow", "")
                if pattern_key in self.INTENT_PATTERNS:
                    pass  # Already registered
    
    def route_intent(self, user_input: str) -> Optional[ToolSpec]:
        """Route user intent to appropriate tool"""
        input_lower = user_input.lower()
        
        for tool_key, patterns in self.INTENT_PATTERNS.items():
            if any(p in input_lower for p in patterns):
                return self.TOOL_REGISTRY.get(tool_key)
        
        return None
    
    def check_governance(self, tool: ToolSpec, params: Dict) -> Dict[str, Any]:
        """Check if action passes governance constraints"""
        result = {
            "approved": True,
            "requires_dhitl": False,
            "violations": [],
            "tool": tool.adapter_id
        }
        
        # Check materiality ceiling
        if tool.materiality_ceiling and "amount" in params:
            amount = params.get("amount", 0)
            if amount > tool.materiality_ceiling:
                result["approved"] = False
                result["requires_dhitl"] = True
                result["violations"].append(f"Amount ${amount} exceeds ceiling ${tool.materiality_ceiling}")
        
        return result
    
    def get_tool_for_category(self, category: ToolCategory) -> List[ToolSpec]:
        """Get all tools for a category"""
        return [t for t in self.TOOL_REGISTRY.values() if t.category == category]
    
    def list_tools(self) -> List[Dict]:
        """List all available tools"""
        return [
            {
                "id": t.adapter_id,
                "function": t.tool_function,
                "category": t.category.value,
                "description": t.description
            }
            for t in self.TOOL_REGISTRY.values()
        ]


def create_tool_router(adapters_dir: str = "adapters") -> NeuralToolRouter:
    """Factory function"""
    return NeuralToolRouter(adapters_dir)


if __name__ == "__main__":
    router = create_tool_router()
    
    print("=== MAIA Neural Tool Router ===\n")
    print("Available Tools:")
    for tool in router.list_tools():
        print(f"  {tool['id']}: {tool['function']}")
    
    print("\n=== Intent Routing Test ===")
    test_inputs = [
        "Send email to john about the project",
        "Query the sales database",
        "Reconcile invoice for $75000",
        "Generate forensic hash for transaction 12345"
    ]
    
    for inp in test_inputs:
        tool = router.route_intent(inp)
        print(f"\nInput: {inp}")
        print(f"  Tool: {tool.adapter_id if tool else 'None'}")
        print(f"  Function: {tool.tool_function if tool else 'None'}")