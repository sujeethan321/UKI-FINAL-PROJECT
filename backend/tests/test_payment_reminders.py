"""Real-JWT reminder API and shared financial semantics."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import engine
from app.models import Business, BusinessMember, CreditAccount, CustomerProfile, LedgerEntry, PaymentReminder
from app.routers import shop_owner_reminders
from test_day7_integration import integration_api
from test_shop_owner_credit_sales import sale_api, post_sale, details
from test_shop_owner_dashboard import db, make_entry

URL = "/api/v1/shop-owner/payment-reminders"


def post(ctx, **changes):
    payload = dict(customer_id=ctx["customer"], idempotency_key=f"reminder-{uuid4().hex}")
    payload.update(changes)
    return ctx["client"].post(URL, params={"business_id": ctx["business"]}, json=payload)


def history(ctx, **params):
    return ctx["client"].get(URL, params={"business_id": ctx["business"], **params})


@pytest.fixture
def reminder_api(sale_api):
    assert post_sale(sale_api, amount="100.25").status_code == 201
    return sale_api


def test_snapshot_identity_no_delivery_and_unchanged_ledger(reminder_api):
    ctx = reminder_api
    before = details(ctx)
    result = post(ctx, note="  private internal note  ")
    assert result.status_code == 201
    data = result.json()
    assert data["outstanding_amount"] == "100.25"
    assert data["status"] == "recorded" and data["currency"] == "LKR"
    assert data["created_by"] == ctx["owner"].user_id
    assert data["consent_status"] == "unknown" and data["delivery_allowed"] is False
    assert "LKR 100.25" in data["message"] and "overdue" not in data["message"]
    assert data["note"] == "private internal note" and "private internal note" not in data["message"]
    assert data["created_at"] == data["updated_at"]
    assert result.headers["cache-control"] == "no-store"
    assert details(ctx) == before
    assert history(ctx).json()["reminders"][0]["reminder_id"] == data["reminder_id"]


@pytest.mark.parametrize("kind,expected", [("partial", "60.25"), ("full", None),
    ("sale_reversal", None), ("repayment_reversal", "100.25"), ("advance", None)])
def test_effective_ledger(reminder_api, kind, expected):
    ctx = reminder_api
    session = ctx["db"]
    if kind in ("partial", "full", "repayment_reversal", "advance"):
        amount = "100.25" if kind == "full" else "200.00" if kind == "advance" else "40.00"
        entry_id = make_entry(session, ctx["owner"].user_id, ctx["account"], "repayment", amount)
        if kind == "repayment_reversal":
            make_entry(session, ctx["owner"].user_id, ctx["account"], "reversal", amount, entry_id)
    else:
        sale_id = session.scalar(select(LedgerEntry.entry_id).where(LedgerEntry.credit_account_id == ctx["account"]))
        make_entry(session, ctx["owner"].user_id, ctx["account"], "reversal", "100.25", sale_id)
    session.commit()
    result = post(ctx)
    assert result.status_code == (201 if expected else 409)
    if expected:
        assert result.json()["outstanding_amount"] == details(ctx)["outstanding_balance"] == expected


def test_no_account(integration_api):
    assert post(integration_api).status_code == 404


def test_empty_account(sale_api):
    assert post(sale_api).status_code == 409


def test_account_business_mismatch(reminder_api):
    ctx = reminder_api
    ctx["db"].get(CreditAccount, ctx["account"]).creditor_business_id = ctx["other_business"]
    ctx["db"].commit()
    assert post(ctx).status_code == 404


def test_large_aggregate_snapshot(reminder_api):
    ctx = reminder_api
    for _ in range(2):
        make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "credit_sale", "999999999999.99")
    ctx["db"].commit()
    result = post(ctx)
    assert result.status_code == 201
    assert result.json()["outstanding_amount"] == details(ctx)["outstanding_balance"] == "2000000000100.23"


def test_database_unique_key_and_case_sensitive_keys(reminder_api, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    ctx = reminder_api
    monkeypatch.setattr(settings, "REMINDER_COOLDOWN_SECONDS", 0)
    assert post(ctx, idempotency_key="CaseKey").status_code == 201
    assert post(ctx, idempotency_key="casekey").status_code == 201
    row = ctx["db"].scalar(select(PaymentReminder).where(PaymentReminder.business_id == ctx["business"]))
    values = {column.name: getattr(row, column.name) for column in PaymentReminder.__table__.columns if column.name != "reminder_id"}
    with ctx["db"].begin_nested():
        with pytest.raises(IntegrityError):
            ctx["db"].execute(PaymentReminder.__table__.insert().values(**values))


@pytest.mark.parametrize("condition", ["anonymous", "invalid", "customer", "driver", "admin", "inactive_user", "pending", "inactive_member", "unowned"])
def test_security_for_create_and_history(reminder_api, condition):
    ctx = reminder_api
    if condition == "anonymous":
        ctx["client"].headers.pop("Authorization")
    elif condition == "invalid":
        ctx["client"].headers["Authorization"] = "Bearer invalid"
    elif condition in ("customer", "driver", "admin"):
        ctx["owner"].platform_role = condition
    elif condition == "inactive_user":
        ctx["owner"].account_status = "suspended"
    elif condition == "pending":
        ctx["db"].get(Business, ctx["business"]).approval_status = "pending"
    elif condition == "inactive_member":
        ctx["db"].scalar(select(BusinessMember).where(BusinessMember.business_id == ctx["business"])).membership_status = "inactive"
    else:
        ctx["business"] = ctx["other_business"]
    ctx["db"].commit()
    expected = 401 if condition in ("anonymous", "invalid") else 403
    assert post(ctx).status_code == history(ctx).status_code == expected


def test_foreign_customer_and_history_filter(reminder_api):
    ctx = reminder_api
    assert post(ctx, customer_id=ctx["other_customer"]).status_code == 404
    assert history(ctx, customer_id=ctx["other_customer"]).status_code == 404
    assert post(ctx).status_code == 201
    ctx["db"].add(BusinessMember(business_id=ctx["other_business"], user_id=ctx["owner"].user_id,
        business_role="owner", membership_status="active"))
    ctx["db"].commit()
    ctx["business"] = ctx["other_business"]
    assert history(ctx).json()["total"] == 0
    assert post(ctx).status_code == 404


@pytest.mark.parametrize("changes", [{"channel": "email"}, {"channel": "bogus"}, {"language": "xx"},
    {"idempotency_key": ""}, {"idempotency_key": "bad key"}, {"idempotency_key": "x" * 101},
    {"customer_id": True}, {"customer_id": "1"}, {"customer_id": 0}, {"note": "x" * 1001},
    {"note": "bad\x00"}, {"outstanding_amount": "1.00"}, {"status": "sent"}, {"created_by": 1}, {"message": "custom"}])
def test_input_validation(reminder_api, changes):
    assert post(reminder_api, **changes).status_code == 422


def test_replay_is_original_snapshot_even_after_settlement(reminder_api):
    ctx = reminder_api
    key = uuid4().hex
    first = post(ctx, idempotency_key=key)
    make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "repayment", "100.25")
    ctx["db"].commit()
    second = post(ctx, idempotency_key=key)
    assert second.status_code == 200
    assert second.json() == {**first.json(), "replayed": True}
    assert post(ctx, idempotency_key=key, language="ta").status_code == 409
    assert history(ctx).json()["total"] == 1


def test_cooldown_cross_channel_expiry_and_config(reminder_api, monkeypatch):
    ctx = reminder_api
    ctx["db"].get(CustomerProfile, ctx["customer"]).phone = "0771234567"
    ctx["db"].commit()
    assert post(ctx).status_code == 201
    assert post(ctx, channel="whatsapp").status_code == 409
    row = ctx["db"].scalar(select(PaymentReminder).where(PaymentReminder.business_id == ctx["business"]))
    row.created_at -= timedelta(days=2)
    ctx["db"].commit()
    assert post(ctx, channel="whatsapp").status_code == 201
    monkeypatch.setattr(settings, "REMINDER_COOLDOWN_SECONDS", 0)
    assert post(ctx).status_code == 201


@pytest.mark.parametrize("channel", ["copy", "whatsapp", "sms"])
def test_missing_phone_internal_only(reminder_api, channel):
    assert post(reminder_api, channel=channel).status_code == 409
    assert post(reminder_api).status_code == 201


@pytest.mark.parametrize("status", ["closed", "suspended"])
def test_inactive_account(reminder_api, status):
    ctx = reminder_api
    ctx["db"].get(CreditAccount, ctx["account"]).account_status = status
    ctx["db"].commit()
    assert post(ctx).status_code == 409


def test_tamil_and_history_pagination(reminder_api, monkeypatch):
    ctx = reminder_api
    monkeypatch.setattr(settings, "REMINDER_COOLDOWN_SECONDS", 0)
    ids = [post(ctx, language="ta").json()["reminder_id"] for _ in range(3)]
    result = history(ctx, customer_id=ctx["customer"], status="recorded", page=2, page_size=1, ordering="oldest")
    assert result.status_code == 200 and result.json()["total"] == 3
    assert result.json()["reminders"][0]["reminder_id"] == ids[1]
    assert "நிலுவை" in result.json()["reminders"][0]["message"]
    assert history(ctx).json()["reminders"][0]["reminder_id"] == ids[-1]
    for params in ({"page": 0}, {"page_size": 101}, {"status": "delivered"}, {"ordering": "invalid"}):
        assert history(ctx, **params).status_code == 422


@pytest.mark.parametrize("operation", ["create", "history"])
def test_database_errors_are_sanitized(reminder_api, monkeypatch, operation):
    def fail(*args, **kwargs):
        raise SQLAlchemyError("secret phone and message")
    monkeypatch.setattr(shop_owner_reminders, "record_reminder" if operation == "create" else "reminder_history", fail)
    result = post(reminder_api) if operation == "create" else history(reminder_api)
    assert result.status_code == 500 and "secret" not in result.text
    assert reminder_api["db"].scalar(select(func.count()).select_from(PaymentReminder)) == 0


def test_migration_constraints_and_route_registration():
    inspector = inspect(engine)
    assert {"business_id", "idempotency_key"} in [set(item["column_names"]) for item in inspector.get_unique_constraints("payment_reminders")]
    assert len(inspector.get_foreign_keys("payment_reminders")) == 4
    from app.main import app
    paths = app.openapi()["paths"]
    assert set(paths[URL]) == {"get", "post"}
    assert "patch" not in paths[URL]
