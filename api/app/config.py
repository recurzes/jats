import uuid
from functools import lru_cache

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    environment: str = "development"

    # The Neon Auth URL of the project. Access tokens are checked against its public signing keys.
    # Optional so migrations and the CLI run without it; while it is empty every token is refused.
    neon_auth_base_url: str = ""
    # The only user allowed in. No Neon Auth user has the placeholder id, so it locks everyone out.
    owner_user_id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # Comma-separated browser origins allowed to call the API.
    cors_origins: str = "http://localhost:5173"

    # Fernet key that encrypts the Gmail refresh token at rest. Optional like the Neon Auth URL;
    # while it is empty nothing can be encrypted or decrypted.
    token_enc_key: str = ""
    # Signs the `state` value of the Gmail connect flow. While it is empty no state is valid.
    state_secret: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    # Where the Google callback sends the browser back to.
    frontend_url: str = "http://localhost:5173"

    # The in-process scheduler runs a Gmail sync this often. Tests turn the scheduler off.
    sync_interval_minutes: int = Field(default=5, ge=1)
    scheduler_enabled: bool = True

    # Any OpenAI-compatible provider. An empty base URL means OpenAI itself.
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = Field(default=30, gt=0)

    # A result less confident than this is flagged for review and not printed.
    review_threshold: float = Field(default=0.6, ge=0, le=1)
    # AI calls one sync may make; the rest wait for the next run. 0 turns classification off.
    max_classifications_per_run: int = Field(default=30, ge=0)

    receipt_width: int = 32  # characters per line on 58 mm paper
    lease_seconds: int = 60
    max_attempts: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


class SettingsError(RuntimeError):
    pass


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        names = ", ".join(str(error["loc"][0]).upper() for error in exc.errors())
        raise SettingsError(
            f"Missing or invalid settings: {names}. "
            "Set them in the environment or in api/.env (see .env.example)."
        ) from None
