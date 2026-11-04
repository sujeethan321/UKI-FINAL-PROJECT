"""No external requests: real JWTs and rollback-isolated MySQL communication tests."""
from uuid import uuid4
from urllib.parse import urlsplit, parse_qs
import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import engine
from app.models import Business, BusinessMember, CommunicationAttempt, CommunicationConsent, CustomerProfile, LedgerEntry, PaymentReminder
from app.routers import shop_owner_communication
from app.services.communication_service import normalize_whatsapp_phone
from test_day7_integration import integration_api
from test_shop_owner_credit_sales import sale_api, post_sale, details
from test_shop_owner_dashboard import db, make_entry

ROOT = "/api/v1/shop-owner"


@pytest.fixture
def communication_api(sale_api):
    ctx = sale_api
    ctx["db"].get(CustomerProfile, ctx["customer"]).phone = "0771234567"
    ctx["db"].commit()
    assert post_sale(ctx).status_code == 201
    response = ctx["client"].post(ROOT + "/payment-reminders", params={"business_id": ctx["business"]}, json={"customer_id": ctx["customer"], "language": "ta", "idempotency_key": uuid4().hex})
    assert response.status_code == 201
    ctx["reminder"] = response.json()["reminder_id"]
    ctx["saved_message"] = response.json()["message"]
    return ctx


def preference(ctx, status="granted", **changes):
    payload = {"channel": "whatsapp", "consent_status": status, "evidence": "Customer stated preference in person today", "confirmed": True, "idempotency_key": uuid4().hex, **changes}
    return ctx["client"].post(ROOT + f"/customers/{ctx['customer']}/communication/consent", params={"business_id": ctx["business"]}, json=payload)


def preview(ctx, **changes):
    params = {"business_id": ctx["business"], "customer_id": ctx["customer"], **changes}
    return ctx["client"].get(ROOT + f"/payment-reminders/{ctx['reminder']}/communication", params=params)


def handoff(ctx, **changes):
    return ctx["client"].post(ROOT + f"/payment-reminders/{ctx['reminder']}/whatsapp-handoff", params={"business_id": ctx["business"]}, json={"customer_id": ctx["customer"], "channel": "whatsapp", "idempotency_key": uuid4().hex, **changes})


def count(ctx, model=CommunicationAttempt):
    return ctx["db"].scalar(select(func.count()).select_from(model))


@pytest.mark.parametrize("phone", ["0771234567", "+94771234567", "94771234567", "+94 77 123 4567", "(077) 123-4567"])
def test_supported_phone_forms(phone):
    assert normalize_whatsapp_phone(phone) == "94771234567"


@pytest.mark.parametrize("phone", [None, "", " ", "771234567", "0094771234567", "+44771234567", "0112345678", "077123456", "07712345678", "0771234567?text=bad", "０７７１２３４５６７", "077\n1234567"])
def test_unsupported_ambiguous_or_missing_phone(phone):
    assert normalize_whatsapp_phone(phone) is None


def test_unknown_consent_blocks_without_assuming_permission(communication_api):
    ctx = communication_api
    response = preview(ctx)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json()["consent_status"] == "unknown" and response.json()["eligible"] is False
    assert handoff(ctx).status_code == 409 and count(ctx) == 0


def test_authorized_handoff_uses_exact_saved_message_and_never_updates_ledger_or_status(communication_api):
    ctx = communication_api
    before = details(ctx)
    assert preference(ctx).status_code == 201
    assert preview(ctx).json()["eligible"] is True
    key = uuid4().hex
    first = handoff(ctx, idempotency_key=key)
    assert first.status_code == 201
    result = first.json()
    assert result["status"] == "handoff_requested" and result["provider_delivery_available"] is False
    assert result["message"] == ctx["saved_message"]
    url = urlsplit(result["handoff_url"])
    assert url.scheme == "https" and url.netloc == "wa.me" and url.path == "/94771234567"
    assert parse_qs(url.query) == {"text": [ctx["saved_message"]]}
    assert "%E0%AE" in url.query
    replay = handoff(ctx, idempotency_key=key)
    assert replay.status_code == 200 and replay.json() == {**result, "replayed": True}
    assert count(ctx) == 1
    assert ctx["db"].get(PaymentReminder, ctx["reminder"]).status == "recorded"
    assert details(ctx) == before
    assert preview(ctx).json()["attempts"][0]["status"] == "handoff_requested"


def test_english_encoding_and_no_internal_metadata(communication_api):
    ctx = communication_api
    reminder = ctx["db"].get(PaymentReminder, ctx["reminder"])
    # Saved template content is the sole source even for punctuation and UTF-8.
    reminder.message = "Hello Customer & Shop, LKR 100.25. Please arrange payment."
    reminder.language = "en"
    ctx["db"].commit()
    preference(ctx)
    result = handoff(ctx).json()
    assert parse_qs(urlsplit(result["handoff_url"]).query) == {"text": [reminder.message]}
    assert "%26" in result["handoff_url"] and "access_token" not in result["handoff_url"]


def test_opt_out_blocks_even_prior_successful_key_replay(communication_api):
    ctx = communication_api
    preference(ctx)
    key = uuid4().hex
    assert handoff(ctx, idempotency_key=key).status_code == 201
    assert preference(ctx, "opted_out").status_code == 201
    assert preview(ctx).json()["consent_status"] == "opted_out"
    assert handoff(ctx, idempotency_key=key).status_code == 409
    assert count(ctx) == 1


def test_consent_is_audited_idempotent_and_old_replay_cannot_reverse_opt_out(communication_api):
    ctx = communication_api
    key = uuid4().hex
    first = preference(ctx, idempotency_key=key)
    assert first.status_code == 201 and first.json()["independently_verified"] is False
    assert preference(ctx, "opted_out").status_code == 201
    assert preference(ctx, idempotency_key=key).status_code == 200
    assert preview(ctx).json()["consent_status"] == "opted_out"
    assert count(ctx, CommunicationConsent) == 2
    assert preference(ctx, "opted_out", idempotency_key=key).status_code == 409


def test_contact_change_requires_new_permission_and_never_rewrites_phone_storage(communication_api):
    ctx = communication_api
    preference(ctx)
    profile = ctx["db"].get(CustomerProfile, ctx["customer"])
    assert profile.phone == "0771234567"
    profile.phone = "0777654321"
    ctx["db"].commit()
    assert preview(ctx).json()["consent_status"] == "unknown"
    assert handoff(ctx).status_code == 409
    assert preference(ctx).status_code == 201
    assert handoff(ctx).json()["normalized_phone"] == "94777654321"
    assert profile.phone == "0777654321"


@pytest.mark.parametrize("phone", [None, "bad", "771234567"])
def test_missing_invalid_phone_blocks_grant_and_handoff_but_allows_opt_out(communication_api, phone):
    ctx = communication_api
    ctx["db"].get(CustomerProfile, ctx["customer"]).phone = phone
    ctx["db"].commit()
    assert preference(ctx).status_code == 409
    assert preview(ctx).json()["eligible"] is False
    assert handoff(ctx).status_code == 409
    assert preference(ctx, "opted_out").status_code == 201


@pytest.mark.parametrize("condition", ["anonymous", "invalid", "customer", "driver", "admin", "inactive", "pending", "inactive_member", "other_business"])
def test_all_endpoints_enforce_auth_and_business_ownership(communication_api, condition):
    ctx = communication_api
    if condition == "anonymous":
        ctx["client"].headers.pop("Authorization")
    elif condition == "invalid":
        ctx["client"].headers["Authorization"] = "Bearer invalid"
    elif condition in ("customer", "driver", "admin"):
        ctx["owner"].platform_role = condition
    elif condition == "inactive":
        ctx["owner"].account_status = "suspended"
    elif condition == "pending":
        ctx["db"].get(Business, ctx["business"]).approval_status = "pending"
    elif condition == "inactive_member":
        ctx["db"].scalar(select(BusinessMember).where(BusinessMember.business_id == ctx["business"])).membership_status = "inactive"
    else:
        ctx["business"] = ctx["other_business"]
    ctx["db"].commit()
    expected = 401 if condition in ("anonymous", "invalid") else 403
    assert preview(ctx).status_code == preference(ctx).status_code == handoff(ctx).status_code == expected
    assert count(ctx) == 0


def test_cross_business_customer_and_manipulated_reminder_ids_are_concealed(communication_api):
    ctx = communication_api
    assert preview(ctx, customer_id=ctx["other_customer"]).status_code == 404
    assert handoff(ctx, customer_id=ctx["other_customer"]).status_code == 404
    original = ctx["customer"]
    ctx["customer"] = ctx["other_customer"]
    assert preference(ctx).status_code == 404
    ctx["customer"] = original
    for bad, expected in [(0, 422), (-1, 422), ("bad", 422), (9223372036854775807, 404)]:
        ctx["reminder"] = bad
        assert preview(ctx).status_code == handoff(ctx).status_code == expected


@pytest.mark.parametrize("patch", [{"channel": "sms"}, {"channel": "email"}, {"amount": "1.00"}, {"phone": "0771234567"}, {"message": "fake"}, {"status": "delivered"}, {"customer_id": True}, {"idempotency_key": "bad key"}])
def test_handoff_accepts_only_supported_fields(communication_api, patch):
    assert handoff(communication_api, **patch).status_code == 422


@pytest.mark.parametrize("patch", [{"confirmed": False}, {"confirmed": "true"}, {"evidence": " "}, {"evidence": "x" * 501}, {"evidence": "bad\x00"}, {"consent_status": "unknown"}, {"channel": "sms"}, {"delivery_allowed": True}])
def test_preference_requires_explicit_customer_statement(communication_api, patch):
    assert preference(communication_api, **patch).status_code == 422


@pytest.mark.parametrize("kind", ["partial", "settled", "closed"])
def test_changed_balances_or_account_block_saved_handoff(communication_api, kind):
    ctx = communication_api
    preference(ctx)
    if kind == "closed":
        from app.models import CreditAccount
        ctx["db"].get(CreditAccount, ctx["account"]).account_status = "closed"
    else:
        make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "repayment", "10.00" if kind == "partial" else "100.25")
    ctx["db"].commit()
    assert preview(ctx).json()["eligible"] is False
    assert handoff(ctx).status_code == 409 and count(ctx) == 0


def test_failed_financial_operation_cannot_create_a_communication_event(sale_api):
    ctx = sale_api
    assert post_sale(ctx, amount="2000").status_code == 409
    assert count(ctx, LedgerEntry) == 0 and count(ctx) == 0
    ctx["reminder"] = 9223372036854775807
    assert handoff(ctx).status_code == 404
    assert count(ctx) == 0


@pytest.mark.parametrize("operation", ["preview", "consent", "handoff"])
def test_database_failures_rollback_and_hide_diagnostics(communication_api, monkeypatch, operation):
    def fail(*args, **kwargs):
        raise SQLAlchemyError("private SQL phone token message")
    target = {"preview": "communication_preview", "consent": "record_consent", "handoff": "request_handoff"}[operation]
    monkeypatch.setattr(shop_owner_communication, target, fail)
    response = {"preview": preview, "consent": preference, "handoff": handoff}[operation](communication_api)
    assert response.status_code == 500 and "private" not in response.text
    assert count(communication_api) == 0


def test_migration_indexes_and_no_delivery_status_mutation_routes():
    inspector = inspect(engine)
    assert {"business_id", "idempotency_key"} in [set(c["column_names"]) for c in inspector.get_unique_constraints("communication_attempts")]
    assert len(inspector.get_foreign_keys("communication_attempts")) == 5
    assert len(inspector.get_foreign_keys("communication_consents")) == 3
    from app.main import app
    paths = app.openapi()["paths"]
    assert set(paths[ROOT + "/payment-reminders/{reminder_id}/whatsapp-handoff"]) == {"post"}


def test_existing_reminder_history_reflects_permission_without_claiming_delivery(communication_api):
    ctx = communication_api
    assert preference(ctx).status_code == 201
    history = ctx["client"].get(ROOT + "/payment-reminders", params={"business_id": ctx["business"]}).json()
    assert history["reminders"][0]["consent_status"] == "granted"
    assert history["reminders"][0]["delivery_allowed"] is False
    assert preference(ctx, "opted_out").status_code == 201
    history = ctx["client"].get(ROOT + "/payment-reminders", params={"business_id": ctx["business"]}).json()
    assert history["reminders"][0]["consent_status"] == "opted_out"
