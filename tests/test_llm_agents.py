"""Test LLM-powered agents return cited output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

HEADERS = {"Authorization": "Bearer demo-tester:junior,senior,compliance"}
SAMPLE_PATH = Path("tests/data/sample.txt")


async def _ingest_sample(client, case_id: str) -> None:
    files = [("files", (SAMPLE_PATH.name, SAMPLE_PATH.read_bytes(), "text/plain"))]
    data = {"case_id": case_id}
    response = await client.post("/ingest", data=data, files=files, headers=HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["indexed"] > 0


@pytest.mark.asyncio
async def test_llm_agents_return_cited_output(client):
    """Test that LLM-powered agents return answers with citation tags or 'need more docs'."""
    case_id = "case-llm-test"
    await _ingest_sample(client, case_id)

    response = await client.post(
        "/ask",
        json={"query": "What are the data retention requirements?", "case_id": case_id},
        headers=HEADERS,
    )
    assert response.status_code == 200
    content = response.text.strip().splitlines()[-1]
    payload = json.loads(content)

    final_answer = payload.get("final_answer", "")
    # Assert that the answer contains either citation tags [S#] or "need more docs"
    has_citation_tags = "[" in final_answer and "]" in final_answer
    has_need_more_docs = "need more docs" in final_answer.lower()

    assert (
        has_citation_tags or has_need_more_docs
    ), f"Answer must contain citation tags [S#] or 'need more docs', got: {final_answer[:200]}"

