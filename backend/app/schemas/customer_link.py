# Purpose: Define typed customer link API payloads so incoming data is validated and outgoing fields have an explicit contract.
"""Explicit two-party customer profile link inputs and minimal responses."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# Define the link invitation request field contract used when validating or serializing API data.
class LinkInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_email: EmailStr


# Define the link invitation field contract used when validating or serializing API data.
class LinkInvitation(BaseModel):
    invitation: str
    expires_at: datetime


# Define the link acceptance field contract used when validating or serializing API data.
class LinkAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invitation: str = Field(pattern=r"^[0-9]{6}$")


# Define the linked profile field contract used when validating or serializing API data.
class LinkedProfile(BaseModel):
    customer_id: int
    business_id: int
    linked: bool
