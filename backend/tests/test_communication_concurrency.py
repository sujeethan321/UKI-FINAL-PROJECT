"""Real independent MySQL handoff retries serialize with opt-out eligibility."""
from uuid import uuid4
import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models import CommunicationAttempt, CommunicationConsent, CustomerProfile
from test_credit_sales_concurrency import committed_sales, race_requests
from test_payment_reminders_concurrency import committed_reminders


@pytest.fixture
def handoff_race(committed_reminders):
    ctx = committed_reminders
    try:
        with Session(engine) as session:
            assert session.scalar(text("SELECT DATABASE()")) == "lankapex_test_db"
            session.get(CustomerProfile, ctx["customers"][0]).phone = "0771234567"
            session.commit()
        consent_url = f"/api/v1/shop-owner/customers/{ctx['customers'][0]}/communication/consent"
        consent = ctx["client"].post(consent_url, params={"business_id": ctx["business"]}, headers=ctx["headers"], json={"consent_status": "granted", "evidence": "Customer stated permission in person", "confirmed": True, "idempotency_key": uuid4().hex})
        assert consent.status_code == 201
        reminder = ctx["client"].post("/api/v1/shop-owner/payment-reminders", params={"business_id": ctx["business"]}, headers=ctx["headers"], json={"customer_id": ctx["customers"][0], "idempotency_key": uuid4().hex})
        assert reminder.status_code == 201
        ctx["reminder"] = reminder.json()["reminder_id"]
        yield ctx
    finally:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT DATABASE()")) == "lankapex_test_db"
            connection.execute(delete(CommunicationAttempt).where(CommunicationAttempt.business_id == ctx["business"]))
            connection.execute(delete(CommunicationConsent).where(CommunicationConsent.business_id == ctx["business"]))


def test_simultaneous_identical_handoffs_record_only_once(handoff_race):
    ctx = handoff_race
    url = f"/api/v1/shop-owner/payment-reminders/{ctx['reminder']}/whatsapp-handoff"
    payload = {"customer_id": ctx["customers"][0], "idempotency_key": uuid4().hex}
    results = race_requests(ctx, [payload, payload], paths=[url, url])
    assert sorted(row.status_code for row in results) == [200, 201]
    assert results[0].json()["attempt_id"] == results[1].json()["attempt_id"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(CommunicationAttempt).where(CommunicationAttempt.business_id == ctx["business"])) == 1
