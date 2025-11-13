"""Persistence helpers for conversations and document metadata."""

from __future__ import annotations

import json
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Iterable, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base, Chunk, Conversation, Document, Message


DEFAULT_DSN = os.getenv(
    "POSTGRES_DSN",
    "sqlite+aiosqlite:///./local_memory.db",
)


@dataclass
class ChunkRecord:
    id: str
    doc_id: str
    case_id: str
    index: int
    page: int
    text: str


class MemoryStore:
    def __init__(self, dsn: Optional[str] = None) -> None:
        self.engine = create_async_engine(dsn or DEFAULT_DSN, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def upsert_document(self, doc: Document, chunks: Iterable[ChunkRecord]) -> None:
        async with self.session() as session:
            await session.merge(doc)
            await session.execute(delete(Chunk).where(Chunk.doc_id == doc.id))
            for record in chunks:
                session.add(
                    Chunk(
                        id=record.id,
                        doc_id=record.doc_id,
                        case_id=record.case_id,
                        chunk_index=record.index,
                        page=record.page,
                        text=record.text,
                    )
                )
            await session.commit()

    async def get_chunks_for_case(self, case_id: str) -> List[Chunk]:
        async with self.session() as session:
            result = await session.execute(select(Chunk).where(Chunk.case_id == case_id))
            return list(result.scalars().all())

    async def log_message(
        self,
        conversation_id: str,
        case_id: str,
        role: str,
        content: str,
        citations: Optional[Iterable[dict]] = None,
    ) -> None:
        async with self.session() as session:
            convo = await session.get(Conversation, conversation_id)
            if convo is None:
                convo = Conversation(id=conversation_id, case_id=case_id)
                session.add(convo)
                await session.flush()

            session.add(
                Message(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    role=role,
                    content=content,
                    citations=json.dumps(list(citations or [])),
                )
            )
            await session.commit()

    async def ensure_conversation(self, conversation: Conversation) -> None:
        async with self.session() as session:
            await session.merge(conversation)
            await session.commit()

    async def gdpr_delete(self, case_id: str) -> None:
        async with self.session() as session:
            convo_ids = await session.execute(
                select(Conversation.id).where(Conversation.case_id == case_id)
            )
            ids = [row[0] for row in convo_ids]
            if ids:
                await session.execute(delete(Message).where(Message.conversation_id.in_(ids)))
            await session.execute(delete(Conversation).where(Conversation.case_id == case_id))
            await session.execute(delete(Chunk).where(Chunk.case_id == case_id))
            await session.execute(delete(Document).where(Document.case_id == case_id))
            await session.commit()


async def GDPR_DELETE(case_id: str, store: Optional[MemoryStore] = None) -> None:
    memory_store = store or MemoryStore()
    await memory_store.gdpr_delete(case_id)


__all__ = ["MemoryStore", "ChunkRecord", "GDPR_DELETE"]

