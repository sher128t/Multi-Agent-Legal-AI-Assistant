"""Compliance agent checks snippets for policy issues.

TODO: Consider LLM-powered compliance checking for more nuanced policy analysis.
"""

from __future__ import annotations

from typing import Dict, List

from backend.rag.retrieval import Snippet


KEYWORDS = {
    "pii": ["personal data", "pii", "identifiable", "data subject"],
    "gdpr": ["gdpr", "general data protection"],
    "retention": ["retention", "store", "archiv"],
}


def check(snippets: List[Snippet]) -> List[Dict[str, object]]:
    issues: List[Dict[str, object]] = []
    for snippet in snippets:
        text_lower = snippet.text.lower()
        if any(keyword in text_lower for keyword in KEYWORDS["gdpr"]):
            issues.append(
                {
                    "issue": "GDPR-related content detected; ensure processing basis is documented.",
                    "severity": "med",
                    "source": {"doc_id": snippet.doc_id, "page": snippet.page},
                }
            )
        if any(keyword in text_lower for keyword in KEYWORDS["pii"]):
            issues.append(
                {
                    "issue": "Snippet mentions personal data—verify minimisation and consent.",
                    "severity": "med",
                    "source": {"doc_id": snippet.doc_id, "page": snippet.page},
                }
            )
        if any(keyword in text_lower for keyword in KEYWORDS["retention"]):
            issues.append(
                {
                    "issue": "Review data retention obligations for the cited material.",
                    "severity": "low",
                    "source": {"doc_id": snippet.doc_id, "page": snippet.page},
                }
            )

    # Deduplicate identical issues by source
    unique = {(issue["issue"], issue["source"]["doc_id"], issue["source"]["page"]): issue for issue in issues}
    return list(unique.values())


__all__ = ["check"]

