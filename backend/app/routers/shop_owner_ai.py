"""Authenticated, read-only Shop Owner AI explanation endpoints."""
from collections.abc import AsyncIterator
from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, Path, Request, Response
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import ai_generation_limit
from app.integrations.ai.base import AIClientError, AIFailureCategory, GenerationRequest
from app.integrations.ai.groq_client import GroqAIClient
from app.models import User
from app.schemas.ai_summary import TamilCreditSummaryResponse
from app.services.customer_financial_snapshot_service import (
    CustomerFinancialSnapshotService, SQLAlchemyCustomerFinancialSnapshotRepository,
)
from app.services.shop_owner_ai_summary_service import (
    ShopOwnerFinancialSnapshotService,
    SQLAlchemyOwnerCustomerAccountScopeRepository,
)
from app.services.tamil_credit_summary_service import TamilCreditSummaryService

router = APIRouter(prefix="/shop-owner", tags=["Shop Owner AI"])
require_shop_owner = require_roles("shop_owner")


class _DisabledAIClient:
    async def generate(self, request: GenerationRequest):
        raise AIClientError(AIFailureCategory.CONFIGURATION)


def get_owner_snapshot_service(db: Session = Depends(get_db)):
    return ShopOwnerFinancialSnapshotService(
        SQLAlchemyOwnerCustomerAccountScopeRepository(db),
        CustomerFinancialSnapshotService(
            SQLAlchemyCustomerFinancialSnapshotRepository(db)),
    )


async def get_tamil_summary_service() -> AsyncIterator[TamilCreditSummaryService]:
    if not settings.AI_ENABLED:
        yield TamilCreditSummaryService(_DisabledAIClient())
        return
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as client:
        yield TamilCreditSummaryService(GroqAIClient(settings, client))


def _money(value: Decimal) -> str:
    return format(value, ".2f")


@router.post(
    "/businesses/{business_id}/customers/{customer_id}/credit-accounts/"
    "{credit_account_id}/tamil-credit-summary",
    response_model=TamilCreditSummaryResponse,
)
async def generate_tamil_credit_summary(
    request: Request,
    response: Response,
    business_id: int = Path(gt=0),
    customer_id: int = Path(gt=0),
    credit_account_id: int = Path(gt=0),
    current_user: User = Depends(require_shop_owner),
    snapshot_service: ShopOwnerFinancialSnapshotService = Depends(get_owner_snapshot_service),
    summary_service: TamilCreditSummaryService = Depends(get_tamil_summary_service),
):
    ai_generation_limit(request, current_user.user_id, business_id)
    snapshot = snapshot_service.assemble(
        current_user.user_id, business_id, customer_id, credit_account_id)
    result = await summary_service.summarize(snapshot)
    response.headers["Cache-Control"] = "no-store"
    return TamilCreditSummaryResponse(
        summary=result.text,
        source=result.source.value,
        provider_status=result.provider_status.value,
        failure_category=(result.failure_category.value
                          if result.failure_category is not None else None),
        currency=snapshot.currency,
        total_credit_purchases=_money(snapshot.total_credit_purchases),
        total_repayments=_money(snapshot.total_repayments),
        outstanding_balance=_money(snapshot.outstanding_balance),
        overdue_balance=(_money(snapshot.overdue_balance)
                         if snapshot.overdue_balance is not None else None),
        captured_at=snapshot.captured_at,
    )
