# Purpose: Expose shop owner communication HTTP endpoints and connect request validation and dependencies to the application services.
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.routers.shop_owner import get_approved_owned_business
from app.schemas.communication import CommunicationPreview, ConsentCreate, ConsentResponse, HandoffCreate, HandoffResponse
from app.services.communication_service import communication_preview, record_consent, request_handoff

router = APIRouter(prefix="/shop-owner", tags=["Customer Communication"])


# Wrap the service call at the HTTP boundary with cache policy and transaction/error handling.
def operation(db, user, business_id, response, callback, write=False):
    response.headers["Cache-Control"] = "no-store"
    for attempt in range(3):
        try:
            get_approved_owned_business(db, user, business_id)
            result = callback()
            if write:
                db.commit()
                response.status_code = 200 if result.replayed else 201
            return result
        except HTTPException:
            db.rollback()
            raise
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise HTTPException(409, "Communication operation conflicts with an existing record") from None
        except OperationalError as error:
            db.rollback()
            code = error.orig.args[0] if error.orig and error.orig.args else None
            if code not in (1205, 1213) or attempt == 2:
                raise HTTPException(500, "Unable to process customer communication") from None
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(500, "Unable to process customer communication") from None


# Handle GET /payment-reminders/{reminder_id}/communication through the declared request and dependency contract.
@router.get("/payment-reminders/{reminder_id}/communication", response_model=CommunicationPreview)
def preview_communication(
    response: Response, customer_id: int = Query(gt=0, le=9223372036854775807),
    reminder_id: int = Path(gt=0, le=9223372036854775807), business_id: int = Query(gt=0, le=9223372036854775807),
    user: User = Depends(require_roles("shop_owner")), db: Session = Depends(get_db),
):
    return operation(db, user, business_id, response, lambda: communication_preview(db, business_id, customer_id, reminder_id))


# Handle POST /customers/{customer_id}/communication/consent through the declared request and dependency contract.
@router.post("/customers/{customer_id}/communication/consent", response_model=ConsentResponse, status_code=201)
def save_consent(
    payload: ConsentCreate, response: Response, customer_id: int = Path(gt=0, le=9223372036854775807),
    business_id: int = Query(gt=0, le=9223372036854775807),
    user: User = Depends(require_roles("shop_owner")), db: Session = Depends(get_db),
):
    return operation(db, user, business_id, response, lambda: record_consent(db, business_id, customer_id, user.user_id, payload), write=True)


# Handle POST /payment-reminders/{reminder_id}/whatsapp-handoff through the declared request and dependency contract.
@router.post("/payment-reminders/{reminder_id}/whatsapp-handoff", response_model=HandoffResponse, status_code=201)
def prepare_whatsapp_handoff(
    payload: HandoffCreate, response: Response, reminder_id: int = Path(gt=0, le=9223372036854775807),
    business_id: int = Query(gt=0, le=9223372036854775807),
    user: User = Depends(require_roles("shop_owner")), db: Session = Depends(get_db),
):
    return operation(db, user, business_id, response, lambda: request_handoff(db, business_id, reminder_id, user.user_id, payload), write=True)
