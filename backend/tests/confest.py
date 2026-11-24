
import pytest

from app.core.config import settings


@pytest.fixture(scope="session", autouse=True)
def require_test_database():
    if settings.MYSQL_DATABASE != "lankapex_test_db":
        pytest.fail(
            "Tests must run against lankapex_test_db. "
            "Main development database is not allowed."
        )
