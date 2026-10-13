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

## Device and print queue

```sh
uv run python -m app.cli create-device "desk-esp32"     # prints the device key once
uv run python -m app.cli enqueue-test --status REJECTED # queues a sample receipt
```

Both commands use `DATABASE_URL`, so point it at production to register the real ESP32.

The ESP32 sends its key in the `X-Device-Key` header and only uses these three endpoints:

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/device/jobs/next` | Claims the oldest waiting job and returns its receipt lines, or 204 |
| POST | `/device/jobs/{id}/ack` | Marks the job printed; safe to repeat |
| POST | `/device/jobs/{id}/fail` | Body `{"reason": "bt_connect" \| "out_of_paper" \| "print_error" \| "other"}`; requeues the job |

A claimed job that is never acked returns to the queue after `LEASE_SECONDS`. After `MAX_ATTEMPTS` claims it is marked `failed`.

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

The container runs uvicorn on port 8000. It does not run migrations; CI does that before each deploy.

## CI/CD

[.github/workflows/api.yml](../.github/workflows/api.yml) runs when `api/` or the workflow file changes:

```
any push or PR  -> lint-and-test (ruff, migrations up and down, pytest) + image (build, serve /health)
push to main    -> build -> push ghcr.io/<owner>/jats-api:sha-<commit> -> Trivy scan
                -> migrate production -> deploy to Dokploy -> wait for Dokploy -> smoke test /health
manual run      -> rollback_tag redeploys an existing sha- tag, without migrating
```

The deploy job is skipped until the repo variable `DEPLOY_ENABLED` is `true`. Set that last, at repo level, after these are in the `production` environment (or the repo) in GitHub settings:

| Type | Name | Value |
| --- | --- | --- |
| Secret | `DOKPLOY_URL` | `https://dokploy.example.com`, no trailing slash |
| Secret | `DOKPLOY_API_KEY` | Dokploy > Settings > Profile > API/CLI |
| Secret | `DOKPLOY_APP_ID` | the Dokploy application ID |
| Secret | `CF_ACCESS_CLIENT_ID` | Cloudflare Access service token id |
| Secret | `CF_ACCESS_CLIENT_SECRET` | Cloudflare Access service token secret |
| Secret | `GHCR_PULL_USERNAME` | GitHub username, lowercase |
| Secret | `GHCR_PULL_TOKEN` | GitHub token with `read:packages` |
| Secret | `MIGRATION_DATABASE_URL` | production database URL, starting `postgresql+psycopg://` |
| Variable | `HEALTH_URL` | `https://<api-domain>/health` |

In Dokploy, the application uses source type **Docker**, port 8000, and `DATABASE_URL` and `ENVIRONMENT` set as env vars.

To roll back: Actions > api > Run workflow, and put an older tag such as `sha-<commit>` in `rollback_tag`.
