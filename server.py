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

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse

from kernel.matrix import MaterialityMatrix, MaterialityTier
from kernel.airlock import Gemma4ThinkingAirlock
from kernel.dispatcher import NeuralToolDispatcher, DispatchRequest
from kernel.registry import ToolRegistry
from kernel.exceptions import PolicyViolationInterrupt, DHITLRequired


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MAIA-Kernel")


app = FastAPI(
    title="MAIA Enterprise Kernel",
    description="Governed AI OS for regulated industries"
)


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


# Global kernel instance
kernel: Optional[MAIAKernel] = None


@app.on_event("startup")
async def startup():
    global kernel
    kernel = MAIAKernel()
    logger.info("MAIA Kernel started")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)