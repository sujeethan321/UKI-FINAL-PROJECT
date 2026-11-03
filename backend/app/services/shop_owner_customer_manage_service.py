"""Customer maintenance without rewriting financial history."""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Business, CreditAccount, CustomerProfile, LedgerEntry
from app.services.shop_owner_customer_create_service import normalize_phone


def lock_customer(db: Session, business_id: int, customer_id: int):
    # Serialize phone checks and account creation within the business, including
    # the case where no credit account exists yet.
    db.scalar(select(Business).where(Business.business_id == business_id).with_for_update())
    customer = db.scalar(select(CustomerProfile).where(
        CustomerProfile.business_id == business_id,
        CustomerProfile.customer_id == customer_id,
    ).with_for_update())
    if customer is None:
        raise HTTPException(404, "Customer not found in this business")
    return customer


def update_customer(db, business_id, customer_id, payload):
    customer = lock_customer(db, business_id, customer_id)
    changes = payload.model_dump(exclude_unset=True)
    phone = changes.get("phone")
    if phone:
        others = db.scalars(select(CustomerProfile).where(
            CustomerProfile.business_id == business_id,
            CustomerProfile.customer_id != customer_id,
            CustomerProfile.phone.is_not(None),
        ).with_for_update()).all()
        if any(normalize_phone(other.phone) == phone for other in others):
            raise HTTPException(409, "A customer with this phone number already exists in your business")
    for field, value in changes.items():
        setattr(customer, field, value)
    db.flush()


def manage_credit_account(db, business_id, customer_id, payload, create=False):
    lock_customer(db, business_id, customer_id)
    account = db.scalar(select(CreditAccount).where(
        CreditAccount.creditor_business_id == business_id,
        CreditAccount.customer_id == customer_id,
    ).with_for_update())
    if create:
        if account is not None:
            raise HTTPException(409, "This customer already has a credit account")
        account = CreditAccount(creditor_business_id=business_id, customer_id=customer_id,
                                **payload.model_dump())
        db.add(account)
    else:
        if account is None:
            raise HTTPException(404, "Credit account not found")
        # A locking read sees the latest committed ledger even under MySQL's
        # REPEATABLE READ isolation. Keep every original and reversal intact.
        entries = db.scalars(select(LedgerEntry).where(
            LedgerEntry.credit_account_id == account.credit_account_id,
        ).with_for_update()).all()
        reversed_ids = {entry.reverses_entry_id for entry in entries if entry.entry_type == "reversal"}
        balance = sum((entry.amount if entry.entry_type == "credit_sale" else -entry.amount
                       for entry in entries if entry.entry_type in ("credit_sale", "repayment")
                       and entry.entry_id not in reversed_ids), Decimal("0.00"))
        changes = payload.model_dump(exclude_unset=True)
        if "credit_limit" in changes and changes["credit_limit"] < max(balance, Decimal("0.00")):
            raise HTTPException(409, "Credit limit cannot be below outstanding debt")
        if changes.get("account_status") == "closed" and balance != 0:
            raise HTTPException(409, "Settle outstanding debt or customer advance before closing the account")
        for field, value in changes.items():
            setattr(account, field, value)
    db.flush()
