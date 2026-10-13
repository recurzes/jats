# Jats API

FastAPI backend for Jats: Gmail sync, classifier, board API and the print queue.

## Setup

```sh
docker compose up -d          # from the repo root: Postgres on port 5433 (jats + jats_test)
cp .env.example .env          # from api/
uv sync
uv run alembic upgrade head
```

## Run

```sh
uv run uvicorn app.main:app --reload
```

`/health` is the liveness check and `/docs` has the OpenAPI UI.

## Checks

```sh
uv run ruff check .
uv run pytest
```

Tests run against the `jats_test` database and roll back after each test. Set `TEST_DATABASE_URL` to point them somewhere else.

## Migrations

```sh
uv run alembic revision --autogenerate -m "what changed"
uv run alembic upgrade head
uv run alembic downgrade -1
```
