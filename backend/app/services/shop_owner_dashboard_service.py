
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CreditAccount, LedgerEntry
from sqlalchemy.orm import aliased

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
    )))
    balances = account_balances(load_ledger_entries(db, account_ids))

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

    return {
        "business_id": business_id,
        "currency": "LKR",
        "total_outstanding": total_outstanding,
        "collected_today": None,
        "overdue_amount": None,
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

