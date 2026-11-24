# Purpose: Define typed notification API payloads so incoming data is validated and outgoing fields have an explicit contract.
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NotificationType = Literal["driver_approved", "driver_rejected", "credit_sale_recorded", "repayment_recorded", "payment_reminder_recorded", "business_approved", "business_rejected", "delivery_requested", "delivery_cancelled", "delivery_assigned", "delivery_picked_up", "delivery_in_transit", "delivery_delivered", "order_submitted", "order_approved", "order_rejected", "order_processing", "order_completed", "order_cancelled", "support_created", "support_replied", "support_awaiting_user", "support_resolved", "support_reopened"]
RelatedEntityType = Literal["admin_audit", "ledger_entry", "payment_reminder", "business_approval_audit", "delivery_request", "order", "support_case"]


# Define the notification filters field contract used when validating or serializing API data.
class NotificationFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1, le=1000000)
    page_size: int = Field(default=20, ge=1, le=100)
    unread_only: bool = False
    is_read: bool | None = None
    notification_type: NotificationType | None = None

    # Validate compatible read filters before the schema accepts the value.
    @model_validator(mode="after")
    def compatible_read_filters(self):
        if self.unread_only and self.is_read is True:
            raise ValueError("Unread-only cannot be combined with is_read=true")
        return self


# Define the notification response field contract used when validating or serializing API data.
class NotificationResponse(BaseModel):
    notification_id: int
    business_id: int | None
    notification_type: NotificationType
    title: str
    message: str
    related_entity_type: RelatedEntityType
    related_entity_id: int
    is_read: bool
    created_at: datetime
    read_at: datetime | None


# Define the notification list field contract used when validating or serializing API data.
class NotificationList(BaseModel):
    page: int
    page_size: int
    total: int
    notifications: list[NotificationResponse]


# Define the unread count field contract used when validating or serializing API data.
class UnreadCount(BaseModel):
    unread_count: int


# Define the mark all read response field contract used when validating or serializing API data.
class MarkAllReadResponse(BaseModel):
    updated_count: int
