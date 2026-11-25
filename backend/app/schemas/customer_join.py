# Purpose: Define typed customer join API payloads so incoming data is validated and outgoing fields have an explicit contract.
"""Narrow QR-join API payloads; never accept caller-supplied user IDs."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Define the join submission field contract used when validating or serializing API data.
class JoinSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    public_code: str = Field(pattern=r"^[A-Za-z0-9_-]{32}$")


# Define the join decision field contract used when validating or serializing API data.
class JoinDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]


# Define the join preview field contract used when validating or serializing API data.
class JoinPreview(BaseModel):
    business_name: str
    business_type: str


# Define the join link response field contract used when validating or serializing API data.
class JoinLinkResponse(BaseModel):
    public_code: str


# Define the join request response field contract used when validating or serializing API data.
class JoinRequestResponse(BaseModel):
    request_id: int
    status: Literal["pending", "approved", "rejected", "cancelled"]
    business_name: str
    created_at: datetime
    customer_name: str | None = None
    customer_email: str | None = None


# Define the join request list field contract used when validating or serializing API data.
class JoinRequestList(BaseModel):
    total: int
    page: int
    page_size: int
    requests: list[JoinRequestResponse]


# Define the join request status field contract used when validating or serializing API data.
class JoinRequestStatus(BaseModel):
    request_id: int | None
    status: Literal["none", "pending", "approved", "rejected", "cancelled", "already_linked"]
    