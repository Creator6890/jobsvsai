# JobsVsAI Phase 1

JobsVsAI is a career-intelligence MVP that keeps **AI Exposure** separate from **Replacement Risk**, explains the task-level drivers behind both, and connects each analysis to realistic next-career options.

## Architecture

- `frontend/` — Next.js App Router, TypeScript, server-rendered profession and ranking pages
- `backend/` — FastAPI API with async PostgreSQL access
- `worker/` — RQ background worker for imports and dependency-based recalculation
- `scoring/` — versionable Python scoring logic
- `ingestion/` — source-specific ingestion boundary
- `migrations/` — normalized PostgreSQL schema and demo seed
- `docker-compose.yml` — local portable stack (Next.js, FastAPI, PostgreSQL, Redis, worker)

The frontend calls FastAPI for PostgreSQL-backed occupation records. There are no fixture fallbacks. Full scores are precomputed and stored; public requests never run scoring calculations.

## Run the complete stack

1. Copy `.env.example` to `.env` and replace the example passwords.
2. Run `docker compose up --build`.
3. Open `http://localhost:3000`. API docs are at `http://localhost:8000/api/docs`.

The initial SQL migrations run automatically when PostgreSQL creates a fresh data volume. For production-like settings use:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## O*NET subset ingestion

The O*NET ingestion boundary is staged and score-neutral. See `ingestion/ONET_MAPPING.md` before expanding its scope. After downloading the official 30.3 CSV files into `ingestion/data/onet/30.3`, apply migration `005_onet_ingestion_layer.sql` and run:

```bash
docker compose run --rm backend python -m ingestion.onet_import import \
  --version 30.3 \
  --data-dir ingestion/data/onet/30.3 \
  --subset-file ingestion/subsets/representative_31.txt
```

Replaying the same command is idempotent. Validate the current canonical layer with `python -m ingestion.onet_import validate --version 30.3` inside the backend service.

## Tests and validation

```bash
cd frontend && npm run lint && npm run build
python -m pytest backend/tests
```

## Phase 1 routes

- `/`, `/jobs/[slug]`, `/rankings`
- `/career-finder`, `/career-finder/results`
- `/compare`, `/compare/[job-a]-vs-[job-b]`
- `/methodology`, `/about`
- `/admin`, `/admin/jobs`, `/admin/jobs/[slug]`, `/admin/scores`, `/admin/imports`, `/admin/system`

Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in production. The admin routes are intentionally excluded from public navigation and protected by HTTP Basic authentication in production.
