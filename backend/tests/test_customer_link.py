"""Six-digit consent link; synthetic rows roll back in lankapex_test_db."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models import BusinessMember, CreditAccount, CustomerLinkInvitation, CustomerProfile, LedgerEntry, User
from test_shop_owner_dashboard import db, make_business, make_entry


def test_owner_invitation_customer_consent_preserves_ledger_and_blocks_replay(db):
    def user(role):
        row = User(full_name="Synthetic account", email=f"link-{uuid4().hex}@example.com",
                   password_hash="test-only", platform_role=role, account_status="active", preferred_language="en")
        db.add(row); db.flush(); return row

    owner, customer, other, foreign_owner = (user(role) for role in ("shop_owner", "customer", "customer", "shop_owner"))
    business_id = make_business(db)
    db.add(BusinessMember(business_id=business_id, user_id=owner.user_id,
                          business_role="owner", membership_status="active"))
    db.flush()
    profile = CustomerProfile(business_id=business_id, user_id=None, customer_name="Synthetic account")
    db.add(profile); db.flush()
    account = CreditAccount(creditor_business_id=business_id, customer_id=profile.customer_id,
                            credit_limit=Decimal("1000.00"), payment_term_days=30, account_status="active")
    db.add(account); db.flush()
    make_entry(db, owner.user_id, account.credit_account_id, "credit_sale", "100.25")
    make_entry(db, owner.user_id, account.credit_account_id, "repayment", "25.10")
    before = db.scalar(select(func.count()).select_from(LedgerEntry).where(LedgerEntry.credit_account_id == account.credit_account_id))

    connection = db.connection()
    def session_override():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
    previous = app.dependency_overrides.copy()
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_db] = session_override
    headers = lambda row: {"Authorization": "Bearer " + create_access_token(row.user_id)}
    issue_path = f"/api/v1/shop-owner/customers/{profile.customer_id}/link-invitations"
    accept_path = "/api/v1/customer/link-invitations/accept"
    with TestClient(app) as client:
        try:
            assert client.get("/api/v1/customer/credit-accounts", headers=headers(customer)).json()["total"] == 0
            assert client.get("/api/v1/customer/transactions", headers=headers(customer)).json()["total"] == 0
            assert client.post(issue_path, params={"business_id": business_id},
                               json={"recipient_email": customer.email}, headers=headers(foreign_owner)).status_code == 404
            assert client.post(issue_path, params={"business_id": business_id},
                               json={"recipient_email": customer.email}).status_code == 401
            issued = client.post(issue_path, params={"business_id": business_id},
                                 json={"recipient_email": customer.email}, headers=headers(owner))
            assert issued.status_code == 200
            token = issued.json()["invitation"]
            assert len(token) == 6 and token.isascii() and token.isdecimal()
            assert profile.user_id is None
            assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401
            assert client.post(issue_path, params={"business_id": business_id},
                               json={"recipient_email": customer.email, "user_id": other.user_id},
                               headers=headers(owner)).status_code == 422
            assert client.post(accept_path, json={"invitation": token}, headers=headers(other)).status_code == 404
            db.expire_all()
            assert db.get(CustomerProfile, profile.customer_id).user_id is None
            assert client.post(accept_path, json={"invitation": token}, headers=headers(owner)).status_code == 403
            assert client.post(accept_path, json={"invitation": token}).status_code == 401
            assert client.post(accept_path, json={"invitation": "12345"}, headers=headers(customer)).status_code == 422
            assert client.post(accept_path, json={"invitation": "abcdef"}, headers=headers(customer)).status_code == 422
            assert client.post(accept_path, json={"invitation": "999999" if token != "999999" else "888888"}, headers=headers(customer)).status_code == 404
            db.execute(update(CustomerLinkInvitation).where(
                CustomerLinkInvitation.customer_id == profile.customer_id).values(expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)))
            assert client.post(accept_path, json={"invitation": token}, headers=headers(customer)).status_code == 404
            renewed = client.post(issue_path, params={"business_id": business_id},
                                  json={"recipient_email": customer.email}, headers=headers(owner))
            assert renewed.status_code == 200
            token = renewed.json()["invitation"]
            accepted = client.post(accept_path, json={"invitation": token}, headers=headers(customer))
            assert accepted.status_code == 200 and accepted.json()["linked"] is True
            assert client.post(accept_path, json={"invitation": token}, headers=headers(customer)).status_code == 404
            db.expire_all()
            assert db.get(CustomerProfile, profile.customer_id).user_id == customer.user_id
            accounts = client.get("/api/v1/customer/credit-accounts", headers=headers(customer)).json()
            assert accounts["total"] == 1 and accounts["credit_accounts"][0]["outstanding_balance"] == "75.15"
            history = client.get("/api/v1/customer/transactions", headers=headers(customer)).json()
            assert history["total"] == 2 and {row["entry_type"] for row in history["transactions"]} == {"credit_sale", "repayment"}
            statement = client.get(f"/api/v1/customer/credit-accounts/{account.credit_account_id}/statement",
                                   params={"start_date": "2020-01-01", "end_date": "2099-12-31"}, headers=headers(customer))
            assert statement.status_code == 200
            assert client.get("/api/v1/customer/credit-accounts", headers=headers(other)).json()["total"] == 0
            assert client.get("/api/v1/customer/transactions", headers=headers(other)).json()["total"] == 0
            assert client.get(f"/api/v1/customer/credit-accounts/{account.credit_account_id}", headers=headers(other)).status_code == 404
            assert db.scalar(select(func.count()).select_from(LedgerEntry).where(LedgerEntry.credit_account_id == account.credit_account_id)) == before
            # A short code must not allow unbounded online guesses, even after use.
            app.state.rate_limiter.clear()
            assert [client.post(accept_path, json={"invitation": token}, headers=headers(customer)).status_code
                    for _ in range(5)] == [404] * 5
            blocked = client.post(accept_path, json={"invitation": token}, headers=headers(customer))
            assert blocked.status_code == 429 and "Retry-After" in blocked.headers
        finally:
            app.dependency_overrides.clear(); app.dependency_overrides.update(previous)
