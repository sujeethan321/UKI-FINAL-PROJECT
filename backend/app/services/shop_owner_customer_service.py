
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CustomerProfile,
    CreditAccount,
)

from app.services.ledger_service import account_balances, load_ledger_entries


def list_business_customers(
    db: Session,
    business_id: int,
) -> list[dict]:
    """
    Return customers belonging to one business.

    Customer balances are calculated from active ledger
    entries, excluding reversed credit sales and payments.
    """

    customers = db.scalars(
        select(CustomerProfile)
        .where(CustomerProfile.business_id == business_id)
        .order_by(CustomerProfile.customer_id.desc())
    ).all()

    accounts = db.scalars(
        select(CreditAccount).where(
            CreditAccount.creditor_business_id == business_id,
            CreditAccount.customer_id.is_not(None),
        )
    ).all()

    accounts_by_customer = {
        account.customer_id: account
        for account in accounts
    }

    account_ids = [
        account.credit_account_id
        for account in accounts
    ]

    balances = account_balances(load_ledger_entries(db, account_ids))

    result = []

    for customer in customers:
        account = accounts_by_customer.get(
            customer.customer_id
        )

        balance = (
            balances.get(
                account.credit_account_id,
                Decimal("0.00"),
            )
            if account
            else Decimal("0.00")
        )

        result.append({
            "customer_id": customer.customer_id,
            "customer_name": customer.customer_name,
            "phone": customer.phone,
            "address": customer.address,
            "credit_account_id": (
                account.credit_account_id
                if account else None
            ),
            "credit_limit": (
                str(account.credit_limit)
                if account else None
            ),
            "outstanding_balance": str(
                max(balance, Decimal("0.00"))
            ),
            "account_status": (
                account.account_status
                if account else "no_account"
            ),
        })

    return result


