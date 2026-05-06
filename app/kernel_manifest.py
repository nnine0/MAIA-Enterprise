"""
MAIA Kernel Manifest Loader
=========================
Loads and validates the MAIA Tool-Manifest registry.
Provides Neural-Action binding verification.
"""

import json
import hashlib
import re
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ToolDefinition:
    tool_id: str
    description: str
    adapter_id: str
    base_model: str
    logit_bias_mask: str
    max_tokens: int
    materiality: str
    airlock_policy: str
    protocol: str
    endpoint: str
    method: str
    parameters: Dict[str, str]
    dhitl_required: bool = False
    requires_forensic_hash: bool = False


class KernelManifest:
    """
    Loads and queries the MAIA Tool-Manifest.
    Provides Neural-Action binding verification.
    """
    
    def __init__(self, manifest_path: str = "configs/maia_kernel_manifest.json"):
        self.manifest_path = Path(manifest_path)
        self.manifest: Dict = {}
        self.tools: Dict[str, ToolDefinition] = {}
        self._load_manifest()
    
    def _load_manifest(self):
        """Load manifest from JSON"""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")
        
        with open(self.manifest_path) as f:
            self.manifest = json.load(f)
        
        for tool in self.manifest.get("registry", []):
            neural = tool.get("neural_layer", {})
            governance = tool.get("governance_layer", {})
            action = tool.get("action_layer", {})
            
            self.tools[tool["tool_id"]] = ToolDefinition(
                tool_id=tool["tool_id"],
                description=tool.get("description", ""),
                adapter_id=neural.get("adapter_id", ""),
                base_model=neural.get("base_model", ""),
                logit_bias_mask=neural.get("logit_bias_mask", ""),
                max_tokens=neural.get("max_tokens", 512),
                materiality=governance.get("materiality", "LOW"),
                airlock_policy=governance.get("airlock_policy", ""),
                protocol=action.get("protocol", "json-rpc"),
                endpoint=action.get("endpoint", ""),
                method=action.get("method", ""),
                parameters=action.get("parameters", {}),
                dhitl_required=governance.get("dhitl_required", False),
                requires_forensic_hash=governance.get("required_forensic_hash") is not None
            )
    
    def get_tool(self, tool_id: str) -> Optional[ToolDefinition]:
        """Get tool definition by ID"""
        return self.tools.get(tool_id)
    
    def get_tools_by_materiality(self, materiality: str) -> List[ToolDefinition]:
        """Get all tools with specified materiality"""
        return [t for t in self.tools.values() if t.materiality == materiality]
    
    def verify_neural_binding(self, tool_id: str, active_adapter: str) -> Dict[str, Any]:
        """
        Verify Neural-Action binding.
        Returns verification result.
        """
        tool = self.tools.get(tool_id)
        
        if not tool:
            return {"valid": False, "reason": "Tool not found"}
        
        binding_valid = (active_adapter == tool.adapter_id)
        
        return {
            "valid": binding_valid,
            "tool_id": tool_id,
            "required_adapter": tool.adapter_id,
            "active_adapter": active_adapter,
            "reason": "Neural binding verified" if binding_valid else "Adapter mismatch"
        }
    
    def build_jsonrpc_call(
        self,
        tool_id: str,
        params: Dict,
        forensic_hash: Optional[str] = None
    ) -> Dict:
        """Build JSON-RPC call from tool definition"""
        tool = self.tools.get(tool_id)
        
        if not tool:
            raise ValueError(f"Tool not found: {tool_id}")
        
        # Include forensic hash if required
        rpc_params = params.copy()
        if tool.requires_forensic_hash and forensic_hash:
            rpc_params["_forensic_hash"] = forensic_hash
        
        return {
            "jsonrpc": "2.0",
            "method": tool.method,
            "params": rpc_params,
            "id": self._generate_rpc_id(tool_id, params)
        }
    
    def _generate_rpc_id(self, tool_id: str, params: Dict) -> str:
        """Generate unique RPC ID"""
        data = f"{tool_id}:{json.dumps(params, sort_keys=True)}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def list_tools(self) -> List[Dict]:
        """List all registered tools"""
        return [
            {
                "id": t.tool_id,
                "description": t.description,
                "adapter": t.adapter_id,
                "materiality": t.materiality,
                "endpoint": t.endpoint,
                "method": t.method,
                "dhitl": t.dhitl_required
            }
            for t in self.tools.values()
        ]
    
    def get_metadata(self) -> Dict:
        """Get manifest metadata"""
        return {
            "version": self.manifest.get("manifest_version"),
            "node_id": self.manifest.get("node_id"),
            "tool_count": len(self.tools),
            "loaded_at": datetime.utcnow().isoformat()
        }


def create_kernel_manifest(manifest_path: str = "configs/maia_kernel_manifest.json") -> KernelManifest:
    """Factory function"""
    return KernelManifest(manifest_path)


if __name__ == "__main__":
    manifest = create_kernel_manifest()
    
    print("=== MAIA Kernel Manifest ===")
    meta = manifest.get_metadata()
    for k, v in meta.items():
        print(f"  {k}: {v}")
    
    print(f"\nRegistered Tools ({len(manifest.tools)}):")
    for tool in manifest.list_tools():
        print(f"  {tool['id']}")
        print(f"    Adapter: {tool['adapter']}")
        print(f"    Materiality: {tool['materiality']}")
        print(f"    Method: {tool['method']}")
        print(f"    DHITL: {tool['dhitl']}")
        print()
    
    print("=== JSON-RPC Call Builder ===")
    rpc = manifest.build_jsonrpc_call(
        "FINANCIAL_WIRE_V1",
        {"amount": 75000, "currency": "USD", "routing_number": "063000021", "account_number": "123456789", "motive_code": "SUBCONTRACT"},
        forensic_hash="abc123"
    )
    print(json.dumps(rpc, indent=2))