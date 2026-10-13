import os
from collections.abc import Iterator
from pathlib import Path

# Point the app at the test database before anything imports app.config.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://jats:jats@localhost:5433/jats_test"
)
# Fixed values, so a developer's own environment or .env cannot change what the tests see.
os.environ["NEON_AUTH_BASE_URL"] = "https://ep-test.neonauth.example.com/neondb/auth"
os.environ["OWNER_USER_ID"] = "11111111-1111-1111-1111-111111111111"
os.environ["CORS_ORIGINS"] = "http://localhost:5173, https://jats.example.com"
os.environ["TOKEN_ENC_KEY"] = "dGVzdC1rZXktdGVzdC1rZXktdGVzdC1rZXktMTIzNDU="  # a Fernet key
os.environ["STATE_SECRET"] = "test-state-secret-that-is-long-enough-to-sign"
os.environ["GOOGLE_CLIENT_ID"] = "test-client.apps.googleusercontent.com"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
os.environ["GOOGLE_REDIRECT_URI"] = "http://localhost:8000/auth/google/callback"
os.environ["FRONTEND_URL"] = "http://localhost:5173"

from collections.abc import Callable  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from jwt.algorithms import OKPAlgorithm  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth.device import generate_device_key, hash_device_key  # noqa: E402
from app.auth.jwt import issuer, jwk_client  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.printing.models import Device  # noqa: E402

API_DIR = Path(__file__).resolve().parent.parent
TEST_KEY_ID = "test-key"


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database() -> None:
    config = Config(API_DIR / "alembic.ini")
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")


@pytest.fixture
def db() -> Iterator[Session]:
    """A session inside a transaction that is rolled back after the test."""
    connection = engine.connect()
    transaction = connection.begin()
    # Commits inside the test only release a savepoint, so the rollback still undoes them.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def signing_key() -> Ed25519PrivateKey:
    """Stands in for the Neon Auth project's signing key."""
    return Ed25519PrivateKey.generate()


@pytest.fixture(autouse=True)
def neon_auth_jwks(
    signing_key: Ed25519PrivateKey, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Serve the test key as the project's key set, so no test calls Neon Auth."""
    jwk = OKPAlgorithm.to_jwk(signing_key.public_key(), as_dict=True)
    jwk.update(kid=TEST_KEY_ID, alg="EdDSA")
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: {"keys": [jwk]})
    jwk_client.cache_clear()
    yield
    jwk_client.cache_clear()


@pytest.fixture
def make_token(signing_key: Ed25519PrivateKey) -> Callable[..., str]:
    """Build a Neon Auth-style token; keyword arguments override or add claims."""

    def make(
        sub: object = None, key: object = None, algorithm: str = "EdDSA", **claims: object
    ) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(sub or get_settings().owner_user_id),
            "aud": issuer(),
            "iss": issuer(),
            "iat": now,
            "exp": now + timedelta(minutes=15),
            "role": "user",
            **claims,
        }
        return jwt.encode(
            payload, key or signing_key, algorithm=algorithm, headers={"kid": TEST_KEY_ID}
        )

    return make


@pytest.fixture
def auth_headers(make_token: Callable[..., str]) -> dict[str, str]:
    """Headers of the logged-in owner."""
    return {"Authorization": f"Bearer {make_token()}"}


@pytest.fixture
def device_key(db: Session) -> str:
    """The key of a device that exists in the database."""
    key = generate_device_key()
    db.add(
        Device(user_id=get_settings().owner_user_id, name="test", key_hash=hash_device_key(key))
    )
    db.commit()
    return key


@pytest.fixture
def device(db: Session, device_key: str) -> Device:
    return db.query(Device).filter_by(key_hash=hash_device_key(device_key)).one()


@pytest.fixture
def device_headers(device_key: str) -> dict[str, str]:
    return {"X-Device-Key": device_key}
