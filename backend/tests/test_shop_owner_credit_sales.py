"""Credit-sale API validation, real JWT authorization, and ledger consistency."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.models import Business, BusinessMember, CreditAccount, CustomerProfile, LedgerEntry
from app.routers import shop_owner
from app.services.ledger_service import account_balances, load_ledger_entries
from app.services.shop_owner_dashboard_service import get_dashboard_summary
from test_day7_integration import integration_api
from test_shop_owner_dashboard import db, make_business, make_customer_account, make_entry


@pytest.fixture
def sale_api(integration_api):
    ctx = integration_api
    account = CreditAccount(creditor_business_id=ctx["business"], customer_id=ctx["customer"],
                            credit_limit=Decimal("1000.00"), payment_term_days=30, account_status="active")
    ctx["db"].add(account)
    ctx["db"].commit()
    ctx["account"] = account.credit_account_id
    return ctx


def post_sale(ctx, *, business_id=None, **changes):
    payload = {"customer_id": ctx["customer"], "amount": "100.25",
               "notes": "Test credit sale", "idempotency_key": f"sale-{uuid4().hex}"}
    payload.update(changes)
    return ctx["client"].post("/api/v1/shop-owner/credit-sales",
                            params={"business_id": business_id or ctx["business"]}, json=payload)


def details(ctx):
    response = ctx["client"].get(f"/api/v1/shop-owner/customers/{ctx['customer']}",
                                 params={"business_id": ctx["business"]})
    assert response.status_code == 200
    return response.json()


def entry_count(ctx):
    return ctx["db"].scalar(select(func.count()).select_from(LedgerEntry).where(
        LedgerEntry.credit_account_id == ctx["account"]))


def test_valid_sale_persists_and_all_balances_agree(sale_api):
    ctx = sale_api
    response = post_sale(ctx, notes="  Sale notes  ")
    assert response.status_code == 201
    data = response.json()
    assert data["business_id"] == ctx["business"]
    assert data["customer_id"] == ctx["customer"]
    assert data["credit_account_id"] == ctx["account"]
    assert data["amount"] == data["outstanding_balance"] == "100.25"
    assert data["available_credit"] == "899.75"
    assert data["advance_balance"] == "0.00"
    assert data["replayed"] is False
    assert data["currency"] == "LKR"
    entry = ctx["db"].get(LedgerEntry, data["entry_id"])
    assert entry.amount == Decimal("100.25")
    assert entry.created_by == ctx["owner"].user_id
    assert entry.entry_type == "credit_sale"
    assert entry.notes == "Sale notes"
    assert entry.due_at == entry.recorded_at + timedelta(days=30)
    assert entry.receipt_number.startswith("CS-")
    assert data["reference"] == data["receipt_number"] == entry.receipt_number
    ledger = details(ctx)
    assert ledger["transactions"][0]["entry_id"] == data["entry_id"]
    assert ledger["transactions"][0]["running_balance"] == "100.25"
    assert ledger["transactions"][0]["due_at"] == data["due_at"]
    for field in ("outstanding_balance", "available_credit", "advance_balance"):
        assert ledger[field] == data[field]
    listed = ctx["client"].get("/api/v1/shop-owner/customers", params={"business_id": ctx["business"]}).json()["customers"]
    assert next(c for c in listed if c["customer_id"] == ctx["customer"])["outstanding_balance"] == "100.25"
    assert get_dashboard_summary(ctx["db"], ctx["business"])["total_outstanding"] == Decimal("100.25")
    recent = ctx["client"].get("/api/v1/shop-owner/dashboard/recent-transactions", params={"business_id": ctx["business"]}).json()["transactions"]
    assert recent[0]["id"] == data["entry_id"]


@pytest.mark.parametrize("amount", ["0", "-0.01", "1000.001", "1000000000000.00", "NaN", "Infinity", "-Infinity", "abc", None, True])
def test_invalid_amounts(sale_api, amount):
    assert post_sale(sale_api, amount=amount).status_code == 422
    assert entry_count(sale_api) == 0


@pytest.mark.parametrize("changes", [{"idempotency_key": ""}, {"idempotency_key": "x" * 101},
    {"idempotency_key": "white space"}, {"idempotency_key": None}, {"customer_id": 0},
    {"customer_id": True}, {"customer_id": "1"}, {"customer_id": 9223372036854775808},
    {"notes": "x" * 2001}, {"entry_type": "repayment"}, {"receipt_number": "client-receipt"},
    {"credit_limit": "999999"}, {"created_by": 1}, {"due_at": "2030-01-01"}, {"payment_method": "cash"}])
def test_malformed_or_server_controlled_fields_rejected(sale_api, changes):
    assert post_sale(sale_api, **changes).status_code == 422
    assert entry_count(sale_api) == 0


@pytest.mark.parametrize("missing", ["amount", "customer_id", "idempotency_key"])
def test_required_fields(sale_api, missing):
    payload = {"customer_id": sale_api["customer"], "amount": "1", "idempotency_key": "required-test"}
    del payload[missing]
    response = sale_api["client"].post("/api/v1/shop-owner/credit-sales",
        params={"business_id": sale_api["business"]}, json=payload)
    assert response.status_code == 422


def test_exact_limit_and_excess(sale_api):
    assert post_sale(sale_api, amount="1000.01").status_code == 409
    assert entry_count(sale_api) == 0
    response = post_sale(sale_api, amount="1000.00", notes=None)
    assert response.status_code == 201
    assert response.json()["available_credit"] == "0.00"
    assert post_sale(sale_api, amount="0.01").status_code == 409
    assert entry_count(sale_api) == 1


def test_missing_account(integration_api):
    assert post_sale(integration_api).status_code == 404


@pytest.mark.parametrize("status", ["suspended", "closed"])
def test_inactive_account(sale_api, status):
    ctx = sale_api
    ctx["db"].get(CreditAccount, ctx["account"]).account_status = status
    ctx["db"].commit()
    assert post_sale(ctx).status_code == 409
    assert entry_count(ctx) == 0


@pytest.mark.parametrize("condition", ["anonymous", "invalid_token", "customer", "driver", "admin", "inactive_user", "pending", "inactive_member", "unowned"])
def test_authorization(sale_api, condition):
    ctx = sale_api
    business = ctx["business"]
    if condition == "anonymous":
        ctx["client"].headers.pop("Authorization")
    elif condition == "invalid_token":
        ctx["client"].headers["Authorization"] = "Bearer invalid-token"
    elif condition in ("customer", "driver", "admin"):
        ctx["owner"].platform_role = condition
    elif condition == "inactive_user":
        ctx["owner"].account_status = "suspended"
    elif condition == "pending":
        ctx["db"].get(Business, business).approval_status = "pending"
    elif condition == "inactive_member":
        member = ctx["db"].scalar(select(BusinessMember).where(BusinessMember.business_id == business))
        member.membership_status = "inactive"
    else:
        business = ctx["other_business"]
    ctx["db"].commit()
    assert post_sale(ctx, business_id=business).status_code == (401 if condition in ("anonymous", "invalid_token") else 403)
    assert entry_count(ctx) == 0


def test_foreign_or_absent_customer_is_hidden(sale_api):
    for customer_id in (sale_api["other_customer"], 9223372036854775807):
        response = post_sale(sale_api, customer_id=customer_id)
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found in this business"
    assert entry_count(sale_api) == 0


def test_credit_account_must_match_business(sale_api):
    ctx = sale_api
    ctx["db"].get(CreditAccount, ctx["account"]).creditor_business_id = ctx["other_business"]
    ctx["db"].commit()
    assert post_sale(ctx).status_code == 404
    assert entry_count(ctx) == 0


def test_same_key_replays_identical_financial_operation(sale_api):
    key = f"replay-{uuid4().hex}"
    first = post_sale(sale_api, idempotency_key=key, notes="  Same notes  ")
    second = post_sale(sale_api, idempotency_key=key, amount="100.250", notes="Same notes")
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["replayed"] is True
    assert second.json()["entry_id"] == first.json()["entry_id"]
    assert second.json()["receipt_number"] == first.json()["receipt_number"]
    assert second.json()["outstanding_balance"] == "100.25"
    assert entry_count(sale_api) == 1


@pytest.mark.parametrize("changes", [{"amount": "100.26"}, {"notes": "Different notes"}, {"notes": None}])
def test_key_reuse_with_different_details_conflicts(sale_api, changes):
    key = f"conflict-{uuid4().hex}"
    assert post_sale(sale_api, idempotency_key=key).status_code == 201
    assert post_sale(sale_api, idempotency_key=key, **changes).status_code == 409
    assert entry_count(sale_api) == 1


def test_key_cannot_replay_another_account_or_entry_type(sale_api):
    ctx = sale_api
    key = f"foreign-{uuid4().hex}"
    entry_id = make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "repayment", "100.25")
    entry = ctx["db"].get(LedgerEntry, entry_id)
    entry.idempotency_key = key
    entry.notes = "Test credit sale"
    ctx["db"].commit()
    assert post_sale(ctx, idempotency_key=key).status_code == 409
    other_account = CreditAccount(creditor_business_id=ctx["other_business"], customer_id=ctx["other_customer"],
        credit_limit=Decimal("1000"), payment_term_days=30, account_status="active")
    ctx["db"].add(other_account)
    ctx["db"].flush()
    foreign_entry = LedgerEntry(credit_account_id=other_account.credit_account_id, created_by=ctx["owner"].user_id,
        entry_type="credit_sale", amount=Decimal("100.25"), notes="Test credit sale", idempotency_key=f"private-{uuid4().hex}")
    ctx["db"].add(foreign_entry)
    ctx["db"].commit()
    response = post_sale(ctx, idempotency_key=foreign_entry.idempotency_key)
    assert response.status_code == 409
    assert "entry_id" not in response.json()


@pytest.mark.parametrize("scenario,expected", [("partial", "500.00"), ("reversed_sale", "100.00"),
    ("reversed_repayment", "700.00"), ("advance", "0.00")])
def test_historical_entries_and_reversals(sale_api, scenario, expected):
    ctx = sale_api
    account, actor = ctx["account"], ctx["owner"].user_id
    if scenario == "advance":
        make_entry(ctx["db"], actor, account, "repayment", "200")
    else:
        sale = make_entry(ctx["db"], actor, account, "credit_sale", "600")
        repay = make_entry(ctx["db"], actor, account, "repayment", "200")
        if scenario == "reversed_sale":
            make_entry(ctx["db"], actor, account, "reversal", "600", reverses_entry_id=sale)
            # No effective repayment remains, for a fully reversed sale/payment pair.
            make_entry(ctx["db"], actor, account, "reversal", "200", reverses_entry_id=repay)
        elif scenario == "reversed_repayment":
            make_entry(ctx["db"], actor, account, "reversal", "200", reverses_entry_id=repay)
    ctx["db"].commit()
    before = [(e.entry_id, e.entry_type, e.amount, e.reverses_entry_id) for e in load_ledger_entries(ctx["db"], [account])]
    response = post_sale(ctx, amount="100.00")
    assert response.status_code == 201
    data = response.json()
    assert data["outstanding_balance"] == expected
    assert data["advance_balance"] == ("100.00" if scenario == "advance" else "0.00")
    ledger = details(ctx)
    assert ledger["outstanding_balance"] == data["outstanding_balance"]
    assert ledger["available_credit"] == data["available_credit"]
    assert ledger["transactions"][-1]["running_balance"] == ("-100.00" if scenario == "advance" else expected)
    after = [(e.entry_id, e.entry_type, e.amount, e.reverses_entry_id) for e in load_ledger_entries(ctx["db"], [account])]
    assert after[:-1] == before


def test_reversed_repayment_restricts_new_credit(sale_api):
    ctx = sale_api
    actor = ctx["owner"].user_id
    make_entry(ctx["db"], actor, ctx["account"], "credit_sale", "900")
    repayment = make_entry(ctx["db"], actor, ctx["account"], "repayment", "800")
    make_entry(ctx["db"], actor, ctx["account"], "reversal", "800", reverses_entry_id=repayment)
    ctx["db"].commit()
    assert post_sale(ctx, amount="100.01").status_code == 409
    assert post_sale(ctx, amount="100").status_code == 201


def test_advances_do_not_expand_credit_limit(sale_api):
    ctx = sale_api
    make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "repayment", "200")
    ctx["db"].commit()
    assert post_sale(ctx, amount="1000.01").status_code == 409
    assert post_sale(ctx, amount="1000").json()["outstanding_balance"] == "800.00"


def test_replay_after_account_suspension_and_reversal_is_not_new_sale(sale_api):
    ctx = sale_api
    key = f"historical-{uuid4().hex}"
    first = post_sale(ctx, idempotency_key=key).json()
    make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "reversal", "100.25", reverses_entry_id=first["entry_id"])
    ctx["db"].get(CreditAccount, ctx["account"]).account_status = "suspended"
    ctx["db"].commit()
    replay = post_sale(ctx, idempotency_key=key)
    assert replay.status_code == 200
    assert replay.json()["entry_id"] == first["entry_id"]
    assert replay.json()["outstanding_balance"] == "0.00"
    assert entry_count(ctx) == 2


def test_database_failure_rolls_back_flushed_sale(sale_api, monkeypatch):
    original = shop_owner.record_credit_sale
    def fail_after_flush(*args):
        original(*args)
        raise SQLAlchemyError("private database diagnostic")
    monkeypatch.setattr(shop_owner, "record_credit_sale", fail_after_flush)
    response = post_sale(sale_api)
    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to record credit sale"
    assert "private" not in response.text
    assert entry_count(sale_api) == 0
    assert details(sale_api)["outstanding_balance"] == "0.00"


def test_due_date_overflow_rolls_back(sale_api):
    ctx = sale_api
    ctx["db"].get(CreditAccount, ctx["account"]).payment_term_days = 2147483647
    ctx["db"].commit()
    assert post_sale(ctx).status_code == 422
    assert entry_count(ctx) == 0


def test_sale_route_is_registered_once():
    routes = [route for route in shop_owner.router.routes if getattr(route, "path", "") == "/shop-owner/credit-sales" and "POST" in route.methods]
    assert len(routes) == 1
