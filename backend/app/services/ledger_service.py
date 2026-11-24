# Purpose: Calculate balances from effective ledger entries and share locking and replay checks across financial workflows.
"""Authoritative effective-ledger arithmetic shared by financial workflows."""
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CreditAccount, CustomerProfile, LedgerEntry

ZERO = Decimal("0.00")


# Load account entries in stable order, optionally locking current rows and enforcing the interactive dataset limit.
def load_ledger_entries(db: Session, account_ids: list[int], *, lock=False, max_entries=None):
    if not account_ids:
        return []
    statement = select(LedgerEntry).where(
        LedgerEntry.credit_account_id.in_(account_ids),
    ).order_by(LedgerEntry.recorded_at, LedgerEntry.entry_id)
    if lock:
        # Read originals AND reversals as current rows, not from an older
        # REPEATABLE READ snapshot established by authorization queries.
        statement = statement.with_for_update().execution_options(populate_existing=True)
    if max_entries is not None:
        statement = statement.limit(max_entries + 1)
    entries = list(db.scalars(statement))
    if max_entries is not None and len(entries) > max_entries:
        raise HTTPException(422, 'This data set exceeds the interactive report limit. Contact support.')
    return entries


# Exclude reversals and the originals they cancel so balances reflect only effective sales and repayments.
def effective_entries(entries):
    reversed_ids = {
        (entry.credit_account_id, entry.reverses_entry_id)
        for entry in entries if entry.entry_type == "reversal"
        and entry.reverses_entry_id is not None
    }
    return [entry for entry in entries
            if entry.entry_type in ("credit_sale", "repayment")
            and (entry.credit_account_id, entry.entry_id) not in reversed_ids]


# Treat a credit sale as added debt and a repayment as reduced debt using decimal arithmetic.
def entry_delta(entry) -> Decimal:
    amount = Decimal(entry.amount)
    return amount if entry.entry_type == "credit_sale" else -amount


# Sum effective entry deltas per account so all financial workflows derive balances the same way.
def account_balances(entries) -> dict[int, Decimal]:
    balances = {}
    for entry in effective_entries(entries):
        account_id = entry.credit_account_id
        balances[account_id] = balances.get(account_id, ZERO) + entry_delta(entry)
    return balances


# Separate debt and advance balances and calculate available credit without increasing the account limit for advances.
def balance_position(balance: Decimal, credit_limit: Decimal):
    outstanding = max(balance, ZERO)
    return {
        "outstanding_balance": outstanding,
        "advance_balance": max(-balance, ZERO),
        # Preserve Day 7 semantics: advances offset the ledger balance but do
        # not increase the permitted sale amount beyond the account limit.
        "available_credit": max(Decimal(credit_limit) - outstanding, ZERO),
    }



# Resolve the customer inside the business and lock the credit account before a financial operation reads its balance.
def lock_customer_credit_account(db: Session, business_id: int, customer_id: int):
    customer = db.scalar(select(CustomerProfile).where(
        CustomerProfile.customer_id == customer_id,
        CustomerProfile.business_id == business_id,
    ))
    if customer is None:
        raise HTTPException(404, "Customer not found in this business")
    account = db.scalar(select(CreditAccount).where(
        CreditAccount.customer_id == customer_id,
        CreditAccount.creditor_business_id == business_id,
    ).with_for_update().execution_options(populate_existing=True))
    if account is None:
        raise HTTPException(404, "Credit account not found")
    return account


# Find an earlier request and reject mismatched payloads so a retry cannot silently become a different transaction.
def find_idempotent_operation(db, entries, payload, account_id, entry_type, *, payment_method=None):
    # Locked account rows see concurrent same-account commits even when the
    # authorization query established an earlier repeatable-read snapshot.
    existing = next((entry for entry in entries if entry.idempotency_key == payload.idempotency_key), None)
    if existing is None:
        existing = db.scalar(select(LedgerEntry).where(
            LedgerEntry.idempotency_key == payload.idempotency_key,
        ))
    if existing is not None and (
        existing.idempotency_key != payload.idempotency_key
        or existing.credit_account_id != account_id
        or existing.entry_type != entry_type
        or existing.amount != payload.amount
        or existing.notes != payload.notes
        or (entry_type == "repayment" and existing.payment_method != payment_method)
    ):
        raise HTTPException(409, "Idempotency key is already used for a different operation")
    return existing


# Generate an opaque receipt identifier with an allowed transaction prefix.
def generate_receipt_number(prefix: str):
    if prefix not in ("CS", "RP"):
        raise ValueError("Unsupported transaction receipt prefix")
    return f"{prefix}-{uuid4().hex}"


# Serialize transaction amounts and resulting balances as two-decimal strings for the API response.
def transaction_response_data(entry, account, business_id, customer_id, balance, replayed):
    position = balance_position(balance, account.credit_limit)
    return dict(
        entry_id=entry.entry_id, business_id=business_id, customer_id=customer_id,
        credit_account_id=account.credit_account_id, amount=f"{entry.amount:.2f}",
        **{key: f"{value:.2f}" for key, value in position.items()},
        recorded_at=entry.recorded_at, due_at=entry.due_at,
        receipt_number=entry.receipt_number,
        reference=entry.receipt_number or f"TXN-{entry.entry_id}",
        notes=entry.notes, replayed=replayed,
    )
