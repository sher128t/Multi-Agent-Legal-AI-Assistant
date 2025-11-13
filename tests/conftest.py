from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.api.main import app, memory_store


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    await memory_store.init()
    yield


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app, lifespan="on")
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

