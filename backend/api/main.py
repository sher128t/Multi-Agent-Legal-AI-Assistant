"""FastAPI service exposing ingestion and question answering endpoints."""

from __future__ import annotations

import json
import os
import uuid
from typing import AsyncIterator, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import redis.asyncio as redis

from backend.agents.graph import RedisPublisher, build_graph
from backend.memory.models import Conversation, Document
from backend.memory.store import ChunkRecord, MemoryStore
from backend.observability.logging import app_logger, log_latency, log_tokens
from backend.rag.chunking import chunk_text
from backend.rag.embeddings import embed_texts
from backend.rag.retrieval import HybridRetriever, create_retriever
from backend.security.auth import AuthContext, audit_log, get_current_user, require_role


class Settings(BaseSettings):
    qdrant_url: Optional[str] = Field(default=os.getenv("QDRANT_URL"))
    qdrant_api_key: Optional[str] = Field(default=os.getenv("QDRANT_API_KEY"))
    postgres_dsn: Optional[str] = Field(default=os.getenv("POSTGRES_DSN"))
    redis_url: Optional[str] = Field(default=os.getenv("REDIS_URL"))
    openai_api_key: Optional[str] = Field(default=os.getenv("OPENAI_API_KEY"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
app = FastAPI(title="Legal Multi-Agent RAG", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

retriever: HybridRetriever = create_retriever(settings.qdrant_url, settings.qdrant_api_key)
memory_store = MemoryStore(settings.postgres_dsn)
redis_client = redis.from_url(settings.redis_url) if settings.redis_url else None
publisher = RedisPublisher(redis_client) if redis_client else None
agent_graph = build_graph(retriever, publisher)


@app.on_event("startup")
async def startup() -> None:
    try:
        await memory_store.init()
        app_logger().info("startup_complete", database="connected")
    except Exception as e:
        app_logger().error("startup_database_error", error=str(e))
        # Continue startup even if DB fails - app can still serve /health
        # Database will be required for /ingest and /ask endpoints


class AskRequest(BaseModel):
    query: str
    case_id: str
    session_id: Optional[str] = None


class AskResponse(BaseModel):
    final_answer: str
    citations: List[Dict[str, object]]
    risks: List[str]
    next_steps: List[str]
    request_id: str


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
async def ingest(  # noqa: PLR0913 - FastAPI signature
    case_id: str = Form(...),
    files: List[UploadFile] = File(...),
    user: AuthContext = Depends(get_current_user),
):
    require_role(user, ["junior", "senior"])
    request_id = str(uuid.uuid4())
    indexed_chunks = 0

    for file in files:
        data = await file.read()
        if not data:
            continue

        text = data.decode("utf-8", errors="ignore")
        chunks = chunk_text(text)
        if not chunks:
            continue

        embeddings = embed_texts(chunks)
        doc_id = str(uuid.uuid4())

        retriever.upsert(case_id=case_id, doc_id=doc_id, chunks=chunks, embeddings=embeddings)

        document = Document(id=doc_id, case_id=case_id, name=file.filename or doc_id)
        records = [
            ChunkRecord(
                id=f"{doc_id}:{idx}",
                doc_id=doc_id,
                case_id=case_id,
                index=idx,
                page=idx + 1,
                text=chunk,
            )
            for idx, chunk in enumerate(chunks)
        ]
        await memory_store.upsert_document(document, records)
        indexed_chunks += len(chunks)

    audit_log("ingest", user=user, request_id=request_id, extra={"case_id": case_id, "indexed": indexed_chunks})
    return {"indexed": indexed_chunks}


@app.post("/ask")
async def ask(request: AskRequest, user: AuthContext = Depends(get_current_user)) -> StreamingResponse:
    require_role(user, ["senior"])
    request_id = str(uuid.uuid4())
    session_id = request.session_id or str(uuid.uuid4())

    await memory_store.ensure_conversation(Conversation(id=session_id, case_id=request.case_id))
    await memory_store.log_message(session_id, request.case_id, "user", request.query, [])

    async def generate() -> AsyncIterator[bytes]:
        with log_latency("ask", request_id=request_id, case_id=request.case_id):
            state = {"query": request.query, "case_id": request.case_id}
            result = agent_graph.invoke(state)
            response = result.get("response") or {
                "final_answer": "No supported answer is available. Please ingest additional documents.",
                "citations": [],
                "risks": ["Insufficient citations"],
                "next_steps": ["Provide more case materials."],
            }
            response["request_id"] = request_id

            await memory_store.log_message(
                session_id,
                request.case_id,
                "assistant",
                response["final_answer"],
                response.get("citations", []),
            )

            prompt_tokens = len(request.query.split())
            completion_tokens = len(response.get("final_answer", "").split())
            log_tokens(request_id, prompt_tokens, completion_tokens)
            audit_log("ask", user=user, request_id=request_id, extra={"case_id": request.case_id})

            yield (json.dumps(AskResponse(**response).dict()) + "\n").encode("utf-8")

    return StreamingResponse(generate(), media_type="application/json")


@app.post("/gdpr/delete/{case_id}")
async def gdpr_delete(case_id: str, user: AuthContext = Depends(get_current_user)) -> JSONResponse:
    require_role(user, ["compliance", "senior"])
    await memory_store.gdpr_delete(case_id)
    retriever.delete_case(case_id)
    return JSONResponse({"status": "deleted", "case_id": case_id})


__all__ = ["app"]

