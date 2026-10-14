import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db import get_db


def test_get_db_yields_a_working_session() -> None:
    generator = get_db()
    session = next(generator)
    try:
        assert session.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        generator.close()


def test_db_fixture_uses_the_test_database(db: Session) -> None:
    assert db.execute(text("SELECT current_database()")).scalar_one().endswith("_test")


def test_db_fixture_rolls_back_part_one(db: Session) -> None:
    db.execute(text("CREATE TABLE rollback_probe (id int)"))
    db.commit()


def test_db_fixture_rolls_back_part_two(db: Session) -> None:
    assert db.execute(text("SELECT to_regclass('rollback_probe')")).scalar_one() is None


def test_a_failed_statement_is_reported_without_its_values(db: Session) -> None:
    # A value too long for its column, as an email subject could be.
    with pytest.raises(DBAPIError) as raised:
        db.execute(text("SELECT CAST(:subject AS varchar(3))::int"), {"subject": "Your offer"})

    assert "[SQL parameters hidden" in str(raised.value)
