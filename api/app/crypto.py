from cryptography.fernet import Fernet, InvalidToken

from app.config import SettingsError, get_settings


class DecryptError(Exception):
    """The value was not encrypted with the current TOKEN_ENC_KEY, or it was altered."""


def _fernet() -> Fernet:
    try:
        return Fernet(get_settings().token_enc_key)
    except ValueError:
        raise SettingsError(
            "TOKEN_ENC_KEY is missing or is not a Fernet key (see .env.example)."
        ) from None


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        # Raised without the cause, so neither value can end up in a traceback.
        raise DecryptError("Could not decrypt the value with TOKEN_ENC_KEY") from None
