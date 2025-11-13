"""Utilities for splitting documents into chunks suitable for retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class Chunk:
    doc_id: str
    case_id: str
    index: int
    text: str


def _sliding_window(words: List[str], size: int, overlap: int) -> Iterable[List[str]]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")

    step = max(size - overlap, 1)
    for start in range(0, max(len(words) - overlap, 1), step):
        window = words[start : start + size]
        if not window:
            break
        yield window


def chunk_text(text: str, *, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split *text* into approximately *chunk_size* token windows with *overlap*."""

    normalized = " ".join(text.split())
    words = normalized.split(" ") if normalized else []

    if not words:
        return []

    chunks: List[str] = []
    for window in _sliding_window(words, chunk_size, overlap):
        chunk = " ".join(window).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


__all__ = ["Chunk", "chunk_text"]

