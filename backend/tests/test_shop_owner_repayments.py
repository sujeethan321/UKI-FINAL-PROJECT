"""Repayment contract, manual methods, financial policy, and real JWT security."""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.models import Business, BusinessMember, CreditAccount, CustomerProfile, LedgerEntry
from app.routers import shop_owner
from app.services.ledger_service import load_ledger_entries
from app.services.shop_owner_dashboard_service import get_dashboard_summary
from test_day7_integration import integration_api
from test_shop_owner_dashboard import db, make_entry
from test_shop_owner_credit_sales import sale_api, post_sale, details, entry_count


@pytest.fixture
def repayment_api(sale_api):
    ctx = sale_api
    response = post_sale(ctx, amount="600.30")
    assert response.status_code == 201
    ctx["sale_entry"] = response.json()["entry_id"]
    return ctx


def repay(ctx, *, business_id=None, **changes):
    payload = {"customer_id": ctx["customer"], "amount": "100.10", "payment_method": "cash",
               "notes": "Manual repayment", "idempotency_key": f"repayment-{uuid4().hex}"}
    payload.update(changes)
    return ctx["client"].post("/api/v1/shop-owner/repayments",
                             params={"business_id": business_id or ctx["business"]}, json=payload)


def snapshot(ctx):
    return [(entry.entry_id, entry.entry_type, entry.amount, entry.reverses_entry_id,
             entry.notes, entry.payment_method, entry.receipt_number, entry.recorded_at, entry.due_at)
            for entry in load_ledger_entries(ctx["db"], [ctx["account"]])]


def test_partial_repayment_persists_and_preserves_history(repayment_api):
    ctx = repayment_api
    before = snapshot(ctx)
    response = repay(ctx, notes="  Manual repayment  ")
    assert response.status_code == 201
    data = response.json()
    assert data["business_id"] == ctx["business"]
    assert data["customer_id"] == ctx["customer"]
    assert data["credit_account_id"] == ctx["account"]
    assert data["amount"] == "100.10"
    assert data["payment_method"] == "cash"
    assert data["outstanding_balance"] == "500.20"
    assert data["available_credit"] == "499.80"
    assert data["advance_balance"] == "0.00"
    assert data["replayed"] is False
    assert data["currency"] == "LKR"
    assert data["reference"] == data["receipt_number"]
    assert data["receipt_number"].startswith("RP-")
    assert data["due_at"] is None
    entry = ctx["db"].get(LedgerEntry, data["entry_id"])
    assert entry.amount == Decimal("100.10")
    assert entry.entry_type == "repayment"
    assert entry.payment_method == "cash"
    assert entry.created_by == ctx["owner"].user_id
    assert entry.notes == "Manual repayment"
    assert entry.recorded_at.isoformat() == data["recorded_at"]
    assert snapshot(ctx)[:-1] == before
    account = ctx["db"].get(CreditAccount, ctx["account"])
    assert account.credit_limit == Decimal("1000.00")
    assert account.account_status == "active"
    ledger = details(ctx)
    for field in ("outstanding_balance", "available_credit", "advance_balance"):
        assert ledger[field] == data[field]
    assert ledger["transactions"][-1]["entry_id"] == data["entry_id"]
    assert ledger["transactions"][-1]["credit"] == "100.10"
    assert ledger["transactions"][-1]["running_balance"] == "500.20"
    listed = ctx["client"].get("/api/v1/shop-owner/customers", params={"business_id": ctx["business"]}).json()["customers"]
    assert next(c for c in listed if c["customer_id"] == ctx["customer"])["outstanding_balance"] == "500.20"
    assert get_dashboard_summary(ctx["db"], ctx["business"])["total_outstanding"] == Decimal("500.20")
    recent = ctx["client"].get("/api/v1/shop-owner/dashboard/recent-transactions", params={"business_id": ctx["business"]}).json()["transactions"]
    assert recent[0]["id"] == data["entry_id"]
    assert recent[0]["type"] == "repayment"
    assert "verified" not in data


def test_full_repayment_does_not_close_account(repayment_api):
    response = repay(repayment_api, amount="600.30", notes=None)
    assert response.status_code == 201
    assert response.json()["outstanding_balance"] == "0.00"
    assert response.json()["available_credit"] == "1000.00"
    assert repayment_api["db"].get(CreditAccount, repayment_api["account"]).account_status == "active"
    assert repay(repayment_api, amount="0.01").status_code == 409


@pytest.mark.parametrize("method", ["cash", "bank_transfer", "card", " CASH ", "BANK_TRANSFER"])
def test_approved_manual_payment_methods(repayment_api, method):
    response = repay(repayment_api, payment_method=method)
    assert response.status_code == 201
    assert response.json()["payment_method"] == method.strip().lower()


@pytest.mark.parametrize("method", ["crypto", "cheque", "bank transfer", "", "x" * 31, None, 1, True])
def test_unsupported_payment_methods(repayment_api, method):
    assert repay(repayment_api, payment_method=method).status_code == 422
    assert entry_count(repayment_api) == 1


@pytest.mark.parametrize("amount", ["0", "-0.01", "1.001", "1000000000000.00", "NaN", "Infinity", "abc", None, True])
def test_invalid_repayment_amount(repayment_api, amount):
    assert repay(repayment_api, amount=amount).status_code == 422
    assert entry_count(repayment_api) == 1


def test_overpayment_is_rejected_without_any_entry(repayment_api):
    before = snapshot(repayment_api)
    assert repay(repayment_api, amount="600.31").status_code == 409
    assert snapshot(repayment_api) == before


def test_no_debt_or_legacy_advance_cannot_receive_new_repayment(sale_api):
    assert repay(sale_api).status_code == 409
    make_entry(sale_api["db"], sale_api["owner"].user_id, sale_api["account"], "repayment", "20")
    sale_api["db"].commit()
    assert repay(sale_api).status_code == 409
    assert details(sale_api)["advance_balance"] == "20.00"
    assert entry_count(sale_api) == 1


@pytest.mark.parametrize("status,expected", [("active", 201), ("suspended", 201), ("closed", 409), ("unknown", 409)])
def test_account_status_policy(repayment_api, status, expected):
    ctx = repayment_api
    ctx["db"].get(CreditAccount, ctx["account"]).account_status = status
    ctx["db"].commit()
    response = repay(ctx, amount="600.30")
    assert response.status_code == expected
    ctx["db"].expire_all()
    assert ctx["db"].get(CreditAccount, ctx["account"]).account_status == status


@pytest.mark.parametrize("condition", ["anonymous", "invalid_token", "customer", "driver", "admin", "inactive_user", "pending", "inactive_member", "unowned"])
def test_repayment_authorization(repayment_api, condition):
    ctx = repayment_api
    business_id = ctx["business"]
    if condition == "anonymous":
        ctx["client"].headers.pop("Authorization")
    elif condition == "invalid_token":
        ctx["client"].headers["Authorization"] = "Bearer invalid-token"
    elif condition in ("customer", "driver", "admin"):
        ctx["owner"].platform_role = condition
    elif condition == "inactive_user":
        ctx["owner"].account_status = "suspended"
    elif condition == "pending":
        ctx["db"].get(Business, business_id).approval_status = "pending"
    elif condition == "inactive_member":
        member = ctx["db"].scalar(select(BusinessMember).where(BusinessMember.business_id == business_id))
        member.membership_status = "inactive"
    else:
        business_id = ctx["other_business"]
    ctx["db"].commit()
    assert repay(ctx, business_id=business_id).status_code == (401 if condition in ("anonymous", "invalid_token") else 403)
    assert entry_count(ctx) == 1


def test_missing_or_foreign_customer_hidden(repayment_api):
    ctx = repayment_api
    for customer_id in (ctx["other_customer"], 9223372036854775807):
        response = repay(ctx, customer_id=customer_id)
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found in this business"
    assert entry_count(ctx) == 1


def test_missing_account(integration_api):
    assert repay(integration_api).status_code == 404


def test_account_cannot_belong_to_another_business(repayment_api):
    ctx = repayment_api
    ctx["db"].get(CreditAccount, ctx["account"]).creditor_business_id = ctx["other_business"]
    ctx["db"].commit()
    assert repay(ctx).status_code == 404
    assert entry_count(ctx) == 1


@pytest.mark.parametrize("changes", [{"customer_id": 0}, {"customer_id": True}, {"customer_id": "1"},
    {"idempotency_key": ""}, {"idempotency_key": " "}, {"idempotency_key": "x" * 101},
    {"notes": "x" * 2001}, {"receipt_number": "x" * 61}, {"receipt_number": "RP-reserved"},
    {"receipt_number": "cs-reserved"}, {"receipt_number": "bad\nreference"}, {"receipt_number": 123},
    {"entry_type": "credit_sale"}, {"created_by": 1}, {"due_at": "2030-01-01"}, {"transaction_reference": "unmapped-field"}])
def test_malformed_fields(repayment_api, changes):
    assert repay(repayment_api, **changes).status_code == 422
    assert entry_count(repayment_api) == 1


@pytest.mark.parametrize("missing", ["customer_id", "amount", "payment_method", "idempotency_key"])
def test_required_fields(repayment_api, missing):
    ctx = repayment_api
    payload = {"customer_id": ctx["customer"], "amount": "1.00", "payment_method": "cash", "idempotency_key": f"required-{uuid4().hex}"}
    del payload[missing]
    response = ctx["client"].post("/api/v1/shop-owner/repayments", params={"business_id": ctx["business"]}, json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize("reference", [None, "", "   ", " BANK-TEST-001 "])
def test_optional_reference_maps_to_existing_receipt_field(repayment_api, reference):
    response = repay(repayment_api, receipt_number=reference)
    assert response.status_code == 201
    receipt = response.json()["receipt_number"]
    if reference and reference.strip():
        assert receipt == reference.strip()
    else:
        assert receipt.startswith("RP-")
    assert response.json()["reference"] == receipt


def test_identical_retry_returns_original_receipt_and_no_second_payment(repayment_api):
    key = f"replay-{uuid4().hex}"
    first = repay(repayment_api, idempotency_key=key, notes="  Manual repayment  ")
    second = repay(repayment_api, idempotency_key=key, amount="100.100", payment_method=" CASH ")
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["replayed"] is True
    assert first.json()["entry_id"] == second.json()["entry_id"]
    assert first.json()["receipt_number"] == second.json()["receipt_number"]
    assert first.json()["recorded_at"] == second.json()["recorded_at"]
    assert second.json()["outstanding_balance"] == "500.20"
    assert entry_count(repayment_api) == 2


@pytest.mark.parametrize("changes", [{"amount": "100.11"}, {"payment_method": "card"},
    {"notes": None}, {"notes": "Changed"}, {"receipt_number": "OTHER-REFERENCE"}])
def test_changed_payload_conflicts(repayment_api, changes):
    key = f"different-{uuid4().hex}"
    assert repay(repayment_api, idempotency_key=key).status_code == 201
    assert repay(repayment_api, idempotency_key=key, **changes).status_code == 409
    assert entry_count(repayment_api) == 2


def test_explicit_reference_retry_and_reference_removal_conflict(repayment_api):
    ctx = repayment_api
    key = f"reference-{uuid4().hex}"
    assert repay(ctx, idempotency_key=key, receipt_number="BANK-001").status_code == 201
    assert repay(ctx, idempotency_key=key, receipt_number=" BANK-001 ").status_code == 200
    assert repay(ctx, idempotency_key=key).status_code == 409
    assert entry_count(ctx) == 2


def test_duplicate_receipt_reference_has_no_partial_payment(repayment_api):
    assert repay(repayment_api, receipt_number="BANK-UNIQUE").status_code == 201
    assert repay(repayment_api, receipt_number="BANK-UNIQUE").status_code == 409
    assert entry_count(repayment_api) == 2
    assert details(repayment_api)["outstanding_balance"] == "500.20"


def test_cross_type_idempotency_keys_never_replay_other_financial_operations(repayment_api):
    ctx = repayment_api
    sale = ctx["db"].get(LedgerEntry, ctx["sale_entry"])
    assert repay(ctx, idempotency_key=sale.idempotency_key, amount="600.30", notes="Test credit sale").status_code == 409
    key = f"repay-type-{uuid4().hex}"
    assert repay(ctx, idempotency_key=key).status_code == 201
    assert post_sale(ctx, idempotency_key=key, amount="100.10", notes="Manual repayment").status_code == 409
    assert entry_count(ctx) == 2


def test_other_account_key_is_conflict_without_financial_disclosure(repayment_api):
    ctx = repayment_api
    other = CreditAccount(creditor_business_id=ctx["other_business"], customer_id=ctx["other_customer"],
                          credit_limit=Decimal("1000"), payment_term_days=30, account_status="active")
    ctx["db"].add(other)
    ctx["db"].flush()
    key = f"private-{uuid4().hex}"
    ctx["db"].add(LedgerEntry(credit_account_id=other.credit_account_id, created_by=ctx["owner"].user_id,
        entry_type="repayment", amount=Decimal("100.10"), payment_method="cash", notes="Manual repayment",
        receipt_number="RP-private-test", idempotency_key=key))
    ctx["db"].commit()
    response = repay(ctx, idempotency_key=key)
    assert response.status_code == 409
    assert "entry_id" not in response.json()
    assert "private-test" not in response.text
    assert entry_count(ctx) == 1


def test_reversed_sale_reduces_repayable_balance(repayment_api):
    ctx = repayment_api
    make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "reversal", "600.30", reverses_entry_id=ctx["sale_entry"])
    ctx["db"].commit()
    before = snapshot(ctx)
    assert repay(ctx, amount="0.01").status_code == 409
    assert snapshot(ctx) == before
    assert details(ctx)["outstanding_balance"] == "0.00"


def test_reversed_repayment_restores_repayable_balance(repayment_api):
    ctx = repayment_api
    first = repay(ctx, amount="200.10")
    assert first.status_code == 201
    make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "reversal", "200.10", reverses_entry_id=first.json()["entry_id"])
    ctx["db"].commit()
    before = snapshot(ctx)
    second = repay(ctx, amount="600.30")
    assert second.status_code == 201
    assert second.json()["outstanding_balance"] == "0.00"
    assert snapshot(ctx)[:-1] == before
    assert details(ctx)["transactions"][-1]["running_balance"] == "0.00"


def test_replay_after_full_settlement_and_closure_is_confirmation_only(repayment_api):
    ctx = repayment_api
    key = f"settled-{uuid4().hex}"
    first = repay(ctx, amount="600.30", idempotency_key=key)
    assert first.status_code == 201
    ctx["db"].get(CreditAccount, ctx["account"]).account_status = "closed"
    ctx["db"].commit()
    replay = repay(ctx, amount="600.30", idempotency_key=key)
    assert replay.status_code == 200
    assert replay.json()["entry_id"] == first.json()["entry_id"]
    assert replay.json()["outstanding_balance"] == "0.00"
    assert entry_count(ctx) == 2


def test_replay_of_reversed_repayment_never_reapplies_it(repayment_api):
    ctx = repayment_api
    key = f"reversed-{uuid4().hex}"
    first = repay(ctx, idempotency_key=key)
    make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "reversal", "100.10", reverses_entry_id=first.json()["entry_id"])
    ctx["db"].commit()
    replay = repay(ctx, idempotency_key=key)
    assert replay.status_code == 200
    assert replay.json()["outstanding_balance"] == "600.30"
    assert entry_count(ctx) == 3


def test_repayment_frees_credit_for_next_sale(repayment_api):
    ctx = repayment_api
    assert repay(ctx, amount="200.10").status_code == 201
    sale = post_sale(ctx, amount="599.80")
    assert sale.status_code == 201
    assert sale.json()["outstanding_balance"] == "1000.00"
    assert sale.json()["available_credit"] == "0.00"
    assert details(ctx)["outstanding_balance"] == "1000.00"


def test_database_failure_after_flush_rolls_back_payment(repayment_api, monkeypatch):
    original = shop_owner.record_repayment
    before = snapshot(repayment_api)
    def fail_after_write(*args):
        original(*args)
        raise SQLAlchemyError("private database credentials and SQL diagnostics")
    monkeypatch.setattr(shop_owner, "record_repayment", fail_after_write)
    response = repay(repayment_api)
    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to record repayment"
    assert "private" not in response.text
    assert snapshot(repayment_api) == before
    assert details(repayment_api)["outstanding_balance"] == "600.30"


def test_repayment_route_and_schema_registered_once():
    routes = [route for route in shop_owner.router.routes if getattr(route, "path", "") == "/shop-owner/repayments" and "POST" in route.methods]
    assert len(routes) == 1
    assert routes[0].response_model.__name__ == "RepaymentResponse"
