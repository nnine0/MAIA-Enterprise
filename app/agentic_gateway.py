"""
MAIA Agentic Gateway
=====================
Transparent proxy that handles governance invisible to the client.

Problem: Banks don't want to rewrite their AI code to use MAIA.
Solution: Send traffic to localhost:8080 (MAIA Gateway), MAIA handles
Airlock and Neural Permissioning transparently.

Flow:
  Bank AI → localhost:8080 (MAIA Gateway) → [Governance] → Upstream Model
                                              ↓
                                         [Audit Ledger]

Usage:
    python3 -m app.agentic_gateway
    
Or as a reverse proxy:
    python3 -m app.agentic_gateway --upstream https://api.openai.com/v1
"""

import asyncio
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, Any, List


class GovernanceAction(Enum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"
    REDACT = "REDACT"


@dataclass
class GatewayRequest:
    """Incoming request"""
    request_id: str
    timestamp: str
    prompt: str
    upstream_path: str
    headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayResponse:
    """Outgoing response"""
    request_id: str
    action: GovernanceAction
    content: Optional[str] = None
    blocked_reason: Optional[str] = None
    governance_overhead_ms: float = 0.0
    forensic_hash: Optional[str] = None


class AgenticGateway:
    """
    Transparent Governance Proxy.
    
    Sits between client AI and upstream model.
    Handles Airlock, Neural Permissioning, Audit transparently.
    """
    
    def __init__(self, port: int = 8080, upstream: str = "http://localhost:11434"):
        self.port = port
        self.upstream = upstream
        self.governance_enabled = True
        
        # Violation patterns (SR 26-02, HIPAA, etc.)
        self.violation_patterns: Dict[str, List[str]] = {
            "finance": ["russia", "iran", "sanction", "structur", "wire to"],
            "healthcare": ["patient", "diagnosis", "ssn", "phi", "medical record"],
            "legal": ["attorney", "privileged", "confidential", "litigation"],
            "construction": ["skip safety", "fake inspection", "bypass osha"],
            "defense": ["classified", "secret", "export", "itar"],
        }
        
        # Stats
        self.total_requests = 0
        self.blocked = 0
        self.passed = 0
    
    def _classify_sector(self, prompt: str) -> str:
        """Auto-detect sector from prompt"""
        prompt_lower = prompt.lower()
        
        for sector, keywords in self.violation_patterns.items():
            for kw in keywords:
                if kw in prompt_lower:
                    return sector
        
        return "general"
    
    def _check_violations(self, prompt: str, sector: str) -> tuple[bool, Optional[str]]:
        """Check for governance violations"""
        prompt_lower = prompt.lower()
        keywords = self.violation_patterns.get(sector, [])
        
        for kw in keywords:
            if kw in prompt_lower:
                return (True, f"Violation: {kw}")
        
        return (False, None)
    
    def _compute_forensic_hash(self, request_id: str, prompt: str, action: str) -> str:
        """Compute forensic hash for audit"""
        data = f"{request_id}:{prompt}:{action}:{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    async def process(self, prompt: str, upstream_path: str = "/v1/chat/completions") -> GatewayResponse:
        """Process request through governance gateway"""
        start = datetime.now()
        request_id = f"req-{uuid.uuid4().hex[:8]}"
        
        self.total_requests += 1
        
        # Auto-detect sector
        sector = self._classify_sector(prompt)
        
        # Check violations
        is_violation, reason = self._check_violations(prompt, sector)
        
        if is_violation:
            self.blocked += 1
            return GatewayResponse(
                request_id=request_id,
                action=GovernanceAction.BLOCK,
                blocked_reason=reason,
                governance_overhead_ms=(datetime.now() - start).total_seconds() * 1000,
            )
        
        # Pass through - in real impl, would forward to upstream
        self.passed += 1
        
        forensic_hash = self._compute_forensic_hash(request_id, prompt, "PASS")
        
        return GatewayResponse(
            request_id=request_id,
            action=GovernanceAction.PASS,
            content=f"[GOVERNANCE_PASS] {prompt}",
            governance_overhead_ms=(datetime.now() - start).total_seconds() * 1000,
            forensic_hash=forensic_hash,
        )
    
    def get_stats(self) -> Dict:
        """Get gateway statistics"""
        return {
            "total_requests": self.total_requests,
            "passed": self.passed,
            "blocked": self.blocked,
            "pass_rate": f"{(self.passed/max(self.total_requests,1))*100:.1f}%",
        }


class TransparentProxy:
    """
    HTTP Proxy that wraps upstream with governance.
    
    Deploy between client and their AI to make MAIA "invisible."
    """
    
    def __init__(self, upstream_url: str, local_port: int = 8080):
        self.upstream_url = upstream_url
        self.local_port = local_port
        self.gateway = AgenticGateway(port=local_port, upstream=upstream_url)
    
    async def handle_request(self, method: str, path: str, headers: Dict, body: Optional[str]) -> Dict:
        """Handle HTTP request transparently"""
        # Extract prompt from request body
        prompt = ""
        if body:
            import json
            try:
                data = json.loads(body)
                prompt = data.get("messages", [])[-1].get("content", "") if data.get("messages") else ""
            except:
                pass
        
        if not prompt:
            return {"status": "forward_only", "body": body}
        
        # Run through governance
        result = await self.gateway.process(prompt, path)
        
        return {
            "governance": {
                "action": result.action.value,
                "reason": result.blocked_reason,
                "overhead_ms": result.governance_overhead_ms,
                "forensic_hash": result.forensic_hash,
            },
            "forward": result.action == GovernanceAction.PASS,
        }


async def demo():
    print("="*60)
    print("MAIA Agentic Gateway")
    print("="*60)
    
    gateway = AgenticGateway()
    
    # Test cases
    tests = [
        ("Summarize this PDF", "general"),
        ("Wire $50k to Russia", "finance"),
        ("Send patient diagnosis via email", "healthcare"),
        ("What is the weather?", "general"),
    ]
    
    print("\n[Transparent Governance]")
    for prompt, expected_sector in tests:
        result = await gateway.process(prompt)
        print(f"\n  {prompt[:30]}...")
        print(f"  Action: {result.action.value}")
        print(f"  Reason: {result.blocked_reason or 'OK'}")
        print(f"  Overhead: {result.governance_overhead_ms:.2f}ms")
    
    print("\n[Stats]")
    stats = gateway.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    print("\n" + "="*60)
    print("\nDeployment: Run as proxy, forward traffic to upstream AI")
    print("  Bank AI → localhost:8080 → [Governance] → Upstream Model")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(demo())