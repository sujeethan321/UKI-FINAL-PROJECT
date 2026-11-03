
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import insert, text, select, update, func
from sqlalchemy.orm import Session
from datetime import datetime


from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.core.auth_dependencies import get_current_user
from app.models import BusinessMember, BusinessApprovalAudit



from app.services.shop_owner_dashboard_service import (
    get_recent_credit_transactions,
)

from app.core.config import settings
from app.core.database import engine
from app.models import (
    User,
    Business,
    CustomerProfile,
    CreditAccount,
    LedgerEntry,
)
from app.services.shop_owner_dashboard_service import (
    get_dashboard_summary,
)



@pytest.fixture
def db():
    # Never run financial tests against the main database.
    if settings.MYSQL_DATABASE != "lankapex_test_db":
        pytest.fail("Use lankapex_test_db for these tests.")

    with engine.connect() as connection:
        transaction = connection.begin()

        actual_database = connection.execute(
            text("SELECT DATABASE()")
        ).scalar_one()

        if actual_database != "lankapex_test_db":
            transaction.rollback()
            pytest.fail("Connected to the wrong database.")

        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )

        try:
            yield session
        finally:
            session.close()

            if transaction.is_active:
                transaction.rollback()


def make_business(db, approval_status="approved"):
    result = db.execute(
        insert(Business).values(
            business_name="Dashboard Test Shop",
            business_type="retail",
            address="Jaffna, Sri Lanka",
            approval_status=approval_status,
        )
    )

    return result.inserted_primary_key[0]


def make_customer_account(db, business_id):
    unique = uuid4().hex[:12]

    user_result = db.execute(
        insert(User).values(
            full_name="Dashboard Test Customer",
            email=f"dashboard-{unique}@example.com",
            password_hash="test-only-hash",
            platform_role="customer",
            preferred_language="en",
            account_status="active",
        )
    )
    user_id = user_result.inserted_primary_key[0]

    customer_result = db.execute(
        insert(CustomerProfile).values(
            business_id=business_id,
            user_id=user_id,
            customer_name="Dashboard Test Customer",
        )
    )
    customer_id = customer_result.inserted_primary_key[0]

    account_result = db.execute(
        insert(CreditAccount).values(
            creditor_business_id=business_id,
            customer_id=customer_id,
            debtor_business_id=None,
            credit_limit=Decimal("10000.00"),
            payment_term_days=30,
            account_status="active",
        )
    )
    account_id = account_result.inserted_primary_key[0]

    return user_id, account_id


def make_entry(
    db,
    user_id,
    account_id,
    entry_type,
    amount,
    reverses_entry_id=None,
):
    result = db.execute(
        insert(LedgerEntry).values(
            credit_account_id=account_id,
            created_by=user_id,
            entry_type=entry_type,
            amount=Decimal(amount),
            reverses_entry_id=reverses_entry_id,
            idempotency_key=f"dashboard-{uuid4().hex}",
        )
    )
    return result.inserted_primary_key[0]


def outstanding(db, business_id):
    result = get_dashboard_summary(db, business_id)
    return Decimal(str(result["total_outstanding"]))


def test_credit_sale(db):
    business_id = make_business(db)
    user_id, account_id = make_customer_account(
        db, business_id
    )

    make_entry(
        db, user_id, account_id,
        "credit_sale", "5000.00"
    )

    assert outstanding(
        db, business_id
    ) == Decimal("5000.00")


def test_partial_repayment(db):
    business_id = make_business(db)
    user_id, account_id = make_customer_account(
        db, business_id
    )

    make_entry(
        db, user_id, account_id,
        "credit_sale", "5000.00"
    )
    make_entry(
        db, user_id, account_id,
        "repayment", "2000.00"
    )

    assert outstanding(
        db, business_id
    ) == Decimal("3000.00")


def test_reversed_repayment(db):
    business_id = make_business(db)
    user_id, account_id = make_customer_account(
        db, business_id
    )

    make_entry(
        db, user_id, account_id,
        "credit_sale", "5000.00"
    )

    repayment_id = make_entry(
        db, user_id, account_id,
        "repayment", "2000.00"
    )

    make_entry(
        db, user_id, account_id,
        "reversal", "2000.00",
        reverses_entry_id=repayment_id,
    )

    assert outstanding(
        db, business_id
    ) == Decimal("5000.00")


def test_reversed_credit_sale(db):
    business_id = make_business(db)
    user_id, account_id = make_customer_account(
        db, business_id
    )

    sale_id = make_entry(
        db, user_id, account_id,
        "credit_sale", "5000.00"
    )

    make_entry(
        db, user_id, account_id,
        "reversal", "5000.00",
        reverses_entry_id=sale_id,
    )

    assert outstanding(
        db, business_id
    ) == Decimal("0.00")


def test_two_customers(db):
    business_id = make_business(db)

    user1, account1 = make_customer_account(
        db, business_id
    )
    user2, account2 = make_customer_account(
        db, business_id
    )

    make_entry(
        db, user1, account1,
        "credit_sale", "5000.00"
    )
    make_entry(
        db, user1, account1,
        "repayment", "1000.00"
    )
    make_entry(
        db, user2, account2,
        "credit_sale", "3000.00"
    )

    result = get_dashboard_summary(
        db, business_id
    )

    assert Decimal(
        str(result["total_outstanding"])
    ) == Decimal("7000.00")

    assert result["credit_customers"] == 2


def test_business_data_isolation(db):
    business_a = make_business(db)
    business_b = make_business(db)

    user_a, account_a = make_customer_account(
        db, business_a
    )
    user_b, account_b = make_customer_account(
        db, business_b
    )

    make_entry(
        db, user_a, account_a,
        "credit_sale", "4000.00"
    )
    make_entry(
        db, user_b, account_b,
        "credit_sale", "8000.00"
    )

    assert outstanding(
        db, business_a
    ) == Decimal("4000.00")

    assert outstanding(
        db, business_b
    ) == Decimal("8000.00")


# -------------------------------------------
# Step 5.6.3 - Recent Credit Transactions
# -------------------------------------------


def recent(db, business_id, limit=5):
    return get_recent_credit_transactions(
        db=db,
        business_id=business_id,
        limit=limit,
    )


def test_recent_shows_credit_sale_and_repayment(db):
    business_id = make_business(db)
    user_id, account_id = make_customer_account(
        db, business_id
    )

    sale_id = make_entry(
        db, user_id, account_id,
        "credit_sale", "5000.00"
    )

    repayment_id = make_entry(
        db, user_id, account_id,
        "repayment", "2000.00"
    )

    transactions = recent(db, business_id)

    assert len(transactions) == 2

    returned_ids = {
        transaction["id"]
        for transaction in transactions
    }

    assert returned_ids == {
        sale_id,
        repayment_id,
    }

    returned_types = {
        transaction["type"]
        for transaction in transactions
    }

    assert returned_types == {
        "credit_sale",
        "repayment",
    }


def test_recent_orders_newest_first(db):
    business_id = make_business(db)
    user_id, account_id = make_customer_account(
        db, business_id
    )

    old_id = make_entry(
        db, user_id, account_id,
        "credit_sale", "1000.00"
    )

    middle_id = make_entry(
        db, user_id, account_id,
        "credit_sale", "2000.00"
    )

    newest_id = make_entry(
        db, user_id, account_id,
        "repayment", "500.00"
    )

    timestamps = [
        (old_id, datetime(2026, 10, 1, 9, 0)),
        (middle_id, datetime(2026, 10, 2, 9, 0)),
        (newest_id, datetime(2026, 10, 3, 9, 0)),
    ]

    for entry_id, timestamp in timestamps:
        db.execute(
            update(LedgerEntry)
            .where(
                LedgerEntry.entry_id == entry_id
            )
            .values(recorded_at=timestamp)
        )

    transactions = recent(db, business_id)

    returned_ids = [
        transaction["id"]
        for transaction in transactions
    ]

    assert returned_ids == [
        newest_id,
        middle_id,
        old_id,
    ]


def test_recent_limits_to_five(db):
    business_id = make_business(db)
    user_id, account_id = make_customer_account(
        db, business_id
    )

    entry_ids = []

    for index in range(7):
        entry_id = make_entry(
            db, user_id, account_id,
            "credit_sale", "100.00"
        )

        db.execute(
            update(LedgerEntry)
            .where(
                LedgerEntry.entry_id == entry_id
            )
            .values(
                recorded_at=datetime(
                    2026, 10, index + 1, 10, 0
                )
            )
        )

        entry_ids.append(entry_id)

    transactions = recent(db, business_id)

    assert len(transactions) == 5

    assert [
        transaction["id"]
        for transaction in transactions
    ] == list(reversed(entry_ids[-5:]))


def test_recent_excludes_reversed_entries(db):
    business_id = make_business(db)
    user_id, account_id = make_customer_account(
        db, business_id
    )

    sale_id = make_entry(
        db, user_id, account_id,
        "credit_sale", "5000.00"
    )

    repayment_id = make_entry(
        db, user_id, account_id,
        "repayment", "1000.00"
    )

    reversal_id = make_entry(
        db, user_id, account_id,
        "reversal", "1000.00",
        reverses_entry_id=repayment_id,
    )

    transactions = recent(db, business_id)

    returned_ids = {
        transaction["id"]
        for transaction in transactions
    }

    assert sale_id in returned_ids
    assert repayment_id not in returned_ids
    assert reversal_id not in returned_ids

    assert len(transactions) == 1


def test_recent_business_isolation(db):
    business_a = make_business(db)
    business_b = make_business(db)

    user_a, account_a = make_customer_account(
        db, business_a
    )
    user_b, account_b = make_customer_account(
        db, business_b
    )

    entry_a = make_entry(
        db, user_a, account_a,
        "credit_sale", "4000.00"
    )

    entry_b = make_entry(
        db, user_b, account_b,
        "credit_sale", "8000.00"
    )

    transactions_a = recent(db, business_a)
    transactions_b = recent(db, business_b)

    assert [
        transaction["id"]
        for transaction in transactions_a
    ] == [entry_a]

    assert [
        transaction["id"]
        for transaction in transactions_b
    ] == [entry_b]


def test_recent_empty_business(db):
    business_id = make_business(db)

    transactions = recent(db, business_id)

    assert transactions == []
    
    
# -------------------------------------------
# Admin business approval audit tests
# -------------------------------------------

@pytest.fixture
def admin_api(db):
    """Use the existing rolled-back test DB session."""

    unique = uuid4().hex[:12]

    result = db.execute(
        insert(User).values(
            full_name="Test Administrator",
            email=f"admin-{unique}@example.com",
            password_hash="test-only-hash",
            platform_role="admin",
            preferred_language="en",
            account_status="active",
        )
    )

    admin_id = result.inserted_primary_key[0]
    admin = db.get(User, admin_id)

    def override_db():
        yield db

    def override_user():
        return admin

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = (
        override_user
    )

    try:
        with TestClient(app) as client:
            yield client, admin
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(
            get_current_user, None
        )


def make_owned_business(db):
    business_id = make_business(
        db,
        approval_status="pending",
    )

    unique = uuid4().hex[:12]

    result = db.execute(
        insert(User).values(
            full_name="Test Shop Owner",
            email=f"owner-{unique}@example.com",
            password_hash="test-only-hash",
            platform_role="shop_owner",
            preferred_language="en",
            account_status="active",
        )
    )

    owner_id = result.inserted_primary_key[0]

    db.execute(
        insert(BusinessMember).values(
            business_id=business_id,
            user_id=owner_id,
            business_role="owner",
            membership_status="active",
        )
    )

    return business_id


def test_admin_approves_and_records_audit(db, admin_api):
    client, admin = admin_api
    business_id = make_owned_business(db)
    db.commit()

    response = client.patch(
        f"/api/v1/admin/businesses/{business_id}/decision",
        json={
            "decision": "approve",
            "review_note": "Verified business information",
        },
    )

    assert response.status_code == 200
    assert response.json()["approval_status"] == "approved"

    business = db.get(Business, business_id)
    assert business.approval_status == "approved"

    audits = db.scalars(
        select(BusinessApprovalAudit).where(
            BusinessApprovalAudit.business_id == business_id
        )
    ).all()

    assert len(audits) == 1
    assert audits[0].admin_user_id == admin.user_id
    assert audits[0].decision == "approve"
    assert audits[0].previous_status == "pending"
    assert audits[0].new_status == "approved"
    assert audits[0].review_note == (
        "Verified business information"
    )


def test_admin_rejects_and_records_audit(db, admin_api):
    client, admin = admin_api
    business_id = make_business(
        db,
        approval_status="pending",
    )

    db.commit()

    response = client.patch(
        f"/api/v1/admin/businesses/{business_id}/decision",
        json={
            "decision": "reject",
            "review_note": "Insufficient verification",
        },
    )

    assert response.status_code == 200
    assert response.json()["approval_status"] == "rejected"

    audit = db.scalar(
        select(BusinessApprovalAudit).where(
            BusinessApprovalAudit.business_id == business_id
        )
    )

    assert audit is not None
    assert audit.admin_user_id == admin.user_id
    assert audit.decision == "reject"
    assert audit.new_status == "rejected"


def test_duplicate_decision_is_blocked(db, admin_api):
    client, admin = admin_api
    business_id = make_owned_business(db)
    
    db.commit()

    url = (
        f"/api/v1/admin/businesses/"
        f"{business_id}/decision"
    )

    first = client.patch(
        url, json={"decision": "approve"}
    )

    second = client.patch(
        url, json={"decision": "reject"}
    )

    assert first.status_code == 200
    assert second.status_code == 409

    assert db.get(
        Business, business_id
    ).approval_status == "approved"

    audit_count = db.scalar(
        select(func.count())
        .select_from(BusinessApprovalAudit)
        .where(
            BusinessApprovalAudit.business_id == business_id
        )
    )

    assert audit_count == 1


def test_approval_without_owner_is_blocked(
    db, admin_api
):
    client, admin = admin_api
    business_id = make_business(
        db,
        approval_status="pending",
    )

    db.commit()

    response = client.patch(
        f"/api/v1/admin/businesses/{business_id}/decision",
        json={"decision": "approve"},
    )

    assert response.status_code == 409

    assert db.get(
        Business, business_id
    ).approval_status == "pending"


def test_non_admin_cannot_approve(db, admin_api):
    client, admin = admin_api
    business_id = make_owned_business(db)
    
    db.commit()

    original_role = admin.platform_role
    admin.platform_role = "shop_owner"

    try:
        response = client.patch(
            f"/api/v1/admin/businesses/"
            f"{business_id}/decision",
            json={"decision": "approve"},
        )

        assert response.status_code == 403
    finally:
        admin.platform_role = original_role


def test_audit_history_is_readable_by_admin(
    db, admin_api
):
    client, admin = admin_api
    business_id = make_owned_business(db)
    
    db.commit()

    client.patch(
        f"/api/v1/admin/businesses/"
        f"{business_id}/decision",
        json={"decision": "approve"},
    )

    response = client.get(
        f"/api/v1/admin/businesses/"
        f"{business_id}/audit-history"
    )

    assert response.status_code == 200

    history = response.json()["history"]

    assert len(history) == 1
    assert history[0]["decision"] == "approve"
    assert history[0]["admin_user_id"] == admin.user_id


@pytest.fixture
def pending_shop_owner_api(db):
    business_id = make_business(
        db,
        approval_status="pending",
    )
    unique = uuid4().hex[:12]
    owner_result = db.execute(
        insert(User).values(
            full_name="Test Pending Shop Owner",
            email=f"pending-owner-{unique}@example.com",
            password_hash="test-only-hash",
            platform_role="shop_owner",
            preferred_language="en",
            account_status="active",
        )
    )
    owner = db.get(
        User,
        owner_result.inserted_primary_key[0],
    )
    db.execute(
        insert(BusinessMember).values(
            business_id=business_id,
            user_id=owner.user_id,
            business_role="owner",
            membership_status="active",
        )
    )

    def override_db():
        yield db

    def override_user():
        return owner

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    try:
        with TestClient(app) as client:
            yield client, business_id
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )


def test_pending_owner_cannot_access_financial_endpoints(
    pending_shop_owner_api,
):
    client, business_id = pending_shop_owner_api

    summary = client.get(
        "/api/v1/shop-owner/dashboard/summary",
        params={"business_id": business_id},
    )
    transactions = client.get(
        "/api/v1/shop-owner/dashboard/recent-transactions",
        params={"business_id": business_id},
    )

    assert summary.status_code == 403
    assert transactions.status_code == 403
    assert summary.json()["detail"] == (
        "Business approval is required to access financial data"
    )
    assert transactions.json()["detail"] == (
        "Business approval is required to access financial data"
    )


def test_pending_owner_can_read_business_context(
    pending_shop_owner_api,
):
    client, business_id = pending_shop_owner_api

    response = client.get(
        "/api/v1/shop-owner/business-context"
    )

    assert response.status_code == 200
    assert response.json()["businesses"][0]["business_id"] == (
        business_id
    )
    assert response.json()["businesses"][0]["approval_status"] == (
        "pending"
    )


def test_admin_business_list_paginates_and_filters(
    db,
    admin_api,
):
    client, _admin = admin_api
    pending_ids = [
        make_business(db, approval_status="pending")
        for _ in range(3)
    ]
    make_business(db, approval_status="approved")

    response = client.get(
        "/api/v1/admin/businesses",
        params={
            "status": "all",
            "limit": 2,
            "offset": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    assert payload["limit"] == 2
    assert payload["offset"] == 1
    assert len(payload["businesses"]) == 2

    pending = client.get(
        "/api/v1/admin/businesses",
        params={"status": "pending", "limit": 10},
    )

    assert pending.status_code == 200
    assert pending.json()["total"] == 3
    assert {
        item["business_id"]
        for item in pending.json()["businesses"]
    } == set(pending_ids)


def test_admin_business_list_rejects_invalid_pagination(
    admin_api,
):
    client, _admin = admin_api

    response = client.get(
        "/api/v1/admin/businesses",
        params={"limit": 0},
    )

    assert response.status_code == 422


# --------------------------------------------
# Day 6 - Shop Owner Business Onboarding
# --------------------------------------------

@pytest.fixture
def onboarding_api(db):
    unique = uuid4().hex[:12]

    result = db.execute(
        insert(User).values(
            full_name="Onboarding Test Owner",
            email=f"onboarding-{unique}@example.com",
            password_hash="test-only-hash",
            platform_role="shop_owner",
            preferred_language="en",
            account_status="active",
        )
    )

    owner_id = result.inserted_primary_key[0]
    owner = db.get(User, owner_id)
    db.commit()

    def override_db():
        yield db

    def override_user():
        return owner

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    try:
        with TestClient(app) as client:
            yield client, owner
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(
            get_current_user, None
        )


def onboarding_payload():
    return {
        "business_name": "Nallur Test Grocery",
        "business_type": "grocery",
        "registration_number": None,
        "phone": "0771234567",
        "address": "Nallur, Jaffna",
    }



def test_owner_can_register_business(db, onboarding_api):
    client, owner = onboarding_api

    response = client.post(
        "/api/v1/shop-owner/businesses",
        json=onboarding_payload(),
    )

    print("\nSTATUS:", response.status_code)
    print("RESPONSE:", response.json())

    assert response.status_code == 201

    data = response.json()
    business_id = data["business_id"]

    assert data["approval_status"] == "pending"

    business = db.get(Business, business_id)
    assert business is not None
    assert business.business_name == "Nallur Test Grocery"

    membership = db.scalar(
        select(BusinessMember).where(
            BusinessMember.business_id == business_id,
            BusinessMember.user_id == owner.user_id,
        )
    )

    assert membership is not None
    assert membership.business_role == "owner"
    assert membership.membership_status == "active"


def test_onboarded_business_appears_in_context(
    db, onboarding_api
):
    client, owner = onboarding_api

    creation = client.post(
        "/api/v1/shop-owner/businesses",
        json=onboarding_payload(),
    )

    assert creation.status_code == 201
    business_id = creation.json()["business_id"]

    response = client.get(
        "/api/v1/shop-owner/business-context"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["has_business"] is True

    assert any(
        business["business_id"] == business_id
        and business["approval_status"] == "pending"
        for business in data["businesses"]
    )


def test_pending_new_business_cannot_view_finances(
    db, onboarding_api
):
    client, owner = onboarding_api

    creation = client.post(
        "/api/v1/shop-owner/businesses",
        json=onboarding_payload(),
    )

    assert creation.status_code == 201
    business_id = creation.json()["business_id"]

    for endpoint in [
        "/dashboard/summary",
        "/dashboard/recent-transactions",
    ]:
        response = client.get(
            f"/api/v1/shop-owner{endpoint}",
            params={"business_id": business_id},
        )

        assert response.status_code == 403


def test_non_owner_cannot_register_business(
    db, onboarding_api
):
    client, owner = onboarding_api

    owner.platform_role = "customer"
    db.flush()

    response = client.post(
        "/api/v1/shop-owner/businesses",
        json=onboarding_payload(),
    )

    assert response.status_code == 403


def test_invalid_business_name_is_rejected(
    db, onboarding_api
):
    client, owner = onboarding_api

    payload = onboarding_payload()
    payload["business_name"] = ""

    response = client.post(
        "/api/v1/shop-owner/businesses",
        json=payload,
    )

    assert response.status_code == 422


def test_client_cannot_set_approval_status(
    db, onboarding_api
):
    client, owner = onboarding_api

    payload = onboarding_payload()
    payload["approval_status"] = "approved"

    response = client.post(
        "/api/v1/shop-owner/businesses",
        json=payload,
    )

    assert response.status_code == 422


# --------------------------------------------
# Day 6 Step 6.3B - Duplicate registration
# --------------------------------------------

def test_duplicate_business_submission_is_blocked(
    db, onboarding_api
):
    client, owner = onboarding_api
    payload = onboarding_payload()

    first = client.post(
        "/api/v1/shop-owner/businesses",
        json=payload,
    )

    second = client.post(
        "/api/v1/shop-owner/businesses",
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 409

    businesses = db.execute(
        select(Business)
        .join(
            BusinessMember,
            BusinessMember.business_id == Business.business_id,
        )
        .where(
            BusinessMember.user_id == owner.user_id,
            BusinessMember.business_role == "owner",
        )
    ).scalars().all()

    assert len(businesses) == 1


def test_owner_can_register_different_business(
    db, onboarding_api
):
    client, owner = onboarding_api

    first_payload = onboarding_payload()

    second_payload = onboarding_payload()
    second_payload["business_name"] = "Jaffna Hardware"
    second_payload["business_type"] = "hardware"
    second_payload["address"] = "Jaffna Town"

    first = client.post(
        "/api/v1/shop-owner/businesses",
        json=first_payload,
    )

    second = client.post(
        "/api/v1/shop-owner/businesses",
        json=second_payload,
    )

    assert first.status_code == 201
    assert second.status_code == 201

    assert (
        first.json()["business_id"]
        != second.json()["business_id"]
    )


def test_duplicate_check_ignores_case_and_outer_spaces(
    db, onboarding_api
):
    client, owner = onboarding_api

    first = client.post(
        "/api/v1/shop-owner/businesses",
        json=onboarding_payload(),
    )

    modified_payload = onboarding_payload()
    modified_payload["business_name"] = (
        "  nallur test grocery  "
    )
    modified_payload["address"] = "  nallur, jaffna  "

    second = client.post(
        "/api/v1/shop-owner/businesses",
        json=modified_payload,
    )

    assert first.status_code == 201
    assert second.status_code == 409



# -------------------------------------------------------
# Day 6 Step 6.3C - Cross-business security tests
# -------------------------------------------------------


def test_owner_cannot_access_another_owners_finances(
    db, onboarding_api
):
    """
    Owner A must not access Owner B's approved
    business financial data.
    """

    client, owner_a = onboarding_api

    # Create another business with a different owner.
    business_b_id = make_owned_business(db)

    business_b = db.get(Business, business_b_id)
    business_b.approval_status = "approved"

    db.commit()

    endpoints = [
        "/api/v1/shop-owner/dashboard/summary",
        "/api/v1/shop-owner/dashboard/recent-transactions",
    ]

    for endpoint in endpoints:
        response = client.get(
            endpoint,
            params={"business_id": business_b_id},
        )

        assert response.status_code == 403, (
            f"Expected 403 from {endpoint}, "
            f"received {response.status_code}: "
            f"{response.text}"
        )


def test_business_context_excludes_other_owners_business(
    db, onboarding_api
):
    """
    The business-context API must not expose
    businesses owned by other users.
    """

    client, owner_a = onboarding_api

    # Another Shop Owner's business.
    business_b_id = make_owned_business(db)

    db.commit()

    response = client.get(
        "/api/v1/shop-owner/business-context"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == owner_a.user_id

    business_ids = {
        business["business_id"]
        for business in data["businesses"]
    }

    assert business_b_id not in business_ids


# -------------------------------------------------------
# Day 6 Step 6.3C-2
# Platform Role Permission Tests
# -------------------------------------------------------


@pytest.mark.parametrize(
    "role",
    ["customer", "driver", "admin"],
)
def test_non_shop_owner_cannot_read_business_context(
    db,
    onboarding_api,
    role,
):
    """
    Only shop_owner accounts can access
    the Shop Owner business context.
    """

    client, user = onboarding_api

    user.platform_role = role
    db.flush()

    response = client.get(
        "/api/v1/shop-owner/business-context"
    )

    assert response.status_code == 403, (
        f"Role {role} received "
        f"{response.status_code} instead of 403: "
        f"{response.text}"
    )


@pytest.mark.parametrize(
    "role",
    ["customer", "driver", "admin"],
)
def test_non_shop_owner_cannot_register_business(
    db,
    onboarding_api,
    role,
):
    """
    Customers, Drivers and Admins must not
    create Shop Owner businesses.
    """

    client, user = onboarding_api

    user.platform_role = role
    db.flush()

    response = client.post(
        "/api/v1/shop-owner/businesses",
        json=onboarding_payload(),
    )

    assert response.status_code == 403, (
        f"Role {role} received "
        f"{response.status_code} instead of 403: "
        f"{response.text}"
    )


def test_shop_owner_cannot_access_admin_business_list(
    db,
    onboarding_api,
):
    """
    A shop_owner cannot read the Admin
    business application list.
    """

    client, user = onboarding_api

    response = client.get(
        "/api/v1/admin/businesses",
        params={"status": "pending"},
    )

    assert response.status_code == 403, (
        f"Expected 403, received "
        f"{response.status_code}: {response.text}"
    )


# ==========================================================
# Day 7 Step 7.1B - Shop Owner Customer List API Tests
# ==========================================================

from app.services.shop_owner_customer_service import (
    list_business_customers,
)


def customer_result(db, business_id):
    return list_business_customers(
        db=db,
        business_id=business_id,
    )


def find_customer_by_account(customers, account_id):
    return next(
        customer
        for customer in customers
        if customer["credit_account_id"] == account_id
    )


# TEST 1 - Empty customer list

def test_customer_list_empty_business(db):
    business_id = make_business(db)

    result = customer_result(db, business_id)

    assert result == []


# TEST 2 - Customer without credit account

def test_customer_list_without_credit_account(db):
    business_id = make_business(db)

    created = db.execute(
        insert(CustomerProfile).values(
            business_id=business_id,
            user_id=None,
            customer_name="Walk-in Test Customer",
            phone="0771234567",
            address="Nallur, Jaffna",
        )
    )

    customer_id = created.inserted_primary_key[0]

    result = customer_result(db, business_id)

    assert len(result) == 1
    assert result[0]["customer_id"] == customer_id
    assert result[0]["customer_name"] == "Walk-in Test Customer"
    assert result[0]["credit_account_id"] is None
    assert Decimal(result[0]["outstanding_balance"]) == Decimal("0.00")
    assert result[0]["account_status"] == "no_account"


# TEST 3 - Credit sale increases outstanding

def test_customer_list_credit_sale(db):
    business_id = make_business(db)

    user_id, account_id = make_customer_account(
        db, business_id
    )

    make_entry(
        db, user_id, account_id,
        "credit_sale", "5000.00"
    )

    result = customer_result(db, business_id)
    customer = find_customer_by_account(result, account_id)

    assert Decimal(
        customer["outstanding_balance"]
    ) == Decimal("5000.00")

    assert Decimal(
        customer["credit_limit"]
    ) == Decimal("10000.00")


# TEST 4 - Partial repayment decreases outstanding

def test_customer_list_partial_repayment(db):
    business_id = make_business(db)

    user_id, account_id = make_customer_account(
        db, business_id
    )

    make_entry(
        db, user_id, account_id,
        "credit_sale", "5000.00"
    )

    make_entry(
        db, user_id, account_id,
        "repayment", "2000.00"
    )

    result = customer_result(db, business_id)
    customer = find_customer_by_account(result, account_id)

    assert Decimal(
        customer["outstanding_balance"]
    ) == Decimal("3000.00")


# TEST 5 - Reversed repayment restores outstanding

def test_customer_list_reversed_repayment(db):
    business_id = make_business(db)

    user_id, account_id = make_customer_account(
        db, business_id
    )

    make_entry(
        db, user_id, account_id,
        "credit_sale", "5000.00"
    )

    repayment_id = make_entry(
        db, user_id, account_id,
        "repayment", "2000.00"
    )

    make_entry(
        db, user_id, account_id,
        "reversal", "2000.00",
        reverses_entry_id=repayment_id,
    )

    result = customer_result(db, business_id)
    customer = find_customer_by_account(result, account_id)

    assert Decimal(
        customer["outstanding_balance"]
    ) == Decimal("5000.00")


# TEST 6 - Reversed credit sale is excluded

def test_customer_list_reversed_credit_sale(db):
    business_id = make_business(db)

    user_id, account_id = make_customer_account(
        db, business_id
    )

    sale_id = make_entry(
        db, user_id, account_id,
        "credit_sale", "5000.00"
    )

    make_entry(
        db, user_id, account_id,
        "reversal", "5000.00",
        reverses_entry_id=sale_id,
    )

    result = customer_result(db, business_id)
    customer = find_customer_by_account(result, account_id)

    assert Decimal(
        customer["outstanding_balance"]
    ) == Decimal("0.00")


# TEST 7 - Two businesses cannot see each other's customers

def test_customer_list_business_isolation(db):
    business_a = make_business(db)
    business_b = make_business(db)

    user_a, account_a = make_customer_account(
        db, business_a
    )

    user_b, account_b = make_customer_account(
        db, business_b
    )

    make_entry(
        db, user_a, account_a,
        "credit_sale", "4000.00"
    )

    make_entry(
        db, user_b, account_b,
        "credit_sale", "8000.00"
    )

    customers_a = customer_result(db, business_a)
    customers_b = customer_result(db, business_b)

    assert len(customers_a) == 1
    assert len(customers_b) == 1

    assert customers_a[0]["credit_account_id"] == account_a
    assert customers_b[0]["credit_account_id"] == account_b

    assert account_b not in {
        c["credit_account_id"] for c in customers_a
    }

    assert account_a not in {
        c["credit_account_id"] for c in customers_b
    }

    assert Decimal(
        customers_a[0]["outstanding_balance"]
    ) == Decimal("4000.00")

    assert Decimal(
        customers_b[0]["outstanding_balance"]
    ) == Decimal("8000.00")


# TEST 8 - Endpoint enforces business ownership

def test_customer_list_endpoint_blocks_other_owner(db):
    business_a = make_business(db)
    business_b = make_business(db)

    unique = uuid4().hex[:12]

    created = db.execute(
        insert(User).values(
            full_name="Customer List Security Owner",
            email=f"customer-list-{unique}@example.com",
            password_hash="test-only-hash",
            platform_role="shop_owner",
            preferred_language="en",
            account_status="active",
        )
    )

    owner = db.get(User, created.inserted_primary_key[0])

    db.execute(
        insert(BusinessMember).values(
            business_id=business_a,
            user_id=owner.user_id,
            business_role="owner",
            membership_status="active",
        )
    )

    db.flush()

    def override_db():
        yield db

    def override_user():
        return owner

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    try:
        with TestClient(app) as client:
            own_response = client.get(
                "/api/v1/shop-owner/customers",
                params={"business_id": business_a},
            )

            other_response = client.get(
                "/api/v1/shop-owner/customers",
                params={"business_id": business_b},
            )

        assert own_response.status_code == 200
        assert own_response.json()["business_id"] == business_a
        assert own_response.json()["customers"] == []

        assert other_response.status_code == 403

    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


# ============================================================
# Day 7 Step 7.2B - Add Customer API Security and Validation
# ============================================================

@pytest.fixture
def customer_create_api(db, onboarding_api):
    client, owner = onboarding_api

    business_id = make_business(
        db,
        approval_status="approved",
    )

    db.execute(
        insert(BusinessMember).values(
            business_id=business_id,
            user_id=owner.user_id,
            business_role="owner",
            membership_status="active",
        )
    )
    db.flush()

    return client, owner, business_id


def create_customer_request(client, business_id, **changes):
    payload = {
        "customer_name": "Kumar Raj",
        "phone": "0771234567",
        "address": "Nallur, Jaffna",
    }
    payload.update(changes)

    return client.post(
        "/api/v1/shop-owner/customers",
        params={"business_id": business_id},
        json=payload,
    )


def test_add_customer_valid(customer_create_api):
    client, owner, business_id = customer_create_api

    response = create_customer_request(client, business_id)

    assert response.status_code == 201
    assert response.json()["customer_name"] == "Kumar Raj"
    assert response.json()["business_id"] == business_id


def test_add_customer_blank_name(customer_create_api):
    client, _, business_id = customer_create_api

    response = create_customer_request(
        client, business_id, customer_name="   "
    )

    assert response.status_code == 422


def test_add_customer_invalid_phone(customer_create_api):
    client, _, business_id = customer_create_api

    response = create_customer_request(
        client, business_id, phone="123"
    )

    assert response.status_code == 422


def test_add_customer_duplicate_phone(customer_create_api):
    client, _, business_id = customer_create_api

    first = create_customer_request(
        client, business_id
    )

    second = create_customer_request(
        client,
        business_id,
        customer_name="Another Name",
        phone="+94771234567",
    )

    assert first.status_code == 201
    assert second.status_code == 409

    records = db_count_customers(
        business_id,
        "0771234567",
        client,
    )
    assert records == 1


def db_count_customers(business_id, phone, client):
    response = client.get(
        "/api/v1/shop-owner/customers",
        params={"business_id": business_id},
    )
    assert response.status_code == 200

    return sum(
        customer["phone"] == phone
        for customer in response.json()["customers"]
    )


def test_add_customer_optional_fields(customer_create_api):
    client, _, business_id = customer_create_api

    response = create_customer_request(
        client,
        business_id,
        phone=None,
        address=None,
    )

    assert response.status_code == 201
    assert response.json()["phone"] is None
    assert response.json()["address"] is None


def test_add_customer_same_phone_different_business(
    db, customer_create_api
):
    client, owner, business_a = customer_create_api

    business_b = make_business(
        db,
        approval_status="approved",
    )

    db.execute(
        insert(BusinessMember).values(
            business_id=business_b,
            user_id=owner.user_id,
            business_role="owner",
            membership_status="active",
        )
    )
    db.flush()

    first = create_customer_request(client, business_a)
    second = create_customer_request(client, business_b)

    assert first.status_code == 201
    assert second.status_code == 201


def test_add_customer_other_business_forbidden(
    db, customer_create_api
):
    client, _, _ = customer_create_api

    other_business = make_business(
        db,
        approval_status="approved",
    )

    response = create_customer_request(
        client,
        other_business,
    )

    assert response.status_code == 403


def test_add_customer_pending_business_forbidden(
    db, customer_create_api
):
    client, owner, _ = customer_create_api

    pending_business = make_business(
        db,
        approval_status="pending",
    )

    db.execute(
        insert(BusinessMember).values(
            business_id=pending_business,
            user_id=owner.user_id,
            business_role="owner",
            membership_status="active",
        )
    )
    db.flush()

    response = create_customer_request(
        client,
        pending_business,
    )

    assert response.status_code == 403


@pytest.mark.parametrize("role", ["customer", "driver"])
def test_add_customer_wrong_role_forbidden(
    db, customer_create_api, role
):
    client, owner, business_id = customer_create_api

    original_role = owner.platform_role
    try:
        owner.platform_role = role
        db.flush()

        response = create_customer_request(
            client,
            business_id,
        )

        assert response.status_code == 403
    finally:
        owner.platform_role = original_role
        db.flush()
