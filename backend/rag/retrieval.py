"""Hybrid dense + sparse retrieval built on Qdrant and BM25."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from rank_bm25 import BM25Okapi

from backend.rag.embeddings import embed_text


@dataclass
class Snippet:
    doc_id: str
    page: int
    text: str
    score: float


def _chunk_id_to_int(chunk_id: str) -> int:
    """Convert a chunk ID string to an integer for Qdrant point IDs."""
    # Use MD5 hash and take first 8 bytes to create a 64-bit integer
    hash_bytes = hashlib.md5(chunk_id.encode()).digest()[:8]
    return int.from_bytes(hash_bytes, byteorder="big", signed=False)


class HybridRetriever:
    def __init__(
        self,
        client: Optional[QdrantClient],
        *,
        collection_name: str = "case_chunks",
        similarity_threshold: float = 0.8,
    ) -> None:
        self.client = client
        self.collection_name = collection_name
        self.similarity_threshold = similarity_threshold
        self._bm25_indices: Dict[str, BM25Okapi] = {}
        self._metadata: Dict[str, Tuple[str, int, str]] = {}
        self._case_chunks: Dict[str, List[str]] = {}

    def _ensure_collection(self, vector_size: int) -> None:
        if self.client is None:
            return
        collection_created = False
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=rest.VectorParams(size=vector_size, distance=rest.Distance.COSINE),
            )
            collection_created = True
        
        # Create payload index on case_id for filtering (if it doesn't exist)
        # This is needed for Qdrant to filter by case_id
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="case_id",
                field_schema=rest.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            # Index might already exist, ignore
            pass

    def upsert(
        self,
        *,
        case_id: str,
        doc_id: str,
        chunks: Sequence[str],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have identical length")

        if embeddings and self.client is not None:
            self._ensure_collection(len(embeddings[0]))

        points: List[rest.PointStruct] = []
        chunk_ids = [cid for cid in self._case_chunks.get(case_id, []) if not cid.startswith(f"{doc_id}:")]

        for index, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{doc_id}:{index}"
            payload = {
                "doc_id": doc_id,
                "page": index + 1,
                "text": chunk,
                "case_id": case_id,
            }
            self._metadata[chunk_id] = (doc_id, index + 1, chunk)
            chunk_ids.append(chunk_id)

            if self.client is not None:
                # Qdrant requires point IDs to be integers or UUIDs, not strings with colons
                point_id = _chunk_id_to_int(chunk_id)
                points.append(
                    rest.PointStruct(
                        id=point_id,
                        vector=list(vector),
                        payload=payload,
                    )
                )

        if points and self.client is not None:
            self.client.upsert(collection_name=self.collection_name, points=points)

        self._case_chunks[case_id] = chunk_ids
        documents = [self._metadata[cid][2] for cid in chunk_ids]
        if documents:
            self._bm25_indices[case_id] = BM25Okapi([doc.lower().split() for doc in documents])
        elif case_id in self._bm25_indices:
            del self._bm25_indices[case_id]

    def _dense_search(self, query_vector: Sequence[float], case_id: str) -> List[Snippet]:
        if self.client is None:
            return []

        result = self.client.query_points(
            collection_name=self.collection_name,
            query=list(query_vector),
            limit=10,
            query_filter=rest.Filter(
                must=[rest.FieldCondition(key="case_id", match=rest.MatchValue(value=case_id))]
            ),
            with_payload=True,
        )

        # query_points returns a QueryResponse object with a 'points' attribute
        # or directly returns an iterable of ScoredPoint objects
        if hasattr(result, 'points'):
            hits = result.points
        else:
            hits = result

        snippets: List[Snippet] = []
        for hit in hits:
            # Handle both tuple and object formats
            if isinstance(hit, tuple):
                # Tuple format: could be (id, score, payload) or (score, payload) or similar
                if len(hit) == 3:
                    point_id, score, payload = hit
                elif len(hit) == 2:
                    score, payload = hit
                    payload = payload or {}
                else:
                    # Try to extract score and payload from tuple
                    score = float(hit[1] if len(hit) > 1 else 0.0)
                    payload = hit[2] if len(hit) > 2 else (hit[1] if len(hit) > 1 and isinstance(hit[1], dict) else {})
            else:
                # If it's an object (ScoredPoint), access attributes
                payload = getattr(hit, 'payload', None) or {}
                score = float(getattr(hit, 'score', 0.0) or 0.0)
            
            if score < self.similarity_threshold:
                continue
            snippets.append(
                Snippet(
                    doc_id=payload.get("doc_id", "unknown") if isinstance(payload, dict) else "unknown",
                    page=int(payload.get("page", 1)) if isinstance(payload, dict) else 1,
                    text=payload.get("text", "") if isinstance(payload, dict) else "",
                    score=score,
                )
            )
        return snippets

    def _bm25_search(self, query: str, case_id: str) -> List[Snippet]:
        index = self._bm25_indices.get(case_id)
        if index is None:
            return []
        tokens = query.lower().split()
        scores = index.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        snippets: List[Snippet] = []
        for idx, score in ranked[:10]:
            try:
                chunk_id = self._case_chunks[case_id][idx]
            except (KeyError, IndexError):
                continue
            doc_id, page, text = self._metadata.get(chunk_id, ("unknown", 1, ""))
            snippets.append(Snippet(doc_id=doc_id, page=page, text=text, score=float(score)))
        return snippets

    def retrieve(self, query: str, case_id: str, *, limit: int = 5) -> List[Snippet]:
        if not query:
            return []

        query_vector = embed_text(query)
        dense_hits = self._dense_search(query_vector, case_id)

        unique_keys = {(hit.doc_id, hit.page) for hit in dense_hits}
        if len(unique_keys) < 3:
            sparse_hits = self._bm25_search(query, case_id)
            for hit in sparse_hits:
                key = (hit.doc_id, hit.page)
                if key not in unique_keys:
                    dense_hits.append(hit)
                    unique_keys.add(key)

        dense_hits.sort(key=lambda item: item.score, reverse=True)
        return dense_hits[:limit]

    def delete_case(self, case_id: str) -> None:
        if self.client is not None:
            try:
                self.client.delete(
                    collection_name=self.collection_name,
                    filter=rest.Filter(
                        must=[rest.FieldCondition(key="case_id", match=rest.MatchValue(value=case_id))]
                    ),
                )
            except Exception:  # pragma: no cover
                pass
        chunk_ids = self._case_chunks.pop(case_id, [])
        for chunk_id in chunk_ids:
            self._metadata.pop(chunk_id, None)
        self._bm25_indices.pop(case_id, None)


def create_retriever(qdrant_url: Optional[str], qdrant_api_key: Optional[str] = None) -> HybridRetriever:
    client = None
    if qdrant_url:
        try:
            if qdrant_api_key:
                client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
            else:
                client = QdrantClient(url=qdrant_url)
        except Exception:  # pragma: no cover - network issues during local tests
            client = None
    return HybridRetriever(client)


__all__ = ["Snippet", "HybridRetriever", "create_retriever"]

