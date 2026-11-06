"""Shop Owner delivery requests; follow existing business_id query selection."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.shop_owner_delivery import (
    CancelDeliveryRequest, DeliveryRequestCreate, DeliveryRequestDetail, DeliveryStatus, ShopOwnerDeliveries,
    ShopOwnerDeliverySummary,
)
from app.services import shop_owner_delivery_service as service

router = APIRouter(prefix='/shop-owner/deliveries', tags=['Shop Owner Deliveries'])
Owner = Annotated[User, Depends(require_roles('shop_owner'))]
Database = Annotated[Session, Depends(get_db)]
BusinessId = Annotated[int, Query(gt=0, le=9223372036854775807)]
RequestId = Annotated[int, Path(gt=0, le=9223372036854775807)]


def read(response, operation):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return operation()
    except SQLAlchemyError:
        raise HTTPException(503, 'Delivery requests are temporarily unavailable') from None


def write(db, response, operation):
    response.headers['Cache-Control'] = 'no-store'
    try:
        result = DeliveryRequestDetail.model_validate(operation())
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Delivery request changed. Refresh its recorded status.') from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, 'Operation could not be confirmed. Refresh the delivery list before retrying.') from None


@router.post('', response_model=DeliveryRequestDetail, status_code=201)
def create(response: Response, user: Owner, db: Database, business_id: BusinessId, payload: DeliveryRequestCreate):
    return write(db, response, lambda: service.create_request(db, user, business_id, payload))


@router.get('', response_model=ShopOwnerDeliveries)
def deliveries(response: Response, user: Owner, db: Database, business_id: BusinessId,
               page: Annotated[int, Query(ge=1, le=1000000)] = 1,
               page_size: Annotated[int, Query(ge=1, le=100)] = 10,
               status: DeliveryStatus | None = None):
    return read(response, lambda: service.list_requests(db, user, business_id, page, page_size, status))


@router.get('/summary', response_model=ShopOwnerDeliverySummary)
def summary(response: Response, user: Owner, db: Database, business_id: BusinessId):
    return read(response, lambda: service.summary(db, user, business_id))


@router.get('/{request_id}', response_model=DeliveryRequestDetail)
def detail(response: Response, user: Owner, db: Database, business_id: BusinessId, request_id: RequestId):
    return read(response, lambda: service.request_detail(db, user, business_id, request_id))


@router.post('/{request_id}/cancel', response_model=DeliveryRequestDetail)
def cancel(response: Response, user: Owner, db: Database, business_id: BusinessId,
           request_id: RequestId, payload: CancelDeliveryRequest):
    return write(db, response, lambda: service.cancel_request(db, user, business_id, request_id))
