
import pytest

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.core.auth_dependencies import get_current_user


client = TestClient(app)


ROLES = [
    "customer",
    "shop_owner",
    "driver",
    "admin",
]

ENDPOINTS = {
    "customer": "/api/v1/access/customer",
    "shop_owner": "/api/v1/access/shop-owner",
    "driver": "/api/v1/access/driver",
    "admin": "/api/v1/access/admin",
}


@pytest.fixture(autouse=True)
def clear_auth_overrides():
    app.dependency_overrides.pop(get_current_user, None)
    yield
    app.dependency_overrides.pop(get_current_user, None)


def simulate_user(role):
    """
    Substitute an authenticated user for RBAC testing.
    No real JWT or database record is required here.
    """

    def fake_current_user():
        return SimpleNamespace(
            user_id=1,
            full_name="RBAC Test User",
            platform_role=role,
            account_status="active",
        )

    app.dependency_overrides[get_current_user] = fake_current_user


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("endpoint_role", ROLES)
def test_role_access(role, endpoint_role):
    simulate_user(role)

    response = client.get(
        ENDPOINTS[endpoint_role]
    )

    expected_status = (
        200 if role == endpoint_role else 403
    )

    assert response.status_code == expected_status


@pytest.mark.parametrize("endpoint", ENDPOINTS.values())
def test_missing_token_is_rejected(endpoint):
    response = client.get(endpoint)

    assert response.status_code == 401
