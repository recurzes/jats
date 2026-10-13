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

## Docker

```sh
docker build -t jats-api api          # from the repo root
```

The container runs `alembic upgrade head` and then uvicorn on port 8000. If the migration fails, the container exits and the deploy fails.

## CI/CD

[.github/workflows/api.yml](../.github/workflows/api.yml) runs on pull requests and on pushes to `main`:

```
PR             -> test (ruff + pytest)
merge to main  -> test -> build -> push ghcr.io/<owner>/jats-api:sha-<commit> -> Trivy scan
               -> deploy to Dokploy -> smoke test /health
manual run     -> rollback_tag redeploys an existing sha- tag
```

The deploy job is skipped until Dokploy is set up. To turn it on, in the GitHub repo settings:

| Where | Type | Name | Value |
| --- | --- | --- | --- |
| Repo | Secret | `DOKPLOY_URL` | `https://dokploy.example.com`, no trailing slash |
| Repo | Secret | `DOKPLOY_API_KEY` | Dokploy > Settings > Profile > API/CLI |
| Repo | Variable | `IMAGE_PLATFORM` | `linux/arm64` (default) or `linux/amd64`, matching the server |
| Repo | Variable | `DEPLOY_ENABLED` | `true` |
| `production` environment | Secret | `DOKPLOY_APP_ID` | the Dokploy application ID |
| `production` environment | Variable | `HEALTH_URL` | `https://<api-domain>/health` |

In Dokploy, the application uses source type **Docker**, a GHCR registry entry with a `read:packages` token, port 8000, and `DATABASE_URL` and `ENVIRONMENT` set as env vars.

To roll back: Actions > api > Run workflow, and put an older tag such as `sha-<commit>` in `rollback_tag`.
