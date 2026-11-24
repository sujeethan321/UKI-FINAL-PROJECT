"""Independent MySQL requests must serialize on the existing account lock."""
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models import LedgerEntry, PaymentReminder
from test_credit_sales_concurrency import committed_sales, race_requests

URL = "/api/v1/shop-owner/payment-reminders"


@pytest.fixture
def committed_reminders(committed_sales):
    ctx = committed_sales
    with Session(engine) as session:
        for account in ctx["accounts"]:
            # Fixture ownership is already established by committed_sales.
            from app.models import BusinessMember
            user_id = session.scalar(select(BusinessMember.user_id).where(BusinessMember.business_id == ctx["business"]))
            session.add(LedgerEntry(credit_account_id=account, created_by=user_id,
                entry_type="credit_sale", amount="100.25", idempotency_key=uuid4().hex))
        session.commit()
    try:
        yield ctx
    finally:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT DATABASE()")) == "lankapex_test_db"
            connection.execute(delete(PaymentReminder).where(PaymentReminder.business_id == ctx["business"]))


@pytest.mark.parametrize("kind", ["identical", "changed", "cooldown", "cross_account"])
def test_concurrent_reminders(committed_reminders, kind):
    ctx = committed_reminders
    key = uuid4().hex
    first = dict(customer_id=ctx["customers"][0], idempotency_key=key)
    second = dict(first)
    if kind == "changed":
        second["language"] = "ta"
    elif kind == "cooldown":
        second["idempotency_key"] = uuid4().hex
    elif kind == "cross_account":
        second["customer_id"] = ctx["customers"][1]
    results = race_requests(ctx, [first, second], paths=[URL, URL])
    assert sorted(item.status_code for item in results) == ([200, 201] if kind == "identical" else [201, 409])
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(PaymentReminder).where(
            PaymentReminder.business_id == ctx["business"])) == 1
        assert session.scalar(select(func.count()).select_from(LedgerEntry).where(
            LedgerEntry.credit_account_id.in_(ctx["accounts"]))) == 2
