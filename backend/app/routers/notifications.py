# Purpose: Expose notifications HTTP endpoints and connect request validation and dependencies to the application services.
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.notification import (MarkAllReadResponse, NotificationFilters,
                                      NotificationList, NotificationResponse, UnreadCount)
from app.services.notification_service import list_notifications, mark_all_read, mark_read, unread_count

router = APIRouter(prefix="/notifications", tags=["Notifications"])
notification_user = require_roles("shop_owner", "customer", "driver", "admin")


# Map notification-service outcomes to the public endpoint error contract.
def notification_operation(db, response, operation, write=False):
    response.headers["Cache-Control"] = "no-store"
    try:
        result = operation()
        if write:
            db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Unable to process notifications") from None


# Handle GET  through the declared request and dependency contract.
@router.get("", response_model=NotificationList)
def read_notifications(
    response: Response, filters: Annotated[NotificationFilters, Query()],
    current_user: User = Depends(notification_user), db: Session = Depends(get_db),
):
    return notification_operation(db, response, lambda: list_notifications(db, current_user.user_id, filters))


# Handle GET /unread-count through the declared request and dependency contract.
@router.get("/unread-count", response_model=UnreadCount)
def read_unread_count(
    response: Response, current_user: User = Depends(notification_user), db: Session = Depends(get_db),
):
    return notification_operation(db, response, lambda: {"unread_count": unread_count(db, current_user.user_id)})


# Handle PATCH /read-all through the declared request and dependency contract.
@router.patch("/read-all", response_model=MarkAllReadResponse)
def read_all_notifications(
    response: Response, current_user: User = Depends(notification_user), db: Session = Depends(get_db),
):
    return notification_operation(db, response, lambda: {"updated_count": mark_all_read(db, current_user.user_id)}, write=True)


# Handle PATCH /{notification_id}/read through the declared request and dependency contract.
@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def read_one_notification(
    response: Response, notification_id: int = Path(gt=0, le=9223372036854775807),
    current_user: User = Depends(notification_user), db: Session = Depends(get_db),
):
    return notification_operation(db, response, lambda: mark_read(db, current_user.user_id, notification_id), write=True)
