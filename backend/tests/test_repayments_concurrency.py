"""Actual independent MySQL sessions for repayment and mixed-writer races."""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models import BusinessMember, LedgerEntry
from app.services.ledger_service import ZERO, account_balances, load_ledger_entries
from test_credit_sales_concurrency import committed_sales, race_requests

REPAYMENTS = "/api/v1/shop-owner/repayments"
SALES = "/api/v1/shop-owner/credit-sales"


@pytest.fixture
def repayment_race(committed_sales, request):
    ctx = committed_sales
    amount = Decimal(getattr(request, "param", "1000.00"))
    # Seed visibility requires commit for real independent request connections.
    # The reused committed_sales fixture cleans only its own exact record IDs.
    with Session(engine) as session:
        # Use the authenticated fixture user from its membership without
        # accessing any unrelated database row.
        user_id = session.scalar(select(BusinessMember.user_id).where(BusinessMember.business_id == ctx["business"]))
        for account_id in ctx["accounts"]:
            session.add(LedgerEntry(credit_account_id=account_id, created_by=user_id,
                entry_type="credit_sale", amount=amount,
                idempotency_key=f"repayment-seed-{uuid4().hex}", receipt_number=f"SEED-{uuid4().hex}"))
        session.commit()
    return ctx


def repayment_payload(ctx, amount="600.00", key=None, customer=None, **changes):
    return {"customer_id": customer or ctx["customers"][0], "amount": amount,
            "payment_method": "cash", "idempotency_key": key or f"repayment-race-{uuid4().hex}", **changes}


def assert_financial_state(ctx, expected_repayments, expected_balance):
    with Session(engine) as session:
        entries = load_ledger_entries(session, ctx["accounts"])
        repayments = [entry for entry in entries if entry.entry_type == "repayment"]
        assert len(repayments) == expected_repayments
        balances = account_balances(entries)
        assert balances.get(ctx["accounts"][0], ZERO) == Decimal(expected_balance)
        assert all(balance >= ZERO for balance in balances.values())
        assert all(balance <= Decimal("1000.00") for balance in balances.values())


def test_jointly_excessive_repayments_serialize(repayment_race):
    ctx = repayment_race
    payloads = [repayment_payload(ctx) for _ in range(2)]
    responses = race_requests(ctx, payloads, paths=[REPAYMENTS, REPAYMENTS])
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert_financial_state(ctx, 1, "400.00")


def test_concurrent_identical_full_payment_is_replayed_once(repayment_race):
    ctx = repayment_race
    payload = repayment_payload(ctx, "1000.00")
    responses = race_requests(ctx, [payload, payload], paths=[REPAYMENTS, REPAYMENTS])
    assert sorted(response.status_code for response in responses) == [200, 201]
    assert responses[0].json()["entry_id"] == responses[1].json()["entry_id"]
    assert responses[0].json()["receipt_number"] == responses[1].json()["receipt_number"]
    assert responses[0].json()["outstanding_balance"] == responses[1].json()["outstanding_balance"] == "0.00"
    assert_financial_state(ctx, 1, "0.00")


def test_same_key_changed_method_under_concurrency_conflicts(repayment_race):
    ctx = repayment_race
    key = f"method-race-{uuid4().hex}"
    payloads = [repayment_payload(ctx, "100.10", key=key, payment_method=method) for method in ("cash", "card")]
    responses = race_requests(ctx, payloads, paths=[REPAYMENTS, REPAYMENTS])
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert_financial_state(ctx, 1, "899.90")


def test_global_key_uniqueness_across_accounts_is_database_enforced(repayment_race):
    ctx = repayment_race
    key = f"global-repayment-{uuid4().hex}"
    payloads = [repayment_payload(ctx, "100.10", key=key, customer=customer) for customer in ctx["customers"]]
    responses = race_requests(ctx, payloads, paths=[REPAYMENTS, REPAYMENTS])
    assert sorted(response.status_code for response in responses) == [201, 409]
    with Session(engine) as session:
        matches = session.scalars(select(LedgerEntry).where(LedgerEntry.idempotency_key == key)).all()
        assert len(matches) == 1
        assert matches[0].entry_type == "repayment"
        assert matches[0].amount == Decimal("100.10")


def test_receipt_uniqueness_across_accounts_is_database_enforced(repayment_race):
    ctx = repayment_race
    reference = f"BANK-{uuid4().hex}"
    payloads = [repayment_payload(ctx, "100.10", customer=customer, receipt_number=reference) for customer in ctx["customers"]]
    responses = race_requests(ctx, payloads, paths=[REPAYMENTS, REPAYMENTS])
    assert sorted(response.status_code for response in responses) == [201, 409]
    with Session(engine) as session:
        matches = session.scalars(select(LedgerEntry).where(LedgerEntry.receipt_number == reference)).all()
        assert len(matches) == 1
        assert matches[0].amount == Decimal("100.10")


def test_sale_and_repayment_share_account_lock_and_current_balance(repayment_race):
    ctx = repayment_race
    sale = {"customer_id": ctx["customers"][0], "amount": "500.00", "idempotency_key": f"mixed-sale-{uuid4().hex}"}
    payment = repayment_payload(ctx, "600.00")
    responses = race_requests(ctx, [sale, payment], paths=[SALES, REPAYMENTS])
    assert responses[1].status_code == 201
    assert responses[0].status_code in (201, 409)
    expected_balance = "900.00" if responses[0].status_code == 201 else "400.00"
    assert_financial_state(ctx, 1, expected_balance)


@pytest.mark.parametrize("repayment_race", ["500.00"], indirect=True)
def test_sale_repayment_same_global_key_cannot_cross_replay_namespaces(repayment_race):
    ctx = repayment_race
    key = f"cross-type-race-{uuid4().hex}"
    sale = {"customer_id": ctx["customers"][0], "amount": "100.00", "idempotency_key": key}
    payment = repayment_payload(ctx, "100.00", key=key)
    responses = race_requests(ctx, [sale, payment], paths=[SALES, REPAYMENTS])
    assert sorted(response.status_code for response in responses) == [201, 409]
    with Session(engine) as session:
        matches = session.scalars(select(LedgerEntry).where(LedgerEntry.idempotency_key == key)).all()
        assert len(matches) == 1
        entry = matches[0]
        balances = account_balances(load_ledger_entries(session, ctx["accounts"]))
        assert balances[ctx["accounts"][0]] == (Decimal("600.00") if entry.entry_type == "credit_sale" else Decimal("400.00"))
