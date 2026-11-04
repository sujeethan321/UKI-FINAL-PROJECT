from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.routers.shop_owner import get_approved_owned_business
from app.schemas.payment_reminder import PaymentReminderCreate, PaymentReminderResponse, PaymentReminderHistory
from app.services.shop_owner_reminder_service import record_reminder, reminder_history

router = APIRouter(prefix="/shop-owner/payment-reminders", tags=["Payment Reminders"])


@router.post("", response_model=PaymentReminderResponse, status_code=201)
def create_reminder(
    payload: PaymentReminderCreate, response: Response,
    business_id: int = Query(gt=0, le=9223372036854775807),
    current_user: User = Depends(require_roles("shop_owner")), db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    for attempt in range(3):
        try:
            business = get_approved_owned_business(db, current_user, business_id)
            result = record_reminder(db, business, current_user.user_id, payload)
            db.commit()
            response.status_code = 200 if result.replayed else 201
            return result
        except HTTPException:
            db.rollback()
            raise
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise HTTPException(409, "Reminder conflicts with an existing operation") from None
        except OperationalError as error:
            db.rollback()
            code = error.orig.args[0] if error.orig and error.orig.args else None
            if code not in (1205, 1213) or attempt == 2:
                raise HTTPException(500, "Unable to record reminder") from None
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(500, "Unable to record reminder") from None


@router.get("", response_model=PaymentReminderHistory)
def list_reminders(
    response: Response,
    business_id: int = Query(gt=0, le=9223372036854775807),
    customer_id: int | None = Query(default=None, gt=0, le=9223372036854775807),
    status: Literal["recorded"] | None = None,
    ordering: Literal["newest", "oldest"] = "newest",
    page: int = Query(default=1, ge=1, le=1000000),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles("shop_owner")), db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        get_approved_owned_business(db, current_user, business_id)
        return reminder_history(db, business_id, customer_id, status, page, page_size, ordering)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Unable to load reminder history") from None
