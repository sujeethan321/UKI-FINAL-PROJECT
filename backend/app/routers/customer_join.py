"""QR discovery, customer requests, and owner decisions."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.customer_join import JoinDecision, JoinLinkResponse, JoinPreview, JoinRequestList, JoinRequestResponse, JoinRequestStatus, JoinSubmission
from app.services import customer_join_service as service

public_router = APIRouter(prefix="/business-join", tags=["Customer QR Joining"])
owner_router = APIRouter(prefix="/shop-owner/businesses", tags=["Customer QR Joining"])
customer_router = APIRouter(prefix="/customer/join-requests", tags=["Customer QR Joining"])


@public_router.get("/{public_code}", response_model=JoinPreview)
def preview(public_code: str = Path(pattern=r"^[A-Za-z0-9_-]{32}$"), db: Session = Depends(get_db)):
    return service.preview(db, public_code)


@owner_router.post("/{business_id}/join-link", response_model=JoinLinkResponse)
def issue_link(business_id: int = Path(gt=0), owner: User = Depends(require_roles("shop_owner")),
               db: Session = Depends(get_db)):
    try:
        result = service.issue_link(db, owner, business_id)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Join link could not be issued") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Join link unavailable") from None


@customer_router.post("", response_model=JoinRequestResponse)
def submit(payload: JoinSubmission, response: Response,
           customer: User = Depends(require_roles("customer")), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    try:
        result = service.submit(db, customer, payload.public_code)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Join request already exists") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Join request unavailable") from None


@customer_router.get("", response_model=JoinRequestList)
def customer_requests(response: Response, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                      customer: User = Depends(require_roles("customer")), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return service.customer_requests(db, customer, page, page_size)


@customer_router.get("/by-code/{public_code}", response_model=JoinRequestStatus)
def request_status(response: Response, public_code: str = Path(pattern=r"^[A-Za-z0-9_-]{32}$"),
                   customer: User = Depends(require_roles("customer")), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.customer_request_status(db, customer, public_code)
    except HTTPException as exc:
        exc.headers = {**(exc.headers or {}), "Cache-Control": "no-store"}
        raise
    except SQLAlchemyError:
        raise HTTPException(503, "Join status unavailable", headers={"Cache-Control": "no-store"}) from None


@customer_router.post("/{request_id}/cancel", response_model=JoinRequestResponse)
def cancel(response: Response, request_id: int = Path(gt=0),
           customer: User = Depends(require_roles("customer")), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    try:
        result = service.cancel(db, customer, request_id)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Join request unavailable") from None


@owner_router.get("/{business_id}/join-requests", response_model=JoinRequestList)
def owner_requests(response: Response, business_id: int = Path(gt=0),
                   page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                   status: Literal["pending", "approved", "rejected", "cancelled"] | None = None,
                   owner: User = Depends(require_roles("shop_owner")), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return service.owner_requests(db, owner, business_id, page, page_size, status)


@owner_router.post("/{business_id}/join-requests/{request_id}/decision", response_model=JoinRequestResponse)
def decide(payload: JoinDecision, response: Response, business_id: int = Path(gt=0),
           request_id: int = Path(gt=0), owner: User = Depends(require_roles("shop_owner")),
           db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    try:
        result = service.decide(db, owner, business_id, request_id, payload.decision)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Customer is already linked") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Join decision unavailable") from None
