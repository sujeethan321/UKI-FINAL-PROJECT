"""Narrow QR-join API payloads; never accept caller-supplied user IDs."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JoinSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    public_code: str = Field(pattern=r"^[A-Za-z0-9_-]{32}$")


class JoinDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]


class JoinPreview(BaseModel):
    business_name: str
    business_type: str


class JoinLinkResponse(BaseModel):
    public_code: str


class JoinRequestResponse(BaseModel):
    request_id: int
    status: Literal["pending", "approved", "rejected", "cancelled"]
    business_name: str
    created_at: datetime
    customer_name: str | None = None
    customer_email: str | None = None


class JoinRequestList(BaseModel):
    total: int
    page: int
    page_size: int
    requests: list[JoinRequestResponse]


class JoinRequestStatus(BaseModel):
    request_id: int | None
    status: Literal["none", "pending", "approved", "rejected", "cancelled", "already_linked"]
