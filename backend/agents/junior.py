"""Junior associate agent: performs retrieval-grounded drafting with LLM."""

from __future__ import annotations

from typing import Dict, List

from backend.llm import generate
from backend.rag.retrieval import Snippet

JUNIOR_SYSTEM = (
    "You are a junior legal researcher. Answer ONLY using the provided snippets. "
    "Do not invent facts. Include inline citations referencing snippet IDs we provide. "
    "If evidence is insufficient, reply: 'need more docs'."
)


def _format_snippets(snippets: List[Snippet]) -> str:
    """Format snippets with labels S1..Sn for citation."""
    lines = []
    for i, s in enumerate(snippets, 1):
        lines.append(f"[S{i}] doc_id={s.doc_id} page={s.page} :: {s.text}")
    return "\n".join(lines)


def answer(query: str, snippets: List[Snippet]) -> Dict[str, object]:
    if not snippets:
        return {"draft": "need more docs", "citations": []}

    user = (
        f"USER QUESTION:\n{query}\n\n"
        f"EVIDENCE SNIPPETS (cite like [S1], [S2], etc.):\n{_format_snippets(snippets)}\n\n"
        "RESPONSE FORMAT:\n"
        "1) A concise answer in bullets or short paragraphs.\n"
        "2) After each bullet or paragraph, include one or more citations like [S2][S3].\n"
    )

    draft = generate(JUNIOR_SYSTEM, user)

    # Map [S#] to {doc_id, page}
    cits = []
    for i, s in enumerate(snippets, 1):
        tag = f"[S{i}]"
        if tag in draft:
            cits.append({"doc_id": s.doc_id, "page": s.page, "quote": s.text[:200]})

    # De-duplicate while preserving order
    seen = set()
    citations = []
    for c in cits:
        key = (c["doc_id"], c["page"])
        if key not in seen:
            seen.add(key)
            citations.append(c)

    # If model failed to include any snippet tags, force "need more docs"
    if not citations and "need more docs" not in draft.lower():
        draft = "need more docs"
        citations = []

    return {"draft": draft, "citations": citations}


__all__ = ["answer"]

