"""
MAIA Neural Tool Dispatcher (Kernel)
=====================================
The "Brain" of the MAIA OS.

Watches thinking stream, finds right tool via registry,
triggers LoRA swap via vLLM/LoRAX API.

SR 26-02: Orchestrates Neural-Action binding at runtime.
"""

import json
import logging
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any, Generator
from dataclasses import dataclass, field
from enum import Enum

from kernel.registry import ToolRegistry, ToolDefinition
from kernel.exceptions import ToolExecutionError, PolicyViolationInterrupt


class DispatchState(Enum):
    """Dispatcher state machine"""
    IDLE = "idle"
    INTENT_DETECTED = "intent_detected"
    LOADAING_ADAPTER = "loading_adapter"
    GENERATING_PARAMS = "generating_params"
    EXECUTING = "executing"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class DispatchRequest:
    """Request for tool dispatch"""
    query: str
    reasoning: str = ""
    tool_id: Optional[str] = None
    user_id: Optional[str] = None


@dataclass
class DispatchResponse:
    """Response from tool dispatch"""
    success: bool
    tool_id: str
    rpc_call: Dict = field(default_factory=dict)
    forensic_hash: str = ""
    error: str = ""
    dhitl_required: bool = False


class NeuralToolDispatcher:
    """
    The OS Kernel's "Brain".
    
    Orchestrates the full dispatch workflow:
    1. Watch thinking stream for [CALL_TOOL:ID]
    2. Check registry for tool definition
    3. Verify Neural-Action binding (SR 26-02)
    4. Trigger LoRA hot-swap via vLLM/LoRAX
    5. Generate governed parameters
    6. Execute JSON-RPC call
    
    Usage:
        dispatcher = NeuralToolDispatcher()
        
        # Process dispatch request
        response = await dispatcher.dispatch(request)
    """
    
    TOOL_CALL_PATTERN = r"\[CALL_TOOL:([A-Z0-9_]+)\]"
    
    def __init__(
        self,
        registry_path: str = "configs/maia_kernel_manifest.json",
        logit_bias_dir: str = "configs/masks"
    ):
        self.logger = logging.getLogger("MAIA-Dispatcher")
        
        # Initialize registry
        self.registry = ToolRegistry(registry_path)
        
        # Configuration
        self.logit_bias_dir = Path(logit_bias_dir)
        
        # State
        self.state = DispatchState.IDLE
        self.active_tool: Optional[ToolDefinition] = None
        self.dispatch_history: List[DispatchResponse] = []
    
    def detect_intent(self, text: str) -> Optional[str]:
        """
        Detect tool intent in thinking text.
        
        Returns tool_id if found, None otherwise.
        """
        import re
        pattern = re.compile(self.TOOL_CALL_PATTERN)
        match = pattern.search(text)
        
        if match:
            return match.group(1)
        return None
    
    async def dispatch(self, request: DispatchRequest) -> DispatchResponse:
        """
        Execute full dispatch workflow.
        
        Steps:
        1. Detect intent in reasoning
        2. Lookup tool in registry
        3. Verify binding
        4. Hot-swap adapter
        5. Generate params
        6. Execute RPC
        """
        self.state = DispatchState.INTENT_DETECTED
        
        # 1. Detect intent
        tool_id = request.tool_id or self.detect_intent(request.reasoning or request.query)
        
        if not tool_id:
            return DispatchResponse(
                success=False,
                tool_id="",
                error="No tool intent detected"
            )
        
        # 2. Lookup tool
        tool = self.registry.get_tool(tool_id)
        
        if not tool:
            return DispatchResponse(
                success=False,
                tool_id=tool_id,
                error=f"Tool not found: {tool_id}"
            )
        
        # 3. Verify binding (SR 26-02)
        binding = self.registry.verify_neural_binding(
            tool_id,
            tool.neural_layer.adapter_id
        )
        
        if not binding["valid"]:
            return DispatchResponse(
                success=False,
                tool_id=tool_id,
                error=f"Binding invalid: {binding['reason']}"
            )
        
        self.active_tool = tool
        self.state = DispatchState.LOADAING_ADAPTER
        
        # 4. Hot-swap adapter (simulated - in prod calls LoRAX)
        self.logger.info(f"HOT-SWAP: Loading {tool.neural_layer.adapter_id}")
        await self._load_adapter(tool.neural_layer.adapter_id)
        
        # 5. Generate governed parameters
        self.state = DispatchState.GENERATING_PARAMS
        rpc_call = await self._generate_rpc_params(tool, request)
        
        # 6. Check DHITL
        dhitl = tool.governance_layer.dhitl_required or tool.neural_layer.requires_dhitl
        
        # 7. Execute (simulated)
        self.state = DispatchState.EXECUTING
        forensic_hash = self._compute_hash(request, rpc_call)
        
        response = DispatchResponse(
            success=True,
            tool_id=tool_id,
            rpc_call=rpc_call,
            forensic_hash=forensic_hash,
            dhitl_required=dhitl
        )
        
        self.dispatch_history.append(response)
        self.state = DispatchState.COMPLETE
        
        return response
    
    async def _load_adapter(self, adapter_id: str):
        """Hot-swap LoRA adapter via vLLM/LoRAX"""
        # In production:
        # requests.post(f"{LORAX_URL}/models/load", json={"model_id": adapter_id})
        self.logger.debug(f"Adapter loaded: {adapter_id}")
    
    async def _generate_rpc_params(
        self,
        tool: ToolDefinition,
        request: DispatchRequest
    ) -> Dict:
        """Generate JSON-RPC parameters"""
        action = tool.action_layer
        
        params = {
            k: f"<{k}>" for k in action.parameters.keys()
        }
        
        return {
            "jsonrpc": "2.0",
            "method": action.method,
            "params": params,
            "id": hashlib.md5(f"{request.query}{tool.tool_id}".encode()).hexdigest()[:8]
        }
    
    def _compute_hash(self, request: DispatchRequest, rpc: Dict) -> str:
        """Compute forensic hash"""
        data = f"{request.query}:{json.dumps(rpc)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def get_stats(self) -> Dict:
        """Get dispatcher statistics"""
        return {
            "state": self.state.value,
            "tools_registered": len(self.registry.tools),
            "dispatches_total": len(self.dispatch_history),
            "dispatches_success": sum(1 for r in self.dispatch_history if r.success),
            "active_tool": self.active_tool.tool_id if self.active_tool else None
        }


def create_dispatcher(registry_path: str = "configs/maia_kernel_manifest.json") -> NeuralToolDispatcher:
    """Factory function"""
    return NeuralToolDispatcher(registry_path=registry_path)


if __name__ == "__main__":
    print("=== MAIA Neural Tool Dispatcher ===\n")
    
    # Test dispatch
    import asyncio
    
    async def test():
        dispatcher = create_dispatcher()
        
        # Test intent detection
        text = "Transfer wire [CALL_TOOL:FINANCIAL_WIRE_V1]"
        intent = dispatcher.detect_intent(text)
        print(f"Intent: {text} -> {intent}")
        
        # Test dispatch
        request = DispatchRequest(
            query="Transfer $50k",
            reasoning="I need to send wire [CALL_TOOL:FINANCIAL_WIRE_V1]"
        )
        
        response = await dispatcher.dispatch(request)
        
        print(f"\\nDispatch: {response.success}")
        print(f"  Tool: {response.tool_id}")
        print(f"  Hash: {response.forensic_hash}")
        print(f"  DHITL: {response.dhitl_required}")
        
        print(f"\\nStats: {dispatcher.get_stats()}")
    
    asyncio.run(test())