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
uv run python -m app.cli list-devices                   # id, name and last poll of each device
uv run python -m app.cli delete-device <id>             # the device's key stops working
```

Every command uses `DATABASE_URL`, so point it at production to register the real ESP32.

The ESP32 sends its key in the `X-Device-Key` header and only uses these three endpoints:

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/device/jobs/next` | Claims the oldest waiting job and returns its receipt lines, or 204 |
| POST | `/device/jobs/{id}/ack` | Marks the job printed; safe to repeat |
| POST | `/device/jobs/{id}/fail` | Body `{"reason": "bt_connect" \| "out_of_paper" \| "print_error" \| "other"}`; requeues the job |

A claimed job that is never acked returns to the queue after `LEASE_SECONDS`. After `MAX_ATTEMPTS` claims it is marked `failed`.

## Web auth

Login is Neon Auth. The web app gets a token from `authClient.token()` and sends it as `Authorization: Bearer <token>`; tokens last 15 minutes. The API checks the EdDSA signature against the project's public signing keys (`NEON_AUTH_BASE_URL`), the expiry, and that the issuer and audience are the origin of that URL, then checks the user id is `OWNER_USER_ID`.

| Response | Meaning |
| --- | --- |
| 401 `AUTH_INVALID` | Missing, expired, tampered or otherwise invalid token |
| 403 `NOT_OWNER` | A valid token for a user who is not the owner |

One-time setup in the Neon console, under Auth: create your user, copy its id into `OWNER_USER_ID`, and turn off public sign-ups.

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/devices` | Body `{"name": "desk-esp32"}`; returns `{id, name, key}`. The key is shown only in this response |

Browsers may call the API from the origins in `CORS_ORIGINS` (comma-separated), with methods GET, POST and PATCH.

## Gmail connection

One-time setup in the Google Cloud console: enable the Gmail API, set up an External consent screen with the `https://www.googleapis.com/auth/gmail.readonly` scope, create a Web OAuth client whose redirect URIs are the local and deployed `/auth/google/callback`, and **publish** the app (it stays unverified). An app left in *Testing* loses its refresh token after 7 days. Then fill in `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `FRONTEND_URL`, `TOKEN_ENC_KEY` and `STATE_SECRET`; `.env.example` has the commands that generate the last two.

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/auth/google/start` | Owner only. Returns `{"url": "..."}`; the web app navigates to it |
| GET | `/auth/google/callback` | Public; Google sends the browser here. Stores the refresh token and redirects to `FRONTEND_URL/?gmail=connected`, or `?gmail=error` |

The `state` value in the URL is signed with `STATE_SECRET` and lasts 10 minutes; the callback trusts nothing else. The refresh token is stored encrypted with `TOKEN_ENC_KEY` and never logged. If it leaks, revoke it in your Google account settings. Running the flow again replaces the stored token.

```sh
uv run python -m app.cli gmail-address    # asks Gmail for the address, using the stored token
```

Until the Google values, `STATE_SECRET` and `TOKEN_ENC_KEY` are all set, `/auth/google/start` answers 503 `GMAIL_CONFIG`.

## Gmail sync

While `SCHEDULER_ENABLED` is true, the API syncs the connected inbox every `SYNC_INTERVAL_MINUTES` (default 5), in-process. The first sync lists the last 7 days; later ones ask Gmail only for what changed since the stored history id, and fall back to the 7-day listing when that id has expired.

Each new message becomes an `emails` row with its subject, sender and a snippet of at most 500 characters. The body is read for classification only and is never stored. `is_candidate` marks the emails worth an AI call: mail from a job board, or with a job keyword in the subject. Both lists are in [app/classifier/rules.py](app/classifier/rules.py).

Every run leaves a `sync_runs` row:

| `result` | Meaning |
| --- | --- |
| `ok` | Finished |
| `fallback_full` | Finished, after the history id had expired and the last 7 days were listed again |
| `skipped_locked` | Another sync was running; a Postgres advisory lock lets one run at a time |
| `error` | Failed; `error` has the message. Rows saved before the failure are kept and the rest is read again next time |

If Gmail refuses the refresh token, the account is marked `needs_reauth` and syncing stops until the connect flow is run again.

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/sync` | Owner only. Starts a sync in the background and answers 202; 409 `GMAIL_NOT_CONNECTED` or `GMAIL_NEEDS_REAUTH` when there is nothing to sync |

```sh
uv run python -m app.cli gmail-count      # how many messages the inbox got in the last 7 days
uv run python -m app.cli sync             # runs one sync now and prints the counts
```

The advisory lock needs a direct database connection, not Neon's pooled one (see `.env.example`).

## Classifier

Candidate emails are classified by an AI provider, through one OpenAI-compatible client: set `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL`, and swap providers by changing only those. The provider has to support JSON mode (`response_format: json_object`). A call waits `LLM_TIMEOUT_SECONDS` (default 30) and is retried once, 2 seconds later, on a 429, a 5xx or a timeout.

```sh
uv run python -m app.cli llm-ping         # asks the provider for a one-line reply
```

The provider gets the sender, the subject, the date and at most 3,000 characters of the body, wrapped in `<email>` tags; the prompt in [app/classifier/prompts.py](app/classifier/prompts.py) tells the model that text is data, not instructions. The answer is validated against [app/classifier/schema.py](app/classifier/schema.py): `is_job_related`, `company`, `role`, `status` (`acknowledged`, `replied`, `update` or `rejected`) and `confidence` from 0 to 1. An answer that fails validation is asked for once more, then given up on.

`classify_and_store()` puts the result on the `emails` row, and the sync commits it together with what the result changes:

| Outcome | What is saved |
| --- | --- |
| Classified | `classification` (the JSON), `confidence` and `processed_at`. An email with `processed_at` is never sent to the AI again |
| No valid answer after the retry, or the provider refused the request (a 4xx) | `classification_attempts` goes up by one; `processed_at` stays empty |
| Provider down or key refused (`LLMUnavailable`, `LLMAuthError`) | Nothing; the error is raised to the caller |

The API key, the email text and the provider's answers are never logged.

## Applications and auto-print

Every sync ends by sending the waiting candidates to the AI, oldest first, and applying each answer with `apply_classification()` in [app/applications/service.py](app/applications/service.py). The email, its application, the status event and the print job are saved in one transaction.

1. An email that is not about a job is marked processed and nothing else happens.
2. The application is found by Gmail thread first, then by company name among the applications that are not `rejected`. Company names are compared through `normalize_company()`, so `Acme Corp.` and `ACME, Inc.` are the same company. No match creates a new application.
3. The status changes unless it is the same status again, or an `acknowledged` arriving after any other status (a late auto-reply). A change is recorded as a `status_events` row.
4. Each change queues one receipt for the ESP32.

A result with confidence below `REVIEW_THRESHOLD` (default 0.6), or for an application with no company (it is named `Unknown`), sets `needs_review` and prints nothing. The status change is still recorded.

An email in a thread that already has an application is always a candidate, whatever its sender and subject, so a recruiter replying from a personal address is not missed.

| Limit | What happens |
| --- | --- |
| `MAX_CLASSIFICATIONS_PER_RUN` (default 30) | A sync makes at most this many AI calls and leaves the rest for the next one. `0` turns classification off |
| 3 attempts | An email the AI cannot classify is tried on three syncs, its body read from Gmail again each time. Then it is marked processed with `classification = {"error": "..."}` and a warning is logged |
| Provider down or key refused | The sync stops classifying and its `sync_runs` row is an `error`. The emails are already stored, no attempt is counted, and the next sync picks them up |

Three database rules stop anything being written twice: `emails.gmail_message_id` is unique, an email has at most one status event, and a status event has at most one print job.

### Accuracy

```sh
uv run python -m scripts.eval_classifier  # calls the real provider, once per email
```

It classifies every email in the JSON files under [tests/fixtures/classifier/](tests/fixtures/classifier/) and prints the accuracy and each miss; the target is 85%. `synthetic.json` has 20 made-up emails. Put real ones in `tests/fixtures/classifier/local/*.json`, in the same format with `"expected"` set to a status or `null` for mail that is not job related. That folder is gitignored, because real emails hold personal data.

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

In Dokploy, the application uses source type **Docker**, port 8000, and `DATABASE_URL`, `ENVIRONMENT`, `NEON_AUTH_BASE_URL`, `OWNER_USER_ID`, `CORS_ORIGINS`, `TOKEN_ENC_KEY`, `STATE_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `FRONTEND_URL`, `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` set as env vars. The [env var table](#environment-variables) lists the optional ones.

To roll back: Actions > api > Run workflow, and put an older tag such as `sha-<commit>` in `rollback_tag`.

## Board API

What the web app runs on. Every route is owner only, and the board refreshes by polling.

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/applications` | The cards, most recently changed first. Optional filters `status` and `needs_review`; an empty value means no filter |
| GET | `/applications/{id}` | One application with its emails and status events, both newest first. 404 `NOT_FOUND` |
| PATCH | `/applications/{id}` | Any of `status`, `company`, `role`, `needs_review`. Returns the same body as the GET |
| POST | `/applications/{id}/reprint` | Queues a receipt for the current status and answers 201 `{job_id}`. 409 `REPRINT_PENDING` while an earlier reprint is still waiting |
| GET | `/status` | `last_sync`, `gmail`, `device`, `queue` and `failed_classifications`, for the status strip |

A manual fix through PATCH:

- A new status is recorded as a `status_events` row with `source = manual`. It prints nothing; the reprint covers that.
- Sending a status, even the one the card already has, clears `needs_review`. Sending `needs_review` in the same request wins.
- A new company also replaces `company_key`, so later emails match the corrected name.
- `"role": null` clears the role. The other fields cannot be null.

A reprint is a print job with no `status_event_id` and the application in `application_id`. When the current status came from an email, the receipt is the same as the first one. After a manual change it has no subject and no match line.

In `/status`, `device.online` means the most recently seen device polled within the last 2 minutes. `last_sync` is the latest run that was not `skipped_locked`, and its `result` is empty while it is still running. `queue` counts `pending` and `failed` print jobs. `failed_classifications` counts the emails the classifier gave up on.

## API contract

Every error, whatever its status code, has the body `{"error": {"code": "...", "message": "..."}}`. `code` is stable; `message` is for a person to read.

The web app reads only [../contracts/openapi.json](../contracts/openapi.json) and generates its types from it. After changing a route or a response model, write the file again and commit it:

```sh
uv run python -m scripts.export_openapi
```

A test fails while the committed file is out of date.

## Logs and errors

Every log line is one JSON object on stdout, with the `request_id` that the response carries in `X-Request-ID`. In production, read them in Dokploy under the application's Logs tab.

A filter on the log handler replaces credentials with `***` before a line is written: the value of any header, field or query parameter named like a secret (`Authorization`, `X-Device-Key`, `Cookie`, and any name ending in `token`, `secret`, `password` or `api_key`), anything shaped like a token (a JWT, a device key, a Google token or authorisation code, an `sk-` key, a Fernet token, the password in a URL), and the configured values of `LLM_API_KEY`, `TOKEN_ENC_KEY`, `STATE_SECRET` and `GOOGLE_CLIENT_SECRET`. It covers the message, the `data` fields and the traceback. The access line has the path without the query string, and a failed database statement is logged without its values.

Email bodies, AI prompts and AI answers are never passed to a logger. Keep it that way: log the `gmail_message_id`, not the text.

While `SENTRY_DSN` is set, unhandled errors and `ERROR` log lines go to Sentry. An event keeps only the method and URL of its request: headers, cookies, the query string, the body and the local variables of stack frames are left out, and the rest goes through the same masking as the logs.

```sh
uv run python -m app.cli sentry-test      # sends one test error; needs SENTRY_DSN
```

## Runbook

### Environment variables

Locally they live in `api/.env`; in production, in the Dokploy application's Environment tab. `.env.example` has a comment on each. Changing one in Dokploy needs a redeploy to take effect.

| Name | Production | Default | What it is |
| --- | --- | --- | --- |
| `DATABASE_URL` | required | none | Neon's *direct* connection string, with the scheme `postgresql+psycopg://`. Not the pooled one |
| `ENVIRONMENT` | `production` | `development` | A label, sent to Sentry |
| `NEON_AUTH_BASE_URL` | required | empty | Neon console > Auth > Configuration. Empty refuses every token |
| `OWNER_USER_ID` | required | a placeholder | Your user id, from Neon console > Auth > Users. The placeholder locks everyone out |
| `CORS_ORIGINS` | required | `http://localhost:5173` | Comma-separated origins of the web app |
| `TOKEN_ENC_KEY` | required | empty | Fernet key that encrypts the Gmail refresh token. Changing it means [reconnecting Gmail](#reconnect-gmail) |
| `STATE_SECRET` | required | empty | Signs the `state` of the Gmail connect flow |
| `GOOGLE_CLIENT_ID` | required | empty | The Web OAuth client, from the Google Cloud console |
| `GOOGLE_CLIENT_SECRET` | required | empty | Same client |
| `GOOGLE_REDIRECT_URI` | required | `http://localhost:8000/auth/google/callback` | `https://<api-domain>/auth/google/callback`, exactly as registered on the client |
| `FRONTEND_URL` | required | `http://localhost:5173` | Where the Google callback sends the browser back to |
| `LLM_BASE_URL` | optional | empty | An OpenAI-compatible API. Empty means OpenAI itself |
| `LLM_API_KEY` | required | empty | The AI provider's key |
| `LLM_MODEL` | required | empty | The model name, as the provider spells it |
| `LLM_TIMEOUT_SECONDS` | optional | `30` | How long one AI call may take |
| `SYNC_INTERVAL_MINUTES` | optional | `5` | Minutes between Gmail syncs |
| `SCHEDULER_ENABLED` | optional | `true` | `false` stops the automatic syncs; `POST /sync` still works |
| `REVIEW_THRESHOLD` | optional | `0.6` | A less confident result is flagged for review and not printed |
| `MAX_CLASSIFICATIONS_PER_RUN` | optional | `30` | AI calls per sync. `0` turns classification off |
| `SENTRY_DSN` | optional | empty | Sentry > Project settings > Client keys. Empty turns Sentry off |
| `RECEIPT_WIDTH` | optional | `32` | Characters per receipt line; 32 is 58 mm paper |
| `LEASE_SECONDS` | optional | `60` | A claimed job that is not acked returns to the queue after this long |
| `MAX_ATTEMPTS` | optional | `5` | Claims before a print job is marked `failed` |

`TEST_DATABASE_URL` is read by the tests only.

Generate the two keys with the commands in `.env.example`. Keep a copy of every production value in a password manager: Dokploy is the only other place they exist.

### Rebuild from scratch

1. **Database.** Create a Neon project. Turn on Neon Auth, create your user, turn off public sign-ups, and note the Auth URL and your user id ([Web auth](#web-auth)).
2. **Google.** Set up the OAuth client and publish the consent screen ([Gmail connection](#gmail-connection)).
3. **Dokploy.** Create an application with source type Docker and port 8000, give it a domain, and set the env vars from the table above.
4. **GitHub.** Add the secrets and variables in [CI/CD](#cicd), then set `DEPLOY_ENABLED` to `true`.
5. **Deploy.** Push to `main`. The workflow migrates the database, deploys the image and checks `/health`.
6. **Printer.** [Create a device key](#create-or-rotate-a-device-key) and flash it to the ESP32.
7. **Gmail.** [Connect Gmail](#reconnect-gmail).
8. **Check.** Run the [smoke test](#smoke-test).

### Deploy and roll back

A push to `main` that changes `api/` deploys by itself; watch it under Actions > api. A red `lint-and-test`, `image` or `build` job deploys nothing. A red `deploy` job at the *Migrate* step also deploys nothing, and the old version keeps serving.

To roll back the code: Actions > api > Run workflow, with an older tag such as `sha-<commit>` in `rollback_tag`. This redeploys that image and does not touch the database.

To redeploy without a code change, for example after editing an env var, press Deploy on the application in Dokploy.

### Migrations in production

CI runs `alembic upgrade head` against production before each deploy, so there is normally nothing to do by hand. The container never migrates.

A migration must leave the previous image working, because a rollback runs old code on the new schema: add columns as nullable or with a default, and drop a column only in a later deploy than the one that stops using it.

To run one by hand, from `api/` with `DATABASE_URL` set to the production database:

```sh
uv run alembic current                    # the revision the database is at
uv run alembic upgrade head
uv run alembic downgrade -1               # undoes the last one; loses the data it added
```

### Create or rotate a device key

All from `api/`, with `DATABASE_URL` set to the production database. A key is shown once and only its hash is stored, so a lost key cannot be read back, only replaced.

```sh
uv run python -m app.cli create-device "desk-esp32"     # prints the new key
uv run python -m app.cli list-devices
uv run python -m app.cli delete-device <id of the old device>
```

To rotate: create a device, flash the new key to the ESP32, check that `list-devices` shows the new device polling, then delete the old one. Deleting first works too, but nothing prints until the new key is flashed. If a key leaks, delete its device straight away. The web app can also create a device, with `POST /devices`.

### Reconnect Gmail

Needed when `/status` shows `gmail.state` as `needs_reauth` (Google refused the refresh token: it was revoked, the Google password changed, or the consent screen was left in *Testing*), and after changing `TOKEN_ENC_KEY`, which shows up as every sync ending in `error` with a decrypt message.

Press connect in the web app. Without it, ask the API for the consent URL and open the `url` it returns in a browser:

```sh
curl -H "Authorization: Bearer <token>" https://<api-domain>/auth/google/start
```

`<token>` is your access token: `await authClient.token()` in the web app's browser console. Google sends the browser back to `FRONTEND_URL/?gmail=connected`. The stored token is replaced, the account goes back to `ok`, and the next sync starts within `SYNC_INTERVAL_MINUTES`; `POST /sync` starts one now. Mail that arrived in the meantime is picked up, as long as it is less than 7 days old.

If it comes back as `?gmail=error`, the log line that starts `Gmail connect failed` says why. A 503 `GMAIL_CONFIG` from `/auth/google/start` means one of the Google values, `STATE_SECRET` or `TOKEN_ENC_KEY` is missing.

### The printer is offline

Nothing is lost while the printer is off: receipts wait in the queue as `pending` and print in order when the ESP32 polls again.

Look at `/status`:

| What it shows | Meaning | What to do |
| --- | --- | --- |
| `device.online` is `false` | The ESP32 has not polled for 2 minutes | Check its power and Wi-Fi. If it polls and gets a 401, its key was deleted or is wrong: [create a new one](#create-or-rotate-a-device-key) |
| `device.online` is `true`, `queue.pending` keeps growing | The ESP32 reaches the API but cannot print | Check the printer's power, its Bluetooth pairing and the paper. The `failure_reason` column of `print_jobs` has what the ESP32 reported |
| `queue.failed` above 0 | A job was claimed `MAX_ATTEMPTS` times without printing | Fix the printer, then reprint from the board: `POST /applications/{id}/reprint` |

To check the path end to end, queue a sample receipt with `uv run python -m app.cli enqueue-test`.

### Smoke test

```sh
API_URL=https://<api-domain> SMOKE_TOKEN=<token> DEVICE_KEY=<key> bash scripts/smoke.sh
```

It checks one route per kind of caller: `/health` (public), `/status` (the web app, with your access token) and `/device/jobs/next` (the ESP32, with a device key), and exits 0 only when all three answer. `<token>` lasts 15 minutes.

The device check is a real claim. If a job is waiting, the script claims it instead of the printer; the job returns to the queue after `LEASE_SECONDS` with one attempt used. Run it when the queue is empty, or accept the delay.

### Something is wrong and it is 2am

1. `curl https://<api-domain>/health`. No answer: the container is down. Look at the Dokploy logs and redeploy, or [roll back](#deploy-and-roll-back).
2. `/status`. `last_sync.result` is `error`: `last_sync.error` has the message. `gmail.state` is `needs_reauth`: [reconnect Gmail](#reconnect-gmail). `last_sync.started_at` is old: the scheduler is not running; check `SCHEDULER_ENABLED` and restart the application.
3. `failed_classifications` is going up, or syncs end in an AI error: run `uv run python -m app.cli llm-ping`. A refused key or an empty balance at the provider shows up here.
4. Emails arrive but nothing prints: see [The printer is offline](#the-printer-is-offline). A card flagged `needs_review` prints nothing on purpose.
5. Search the logs for the `request_id` of a failed response, or look in Sentry.
