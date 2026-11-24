# Purpose: Implement shop owner credit sale operations behind the HTTP layer so related business rules are shared by their callers.
"""Record one sale while holding the account lock until the route commits."""
from datetime import timedelta

from app.services.notification_service import notify_event

from fastapi import HTTPException

from app.models import LedgerEntry
from app.schemas.ledger import CreditSaleResponse
from app.services.ledger_service import (
    ZERO, account_balances, balance_position, load_ledger_entries,
    lock_customer_credit_account, find_idempotent_operation,
    generate_receipt_number, transaction_response_data,
)


# Shape sale fields for the response contract.
def sale_response(entry, account, business_id, customer_id, balance, replayed):
    return CreditSaleResponse(**transaction_response_data(
        entry, account, business_id, customer_id, balance, replayed,
    ))


# Record a credit sale using the shared account-locking, balance, and request-replay rules.
def record_credit_sale(db, business_id, user_id, payload):
    account = lock_customer_credit_account(db, business_id, payload.customer_id)

    entries = load_ledger_entries(db, [account.credit_account_id], lock=True)
    balance = account_balances(entries).get(account.credit_account_id, ZERO)
    existing = find_idempotent_operation(db, entries, payload, account.credit_account_id, "credit_sale")
    if existing is not None:
        # Replays never reinstate reversed sales or re-apply current eligibility
        # rules to a previously successful operation. Authorization still applies.
        return sale_response(existing, account, business_id, payload.customer_id, balance, True)

    if account.account_status != "active":
        raise HTTPException(409, "Credit account must be active to record a sale")
    position = balance_position(balance, account.credit_limit)
    if payload.amount > position["available_credit"]:
        raise HTTPException(409, "Sale amount exceeds available credit")

    entry = LedgerEntry(
        credit_account_id=account.credit_account_id, created_by=user_id,
        entry_type="credit_sale", amount=payload.amount, notes=payload.notes,
        idempotency_key=payload.idempotency_key, receipt_number=generate_receipt_number("CS"),
    )
    db.add(entry)
    db.flush()
    try:
        entry.due_at = entry.recorded_at + timedelta(days=account.payment_term_days)
    except OverflowError:
        raise HTTPException(422, "Account payment terms exceed the supported due-date range") from None
    db.flush()
    notify_event(db, "credit_sale_recorded", entry.entry_id)
    return sale_response(entry, account, business_id, payload.customer_id,
                         balance + payload.amount, False)
