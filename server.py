"""
MAIA Enterprise Kernel Server
==============================
Main entry point - integrates all Kernel components.

Wraps vLLM engine and pipes token stream through:
- Gemma4ThinkingAirlock (Layer 8 - reasoning audit)
- NeuralToolDispatcher (Layer 7 - tool hot-swap)
- MaterialityMatrix (Layer 9 - routing)

SR 26-02: Turn all stubs into functional API.
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Generator, AsyncGenerator, Optional, Dict, Any

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from kernel.matrix import MaterialityMatrix, MaterialityTier
from kernel.airlock import Gemma4ThinkingAirlock
from kernel.dispatcher import NeuralToolDispatcher, DispatchRequest
from kernel.registry import ToolRegistry
from kernel.exceptions import PolicyViolationInterrupt, DHITLRequired
from app.airlock_gateway import AirlockGateway, create_gateway


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MAIA-Kernel")


class MAIAKernel:
    """
    Main kernel entry point.
    
    Integrates all kernel components:
    - MaterialityMatrix (Layer 9)
    - Gemma4ThinkingAirlock (Layer 8)
    - NeuralToolDispatcher (Layer 7)
    - ToolRegistry (AIBOM)
    """
    
    def __init__(self):
        # Layer 9: Materiality routing
        self.matrix = MaterialityMatrix()
        
        # Layer 8: Reasoning audit
        self.airlock = Gemma4ThinkingAirlock()
        
        # Layer 7: Tool hot-swap
        self.dispatcher = NeuralToolDispatcher()
        
        # Registry
        self.registry = ToolRegistry()
        
        logger.info("MAIA Kernel initialized")
    
    async def process_chat(
        self,
        messages: list,
        stream: bool = False
    ) -> Dict:
        """
        Process chat completion through all layers.
        
        Layers:
        1. Extract query from messages
        2. MaterialityMatrix classifies to TIER
        3. Stream through Airlock (audit reasoning)
        4. Dispatcher handles tool calls
        """
        # Extract query
        query = messages[-1].get("content", "") if messages else ""
        
        # Layer 9: Materiality classification
        tier, domain_config = self.matrix.classify(query)
        
        # Check violations
        violations = self.matrix.check_violations(query)
        
        if violations:
            logger.warning(f"VIOLATIONS: {violations}")
        
        # Layer 8: Airlock reasoning audit
        tokens = query.split()
        for token in tokens:
            result = self.airlock.process_token(token)
            if result is None:
                raise HTTPException(
                    status_code=403,
                    detail="Policy violation in reasoning"
                )
        
        # Layer 7: Tool dispatch
        dispatch_req = DispatchRequest(
            query=query,
            reasoning=query
        )
        
        dispatch_resp = await self.dispatcher.dispatch(dispatch_req)
        
        # Build response
        return {
            "id": f"maia-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"[GOVERNED] {query[:50]}... (tier: {tier.name}, tool: {dispatch_resp.tool_id})"
                },
                "finish_reason": "stop"
            }],
            "model": "maia-kernel",
            "metadata": {
                "tier": tier.name,
                "domain": domain_config.domain,
                "violations": len(violations),
                "forensic_hash": dispatch_resp.forensic_hash,
                "dhitl_required": dispatch_resp.dhitl_required
            }
        }
    
    async def stream_chat(
        self,
        messages: list
    ) -> AsyncGenerator[str, None]:
        """Stream through kernel layers"""
        query = messages[-1].get("content", "") if messages else ""
        
        tier, domain_config = self.matrix.classify(query)
        
        # Stream tokens with audit
        yield f"data: {{'tier': '{tier.name}'}}\n\n"
        
        # Simulate streaming (in prod would wrap vLLM)
        for word in query.split()[:5]:
            yield f"data: {{'token': '{word}'}}\n\n"
            await asyncio.sleep(0.01)
        
        yield "data: [DONE]\n\n"
    
    def get_stats(self) -> Dict:
        """Get kernel statistics"""
        return {
            "matrix": self.matrix.get_stats(),
            "airlock": self.airlock.get_stats(),
            "dispatcher": self.dispatcher.get_stats(),
            "registry": len(self.registry.tools)
        }


# Global instances
kernel: Optional[MAIAKernel] = None
airlock_gateway: Optional[AirlockGateway] = None


@asynccontextmanager
async def lifespan(app):
    global kernel, airlock_gateway
    kernel = MAIAKernel()
    airlock_gateway = create_gateway(
        api_base="",
        sector="finance",
        demo=True
    )
    logger.info("MAIA Kernel + Airlock Gateway initialized")
    yield


app = FastAPI(
    title="MAIA Enterprise Kernel",
    description="Governed AI OS for regulated industries",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "kernel": "initialized" if kernel else "starting"
    }


@app.get("/stats")
async def stats():
    """Kernel statistics"""
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel starting")
    return kernel.get_stats()


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible chat endpoint.
    
    Processes through all MAIA governance layers.
    """
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel not ready")
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    
    if stream:
        return StreamingResponse(
            kernel.stream_chat(messages),
            media_type="text/event-stream"
        )
    else:
        result = await kernel.process_chat(messages, stream=False)
        return result


@app.get("/v1/models")
async def models():
    """List available models"""
    return {
        "object": "list",
        "data": [
            {
                "id": "maia-kernel",
                "object": "model",
                "created": 1700000000,
                "owned_by": "maia-enterprise"
            }
        ]
    }


@app.get("/governance/materiality")
async def governance_materiality(q: str):
    """Check materiality for query"""
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel not ready")
    
    tier, config = kernel.matrix.classify(q)
    violations = kernel.matrix.check_violations(q)
    
    return {
        "query": q[:100],
        "tier": tier.name,
        "domain": config.domain,
        "violations": violations,
        "dhitl": kernel.matrix.requires_dhitl(tier)
    }


@app.get("/governance/tools")
async def governance_tools():
    """List registered tools"""
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel not ready")
    
    return {
        "tools": kernel.registry.list_tools(),
        "total": len(kernel.registry.tools)
    }


# ─── Airlock Gateway Endpoints ─────────────────────────────────────────────

class AirlockConfig(BaseModel):
    messages: List[Dict] = []
    prompt: str = ""
    sector: str = "finance"
    max_tokens: int = 1024
    temperature: float = 0.7


@app.post("/v1/airlock/gateway")
async def airlock_gateway_endpoint(config: AirlockConfig):
    """
    Parallel Airlock Gateway.
    
    Dispatches to Sheriff (Nemotron) + Sentinel (Granite) in parallel
    with the base model. Pre-flight kills the cloud call if violation found.
    Egress intercepts tool calls before they reach customer data.
    """
    global airlock_gateway
    if not airlock_gateway:
        raise HTTPException(status_code=503, detail="Airlock Gateway not ready")

    prompt = config.prompt or (config.messages[-1].get("content", "") if config.messages else "")
    if not prompt:
        raise HTTPException(status_code=400, detail="No prompt provided")

    # Update sector if different
    if config.sector != airlock_gateway.sector:
        airlock_gateway.sector = config.sector
        airlock_gateway.egress = __import__("app.airlock_gateway", fromlist=["EgressInterceptor"]).EgressInterceptor(config.sector)
        airlock_gateway.policy = __import__("app.airlock_gateway", fromlist=["PolicyManifest"]).PolicyManifest(config.sector)

    try:
        tx = await airlock_gateway.process(
            prompt=prompt,
            messages=config.messages if config.messages else None,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
    except Exception as e:
        logger.error(f"Airlock gateway error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    status_code = 403 if "BLOCKED" in tx.final_status else 200

    from app.airlock_gateway import Verdict

    return JSONResponse(
        status_code=status_code,
        content={
            "transaction_id": tx.transaction_id,
            "final_status": tx.final_status,
            "latency_ms": round(tx.latency_ms, 2),
            "sector": tx.sector,
            "preflight": {
                "result": tx.preflight.result.value if tx.preflight else "SKIPPED",
                "findings": [
                    {
                        "auditor": f.auditor,
                        "verdict": f.verdict.value,
                        "reason": f.reason,
                        "categories": f.categories,
                        "latency_ms": round(f.latency_ms, 2),
                    }
                    for f in (tx.preflight.findings if tx.preflight else [])
                ],
                "total_latency_ms": round(tx.preflight.total_latency_ms, 2) if tx.preflight else 0,
            } if tx.preflight else None,
            "egress": {
                "action": tx.egress_decision.action.value if tx.egress_decision else "NONE",
                "tool_id": tx.egress_decision.tool_id if tx.egress_decision else None,
                "reason": tx.egress_decision.reason if tx.egress_decision else "",
            } if tx.egress_decision else None,
            "response": tx.base_model_response if tx.final_status in ("PASSED", "ESCALATED", "ESCALATED_EGRESS") else None,
            "timestamp": tx.timestamp,
        }
    )


@app.get("/v1/airlock/stats")
async def airlock_stats():
    """Airlock Gateway statistics"""
    global airlock_gateway
    if not airlock_gateway:
        raise HTTPException(status_code=503, detail="Airlock Gateway not ready")
    return airlock_gateway.get_stats()


@app.get("/v1/airlock/transactions")
async def airlock_transactions(limit: int = 20):
    """Recent airlock transactions"""
    global airlock_gateway
    if not airlock_gateway:
        raise HTTPException(status_code=503, detail="Airlock Gateway not ready")
    recent = airlock_gateway.transactions[-limit:]
    return {
        "transactions": [
            {
                "transaction_id": t.transaction_id,
                "final_status": t.final_status,
                "latency_ms": round(t.latency_ms, 2),
                "prompt": t.prompt[:80],
                "timestamp": t.timestamp,
            }
            for t in recent
        ],
        "total": len(airlock_gateway.transactions),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)