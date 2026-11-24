"""Run only after the reviewed QR migration reaches isolated lankapex_test_db."""
from uuid import uuid4
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models import Business, BusinessJoinLink, BusinessMember, CreditAccount, CustomerJoinRequest, CustomerProfile, LedgerEntry, User
from test_shop_owner_dashboard import db, make_business, make_entry


def test_qr_join_requires_customer_consent_and_owner_approval_without_financial_writes(db):
    assert db.scalar(text("SELECT DATABASE()")) == "lankapex_test_db"
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == "7b9e4d2c8a15"

    def user(role, status="active"):
        row = User(full_name="Synthetic person", email=f"qr-{uuid4().hex}@example.com",
                   password_hash="test-only", platform_role=role,
                   account_status=status, preferred_language="en")
        db.add(row)
        db.flush()
        return row

    owner, foreign_owner, customer, other, driver, inactive = (
        user("shop_owner"), user("shop_owner"), user("customer"),
        user("customer"), user("driver"), user("customer", "suspended"))
    business_id = make_business(db)
    pending_id = make_business(db, "pending")
    rejected_id = make_business(db, "rejected")
    db.add_all([
        BusinessMember(business_id=business_id, user_id=owner.user_id,
                       business_role="owner", membership_status="active"),
        BusinessMember(business_id=pending_id, user_id=owner.user_id,
                       business_role="owner", membership_status="active"),
        BusinessMember(business_id=rejected_id, user_id=owner.user_id,
                       business_role="owner", membership_status="active"),
    ])
    manual = CustomerProfile(business_id=business_id, user_id=None,
                             customer_name="Unlinked manual account")
    db.add(manual)
    db.flush()
    manual_account = CreditAccount(creditor_business_id=business_id, customer_id=manual.customer_id,
                                   credit_limit=Decimal("500.00"), payment_term_days=30,
                                   account_status="active")
    db.add(manual_account)
    db.flush()
    make_entry(db, owner.user_id, manual_account.credit_account_id, "credit_sale", "100.25")
    make_entry(db, owner.user_id, manual_account.credit_account_id, "repayment", "25.10")
    manual_ledger_before = db.execute(select(LedgerEntry.entry_type, LedgerEntry.amount).where(
        LedgerEntry.credit_account_id == manual_account.credit_account_id)
        .order_by(LedgerEntry.entry_id)).all()
    baseline = {"profiles": db.scalar(select(func.count()).select_from(CustomerProfile).where(
        CustomerProfile.business_id == business_id)),
                "accounts": db.scalar(select(func.count()).select_from(CreditAccount).where(
                    CreditAccount.creditor_business_id == business_id)),
                "ledger": db.scalar(select(func.count()).select_from(LedgerEntry))}

    connection = db.connection()
    def session_override():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
    previous = app.dependency_overrides.copy()
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_db] = session_override
    headers = lambda row: {"Authorization": "Bearer " + create_access_token(row.user_id)}
    with TestClient(app) as client:
        try:
            base = f"/api/v1/shop-owner/businesses/{business_id}"
            assert client.post(base + "/join-link", headers=headers(foreign_owner)).status_code == 404
            assert client.post(f"/api/v1/shop-owner/businesses/{pending_id}/join-link", headers=headers(owner)).status_code == 404
            assert client.post(f"/api/v1/shop-owner/businesses/{rejected_id}/join-link", headers=headers(owner)).status_code == 404
            issued = client.post(base + "/join-link", headers=headers(owner))
            assert issued.status_code == 200
            code = issued.json()["public_code"]
            assert len(code) == 32 and code != str(business_id)
            assert client.post(base + "/join-link", headers=headers(owner)).json()["public_code"] == code
            assert db.scalar(select(func.count()).select_from(BusinessJoinLink).where(
                BusinessJoinLink.business_id == business_id)) == 1
            public = f"/api/v1/business-join/{code}"
            assert client.get(public).status_code == 200
            assert "business_id" not in client.get(public).json()
            join = "/api/v1/customer/join-requests"
            assert client.post(join, json={"public_code": code}).status_code == 401
            assert client.post(join, json={"public_code": code}, headers=headers(driver)).status_code == 403
            assert client.post(join, json={"public_code": code}, headers=headers(inactive)).status_code == 403
            assert client.post(join, json={"public_code": code, "user_id": other.user_id},
                               headers=headers(customer)).status_code == 422
            requested = client.post(join, json={"public_code": code}, headers=headers(customer))
            assert requested.status_code == 200 and requested.json()["status"] == "pending"
            request_id = requested.json()["request_id"]
            assert client.post(join, json={"public_code": code}, headers=headers(customer)).json()["request_id"] == request_id
            decision = base + f"/join-requests/{request_id}/decision"
            assert client.post(decision, json={"decision": "approve"}, headers=headers(foreign_owner)).status_code == 404
            assert client.get(base + "/join-requests", headers=headers(owner)).json()["total"] == 1
            approved = client.post(decision, json={"decision": "approve"}, headers=headers(owner))
            assert approved.status_code == 200 and approved.json()["status"] == "approved"
            assert client.post(decision, json={"decision": "approve"}, headers=headers(owner)).status_code == 200
            assert client.post(decision, json={"decision": "reject"}, headers=headers(owner)).status_code == 409
            assert client.post(join, json={"public_code": code}, headers=headers(customer)).status_code == 409
            rejected_code = "R" * 32
            db.add(BusinessJoinLink(business_id=rejected_id, public_code=rejected_code))
            db.flush()
            assert client.get(f"/api/v1/business-join/{rejected_code}").status_code == 404
            assert client.post(join, json={"public_code": rejected_code}, headers=headers(other)).status_code == 404
            db.expire_all()
            assert db.get(CustomerProfile, manual.customer_id).user_id is None
            assert db.scalar(select(func.count()).select_from(CustomerProfile).where(
                CustomerProfile.business_id == business_id, CustomerProfile.user_id == customer.user_id)) == 1
            assert db.scalar(select(func.count()).select_from(CustomerProfile).where(
                CustomerProfile.business_id == business_id)) == baseline["profiles"] + 1
            assert db.scalar(select(func.count()).select_from(CreditAccount).where(
                CreditAccount.creditor_business_id == business_id)) == baseline["accounts"]
            assert db.scalar(select(func.count()).select_from(LedgerEntry)) == baseline["ledger"]
            assert db.execute(select(LedgerEntry.entry_type, LedgerEntry.amount).where(
                LedgerEntry.credit_account_id == manual_account.credit_account_id)
                .order_by(LedgerEntry.entry_id)).all() == manual_ledger_before
            shops = client.get("/api/v1/customer/shops", headers=headers(customer)).json()
            assert any(shop["business_id"] == business_id and shop["credit_account_count"] == 0
                       for shop in shops["shops"])
            assert client.get("/api/v1/customer/credit-accounts", headers=headers(customer)).json()["total"] == 0
            other_request = client.post(join, json={"public_code": code}, headers=headers(other))
            reject_path = base + f"/join-requests/{other_request.json()['request_id']}/decision"
            assert client.post(reject_path, json={"decision": "reject"}, headers=headers(owner)).json()["status"] == "rejected"
            assert db.scalar(select(func.count()).select_from(CustomerProfile).where(
                CustomerProfile.business_id == business_id, CustomerProfile.user_id == other.user_id)) == 0
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous)
