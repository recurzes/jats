import uuid
from functools import lru_cache

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    environment: str = "development"

    # Placeholder until web auth exists; the real owner id replaces it then.
    owner_user_id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")

    receipt_width: int = 32  # characters per line on 58 mm paper
    lease_seconds: int = 60
    max_attempts: int = 5


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
