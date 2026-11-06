"""Customer-only, read-only dashboard foundation."""
from collections.abc import Callable
from typing import Annotated, Literal
from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.customer_dashboard import (
    CustomerCreditStatement, CustomerCreditAccountDetail, CustomerCreditAccounts, CustomerShops, CustomerSummary, CustomerTransactions,
)
from app.services import customer_dashboard_service as service

router = APIRouter(prefix="/customer", tags=["Customer Dashboard"])
Customer = Annotated[User, Depends(require_roles("customer"))]
Database = Annotated[Session, Depends(get_db)]
Page = Annotated[int, Query(ge=1, le=1000000)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def read_operation(response: Response, operation: Callable):
    response.headers["Cache-Control"] = "no-store"
    try:
        return operation()
    except SQLAlchemyError:
        raise HTTPException(500, "Unable to load customer information") from None


@router.get("/dashboard/summary", response_model=CustomerSummary)
def dashboard(response: Response, user: Customer, db: Database):
    return read_operation(response, lambda: service.dashboard_summary(db, user.user_id))


@router.get("/shops", response_model=CustomerShops)
def linked_shops(response: Response, user: Customer, db: Database, page: Page = 1, page_size: PageSize = 20):
    return read_operation(response, lambda: service.shops(db, user.user_id, page, page_size))


@router.get("/credit-accounts", response_model=CustomerCreditAccounts)
def accounts(response: Response, user: Customer, db: Database, page: Page = 1, page_size: PageSize = 20,
             business_id: Annotated[int | None, Query(gt=0)] = None):
    return read_operation(response, lambda: service.credit_accounts(db, user.user_id, page, page_size, business_id))


@router.get("/credit-accounts/{credit_account_id}", response_model=CustomerCreditAccountDetail)
def account_detail(response: Response, user: Customer, db: Database, credit_account_id: Annotated[int, Path(gt=0)]):
    return read_operation(response, lambda: service.credit_account_detail(db, user.user_id, credit_account_id))


@router.get("/transactions", response_model=CustomerTransactions)
def history(response: Response, user: Customer, db: Database, page: Page = 1, page_size: PageSize = 20,
            credit_account_id: Annotated[int | None, Query(gt=0)] = None,
            business_id: Annotated[int | None, Query(gt=0)] = None,
            entry_type: Literal["credit_sale", "repayment", "reversal"] | None = None,
            start_date: date | None = None, end_date: date | None = None):
    return read_operation(response, lambda: service.transactions(db, user.user_id, page, page_size, credit_account_id,
                                                               business_id, entry_type, start_date, end_date))


@router.get("/credit-accounts/{credit_account_id}/statement", response_model=CustomerCreditStatement)
def account_statement(response: Response, user: Customer, db: Database,
                      credit_account_id: Annotated[int, Path(gt=0)], start_date: date, end_date: date):
    return read_operation(response, lambda: service.statement(db, user.user_id, credit_account_id, start_date, end_date))


@router.get("/credit-accounts/{credit_account_id}/statement.pdf")
def account_statement_pdf(response: Response, user: Customer, db: Database,
                          credit_account_id: Annotated[int, Path(gt=0)], start_date: date, end_date: date):
    from app.services.customer_statement_pdf import render_statement_pdf
    data = read_operation(response, lambda: service.statement(db, user.user_id, credit_account_id, start_date, end_date))
    try:
        content = render_statement_pdf(data)
    except Exception:
        raise HTTPException(500, "Unable to generate statement PDF") from None
    return Response(content=content, media_type="application/pdf", headers={
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'attachment; filename="LankaPex-statement-{credit_account_id}-{start_date}-{end_date}.pdf"',
    })
