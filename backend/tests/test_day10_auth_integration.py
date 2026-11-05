"""Day 10 auth integration: real JWTs and test-database rollback fixtures only."""
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import JWT_ALGORITHM, hash_password
from app.main import app
from app.models import User
from test_shop_owner_dashboard import db


@pytest.fixture
def auth_api(db):
    assert settings.MYSQL_DATABASE == "lankapex_test_db"
    connection = db.connection()
    previous = app.dependency_overrides.copy()
    def request_session():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_db] = request_session
    try:
        with TestClient(app) as client:
            yield client, db
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize("role,url_role", [("shop_owner", "shop-owner"), ("customer", "customer"), ("driver", "driver"), ("admin", None)])
def test_registration_login_identity_and_cross_role_access(auth_api, role, url_role):
    client, session = auth_api
    email = f"day10-{uuid4().hex}@example.com"
    password = secrets.token_urlsafe(24)
    if url_role:
        result = client.post(f"/api/v1/auth/register/{url_role}", json={"full_name": "Day 10 Test Account", "email": email, "password": password})
        assert result.status_code == 201
        assert result.json()["role"] == role
        assert "access_token" not in result.json()
    else:
        # Admin is provisioned only by the trusted fixture, never public registration.
        session.add(User(full_name="Day 10 Test Admin", email=email, password_hash=hash_password(password), platform_role="admin", account_status="active", preferred_language="en"))
        session.commit()
    login = client.post("/api/v1/auth/login", data={"username": email.upper(), "password": password})
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["platform_role"] == role
    assert me.json()["account_status"] == "active"
    for target in ["shop-owner", "customer", "driver", "admin"]:
        response = client.get(f"/api/v1/access/{target}", headers=headers)
        assert response.status_code == (200 if target.replace("-", "_") == role else 403)
    assert client.get("/api/v1/auth/me").status_code == 401
    # Existing stored role and status remain authoritative after token issuance.
    user = session.get(User, me.json()["user_id"])
    user.account_status = "suspended"
    session.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 403
    assert client.post("/api/v1/auth/login", data={"username": email, "password": password}).status_code == 403


@pytest.mark.parametrize("role", ["customer", "shop-owner", "driver"])
def test_registration_cannot_accept_browser_privileges(auth_api, role):
    client, _ = auth_api
    payload = {"full_name": "Day 10 Test Account", "email": f"day10-{uuid4().hex}@example.com", "password": secrets.token_urlsafe(24), "platform_role": "admin", "account_status": "active"}
    assert client.post(f"/api/v1/auth/register/{role}", json=payload).status_code == 422
    assert client.post("/api/v1/auth/register/admin", json=payload).status_code == 404


def test_invalid_credentials_and_expired_or_tampered_tokens(auth_api):
    client, _ = auth_api
    password = secrets.token_urlsafe(24)
    email = f"day10-{uuid4().hex}@example.com"
    registered = client.post("/api/v1/auth/register/customer", json={"full_name": "Day 10 Test Account", "email": email, "password": password})
    assert registered.status_code == 201
    missing = client.post("/api/v1/auth/login", data={"username": f"absent-{uuid4().hex}@example.com", "password": password})
    wrong = client.post("/api/v1/auth/login", data={"username": email, "password": password + "wrong"})
    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == wrong.json()
    assert client.post("/api/v1/auth/login", data={}).status_code == 422
    now = datetime.now(timezone.utc)
    payload = {"sub": str(registered.json()["user_id"]), "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1), "type": "access"}
    expired = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    payload["exp"] = now + timedelta(hours=1)
    tampered = jwt.encode(payload, secrets.token_urlsafe(40), algorithm=JWT_ALGORITHM)
    for token in [expired, tampered]:
        assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401


@pytest.mark.parametrize("status", ["pending", "suspended", "disabled"])
def test_inactive_driver_cannot_login_or_access_protected_api(auth_api, status):
    client, session = auth_api
    password = secrets.token_urlsafe(24)
    email = f"day10-{uuid4().hex}@example.com"
    session.add(User(full_name="Day 10 Test Driver", email=email, password_hash=hash_password(password), platform_role="driver", account_status=status, preferred_language="en"))
    session.commit()
    response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 403
