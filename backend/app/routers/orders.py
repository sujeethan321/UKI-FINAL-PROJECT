# Purpose: Expose orders HTTP endpoints and connect request validation and dependencies to the application services.
"""Customer-scoped and approved-owner-scoped order routes."""

from fastapi import APIRouter, Response, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.routers.catalogue import Customer, Owner, Database, BusinessId, Id, Page, Size
from app.schemas.order import (
    Cart,
    OrderCreate,
    Decision,
    Quote,
    OrderResponse,
    Orders,
    Status,
)
from app.services import order_service as service

customer_router = APIRouter(prefix="/customer/orders", tags=["Customer Orders"])
owner_router = APIRouter(prefix="/shop-owner/orders", tags=["Shop Owner Orders"])


# Wrap the service call at the HTTP boundary with cache policy and transaction/error handling.
def operation(db, response, action, schema, write=False):
    response.headers["Cache-Control"] = "no-store"
    try:
        result = schema.model_validate(action())
        if write:
            db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Order conflict. Retry the same request or refresh the order"
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            503,
            "Order operation unconfirmed. Retry with the same request key or refresh",
        ) from None


# Handle POST /quote through the declared request and dependency contract.
@customer_router.post("/quote", response_model=Quote)
def quote(response: Response, user: Customer, db: Database, payload: Cart):
    return operation(db, response, lambda: service.quote(db, user, payload), Quote)


# Handle POST  through the declared request and dependency contract.
@customer_router.post("", response_model=OrderResponse, status_code=201)
def create(response: Response, user: Customer, db: Database, payload: OrderCreate):
    return operation(
        db, response, lambda: service.create(db, user, payload), OrderResponse, True
    )


# Handle GET  through the declared request and dependency contract.
@customer_router.get("", response_model=Orders)
def customer_list(
    response: Response,
    user: Customer,
    db: Database,
    page: Page = 1,
    page_size: Size = 10,
    status: Status | None = None,
):
    return operation(
        db, response, lambda: service.listing(db, user, page, page_size, status), Orders
    )


# Handle GET /{order_id} through the declared request and dependency contract.
@customer_router.get("/{order_id}", response_model=OrderResponse)
def customer_detail(response: Response, user: Customer, db: Database, order_id: Id):
    return operation(
        db, response, lambda: service.detail(db, user, order_id), OrderResponse
    )


# Handle POST /{order_id}/decision through the declared request and dependency contract.
@customer_router.post("/{order_id}/decision", response_model=OrderResponse)
def customer_decision(
    response: Response, user: Customer, db: Database, order_id: Id, payload: Decision
):
    return operation(
        db,
        response,
        lambda: service.decide(db, user, order_id, payload.action),
        OrderResponse,
        True,
    )


# Handle GET  through the declared request and dependency contract.
@owner_router.get("", response_model=Orders)
def owner_list(
    response: Response,
    user: Owner,
    db: Database,
    business_id: BusinessId,
    page: Page = 1,
    page_size: Size = 10,
    status: Status | None = None,
):
    return operation(
        db,
        response,
        lambda: service.listing(db, user, page, page_size, status, business_id),
        Orders,
    )


# Handle GET /{order_id} through the declared request and dependency contract.
@owner_router.get("/{order_id}", response_model=OrderResponse)
def owner_detail(
    response: Response, user: Owner, db: Database, business_id: BusinessId, order_id: Id
):
    return operation(
        db,
        response,
        lambda: service.detail(db, user, order_id, business_id),
        OrderResponse,
    )


# Handle POST /{order_id}/decision through the declared request and dependency contract.
@owner_router.post("/{order_id}/decision", response_model=OrderResponse)
def owner_decision(
    response: Response,
    user: Owner,
    db: Database,
    business_id: BusinessId,
    order_id: Id,
    payload: Decision,
):
    return operation(
        db,
        response,
        lambda: service.decide(db, user, order_id, payload.action, business_id),
        OrderResponse,
        True,
    )


# Dedicated projections keep existing Order DTOs and frontend contracts stable.
from app.schemas.order_delivery import (
    OrderDeliveryCreate,
    OwnerOrderDelivery,
    CustomerOrderDelivery,
)
from app.services import order_delivery_service as delivery_service


# Handle POST /{order_id}/delivery through the declared request and dependency contract.
@owner_router.post(
    "/{order_id}/delivery", response_model=OwnerOrderDelivery, status_code=201
)
def request_order_delivery(
    response: Response,
    user: Owner,
    db: Database,
    order_id: Id,
    business_id: BusinessId,
    payload: OrderDeliveryCreate,
):
    return operation(
        db,
        response,
        lambda: delivery_service.create(db, user, order_id, business_id, payload),
        OwnerOrderDelivery,
        True,
    )


# Handle GET /{order_id}/delivery through the declared request and dependency contract.
@owner_router.get("/{order_id}/delivery", response_model=OwnerOrderDelivery)
def owner_order_delivery(
    response: Response, user: Owner, db: Database, order_id: Id, business_id: BusinessId
):
    return operation(
        db,
        response,
        lambda: delivery_service.owner_summary(db, user, order_id, business_id),
        OwnerOrderDelivery,
    )


# Handle GET /{order_id}/delivery through the declared request and dependency contract.
@customer_router.get("/{order_id}/delivery", response_model=CustomerOrderDelivery)
def customer_order_delivery(
    response: Response, user: Customer, db: Database, order_id: Id
):
    return operation(
        db,
        response,
        lambda: delivery_service.customer_summary(db, user, order_id),
        CustomerOrderDelivery,
    )
