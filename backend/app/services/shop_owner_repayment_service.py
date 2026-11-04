"""Manual Shop Owner repayments; no external payment verification is implied."""
from app.services.notification_service import notify_event

from fastapi import HTTPException

from app.models import LedgerEntry
from app.schemas.ledger import RepaymentResponse
from app.services.ledger_service import (
    ZERO, account_balances, load_ledger_entries, lock_customer_credit_account,
    find_idempotent_operation, generate_receipt_number, transaction_response_data,
)


def repayment_response(entry, account, business_id, customer_id, balance, replayed):
    return RepaymentResponse(
        **transaction_response_data(entry, account, business_id, customer_id, balance, replayed),
        payment_method=entry.payment_method,
    )


def record_repayment(db, business_id, user_id, payload):
    account = lock_customer_credit_account(db, business_id, payload.customer_id)
    entries = load_ledger_entries(db, [account.credit_account_id], lock=True)
    balance = account_balances(entries).get(account.credit_account_id, ZERO)
    existing = find_idempotent_operation(db, entries, payload, account.credit_account_id,
                                         "repayment", payment_method=payload.payment_method)
    if existing is not None:
        # Reserved server prefixes distinguish an omitted reference from an
        # explicit reference without adding fields or embedding data in notes.
        same_reference = (existing.receipt_number == payload.receipt_number
                          if payload.receipt_number is not None else
                          bool(existing.receipt_number and existing.receipt_number.startswith("RP-")))
        if not same_reference:
            raise HTTPException(409, "Idempotency key is already used for a different operation")
        # A replay only confirms the original record; it does not pay again or
        # undo a reversal, even after settlement or subsequent account closure.
        return repayment_response(existing, account, business_id, payload.customer_id, balance, True)

    # Policy: suspended accounts can settle debt. Closed accounts need a
    # separate correction workflow; repayments never change account status.
    if account.account_status not in ("active", "suspended"):
        raise HTTPException(409, "Closed or unsupported credit accounts cannot receive repayments")
    if payload.amount > max(balance, ZERO):
        raise HTTPException(409, "Repayment amount exceeds current outstanding balance")

    entry = LedgerEntry(
        credit_account_id=account.credit_account_id, created_by=user_id,
        entry_type="repayment", amount=payload.amount, payment_method=payload.payment_method,
        notes=payload.notes, idempotency_key=payload.idempotency_key,
        receipt_number=payload.receipt_number or generate_receipt_number("RP"),
    )
    db.add(entry)
    db.flush()
    notify_event(db, "repayment_recorded", entry.entry_id)
    return repayment_response(entry, account, business_id, payload.customer_id,
                              balance - payload.amount, False)
