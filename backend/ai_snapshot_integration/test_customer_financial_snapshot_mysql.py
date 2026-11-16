"""Rollback-isolated live contracts for the dedicated AI snapshot schema only."""
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models import Business, CreditAccount, CustomerProfile, LedgerEntry, User
from app.services.customer_financial_snapshot_service import (
    CustomerFinancialSnapshotService, SQLAlchemyCustomerFinancialSnapshotRepository,
)


def user(db, status="active"):
    row = User(full_name="AI snapshot fixture", phone=None,
               email=f"ai-snapshot-{uuid4().hex}@example.invalid",
               password_hash="not-a-login-secret", platform_role="customer",
               preferred_language="ta", account_status=status)
    db.add(row); db.flush(); return row


def business(db, status="approved"):
    row = Business(business_name="AI snapshot fixture", business_type="retail",
                   registration_number=uuid4().hex, approval_status=status)
    db.add(row); db.flush(); return row


def account(db, customer, shop, status="active", creditor=None):
    profile = CustomerProfile(business_id=shop.business_id, user_id=customer.user_id,
                              customer_name="Synthetic", phone=None, address=None)
    db.add(profile); db.flush()
    row = CreditAccount(creditor_business_id=(creditor or shop).business_id,
                        customer_id=profile.customer_id, credit_limit=Decimal("1000.00"),
                        payment_term_days=30, account_status=status)
    db.add(row); db.flush(); return row


def ledger(db, creator, target, kind, amount, reversed_id=None, recorded_at=None):
    row = LedgerEntry(credit_account_id=target.credit_account_id,
                      created_by=creator.user_id, entry_type=kind,
                      amount=Decimal(amount), reverses_entry_id=reversed_id,
                      idempotency_key=uuid4().hex,
                      recorded_at=recorded_at or datetime.now(timezone.utc).replace(tzinfo=None))
    db.add(row); db.flush(); return row


def assemble(db, customer, target):
    return CustomerFinancialSnapshotService(
        SQLAlchemyCustomerFinancialSnapshotRepository(db),
        clock=lambda: datetime(2026, 11, 14, tzinfo=timezone.utc),
    ).assemble(customer.user_id, target.credit_account_id)


def fingerprint(db):
    counts = tuple(db.scalar(select(func.count()).select_from(model))
                   for model in (User, Business, CustomerProfile, CreditAccount, LedgerEntry))
    accounts = list(db.execute(select(
        CreditAccount.credit_account_id, CreditAccount.creditor_business_id,
        CreditAccount.customer_id, CreditAccount.credit_limit, CreditAccount.account_status,
    ).order_by(CreditAccount.credit_account_id)))
    ledger_rows = list(db.execute(select(
        LedgerEntry.entry_id, LedgerEntry.credit_account_id, LedgerEntry.entry_type,
        LedgerEntry.amount, LedgerEntry.reverses_entry_id, LedgerEntry.recorded_at,
    ).order_by(LedgerEntry.entry_id)))
    digest = sha256(repr((accounts, ledger_rows)).encode("utf-8")).hexdigest()
    return counts, digest


def test_authorization_current_position_reversals_and_no_writes(db):
    customer, other = user(db), user(db)
    shop = business(db)
    target = account(db, customer, shop)
    sale = ledger(db, customer, target, "credit_sale", "100.20")
    payment = ledger(db, customer, target, "repayment", "30.10")
    before = fingerprint(db)
    result = assemble(db, customer, target)
    assert (result.total_credit_purchases, result.total_repayments,
            result.outstanding_balance) == (Decimal("100.20"), Decimal("30.10"), Decimal("70.10"))
    assert fingerprint(db) == before and not db.new and not db.dirty and not db.deleted
    with pytest.raises(HTTPException) as denied:
        assemble(db, other, target)
    assert denied.value.status_code == 404
    ledger(db, customer, target, "reversal", "1.00", sale.entry_id)
    result = assemble(db, customer, target)
    assert result.total_credit_purchases == Decimal("0.00")
    assert result.total_repayments == Decimal("30.10")
    assert result.outstanding_balance == Decimal("0.00")
    ledger(db, customer, target, "reversal", "1.00", payment.entry_id)
    result = assemble(db, customer, target)
    assert result.total_repayments == Decimal("0.00") and result.outstanding_balance == Decimal("0.00")


def test_inactive_missing_cross_business_malformed_and_precision(db):
    customer, inactive = user(db), user(db, "suspended")
    first, second = business(db), business(db)
    active = account(db, customer, first)
    # Lifetime snapshot includes both old and current activity; it is not a
    # selectable statement-period projection.
    ledger(db, customer, active, "credit_sale", "0.10",
           recorded_at=datetime(2020, 1, 1))
    ledger(db, customer, active, "credit_sale", "0.20")
    ledger(db, customer, active, "repayment", "0.40")
    result = assemble(db, customer, active)
    assert result.total_credit_purchases == Decimal("0.30")
    assert result.total_repayments == Decimal("0.40") and result.outstanding_balance == Decimal("0.00")
    closed = account(db, customer, second, "closed")
    malformed_shop, creditor = business(db), business(db)
    malformed = account(db, customer, malformed_shop, creditor=creditor)
    for actor, target in ((customer, closed), (customer, malformed), (inactive, active)):
        with pytest.raises(HTTPException) as denied:
            assemble(db, actor, target)
        assert denied.value.status_code == 404
    with pytest.raises(HTTPException):
        CustomerFinancialSnapshotService(SQLAlchemyCustomerFinancialSnapshotRepository(db)).assemble(
            customer.user_id, 9223372036854775807)
