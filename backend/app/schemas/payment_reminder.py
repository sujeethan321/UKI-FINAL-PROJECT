from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentReminderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: int = Field(gt=0, le=9223372036854775807, strict=True)
    channel: Literal["internal", "copy", "whatsapp", "sms"] = "internal"
    language: Literal["en", "ta"] = "en"
    note: str | None = Field(default=None, max_length=1000)
    idempotency_key: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")

    @field_validator("note")
    @classmethod
    def clean_note(cls, value):
        if value is not None and any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Note contains unsupported control characters")
        return value.strip() or None if value is not None else None


class PaymentReminderResponse(BaseModel):
    reminder_id: int
    business_id: int
    customer_id: int
    credit_account_id: int
    created_by: int
    outstanding_amount: str
    currency: Literal["LKR"]
    message: str
    template_version: str
    channel: Literal["internal", "copy", "whatsapp", "sms"]
    language: Literal["en", "ta"]
    note: str | None
    status: Literal["recorded"]
    created_at: datetime
    updated_at: datetime
    consent_status: Literal["unknown", "granted", "opted_out"] = "unknown"
    delivery_allowed: Literal[False] = False
    delivery_blocked_reason: str = "Automated provider delivery is unavailable; check WhatsApp handoff eligibility separately."
    replayed: bool = False


class PaymentReminderHistory(BaseModel):
    business_id: int
    page: int
    page_size: int
    total: int
    reminders: list[PaymentReminderResponse]
