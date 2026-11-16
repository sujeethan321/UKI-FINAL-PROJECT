"""Fail before collection if tests could connect to a non-test database."""
import pytest
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine


def pytest_sessionstart(session):
    if settings.APP_ENV != "testing":
        raise pytest.UsageError("Tests require explicit APP_ENV=testing")
    if settings.MYSQL_DATABASE != "lankapex_test_db" or engine.url.database != "lankapex_test_db":
        raise pytest.UsageError("Tests require lankapex_test_db")
    with engine.connect() as connection:
        if connection.scalar(text("SELECT DATABASE()")) != "lankapex_test_db":
            raise pytest.UsageError("Actual database must be lankapex_test_db")


@pytest.fixture(autouse=True)
def isolated_local_rate_counters():
    # Isolate volatile limiter state, not the database. No production bypass.
    from app.main import app
    limiter = app.state.rate_limiter
    if limiter is not None:
        limiter.clear()
    yield
    if limiter is not None:
        limiter.clear()
