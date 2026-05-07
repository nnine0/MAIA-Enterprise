"""
MAIA Triage Supervisor & Governance Levels
======================================
Implements:
1. Triage Agent - lightweight entry point
2. Governor-Lite Mode - GL-1 to GL-3 governance levels
3. Deterministic Offloading - symbolic scripts for predictable tasks
4. Shared Context - tools instead of agent handoffs

Run: python3 -m app.triage_supervisor
"""

import asyncio
import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class GovernanceLevel(Enum):
    """Governance levels - complexity slider"""
    GL_1_TRANSACTIONAL = 1  # Single agent, bypass gates
    GL_2_OPERATIONAL = 2     # Sequential pipeline
    GL_3_STRATEGIC = 3      # Full multi-agent


class TaskComplexity(Enum):
    """Task complexity classification"""
    SIMPLE = "simple"         # Fast track - single agent
    MODERATE = "moderate"    # Sequential pipeline
    COMPLEX = "complex"       # Full multi-agent


# Deterministic scripts for predictable tasks
DETERMINISTIC_SCRIPTS = {
    "sql_query": {
        "type": "script",
        "predictable": True,
        "handler": "execute_sql",
        "replace_agent": True,
    },
    "format_json": {
        "type": "script", 
        "predictable": True,
        "handler": "format_json",
        "replace_agent": True,
    },
    "send_email": {
        "type": "script",
        "predictable": True,
        "handler": "smtp_send",
        "replace_agent": True,
    },
    "lookup_database": {
        "type": "function",
        "predictable": True,
        "handler": "db_lookup",
        "replace_agent": True,
    },
    "validate_format": {
        "type": "function",
        "predictable": True,
        "handler": "validate_schema",
        "replace_agent": True,
    },
}


class TriageSupervisor:
    """
    Lightweight supervisor - Entry point for all requests.
    
    Determines:
    - Task complexity
    - Governance level needed
    - Routing (fast track vs full pipeline)
    """
    
    # Keywords for fast track
    FAST_TRACK_KEYWORDS = [
        "summarize", "list", "find", "search", "get", "show",
        "check database", "lookup", "query", "format"
    ]
    
    # Keywords requiring full governance
    HIGH_STAKES_KEYWORDS = [
        "wire", "transfer", "approve", "deny", "execute",
        "delete", "modify", "create user", "grant access"
    ]
    
    def __init__(self, default_gl: GovernanceLevel = GovernanceLevel.GL_2_OPERATIONAL):
        self.default_gl = default_gl
    
    def classify_task(self, query: str) -> TaskComplexity:
        """Classify task complexity"""
        query_lower = query.lower()
        
        # Simple - fast track
        if any(kw in query_lower for kw in self.FAST_TRACK_KEYWORDS):
            # But check if it's high stakes
            if any(kw in query_lower for kw in self.HIGH_STAKES_KEYWORDS):
                return TaskComplexity.COMPLEX
            return TaskComplexity.SIMPLE
        
        # High stakes always complex
        if any(kw in query_lower for kw in self.HIGH_STAKES_KEYWORDS):
            return TaskComplexity.COMPLEX
        
        # Default to moderate
        return TaskComplexity.MODERATE
    
    def determine_gl(self, query: str, user_specified: Optional[GovernanceLevel] = None) -> GovernanceLevel:
        """Determine governance level needed"""
        if user_specified:
            return user_specified
        
        complexity = self.classify_task(query)
        
        if complexity == TaskComplexity.SIMPLE:
            return GovernanceLevel.GL_1_TRANSACTIONAL
        elif complexity == TaskComplexity.MODERATE:
            return GovernanceLevel.GL_2_OPERATIONAL
        else:
            return GovernanceLevel.GL_3_STRATEGIC
    
    def should_deterministic(self, query: str) -> Optional[str]:
        """Check if deterministic offloading applies"""
        query_lower = query.lower()
        
        for script_name, config in DETERMINISTIC_SCRIPTS.items():
            if script_name.replace("_", " ") in query_lower:
                return script_name
        
        return None
    
    def route(self, query: str, user_gl: Optional[GovernanceLevel] = None) -> Dict[str, Any]:
        """
        Route request to appropriate path.
        
        Returns routing decision with metadata.
        """
        complexity = self.classify_task(query)
        gl = self.determine_gl(query, user_gl)
        deterministic = self.should_deterministic(query)
        
        # Determine route
        if deterministic:
            route = "deterministic"
            agents_needed = 0
        elif complexity == TaskComplexity.SIMPLE:
            route = "fast_track"
            agents_needed = 1
        elif complexity == TaskComplexity.MODERATE:
            route = "sequential"
            agents_needed = 2
        else:
            route = "full_pipeline"
            agents_needed = 5  # Multi-agent
        
        return {
            "route": route,
            "complexity": complexity.value,
            "governance_level": gl.value,
            "agents_needed": agents_needed,
            "deterministic_script": deterministic,
            "latency_estimate_ms": agents_needed * 50 + (100 if gl == GovernanceLevel.GL_3_STRATEGIC else 0),
        }


class SymbolicExecutor:
    """
    Deterministic executor - runs scripts instead of agents.
    """
    
    def __init__(self):
        self.results: List[Dict] = []
    
    async def execute(self, script_name: str, params: Dict) -> Dict:
        """Execute deterministic script"""
        start = datetime.now()
        
        # Simulate script execution
        result = {
            "script": script_name,
            "status": "success",
            "output": f"Executed {script_name}",
            "latency_ms": 10,  # Very fast
            "timestamp": start.isoformat(),
        }
        
        self.results.append(result)
        return result
    
    def can_handle(self, query: str) -> Optional[str]:
        """Check if query can be handled deterministically"""
        return TriageSupervisor().should_deterministic(query)


class SharedContextAgent:
    """
    Single agent with tools - replaces agent handoffs.
    
    Instead of Agent A -> Agent B -> Agent C,
    use Agent A with tools=[search, format, validate]
    """
    
    def __init__(self, name: str, tools: List[str]):
        self.name = name
        self.tools = tools
        self.context: Dict = {}
    
    def add_tool(self, tool: str):
        """Add tool to agent"""
        if tool not in self.tools:
            self.tools.append(tool)
    
    async def execute(self, query: str, deterministic_script: Optional[str] = None) -> Dict:
        """Execute with shared context"""
        
        # Build execution plan
        plan = {
            "agent": self.name,
            "tools_used": self.tools.copy(),
            "context": self.context,
            "deterministic": deterministic_script is not None,
        }
        
        # Simulate execution
        return {
            "status": "success",
            "query": query,
            "execution_plan": plan,
            "handoffs": 0,  # No handoffs - single agent
            "latency_ms": len(self.tools) * 20,
        }


async def demo():
    print("="*60)
    print("MAIA Triage Supervisor & Governance Levels")
    print("="*60)
    
    supervisor = TriageSupervisor()
    executor = SymbolicExecutor()
    
    # Test queries
    print("\n[1] Triage Classification")
    test_queries = [
        "Summarize this document",
        "Wire $50k to Russia",
        "Query database for vendor",
        "Approve loan application",
    ]
    
    for query in test_queries:
        route = supervisor.route(query)
        print(f"\n  Query: {query}")
        print(f"  Route: {route['route']}")
        print(f"  Complexity: {route['complexity']}")
        print(f"  GL Level: {route['governance_level']}")
        print(f"  Agents needed: {route['agents_needed']}")
    
    # Deterministic offloading
    print("\n[2] Deterministic Offloading")
    det_queries = [
        "Run SQL query select * from vendors",
        "Format this data as JSON",
        "Send email to team",
    ]
    
    for query in det_queries:
        det = supervisor.should_deterministic(query)
        print(f"  '{query[:25]}...' -> deterministic: {det}")
    
    # Governance levels
    print("\n[3] Governance Levels (GL)")
    for gl in GovernanceLevel:
        print(f"  GL-{gl.value}: {gl.name}")
    
    # Shared context agent
    print("\n[4] Shared Context Agent")
    agent = SharedContextAgent("QueryAgent", tools=["sql_query", "format_json"])
    result = await agent.execute("Get vendor list")
    print(f"  Agent: {result['execution_plan']['agent']}")
    print(f"  Tools: {result['execution_plan']['tools_used']}")
    print(f"  Handoffs: {result['handoffs']} (no agent chains)")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(demo())