"""Guarded endpoint tests; runnable only through the dedicated-schema launcher."""
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token
from app.integrations.ai.base import AIClientError, AIFailureCategory
from app.main import app
from app.models import Business, BusinessMember, CreditAccount, CustomerProfile, LedgerEntry, User
from app.routers.shop_owner_ai import get_tamil_summary_service
from app.services.tamil_credit_summary_service import TamilCreditSummaryService


def make_user(db, role, status="active"):
    row = User(
        full_name="Synthetic AI endpoint fixture", phone=None,
        email=f"ai-endpoint-{uuid4().hex}@example.invalid",
        password_hash="not-a-login-secret", platform_role=role,
        preferred_language="ta", account_status=status,
    )
    db.add(row); db.flush()
    return row


def make_business(db, owner, status="approved"):
    row = Business(
        business_name="Synthetic AI endpoint shop", business_type="retail",
        registration_number=uuid4().hex, approval_status=status,
    )
    db.add(row); db.flush()
    membership = BusinessMember(
        business_id=row.business_id, user_id=owner.user_id,
        business_role="owner", membership_status="active",
    )
    db.add(membership); db.flush()
    return row


def make_account(db, customer, shop, *, linked=True, status="active", creditor=None):
    profile = CustomerProfile(
        business_id=shop.business_id,
        user_id=customer.user_id if linked else None,
        customer_name="Synthetic Customer", phone=None, address=None,
    )
    db.add(profile); db.flush()
    account = CreditAccount(
        creditor_business_id=(creditor or shop).business_id,
        customer_id=profile.customer_id, credit_limit=Decimal("1000.00"),
        payment_term_days=30, account_status=status,
    )
    db.add(account); db.flush()
    return profile, account


def make_entry(db, owner, account, kind, amount, reverses=None):
    row = LedgerEntry(
        credit_account_id=account.credit_account_id, created_by=owner.user_id,
        entry_type=kind, amount=Decimal(amount), reverses_entry_id=reverses,
        idempotency_key=uuid4().hex,
        recorded_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(row); db.flush()
    return row


def fixture_fingerprint(db):
    """Detect any endpoint mutation without exposing fixture values."""
    rows = []
    for model, columns in (
        (User, (User.user_id, User.platform_role, User.account_status)),
        (Business, (Business.business_id, Business.approval_status)),
        (BusinessMember, (BusinessMember.membership_id, BusinessMember.business_id,
                          BusinessMember.user_id, BusinessMember.membership_status)),
        (CustomerProfile, (CustomerProfile.customer_id, CustomerProfile.business_id,
                           CustomerProfile.user_id)),
        (CreditAccount, (CreditAccount.credit_account_id, CreditAccount.creditor_business_id,
                         CreditAccount.customer_id, CreditAccount.account_status,
                         CreditAccount.credit_limit)),
        (LedgerEntry, (LedgerEntry.entry_id, LedgerEntry.credit_account_id,
                       LedgerEntry.entry_type, LedgerEntry.amount,
                       LedgerEntry.reverses_entry_id)),
    ):
        rows.append((model.__tablename__, list(db.execute(
            select(*columns).order_by(columns[0])).all())))
    return sha256(repr(rows).encode("utf-8")).hexdigest()


def path(shop, profile, account):
    return (f"/api/v1/shop-owner/businesses/{shop.business_id}/customers/"
            f"{profile.customer_id}/credit-accounts/{account.credit_account_id}/"
            "tamil-credit-summary")


def token(user):
    return {"Authorization": "Bearer " + create_access_token(user.user_id)}


def api(db, summary_override=None):
    connection = db.connection()

    def request_session():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session

    previous = app.dependency_overrides.copy()
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_db] = request_session
    if summary_override is not None:
        app.dependency_overrides[get_tamil_summary_service] = lambda: summary_override
    app.state.rate_limiter.clear()
    return previous


def restore_overrides(previous):
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    if app.state.rate_limiter is not None:
        app.state.rate_limiter.clear()


def test_authorized_totals_reversals_disabled_ai_and_no_writes(db):
    owner, customer = make_user(db, "shop_owner"), make_user(db, "customer")
    shop = make_business(db, owner)
    profile, account = make_account(db, customer, shop)
    sale = make_entry(db, owner, account, "credit_sale", "100.20")
    make_entry(db, owner, account, "repayment", "30.10")
    baseline = fixture_fingerprint(db)
    previous = api(db)
    try:
        with TestClient(app) as client:
            first = client.post(path(shop, profile, account), headers=token(owner))
            assert first.status_code == 200
            assert first.json()["source"] == "fallback"
            assert first.json()["failure_category"] == "configuration"
            assert first.json()["total_credit_purchases"] == "100.20"
            assert first.json()["total_repayments"] == "30.10"
            assert first.json()["outstanding_balance"] == "70.10"
            assert first.headers["cache-control"] == "no-store"
            assert "email" not in first.text.lower() and customer.email not in first.text

            make_entry(db, owner, account, "reversal", "1.00", sale.entry_id)
            after_reversal = fixture_fingerprint(db)
            second = client.post(path(shop, profile, account), headers=token(owner))
            assert second.status_code == 200
            assert second.json()["total_credit_purchases"] == "0.00"
            assert second.json()["total_repayments"] == "30.10"
            assert second.json()["outstanding_balance"] == "0.00"
            assert fixture_fingerprint(db) == after_reversal
    finally:
        restore_overrides(previous)
    # The only change since the first fingerprint is the test-created reversal.
    assert baseline != fixture_fingerprint(db)
    assert not db.new and not db.dirty and not db.deleted


def test_auth_roles_and_exact_relationship_scope(db):
    owner, other_owner = make_user(db, "shop_owner"), make_user(db, "shop_owner")
    customer = make_user(db, "customer")
    shop, foreign_shop = make_business(db, owner), make_business(db, other_owner)
    profile, account = make_account(db, customer, shop)
    foreign_profile, foreign_account = make_account(db, customer, foreign_shop)
    baseline = fixture_fingerprint(db)
    previous = api(db)
    try:
        with TestClient(app) as client:
            endpoint = path(shop, profile, account)
            assert client.post(endpoint).status_code == 401
            assert client.post(endpoint, headers={"Authorization": "Bearer invalid"}).status_code == 401
            assert client.post(endpoint, headers=token(customer)).status_code == 403
            assert client.post(endpoint, headers=token(other_owner)).status_code == 404
            assert client.post(path(shop, foreign_profile, foreign_account),
                               headers=token(owner)).status_code == 404
            wrong_profile = path(shop, foreign_profile, account)
            assert client.post(wrong_profile, headers=token(owner)).status_code == 404
    finally:
        restore_overrides(previous)
    assert fixture_fingerprint(db) == baseline


def test_inactive_unlinked_and_malformed_accounts_are_hidden(db):
    owner = make_user(db, "shop_owner")
    active, inactive = make_user(db, "customer"), make_user(db, "customer", "suspended")
    shop, other_shop = make_business(db, owner), make_business(db, owner)
    inactive_profile, inactive_account = make_account(db, inactive, shop)
    unlinked_profile, unlinked_account = make_account(db, active, other_shop, linked=False)
    malformed_shop = make_business(db, owner)
    malformed_profile, malformed_account = make_account(
        db, active, malformed_shop, creditor=shop)
    baseline = fixture_fingerprint(db)
    previous = api(db)
    try:
        with TestClient(app) as client:
            for endpoint in (
                path(shop, inactive_profile, inactive_account),
                path(other_shop, unlinked_profile, unlinked_account),
                path(malformed_shop, malformed_profile, malformed_account),
            ):
                response = client.post(endpoint, headers=token(owner))
                assert response.status_code == 404
                assert response.json() == {"detail": "Credit account not found"}
    finally:
        restore_overrides(previous)
    assert fixture_fingerprint(db) == baseline


def test_mocked_provider_failure_returns_sanitized_fallback(db):
    class ProviderFailure:
        async def generate(self, request):
            raise AIClientError(AIFailureCategory.PROVIDER_ERROR)

    owner, customer = make_user(db, "shop_owner"), make_user(db, "customer")
    shop = make_business(db, owner)
    profile, account = make_account(db, customer, shop)
    make_entry(db, owner, account, "credit_sale", "25.00")
    baseline = fixture_fingerprint(db)
    previous = api(db, TamilCreditSummaryService(ProviderFailure()))
    try:
        with TestClient(app) as client:
            response = client.post(path(shop, profile, account), headers=token(owner))
            body = response.json()
            assert response.status_code == 200
            assert body["source"] == "fallback"
            assert body["failure_category"] == "provider_error"
            assert not any(term in response.text.lower() for term in (
                "authorization", "bearer", "api key", "stack trace", "groq"))
    finally:
        restore_overrides(previous)
    assert fixture_fingerprint(db) == baseline
