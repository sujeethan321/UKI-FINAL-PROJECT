"""Isolated Day 9 API smoke: real login/JWTs, no provider/browser requests."""
from decimal import Decimal
from uuid import uuid4
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import func, select
from app.core.security import create_access_token
from app.models import BusinessMember, CommunicationAttempt, CustomerProfile, LedgerEntry, PaymentReminder, User
from test_day7_integration import integration_api
from test_shop_owner_dashboard import db


def test_day9_full_customer_reminder_handoff_inbox_and_settlement_lifecycle(integration_api):
    ctx = integration_api
    session, client = ctx["db"], ctx["client"]
    coowner = User(full_name="Day 9 test coowner", email=f"day9-coowner-{uuid4().hex}@example.com", password_hash="test-only-no-login", platform_role="shop_owner", account_status="active")
    customer_user = User(full_name="Day 9 linked customer", email=f"day9-customer-{uuid4().hex}@example.com", password_hash="test-only-no-login", platform_role="customer", account_status="active")
    session.add_all([coowner, customer_user]); session.flush()
    session.add(BusinessMember(user_id=coowner.user_id, business_id=ctx["business"], business_role="owner", membership_status="active"))
    profile = session.get(CustomerProfile, ctx["customer"])
    profile.user_id = customer_user.user_id; profile.phone = "0771234567"
    session.commit()
    login = client.post("/api/v1/auth/login", data={"username": ctx["owner"].email, "password": ctx["password"]})
    assert login.status_code == 200
    owner_token = login.json()["access_token"]
    client.headers["Authorization"] = "Bearer " + owner_token
    assert client.get("/api/v1/auth/me").json()["platform_role"] == "shop_owner"
    root = "/api/v1/shop-owner"
    params = {"business_id": ctx["business"]}
    customers = client.get(root + "/customers", params=params).json()["customers"]
    assert {r["customer_id"] for r in customers} == {ctx["customer"]}
    account = client.post(root + f"/customers/{ctx['customer']}/credit-account", params=params, json={"credit_limit": "500.00"})
    assert account.status_code == 201
    sale = client.post(root + "/credit-sales", params=params, json={"customer_id": ctx["customer"], "amount": "100.25", "idempotency_key": uuid4().hex})
    assert sale.status_code == 201 and sale.json()["outstanding_balance"] == "100.25"
    reminder_payload = {"customer_id": ctx["customer"], "language": "ta", "idempotency_key": uuid4().hex}
    reminder = client.post(root + "/payment-reminders", params=params, json=reminder_payload)
    assert reminder.status_code == 201
    reminder_id = reminder.json()["reminder_id"]
    assert client.post(root + "/payment-reminders", params=params, json=reminder_payload).status_code == 200
    history = client.get(root + "/payment-reminders", params=params).json()
    assert history["total"] == 1 and history["reminders"][0]["message"] == reminder.json()["message"]
    handoff_url = root + f"/payment-reminders/{reminder_id}/whatsapp-handoff"
    handoff_payload = {"customer_id": ctx["customer"], "idempotency_key": uuid4().hex}
    assert client.post(handoff_url, params=params, json=handoff_payload).status_code == 409
    consent = client.post(root + f"/customers/{ctx['customer']}/communication/consent", params=params, json={"consent_status": "granted", "confirmed": True, "evidence": "Customer explicitly stated WhatsApp permission in person today", "idempotency_key": uuid4().hex})
    assert consent.status_code == 201 and consent.json()["independently_verified"] is False
    prepared = client.post(handoff_url, params=params, json=handoff_payload)
    assert prepared.status_code == 201
    assert parse_qs(urlsplit(prepared.json()["handoff_url"]).query) == {"text": [reminder.json()["message"]]}
    assert prepared.json()["status"] == "handoff_requested"
    assert client.post(handoff_url, params=params, json=handoff_payload).status_code == 200
    assert session.scalar(select(func.count()).select_from(CommunicationAttempt)) == 1
    assert session.get(PaymentReminder, reminder_id).status == "recorded"
    assert session.scalar(select(func.count()).select_from(LedgerEntry)) == 1
    assert client.get("/api/v1/notifications").json()["total"] == 0
    client.headers["Authorization"] = "Bearer " + create_access_token(coowner.user_id)
    inbox = client.get("/api/v1/notifications").json()
    assert inbox["total"] == 1 and inbox["notifications"][0]["notification_type"] == "payment_reminder_recorded"
    assert client.get("/api/v1/notifications/unread-count").json() == {"unread_count": 1}
    read_url = f"/api/v1/notifications/{inbox['notifications'][0]['notification_id']}/read"
    first = client.patch(read_url)
    assert first.status_code == 200 and client.patch(read_url).json()["read_at"] == first.json()["read_at"]
    assert client.get("/api/v1/notifications/unread-count").json() == {"unread_count": 0}
    client.headers["Authorization"] = "Bearer " + owner_token
    for amount, debt in [("25.00", "75.25"), ("75.25", "0.00")]:
        payment = client.post(root + "/repayments", params=params, json={"customer_id": ctx["customer"], "amount": amount, "payment_method": "cash", "idempotency_key": uuid4().hex})
        assert payment.status_code == 201 and Decimal(payment.json()["outstanding_balance"]) == Decimal(debt)
        receipt = client.get(root + f"/repayments/{payment.json()['entry_id']}/receipt", params=params)
        assert receipt.status_code == 200
    assert client.post(handoff_url, params=params, json=handoff_payload).status_code == 409
    assert session.scalar(select(func.count()).select_from(CommunicationAttempt)) == 1
    client.headers["Authorization"] = "Bearer " + create_access_token(customer_user.user_id)
    assert client.get("/api/v1/notifications").json()["total"] == 3
    client.headers.pop("Authorization")
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/notifications").status_code == 401
    assert client.get(root + "/customers", params=params).status_code == 401
