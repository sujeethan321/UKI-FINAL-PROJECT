"""Real MySQL races using independent connections and fixture-owned rows only.

Outer rollback fixtures cannot make seed rows visible to independent sessions.
These tests commit their unique seeds and delete only their exact owned IDs.
"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event, Lock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.core.security import create_access_token
from app.main import app
from app.models import Business, BusinessMember, CreditAccount, CustomerProfile, LedgerEntry, User


@pytest.fixture
def committed_sales():
    assert settings.MYSQL_DATABASE == engine.url.database == "lankapex_test_db"
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT DATABASE()")) == "lankapex_test_db"
    assert not app.dependency_overrides, "Concurrency tests require actual per-request sessions"
    user_id = business_id = None
    customer_ids, account_ids = [], []
    try:
        with Session(engine) as session:
            user = User(full_name="Day 8 concurrency fixture", email=f"day8-race-{uuid4().hex}@example.com",
                        password_hash="test-only-no-login", platform_role="shop_owner",
                        preferred_language="en", account_status="active")
            session.add(user)
            session.flush()
            user_id = user.user_id
            business = Business(business_name="Day 8 concurrency fixture", business_type="retail", approval_status="approved")
            session.add(business)
            session.flush()
            business_id = business.business_id
            session.add(BusinessMember(user_id=user_id, business_id=business_id,
                                       business_role="owner", membership_status="active"))
            for index in range(2):
                customer = CustomerProfile(business_id=business_id, customer_name=f"Race fixture {index}")
                session.add(customer)
                session.flush()
                customer_ids.append(customer.customer_id)
                account = CreditAccount(creditor_business_id=business_id, customer_id=customer.customer_id,
                    credit_limit=Decimal("1000.00"), payment_term_days=30, account_status="active")
                session.add(account)
                session.flush()
                account_ids.append(account.credit_account_id)
            session.commit()
        with TestClient(app) as client:
            yield {"client": client, "business": business_id, "customers": customer_ids, "accounts": account_ids,
                   "headers": {"Authorization": f"Bearer {create_access_token(user_id)}"}}
    finally:
        # No bulk reset, truncate, schema changes, or unrelated rows are touched.
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT DATABASE()")) == "lankapex_test_db"
            if account_ids:
                connection.execute(delete(LedgerEntry).where(LedgerEntry.credit_account_id.in_(account_ids)))
                connection.execute(delete(CreditAccount).where(CreditAccount.credit_account_id.in_(account_ids)))
            if customer_ids:
                connection.execute(delete(CustomerProfile).where(CustomerProfile.customer_id.in_(customer_ids)))
            if business_id is not None:
                connection.execute(delete(BusinessMember).where(BusinessMember.business_id == business_id))
                connection.execute(delete(Business).where(Business.business_id == business_id))
            if user_id is not None:
                connection.execute(delete(User).where(User.user_id == user_id))
        with engine.connect() as connection:
            if account_ids:
                assert connection.scalar(select(func.count()).select_from(LedgerEntry).where(
                    LedgerEntry.credit_account_id.in_(account_ids))) == 0
            if user_id is not None:
                assert connection.scalar(select(func.count()).select_from(User).where(User.user_id == user_id)) == 0


def race_requests(ctx, payloads, paths=None):
    both_attempted = Event()
    counter_lock = Lock()
    attempts = 0

    def observe_account_lock(connection, cursor, statement, parameters, context, executemany):
        nonlocal attempts
        sql = statement.lower()
        if "from credit_accounts" in sql and "for update" in sql:
            with counter_lock:
                attempts += 1
                if attempts >= 2:
                    both_attempted.set()

    def send(index, payload):
        path = paths[index] if paths else "/api/v1/shop-owner/credit-sales"
        return ctx["client"].post(path, params={"business_id": ctx["business"]},
                                  headers=ctx["headers"], json=payload)

    with engine.connect() as blocker:
        transaction = blocker.begin()
        blocker.execute(select(CreditAccount.credit_account_id).where(
            CreditAccount.credit_account_id.in_(ctx["accounts"])).with_for_update()).all()
        event.listen(engine, "before_cursor_execute", observe_account_lock)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(send, index, payload) for index, payload in enumerate(payloads)]
                try:
                    assert both_attempted.wait(20), "Both independent requests must reach the account lock"
                    assert all(not future.done() for future in futures), "Requests must wait for the MySQL row lock"
                finally:
                    transaction.rollback()
                return [future.result(timeout=30) for future in futures]
        finally:
            if transaction.is_active:
                transaction.rollback()
            event.remove(engine, "before_cursor_execute", observe_account_lock)


def persisted_entries(ctx):
    with Session(engine) as session:
        return [(entry.entry_id, entry.amount, entry.idempotency_key) for entry in session.scalars(
            select(LedgerEntry).where(LedgerEntry.credit_account_id.in_(ctx["accounts"])))]


def test_simultaneous_sales_cannot_jointly_exceed_limit(committed_sales):
    ctx = committed_sales
    payloads = [{"customer_id": ctx["customers"][0], "amount": "600.00", "idempotency_key": f"limit-{uuid4().hex}"} for _ in range(2)]
    responses = race_requests(ctx, payloads)
    assert sorted(response.status_code for response in responses) == [201, 409]
    rows = persisted_entries(ctx)
    assert len(rows) == 1
    assert sum((row[1] for row in rows), Decimal("0.00")) == Decimal("600.00")


def test_simultaneous_identical_key_replays_once(committed_sales):
    ctx = committed_sales
    payload = {"customer_id": ctx["customers"][0], "amount": "600", "idempotency_key": f"same-{uuid4().hex}"}
    responses = race_requests(ctx, [payload, payload])
    assert sorted(response.status_code for response in responses) == [200, 201]
    assert responses[0].json()["entry_id"] == responses[1].json()["entry_id"]
    assert responses[0].json()["receipt_number"] == responses[1].json()["receipt_number"]
    assert len(persisted_entries(ctx)) == 1


def test_simultaneous_key_with_different_amount_conflicts(committed_sales):
    ctx = committed_sales
    key = f"different-{uuid4().hex}"
    payloads = [{"customer_id": ctx["customers"][0], "amount": amount, "idempotency_key": key} for amount in ("600", "700")]
    responses = race_requests(ctx, payloads)
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert len(persisted_entries(ctx)) == 1


def test_global_key_uniqueness_across_simultaneous_accounts(committed_sales):
    ctx = committed_sales
    key = f"global-{uuid4().hex}"
    payloads = [{"customer_id": customer, "amount": "100", "idempotency_key": key} for customer in ctx["customers"]]
    responses = race_requests(ctx, payloads)
    assert sorted(response.status_code for response in responses) == [201, 409]
    rows = persisted_entries(ctx)
    assert len(rows) == 1
    assert rows[0][2] == key
