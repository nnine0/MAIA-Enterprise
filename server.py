"""
MAIA Enterprise Hybrid Server
=============================
Refactored server using SGLang + LoRAX hybrid kernel with Airlock Gateway.

Key changes from original:
1. Uses HybridInferenceKernel instead of standalone components
2. Implements T0/T1/T2/T3 speculative verification pipeline
3. Exposes SVP metrics at /stats endpoint
4. Shared memory IPC for <1ms inter-process handoff
5. Parallel Airlock Gateway (Sheriff/Sentinel/Basemodel dispatch)

SR 26-02: Turn all stubs into functional API.
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Generator, AsyncGenerator, Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from kernel.hybrid_kernel import HybridInferenceKernel, create_hybrid_kernel
from kernel.hybrid_config import get_kernel_manifest
from kernel.exceptions import PolicyViolationInterrupt, DHITLRequired
from app.airlock_gateway import AirlockGateway, create_gateway

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MAIA-Hybrid-Server")

# Global instances
kernel: Optional[HybridInferenceKernel] = None
airlock_gateway: Optional[AirlockGateway] = None


@asynccontextmanager
async def lifespan(app):
    global kernel, airlock_gateway
    kernel = create_hybrid_kernel()
    airlock_gateway = create_gateway(
        api_base="",
        sector="finance",
        demo=True
    )
    logger.info("MAIA Hybrid Kernel + Airlock Gateway initialized")
    if kernel:
        logger.info(f"VRAM: {kernel.stratifier.get_vram_breakdown()}")
    yield


app = FastAPI(
    title="MAIA Enterprise Hybrid Kernel",
    description="Governed AI OS for regulated industries - SGLang + LoRAX SGMV + Airlock Gateway",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "kernel": "hybrid_sglang_lorax" if kernel else "starting",
        "airlock_gateway": "ready" if airlock_gateway else "starting",
        "kernel_type": "sglang_lorax_hybrid"
    }


@app.get("/stats")
async def stats():
    """Kernel statistics with SVP metrics for Fed reporting"""
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel starting")

    stats = kernel.get_stats()
    return {
        "kernel_type": "sglang_lorax_hybrid",
        "vram": stats.get("vram"),
        "requests": {
            "total": stats.get("requests_total"),
            "success": stats.get("requests_success"),
            "blocked": stats.get("requests_blocked")
        },
        "latency_ms": {
            "t0_hub_routing": stats.get("t0_hub_routing_ms"),
            "t1_speculating": stats.get("t1_speculating_ms"),
            "t2_verifying": stats.get("t2_verifying_ms"),
            "t3_auditing": stats.get("t3_auditing_ms"),
            "context_switch_avg": stats.get("context_switch_avg_ms")
        },
        "radix_cache": stats.get("radix_cache"),
        "svp": stats.get("svp"),
        "manifest": get_kernel_manifest()
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible chat endpoint.

    Processes through all MAIA hybrid kernel layers:
    T0 (0ms):   Materiality classification (Hub LoRA)
    T1 (1ms):   DFlash parallel drafting
    T2 (<100ms): Saguaro verification + async audit
    T3 (finish): Forensic hash generation
    """
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel not ready")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    messages = body.get("messages", [])
    stream = body.get("stream", False)

    prompt = messages[-1].get("content", "") if messages else ""

    if stream:
        return StreamingResponse(
            kernel.stream_request(prompt, messages),
            media_type="text/event-stream"
        )
    else:
        response, stats = await kernel.process_request(prompt, messages)

        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            parsed = {"response": response}

        return {
            "id": f"maia-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": parsed.get("response", response)
                },
                "finish_reason": "stop"
            }],
            "model": "maia-hybrid-kernel",
            "metadata": {
                "tier": parsed.get("tier"),
                "domain": parsed.get("domain"),
                "tool_id": parsed.get("tool_id"),
                "forensic_hash": parsed.get("forensic_hash"),
                "svp": parsed.get("svp"),
                "latent_hashes": parsed.get("latent_hashes", [])
            }
        }


@app.get("/v1/models")
async def models():
    """List available models"""
    return {
        "object": "list",
        "data": [
            {
                "id": "maia-hybrid-kernel",
                "object": "model",
                "created": 1700000000,
                "owned_by": "maia-enterprise",
                "commentary": "SGLang + LoRAX SGMV hybrid kernel"
            },
            {
                "id": "google/gemma-4-26B-A4B",
                "object": "model",
                "created": 1700000000,
                "owned_by": "google",
                "commentary": "Base engine with NVFP4 quantization"
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
        "tools": kernel.dispatcher.list_tools(),
        "total": len(kernel.dispatcher.list_tools()),
        "manifest_version": "2.0.0"
    }


@app.get("/governance/svp")
async def governance_svp():
    """
    SVP (Speed vs. Parity) metrics for Fed reporting.

    This is what you hand to Federal Reserve examiners:
    - Context Switching Latency: <20ms (via LoRAX hot-swapping)
    - Audit Resolution: 100% of Trajectories (via L8 Circuit Breaker)
    - VRAM Utilization: 74% (Total safety stack fits on one consumer card)
    - Human-to-Machine Parity: 6.1x Speedup over manual audit
    """
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel not ready")

    svp = kernel.stats.svp.to_dict()

    return {
        "svp_status": svp.get("svp_status"),
        "context_switch_latency_ms": svp.get("context_switch_latency_ms"),
        "audit_resolution_pct": svp.get("audit_resolution_pct"),
        "vram_utilization_pct": svp.get("vram_utilization_pct"),
        "human_machine_parity": svp.get("human_machine_parity"),
        "fed_requirements": {
            "context_switch_latency_ms": {"target": "<20", "actual": svp.get("context_switch_latency_ms")},
            "audit_resolution_pct": {"target": "100", "actual": svp.get("audit_resolution_pct")},
            "vram_utilization_pct": {"target": "<95", "actual": svp.get("vram_utilization_pct")}
        },
        "verdict": "APPROVED" if svp.get("svp_status") == "OPTIMAL" else "REVIEW_REQUIRED"
    }


@app.get("/kernel/manifest")
async def kernel_manifest():
    """Get kernel manifest for SGLang + LoRAX configuration"""
    return get_kernel_manifest()


@app.get("/kernel/vram")
async def kernel_vram():
    """Get VRAM budget breakdown"""
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel not ready")

    return kernel.stratifier.get_vram_breakdown()


@app.get("/kernel/radix")
async def kernel_radix():
    """Get RadixAttention cache statistics"""
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel not ready")

    return kernel.radix.get_stats()


# ─── Airlock Gateway Endpoints ─────────────────────────────────────────────

class AirlockConfig(BaseModel):
    messages: List[Dict] = []
    prompt: str = ""
    sector: str = "finance"
    max_tokens: int = 1024
    temperature: float = 0.7


class AirlockBatchConfig(BaseModel):
    prompts: List[str]
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


@app.post("/v1/airlock/gateway/batch")
async def airlock_batch(config: AirlockBatchConfig):
    """Batched airlock gateway — N prompts in one coalesced batched preflight.

    All N prompts go through Sheriff + Sentinel in a single GPU forward pass
    each. Amortizes prefill cost across the batch.
    """
    global airlock_gateway
    if not airlock_gateway:
        raise HTTPException(status_code=503, detail="Airlock Gateway not ready")

    if not config.prompts:
        raise HTTPException(status_code=400, detail="No prompts provided")

    try:
        txs = await airlock_gateway.process_batch(config.prompts, config.sector)
    except Exception as e:
        logger.error(f"Airlock batch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    errors = sum(1 for t in txs if t.final_status == "ERROR")
    status_code = 207 if errors else 200

    return JSONResponse(
        status_code=status_code,
        content={
            "batch_size": len(txs),
            "errors": errors,
            "transactions": [
                {
                    "transaction_id": t.transaction_id,
                    "final_status": t.final_status,
                    "latency_ms": round(t.latency_ms, 2),
                }
                for t in txs
            ],
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
