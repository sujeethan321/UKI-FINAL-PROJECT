"""Read-only JWT-user-scoped customer projections over the existing ledger.

Balances aggregate complete histories in SQL, rather than loading unbounded ORM
rows or computing from a paginated history. The NOT EXISTS reversal predicate
mirrors ledger_service.effective_entries (same-account, full-original removal).
"""
from decimal import Decimal
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.orm import aliased

from app.models import Business, CreditAccount, CustomerProfile, LedgerEntry
from app.services.ledger_service import ZERO, balance_position, entry_delta


def money(value):
    return f"{Decimal(value):.2f}"


def linked_shops(user_id):
    return select(Business.business_id, Business.business_name).join(
        CustomerProfile, CustomerProfile.business_id == Business.business_id,
    ).where(CustomerProfile.user_id == user_id, Business.approval_status == "approved").distinct()


def scoped_accounts(user_id):
    # Both foreign keys must agree on business; a malformed legacy account is
    # excluded even if the customer profile itself belongs to this user.
    return select(
        CreditAccount.credit_account_id, CreditAccount.credit_limit,
        CreditAccount.account_status, CreditAccount.opened_at,
        Business.business_id, Business.business_name,
    ).join(CustomerProfile, and_(
        CustomerProfile.customer_id == CreditAccount.customer_id,
        CustomerProfile.business_id == CreditAccount.creditor_business_id,
    )).join(Business, Business.business_id == CustomerProfile.business_id).where(
        CustomerProfile.user_id == user_id, Business.approval_status == "approved",
    ).cte("customer_accounts")


def reversal_exists():
    reversal = aliased(LedgerEntry)
    return exists(select(1).where(
        reversal.credit_account_id == LedgerEntry.credit_account_id,
        reversal.entry_type == "reversal",
        reversal.reverses_entry_id == LedgerEntry.entry_id,
    )).correlate(LedgerEntry)


def account_positions(user_id):
    accounts = scoped_accounts(user_id)
    balances = select(
        LedgerEntry.credit_account_id,
        func.sum(case((LedgerEntry.entry_type == "credit_sale", LedgerEntry.amount),
                      else_=-LedgerEntry.amount)).label("balance"),
    ).join(accounts, accounts.c.credit_account_id == LedgerEntry.credit_account_id).where(
        LedgerEntry.entry_type.in_(("credit_sale", "repayment")), ~reversal_exists(),
    ).group_by(LedgerEntry.credit_account_id).cte("effective_balances")
    balance = func.coalesce(balances.c.balance, ZERO)
    return select(*accounts.c, balance.label("balance"),
                  func.greatest(balance, ZERO).label("outstanding_balance")).outerjoin(
        balances, balances.c.credit_account_id == accounts.c.credit_account_id,
    ).cte("account_positions")


def account_data(row):
    return dict(
        credit_account_id=row["credit_account_id"], business_id=row["business_id"],
        business_name=row["business_name"], account_status=row["account_status"],
        opened_at=row["opened_at"], credit_limit=money(row["credit_limit"]),
        **{key: money(value) for key, value in balance_position(
            Decimal(row["balance"]), Decimal(row["credit_limit"])).items()},
    )


def credit_accounts(db, user_id, page, page_size, business_id=None):
    positions = account_positions(user_id)
    query = select(positions)
    if business_id is not None:
        if db.scalar(linked_shops(user_id).where(Business.business_id == business_id)) is None:
            raise HTTPException(404, "Shop not found")
        query = query.where(positions.c.business_id == business_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(
        positions.c.opened_at.desc(), positions.c.credit_account_id.desc(),
    ).offset((page - 1) * page_size).limit(page_size)).mappings()
    return dict(total=total, page=page, page_size=page_size,
                credit_accounts=[account_data(row) for row in rows])


def credit_account_detail(db, user_id, credit_account_id):
    positions = account_positions(user_id)
    row = db.execute(select(positions).where(
        positions.c.credit_account_id == credit_account_id,
    )).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "Credit account not found")
    return dict(account=account_data(row))


def shops(db, user_id, page, page_size):
    links = linked_shops(user_id).subquery()
    positions = account_positions(user_id)
    totals = select(
        positions.c.business_id, func.count().label("account_count"),
        func.sum(positions.c.outstanding_balance).label("outstanding"),
    ).group_by(positions.c.business_id).subquery()
    total = db.scalar(select(func.count()).select_from(links))
    rows = db.execute(select(
        links.c.business_id, links.c.business_name,
        func.coalesce(totals.c.account_count, 0).label("credit_account_count"),
        func.coalesce(totals.c.outstanding, ZERO).label("outstanding_balance"),
    ).outerjoin(totals, totals.c.business_id == links.c.business_id).order_by(
        links.c.business_id,
    ).offset((page - 1) * page_size).limit(page_size)).mappings()
    return dict(total=total, page=page, page_size=page_size, shops=[dict(
        business_id=row["business_id"], business_name=row["business_name"],
        credit_account_count=row["credit_account_count"], outstanding_balance=money(row["outstanding_balance"]),
    ) for row in rows])


def transactions(db, user_id, page, page_size, credit_account_id=None, business_id=None, entry_type=None, start_date=None, end_date=None):
    validate_period(start_date, end_date)
    accounts = scoped_accounts(user_id)
    if credit_account_id is not None:
        if db.scalar(select(accounts.c.credit_account_id).where(
            accounts.c.credit_account_id == credit_account_id,
        )) is None:
            raise HTTPException(404, "Credit account not found")
    if business_id is not None and db.scalar(linked_shops(user_id).where(Business.business_id == business_id)) is None:
        raise HTTPException(404, "Shop not found")
    original = aliased(LedgerEntry)
    query = select(
        LedgerEntry, original, accounts.c.business_id, accounts.c.business_name,
        reversal_exists().label("is_reversed"),
    ).join(accounts, accounts.c.credit_account_id == LedgerEntry.credit_account_id).outerjoin(
        original, and_(original.entry_id == LedgerEntry.reverses_entry_id,
                       original.credit_account_id == LedgerEntry.credit_account_id),
    )
    if credit_account_id is not None:
        query = query.where(LedgerEntry.credit_account_id == credit_account_id)
    if business_id is not None:
        query = query.where(accounts.c.business_id == business_id)
    if entry_type is not None:
        query = query.where(LedgerEntry.entry_type == entry_type)
    if start_date is not None:
        query = query.where(LedgerEntry.recorded_at >= datetime.combine(start_date, time.min))
    if end_date is not None:
        query = query.where(LedgerEntry.recorded_at < datetime.combine(end_date + timedelta(days=1), time.min))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(LedgerEntry.recorded_at.desc(), LedgerEntry.entry_id.desc()).offset(
        (page - 1) * page_size).limit(page_size))
    items = []
    for entry, reversed_entry, business_id, business_name, is_reversed in rows:
        if entry.entry_type == "reversal":
            if (reversed_entry is None or reversed_entry.entry_type not in ("credit_sale", "repayment")
                    or (reversed_entry.recorded_at, reversed_entry.entry_id) >= (entry.recorded_at, entry.entry_id)):
                raise HTTPException(409, "Ledger reversal history cannot be reconstructed")
            delta = -entry_delta(reversed_entry)
        else:
            delta = entry_delta(entry)
        items.append(dict(
            entry_id=entry.entry_id, credit_account_id=entry.credit_account_id,
            business_id=business_id, business_name=business_name,
            entry_type=entry.entry_type, recorded_at=entry.recorded_at,
            amount=money(entry.amount), balance_delta=money(delta),
            reference=entry.receipt_number or f"TXN-{entry.entry_id}",
            status="reversal" if entry.entry_type == "reversal" else "reversed" if is_reversed else "recorded",
        ))
    return dict(total=total, page=page, page_size=page_size, transactions=items)


def dashboard_summary(db, user_id):
    positions = account_positions(user_id)
    count, outstanding = db.execute(select(
        func.count(), func.coalesce(func.sum(positions.c.outstanding_balance), ZERO),
    ).select_from(positions)).one()
    return dict(
        linked_shop_count=db.scalar(select(func.count()).select_from(linked_shops(user_id).subquery())),
        credit_account_count=count, total_outstanding_balance=money(outstanding),
        recent_activity=transactions(db, user_id, 1, 5)["transactions"],
    )


def validate_period(start_date, end_date):
    if (start_date and end_date and start_date > end_date) or end_date == date.max:
        raise HTTPException(422, "Choose a valid inclusive date range ending before 9999-12-31")


def statement(db, user_id, account_id, start_date, end_date):
    from app.services.shop_owner_financial_documents_service import customer_statement
    validate_period(start_date, end_date)
    # Authorize the exact profile/account/business relationship before using
    # the trusted existing statement calculation. Never accept customer IDs.
    row = db.execute(select(CreditAccount, CustomerProfile, Business).join(
        CustomerProfile, and_(CustomerProfile.customer_id == CreditAccount.customer_id,
                              CustomerProfile.business_id == CreditAccount.creditor_business_id),
    ).join(Business, Business.business_id == CustomerProfile.business_id).where(
        CreditAccount.credit_account_id == account_id, CustomerProfile.user_id == user_id,
        Business.approval_status == "approved",
    )).one_or_none()
    if row is None:
        raise HTTPException(404, "Credit account not found")
    account, customer, business = row
    # Complete snapshots are bounded rather than silently truncated. The
    # existing calculation loads the entire account history, including originals.
    count = db.scalar(select(func.count()).select_from(LedgerEntry).where(
        LedgerEntry.credit_account_id == account.credit_account_id))
    if count > 5000:
        raise HTTPException(422, "This account requires a larger statement export. Contact your shop.")
    source = customer_statement(db, business, customer.customer_id, start_date, end_date)
    permitted = ("currency", "credit_account_id", "start_date", "end_date", "time_basis", "reversal_policy",
                 "historical_limitations", "opening_balance", "total_credit_sales", "total_repayments",
                 "reversal_impact", "closing_balance", "outstanding_balance", "advance_balance")
    fields = ("entry_id", "entry_type", "recorded_at", "reference", "amount", "debit", "credit", "running_balance", "status")
    return dict(**{key: source[key] for key in permitted}, business_id=business.business_id,
                business_name=business.business_name, customer_name=customer.customer_name,
                transactions=[{key: entry[key] for key in fields} for entry in source["transactions"]])
