"""Embedding helpers with OpenAI primary path and deterministic fallback."""

from __future__ import annotations

import hashlib
import os
from typing import Iterable, List, Sequence

import numpy as np

try:  # Optional import at runtime
    from openai import OpenAI
except ImportError:  # pragma: no cover - handled in fallback path
    OpenAI = None  # type: ignore[assignment]


EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
_FALLBACK_DIM = 1536


class EmbeddingError(RuntimeError):
    """Raised when embeddings cannot be produced."""


def _fallback_embed(texts: Sequence[str]) -> List[List[float]]:
    def _hash(text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        repeat = (_FALLBACK_DIM * 4 + len(digest) - 1) // len(digest)
        extended = (digest * repeat)[: _FALLBACK_DIM * 4]
        vector = np.frombuffer(extended, dtype=np.uint32).astype(np.float32)
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector.tolist()
        return (vector / norm).tolist()

    return [_hash(text) for text in texts]


def embed_texts(texts: Sequence[str]) -> List[List[float]]:
    if not texts:
        return []

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and OpenAI is not None:
        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=list(texts))
        return [data.embedding for data in response.data]

    return _fallback_embed(texts)


def embed_text(text: str) -> List[float]:
    return embed_texts([text])[0]


__all__ = ["EMBEDDING_MODEL", "EmbeddingError", "embed_text", "embed_texts"]

