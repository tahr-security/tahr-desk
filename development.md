# Tahr Desk development

## Prerequisites

Python 3.14, uv 0.12.2, Bun 1.3.14, and PostgreSQL 18 (or Docker Compose v2)
are the pinned development foundation. Copy `.env.example` to `.env`, use
`ENVIRONMENT=local`, set `POSTGRES_SERVER=localhost` for a host backend, and
replace every secret placeholder.

## Install and run

```bash
uv sync --frozen --all-packages
bun install --frozen-lockfile
cd backend
uv run bash scripts/prestart.sh
uv run fastapi dev app/main.py
```

In another terminal, run `bun run dev`. Vite serves the frontend on port 5173;
FastAPI serves the production single-origin build on port 8000.

## Migrations and generated client

Alembic is the only schema authority. Create a semantic migration, test an
upgrade/downgrade/upgrade against PostgreSQL, and never edit an applied release
migration. After any API model or route change:

```bash
bun run generate-client
git diff -- frontend/openapi.json frontend/src/client
```

Commit the OpenAPI document, generated client, and TanStack route tree. Frontend
feature code must call the generated services rather than hand-written HTTP
contracts.

## Verification

```bash
cd backend
uv run ruff check app tests
uv run ruff format app tests --check
uv run ty check app
uv run coverage run -m pytest tests
uv run coverage report --fail-under=90

cd ../frontend
bunx biome check --no-errors-on-unmatched --files-ignore-unknown=true ./
bun run build
bunx playwright test
```

For container checks, render Compose, build the same image, start app/prestart,
worker/PostgreSQL, inspect runtime restrictions, execute browser journeys, and
verify persistence across restart. Provider acceptance tests are separate and
require explicit approval plus real credentials.

## Domain rules

Lock a case row before assignment, transition, classification, message, or
attachment-count changes. Staff mutations require `If-Match`; increment the
integer case version exactly once per committed domain mutation. Events and any
webhook deliveries are created in the same transaction. Private notes must not
enter reporter models, public exports, or webhook payloads.
