"""
MAIA Neural Tool Dispatcher
========================
The "CPU Scheduler" of the MAIA-Enterprise OS.
Bridges probabilistic reasoning (thinking) to deterministic action (JSON-RPC).

Implements Interrupt-and-Reconfigure pattern:
1. Detects tool intent in <|think|> stream
2. Hot-swaps neural weights via LoRAX
3. Applies Logit Bias firewall
4. Generates governed parameters
5. Dispatches via JSON-RPC
6. Logs to forensics for SR 26-02 compliance
"""

import re
import json
import hashlib
import logging
from typing import Generator, Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Forensics integration
try:
    from forensics.logger import get_logger
    FORENSICS_AVAILABLE = True
except ImportError:
    FORENSICS_AVAILABLE = False


logger = logging.getLogger("MAIA-Dispatcher")


class DispatchState(Enum):
    IDLE = "idle"
    REASONING = "reasoning"
    TOOL_DETECTED = "tool_detected"
    KERNEL_SWAP = "kernel_swap"
    GOVERNED_GEN = "governed_gen"
    EXECUTING = "executing"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ToolIntent:
    tool_id: str
    reasoning_context: str
    confidence: float = 1.0
    requires_dhitl: bool = False


@dataclass
class DispatchResult:
    success: bool
    tool_id: str
    rpc_response: Optional[Dict] = None
    forensic_hash: Optional[str] = None
    error: Optional[str] = None
    state: DispatchState = DispatchState.IDLE


class LogitBiasMask:
    """
    Pre-Execution Firewall.
    Applies mathematical constraints at the logit level.
    """
    
    def __init__(self, mask_path: str):
        self.mask_path = Path(mask_path)
        self.mask_config: Dict = {}
        self._load()
    
    def _load(self):
        if self.mask_path.exists():
            with open(self.mask_path) as f:
                self.mask_config = json.load(f)
    
    def should_block(self, text: str) -> bool:
        """Check if text contains blocked patterns"""
        for pattern in self.mask_config.get("blocked_patterns", []):
            pat = pattern.get("pattern", "")
            if re.search(pat, text, re.IGNORECASE):
                return True
        return False
    
    def get_replacement(self, pattern: str) -> str:
        """Get replacement token for blocked pattern"""
        for p in self.mask_config.get("blocked_patterns", []):
            if p.get("pattern") == pattern:
                return p.get("replacement", "[REDACTED]")
        return "[REDACTED]"


class NeuralToolDispatcher:
    """
    MAIA Dispatcher: Watches Thinking Stream and Hot-Swaps Neural Contexts.
    
    Workflow:
    1. Detect tool intent in <|channel>thought
    2. Hot-swap LoRA adapter
    3. Apply logit bias
    4. Generate governed parameters
    5. Dispatch JSON-RPC
    """
    
    TOOL_CALL_PATTERN = re.compile(r"\[CALL_TOOL:\s*([\w_]+)\]")
    THOUGHT_START = "<|channel>thought"
    THOUGHT_END = "<|channel|>"
    
    def __init__(self, manifest_path: str = "configs/maia_kernel_manifest.json"):
        self.manifest_path = Path(manifest_path)
        self.manifest: Dict = {}
        self.tools: Dict[str, Dict] = {}
        self.active_tool: Optional[Dict] = None
        self.state = DispatchState.IDLE
        
        # Regex patterns
        self.tool_pattern = re.compile(r"\[CALL_TOOL:\s*([\w_]+)\]")
        
        # Logging
        self.logger = logging.getLogger("MAIA-Dispatcher")
        
        # Dispatch history
        self.dispatch_history: List[DispatchResult] = []
        
        self._load_manifest()
    
    def _load_manifest(self):
        """Load tool manifest"""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")
        
        with open(self.manifest_path) as f:
            self.manifest = json.load(f)
        
        for tool in self.manifest.get("registry", []):
            self.tools[tool["tool_id"]] = tool
    
    def detect_tool_intent(self, reasoning: str) -> Optional[ToolIntent]:
        """Detect tool call intent in reasoning stream"""
        match = self.TOOL_CALL_PATTERN.search(reasoning)
        
        if match:
            tool_id = match.group(1)
            tool_spec = self.tools.get(tool_id)
            
            if tool_spec:
                governance = tool_spec.get("governance_layer", {})
                return ToolIntent(
                    tool_id=tool_id,
                    reasoning_context=reasoning,
                    requires_dhitl=governance.get("dhitl_required", False)
                )
        
        return None
    
    def reconfigure_kernel(self, tool_id: str) -> bool:
        """
        Hot-swap neural context (LoRA + Logit Bias).
        
        Returns True if successful.
        """
        tool_spec = self.tools.get(tool_id)
        
        if not tool_spec:
            self.logger.error(f"Tool not found: {tool_id}")
            return False
        
        self.state = DispatchState.KERNEL_SWAP
        self.active_tool = tool_spec
        
        neural = tool_spec.get("neural_layer", {})
        adapter_id = neural.get("adapter_id")
        
        self.logger.info(f"KERNEL: Loading adapter {adapter_id} for {tool_id}")
        
        # In production, this would call LoRAX API:
        # requests.post(f"{LORAX_URL}/models/load", json={"model_id": adapter_id})
        
        return True
    
    def apply_logit_bias(self, tool_id: str) -> Optional[LogitBiasMask]:
        """Apply logit bias mask for tool"""
        tool_spec = self.tools.get(tool_id)
        
        if not tool_spec:
            return None
        
        neural = tool_spec.get("neural_layer", {})
        mask_path = neural.get("logit_bias_mask")
        
        if mask_path:
            return LogitBiasMask(mask_path)
        
        return None
    
    def check_governance(self, tool_id: str, generated_text: str) -> Dict[str, Any]:
        """
        Check generated text against governance constraints.
        """
        tool_spec = self.tools.get(tool_id)
        
        result = {
            "passed": True,
            "violations": [],
            "requires_dhitl": False
        }
        
        if not tool_spec:
            result["passed"] = False
            result["violations"].append("Tool not found")
            return result
        
        governance = tool_spec.get("governance_layer", {})
        
        # Check DHITL requirement
        if governance.get("dhitl_required"):
            result["requires_dhitl"] = True
            # In production, route to human approval queue
        
        # Apply logit bias check
        mask = self.apply_logit_bias(tool_id)
        if mask and mask.should_block(generated_text):
            result["passed"] = False
            result["violations"].append("Logit bias violation - blocked patterns detected")
        
        return result
    
    def build_rpc_payload(
        self,
        tool_id: str,
        params: Dict,
        forensic_hash: Optional[str] = None
    ) -> Dict:
        """Build JSON-RPC payload"""
        tool_spec = self.tools.get(tool_id)
        
        if not tool_spec:
            raise ValueError(f"Tool not found: {tool_id}")
        
        action = tool_spec.get("action_layer", {})
        
        rpc_params = params.copy()
        
        # Add forensic hash if required
        if governance := tool_spec.get("governance_layer"):
            if governance.get("required_forensic_hash") and forensic_hash:
                rpc_params["_forensic_hash"] = forensic_hash
        
        return {
            "jsonrpc": "2.0",
            "method": action.get("method"),
            "params": rpc_params,
            "id": self._generate_tx_id(tool_id, params)
        }
    
    def _generate_tx_id(self, tool_id: str, params: Dict) -> str:
        """Generate unique transaction ID"""
        data = f"{tool_id}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def generate_forensic_hash(self, tool_id: str, context: str) -> str:
        """Generate forensic hash for audit trail"""
        data = f"{tool_id}:{context}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def execute_dispatch(
        self,
        tool_id: str,
        generated_params: str,
        reasoning_context: str,
        query: str = ""
    ) -> DispatchResult:
        """
        Execute the full dispatch workflow.
        """
        self.state = DispatchState.EXECUTING
        
        tool_spec = self.tools.get(tool_id)
        
        if not tool_spec:
            return DispatchResult(
                success=False,
                tool_id=tool_id,
                error=f"Tool not found: {tool_id}",
                state=DispatchState.ERROR
            )
        
        # Check governance
        governance = self.check_governance(tool_id, generated_params)
        violations = governance.get("violations", [])
        
        # Log to forensics (SR 26-02 compliance)
        if FORENSICS_AVAILABLE:
            try:
                forensics = get_logger()
                governance_layer = tool_spec.get("governance_layer", {})
                tier = 1 if governance_layer.get("materiality") == "CRITICAL" else 2
                policy_id = governance_layer.get("airlock_policy", "default")
                
                forensics.log(
                    query=query or "dispatch",
                    thinking_block=reasoning_context[:500],
                    tool_id=tool_id,
                    tool_intent_detected=True,
                    policy_id=policy_id,
                    tier=tier,
                    violations=violations,
                    governance_passed=governance["passed"],
                    dhitl_required=governance.get("requires_dhitl", False),
                    response_denied=not governance["passed"],
                    blocked_reason=violations[0] if violations else None
                )
            except Exception as e:
                self.logger.warning(f"Forensics logging failed: {e}")
        
        if not governance["passed"]:
            return DispatchResult(
                success=False,
                tool_id=tool_id,
                error="; ".join(governance["violations"]),
                state=DispatchState.ERROR
            )
        
        # Generate forensic hash
        forensic_hash = self.generate_forensic_hash(tool_id, reasoning_context)
        
        # In production, execute RPC:
        # action = tool_spec.get("action_layer", {})
        # response = requests.post(action["endpoint"], json=rpc_payload)
        
        result = DispatchResult(
            success=True,
            tool_id=tool_id,
            forensic_hash=forensic_hash,
            rpc_response={"status": "simulated", "tool_id": tool_id},
            state=DispatchState.COMPLETE
        )
        
        self.dispatch_history.append(result)
        self.state = DispatchState.COMPLETE
        
        return result
    
    def process_stream_chunk(self, chunk: str, accumulator: str) -> Optional[ToolIntent]:
        """Process a chunk from reasoning stream"""
        accumulator += chunk
        
        # Check for tool intent in reasoning
        intent = self.detect_tool_intent(accumulator)
        
        if intent and self.state == DispatchState.REASONING:
            self.state = DispatchState.TOOL_DETECTED
            return intent
        
        # Track state
        if self.THOUGHT_START in accumulator:
            self.state = DispatchState.REASONING
        elif self.THOUGHT_END in accumulator:
            self.state = DispatchState.IDLE
        
        return None
    
    def list_tools(self) -> List[Dict]:
        """List all available tools"""
        return [
            {
                "id": t["tool_id"],
                "description": t.get("description"),
                "adapter": t.get("neural_layer", {}).get("adapter_id"),
                "materiality": t.get("governance_layer", {}).get("materiality"),
                "dhitl": t.get("governance_layer", {}).get("dhitl_required", False)
            }
            for t in self.tools.values()
        ]
    
    def get_stats(self) -> Dict:
        """Get dispatcher statistics"""
        return {
            "tools_registered": len(self.tools),
            "dispatches_total": len(self.dispatch_history),
            "dispatches_success": sum(1 for r in self.dispatch_history if r.success),
            "current_state": self.state.value,
            "active_tool": self.active_tool.get("tool_id") if self.active_tool else None
        }


def create_dispatcher(manifest_path: str = "configs/maia_kernel_manifest.json") -> NeuralToolDispatcher:
    """Factory function"""
    return NeuralToolDispatcher(manifest_path)


if __name__ == "__main__":
    dispatcher = create_dispatcher()
    
    print("=== MAIA Neural Tool Dispatcher ===\n")
    
    stats = dispatcher.get_stats()
    print(f"Tools Registered: {stats['tools_registered']}")
    print(f"Current State: {stats['current_state']}")
    
    print("\n=== Tool Intent Detection ===")
    test_reasoning = [
        "I need to send an email to the client. [CALL_TOOL:GOVERNED_SMTP_V1]",
        "Let me transfer funds to the subcontractor. [CALL_TOOL:FINANCIAL_WIRE_V1]",
        "Generating a forensic hash for the audit. [CALL_TOOL:AIBOM_FORENSIC_V1]"
    ]
    
    for reasoning in test_reasoning:
        intent = dispatcher.detect_tool_intent(reasoning)
        print(f"\nReasoning: {reasoning}")
        if intent:
            print(f"  -> Tool: {intent.tool_id}")
            print(f"  -> DHITL: {intent.requires_dhitl}")
        else:
            print(f"  -> No intent detected")
    
    print("\n=== Governance Check ===")
    check = dispatcher.check_governance("GOVERNED_SMTP_V1", "123-45-6789")
    print(f"PII in text: {check}")
    
    print("\n=== RPC Payload Builder ===")
    rpc = dispatcher.build_rpc_payload(
        "FINANCIAL_WIRE_V1",
        {"amount": 50000, "currency": "USD", "routing_number": "063000021", "account_number": "987654321", "motive_code": "INVOICE"},
        forensic_hash="audit123"
    )
    print(json.dumps(rpc, indent=2))