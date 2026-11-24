# Purpose: Implement shop owner customer details operations behind the HTTP layer so related business rules are shared by their callers.
"""Read-only customer details and effective credit ledger for one business."""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import CustomerProfile, CreditAccount
from app.services.ledger_service import (
    ZERO, load_ledger_entries, effective_entries, entry_delta, balance_position,
)


# Format the financial value for the customer-details response.
def cash(value: Decimal) -> str:
    return f"{value:.2f}"

# Serialize an available date/time value for the response.
def iso(dt):
    return dt.isoformat() if dt is not None else None

# Get customer details for the shop owner customer details workflow.
def get_customer_details(db: Session, business_id: int, customer_id: int) -> dict:
    customer = db.scalar(select(CustomerProfile).where(
        CustomerProfile.customer_id == customer_id,
        CustomerProfile.business_id == business_id,
    ))
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found in this business")

    info = {
        "customer_id": customer.customer_id,
        "business_id": customer.business_id,
        "customer_name": customer.customer_name,
        "phone": customer.phone,
        "address": customer.address,
        "created_at": iso(customer.created_at),
    }
    account = db.scalar(select(CreditAccount).where(
        CreditAccount.customer_id == customer_id,
        CreditAccount.creditor_business_id == business_id,
    ))
    if account is None:
        return {
            "business_id": business_id, "currency": "LKR", "customer": info,
            "credit_account": None, "outstanding_balance": "0.00",
            "advance_balance": "0.00", "available_credit": None, "transactions": [],
        }

    entries = effective_entries(load_ledger_entries(db, [account.credit_account_id]))

    balance = ZERO
    transactions = []
    for entry in entries:
        value = Decimal(entry.amount)
        sale = entry.entry_type == "credit_sale"
        balance += entry_delta(entry)
        transactions.append({
            "entry_id": entry.entry_id,
            "entry_type": entry.entry_type,
            "recorded_at": iso(entry.recorded_at),
            "reference": entry.receipt_number or f"TXN-{entry.entry_id}",
            "debit": cash(value if sale else ZERO),
            "credit": cash(ZERO if sale else value),
            "running_balance": cash(balance),
            "payment_method": entry.payment_method,
            "receipt_number": entry.receipt_number,
            "notes": entry.notes,
            "due_at": iso(entry.due_at),
        })

    credit_limit = Decimal(account.credit_limit)
    position = balance_position(balance, credit_limit)
    return {
        "business_id": business_id, "currency": "LKR", "customer": info,
        "credit_account": {
            "credit_account_id": account.credit_account_id,
            "credit_limit": cash(credit_limit),
            "payment_term_days": account.payment_term_days,
            "account_status": account.account_status,
            "opened_at": iso(account.opened_at),
        },
        "outstanding_balance": cash(position["outstanding_balance"]),
        "advance_balance": cash(position["advance_balance"]),
        "available_credit": cash(position["available_credit"]),
        "transactions": transactions,
    }
