
from decimal import Decimal
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CreditAccount, LedgerEntry
from sqlalchemy.orm import aliased
from fastapi import HTTPException
from app.core.config import settings

from app.models import CustomerProfile
from app.services.ledger_service import account_balances, load_ledger_entries


def get_dashboard_summary(
    db: Session,
    business_id: int,
) -> dict:
    """
    Return verified dashboard metrics for one business.

    Reversed ledger entries are excluded.
    Only customer credit accounts are included.
    """

    account_ids = list(db.scalars(select(CreditAccount.credit_account_id).where(
        CreditAccount.creditor_business_id == business_id,
        CreditAccount.customer_id.is_not(None),
    ).limit(settings.MAX_INTERACTIVE_CUSTOMERS + 1)))
    if len(account_ids) > settings.MAX_INTERACTIVE_CUSTOMERS:
        raise HTTPException(422, 'Dashboard exceeds the interactive account limit. Contact support.')
    entries = load_ledger_entries(db, account_ids,
        max_entries=settings.MAX_READ_LEDGER_ENTRIES)
    balances = account_balances(entries)

    total_outstanding = sum(
        (
            max(balance, Decimal("0.00"))
            for balance in balances.values()
        ),
        Decimal("0.00"),
    )

    customer_count = db.scalar(
        select(
            func.count(
                func.distinct(CreditAccount.customer_id)
            )
        ).where(
            CreditAccount.creditor_business_id == business_id,
            CreditAccount.customer_id.is_not(None),
        )
    ) or 0

    # Use the same stored database wall clock and reversal-date calculations
    # as Reports. Import lazily because Reports also reuses this summary.
    from app.services.shop_owner_reports_service import trends
    from app.services.dashboard_due_service import due_totals
    now = db.scalar(select(func.now()))
    collected = None
    if isinstance(now, datetime) and now.tzinfo is None:
        try:
            _, collected = trends(entries, now.date(), now.date(), now.date())
        except HTTPException as error:
            if error.status_code != 409:
                raise
    due = due_totals(entries, now, total_outstanding)

    return {
        "business_id": business_id,
        "currency": "LKR",
        "total_outstanding": total_outstanding,
        "collected_today": collected,
        "overdue_amount": due['overdue_amount'],
        "due_totals_status": due['due_totals_status'],
        "due_date_policy": due['due_date_policy'],
        "credit_customers": customer_count,
        "pending_credit_requests": None,
        "active_deliveries": None,
    }
    
def get_recent_credit_transactions(
    db: Session,
    business_id: int,
    limit: int = 5,
) -> list[dict]:
    """
    Return the latest active customer credit sales and
    repayments for the specified business.

    A reversed transaction is excluded.
    Reversal entries themselves are also excluded.
    """

    reversed_entry = aliased(LedgerEntry)

    # Find transactions that have a reversal entry.
    has_reversal = (
        select(reversed_entry.entry_id)
        .where(
            reversed_entry.reverses_entry_id
            == LedgerEntry.entry_id,
            reversed_entry.entry_type == "reversal",
            reversed_entry.credit_account_id == LedgerEntry.credit_account_id,
        )
        .correlate(LedgerEntry)
        .exists()
    )

    statement = (
        select(
            LedgerEntry.entry_id,
            LedgerEntry.entry_type,
            LedgerEntry.amount,
            LedgerEntry.recorded_at,
            CustomerProfile.customer_name,
        )
        .join(
            CreditAccount,
            CreditAccount.credit_account_id
            == LedgerEntry.credit_account_id,
        )
        .join(
            CustomerProfile,
            CustomerProfile.customer_id
            == CreditAccount.customer_id,
        )
        .where(
            CreditAccount.creditor_business_id
            == business_id,
            CustomerProfile.business_id
            == business_id,
            LedgerEntry.entry_type.in_(
                ["credit_sale", "repayment"]
            ),
            ~has_reversal,
        )
        .order_by(
            LedgerEntry.recorded_at.desc(),
            LedgerEntry.entry_id.desc(),
        )
        .limit(limit)
    )

    rows = db.execute(statement).all()

    return [
        {
            "id": row.entry_id,
            "customer_name": row.customer_name,
            "type": row.entry_type,
            "amount": str(row.amount),
            "recorded_at": row.recorded_at.isoformat(),
        }
        for row in rows
    ]

