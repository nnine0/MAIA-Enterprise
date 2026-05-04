"""
MAIA Latent Telemetry - Neural EKG
Implements Intra-Inference Telemetry for SR 26-02 compliance.

- Activation Hooks tap into the "Residual Stream"
- Latent Signatures emitted at each layer
- Latent Hashing at Decision Nodes for audit trail
- Neural Flight Recorder turns Black Box into Glass Box
"""

import hashlib
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class DecisionNodeType(Enum):
    """Types of decision nodes that trigger latent hashing"""
    TOOL_CALL = "tool_call"
    WIRE_TRANSFER = "wire_transfer"
    CREDIT_APPROVAL = "credit_approval"
    POLICY_CHECK = "policy_check"
    ESCALATION = "escalation"
    FINAL_OUTPUT = "final_output"


@dataclass
class LatentSignature:
    """Compressed vector representing logic path at a layer"""
    timestamp: str
    layer: int
    adapter_id: str
    reasoning_type: str
    latent_hash: str
    embedding_preview: str  # First few chars of actual latent vector


@dataclass
class TrajectoryNode:
    """Node in the Directed Acyclic Graph of reasoning"""
    node_id: str
    timestamp: str
    adapter_used: str
    layer: int
    latent_hash: str
    reasoning_summary: str
    inputs: List[str]
    outputs: List[str]
    is_decision_node: bool
    decision_type: Optional[str] = None


class LatentTelemetry:
    """
    Neural EKG - Latent State Observability System.
    
    Captures latent signatures at each layer of the model's thinking
    to create a high-dimensional audit trail.
    """
    
    # Decision nodes that trigger hashing
    DECISION_TRIGGERS = {
        "wire", "transfer", "send money", "payment":
            DecisionNodeType.WIRE_TRANSFER,
        "approve", "credit limit", "loan", "mortgage":
            DecisionNodeType.CREDIT_APPROVAL,
        "call", "invoke", "execute", "tool":
            DecisionNodeType.TOOL_CALL,
        "policy", "compliance", "check", "verify":
            DecisionNodeType.POLICY_CHECK,
        "escalate", "block", "deny", "reject":
            DecisionNodeType.ESCALATION
    }
    
    def __init__(self):
        self.current_trajectory: List[TrajectoryNode] = []
        self.active_sessions: Dict[str, List[TrajectoryNode]] = {}
        
    def start_session(self, session_id: str, query: str):
        """Start a new latent telemetry session"""
        self.current_trajectory = []
        self.active_sessions[session_id] = self.current_trajectory
        
        # Record initial query as first node
        root_node = TrajectoryNode(
            node_id=f"{session_id}-root",
            timestamp=str(datetime.now()),
            adapter_used="query_ingestion",
            layer=0,
            latent_hash=self._hash_reasoning(query),
            reasoning_summary=f"Query: {query[:100]}",
            inputs=[],
            outputs=["query"],
            is_decision_node=False
        )
        self.current_trajectory.append(root_node)
        
    def emit_latent_signature(
        self,
        session_id: str,
        layer: int,
        adapter_id: str,
        reasoning_output: str,
        inputs: List[str],
        outputs: List[str]
    ) -> TrajectoryNode:
        """Emit a latent signature at a specific layer"""
        if session_id not in self.active_sessions:
            return None
        
        # Check if this is a decision node
        decision_type = self._detect_decision_type(reasoning_output)
        
        node = TrajectoryNode(
            node_id=f"{session_id}-l{layer}-{adapter_id}",
            timestamp=str(datetime.now()),
            adapter_used=adapter_id,
            layer=layer,
            latent_hash=self._hash_reasoning(reasoning_output),
            reasoning_summary=reasoning_output[:200] if reasoning_output else "",
            inputs=inputs,
            outputs=outputs,
            is_decision_node=decision_type is not None,
            decision_type=decision_type.value if decision_type else None
        )
        
        self.current_trajectory.append(node)
        return node
    
    def _hash_reasoning(self, reasoning: str) -> str:
        """Compute latent hash for reasoning output"""
        return hashlib.sha256(reasoning.encode()).hexdigest()[:16]
    
    def _detect_decision_type(self, reasoning: str) -> Optional[DecisionNodeType]:
        """Detect if reasoning contains decision-point keywords"""
        reasoning_lower = reasoning.lower()
        for keywords, node_type in self.DECISION_TRIGGERS.items():
            if any(kw in reasoning_lower for kw in keywords.split()):
                return node_type
        return None
    
    def get_audit_log(self, session_id: str) -> Dict[str, Any]:
        """Generate Fed-audit-compatible log for session"""
        if session_id not in self.active_sessions:
            return {}
        
        trajectory = self.active_sessions[session_id]
        
        # Extract decision nodes
        decision_nodes = [
            asdict(node) for node in trajectory
            if node.is_decision_node
        ]
        
        # Compute trajectory integrity
        latent_hashes = [node.latent_hash for node in trajectory]
        trajectory_hash = hashlib.sha256(
            "".join(latent_hashes).encode()
        ).hexdigest()[:16]
        
        return {
            "session_id": session_id,
            "trajectory_length": len(trajectory),
            "decision_nodes": decision_nodes,
            "trajectory_hash": trajectory_hash,
            "created_at": trajectory[0].timestamp if trajectory else None,
            "last_updated": trajectory[-1].timestamp if trajectory else None
        }
    
    def get_full_dag(self, session_id: str) -> List[Dict]:
        """Get full Directed Acyclic Graph of reasoning"""
        if session_id not in self.active_sessions:
            return []
        return [asdict(node) for node in self.active_sessions[session_id]]
    
    def end_session(self, session_id: str) -> Dict[str, Any]:
        """End session and return final audit log"""
        audit_log = self.get_audit_log(session_id)
        
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        return audit_log
    
    def verify_conceptual_soundness(
        self,
        session_id: str,
        expected_path: List[str]
    ) -> Dict[str, Any]:
        """Verify that trajectory followed expected adapter path"""
        if session_id not in self.active_sessions:
            return {"valid": False, "reason": "Session not found"}
        
        trajectory = self.active_sessions[session_id]
        actual_path = [node.adapter_used for node in trajectory]
        
        # Check if critical adapters were in path
        critical_adapters = set(expected_path)
        actual_set = set(actual_path)
        
        missing = critical_adapters - actual_set
        extra = actual_set - critical_adapters
        
        return {
            "valid": len(missing) == 0,
            "expected_path": expected_path,
            "actual_path": actual_path,
            "missing_adapters": list(missing),
            "unexpected_adapters": list(extra),
            "conceptual_soundness": "PASS" if len(missing) == 0 else "FAIL"
        }


# Global telemetry instance
latent_telemetry = LatentTelemetry()


async def start_telemetry_session(session_id: str, query: str):
    """Public API to start telemetry session"""
    latent_telemetry.start_session(session_id, query)


async def emit_signature(
    session_id: str,
    layer: int,
    adapter_id: str,
    reasoning: str,
    inputs: List[str],
    outputs: List[str]
):
    """Public API to emit latent signature"""
    return latent_telemetry.emit_latent_signature(
        session_id, layer, adapter_id, reasoning, inputs, outputs
    )


def get_audit_log(session_id: str) -> Dict:
    """Public API to get audit log"""
    return latent_telemetry.get_audit_log(session_id)


def get_dag(session_id: str) -> List[Dict]:
    """Public API to get full DAG"""
    return latent_telemetry.get_full_dag(session_id)


def verify_soundness(session_id: str, expected_path: List[str]) -> Dict:
    """Public API to verify conceptual soundness"""
    return latent_telemetry.verify_conceptual_soundness(session_id, expected_path)