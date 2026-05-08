"""
MAIA DAG Orchestrator - Event-Driven Workflow Execution
Implements async orchestration with parallel streams and convergence points.

- Stream A (Identity): Identity-Verification + Sanctions-Screening (Parallel)
- Stream B (Financials): Income-Analysis + Asset-Valuation (Parallel)
- Convergence Point: Debt-to-Equity-Math (waits for both streams)
- Speculative Execution: Draft while waiting
- Information Request Interrupt: Yield and park workflow
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class NodeStatus(Enum):
    """Workflow node status"""
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"  # Waiting for dependency
    COMPLETED = "completed"
    FAILED = "failed"
    YIELDED = "yielded"  # Waiting for external input
    PARKED = "parked"    # Waiting for external data


class StreamType(Enum):
    """Types of workflow streams"""
    IDENTITY = "identity"     # KYC, Sanctions
    FINANCIALS = "financials"  # Income, Assets
    COMPLIANCE = "compliance"  # Policy checks
    EXECUTION = "execution"   # Final action


@dataclass
class WorkflowNode:
    """Node in the DAG workflow"""
    node_id: str
    node_type: str
    adapter_id: str
    dependencies: List[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    input_data: Dict = field(default_factory=dict)
    output_data: Dict = field(default_factory=dict)
    error: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@dataclass
class Workflow:
    """Complete workflow with DAG"""
    workflow_id: str
    nodes: Dict[str, WorkflowNode] = field(default_factory=dict)
    streams: Dict[str, List[str]] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: str(datetime.now()))
    status: str = "running"


class DAGOrchestrator:
    """
    Event-Driven DAG Orchestrator for MAIA.
    
    Manages parallel streams with convergence points,
    speculative execution, and information request interrupts.
    """
    
    # Default workflow templates
    CREDIT_WORKFLOW = {
        "streams": {
            "identity": ["kyc_verification", "sanctions_screening"],
            "financials": ["income_analysis", "asset_valuation"],
            "compliance": ["policy_validation"],
            "execution": ["credit_decision"]
        },
        "convergence": {
            "debt_equity_math": ["income_analysis", "asset_valuation"]
        }
    }
    
    def __init__(self):
        self.active_workflows: Dict[str, Workflow] = {}
        self.completed_workflows: Dict[str, Workflow] = {}
        
    async def create_workflow(
        self,
        workflow_type: str,
        initial_data: Dict
    ) -> str:
        """Create a new workflow from template"""
        workflow_id = f"{workflow_type}-{uuid.uuid4().hex[:8]}"
        
        template = self.CREDIT_WORKFLOW if workflow_type == "credit" else {}
        
        workflow = Workflow(workflow_id=workflow_id)
        
        # Create nodes from template
        for stream_name, node_ids in template.get("streams", {}).items():
            workflow.streams[stream_name] = node_ids
            for node_id in node_ids:
                workflow.nodes[node_id] = WorkflowNode(
                    node_id=node_id,
                    node_type=stream_name,
                    adapter_id=self._get_adapter_for_node(node_id)
                )
        
        # Set initial data for root nodes
        if "kyc_verification" in workflow.nodes:
            workflow.nodes["kyc_verification"].input_data = initial_data
        
        self.active_workflows[workflow_id] = workflow
        return workflow_id
    
    def _get_adapter_for_node(self, node_id: str) -> str:
        """Map node to adapter"""
        adapter_map = {
            "kyc_verification": "kyc-verifier",
            "sanctions_screening": "sanctions-list-sme",
            "income_analysis": "cash-flow-sme",
            "asset_valuation": "collateral-valuator",
            "debt_equity_math": "credit-expert-v4",
            "policy_validation": "pvi-airlock-sr2602",
            "credit_decision": "credit-expert-v4"
        }
        return adapter_map.get(node_id, "default-expert")
    
    async def execute_node(
        self,
        workflow_id: str,
        node_id: str,
        executor: Callable
    ) -> Dict:
        """Execute a single node"""
        if workflow_id not in self.active_workflows:
            return {"error": "Workflow not found"}
        
        workflow = self.active_workflows[workflow_id]
        if node_id not in workflow.nodes:
            return {"error": "Node not found"}
        
        node = workflow.nodes[node_id]
        
        # Check dependencies
        if not await self._check_dependencies(workflow, node):
            node.status = NodeStatus.WAITING
            return {"status": "waiting", "reason": "Dependencies not met"}
        
        # Execute
        node.status = NodeStatus.RUNNING
        node.start_time = str(datetime.now())
        
        try:
            result = await executor(node.input_data)
            node.output_data = result
            node.status = NodeStatus.COMPLETED
            node.end_time = str(datetime.now())
            return {"status": "completed", "output": result}
        except Exception as e:
            node.status = NodeStatus.FAILED
            node.error = str(e)
            return {"status": "failed", "error": str(e)}
    
    async def _check_dependencies(self, workflow: Workflow, node: WorkflowNode) -> bool:
        """Check if node dependencies are satisfied"""
        if not node.dependencies:
            return True
        
        for dep_id in node.dependencies:
            if dep_id not in workflow.nodes:
                continue
            if workflow.nodes[dep_id].status != NodeStatus.COMPLETED:
                return False
        return True
    
    async def execute_parallel_stream(
        self,
        workflow_id: str,
        stream_name: str,
        executor: Callable
    ) -> List[Dict]:
        """Execute all nodes in a stream in parallel"""
        if workflow_id not in self.active_workflows:
            return []
        
        workflow = self.active_workflows[workflow_id]
        node_ids = workflow.streams.get(stream_name, [])
        
        tasks = [
            self.execute_node(workflow_id, node_id, executor)
            for node_id in node_ids
        ]
        
        return await asyncio.gather(*tasks)
    
    async def execute_with_convergence(
        self,
        workflow_id: str,
        convergence_node: str,
        dependency_streams: List[str],
        executor: Callable
    ) -> Dict:
        """
        Execute convergence node after all dependency streams complete.
        """
        # First execute all dependency streams in parallel
        for stream in dependency_streams:
            await self.execute_parallel_stream(workflow_id, stream, executor)
        
        # Now execute convergence node
        return await self.execute_node(workflow_id, convergence_node, executor)
    
    async def yield_node(
        self,
        workflow_id: str,
        node_id: str,
        yield_reason: str,
        external_action: Callable
    ):
        """
        Yield a node - emit interrupt, trigger external action, park workflow.
        GPU is NOT blocked - continues to next transaction.
        """
        if workflow_id not in self.active_workflows:
            return
        
        workflow = self.active_workflows[workflow_id]
        node = workflow.nodes.get(node_id)
        
        if not node:
            return
        
        # Emit yield signal
        node.status = NodeStatus.YIELDED
        
        # Trigger external action (e.g., send email to client)
        await external_action(node.input_data)
        
        # Park the workflow
        node.status = NodeStatus.PARKED
        
        print(f"[DAG] Node {node_id} YIELDED: {yield_reason}. Workflow parked.")
    
    def get_workflow_status(self, workflow_id: str) -> Dict:
        """Get workflow status"""
        if workflow_id not in self.active_workflows:
            return {"error": "Not found"}
        
        workflow = self.active_workflows[workflow_id]
        return {
            "workflow_id": workflow_id,
            "status": workflow.status,
            "streams": {
                stream: [
                    {"node": node_id, "status": node.status.value}
                    for node_id in node_ids
                ]
                for stream, node_ids in workflow.streams.items()
            },
            "created_at": workflow.created_at
        }
    
    def get_all_workflows(self) -> List[str]:
        """Get all active workflow IDs"""
        return list(self.active_workflows.keys())


# Global orchestrator instance
dag_orchestrator = DAGOrchestrator()


async def create_workflow(workflow_type: str, initial_data: Dict) -> str:
    """Public API to create workflow"""
    return await dag_orchestrator.create_workflow(workflow_type, initial_data)


async def execute_stream(workflow_id: str, stream_name: str, executor: Callable) -> List[Dict]:
    """Public API to execute parallel stream"""
    return await dag_orchestrator.execute_parallel_stream(workflow_id, stream_name, executor)


async def execute_with_convergence(
    workflow_id: str,
    convergence_node: str,
    dependency_streams: List[str],
    executor: Callable
) -> Dict:
    """Public API to execute with convergence"""
    return await dag_orchestrator.execute_with_convergence(
        workflow_id, convergence_node, dependency_streams, executor
    )


def get_workflow_status(workflow_id: str) -> Dict:
    """Public API to get workflow status"""
    return dag_orchestrator.get_workflow_status(workflow_id)