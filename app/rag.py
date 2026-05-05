"""
RAG module for context retrieval.
"""

import httpx
import nltk
from rank_bm25 import BM25Okapi
from qdrant_client import AsyncQdrantClient
from openai import AsyncOpenAI
from config import EMBEDDINGS_URL, LORAX_URL, QDRANT_URL, MAX_CONTEXT_LENGTH
from typing import List

nltk.download('punkt')

vector_db = AsyncQdrantClient(url=QDRANT_URL)
client = AsyncOpenAI(base_url=f"{LORAX_URL}/v1", api_key="not-needed")

async def get_rag_context(user_query: str) -> str:
    """
    Hybrid search: Vector + BM25 + Rerank.
    """
    # Get embedding
    embed_response = await httpx.post(f"{EMBEDDINGS_URL}/embed", json={"text": user_query})
    embed_response.raise_for_status()
    query_vector = embed_response.json()["embedding"]

    # Vector search
    vector_results = await vector_db.search(collection_name="sops", query_vector=query_vector, limit=20)
    candidates = [r.payload['text'] for r in vector_results]
    vector_scores = [r.score for r in vector_results]

    # BM25
    tokenized_docs = [nltk.word_tokenize(doc.lower()) for doc in candidates]
    bm25 = BM25Okapi(tokenized_docs)
    tokenized_query = nltk.word_tokenize(user_query.lower())
    bm25_scores = bm25.get_scores(tokenized_query)

    # Combine scores
    combined_scores = [(v + b) / 2 for v, b in zip(vector_scores, bm25_scores)]

    # Rerank top 10
    top_indices = sorted(range(len(combined_scores)), key=lambda i: combined_scores[i], reverse=True)[:10]
    top_candidates = [candidates[i] for i in top_indices]

    rerank_response = await httpx.post(f"{EMBEDDINGS_URL}/rerank", json={"query": user_query, "documents": top_candidates})
    rerank_response.raise_for_status()
    rerank_scores = rerank_response.json()["scores"]
    ranked = sorted(zip(top_candidates, rerank_scores), key=lambda x: x[1], reverse=True)

    # Take top 3
    top_texts = [text for text, score in ranked[:3]]
    context = "\n".join(top_texts)

    # Summarize if too long
    if len(context.split()) > MAX_CONTEXT_LENGTH:
        summary_prompt = f"Summarize the following information into a concise briefing note for an expert, retaining key facts and details:\n\n{context}"
        summary_response = await client.chat.completions.create(
            model="google/gemma-4-26b-a4b-it",
            messages=[{"role": "user", "content": summary_prompt}],
            max_tokens=1000
        )
        context = summary_response.choices[0].message.content

    return context