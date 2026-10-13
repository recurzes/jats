import os
from collections.abc import Iterator
from pathlib import Path

# Point the app at the test database before anything imports app.config.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://jats:jats@localhost:5433/jats_test"
)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402

API_DIR = Path(__file__).resolve().parent.parent


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
