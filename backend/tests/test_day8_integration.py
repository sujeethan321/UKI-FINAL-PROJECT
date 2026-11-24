"""Day 8 API lifecycle: one ledger, consistent views and DB reversal integrity."""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import LedgerEntry
from test_day7_integration import integration_api
from test_shop_owner_dashboard import db, make_entry
from test_shop_owner_credit_sales import sale_api, post_sale, details
from test_shop_owner_repayments import repay


def get(ctx, path, **params):
    response = ctx["client"].get('/api/v1/shop-owner/' + path, params={"business_id": ctx["business"], **params})
    assert response.status_code == 200, response.text
    return response.json()


def consistent_position(ctx, debt, available):
    position = details(ctx)
    assert Decimal(position["outstanding_balance"]) == Decimal(debt)
    assert Decimal(position["available_credit"]) == Decimal(available)
    listed = get(ctx, "customers")["customers"]
    assert Decimal(next(row for row in listed if row["customer_id"] == ctx["customer"])["outstanding_balance"]) == Decimal(debt)
    outstanding = get(ctx, "outstanding-payments")
    assert Decimal(outstanding["total_outstanding"]) == Decimal(debt)
    row = next(row for row in outstanding["customers"] if row["customer_id"] == ctx["customer"])
    assert Decimal(row["available_credit"]) == Decimal(available)
    assert outstanding["overdue_amount"] is None
    assert Decimal(str(get(ctx, "dashboard/summary")["total_outstanding"])) == Decimal(debt)
    statement = get(ctx, f"customers/{ctx['customer']}/statement", start_date="1000-01-01", end_date="9999-12-30")
    assert Decimal(statement["opening_balance"]) == Decimal("0.00")
    assert Decimal(statement["closing_balance"]) == Decimal(debt)
    assert Decimal(statement["outstanding_balance"]) == Decimal(debt)
    return statement


def test_sale_to_settlement_receipts_retries_and_cross_api_balances(sale_api):
    ctx = sale_api
    sale_key, partial_key, full_key = [f"day8-{uuid4().hex}" for _ in range(3)]
    sale = post_sale(ctx, amount="600.30", idempotency_key=sale_key)
    assert sale.status_code == 201
    consistent_position(ctx, "600.30", "399.70")
    retry = post_sale(ctx, amount="600.30", idempotency_key=sale_key)
    assert retry.status_code == 200 and retry.json()["entry_id"] == sale.json()["entry_id"]
    assert post_sale(ctx, amount="399.71").status_code == 409
    partial = repay(ctx, amount="100.10", idempotency_key=partial_key)
    assert partial.status_code == 201
    consistent_position(ctx, "500.20", "499.80")
    retry = repay(ctx, amount="100.10", idempotency_key=partial_key)
    assert retry.status_code == 200 and retry.json()["entry_id"] == partial.json()["entry_id"]
    assert repay(ctx, amount="100.11", idempotency_key=partial_key).status_code == 409
    full = repay(ctx, amount="500.20", payment_method="bank_transfer", idempotency_key=full_key)
    assert full.status_code == 201
    statement = consistent_position(ctx, "0.00", "1000.00")
    assert statement["total_credit_sales"] == statement["total_repayments"] == "600.30"
    assert repay(ctx, amount="0.01").status_code == 409
    ids = [row["entry_id"] for row in statement["transactions"]]
    assert ids == [sale.json()["entry_id"], partial.json()["entry_id"], full.json()["entry_id"]]
    receipts = [get(ctx, f"repayments/{row.json()['entry_id']}/receipt") for row in [partial, full]]
    assert len({row["receipt_identifier"] for row in receipts}) == len({row["receipt_number"] for row in receipts}) == 2
    assert [row["amount"] for row in receipts] == ["100.10", "500.20"]
    assert all(row["status"] == "recorded" for row in receipts)
    assert post_sale(ctx, amount="600.30", idempotency_key=sale_key).json()["outstanding_balance"] == "0.00"
    assert ctx["db"].scalar(select(func.count()).select_from(LedgerEntry).where(LedgerEntry.credit_account_id == ctx["account"])) == 3


def test_reversals_restore_debt_preserve_audit_and_reject_duplicates(sale_api):
    ctx = sale_api
    sale = post_sale(ctx, amount="600.30").json()
    partial = repay(ctx, amount="100.10").json()
    full = repay(ctx, amount="500.20").json()
    originals = {row.entry_id: (row.entry_type, row.amount, row.receipt_number) for row in ctx["db"].scalars(select(LedgerEntry).where(LedgerEntry.credit_account_id == ctx["account"]))}
    reversal = make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "reversal", "500.20", full["entry_id"])
    ctx["db"].commit()
    consistent_position(ctx, "500.20", "499.80")
    with pytest.raises(IntegrityError):
        with ctx["db"].begin_nested():
            make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "reversal", "500.20", full["entry_id"])
    ctx["db"].commit()
    consistent_position(ctx, "500.20", "499.80")
    receipt = get(ctx, f"repayments/{full['entry_id']}/receipt")
    assert receipt["status"] == "reversed" and receipt["reversal_entry_id"] == reversal
    make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "reversal", "100.10", partial["entry_id"])
    ctx["db"].commit(); consistent_position(ctx, "600.30", "399.70")
    make_entry(ctx["db"], ctx["owner"].user_id, ctx["account"], "reversal", "600.30", sale["entry_id"])
    ctx["db"].commit(); statement = consistent_position(ctx, "0.00", "1000.00")
    assert len(statement["transactions"]) == 6
    assert len([row for row in statement["transactions"] if row["entry_type"] == "reversal"]) == 3
    for entry_id, original in originals.items():
        entry = ctx["db"].get(LedgerEntry, entry_id)
        assert (entry.entry_type, entry.amount, entry.receipt_number) == original
