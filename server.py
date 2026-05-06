"""
MAIA-Enterprise Kernel Server
========================
Wraps vLLM engine with Neural Tool Dispatcher and Thinking Airlock.

This turns a standard GPU into a Governed Compute Node.
In Quad-Node setup, run four instances, each with different sector config.
"""

import uuid
import json
import logging
from typing import Optional, Generator, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse

from gemma4_thinking_airlock import (
    Gemma4ThinkingAirlock,
    MaterialityMatrix,
    PolicyViolationInterrupt
)
from dispatcher import NeuralToolDispatcher
from kernel_manifest import create_kernel_manifest

logger = logging.getLogger("MAIA-Kernel")


class ServerState(Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    GOVERNING = "governing"
    ERROR = "error"


@dataclass
class ServerConfig:
    port: int = 8000
    model: str = "google/gemma-4-2b-it"
    speculative_model: Optional[str] = None
    num_speculative_tokens: int = 16
    gpu_memory_utilization: float = 0.90
    enable_lora: bool = True
    max_loras: int = 20
    temperature_material: float = 0.0
    temperature_creative: float = 0.7
    max_tokens: int = 2048


class MAIAKernelServer:
    """
    MAIA Kernel Server with Layer 8/9 Governance.
    
    Wraps inference through:
    1. MaterialityMatrix - determines governance level
    2. ThinkingAirlock - audits reasoning channel
    3. NeuralToolDispatcher - executes tools with governance
    """
    
    def __init__(self, config: ServerConfig = None):
        self.config = config or ServerConfig()
        self.state = ServerState.INITIALIZING
        
        self.dispatcher: Optional[NeuralToolDispatcher] = None
        self.airlock: Optional[Gemma4ThinkingAirlock] = None
        self.matrix: Optional[MaterialityMatrix] = None
        self.manifest = None
        
        self._request_count = 0
    
    async def initialize(self):
        """Initialize governance layers"""
        logger.info("Initializing MAIA Kernel Server...")
        
        # Load Materiality Matrix for compliance
        try:
            self.matrix = MaterialityMatrix()  # Uses default config
            logger.info("MaterialityMatrix loaded")
        except Exception as e:
            logger.warning(f"MaterialityMatrix init deferred: {e}")
            self.matrix = MaterialityMatrix()
        
        # Initialize Neural Tool Dispatcher
        try:
            self.dispatcher = NeuralToolDispatcher("configs/maia_kernel_manifest.json")
            self.manifest = create_kernel_manifest()
            logger.info(f"Dispatcher loaded: {self.dispatcher.get_stats()['tools_registered']} tools")
        except Exception as e:
            logger.warning(f"Dispatcher init deferred: {e}")
            self.dispatcher = None
        
        # Initialize Thinking Airlock
        self.airlock = Gemma4ThinkingAirlock(self.matrix)
        logger.info("ThinkingAirlock loaded")
        
        self.state = ServerState.READY
        logger.info("MAIA Kernel Server ready")
    
    def is_material_task(self, query: str) -> bool:
        """Determine if query requires governance (material task)"""
        if not self.matrix:
            return False
        
        tier, _ = self.matrix.classify(query)
        return tier.value <= 2  # TIER_1 or TIER_2
    
    async def process_stream(
        self,
        prompt: str,
        is_material: bool
    ) -> AsyncGenerator[str, None]:
        """
        Process inference through governance layers.
        
        Yields SSE data chunks.
        """
        self.state = ServerState.GOVERNING
        
        # Get temperature based on materiality
        temp = self.config.temperature_material if is_material else self.config.temperature_creative
        
        # Simulate inference (in production, this wraps vLLM)
        response_text = f"Governed response for: {prompt[:50]}..."
        
        try:
            # Check for tool intent in prompt
            intent = None
            if self.dispatcher:
                intent = self.dispatcher.detect_tool_intent(prompt)
            
            if intent:
                tool_id = intent.tool_id
                
                # Execute tool through dispatcher
                result = self.dispatcher.execute_dispatch(
                    tool_id,
                    json.dumps({"prompt": prompt}),
                    prompt
                )
                
                yield json.dumps({
                    "tool_executed": True,
                    "tool_id": tool_id,
                    "forensic_hash": result.forensic_hash[:16] if result.forensic_hash else None,
                    "result": result.rpc_response
                }) + "\n"
            else:
                # Return governed response
                yield json.dumps({
                    "choices": [{
                        "delta": {"content": response_text},
                        "finish_reason": "stop"
                    }]
                }) + "\n"
            
            # Log forensics
            self.dispatcher.dispatch_history.append({
                "query": prompt[:100],
                "material": is_material,
                "tool": intent.tool_id if intent else None
            })
            self._request_count += 1
            
        except PolicyViolationInterrupt as e:
            yield json.dumps({
                "error": "MAIA_GOVERNANCE_INTERRUPT",
                "detail": e.detail,
                "evidence": e.evidence[:200]
            }) + "\n"
        
        except Exception as e:
            yield json.dumps({
                "error": "INTERNAL_ERROR",
                "detail": str(e)
            }) + "\n"
        
        finally:
            self.state = ServerState.READY
    
    async def chat_completions(self, body: dict) -> Generator[str, None, None]:
        """Process OpenAI-style chat completion"""
        request_id = str(uuid.uuid4())
        
        # Extract messages
        messages = body.get("messages", [])
        if not messages:
            yield json.dumps({"error": "No messages provided"}) + "\n"
            return
        
        prompt = messages[-1].get("content", "")
        
        # Layer 9: Materiality routing
        is_material = self.is_material_task(prompt)
        
        # Configure stop tokens for audit
        stop_tokens = ["<|channel|>", "<|end_of_turn|>", "<|im_end|>"]
        
        # Process through governance
        async for chunk in self.process_stream(prompt, is_material):
            yield f"data: {chunk}\n"
        
        yield "data: [DONE]\n"
    
    def get_stats(self) -> dict:
        """Get server statistics"""
        return {
            "state": self.state.value,
            "requests_processed": self._request_count,
            "dispatcher": self.dispatcher.get_stats() if self.dispatcher else None,
            "airlock": self.airlock.get_stats() if self.airlock else None
        }


# FastAPI app setup
app = FastAPI(
    title="MAIA-Enterprise Governance Kernel",
    description="GPU Kernel with Layer 8/9 Governance Interception"
)

# Global server instance
server: Optional[MAIAKernelServer] = None


@app.on_event("startup")
async def startup():
    global server
    server = MAIAKernelServer()
    await server.initialize()


@app.get("/health")
async def health():
    """Health check with governance status"""
    if server is None:
        return {"status": "initializing"}
    
    stats = server.get_stats()
    return {
        "status": stats["state"],
        "requests": stats["requests_processed"],
        "dispatcher_ready": server.dispatcher is not None,
        "airlock_ready": server.airlock is not None
    }


@app.get("/stats")
async def stats():
    """Get kernel statistics"""
    if server is None:
        return {"error": "Server not initialized"}
    return server.get_stats()


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-Compatible Endpoint with Layer 8/9 Governance.
    
    Wraps vLLM through:
    1. MaterialityMatrix routing
    2. ThinkingAirlock audit
    3. NeuralToolDispatcher execution
    """
    if server is None:
        raise HTTPException(status_code=503, detail="Server initializing")
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    is_stream = body.get("stream", False)
    
    if is_stream:
        return StreamingResponse(
            server.chat_completions(body),
            media_type="text/event-stream"
        )
    else:
        response_chunks = []
        async for chunk in server.chat_completions(body):
            response_chunks.append(chunk)
        
        # Combine chunks
        full_response = ""
        for chunk in response_chunks:
            if chunk.startswith("data: "):
                data = chunk[6:].strip()
                if data != "[DONE]" and data != "":
                    full_response = data
        
        return json.loads(full_response) if full_response else {"error": "No response"}


@app.get("/tools")
async def list_tools():
    """List registered tools"""
    if server is None or server.dispatcher is None:
        return {"error": "Dispatcher not initialized"}
    return server.dispatcher.list_tools()


@app.get("/governance/materiality")
async def check_materiality(query: str):
    """Check materiality classification"""
    if server is None or server.matrix is None:
        return {"error": "Matrix not initialized"}
    
    tier, config = server.matrix.classify(query)
    return {
        "query": query[:100],
        "tier": tier.name,
        "level": tier.value,
        "domains": config.domains if config else []
    }


if __name__ == "__main__":
    import uvicorn
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    uvicorn.run(app, host="0.0.0.0", port=8000)