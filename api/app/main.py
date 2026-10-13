from fastapi import FastAPI

from app.config import get_settings
from app.errors import register_error_handlers
from app.logging import RequestIdMiddleware, configure_logging

configure_logging()
get_settings()  # fail at startup, not on the first request, if settings are missing

app = FastAPI(title="Jats API")
app.add_middleware(RequestIdMiddleware)
register_error_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
