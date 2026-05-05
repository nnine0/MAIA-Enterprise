"""
MAIA Council Controller - Governance Layer for Business Intelligence
====================================================================
Integrates: Supervisor Router, Circuit Breaker, Memory Manager, Latent Telemetry

Zero-Trust Architecture:
- Agentic Layer: Generates intent payloads
- Governance Layer: Circuit Breaker validates and signs
- Application Layer: Executes only signed trajectories
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header
from pydantic import BaseModel
import os
import httpx
import asyncio
import logging
import json
import uuid
from datetime import datetime
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

from llm_guard import scan_prompt

from routing import route_to_expert_semantic
from rag import get_rag_context
from auditing import audit_response, extract_response

from airlock import execute_vetted_transaction, batch_vetted_transactions, AirlockVerdict
from circuit_breaker import intercept_and_validate
from supervisor_router import route_query, supervisor_router
from memory_manager import get_memory_status, load_adapter
from latent_telemetry import (
    start_telemetry_session,
    emit_signature,
    get_audit_log,
    get_dag,
    verify_soundness
)
from dag_orchestrator import (
    create_workflow,
    execute_stream,
    execute_with_convergence,
    get_workflow_status
)

from config import (
    MAIA_API_KEY,
    LORAX_URL,
    BASE_MODEL_ID,
    QDRANT_URL,
    API_HOST,
    API_PORT,
    METADATA_FILE,
    DATA_LOGS_DIR,
)
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MAIA Governance Layer",
    description="AI Governance Operating System for SR 26-02 Compliance"
)

def get_live_adapter(expert: str) -> str:
    if os.path.exists(config.METADATA_FILE):
        with open(config.METADATA_FILE, 'r') as f:
            metadata = json.load(f)
        return metadata.get(expert, f"adapter_{expert}")
    return f"adapter_{expert}"

def verify_api_key(x_maia_key: str = Header(...)) -> str:
    if x_maia_key != config.MAIA_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return x_maia_key

client = AsyncOpenAI(base_url=f"{config.LORAX_URL}/v1", api_key=config.LORAX_API_KEY)
vector_db = AsyncQdrantClient(url=config.QDRANT_URL)


class QueryRequest(BaseModel):
    query: str
    use_airlock: bool = True
    use_supervisor: bool = True

class ThumbsUpRequest(BaseModel):
    query: str
    response: str
    context: str = ""
    sector: str = "general"


class WorkflowRequest(BaseModel):
    workflow_type: str
    initial_data: dict


async def execute_maia_protocol(user_query: str, session_id: str = None) -> dict:
    """Execute full MAIA protocol with all governance layers"""
    
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    # Start latent telemetry session
    await start_telemetry_session(session_id, user_query)
    
    # Step 1: Hierarchical Routing (Supervisor LoRA)
    dispatch = await route_query(user_query)
    dispatch_token = supervisor_router.get_dispatch_token_string(dispatch)
    logger.info(json.dumps({
        "event": "supervisor_dispatch",
        "session_id": session_id,
        "dispatch": dispatch_token,
        "industry": dispatch.industry,
        "sub_domain": dispatch.sub_domain,
        "materiality_tier": dispatch.materiality_tier
    }))
    
    # Emit telemetry for routing
    await emit_signature(
        session_id, layer=1,
        adapter_id="supervisor-hub",
        reasoning=f"Industry: {dispatch.industry}, Sub-domain: {dispatch.sub_domain}",
        inputs=["user_query"],
        outputs=["dispatch_token"]
    )
    
    # Step 2: Memory Manager - Load adapters
    load_adapter(dispatch.expert_adapter)
    if dispatch.materiality_tier == 1:
        load_adapter(dispatch.auditor_adapter)
    
    # Step 3: PVI Airlock Execution
    if dispatch.materiality_tier == 1:
        # Tier 1: Full Airlock with Actor/Auditor
        audit_result = await execute_vetted_transaction(
            user_query,
            domain=dispatch.industry,
            transaction_id=session_id
        )
        
        # Emit telemetry for audit
        await emit_signature(
            session_id, layer=3,
            adapter_id=dispatch.auditor_adapter,
            reasoning=f"Airlock Verdict: {audit_result['status']}",
            inputs=["actor_reasoning"],
            outputs=["audit_verdict"]
        )
        
        return {
            "session_id": session_id,
            "dispatch": dispatch_token,
            "materiality_tier": dispatch.materiality_tier,
            "audit_result": audit_result,
            "status": "vetted" if audit_result['status'] == "PASS" else "blocked"
        }
    else:
        # Tier 2/3: Direct expert execution with logging
        context = await get_rag_context(user_query)
        system_instruction = f"You are an expert in {dispatch.sub_domain}. Use this context: {context}"
        
        adapter_id = get_live_adapter(dispatch.expert_adapter)
        completion = await client.chat.completions.create(
            model=config.BASE_MODEL_ID,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_query}
            ],
            extra_body={
                "adapter_id": f"/adapters/{adapter_id}",
                "adapter_source": "local",
                "fallback_to_base": True
            },
            temperature=0.4
        )
        
        # Emit telemetry for execution
        await emit_signature(
            session_id, layer=2,
            adapter_id=dispatch.expert_adapter,
            reasoning=completion.choices[0].message.content[:200],
            inputs=["user_query", "context"],
            outputs=["response"]
        )
        
        return {
            "session_id": session_id,
            "dispatch": dispatch_token,
            "materiality_tier": dispatch.materiality_tier,
            "response": completion.choices[0].message.content,
            "status": "completed"
        }


@app.get("/")
async def root():
    return {
        "name": "MAIA Governance Layer",
        "version": "3.0",
        "description": "AI Governance Operating System",
        "architecture": {
            "kernel": "LoRAX + Unified Speculative Stack",
            "speculation": "MTP + DFlash + Saguaro",
            "base_model": "Gemma 4 26B A4B It",
            "mtp_drafter": "native (shared KV cache)",
            "orchestration": "Supervisor LoRA (Hub/Spoke)",
            "governance": "Circuit Breaker + PVI Airlock",
            "telemetry": "Latent State Observability"
        }
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "memory": get_memory_status()
    }


@app.post("/query")
async def query_endpoint(request: QueryRequest, api_key: str = Depends(verify_api_key)) -> dict:
    """Standard query with PVI Airlock and Supervisor routing"""
    sanitized_query = scan_prompt(request.query)
    if sanitized_query != request.query:
        raise HTTPException(status_code=400, detail="Prompt injection detected")
    
    result = await execute_maia_protocol(sanitized_query)
    return result


@app.post("/query_batch")
async def query_batch_endpoint(queries: list[str], api_key: str = Depends(verify_api_key)) -> dict:
    """Batch query with parallel PVI Airlock execution"""
    results = await batch_vetted_transactions(queries)
    return {"results": results}


@app.post("/workflow")
async def workflow_endpoint(request: WorkflowRequest, api_key: str = Depends(verify_api_key)) -> dict:
    """Create and execute DAG workflow"""
    workflow_id = await create_workflow(request.workflow_type, request.initial_data)
    return {"workflow_id": workflow_id, "status": get_workflow_status(workflow_id)}


@app.get("/workflow/{workflow_id}")
async def workflow_status_endpoint(workflow_id: str, api_key: str = Depends(verify_api_key)) -> dict:
    """Get workflow status"""
    return get_workflow_status(workflow_id)


@app.get("/telemetry/{session_id}")
async def telemetry_endpoint(session_id: str, api_key: str = Depends(verify_api_key)) -> dict:
    """Get latent telemetry audit log"""
    return get_audit_log(session_id)


@app.get("/telemetry/{session_id}/dag")
async def dag_endpoint(session_id: str, api_key: str = Depends(verify_api_key)) -> dict:
    """Get full DAG of reasoning"""
    return {"dag": get_dag(session_id)}


@app.post("/telemetry/{session_id}/verify")
async def verify_endpoint(session_id: str, expected_path: list[str], api_key: str = Depends(verify_api_key)) -> dict:
    """Verify conceptual soundness of trajectory"""
    return verify_soundness(session_id, expected_path)


@app.get("/memory")
async def memory_endpoint(api_key: str = Depends(verify_api_key)) -> dict:
    """Get memory hierarchy status"""
    return get_memory_status()


@app.post("/query_image")
async def query_image_endpoint(file: UploadFile = File(...), api_key: str = Depends(verify_api_key)) -> dict:
    contents = await file.read()
    try:
        from tasks import process_ocr_and_analyze
        task = process_ocr_and_analyze.delay(contents, file.filename, file.content_type)
        return {"task_id": task.id, "status": "processing"}
    except Exception as e:
        logger.error(json.dumps({"event": "ocr_task_failed", "error": str(e)}))
        response = await execute_maia_protocol(f"Analyze this file: {file.filename}")
        return {"fallback": True, "response": response}


@app.get("/task/{task_id}")
async def get_task_status(task_id: str, api_key: str = Depends(verify_api_key)):
    from celery_app import celery_app
    task_result = celery_app.AsyncResult(task_id)
    if task_result.state == "PENDING":
        return {"status": "pending"}
    elif task_result.state == "SUCCESS":
        return {"status": "completed", "result": task_result.result}
    else:
        return {"status": "failed", "error": str(task_result.info)}


@app.post("/rollback_adapter")
async def rollback_adapter(expert: str, version: str, api_key: str = Depends(verify_api_key)) -> dict:
    if os.path.exists(config.METADATA_FILE):
        with open(config.METADATA_FILE, 'r') as f:
            metadata = json.load(f)
        metadata[expert] = version
        with open(config.METADATA_FILE, 'w') as f:
            json.dump(metadata, f)
        httpx.post(f"{config.LORAX_URL}/adapters/refresh", json={"adapter_id": f"/adapters/{version}"})
        return {"status": "rolled back"}
    return {"error": "metadata not found"}


@app.post("/train_update")
async def train_update_endpoint(api_key: str = Depends(verify_api_key)) -> dict:
    """
    Trigger retraining with validation gate.
    
    Retraining only occurs when:
    1. Minimum feedback threshold reached (default: 10)
    2. Feedback has passed validation (not user-flagged as spam)
    3. [Optional] SME approval for critical domains
    """
    os.makedirs(config.DATA_LOGS_DIR, exist_ok=True)
    trigger_file = f"{config.DATA_LOGS_DIR}/pending_train"
    
    # Check if we have enough validated feedback
    feedback_count = _count_validated_feedback()
    min_threshold = 10
    
    if feedback_count < min_threshold:
        return {
            "status": "pending",
            "message": f"Need {min_threshold - feedback_count} more valid feedback",
            "feedback_count": feedback_count
        }
    
    # Write trigger - Celery picks this up
    with open(trigger_file, 'w') as f:
        f.write(str(datetime.now()))
    
    return {"status": "triggered", "feedback_count": feedback_count}


def _count_validated_feedback() -> int:
    """Count feedback that passed validation gate (not noise/spam)."""
    # This would query validated feedback from Qdrant
    # Filter out: thumbs_down, duplicate, timestamp anomalies
    # In practice: query where is_validated=True AND vote_count >= 3
    return 0  # Placeholder - implement with actual query


@app.post("/thumbs_up")
async def thumbs_up_endpoint(request: ThumbsUpRequest, api_key: str = Depends(verify_api_key)):
    import uuid
    point = PointStruct(
        id=str(uuid.uuid4()),
        vector=[],
        payload={
            "query": request.query,
            "response": request.response,
            "context": request.context,
            "sector": request.sector,
            "timestamp": str(datetime.now())
        }
    )
    await vector_db.upsert(collection_name="positive_interactions", points=[point])
    return {"status": "Thumbs up logged"}