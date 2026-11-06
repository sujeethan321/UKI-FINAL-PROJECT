from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NotificationType = Literal["credit_sale_recorded", "repayment_recorded", "payment_reminder_recorded", "business_approved", "business_rejected", "delivery_assigned", "delivery_picked_up", "delivery_in_transit", "delivery_delivered"]
RelatedEntityType = Literal["ledger_entry", "payment_reminder", "business_approval_audit", "delivery_request"]


class NotificationFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1, le=1000000)
    page_size: int = Field(default=20, ge=1, le=100)
    unread_only: bool = False
    is_read: bool | None = None
    notification_type: NotificationType | None = None

    @model_validator(mode="after")
    def compatible_read_filters(self):
        if self.unread_only and self.is_read is True:
            raise ValueError("Unread-only cannot be combined with is_read=true")
        return self


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


class NotificationList(BaseModel):
    page: int
    page_size: int
    total: int
    notifications: list[NotificationResponse]


class UnreadCount(BaseModel):
    unread_count: int


class MarkAllReadResponse(BaseModel):
    updated_count: int
