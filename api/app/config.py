import uuid
from functools import lru_cache

from pydantic import ValidationError
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
