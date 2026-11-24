# Purpose: Define typed admin business API payloads so incoming data is validated and outgoing fields have an explicit contract.
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal
from app.schemas.admin import safe_text

# Define the business decision request field contract used when validating or serializing API data.
class BusinessDecisionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    decision: Literal['approve','reject']
    review_note: str | None=Field(default=None,max_length=500)
    _note=field_validator('review_note')(safe_text)

# Define the admin business field contract used when validating or serializing API data.
class AdminBusiness(BaseModel):
    business_id: int
    business_name: str
    business_type: str
    registration_number: str | None
    phone: str | None
    address: str | None
    approval_status: str
    created_at: datetime

# Define the admin businesses field contract used when validating or serializing API data.
class AdminBusinesses(BaseModel):
    businesses: list[AdminBusiness]
    total: int
    limit: int
    offset: int

# Define the business owner field contract used when validating or serializing API data.
class BusinessOwner(BaseModel):
    user_id: int
    full_name: str
    email: str
    phone: str | None

# Define the admin business detail field contract used when validating or serializing API data.
class AdminBusinessDetail(AdminBusiness):
    owners: list[BusinessOwner]

# Define the admin business decision field contract used when validating or serializing API data.
class AdminBusinessDecision(AdminBusiness):
    message: str

# Define the business audit row field contract used when validating or serializing API data.
class BusinessAuditRow(BaseModel):
    audit_id: int
    admin_user_id: int
    reviewer_name: str
    reviewer_email: str
    decision: str
    previous_status: str
    new_status: str
    review_note: str | None
    created_at: datetime

# Define the business history field contract used when validating or serializing API data.
class BusinessHistory(BaseModel):
    business_id: int
    history: list[BusinessAuditRow]
    total: int
    limit: int
    offset: int
