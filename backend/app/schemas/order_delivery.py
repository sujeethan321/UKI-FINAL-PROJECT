"""Separate operational owner and minimal Customer delivery projections."""
from datetime import datetime
from pydantic import BaseModel
from app.schemas.driver import DeliveryEvent
from app.schemas.shop_owner_delivery import DeliveryRequestCreate, DeliveryRequestDetail, DeliveryStatus


class OrderDeliveryCreate(DeliveryRequestCreate):
    """Required public pickup/drop-off areas; no private contact, price or assignment fields."""


class OwnerOrderDelivery(BaseModel):
    can_request_delivery: bool
    delivery_unavailable_reason: str | None
    order_id: int
    delivery_requested: bool
    delivery: DeliveryRequestDetail | None


class CustomerDeliveryProgress(BaseModel):
    reference: str
    status: DeliveryStatus
    created_at: datetime
    updated_at: datetime
    events: list[DeliveryEvent]


class CustomerOrderDelivery(BaseModel):
    order_id: int
    delivery_requested: bool
    delivery: CustomerDeliveryProgress | None
