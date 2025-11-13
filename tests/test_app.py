from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.api.main import retriever

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
async def test_ingestion_indexes_chunks(client):
    await _ingest_sample(client, case_id="case-ingest")


@pytest.mark.asyncio
async def test_retrieval_returns_snippets(client):
    case_id = "case-retrieval"
    await _ingest_sample(client, case_id)
    snippets = retriever.retrieve("Data retention obligations", case_id)
    assert 0 < len(snippets) <= 5
    assert all(snippet.doc_id and snippet.page for snippet in snippets)


@pytest.mark.asyncio
async def test_ask_endpoint_streams_answer(client):
    case_id = "case-ask"
    await _ingest_sample(client, case_id)

    response = await client.post(
        "/ask",
        json={"query": "Summarise the data retention rules", "case_id": case_id},
        headers=HEADERS,
    )
    assert response.status_code == 200
    content = response.text.strip().splitlines()[-1]
    payload = json.loads(content)

    assert "Data Retention" in payload["final_answer"]
    assert payload["citations"]
    citation = payload["citations"][0]
    assert citation["doc_id"]
    assert citation["page"] >= 1

