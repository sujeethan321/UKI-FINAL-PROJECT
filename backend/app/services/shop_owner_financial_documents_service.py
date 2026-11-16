"""Authorized routes call these read-only, business-scoped document queries.

Statements post a reversal's opposite original delta on the reversal's recorded
 date; current-position helpers remain unchanged. No receipt assignment on GET.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import settings

from app.models import CreditAccount, CustomerProfile, LedgerEntry
from app.services.ledger_service import ZERO, entry_delta, load_ledger_entries
from app.services.shop_owner_customer_service import list_business_customers

OVERDUE_UNAVAILABLE = "Repayments are not allocated to individual credit sales; exact overdue amounts are unavailable."


def money(value):
    return f"{Decimal(value):.2f}"


def business_info(business):
    return {key: getattr(business, key) for key in ("business_id", "business_name", "phone", "address")}


def customer_info(customer):
    return {key: getattr(customer, key) for key in ("customer_id", "business_id", "customer_name", "phone", "address")}


def repayment_receipt(db, business, entry_id):
    # An ordinary consistent SELECT sees committed records, never another
    # session's uncommitted writes. Scope every relationship in the same query.
    row = db.execute(select(LedgerEntry, CreditAccount, CustomerProfile).join(
        CreditAccount, CreditAccount.credit_account_id == LedgerEntry.credit_account_id,
    ).join(CustomerProfile, CustomerProfile.customer_id == CreditAccount.customer_id).where(
        LedgerEntry.entry_id == entry_id, LedgerEntry.entry_type == "repayment",
        CreditAccount.creditor_business_id == business.business_id,
        CustomerProfile.business_id == business.business_id,
    )).one_or_none()
    if row is None:
        raise HTTPException(404, "Repayment not found in this business")
    entry, account, customer = row
    reversal = db.scalar(select(LedgerEntry).where(
        LedgerEntry.credit_account_id == account.credit_account_id,
        LedgerEntry.entry_type == "reversal", LedgerEntry.reverses_entry_id == entry.entry_id,
    ))
    return dict(
        business=business_info(business), customer=customer_info(customer),
        credit_account_id=account.credit_account_id, entry_id=entry.entry_id,
        # The primary key namespace is stable even for legacy unnumbered rows.
        # Never turn a read into a numbering write or change a saved reference.
        receipt_identifier=f"ledger-repayment:{entry.entry_id}",
        receipt_number=entry.receipt_number,
        reference=entry.receipt_number or f"Ledger repayment #{entry.entry_id}",
        amount=money(entry.amount), currency="LKR", payment_method=entry.payment_method,
        recorded_at=entry.recorded_at, notes=entry.notes,
        status="reversed" if reversal else "recorded",
        reversal_entry_id=reversal.entry_id if reversal else None,
        reversed_at=reversal.recorded_at if reversal else None,
    )


def customer_statement(db, business, customer_id, start_date, end_date):
    if start_date > end_date or end_date == date.max:
        raise HTTPException(422, "Choose a valid inclusive date range ending before 9999-12-31")
    start = datetime.combine(start_date, time.min)
    stop = datetime.combine(end_date + timedelta(days=1), time.min)
    customer = db.scalar(select(CustomerProfile).where(
        CustomerProfile.customer_id == customer_id, CustomerProfile.business_id == business.business_id,
    ))
    if customer is None:
        raise HTTPException(404, "Customer not found in this business")
    account = db.scalar(select(CreditAccount).where(
        CreditAccount.customer_id == customer_id, CreditAccount.creditor_business_id == business.business_id,
    ))
    entries = load_ledger_entries(db, [account.credit_account_id],
        max_entries=settings.MAX_READ_LEDGER_ENTRIES) if account else []
    by_id = {entry.entry_id: entry for entry in entries}
    through_end = [entry for entry in entries if entry.recorded_at < stop]
    reversed_ids = {entry.reverses_entry_id for entry in through_end if entry.entry_type == "reversal"}
    balance = ZERO
    opening = ZERO
    sales = ZERO
    repayments = ZERO
    reversals = ZERO
    transactions = []
    for entry in through_end:
        if entry.entry_type == "reversal":
            original = by_id.get(entry.reverses_entry_id)
            if (original is None or original.entry_type not in ("credit_sale", "repayment")
                    or (original.recorded_at, original.entry_id) >= (entry.recorded_at, entry.entry_id)):
                raise HTTPException(409, "Ledger reversal history cannot be reconstructed for this period")
            # Existing effective-ledger logic cancels the original in full,
            # regardless of the descriptive reversal amount on legacy rows.
            delta = -entry_delta(original)
        else:
            delta = entry_delta(entry)
        balance += delta
        if entry.recorded_at < start:
            opening = balance
            continue
        if entry.entry_type == "credit_sale":
            sales += Decimal(entry.amount)
        elif entry.entry_type == "repayment":
            repayments += Decimal(entry.amount)
        else:
            reversals += delta
        transactions.append(dict(
            entry_id=entry.entry_id, entry_type=entry.entry_type, recorded_at=entry.recorded_at,
            reference=entry.receipt_number or f"TXN-{entry.entry_id}", amount=money(entry.amount),
            debit=money(max(delta, ZERO)), credit=money(max(-delta, ZERO)), running_balance=money(balance),
            payment_method=entry.payment_method, notes=entry.notes, due_at=entry.due_at,
            reverses_entry_id=entry.reverses_entry_id,
            status="reversal" if entry.entry_type == "reversal" else "reversed" if entry.entry_id in reversed_ids else "recorded",
        ))
    return dict(
        business=business_info(business), customer=customer_info(customer),
        credit_account_id=account.credit_account_id if account else None, currency="LKR",
        start_date=start_date, end_date=end_date,
        time_basis="Inclusive calendar dates in the database recorded_at clock; stored timestamps have no timezone offset.",
        reversal_policy="Keep originals; post the opposite full original delta on the reversal recorded date. Status is as of period end.",
        historical_limitations="Reconstructed from stored recorded_at activity, not an immutable issued snapshot. No edit history or historical customer/shop details are stored. Invalid reversal chronology is rejected.",
        opening_balance=money(opening), total_credit_sales=money(sales), total_repayments=money(repayments),
        reversal_impact=money(reversals), closing_balance=money(balance),
        outstanding_balance=money(max(balance, ZERO)), advance_balance=money(max(-balance, ZERO)),
        transactions=transactions,
    )


def outstanding_payments(db, business_id, search, outstanding_only, page, page_size):
    # Reuse the exact existing effective balance rules, including no-account
    # customers. One customer/account/ledger query each, never one per customer.
    customers = list_business_customers(db, business_id)
    total = sum((Decimal(row["outstanding_balance"]) for row in customers), ZERO)
    debtors = sum(Decimal(row["outstanding_balance"]) > ZERO for row in customers)
    needle = search.strip().casefold()
    filtered = [row for row in customers if
                (not outstanding_only or Decimal(row["outstanding_balance"]) > ZERO) and
                (not needle or any(needle in (row[field] or "").casefold()
                                   for field in ("customer_name", "phone", "address")))]
    items = []
    for row in filtered[(page - 1) * page_size:page * page_size]:
        value = dict(row)
        value["outstanding_balance"] = money(value["outstanding_balance"])
        value["credit_limit"] = money(value["credit_limit"]) if value["credit_limit"] is not None else None
        value["available_credit"] = (money(max(Decimal(row["credit_limit"]) - Decimal(row["outstanding_balance"]), ZERO))
                                      if row["credit_limit"] is not None else None)
        value["overdue_amount"] = None
        items.append(value)
    return dict(business_id=business_id, currency="LKR", total_outstanding=money(total),
                customers_with_outstanding=debtors, overdue_amount=None, overdue_unavailable_reason=OVERDUE_UNAVAILABLE,
                total_customers=len(customers), filtered_customers=len(filtered), page=page, page_size=page_size, customers=items)
