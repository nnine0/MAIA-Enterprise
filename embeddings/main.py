from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, CrossEncoder
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Embeddings Service", version="1.0.0")

# Load models
embed_model = SentenceTransformer('all-MiniLM-L6-v2')
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

class EmbedRequest(BaseModel):
    text: str

class RerankRequest(BaseModel):
    query: str
    documents: list[str]

@app.post("/embed")
async def embed_text(request: EmbedRequest):
    try:
        embedding = embed_model.encode(request.text).tolist()
        return {"embedding": embedding}
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        raise HTTPException(status_code=500, detail="Embedding failed")

@app.post("/rerank")
async def rerank_documents(request: RerankRequest):
    try:
        pairs = [[request.query, doc] for doc in request.documents]
        scores = reranker.predict(pairs).tolist()
        return {"scores": scores}
    except Exception as e:
        logger.error(f"Reranking error: {e}")
        raise HTTPException(status_code=500, detail="Reranking failed")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=6000)