"""Senior partner agent synthesises the final answer and applies governance with LLM."""

from __future__ import annotations

from typing import Dict, Iterable, List

from backend.llm import generate

SENIOR_SYSTEM = (
    "You are a senior lawyer. Produce a clear, client-ready answer. "
    "Do NOT add facts not supported by the cited snippets. "
    "Every paragraph must include at least one snippet tag (e.g., [S1]). "
    "If the draft is 'need more docs', return a brief guidance note."
)


def synthesize(
    draft: str,
    citations: List[Dict[str, object]],
    compliance: Iterable[Dict[str, object]],
) -> Dict[str, object]:
    if "need more docs" in draft.lower():
        final_answer = "We need more documents relevant to the query to provide a substantiated answer."
        return {
            "final_answer": final_answer,
            "risks": [],
            "next_steps": ["Upload additional documents"],
            "citations": [],
        }

    comp_text = ""
    if compliance:
        comp_lines = [
            f"- {c['issue']} (severity: {c['severity']}) [doc:{c['source']['doc_id']}, p.{c['source']['page']}]"
            for c in compliance
        ]
        comp_text = "COMPLIANCE ISSUES:\n" + "\n".join(comp_lines)

    user = (
        f"DRAFT (with citations):\n{draft}\n\n"
        f"{comp_text}\n\n"
        "TASK: Refine the draft into a concise answer with:\n"
        "1) Final answer in short paragraphs, each with at least one citation tag already present in the draft (e.g., [S2]).\n"
        "2) A bullet list of 1-3 risks (if any), grounded in the evidence.\n"
        "3) 1-3 next steps for the client.\n"
        "Do NOT introduce new snippet tags or new facts.\n\n"
        "Format risks as: - Risk: <description>\n"
        "Format next steps as: - Next: <action>"
    )

    final_text = generate(SENIOR_SYSTEM, user)

    # If the final text contains no tags, fail-safe to 'need more docs'
    if "[" not in final_text or "]" not in final_text:
        final_text = "need more docs"
        return {
            "final_answer": final_text,
            "risks": ["Insufficient citations"],
            "next_steps": ["Provide more case materials."],
            "citations": [],
        }

    risks, next_steps = [], []
    # Simple extraction heuristics; keep existing contract surface
    for line in final_text.splitlines():
        low = line.strip().lower()
        if low.startswith("- risk:"):
            risks.append(line.split(":", 1)[1].strip())
        if low.startswith("- next:"):
            next_steps.append(line.split(":", 1)[1].strip())

    # Fallback if extraction failed
    if not risks:
        risks = [issue["issue"] for issue in compliance] or ["No flagged risks. Review manually."]
    if not next_steps:
        next_steps = [
            "Confirm compliance remediation items." if risks else "Validate findings with client lead.",
            "Record decision in matter management system.",
        ]

    return {
        "final_answer": final_text,
        "risks": risks,
        "next_steps": next_steps,
        "citations": citations,
    }


__all__ = ["synthesize"]

