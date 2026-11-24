# Purpose: Define typed shop owner delivery API payloads so incoming data is validated and outgoing fields have an explicit contract.
"""Business-scoped delivery projections; no financial or private Driver data."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.driver import DeliveryEvent

DeliveryStatus = Literal['available', 'assigned', 'picked_up', 'in_transit', 'delivered', 'cancelled']


# Define the delivery request create field contract used when validating or serializing API data.
class DeliveryRequestCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pickup_area: str = Field(min_length=1, max_length=160)
    delivery_area: str = Field(min_length=1, max_length=160)

    # Validate normalize area before the schema accepts the value.
    @field_validator('pickup_area', 'delivery_area', mode='before')
    @classmethod
    def normalize_area(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if any(ord(char) < 32 or ord(char) == 127 for char in value):
                raise ValueError('Provide a single-line area without control characters')
        return value


# Define the delivery request summary field contract used when validating or serializing API data.
class DeliveryRequestSummary(BaseModel):
    delivery_request_id: int
    reference: str
    business_id: int
    pickup_area: str
    delivery_area: str
    status: DeliveryStatus
    created_at: datetime
    updated_at: datetime


# Define the shop owner deliveries field contract used when validating or serializing API data.
class ShopOwnerDeliveries(BaseModel):
    business_id: int
    total: int = Field(ge=0)
    page: int
    page_size: int
    deliveries: list[DeliveryRequestSummary]


# Define the shop owner delivery summary field contract used when validating or serializing API data.
class ShopOwnerDeliverySummary(BaseModel):
    business_id: int
    total_requests_count: int = Field(ge=0)
    available_requests_count: int = Field(ge=0)
    in_progress_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)


# Define the assigned driver summary field contract used when validating or serializing API data.
class AssignedDriverSummary(BaseModel):
    # An operational name only, never email, phone, vehicle registration or profile review.
    full_name: str
    assigned_at: datetime


# Define the delivery request detail field contract used when validating or serializing API data.
class DeliveryRequestDetail(DeliveryRequestSummary):
    assigned_driver: AssignedDriverSummary | None
    events: list[DeliveryEvent]
    can_cancel: bool


# Define the cancel delivery request field contract used when validating or serializing API data.
class CancelDeliveryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
