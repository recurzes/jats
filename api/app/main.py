from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_error_handlers
from app.logging import RequestIdMiddleware, configure_logging
from app.printing.device_router import router as device_router
from app.printing.devices_router import router as devices_router

configure_logging()
settings = get_settings()  # fail at startup, not on the first request, if settings are missing

app = FastAPI(title="Jats API")
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
