"""Read-only owner authorization boundary for customer financial snapshots."""
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import Business, BusinessMember, CreditAccount, CustomerProfile, User
from app.services.customer_financial_snapshot_service import CustomerFinancialSnapshotService
from app.services.tamil_credit_summary_prompt import FinancialSummarySnapshot


class OwnerCustomerAccountScopeRepository(Protocol):
    def authorized_customer_user_id(
        self, owner_user_id: int, business_id: int, customer_id: int,
        credit_account_id: int,
    ) -> int | None:
        """Return the linked active Customer only for one exact owned account."""


class SQLAlchemyOwnerCustomerAccountScopeRepository:
    def __init__(self, db: Session):
        self._db = db

    def authorized_customer_user_id(
        self, owner_user_id: int, business_id: int, customer_id: int,
        credit_account_id: int,
    ) -> int | None:
        statement = select(CustomerProfile.user_id).select_from(Business).join(
            BusinessMember,
            and_(BusinessMember.business_id == Business.business_id,
                 BusinessMember.user_id == owner_user_id,
                 BusinessMember.business_role == "owner",
                 BusinessMember.membership_status == "active"),
        ).join(
            CustomerProfile, CustomerProfile.business_id == Business.business_id,
        ).join(
            CreditAccount,
            and_(CreditAccount.customer_id == CustomerProfile.customer_id,
                 CreditAccount.creditor_business_id == Business.business_id),
        ).join(
            User, User.user_id == CustomerProfile.user_id,
        ).where(
            Business.business_id == business_id,
            Business.approval_status == "approved",
            CustomerProfile.customer_id == customer_id,
            CreditAccount.credit_account_id == credit_account_id,
            CreditAccount.account_status == "active",
            User.platform_role == "customer",
            User.account_status == "active",
        )
        return self._db.scalar(statement)


class ShopOwnerFinancialSnapshotService:
    """Authorize the owner path, then reuse the Customer's scoped assembler."""

    def __init__(self, scope_repository: OwnerCustomerAccountScopeRepository,
                 customer_snapshot_service: CustomerFinancialSnapshotService):
        self._scope_repository = scope_repository
        self._customer_snapshot_service = customer_snapshot_service

    def assemble(self, owner_user_id: int, business_id: int, customer_id: int,
                 credit_account_id: int) -> FinancialSummarySnapshot:
        identifiers = (owner_user_id, business_id, customer_id, credit_account_id)
        if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0
               for value in identifiers):
            raise HTTPException(404, "Credit account not found")
        customer_user_id = self._scope_repository.authorized_customer_user_id(
            owner_user_id, business_id, customer_id, credit_account_id)
        if customer_user_id is None:
            raise HTTPException(404, "Credit account not found")
        return self._customer_snapshot_service.assemble(
            customer_user_id, credit_account_id)
