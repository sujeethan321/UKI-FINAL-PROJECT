"""Day 7 Step 7.4 API coverage using rollback-isolated MySQL fixtures."""
from decimal import Decimal

import pytest
from sqlalchemy import insert, select

from app.core.auth_dependencies import get_current_user
from app.main import app
from app.models import Business, BusinessMember, CreditAccount, CustomerProfile, LedgerEntry
from test_shop_owner_dashboard import (
    db, onboarding_api, customer_create_api, create_customer_request,
    make_business, make_customer_account, make_entry,
)


@pytest.fixture
def api(customer_create_api):
    client, owner, business_id = customer_create_api
    response = create_customer_request(client, business_id)
    assert response.status_code == 201
    return client, owner, business_id, response.json()["customer_id"]


def request(api, payload, operation="edit", customer_id=None, business_id=None):
    client, _, business, customer = api
    url = f"/api/v1/shop-owner/customers/{customer_id or customer}"
    if operation != "edit":
        url += "/credit-account"
    return getattr(client, "post" if operation == "create" else "patch")(
        url, params={"business_id": business_id or business}, json=payload)


def test_edit_normalizes_and_preserves_omitted_fields(api):
    response = request(api, {"customer_name": "  New   Name ", "phone": "+94 (77) 765-4321"})
    assert response.status_code == 200
    customer = response.json()["customer"]
    assert customer["customer_name"] == "New Name"
    assert customer["phone"] == "0777654321"
    assert customer["address"] == "Nallur, Jaffna"
    response = request(api, {"phone": None, "address": "   "})
    assert response.json()["customer"]["phone"] is None
    assert response.json()["customer"]["address"] is None


@pytest.mark.parametrize("payload", [{}, {"customer_name": None}, {"customer_name": " "},
    {"customer_name": "a"}, {"customer_name": "x" * 151}, {"phone": "123"},
    {"address": "x" * 501}, {"business_id": 5}])
def test_edit_validation(api, payload):
    assert request(api, payload).status_code == 422


def test_duplicate_phone_and_unchanged_phone(api):
    client, _, business, _ = api
    assert request(api, {"phone": "+94771234567"}).status_code == 200
    second = create_customer_request(client, business, phone="0779999999").json()["customer_id"]
    assert request(api, {"phone": "+94771234567"}, customer_id=second).status_code == 409
    response = client.get(f"/api/v1/shop-owner/customers/{second}", params={"business_id": business})
    assert response.json()["customer"]["phone"] == "0779999999"


def test_same_phone_in_other_business_allowed(db, api):
    _, owner, _, _ = api
    business = make_business(db)
    db.add(BusinessMember(business_id=business, user_id=owner.user_id,
                          business_role="owner", membership_status="active"))
    customer = CustomerProfile(business_id=business, customer_name="Other customer")
    db.add(customer)
    db.flush()
    assert request(api, {"phone": "0771234567"}, customer_id=customer.customer_id,
                   business_id=business).status_code == 200


@pytest.mark.parametrize("operation", ["edit", "create", "update"])
def test_missing_customer(api, operation):
    payload = {"customer_name": "New Name"} if operation == "edit" else {"credit_limit": "100"}
    assert request(api, payload, operation, customer_id=9223372036854775807).status_code == 404


@pytest.mark.parametrize("operation", ["edit", "create", "update"])
@pytest.mark.parametrize("condition", ["unowned", "pending", "inactive", "customer", "driver", "admin", "anonymous"])
def test_authorization(db, api, operation, condition):
    _, owner, business, _ = api
    if condition == "unowned":
        business = make_business(db)
    elif condition == "pending":
        db.get(Business, business).approval_status = "pending"
    elif condition == "inactive":
        member = db.scalar(select(BusinessMember).where(BusinessMember.business_id == business,
                                                       BusinessMember.user_id == owner.user_id))
        member.membership_status = "inactive"
    elif condition == "anonymous":
        app.dependency_overrides.pop(get_current_user)
    else:
        owner.platform_role = condition
    db.flush()
    payload = {"customer_name": "New Name"} if operation == "edit" else {"credit_limit": "100"}
    assert request(api, payload, operation, business_id=business).status_code == (401 if condition == "anonymous" else 403)


def test_create_duplicate_update_and_statuses(db, api):
    response = request(api, {"credit_limit": "1500.25", "payment_term_days": 45}, "create")
    assert response.status_code == 201
    account_id = response.json()["credit_account"]["credit_account_id"]
    assert response.json()["credit_account"]["payment_term_days"] == 45
    assert request(api, {}, "create").status_code == 409
    for status in ("suspended", "active", "closed", "active"):
        response = request(api, {"account_status": status}, "update")
        assert response.status_code == 200
        assert response.json()["credit_account"]["account_status"] == status
        assert response.json()["credit_account"]["credit_account_id"] == account_id
        assert response.json()["credit_account"]["credit_limit"] == "1500.25"
    assert len(db.scalars(select(CreditAccount).where(CreditAccount.customer_id == api[3])).all()) == 1


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("payload", [{"credit_limit": "-1"}, {"credit_limit": "1.001"},
    {"credit_limit": "1000000000000"}, {"credit_limit": "NaN"}, {"credit_limit": "Infinity"},
    {"credit_limit": None}, {"payment_term_days": 0}, {"payment_term_days": -1},
    {"payment_term_days": 1.5}, {"payment_term_days": True}, {"payment_term_days": None},
    {"account_status": "unknown"}, {"account_status": None}, {"customer_id": 99}])
def test_credit_validation(api, operation, payload):
    assert request(api, payload, operation).status_code == 422


def test_missing_account_and_empty_patch(api):
    assert request(api, {"credit_limit": "100"}, "update").status_code == 404
    assert request(api, {}, "update").status_code == 422


@pytest.mark.parametrize("reverse", [None, "sale", "repayment"])
def test_debt_limits_and_history(db, api, reverse):
    _, _, business, _ = api
    user, account_id = make_customer_account(db, business)
    customer = db.get(CreditAccount, account_id).customer_id
    sale = make_entry(db, user, account_id, "credit_sale", "5000")
    repayment = make_entry(db, user, account_id, "repayment", "2000")
    if reverse:
        make_entry(db, user, account_id, "reversal", "5000" if reverse == "sale" else "2000",
                   reverses_entry_id=sale if reverse == "sale" else repayment)
    db.commit()  # Release the fixture savepoint; the outer test transaction still rolls back.
    before = [(e.entry_id, e.entry_type, e.amount, e.reverses_entry_id) for e in db.scalars(
        select(LedgerEntry).where(LedgerEntry.credit_account_id == account_id)).all()]
    outstanding = "0" if reverse == "sale" else "5000" if reverse == "repayment" else "3000"
    if Decimal(outstanding):
        assert request(api, {"credit_limit": "2999.99", "payment_term_days": 60}, "update", customer).status_code == 409
        assert db.get(CreditAccount, account_id).payment_term_days == 30
    assert request(api, {"credit_limit": outstanding, "payment_term_days": 60}, "update", customer).status_code == 200
    assert request(api, {"account_status": "closed"}, "update", customer).status_code == 409
    assert request(api, {"account_status": "suspended"}, "update", customer).status_code == 200
    after = [(e.entry_id, e.entry_type, e.amount, e.reverses_entry_id) for e in db.scalars(
        select(LedgerEntry).where(LedgerEntry.credit_account_id == account_id)).all()]
    assert after == before
    if reverse != "sale":
        make_entry(db, user, account_id, "repayment", outstanding)
        db.flush()
        assert request(api, {"account_status": "closed"}, "update", customer).status_code == 200


@pytest.mark.parametrize("operation", ["edit", "create", "update"])
def test_other_business_customer_hidden(db, api, operation):
    other = make_business(db)
    _, account = make_customer_account(db, other)
    customer = db.get(CreditAccount, account).customer_id
    payload = {"customer_name": "New Name"} if operation == "edit" else {"credit_limit": "100"}
    assert request(api, payload, operation, customer_id=customer).status_code == 404
