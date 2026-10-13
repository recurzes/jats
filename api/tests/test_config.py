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


def test_sync_settings_have_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SYNC_INTERVAL_MINUTES")
    monkeypatch.delenv("SCHEDULER_ENABLED")

    settings = Settings(_env_file=None)

    assert settings.sync_interval_minutes == 5
    assert settings.scheduler_enabled is True


def test_sync_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNC_INTERVAL_MINUTES", "1")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")

    settings = Settings(_env_file=None)

    assert settings.sync_interval_minutes == 1
    assert settings.scheduler_enabled is False


def test_sync_interval_must_be_at_least_a_minute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNC_INTERVAL_MINUTES", "0")
    get_settings.cache_clear()

    try:
        with pytest.raises(SettingsError, match="SYNC_INTERVAL_MINUTES"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_llm_settings_have_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name)

    settings = Settings(_env_file=None)

    assert (settings.llm_base_url, settings.llm_api_key, settings.llm_model) == ("", "", "")
    assert settings.llm_timeout_seconds == 30


def test_llm_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("LLM_API_KEY", "key")
    monkeypatch.setenv("LLM_MODEL", "small-model")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "10")

    settings = Settings(_env_file=None)

    assert settings.llm_base_url == "https://llm.example/v1"
    assert settings.llm_api_key == "key"
    assert settings.llm_model == "small-model"
    assert settings.llm_timeout_seconds == 10
