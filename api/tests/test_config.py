import pytest

from app.config import Settings, SettingsError, get_settings


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@host/db")
    monkeypatch.setenv("ENVIRONMENT", "production")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://u:p@host/db"
    assert settings.environment == "production"


def test_missing_database_url_fails_with_clear_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.chdir(tmp_path)  # no .env here
    get_settings.cache_clear()

    try:
        with pytest.raises(SettingsError, match="DATABASE_URL"):
            get_settings()
    finally:
        get_settings.cache_clear()
