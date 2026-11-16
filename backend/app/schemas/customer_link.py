"""Explicit two-party customer profile link inputs and minimal responses."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LinkInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_email: EmailStr


class LinkInvitation(BaseModel):
    invitation: str
    expires_at: datetime


class LinkAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invitation: str = Field(pattern=r"^[0-9]{6}$")


class LinkedProfile(BaseModel):
    customer_id: int
    business_id: int
    linked: bool
