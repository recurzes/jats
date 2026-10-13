import logging

import pytest
from cryptography.fernet import Fernet

from app.config import SettingsError, get_settings
from app.crypto import DecryptError, decrypt, encrypt

SECRET = "1//refresh-token-value"


def test_round_trip() -> None:
    encrypted = encrypt(SECRET)

    assert SECRET not in encrypted
    assert decrypt(encrypted) == SECRET


def test_same_value_encrypts_differently_each_time() -> None:
    assert encrypt(SECRET) != encrypt(SECRET)


def test_wrong_key_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    encrypted = encrypt(SECRET)
    monkeypatch.setattr(get_settings(), "token_enc_key", Fernet.generate_key().decode())

    with pytest.raises(DecryptError):
        decrypt(encrypted)


def test_tampered_value_fails() -> None:
    encrypted = encrypt(SECRET)
    tampered = encrypted[:20] + ("A" if encrypted[20] != "A" else "B") + encrypted[21:]

    with pytest.raises(DecryptError):
        decrypt(tampered)


@pytest.mark.parametrize("key", ["", "not-a-fernet-key"])
def test_missing_or_bad_key_fails_with_clear_message(
    key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "token_enc_key", key)

    with pytest.raises(SettingsError, match="TOKEN_ENC_KEY"):
        encrypt(SECRET)


def test_nothing_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        decrypt(encrypt(SECRET))

    assert caplog.records == []
