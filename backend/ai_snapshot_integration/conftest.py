"""Live only through the guarded dedicated-schema operator launcher."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import engine
from scripts.check_ai_snapshot_test_runtime import main as preflight


def pytest_sessionstart(session):
    preflight()


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autoflush=False, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
