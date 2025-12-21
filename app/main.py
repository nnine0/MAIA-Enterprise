from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header
from pydantic import BaseModel
import os
import httpx
import asyncio
import logging
import json
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct
from datetime import datetime

from llm_guard import scan_prompt

# Local modules
from routing import route_to_expert_semantic
from rag import get_rag_context
from auditing import audit_response, extract_response
import config

# Structured logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="MAIA Council Controller")

def get_live_adapter(expert: str) -> str:
    """
    Get the live adapter version from metadata.
    """
    if os.path.exists(config.METADATA_FILE):
        with open(config.METADATA_FILE, 'r') as f:
            metadata = json.load(f)
        return metadata.get(expert, f"adapter_{expert}")
    return f"adapter_{expert}"

def verify_api_key(x_maia_key: str = Header(...)) -> str:
    if x_maia_key != config.MAIA_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return x_maia_key

client = AsyncOpenAI(base_url=f"{config.LORAX_URL}/v1", api_key="not-needed")
vector_db = AsyncQdrantClient(url=config.QDRANT_URL)

class QueryRequest(BaseModel):
    query: str

class ThumbsUpRequest(BaseModel):
    query: str
    response: str
    context: str = ""
    sector: str = "general"



async def execute_maia_protocol(user_query: str) -> str:
    context = await get_rag_context(user_query)
    expert = await route_to_expert_semantic(user_query)

    logger.info(json.dumps({"event": "expert_activated", "expert": expert, "query": user_query}))

    system_instruction = f"You are an expert in {expert}. Use this context: {context}"

    # 1. Generate Draft
    adapter_id = get_live_adapter(expert)
    completion = await client.chat.completions.create(
        model=config.BASE_MODEL_ID,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_query}
        ],
        extra_body={"adapter_id": f"/adapters/{adapter_id}", "adapter_source": "local", "fallback_to_base": True},
        temperature=0.4
    )
    draft_response = completion.choices[0].message.content

    # 2. Response Validation (Auditing)
    general_adapter = get_live_adapter("general")
    response = await audit_response(draft_response, general_adapter)
    return response





@app.post("/query")
async def query_endpoint(request: QueryRequest, api_key: str = Depends(verify_api_key)) -> dict:
    # Scan for prompt injection
    sanitized_query = scan_prompt(request.query)
    if sanitized_query != request.query:
        raise HTTPException(status_code=400, detail="Prompt injection detected")
    response = await execute_maia_protocol(sanitized_query)
    return {"response": response}

@app.post("/query_image")
async def query_image_endpoint(file: UploadFile = File(...), api_key: str = Depends(verify_api_key)) -> dict:
    contents = await file.read()
    try:
        from tasks import process_ocr_and_analyze
        task = process_ocr_and_analyze.delay(contents, file.filename, file.content_type)
        return {"task_id": task.id, "status": "processing"}
    except Exception as e:
        logger.error(json.dumps({"event": "ocr_task_failed", "error": str(e)}))
        # Circuit breaker: Fall back to text query with filename
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
    # Update metadata to rollback
    if os.path.exists(config.METADATA_FILE):
        with open(config.METADATA_FILE, 'r') as f:
            metadata = json.load(f)
        metadata[expert] = version
        with open(config.METADATA_FILE, 'w') as f:
            json.dump(metadata, f)
        # Signal LoRAX to refresh
        httpx.post(f"{config.LORAX_URL}/adapters/refresh", json={"adapter_id": f"/adapters/{version}"})
        return {"status": "rolled back"}
    return {"error": "metadata not found"}

@app.post("/train_update")
async def train_update_endpoint() -> dict:
    # Create trigger file for trainer
    os.makedirs(config.DATA_LOGS_DIR, exist_ok=True)
    trigger_file = f"{config.DATA_LOGS_DIR}/trigger_update"
    with open(trigger_file, 'w') as f:
        f.write("trigger")
    return {"status": "Update triggered for trainer"}

@app.post("/thumbs_up")
async def thumbs_up_endpoint(request: ThumbsUpRequest, api_key: str = Depends(verify_api_key)):
    # Store positive interaction in Qdrant
    import uuid
    point = PointStruct(
        id=str(uuid.uuid4()),
        vector=[],  # No vector needed for logs
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