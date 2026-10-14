from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.applications.router import router as applications_router
from app.config import get_settings
from app.errors import register_error_handlers
from app.gmail.router import router as gmail_router
from app.gmail.router import sync_router
from app.gmail.scheduler import start_scheduler
from app.logging import RequestIdMiddleware, configure_logging
from app.printing.device_router import router as device_router
from app.printing.devices_router import router as devices_router
from app.sentry import init_sentry
from app.status.router import router as status_router

configure_logging()
settings = get_settings()  # fail at startup, not on the first request, if settings are missing
init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = start_scheduler() if get_settings().scheduler_enabled else None
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown()


DESCRIPTION = """
Three kinds of caller:

- **The web app** sends a Neon Auth token as `Authorization: Bearer <token>`. Only the owner's
  token is accepted.
- **The ESP32** sends its device key as `X-Device-Key`, and can only call the `/device` routes.
- **Anyone** can call `/health`. Google sends the browser to `/auth/google/callback`.

Every error has the same body, `{"error": {"code": "...", "message": "..."}}`. Branch on `code`;
`message` is for a person to read.
"""

TAGS = [
    {"name": "applications", "description": "The board: list, read, fix and reprint."},
    {"name": "status", "description": "What the status strip shows."},
    {"name": "gmail", "description": "Connecting Gmail and syncing it."},
    {"name": "devices", "description": "Registering a printer device."},
    {"name": "device", "description": "The print queue, as the ESP32 sees it."},
    {"name": "health", "description": "Liveness check."},
]

app = FastAPI(
    title="Jats API",
    version="0.1.0",
    description=DESCRIPTION,
    openapi_tags=TAGS,
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)
# Added last so it wraps everything else and error responses get the CORS headers too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization"],
)
register_error_handlers(app)
app.include_router(applications_router)
app.include_router(status_router)
app.include_router(gmail_router)
app.include_router(sync_router)
app.include_router(devices_router)
app.include_router(device_router)


class Health(BaseModel):
    status: str = "ok"


@app.get("/health", tags=["health"], summary="Check the API is up")
def health() -> Health:
    return Health()
