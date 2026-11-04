from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CommunicationOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: Literal["whatsapp"] = "whatsapp"
    idempotency_key: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class ConsentCreate(CommunicationOperation):
    consent_status: Literal["granted", "opted_out"]
    evidence: str = Field(min_length=1, max_length=500)
    confirmed: bool = Field(strict=True)

    @field_validator("confirmed")
    @classmethod
    def confirmed_statement(cls, value):
        if not value:
            raise ValueError("Confirm that this records the customer's actual stated preference")
        return value

    @field_validator("evidence")
    @classmethod
    def clean_evidence(cls, value):
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Provide a short printable description of when and how the customer stated this preference")
        return value


class ConsentResponse(BaseModel):
    consent_id: int
    business_id: int
    customer_id: int
    channel: Literal["whatsapp"]
    consent_status: Literal["granted", "opted_out"]
    recorded_by: int
    created_at: datetime
    source: Literal["owner_recorded_customer_statement"] = "owner_recorded_customer_statement"
    independently_verified: Literal[False] = False
    replayed: bool = False


class HandoffCreate(CommunicationOperation):
    customer_id: int = Field(gt=0, le=9223372036854775807, strict=True)


class AttemptSummary(BaseModel):
    attempt_id: int
    status: Literal["handoff_requested"]
    created_at: datetime


class CommunicationPreview(BaseModel):
    business_id: int
    customer_id: int
    reminder_id: int
    message: str
    language: Literal["en", "ta"]
    outstanding_amount: str
    currency: Literal["LKR"] = "LKR"
    consent_status: Literal["unknown", "granted", "opted_out"]
    consent_source: str | None
    normalized_phone: str | None
    eligible: bool
    blocked_reason: str | None
    attempts: list[AttemptSummary]
    provider_delivery_available: Literal[False] = False


class HandoffResponse(AttemptSummary):
    business_id: int
    customer_id: int
    reminder_id: int
    channel: Literal["whatsapp"]
    normalized_phone: str
    message: str
    handoff_url: str
    replayed: bool = False
    provider_delivery_available: Literal[False] = False
