"""
MAIA Kernel Registry
====================
Neural-Tool-Binding schema and manifest registry.

Defines how a "Neural Layer" (LoRA) is bound to an "Action Layer" (JSON-RPC).
This is the blueprint for the "Neural App Store."

SR 26-02: AIBOM (Adapter Inventory Bill of Materials) compliance.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum


class ToolCategory(Enum):
    """Categories of neural tools"""
    COMMUNICATION = "communication"
    DATA_OPERATIONS = "data_operations"
    FINANCE = "finance"
    AUDIT = "audit"
    LOGISTICS = "logistics"
    LEGAL = "legal"
    SAFETY = "safety"
    OPERATIONS = "operations"
    GOVERNANCE = "governance"


class MaterialityLevel(Enum):
    """Governance materiality tiers"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ProtocolType(Enum):
    """Action layer protocols"""
    JSON_RPC = "json-rpc"
    REST = "rest"
    GRPC = "grpc"


@dataclass
class NeuralLayerBinding:
    """Binds LoRA adapter to tool"""
    adapter_id: str
    base_model: str
    logit_bias_mask: str = ""
    max_tokens: int = 2048
    requires_dhitl: bool = False


@dataclass
class GovernanceLayerBinding:
    """Governance configuration"""
    materiality: str = "LOW"
    airlock_policy: str = ""
    required_forensic_hash: bool = False
    dhitl_required: bool = False
    violation_triggers: List[str] = field(default_factory=list)


@dataclass
class ActionLayerBinding:
    """Action execution configuration"""
    protocol: str = "json-rpc"
    endpoint: str = ""
    method: str = ""
    parameters: Dict[str, str] = field(default_factory=dict)


@dataclass
class ToolDefinition:
    """Complete tool definition"""
    tool_id: str
    description: str
    category: ToolCategory
    governance_layer: GovernanceLayerBinding
    neural_layer: NeuralLayerBinding
    action_layer: ActionLayerBinding
    
    version: str = "1.0.0"
    created_at: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "tool_id": self.tool_id,
            "description": self.description,
            "category": self.category.value,
            "governance_layer": asdict(self.governance_layer),
            "neural_layer": asdict(self.neural_layer),
            "action_layer": asdict(self.action_layer),
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ToolDefinition":
        return cls(
            tool_id=data["tool_id"],
            description=data["description"],
            category=ToolCategory(data.get("category", "governance")),
            governance_layer=GovernanceLayerBinding(**data.get("governance_layer", {})),
            neural_layer=NeuralLayerBinding(**data.get("neural_layer", {})),
            action_layer=ActionLayerBinding(**data.get("action_layer", {})),
            version=data.get("version", "1.0.0"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


class ToolRegistry:
    """
    The "Neural App Store" registry.
    
    Manages all tool definitions and their Neural-Action bindings.
    Provides AIBOM compliance for SR 26-02.
    """
    
    def __init__(self, manifest_path: str = "configs/maia_kernel_manifest.json"):
        self.manifest_path = Path(manifest_path)
        self.manifest: Dict = {}
        self.tools: Dict[str, ToolDefinition] = {}
        
        if self.manifest_path.exists():
            self._load_manifest()
        else:
            self._init_manifest()
    
    def _init_manifest(self):
        """Initialize empty manifest"""
        self.manifest = {
            "manifest_version": "1.0.0",
            "node_id": "MAIA-CORE-01",
            "registry": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _load_manifest(self):
        """Load from JSON manifest"""
        with open(self.manifest_path) as f:
            self.manifest = json.load(f)
        
        # Parse tool definitions
        for tool_data in self.manifest.get("registry", []):
            try:
                tool = ToolDefinition.from_dict(tool_data)
                self.tools[tool.tool_id] = tool
            except Exception:
                pass  # Skip invalid
    
    def register_tool(self, tool: ToolDefinition) -> bool:
        """
        Register a new tool.
        
        Returns True if successfully registered.
        """
        self.tools[tool.tool_id] = tool
        
        tool_dict = tool.to_dict()
        self.manifest["registry"].append(tool_dict)
        
        return True
    
    def unregister_tool(self, tool_id: str) -> bool:
        """Unregister a tool"""
        if tool_id in self.tools:
            del self.tools[tool_id]
            self.manifest["registry"] = [
                t for t in self.manifest["registry"]
                if t.get("tool_id") != tool_id
            ]
            return True
        return False
    
    def get_tool(self, tool_id: str) -> Optional[ToolDefinition]:
        """Get tool by ID"""
        return self.tools.get(tool_id)
    
    def get_tools_by_category(self, category: ToolCategory) -> List[ToolDefinition]:
        """Get all tools in a category"""
        return [
            t for t in self.tools.values()
            if t.category == category
        ]
    
    def get_tools_by_materiality(self, materiality: str) -> List[ToolDefinition]:
        """Get all tools at or above materiality"""
        level_map = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        min_level = level_map.get(materiality, 1)
        
        return [
            t for t in self.tools.values()
            if level_map.get(t.governance_layer.materiality, 0) >= min_level
        ]
    
    def verify_neural_binding(self, tool_id: str, active_adapter: str) -> Dict:
        """
        Verify Neural-Action binding is valid.
        
        SR 26-02: Ensures tool call originates from governed weights.
        """
        tool = self.tools.get(tool_id)
        
        if not tool:
            return {"valid": False, "reason": "Tool not found"}
        
        expected_adapter = tool.neural_layer.adapter_id
        binding_valid = (active_adapter == expected_adapter)
        
        return {
            "valid": binding_valid,
            "tool_id": tool_id,
            "expected_adapter": expected_adapter,
            "active_adapter": active_adapter,
            "reason": "Binding valid" if binding_valid else "Adapter mismatch"
        }
    
    def get_aibom(self) -> Dict:
        """
        Generate AIBOM (Adapter Inventory Bill of Materials).
        
        SR 26-02: Required for Fed audit compliance.
        """
        aibom = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_tools": len(self.tools),
            "tools": []
        }
        
        for tool in self.tools.values():
            aibom["tools"].append({
                "tool_id": tool.tool_id,
                "adapter_id": tool.neural_layer.adapter_id,
                "materiality": tool.governance_layer.materiality,
                "dhitl": tool.neural_layer.requires_dhitl,
                "protocol": tool.action_layer.protocol,
            })
        
        return aibom
    
    def save_manifest(self, path: str = None):
        """Save manifest to JSON"""
        if path:
            self.manifest_path = Path(path)
        
        self.manifest["registry"] = [
            t.to_dict() for t in self.tools.values()
        ]
        self.manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        with open(self.manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2)
    
    def list_tools(self) -> List[Dict]:
        """List all registered tools"""
        return [
            {
                "id": t.tool_id,
                "category": t.category.value,
                "materiality": t.governance_layer.materiality,
                "adapter": t.neural_layer.adapter_id,
                "endpoint": t.action_layer.endpoint,
            }
            for t in self.tools.values()
        ]


def create_registry(
    manifest_path: str = "configs/maia_kernel_manifest.json"
) -> ToolRegistry:
    """Factory function"""
    return ToolRegistry(manifest_path)


if __name__ == "__main__":
    from datetime import timezone
    
    print("=== MAIA Kernel Registry ===\n")
    
    registry = create_registry()
    
    print(f"Manifest: {registry.manifest.get('node_id')}")
    print(f"Tools registered: {len(registry.tools)}")
    print()
    
    # List tools
    print("Registered Tools:")
    for tool in registry.list_tools():
        print(f"  {tool['id']}: {tool['category']} ({tool['materiality']})")
    
    print()
    
    # AIBOM
    aibom = registry.get_aibom()
    print(f"AIBOM: {aibom['total_tools']} tools")