# Purpose: Implement customer financial snapshot operations behind the HTTP layer so related business rules are shared by their callers.
"""Customer-scoped, read-only assembly of authoritative AI summary facts."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Protocol, Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User
from app.services.customer_dashboard_service import scoped_accounts
from app.services.ledger_service import (
    ZERO, account_balances, effective_entries, load_ledger_entries,
)
from app.services.tamil_credit_summary_prompt import FinancialSummarySnapshot


# Group the state and operations for authorized financial facts in the customer financial snapshot service module.
@dataclass(frozen=True, slots=True)
class AuthorizedFinancialFacts:
    total_credit_purchases: Decimal
    total_repayments: Decimal
    outstanding_balance: Decimal
    overdue_balance: Decimal | None = None
    advance_balance: Decimal = ZERO


# Group the state and operations for customer financial snapshot repository in the customer financial snapshot service module.
class CustomerFinancialSnapshotRepository(Protocol):
    def authorized_facts(self, user_id: int, credit_account_id: int) -> AuthorizedFinancialFacts | None:
        """Return facts only for an active Customer's active, scoped account."""


def _effective_facts(credit_account_id: int, entries: Sequence[object]) -> AuthorizedFinancialFacts:
    """Reuse the ledger's reversal-aware current-position semantics."""
    scoped = [entry for entry in entries
              if getattr(entry, "credit_account_id", None) == credit_account_id]
    current = effective_entries(scoped)
    purchases = sum((Decimal(entry.amount) for entry in current
                     if entry.entry_type == "credit_sale"), ZERO)
    repayments = sum((Decimal(entry.amount) for entry in current
                      if entry.entry_type == "repayment"), ZERO)
    balance = account_balances(scoped).get(credit_account_id, ZERO)
    return AuthorizedFinancialFacts(
        total_credit_purchases=purchases,
        total_repayments=repayments,
        outstanding_balance=max(balance, ZERO),
        advance_balance=max(-balance, ZERO),
        # Account-level aging integration is separately deferred. Do not infer
        # overdue from account terms or the business aggregate aging service.
        overdue_balance=None,
    )


class SQLAlchemyCustomerFinancialSnapshotRepository:
    """Production adapter over the existing request-scoped Session transaction."""

    # Initialize the dependencies and state this instance needs for later operations.
    def __init__(self, db: Session):
        self._db = db

    # Resolve facts within the access scope checked by this service.
    def authorized_facts(self, user_id: int, credit_account_id: int) -> AuthorizedFinancialFacts | None:
        active_customer = self._db.scalar(select(User.user_id).where(
            User.user_id == user_id,
            User.platform_role == "customer",
            User.account_status == "active",
        ))
        if active_customer is None:
            return None

        accounts = scoped_accounts(user_id)
        account = self._db.execute(select(
            accounts.c.credit_account_id, accounts.c.account_status,
        ).where(accounts.c.credit_account_id == credit_account_id)).mappings().one_or_none()
        # AI summaries are deliberately narrower than the existing statement
        # reader: closed/suspended accounts remain readable there, but are not
        # eligible for new AI generation.
        if account is None or account["account_status"] != "active":
            return None

        entries = load_ledger_entries(
            self._db, [credit_account_id],
            max_entries=settings.MAX_READ_LEDGER_ENTRIES,
        )
        return _effective_facts(credit_account_id, entries)


# Group the state and operations for customer financial snapshot service in the customer financial snapshot service module.
class CustomerFinancialSnapshotService:
    # Initialize the dependencies and state this instance needs for later operations.
    def __init__(self, repository: CustomerFinancialSnapshotRepository,
                 clock: Callable[[], datetime] | None = None):
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # Build the financial snapshot only from records authorized for the supplied account scope.
    def assemble(self, user_id: int, credit_account_id: int) -> FinancialSummarySnapshot:
        if (not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0
                or not isinstance(credit_account_id, int)
                or isinstance(credit_account_id, bool) or credit_account_id <= 0):
            raise HTTPException(404, "Credit account not found")
        facts = self._repository.authorized_facts(user_id, credit_account_id)
        if facts is None:
            # Preserve the customer dashboard's non-enumerating object-access response.
            raise HTTPException(404, "Credit account not found")
        return FinancialSummarySnapshot(
            currency="LKR",
            total_credit_purchases=facts.total_credit_purchases,
            total_repayments=facts.total_repayments,
            outstanding_balance=facts.outstanding_balance,
            overdue_balance=facts.overdue_balance,
            advance_balance=facts.advance_balance,
            captured_at=self._clock(),
        )

