"""Real-JWT, isolated MySQL notification ownership and confirmed event integration."""
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from app.core.database import engine
from app.core.security import create_access_token
from app.main import app
from app.models import (Business, BusinessApprovalAudit, BusinessMember, CustomerProfile,
                        LedgerEntry, Notification, PaymentReminder, User)
from app.routers import notifications, admin_businesses
from app.services import notification_service, shop_owner_credit_sale_service, shop_owner_repayment_service, shop_owner_reminder_service
from app.services.notification_service import notify_event, utc_now
from test_day7_integration import integration_api
from test_shop_owner_credit_sales import sale_api, post_sale, details
from test_shop_owner_dashboard import db

URL = "/api/v1/notifications"


def make_user(session, role="customer", status="active"):
    user = User(full_name="Notification test user", email=f"notification-{uuid4().hex}@example.com",
                password_hash="test-only-no-login", platform_role=role, account_status=status)
    session.add(user)
    session.flush()
    return user


def seed(session, user_id, business_id, *, read=False, kind="repayment_recorded", stamp=None):
    row = Notification(recipient_user_id=user_id, business_id=business_id,
        notification_type=kind, title="Test event", message="Minimal test event.",
        related_entity_type="ledger_entry", related_entity_id=1,
        event_key=f"test-{uuid4().hex}", is_read=read,
        created_at=stamp or utc_now(), read_at=utc_now() if read else None)
    session.add(row)
    session.flush()
    return row.notification_id


def auth(ctx, user_id):
    ctx["client"].headers["Authorization"] = f"Bearer {create_access_token(user_id)}"


def count(session, model=Notification):
    return session.scalar(select(func.count()).select_from(model))


@pytest.fixture
def inbox(integration_api):
    ctx = integration_api
    other = make_user(ctx["db"])
    ctx["other_user"] = other.user_id
    ctx["ids"] = [seed(ctx["db"], ctx["owner"].user_id, ctx["business"]) for _ in range(3)]
    ctx["foreign_id"] = seed(ctx["db"], other.user_id, ctx["other_business"])
    ctx["db"].commit()
    return ctx


@pytest.fixture
def linked(sale_api):
    ctx = sale_api
    customer_user = make_user(ctx["db"])
    ctx["db"].get(CustomerProfile, ctx["customer"]).user_id = customer_user.user_id
    ctx["linked_user"] = customer_user.user_id
    ctx["db"].commit()
    return ctx


def test_list_only_owned_notifications_and_minimal_utc_response(inbox):
    response = inbox["client"].get(URL)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3 and data["page"] == 1 and data["page_size"] == 20
    assert [row["notification_id"] for row in data["notifications"]] == inbox["ids"][::-1]
    assert all(row["business_id"] == inbox["business"] for row in data["notifications"])
    for row in data["notifications"]:
        assert row["created_at"].endswith("Z") and row["read_at"] is None
        assert not {"event_key", "recipient_user_id", "amount", "phone", "email", "ledger", "notes", "destination_url"} & row.keys()
    assert response.headers["cache-control"] == "no-store"
    # IDs in query parameters cannot redirect recipient ownership.
    assert inbox["client"].get(URL, params={"recipient_user_id": inbox["other_user"]}).status_code == 422
    assert inbox["client"].get(URL, params={"user_id": inbox["other_user"]}).status_code == 422


@pytest.mark.parametrize("role", ["shop_owner", "customer", "driver", "admin"])
def test_all_supported_roles_are_recipient_scoped(inbox, role):
    inbox["owner"].platform_role = role
    inbox["db"].commit()
    assert inbox["client"].get(URL).json()["total"] == 3
    assert inbox["client"].get(URL + "/unread-count").json() == {"unread_count": 3}
    assert inbox["client"].patch(URL + f"/{inbox['foreign_id']}/read").status_code == 404
    assert inbox["client"].patch(URL + f"/{inbox['ids'][0]}/read").status_code == 200
    assert inbox["client"].patch(URL + "/read-all").json() == {"updated_count": 2}
    inbox["db"].expire_all()
    assert inbox["db"].get(Notification, inbox["foreign_id"]).is_read is False


@pytest.mark.parametrize("identity", ["anonymous", "invalid", "inactive"])
@pytest.mark.parametrize("operation", ["list", "count", "one", "all"])
def test_authentication_required(inbox, identity, operation):
    if identity == "anonymous":
        inbox["client"].headers.pop("Authorization")
    elif identity == "invalid":
        inbox["client"].headers["Authorization"] = "Bearer invalid"
    else:
        inbox["owner"].account_status = "suspended"
        inbox["db"].commit()
    method, suffix = {"list": ("get", ""), "count": ("get", "/unread-count"), "one": ("patch", f"/{inbox['ids'][0]}/read"), "all": ("patch", "/read-all")}[operation]
    assert getattr(inbox["client"], method)(URL + suffix).status_code == (403 if identity == "inactive" else 401)


def test_unread_count_and_idempotent_read_timestamp(inbox):
    client = inbox["client"]
    first = client.patch(URL + f"/{inbox['ids'][0]}/read")
    assert first.status_code == 200 and first.json()["is_read"] is True
    assert first.json()["read_at"].endswith("Z")
    row = inbox["db"].get(Notification, inbox["ids"][0])
    row.read_at -= timedelta(days=1)
    inbox["db"].commit()
    second = client.patch(URL + f"/{inbox['ids'][0]}/read")
    assert second.json()["read_at"] != first.json()["read_at"]
    assert client.patch(URL + f"/{inbox['ids'][0]}/read").json() == second.json()
    assert client.get(URL + "/unread-count").json() == {"unread_count": 2}
    assert client.patch(URL + "/read-all").json() == {"updated_count": 2}
    assert client.patch(URL + "/read-all").json() == {"updated_count": 0}
    assert client.get(URL + "/unread-count").json() == {"unread_count": 0}
    auth(inbox, inbox["other_user"])
    assert client.get(URL + "/unread-count").json() == {"unread_count": 1}


def test_pagination_read_filters_and_type_filter(inbox):
    client = inbox["client"]
    client.patch(URL + f"/{inbox['ids'][0]}/read")
    seed(inbox["db"], inbox["owner"].user_id, inbox["business"], kind="credit_sale_recorded")
    inbox["db"].commit()
    data = client.get(URL, params={"page": 2, "page_size": 2}).json()
    assert data["total"] == 4 and data["page"] == 2 and len(data["notifications"]) == 2
    assert client.get(URL, params={"unread_only": True}).json()["total"] == 3
    assert client.get(URL, params={"is_read": True}).json()["total"] == 1
    assert client.get(URL, params={"is_read": False}).json()["total"] == 3
    assert client.get(URL, params={"notification_type": "credit_sale_recorded"}).json()["total"] == 1
    assert client.get(URL, params={"page": 100}).json()["notifications"] == []


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 101}, {"page_size": 0}, {"page": 1000001}, {"notification_type": "bogus"}, {"notification_type": "sms"}, {"is_read": "bogus"}, {"unread_only": True, "is_read": True}, {"business_id": 123}, {"ordering": "user_sql"}])
def test_query_validation(inbox, params):
    assert inbox["client"].get(URL, params=params).status_code == 422


@pytest.mark.parametrize("notification_id,expected", [(0, 422), (-1, 422), ("bad", 422), (9223372036854775808, 422), (9223372036854775807, 404)])
def test_invalid_notification_ids(inbox, notification_id, expected):
    assert inbox["client"].patch(URL + f"/{notification_id}/read").status_code == expected


def test_owned_history_across_businesses_does_not_grant_business_access(inbox):
    seed(inbox["db"], inbox["owner"].user_id, inbox["other_business"])
    inbox["db"].commit()
    assert inbox["client"].get(URL).json()["total"] == 4
    assert inbox["client"].get("/api/v1/shop-owner/customers", params={"business_id": inbox["other_business"]}).status_code == 403
    auth(inbox, inbox["other_user"])
    own = inbox["client"].get(URL).json()
    assert own["total"] == 1 and own["notifications"][0]["notification_id"] == inbox["foreign_id"]


def test_credit_sale_repayment_notify_only_linked_customer_and_replay_once(linked):
    ctx = linked
    key = uuid4().hex
    first = post_sale(ctx, idempotency_key=key)
    assert first.status_code == 201
    assert post_sale(ctx, idempotency_key=key).status_code == 200
    rows = list(ctx["db"].scalars(select(Notification)))
    assert len(rows) == 1
    assert rows[0].recipient_user_id == ctx["linked_user"]
    assert rows[0].notification_type == "credit_sale_recorded"
    assert rows[0].related_entity_id == first.json()["entry_id"]
    assert rows[0].business_id == ctx["business"]
    repayment = {"customer_id": ctx["customer"], "amount": "25.00", "payment_method": "cash", "idempotency_key": uuid4().hex}
    for status in (201, 200):
        assert ctx["client"].post("/api/v1/shop-owner/repayments", params={"business_id": ctx["business"]}, json=repayment).status_code == status
    assert count(ctx["db"]) == 2
    assert details(ctx)["outstanding_balance"] == "75.25"
    before = details(ctx)
    sale_row = next(row for row in rows if row.notification_type == "credit_sale_recorded")
    assert notify_event(ctx["db"], "credit_sale_recorded", sale_row.related_entity_id) == [sale_row.notification_id]
    ctx["db"].commit()
    assert details(ctx) == before
    auth(ctx, ctx["linked_user"])
    response = ctx["client"].get(URL)
    assert response.json()["total"] == 2
    for row in response.json()["notifications"]:
        assert "100.25" not in row["message"] and "25.00" not in row["message"] and "Test credit sale" not in row["message"]
    assert ctx["client"].patch(URL + "/read-all").json() == {"updated_count": 2}
    assert ctx["db"].scalar(select(func.count()).select_from(LedgerEntry)) == 2


@pytest.mark.parametrize("condition", ["unlinked", "inactive_customer", "wrong_role"])
def test_recipient_must_be_explicit_active_customer_link(linked, condition):
    ctx = linked
    if condition == "unlinked":
        ctx["db"].get(CustomerProfile, ctx["customer"]).user_id = None
    elif condition == "inactive_customer":
        ctx["db"].get(User, ctx["linked_user"]).account_status = "suspended"
    else:
        ctx["db"].get(User, ctx["linked_user"]).platform_role = "driver"
    ctx["db"].commit()
    assert post_sale(ctx).status_code == 201
    assert count(ctx["db"]) == 0


def test_duplicate_internal_event_keeps_original_timestamp_and_read_state(linked):
    ctx = linked
    result = post_sale(ctx).json()
    row = ctx["db"].scalar(select(Notification))
    row.is_read = True
    row.read_at = utc_now() - timedelta(days=1)
    row.created_at -= timedelta(days=2)
    ctx["db"].commit()
    original = (row.notification_id, row.created_at, row.read_at)
    notify_event(ctx["db"], "credit_sale_recorded", result["entry_id"])
    notify_event(ctx["db"], "credit_sale_recorded", result["entry_id"])
    ctx["db"].commit()
    ctx["db"].expire_all()
    row = ctx["db"].scalar(select(Notification))
    assert count(ctx["db"]) == 1 and row.is_read is True
    assert (row.notification_id, row.created_at, row.read_at) == original


def test_reminder_notifies_only_other_active_owners_without_customer_delivery(linked):
    ctx = linked
    assert post_sale(ctx).status_code == 201
    coowner = make_user(ctx["db"], "shop_owner")
    outsider = make_user(ctx["db"], "shop_owner")
    inactive = make_user(ctx["db"], "shop_owner")
    for user, business_id, status in [(coowner, ctx["business"], "active"), (outsider, ctx["other_business"], "active"), (inactive, ctx["business"], "inactive")]:
        ctx["db"].add(BusinessMember(user_id=user.user_id, business_id=business_id, business_role="owner", membership_status=status))
    ctx["db"].commit()
    before = details(ctx)
    payload = {"customer_id": ctx["customer"], "idempotency_key": uuid4().hex}
    for status in (201, 200):
        result = ctx["client"].post("/api/v1/shop-owner/payment-reminders", params={"business_id": ctx["business"]}, json=payload)
        assert result.status_code == status
        assert result.json()["delivery_allowed"] is False
    rows = list(ctx["db"].scalars(select(Notification).where(Notification.notification_type == "payment_reminder_recorded")))
    assert len(rows) == 1 and rows[0].recipient_user_id == coowner.user_id
    assert rows[0].recipient_user_id != ctx["linked_user"]
    assert details(ctx) == before
    assert "100.25" not in rows[0].message and "Existing customer" not in rows[0].message


@pytest.mark.parametrize("decision,kind", [("approve", "business_approved"), ("reject", "business_rejected")])
def test_approval_decisions_notify_active_owners_in_same_transaction(inbox, decision, kind):
    ctx = inbox
    ctx["db"].get(Business, ctx["business"]).approval_status = "pending"
    admin = make_user(ctx["db"], "admin")
    ctx["db"].commit()
    auth(ctx, admin.user_id)
    result = ctx["client"].patch(f"/api/v1/admin/businesses/{ctx['business']}/decision", json={"decision": decision, "review_note": "Private reviewer note"})
    assert result.status_code == 200
    assert ctx["client"].patch(f"/api/v1/admin/businesses/{ctx['business']}/decision", json={"decision": decision}).status_code == 409
    rows = list(ctx["db"].scalars(select(Notification).where(Notification.notification_type == kind)))
    assert len(rows) == 1 and rows[0].recipient_user_id == ctx["owner"].user_id
    assert rows[0].related_entity_type == "business_approval_audit"
    assert rows[0].related_entity_id == ctx["db"].scalar(select(BusinessApprovalAudit.audit_id))
    assert "Private reviewer note" not in rows[0].message
    # Administrator has no global inbox privilege.
    assert ctx["client"].get(URL).json()["total"] == 0


@pytest.mark.parametrize("kind", ["credit_sale", "repayment", "reminder"])
def test_failed_event_rolls_back_notifications_and_financial_writes(linked, monkeypatch, kind):
    ctx = linked
    if kind != "credit_sale":
        assert post_sale(ctx).status_code == 201
    if kind == "reminder":
        owner = make_user(ctx["db"], "shop_owner")
        ctx["db"].add(BusinessMember(user_id=owner.user_id, business_id=ctx["business"], business_role="owner", membership_status="active"))
        ctx["db"].commit()
    before = details(ctx)
    old_notifications, old_entries = count(ctx["db"]), count(ctx["db"], LedgerEntry)
    def fail_after_insert(session, event_type, event_id):
        notify_event(session, event_type, event_id)
        raise SQLAlchemyError("private notification SQL diagnostic")
    module = {"credit_sale": shop_owner_credit_sale_service, "repayment": shop_owner_repayment_service, "reminder": shop_owner_reminder_service}[kind]
    monkeypatch.setattr(module, "notify_event", fail_after_insert)
    if kind == "credit_sale":
        result = post_sale(ctx)
    else:
        url = "/api/v1/shop-owner/repayments" if kind == "repayment" else "/api/v1/shop-owner/payment-reminders"
        payload = {"customer_id": ctx["customer"], "idempotency_key": uuid4().hex}
        if kind == "repayment":
            payload.update(amount="10.00", payment_method="cash")
        result = ctx["client"].post(url, params={"business_id": ctx["business"]}, json=payload)
    assert result.status_code == 500 and "private" not in result.text
    assert count(ctx["db"]) == old_notifications
    assert count(ctx["db"], LedgerEntry) == old_entries
    assert count(ctx["db"], PaymentReminder) == 0
    assert details(ctx) == before


def test_failed_validation_and_conflicts_do_not_create_events(linked):
    ctx = linked
    for amount, status in [("0", 422), ("1001", 409)]:
        assert post_sale(ctx, amount=amount).status_code == status
    assert count(ctx["db"]) == count(ctx["db"], LedgerEntry) == 0
    assert post_sale(ctx).status_code == 201
    before = count(ctx["db"])
    assert ctx["client"].post("/api/v1/shop-owner/repayments", params={"business_id": ctx["business"]}, json={"customer_id": ctx["customer"], "amount": "999", "payment_method": "cash", "idempotency_key": uuid4().hex}).status_code == 409
    assert count(ctx["db"]) == before


def test_failed_business_decision_rolls_back_status_audit_and_notification(inbox, monkeypatch):
    ctx = inbox
    ctx["db"].get(Business, ctx["business"]).approval_status = "pending"
    admin = make_user(ctx["db"], "admin")
    ctx["db"].commit()
    before = count(ctx["db"])
    def fail(session, kind, event_id):
        notify_event(session, kind, event_id)
        raise SQLAlchemyError("private SQL diagnostic")
    monkeypatch.setattr(admin_businesses, "notify_event", fail)
    auth(ctx, admin.user_id)
    result = ctx["client"].patch(f"/api/v1/admin/businesses/{ctx['business']}/decision", json={"decision": "approve"})
    assert result.status_code == 500 and "private" not in result.text
    ctx["db"].expire_all()
    assert ctx["db"].get(Business, ctx["business"]).approval_status == "pending"
    assert count(ctx["db"], BusinessApprovalAudit) == 0
    assert count(ctx["db"]) == before


def test_creation_is_internal_and_rejects_false_events(inbox):
    assert inbox["client"].post(URL, json={"recipient_user_id": inbox["other_user"], "title": "fake", "message": "fake"}).status_code == 405
    for kind, entity in [("bogus", 1), ("credit_sale_recorded", True), ("repayment_recorded", -1), ("credit_sale_recorded", 9223372036854775807), ("payment_reminder_recorded", 9223372036854775807), ("business_approved", 9223372036854775807)]:
        with pytest.raises(ValueError):
            notify_event(inbox["db"], kind, entity)
    assert count(inbox["db"]) == 4


@pytest.mark.parametrize("operation", ["list_notifications", "unread_count", "mark_read", "mark_all_read"])
def test_api_database_errors_are_sanitized(inbox, monkeypatch, operation):
    def fail(*args, **kwargs):
        raise SQLAlchemyError("private password SQL detail")
    monkeypatch.setattr(notifications, operation, fail)
    method, suffix = {"list_notifications": ("get", ""), "unread_count": ("get", "/unread-count"), "mark_read": ("patch", f"/{inbox['ids'][0]}/read"), "mark_all_read": ("patch", "/read-all")}[operation]
    result = getattr(inbox["client"], method)(URL + suffix)
    assert result.status_code == 500 and result.json() == {"detail": "Unable to process notifications"}
    assert count(inbox["db"]) == 4


def test_database_constraints_indexes_and_routes(inbox):
    inspector = inspect(engine)
    assert {"recipient_user_id", "event_key"} in [set(row["column_names"]) for row in inspector.get_unique_constraints("notifications")]
    assert {row["referred_table"] for row in inspector.get_foreign_keys("notifications")} == {"users", "businesses"}
    indexes = {row["name"]: row["column_names"] for row in inspector.get_indexes("notifications")}
    assert indexes["ix_notification_recipient_read_created"] == ["recipient_user_id", "is_read", "created_at", "notification_id"]
    assert indexes["ix_notification_recipient_type_created"] == ["recipient_user_id", "notification_type", "created_at", "notification_id"]
    row = inbox["db"].get(Notification, inbox["ids"][0])
    values = {column.name: getattr(row, column.name) for column in Notification.__table__.columns if column.name != "notification_id"}
    with pytest.raises(IntegrityError):
        with inbox["db"].begin_nested():
            inbox["db"].execute(Notification.__table__.insert().values(**values))
    for patch in [{"notification_type": "bogus"}, {"related_entity_type": "url"}, {"is_read": True, "read_at": None}]:
        with pytest.raises((IntegrityError, OperationalError)) as error:
            with inbox["db"].begin_nested():
                inbox["db"].execute(Notification.__table__.insert().values(**{**values, "event_key": uuid4().hex, **patch}))
        assert error.value.orig.args[0] == 3819
    paths = app.openapi()["paths"]
    assert set(paths[URL]) == {"get"}
    assert set(paths[URL + "/read-all"]) == {"patch"}
    assert set(paths[URL + "/{notification_id}/read"]) == {"patch"}
    assert set(paths[URL + "/unread-count"]) == {"get"}
