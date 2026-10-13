# Jats

Job application tracker: Gmail in, statuses on a board, receipts out of a thermal printer.

- [api/](api/): FastAPI backend
- `web/`: React board (not started)
- `firmware/`: ESP32 print client (not started)

Local Postgres for the API: `docker compose up -d` (port 5433, databases `jats` and `jats_test`).
