"""
MAIA Council Controller - Governance Layer for Business Intelligence
====================================================================
Integrates: Supervisor Router, Circuit Breaker, Memory Manager, Latent Telemetry

Zero-Trust Architecture:
- Agentic Layer: Generates intent payloads
- Governance Layer: Circuit Breaker validates and signs
- Application Layer: Executes only signed trajectories
"""

from typing import Optional
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
from dme_engine import (
    SectorAdapter,
    RoleAdapter,
    ToolAdapter,
    DMEngine,
    MAIAOrchestrator,
    get_orchestrator,
    get_dme_engine,
)
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

from dispatcher import NeuralToolDispatcher, DispatchResult
from kernel_manifest import create_kernel_manifest
from tool_router import create_tool_router
from core.adapter_loader import registry

from app.airlock_gateway import AirlockGateway, Verdict, AuditFinding

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

# Initialize Neural Tool Dispatcher
dispatcher: NeuralToolDispatcher = None
kernel_manifest = None
tool_router = None

def init_dispatcher():
    """Initialize the Neural Tool Dispatcher"""
    global dispatcher, kernel_manifest, tool_router
    try:
        dispatcher = NeuralToolDispatcher("configs/maia_kernel_manifest.json")
        kernel_manifest = create_kernel_manifest()
        tool_router = create_tool_router()
        logger.info("Neural Tool Dispatcher initialized")
        logger.info(f"Tools registered: {dispatcher.get_stats()['tools_registered']}")
    except Exception as e:
        logger.warning(f"Dispatcher init deferred: {e}")
        dispatcher = None
        kernel_manifest = None
        tool_router = None

init_dispatcher()

# Global Airlock Gateway for Tier 2/3 pre-flight governance
_airlock_gateway: Optional[AirlockGateway] = None
_engine = None

def get_airlock_gateway() -> Optional[AirlockGateway]:
    """Lazy-init Airlock Gateway for Tier 2/3 pre-flight checks.
    
    Uses ModelEngine to load Granite Sentinel for governance.
    If real auditors are unavailable, returns None — the Tier 2/3 path
    logs a bypass warning but still proceeds (backwards compatible).
    """
    global _airlock_gateway, _engine
    if _airlock_gateway is not None:
        return _airlock_gateway
    try:
        from app.engine import ModelEngine
        from app.airlock_gateway import create_gateway_from_engine
        _engine = ModelEngine()
        _engine.load_granite()
        sentinel = _engine.granite
        _airlock_gateway = create_gateway_from_engine(
            sheriff=sentinel,
            sentinel=sentinel,
            sector="finance",
        )
        logger.info("Airlock Gateway initialized for Tier 2/3 pre-flight governance (via ModelEngine)")
        return _airlock_gateway
    except Exception as e:
        logger.error(f"Failed to init Airlock Gateway for Tier 2/3: {e}")
        return None

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
        # Tier 2/3: Pre-flight governance via Airlock Gateway
        gateway = get_airlock_gateway()
        if gateway is not None:
            try:
                batch_results = await gateway._coordinator.audit_batch([user_query])
                sheriff_finding, sentinel_finding = batch_results[0]
                findings = [sheriff_finding, sentinel_finding]
                blocks = [f for f in findings if f.verdict == Verdict.BLOCK]
                if blocks:
                    reasons = [f.reason for f in blocks]
                    logger.warning(f"Tier 2/3 pre-flight BLOCKED: {reasons}")
                    await emit_signature(
                        session_id, layer=2,
                        adapter_id="airlock-gateway",
                        reasoning=f"Blocked by governance: {reasons}",
                        inputs=["user_query"],
                        outputs=["block_reason"]
                    )
                    return {
                        "session_id": session_id,
                        "dispatch": dispatch_token,
                        "materiality_tier": dispatch.materiality_tier,
                        "status": "blocked",
                        "reason": f"Governance pre-flight blocked: {reasons}"
                    }
                escalates = [f for f in findings if f.verdict == Verdict.ESCALATE]
                if escalates:
                    logger.warning(f"Tier 2/3 pre-flight ESCALATE: {[f.reason for f in escalates]}")
            except Exception as e:
                logger.error(f"Tier 2/3 pre-flight error (proceeding): {e}")
        else:
            logger.warning(
                "TIER 2/3 BYPASS WARNING: No Airlock Gateway available. "
                "Request proceeding without pre-flight governance."
            )

        # Direct expert execution with logging
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
                "adapter_id": adapter_id,
                "adapter_source": "local",
                "fallback_to_base": True
            },
            temperature=0.4
        )
        
        # Emit telemetry for execution
        await emit_signature(
            session_id, layer=2,
            adapter_id=adapter_id,
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


class ToolDispatchRequest(BaseModel):
    query: str
    force_tool: str = None


class ToolDispatchResponse(BaseModel):
    tool_id: str
    intent_detected: bool
    rpc_call: dict = None
    forensic_hash: str = None
    governance_passed: bool
    error: str = None


@app.post("/tool_dispatch")
async def tool_dispatch_endpoint(
    request: ToolDispatchRequest,
    api_key: str = Depends(verify_api_key)
) -> dict:
    """
    Neural Tool Dispatch endpoint.
    
    Detects [CALL_TOOL:TOOL_ID] in reasoning, hot-swaps adapter,
    applies logit bias, and dispatches JSON-RPC.
    """
    global dispatcher
    
    if dispatcher is None:
        return {"error": "Dispatcher not initialized", "status": "unhealthy"}
    
    # 1. Check if query contains tool intent
    intent = dispatcher.detect_tool_intent(request.query)
    
    if intent:
        tool_id = intent.tool_id
        
        # 2. Reconfigure kernel (hot-swap LoRA)
        dispatcher.reconfigure_kernel(tool_id)
        
        # 3. Check governance
        governance = dispatcher.check_governance(tool_id, request.query)
        
        if not governance["passed"]:
            return {
                "tool_id": tool_id,
                "intent_detected": True,
                "governance_passed": False,
                "error": governance["violations"]
            }
        
        # 4. Get tool router suggestion if no force
        if not request.force_tool:
            router_suggestion = tool_router.route_intent(request.query)
            if router_suggestion:
                tool_id = router_suggestion.adapter_id
        
        # 5. Build RPC call
        rpc = dispatcher.build_rpc_payload(tool_id, {"query": request.query})
        
        # 6. Execute dispatch
        result = dispatcher.execute_dispatch(tool_id, json.dumps(rpc.get("params", {})), request.query)
        
        return {
            "tool_id": tool_id,
            "intent_detected": True,
            "rpc_call": rpc,
            "forensic_hash": result.forensic_hash[:16] if result.forensic_hash else None,
            "governance_passed": result.success,
            "error": result.error
        }
    
    # No tool intent - use tool router to find matching tool
    router_suggestion = tool_router.route_intent(request.query)
    
    if router_suggestion:
        tool_id = router_suggestion.adapter_id
        governance = dispatcher.check_governance(tool_id, request.query)
        
        return {
            "tool_id": tool_id,
            "intent_detected": False,
            "router_suggestion": True,
            "governance_passed": governance["passed"],
            "tool_function": router_suggestion.tool_function
        }
    
    return {
        "intent_detected": False,
        "no_tool_matched": True,
        "message": "No tool intent detected in query"
    }


@app.get("/tools")
async def tools_endpoint(api_key: str = Depends(verify_api_key)) -> dict:
    """List all registered tools"""
    global dispatcher
    
    if dispatcher is None:
        return {"error": "Dispatcher not initialized"}
    
    return {
        "tools": dispatcher.list_tools(),
        "stats": dispatcher.get_stats()
    }


@app.get("/tools/{tool_id}/governance")
async def tool_governance_endpoint(
    tool_id: str,
    api_key: str = Depends(verify_api_key)
) -> dict:
    """Get governance config for specific tool"""
    global dispatcher
    
    if dispatcher is None:
        return {"error": "Dispatcher not initialized"}
    
    tool = dispatcher.tools.get(tool_id)
    
    if not tool:
        return {"error": f"Tool not found: {tool_id}"}
    
    return {
        "tool_id": tool_id,
        "governance_layer": tool.get("governance_layer"),
        "neural_layer": tool.get("neural_layer"),
        "action_layer": tool.get("action_layer")
    }


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
        httpx.post(f"{config.LORAX_URL}/adapters/refresh", json={"adapter_id": version})
        return {"status": "rolled back"}
    return {"error": "metadata not found"}


@app.post("/train_update")
async def train_update_endpoint(api_key: str = Depends(verify_api_key)) -> dict:
    """
    Trigger retraining with validation gate.
    
    Retraining only occurs when:
    1. Minimum feedback threshold reached (default: 10)
    2. All SafetyGuardrails checks pass
    3. [Optional] SME approval for critical domains
    """
    from app.training_guardrails import guardrails, SafetyGuardrails
    
    os.makedirs(config.DATA_LOGS_DIR, exist_ok=True)
    trigger_file = f"{config.DATA_LOGS_DIR}/pending_train"
    
    # Get RLHF training data
    from app.airlock import get_rlhf_training_data
    training_samples = get_rlhf_training_data()
    
    # Run guardrails
    status, message, results = guardrails.run_all_checks(training_samples)
    
    if status.value == "block":
        return {
            "status": "blocked",
            "message": message,
            "guardrail_results": results
        }
    
    if status.value == "warn":
        return {
            "status": "warning",
            "message": message,
            "guardrail_results": results
        }
    
    # Write trigger - Celery picks this up
    with open(trigger_file, 'w') as f:
        f.write(str(datetime.now()))
    
    return {
        "status": "approved",
        "message": "Training guardrails passed",
        "guardrail_results": results
    }
    
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