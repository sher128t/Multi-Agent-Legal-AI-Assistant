# Legal Multi-Agent RAG MVP

Secure collaborative workspace for legal teams. A junior associate agent performs retrieval with citations, a compliance agent flags GDPR/policy risks, and a senior partner agent synthesises the final answer. The frontend streams responses with inline sources, while the backend logs and audits every request.

## Stack
- **Frontend:** Next.js 14, TypeScript, Tailwind, streaming via Fetch reader
- **Backend:** FastAPI, LangGraph orchestration, Redis pub/sub, Postgres metadata, Qdrant vectors, Redis cache
- **Retrieval:** Hybrid dense (Qdrant) + BM25 fallback with configurable embedding model (default: `text-embedding-3-large`)
- **Agents:** LLM-powered (configurable chat model) with strict citation enforcement
- **Memory:** Postgres conversation + document metadata, Redis for agent event bus

## Prerequisites
- Docker + Docker Compose
- Python 3.10+
- `pnpm` (Node 18+ runtime)

Copy the template environment file and fill in secrets:

```bash
cp .env.example .env
```

Minimum variables:

```
OPENAI_API_KEY=sk-...
CHAT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-large
QDRANT_URL=http://localhost:6333
POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@localhost:5432/legal
REDIS_URL=redis://localhost:6379/0
AUTH_SECRET=change-me
```

## Local Development

```bash
# start infra (Qdrant, Postgres, Redis)
make up

# install deps
cd backend && pip install -e .
cd ../frontend && pnpm install

# run backend + frontend
cd ..
make dev  # uvicorn + next dev
```

Frontend runs on <http://localhost:3000>, backend on <http://localhost:8000>.

## Tests & Quality

```bash
# backend tests
make test

# lint/type-check
make lint
make typecheck
```

Tests cover ingestion, retrieval contract, and `/ask` streaming output with citations.

## API Reference

### Health
`GET /health`

### Ingest
`POST /ingest`

Multipart form (`files[]`, `case_id`).

```
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer demo-cli:junior,senior" \
  -F case_id=case-demo \
  -F "files=@tests/data/sample.txt"
```

### Ask
`POST /ask`

```
curl -X POST http://localhost:8000/ask \
  -H "Authorization: Bearer demo-cli:senior" \
  -H "Content-Type: application/json" \
  -d '{
        "query": "Summarise the data retention duties",
        "case_id": "case-demo",
        "session_id": "cli-session"
      }'
```

The response streams newline-delimited JSON:

```json
{
  "final_answer": "...",
  "citations": [{"doc_id": "...", "page": 1}],
  "risks": ["..."],
  "next_steps": ["..."],
  "request_id": "..."
}
```

See `requests.http` for a Postman-compatible collection.

## Multi-Agent Flow
1. **Retrieve:** Hybrid vector/BM25 lookup (`top-k` ≤5, threshold 0.8)
2. **Junior agent:** LLM-powered drafting from snippets with inline citation tags (e.g., [S1], [S2]); enforces that every paragraph references provided snippets
3. **Compliance agent:** keyword-based scan for GDPR/policy issues, flags severity
4. **Senior agent:** LLM-powered synthesis of final memo, enforces per-paragraph citations, prunes unsupported claims, lists risks + next steps
5. **Redis Pub/Sub:** publishes node completion events for telemetry dashboards
6. **Memory:** conversations & document metadata persisted to Postgres; `GDPR_DELETE` endpoint wipes case data

If retrieval returns <1 snippet or LLM fails to cite sources, agents respond with *need more docs* guidance.

## Frontend UX
- Sidebar manages case/session IDs (stored in `localStorage`)
- Document ingest button hits `/ingest`
- Chat pane renders markdown streaming output; citation chips display `Doc XXXXX p.Y`
- Risks and next steps highlighted in alert panels

## Observability & Security
- Bearer auth stub (`demo-<user>:<roles>`) with role checks per endpoint
- Structured logging via `structlog` with request id + latency + token counts
- `GDPR_DELETE(case_id)` helper removes Postgres rows and tombstones vector entries
- No outbound web calls during answers; agents operate only on ingested data

## Data Seed

`tests/data/sample.txt` ships a 2-paragraph “Data Retention” memo used by tests and demo flows.

## Make Targets
- `make up` – start Qdrant, Postgres, Redis
- `make dev` – run FastAPI & Next dev servers (stop with `Ctrl+C`)
- `make backend` / `make frontend` – run each service individually
- `make test` / `make lint` / `make typecheck`

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed instructions on deploying to:
- **Frontend**: Vercel (Next.js)
- **Backend**: Railway (FastAPI)
- **Infrastructure**: Managed services (Qdrant Cloud, Supabase, Upstash)

Quick start:
1. Set up managed services (Qdrant, Supabase, Upstash)
2. Deploy backend to Railway (uses `backend/Procfile` and `backend/requirements.txt`)
3. Deploy frontend to Vercel (uses `vercel.json`)
4. Configure environment variables in both platforms

Happy lawyering! 🧑‍⚖️🤖

