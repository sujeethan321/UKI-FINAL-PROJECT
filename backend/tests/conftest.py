"""Fail before collection if tests could connect to a non-test database."""
import pytest
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine


def pytest_sessionstart(session):
    if settings.MYSQL_DATABASE != "lankapex_test_db" or engine.url.database != "lankapex_test_db":
        raise pytest.UsageError("Tests require lankapex_test_db")
    with engine.connect() as connection:
        if connection.scalar(text("SELECT DATABASE()")) != "lankapex_test_db":
            raise pytest.UsageError("Actual database must be lankapex_test_db")
