"""Real JWT, independent request sessions, and rollback-isolated MySQL integration."""
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Business, BusinessMember, CreditAccount, CustomerProfile, LedgerEntry, User
from app.routers import shop_owner
from app.services.shop_owner_dashboard_service import get_dashboard_summary
from test_shop_owner_dashboard import db, make_business, make_entry


@pytest.fixture
def integration_api(db):
    password = "Day7-test-only-password!"
    owner = User(full_name="Day 7 Integration Owner", email=f"day7-{uuid4().hex}@example.com",
                 password_hash=hash_password(password), platform_role="shop_owner",
                 preferred_language="en", account_status="active")
    db.add(owner)
    db.flush()
    business = make_business(db)
    other_business = make_business(db)
    db.add(BusinessMember(business_id=business, user_id=owner.user_id,
                          business_role="owner", membership_status="active"))
    customer = CustomerProfile(business_id=business, customer_name="Existing customer")
    other_customer = CustomerProfile(business_id=other_business, customer_name="Private customer")
    db.add_all([customer, other_customer])
    db.commit()
    connection = db.connection()

    def request_session():
        # Route commits persist across requests but remain inside the fixture's
        # outer transaction; no test rows survive fixture teardown.
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session

    previous = app.dependency_overrides.copy()
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_db] = request_session
    try:
        with TestClient(app) as client:
            client.headers["Authorization"] = f"Bearer {create_access_token(owner.user_id)}"
            yield {"client": client, "db": db, "business": business, "owner": owner,
                   "customer": customer.customer_id, "other_business": other_business,
                   "other_customer": other_customer.customer_id, "password": password}
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


OPERATIONS = ["list", "details", "add", "edit", "create_account", "update_account"]


def call(context, operation, business=None, customer=None, payload=None):
    client = context["client"]
    params = {"business_id": business or context["business"]}
    url = "/api/v1/shop-owner/customers"
    if operation == "list":
        return client.get(url, params=params)
    if operation == "add":
        return client.post(url, params=params, json=payload or {"customer_name": "New Customer"})
    url += f"/{customer or context['customer']}"
    if operation == "details":
        return client.get(url, params=params)
    if operation == "edit":
        return client.patch(url, params=params, json=payload or {"customer_name": "Updated Customer"})
    url += "/credit-account"
    return getattr(client, "post" if operation == "create_account" else "patch")(
        url, params=params, json=payload or {"credit_limit": "10000.25", "payment_term_days": 45})


def test_full_customer_lifecycle_persists_across_sessions(integration_api):
    ctx = integration_api
    client, session = ctx["client"], ctx["db"]
    owner = ctx["owner"]
    login = client.post("/api/v1/auth/login", data={"username": owner.email, "password": ctx["password"]})
    assert login.status_code == 200
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    created = call(ctx, "add", payload={"customer_name": "  Kumar   Raj ", "phone": "+94 77 123 4567"})
    assert created.status_code == 201
    customer = created.json()["customer_id"]
    persisted = session.get(CustomerProfile, customer)
    assert persisted.customer_name == "Kumar Raj"
    assert persisted.phone == "0771234567"
    assert persisted.address is None
    details = call(ctx, "details", customer=customer).json()
    assert details["credit_account"] is None
    assert details["transactions"] == []
    assert details["outstanding_balance"] == "0.00"
    updated = call(ctx, "edit", customer=customer, payload={"customer_name": "Changed Name", "address": "  Jaffna   Town "})
    assert updated.status_code == 200
    session.expire_all()
    assert session.get(CustomerProfile, customer).address == "Jaffna Town"
    listed = call(ctx, "list").json()["customers"]
    assert next(c for c in listed if c["customer_id"] == customer)["customer_name"] == "Changed Name"
    account = call(ctx, "create_account", customer=customer)
    assert account.status_code == 201
    account_id = account.json()["credit_account"]["credit_account_id"]
    assert session.get(CreditAccount, account_id).payment_term_days == 45
    assert call(ctx, "create_account", customer=customer).status_code == 409
    update = call(ctx, "update_account", customer=customer, payload={"credit_limit": "20000.50", "payment_term_days": 60, "account_status": "suspended"})
    assert update.status_code == 200
    session.expire_all()
    persisted_account = session.get(CreditAccount, account_id)
    assert persisted_account.credit_limit == Decimal("20000.50")
    assert persisted_account.payment_term_days == 60
    assert persisted_account.account_status == "suspended"
    assert call(ctx, "details", customer=customer).json()["credit_account"]["account_status"] == "suspended"
    listed = next(c for c in call(ctx, "list").json()["customers"] if c["customer_id"] == customer)
    assert listed["credit_limit"] == "20000.50"
    assert listed["account_status"] == "suspended"


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("identity", ["anonymous", "invalid_token", "customer", "driver", "admin", "inactive_owner"])
def test_real_authentication_and_role_enforcement(integration_api, operation, identity):
    ctx = integration_api
    if identity == "anonymous":
        ctx["client"].headers.pop("Authorization")
    elif identity == "invalid_token":
        ctx["client"].headers["Authorization"] = "Bearer invalid-token"
    else:
        owner = ctx["owner"]
        if identity == "inactive_owner":
            owner.account_status = "suspended"
        else:
            owner.platform_role = identity
        ctx["db"].flush()
    response = call(ctx, operation)
    assert response.status_code == (401 if identity in ("anonymous", "invalid_token") else 403)


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("condition", ["other_business", "pending", "inactive_membership"])
def test_business_isolation_and_approval(integration_api, operation, condition):
    ctx, business = integration_api, None
    if condition == "other_business":
        business = ctx["other_business"]
    elif condition == "pending":
        ctx["db"].get(Business, ctx["business"]).approval_status = "pending"
    else:
        member = ctx["db"].scalar(select(BusinessMember).where(BusinessMember.business_id == ctx["business"]))
        member.membership_status = "inactive"
    ctx["db"].flush()
    assert call(ctx, operation, business=business).status_code == 403


@pytest.mark.parametrize("operation", ["details", "edit", "create_account", "update_account"])
def test_customer_id_cannot_escape_business_scope(integration_api, operation):
    assert call(integration_api, operation, customer=integration_api["other_customer"]).status_code == 404


@pytest.mark.parametrize("reverse_type", [None, "credit_sale", "repayment"])
def test_decimal_running_list_and_dashboard_balances_agree(integration_api, reverse_type):
    ctx = integration_api
    account = call(ctx, "create_account").json()["credit_account"]["credit_account_id"]
    session, owner = ctx["db"], ctx["owner"].user_id
    sale = make_entry(session, owner, account, "credit_sale", "0.30")
    repayment = make_entry(session, owner, account, "repayment", "0.10")
    if reverse_type:
        original = sale if reverse_type == "credit_sale" else repayment
        amount = "0.30" if reverse_type == "credit_sale" else "0.10"
        make_entry(session, owner, account, "reversal", amount, reverses_entry_id=original)
        with pytest.raises(IntegrityError) as error:
            with session.begin_nested():
                make_entry(session, owner, account, "reversal", amount, reverses_entry_id=original)
        assert error.value.orig.args[0] == 1062
    session.flush()
    details = call(ctx, "details").json()
    listed = next(c for c in call(ctx, "list").json()["customers"] if c["customer_id"] == ctx["customer"])
    dashboard = get_dashboard_summary(session, ctx["business"])
    running = Decimal("0.00")
    for transaction in details["transactions"]:
        running += Decimal(transaction["debit"]) - Decimal(transaction["credit"])
        assert Decimal(transaction["running_balance"]) == running
    expected = Decimal("0.20") if reverse_type is None else Decimal("0.00") if reverse_type == "credit_sale" else Decimal("0.30")
    assert max(running, Decimal("0.00")) == expected
    assert Decimal(details["outstanding_balance"]) == expected
    assert Decimal(listed["outstanding_balance"]) == expected
    assert isinstance(dashboard["total_outstanding"], Decimal)
    assert dashboard["total_outstanding"] == expected


@pytest.mark.parametrize("operation", ["add", "edit", "create_account", "update_account"])
def test_database_errors_are_rolled_back_and_sanitized(integration_api, monkeypatch, operation):
    name = {"add": "create_business_customer", "edit": "update_customer",
            "create_account": "manage_credit_account", "update_account": "manage_credit_account"}[operation]
    def fail(*args, **kwargs):
        raise SQLAlchemyError("private SQL diagnostic with password and parameters")
    monkeypatch.setattr(shop_owner, name, fail)
    response = call(integration_api, operation)
    assert response.status_code == 500
    assert "private SQL" not in response.text
    assert "password" not in response.text
    assert response.json()["detail"] in ("Unable to create customer", "Unable to save customer changes")


def test_customer_routes_are_registered_once():
    seen = set()
    # FastAPI includes routers lazily; inspect declarations for duplicates and
    # verify every operation is exposed by the mounted application schema.
    schema = app.openapi()["paths"]
    for route in shop_owner.router.routes:
        if "/shop-owner/customers" not in getattr(route, "path", ""):
            continue
        for method in route.methods:
            key = (method, route.path)
            assert key not in seen
            seen.add(key)
            assert method.lower() in schema[f"/api/v1{route.path}"]
    assert seen == {
        ("GET", "/shop-owner/customers"),
        ("POST", "/shop-owner/customers"),
        ("GET", "/shop-owner/customers/{customer_id}"),
        ("PATCH", "/shop-owner/customers/{customer_id}"),
        ("POST", "/shop-owner/customers/{customer_id}/credit-account"),
        ("PATCH", "/shop-owner/customers/{customer_id}/credit-account"),
        ("GET", "/shop-owner/customers/{customer_id}/statement"),
    }
