"""Authenticated owner-issued and Customer-accepted profile invitations."""
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.core.rate_limit import customer_link_limit
from app.models import User
from app.schemas.customer_link import LinkAcceptance, LinkInvitation, LinkInvitationRequest, LinkedProfile
from app.services import customer_link_service as service


owner_router = APIRouter(prefix="/shop-owner/customers", tags=["Customer Account Linking"])
customer_router = APIRouter(prefix="/customer", tags=["Customer Account Linking"])


@owner_router.post("/{customer_id}/link-invitations", response_model=LinkInvitation)
def create_invitation(
    payload: LinkInvitationRequest,
    response: Response,
    customer_id: int = Path(gt=0),
    business_id: int = Query(gt=0),
    owner: User = Depends(require_roles("shop_owner")),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        result = service.invite(db, owner, business_id, customer_id, payload.recipient_email)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Invitation could not be prepared") from None


@customer_router.post("/link-invitations/accept", response_model=LinkedProfile)
def accept_invitation(
    payload: LinkAcceptance,
    request: Request,
    response: Response,
    customer: User = Depends(require_roles("customer")),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    customer_link_limit(request, customer.user_id)
    try:
        result = service.accept(db, customer, payload.invitation)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Invitation acceptance could not be confirmed") from None
