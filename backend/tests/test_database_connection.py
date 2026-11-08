from sqlalchemy import text

from backend.app.database.session import (
    SessionLocal,
)


def test_postgres_connection():
    with SessionLocal() as session:
        result = session.execute(
            text("SELECT 1")
        ).scalar_one()

    assert result == 1