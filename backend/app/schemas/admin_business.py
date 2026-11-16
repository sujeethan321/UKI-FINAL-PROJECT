from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal
from app.schemas.admin import safe_text

class BusinessDecisionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    decision: Literal['approve','reject']
    review_note: str | None=Field(default=None,max_length=500)
    _note=field_validator('review_note')(safe_text)

class AdminBusiness(BaseModel):
    business_id: int
    business_name: str
    business_type: str
    registration_number: str | None
    phone: str | None
    address: str | None
    approval_status: str
    created_at: datetime

class AdminBusinesses(BaseModel):
    businesses: list[AdminBusiness]
    total: int
    limit: int
    offset: int

class BusinessOwner(BaseModel):
    user_id: int
    full_name: str
    email: str
    phone: str | None

class AdminBusinessDetail(AdminBusiness):
    owners: list[BusinessOwner]

class AdminBusinessDecision(AdminBusiness):
    message: str

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

class BusinessHistory(BaseModel):
    business_id: int
    history: list[BusinessAuditRow]
    total: int
    limit: int
    offset: int
