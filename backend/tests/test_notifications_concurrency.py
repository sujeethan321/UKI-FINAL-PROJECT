"""Independent MySQL sessions exercise event deduplication and idempotent reads."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from app.core.database import engine
from app.core.security import create_access_token
from app.main import app
from app.models import BusinessMember, CustomerProfile, LedgerEntry, Notification, PaymentReminder, User
from app.services.notification_service import notify_event
from test_credit_sales_concurrency import committed_sales, race_requests


@pytest.fixture
def notification_race(committed_sales):
    ctx = committed_sales
    users = []
    try:
        with Session(engine) as session:
            assert session.scalar(text("SELECT DATABASE()")) == "lankapex_test_db"
            for role in ("customer", "shop_owner"):
                user = User(full_name="Notification race fixture", email=f"notification-race-{uuid4().hex}@example.com", password_hash="test-only-no-login", platform_role=role, account_status="active")
                session.add(user)
                session.flush()
                users.append(user.user_id)
            session.get(CustomerProfile, ctx["customers"][0]).user_id = users[0]
            session.add(BusinessMember(business_id=ctx["business"], user_id=users[1], business_role="owner", membership_status="active"))
            session.commit()
        ctx["recipient"] = users[0]
        ctx["coowner"] = users[1]
        yield ctx
    finally:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT DATABASE()")) == "lankapex_test_db"
            # Only the committed fixture's business/users are touched.
            connection.execute(delete(Notification).where(Notification.business_id == ctx["business"]))
            connection.execute(delete(PaymentReminder).where(PaymentReminder.business_id == ctx["business"]))
            connection.execute(update(CustomerProfile).where(CustomerProfile.customer_id.in_(ctx["customers"])).values(user_id=None))
            if users:
                connection.execute(delete(BusinessMember).where(BusinessMember.user_id.in_(users)))
                connection.execute(delete(User).where(User.user_id.in_(users)))


@pytest.mark.parametrize("kind", ["credit-sales", "repayments", "payment-reminders"])
def test_identical_financial_event_race_creates_one_notification(notification_race, kind):
    ctx = notification_race
    if kind != "credit-sales":
        with Session(engine) as session:
            actor = session.scalar(select(BusinessMember.user_id).where(BusinessMember.business_id == ctx["business"], BusinessMember.user_id != ctx["coowner"]))
            session.add(LedgerEntry(credit_account_id=ctx["accounts"][0], created_by=actor, entry_type="credit_sale", amount="100.00", idempotency_key=uuid4().hex))
            session.commit()
    payload = {"customer_id": ctx["customers"][0], "idempotency_key": uuid4().hex}
    if kind != "payment-reminders":
        payload["amount"] = "25.00"
    if kind == "repayments":
        payload["payment_method"] = "cash"
    url = "/api/v1/shop-owner/" + kind
    results = race_requests(ctx, [payload, payload], paths=[url, url])
    assert sorted(row.status_code for row in results) == [200, 201]
    with Session(engine) as session:
        rows = list(session.scalars(select(Notification).where(Notification.business_id == ctx["business"])))
        assert len(rows) == 1
        assert rows[0].recipient_user_id == (ctx["coowner"] if kind == "payment-reminders" else ctx["recipient"])
        assert session.scalar(select(func.count()).select_from(LedgerEntry).where(LedgerEntry.credit_account_id.in_(ctx["accounts"]))) == (2 if kind == "repayments" else 1)


def test_concurrent_internal_creation_is_deduplicated_by_database(notification_race):
    ctx = notification_race
    with Session(engine) as session:
        actor = session.scalar(select(BusinessMember.user_id).where(BusinessMember.business_id == ctx["business"], BusinessMember.user_id != ctx["coowner"]))
        event = LedgerEntry(credit_account_id=ctx["accounts"][0], created_by=actor, entry_type="credit_sale", amount="10.00", idempotency_key=uuid4().hex)
        session.add(event)
        session.commit()
        event_id = event.entry_id
    barrier = Barrier(2)
    def create():
        with Session(engine) as session:
            barrier.wait(timeout=10)
            ids = notify_event(session, "credit_sale_recorded", event_id)
            session.commit()
            return ids
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(create) for _ in range(2)]
        results = [job.result(timeout=30) for job in jobs]
    assert results[0] == results[1] and len(results[0]) == 1
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Notification).where(Notification.business_id == ctx["business"])) == 1


def test_concurrent_mark_read_preserves_first_transition(notification_race):
    ctx = notification_race
    result = ctx["client"].post("/api/v1/shop-owner/credit-sales", params={"business_id": ctx["business"]}, headers=ctx["headers"], json={"customer_id": ctx["customers"][0], "amount": "10.00", "idempotency_key": uuid4().hex})
    assert result.status_code == 201
    with Session(engine) as session:
        notification_id = session.scalar(select(Notification.notification_id).where(Notification.business_id == ctx["business"]))
    barrier = Barrier(2)
    def mark():
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            return client.patch(f"/api/v1/notifications/{notification_id}/read", headers={"Authorization": "Bearer " + create_access_token(ctx["recipient"])})
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(mark) for _ in range(2)]
        results = [job.result(timeout=30) for job in jobs]
    assert all(row.status_code == 200 for row in results)
    assert results[0].json()["read_at"] == results[1].json()["read_at"]


def test_recipient_resolution_uses_current_link_not_old_auth_snapshot(notification_race):
    ctx = notification_race
    with Session(engine) as session:
        actor = session.scalar(select(BusinessMember.user_id).where(BusinessMember.business_id == ctx["business"], BusinessMember.user_id != ctx["coowner"]))
        event = LedgerEntry(credit_account_id=ctx["accounts"][0], created_by=actor, entry_type="credit_sale", amount="10.00", idempotency_key=uuid4().hex)
        session.add(event)
        session.commit()
        event_id = event.entry_id
    with Session(engine) as old_reader:
        assert old_reader.get(CustomerProfile, ctx["customers"][0]).user_id == ctx["recipient"]
        with Session(engine) as writer:
            writer.get(CustomerProfile, ctx["customers"][0]).user_id = None
            writer.commit()
        assert notify_event(old_reader, "credit_sale_recorded", event_id) == []
        old_reader.commit()
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Notification).where(Notification.business_id == ctx["business"])) == 0
