from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_error_handlers
from app.gmail.router import router as gmail_router
from app.gmail.router import sync_router
from app.gmail.scheduler import start_scheduler
from app.logging import RequestIdMiddleware, configure_logging
from app.printing.device_router import router as device_router
from app.printing.devices_router import router as devices_router

configure_logging()
settings = get_settings()  # fail at startup, not on the first request, if settings are missing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = start_scheduler() if get_settings().scheduler_enabled else None
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown()


app = FastAPI(title="Jats API", lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)
# Added last so it wraps everything else and error responses get the CORS headers too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization"],
)
register_error_handlers(app)
app.include_router(device_router)
app.include_router(devices_router)
app.include_router(gmail_router)
app.include_router(sync_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
