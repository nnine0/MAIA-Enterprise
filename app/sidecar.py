#!/usr/bin/env python3
"""
MAIA Airlock Gateway Sidecar — Phase 3 (Network-Level Enforcement).

A standalone FastAPI service that acts as a governance proxy for all LLM API calls.

Architecture:
    ┌── Application Process ──┐       ┌── Sidecar Process (port 8080) ──┐
    │                         │       │                                  │
    │  client = OpenAI(       │──────▶│  Pre-flight (Sheriff+Sentinel)   │
    │    base_url="localhost" │       │  ↓ PASS                          │
    │  )                      │       │  Forward to upstream LLM API     │
    │                         │       │  ↓ Egress interception           │
    │                         │       │  Return response or 403          │
    └─────────────────────────┘       └──────────────────────────────────┘

    Network policy: Application container has NO egress to internet.
    ONLY the sidecar can reach the upstream LLM API.

Usage:
    # Start sidecar (production):
    python3 -m app.sidecar --upstream https://api.openai.com/v1 --port 8080

    # Application (point all clients to sidecar):
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url="http://localhost:8080/v1", api_key=...)
"""
import asyncio
import json
import logging
import os
import sys
import uuid
import argparse
from typing import Optional, Dict, Any, AsyncGenerator
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.airlock_gateway import (
    AirlockGateway, create_gateway, Verdict, AuditFinding,
    GatewayTransaction, DFlashBlockGovernor, DFlashBlockAuditTrail,
)
from app.bypass_monitor import bypass_detected, GatewayHealthMonitor

logger = logging.getLogger("MAIA-Sidecar")

# ─── Configuration ───────────────────────────────────────────────────────────

SIDECAR_HOST = os.environ.get("MAIA_SIDECAR_HOST", "127.0.0.1")
SIDECAR_PORT = int(os.environ.get("MAIA_SIDECAR_PORT", "8080"))
UPSTREAM_URL = os.environ.get("MAIA_UPSTREAM_URL", "")
UPSTREAM_API_KEY = os.environ.get("MAIA_UPSTREAM_API_KEY", "")

# ─── Global State ────────────────────────────────────────────────────────────

gateway: Optional[AirlockGateway] = None
governor: Optional[DFlashBlockGovernor] = None
health_monitor: Optional[GatewayHealthMonitor] = None
upstream_client: Optional[httpx.AsyncClient] = None


# ─── Request Models ──────────────────────────────────────────────────────────

class ChatCompletionRequest(BaseModel):
    model: str = ""
    messages: list = []
    max_tokens: int = 1024
    temperature: float = 0.7
    stream: bool = False
    extra_body: Optional[Dict[str, Any]] = None


# ─── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global gateway, governor, health_monitor, upstream_client

    # Initialize Airlock Gateway (production mode — no demo)
    try:
        gateway = create_gateway(
            sector="finance",
        )
        logger.info("Sidecar Airlock Gateway initialized (production mode)")
    except RuntimeError as e:
        logger.critical(f"Sidecar gateway init failed: {e}")
        logger.critical("Sidecar cannot start without production auditors")
        raise

    # Initialize DFlash block governor for trajectory logging
    governor = DFlashBlockGovernor(
        sheriff=gateway.sheriff,
        sentinel=gateway.sentinel,
    )

    # Initialize upstream HTTP client
    upstream_client = httpx.AsyncClient(timeout=120.0)

    # Start health monitor
    health_monitor = GatewayHealthMonitor(gateway, interval_seconds=60)
    await health_monitor.start()

    logger.info(f"Sidecar listening on {SIDECAR_HOST}:{SIDECAR_PORT}")
    yield

    await health_monitor.stop()
    if upstream_client:
        await upstream_client.aclose()


app = FastAPI(
    title="MAIA Airlock Sidecar",
    description="Governance proxy for LLM API calls — SR 26-02 compliant",
    version="0.1.0",
    lifespan=lifespan,
)


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "gateway": "ready" if gateway else "unavailable",
        "mode": "production",
        "upstream": UPSTREAM_URL or "not_configured",
    }


@app.get("/v1/models")
async def list_models():
    """List available models (passthrough to upstream)."""
    if not upstream_client or not UPSTREAM_URL:
        return {"data": [{"id": "maia-governed", "object": "model"}]}
    try:
        resp = await upstream_client.get(
            f"{UPSTREAM_URL.rstrip('/v1')}/v1/models",
            headers={"Authorization": f"Bearer {UPSTREAM_API_KEY}"},
        )
        return resp.json()
    except Exception as e:
        return {"data": [{"id": "maia-governed", "object": "model"}], "error": str(e)}


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completion with full governance.

    Flow:
      1. Extract user prompt from messages
      2. Pre-flight: Sheriff + Sentinel audit
      3. If BLOCKED → HTTP 403 with violation details
      4. If CLEAR → forward to upstream LLM API
      5. Egress: check response for policy violations
      6. If EGRESS BLOCK → HTTP 403, else return upstream response
    """
    if gateway is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")

    # Extract the last user message as the prompt
    prompt = ""
    for msg in reversed(request.messages):
        if msg.get("role") == "user":
            prompt = msg.get("content", "")
            break

    if not prompt:
        raise HTTPException(status_code=400, detail="No user message found")

    # ── Step 1: Pre-flight via AirlockGateway ──
    tx = await gateway.process(
        prompt=prompt,
        messages=request.messages,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    )

    # ── Step 2: Circuit breaker — BLOCK on violation ──
    if tx.final_status in ("BLOCKED_PRE_FLIGHT", "BLOCKED_BY_POLICY"):
        reasons = []
        if tx.preflight:
            for f in tx.preflight.findings:
                reasons.append(f"{f.auditor}: {f.reason}")
        logger.warning(f"Sidecar BLOCKED: {reasons}")

        bypass_detected(
            event_type="sidecar_blocked",
            source="sidecar:preflight",
            message=f"Blocked by governance: {'; '.join(reasons)}",
            severity="HIGH",
        )

        return JSONResponse(
            status_code=403,
            content={
                "error": "governance_blocked",
                "message": "Request blocked by MAIA policy enforcement",
                "details": reasons,
                "transaction_id": tx.transaction_id,
            },
        )

    if request.stream:
        return await _handle_streaming(tx, prompt)
    else:
        return await _handle_non_streaming(tx, prompt)


async def _handle_non_streaming(tx: GatewayTransaction, prompt: str) -> dict:
    """Non-streaming: forward to upstream, run egress, return result."""
    if not upstream_client or not UPSTREAM_URL:
        return {
            "id": f"chatcmpl-{tx.transaction_id}",
            "object": "chat.completion",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "model": "maia-governed",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"[Governed by MAIA Airlock] Transaction {tx.transaction_id} "
                               f"passed pre-flight. (Upstream not configured)",
                },
                "finish_reason": "stop",
            }],
        }

    # Forward to upstream LLM API
    upstream_body = {
        "model": tx.prompt,  # placeholder
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.7,
        "stream": False,
    }

    try:
        resp = await upstream_client.post(
            f"{UPSTREAM_URL.rstrip('/v1')}/v1/chat/completions",
            json=upstream_body,
            headers={"Authorization": f"Bearer {UPSTREAM_API_KEY}"},
        )
        resp.raise_for_status()
        upstream_data = resp.json()
    except Exception as e:
        logger.error(f"Upstream call failed: {e}")
        raise HTTPException(status_code=502, detail=f"Upstream LLM error: {e}")

    # ── Egress interception ──
    response_text = ""
    choice = upstream_data.get("choices", [{}])[0]
    if "message" in choice:
        response_text = choice["message"].get("content", "")

    egress_result = await gateway.egress.intercept(response_text)
    if egress_result.action == Verdict.BLOCK:
        logger.warning(f"Sidecar EGRESS BLOCKED: {egress_result.reason}")
        bypass_detected(
            event_type="sidecar_egress_blocked",
            source="sidecar:egress",
            message=f"Egress blocked: {egress_result.reason}",
            severity="HIGH",
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "egress_blocked",
                "message": f"Response blocked by policy: {egress_result.reason}",
            },
        )

    return upstream_data


async def _handle_streaming(tx: GatewayTransaction, prompt: str):
    """Streaming: forward to upstream with streaming egress checks."""
    if not upstream_client or not UPSTREAM_URL:
        raise HTTPException(status_code=501, detail="Streaming requires upstream")

    upstream_body = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.7,
        "stream": True,
    }

    async def stream_generator():
        full_text = ""
        try:
            async with upstream_client.stream(
                "POST",
                f"{UPSTREAM_URL.rstrip('/v1')}/v1/chat/completions",
                json=upstream_body,
                headers={"Authorization": f"Bearer {UPSTREAM_API_KEY}"},
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    if line.strip() == "data: [DONE]":
                        yield "data: [DONE]\n\n"
                        return

                    yield line + "\n\n"
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content", "")
                        full_text += token

                        # Egress check mid-stream
                        if len(full_text) > 50:
                            result = await gateway.egress.intercept(full_text)
                            if result.action == Verdict.BLOCK:
                                logger.warning(f"Streaming egress blocked: {result.reason}")
                                yield f"data: {json.dumps({'error': 'egress_blocked'})}\n\n"
                                yield "data: [DONE]\n\n"
                                return
                    except (json.JSONDecodeError, IndexError):
                        continue

        except Exception as e:
            logger.error(f"Streaming upstream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
    )


@app.get("/v1/governance/trail")
async def get_governance_trail():
    """Return the DFlash block audit trail for Fed reporting (SR 26-02 §4.3)."""
    if governor is None:
        return {"trail": [], "stats": {}}
    return {
        "trail": governor.get_trajectory_log(),
        "stats": governor.get_stats(),
    }


@app.get("/v1/governance/health")
async def get_governance_health():
    """Return governance health status."""
    if health_monitor is None or gateway is None:
        return {"status": "unavailable"}
    return {
        "status": "running",
        "stats": health_monitor.get_stats(),
        "transactions": len(gateway.transactions),
    }


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MAIA Airlock Sidecar")
    parser.add_argument("--upstream", default=UPSTREAM_URL, help="Upstream LLM API URL")
    parser.add_argument("--port", type=int, default=SIDECAR_PORT, help="Sidecar port")
    parser.add_argument("--host", default=SIDECAR_HOST, help="Sidecar host")
    parser.add_argument("--api-key", default=UPSTREAM_API_KEY, help="Upstream API key")
    args = parser.parse_args()

    global UPSTREAM_URL, UPSTREAM_API_KEY, SIDECAR_PORT, SIDECAR_HOST
    if args.upstream:
        UPSTREAM_URL = args.upstream
    if args.api_key:
        UPSTREAM_API_KEY = args.api_key
    SIDECAR_PORT = args.port
    SIDECAR_HOST = args.host

    import uvicorn
    logger.info(f"Starting MAIA Airlock Sidecar on {args.host}:{args.port}")
    if args.upstream:
        logger.info(f"Upstream LLM API: {args.upstream}")
    else:
        logger.warning("No upstream configured — sidecar will respond with governance-only mode")

    uvicorn.run(
        "app.sidecar:app",
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
