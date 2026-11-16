"""Database-free contract checks for the customer QR status lookup."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects import mysql

from app.routers.customer_join import customer_router, request_status
from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.schemas.customer_join import JoinRequestStatus
from app.services.customer_join_service import customer_request_status


CODE = "A" * 32
CUSTOMER = SimpleNamespace(user_id=31)


class ReadOnlySession:
    def __init__(self, business_id=7, request=None, profile_id=None):
        self.values = iter((business_id, request, profile_id))
        self.statements = []

    def scalar(self, statement):
        compiled = statement.compile(dialect=mysql.dialect())
        sql = str(compiled)
        self.statements.append((sql, compiled.params))
        assert sql.lstrip().startswith("SELECT ")
        return next(self.values)


@pytest.mark.parametrize("status", ["pending", "approved", "rejected", "cancelled"])
def test_own_request_status_and_scoped_queries(status):
    row = SimpleNamespace(request_id=12, status=status)
    db = ReadOnlySession(request=row, profile_id=5 if status == "approved" else None)
    assert customer_request_status(db, CUSTOMER, CODE) == {"request_id": 12, "status": status}
    assert len(db.statements) == 3
    assert "businesses.approval_status" in db.statements[0][0]
    assert "customer_join_requests.business_id" in db.statements[1][0]
    assert "customer_join_requests.customer_user_id" in db.statements[1][0]
    assert CUSTOMER.user_id in db.statements[1][1].values()
    assert "customer_profiles.business_id" in db.statements[2][0]
    assert "customer_profiles.user_id" in db.statements[2][0]


@pytest.mark.parametrize("profile_id,expected", [(None, "none"), (4, "already_linked")])
def test_no_own_request_including_manual_invitation_link(profile_id, expected):
    db = ReadOnlySession(request=None, profile_id=profile_id)
    assert customer_request_status(db, CUSTOMER, CODE) == {"request_id": None, "status": expected}


def test_other_customer_request_is_not_returned():
    # The database result is empty because the SQL is scoped to the caller.
    db = ReadOnlySession(request=None)
    assert customer_request_status(db, CUSTOMER, CODE)["status"] == "none"
    assert CUSTOMER.user_id in db.statements[1][1].values()


@pytest.mark.parametrize("business_id", [None])
def test_unknown_or_unavailable_business_is_generic_404(business_id):
    db = ReadOnlySession(business_id=business_id)
    with pytest.raises(HTTPException) as error:
        customer_request_status(db, CUSTOMER, CODE)
    assert error.value.status_code == 404
    assert error.value.detail == "Join resource unavailable"
    assert len(db.statements) == 1


def test_approved_request_without_profile_is_conflict():
    db = ReadOnlySession(request=SimpleNamespace(request_id=12, status="approved"))
    with pytest.raises(HTTPException) as error:
        customer_request_status(db, CUSTOMER, CODE)
    assert error.value.status_code == 409


def test_response_contract_and_route_controlled_no_store():
    assert JoinRequestStatus(request_id=None, status="none").model_dump() == {
        "request_id": None, "status": "none"}
    with pytest.raises(ValidationError):
        JoinRequestStatus(request_id=1, status="unknown")
    response = Response()
    with patch("app.routers.customer_join.service.customer_request_status", return_value={"request_id": 3, "status": "pending"}):
        assert request_status(response, CODE, CUSTOMER, object()) == {"request_id": 3, "status": "pending"}
    assert response.headers["Cache-Control"] == "no-store"
    with patch("app.routers.customer_join.service.customer_request_status", side_effect=HTTPException(404, "Join resource unavailable")):
        with pytest.raises(HTTPException) as error:
            request_status(Response(), CODE, CUSTOMER, object())
    assert error.value.headers["Cache-Control"] == "no-store"


def test_route_contract_and_existing_list_and_cancel_are_preserved():
    routes = {(route.path, tuple(route.methods)): route for route in customer_router.routes}
    assert any(path.endswith("/by-code/{public_code}") and methods == ("GET",) for path, methods in routes)
    assert any(path == "/customer/join-requests" and methods == ("GET",) for path, methods in routes)
    assert any(path.endswith("/{request_id}/cancel") and methods == ("POST",) for path, methods in routes)
    route = next(route for route in customer_router.routes if route.path.endswith("/by-code/{public_code}"))
    assert route.response_model is JoinRequestStatus
    assert route.dependant.dependencies  # Existing auth and DB dependencies remain attached.


def test_http_auth_role_validation_and_no_store_without_database():
    app = FastAPI()
    app.include_router(customer_router)
    app.dependency_overrides[get_db] = lambda: object()
    path = f"/customer/join-requests/by-code/{CODE}"
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            user_id=31, platform_role="driver", account_status="active")
        assert client.get(path).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            user_id=31, platform_role="customer", account_status="active")
        with patch("app.routers.customer_join.service.customer_request_status",
                   return_value={"request_id": None, "status": "none"}):
            result = client.get(path)
        assert result.status_code == 200
        assert result.json() == {"request_id": None, "status": "none"}
        assert result.headers["cache-control"] == "no-store"
        assert client.get("/customer/join-requests/by-code/short").status_code == 422
