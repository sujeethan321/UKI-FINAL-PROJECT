# Purpose: Define typed admin API payloads so incoming data is validated and outgoing fields have an explicit contract.
"""Explicit minimal Administrator projections; no credentials or ledger fields."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ManagedRole = Literal['shop_owner','customer','driver']
AccountStatus = Literal['active','suspended']
DriverApproval = Literal['pending','approved','rejected','suspended','not_submitted']


# Escape or constrain text at the document/export boundary before it is rendered.
def safe_text(value):
    if value is None:
        return None
    value=value.strip()
    if not value or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValueError('Provide nonblank single-line text')
    return value


# Define the admin user field contract used when validating or serializing API data.
class AdminUser(BaseModel):
    user_id: int
    full_name: str
    email: str
    platform_role: str
    account_status: str
    created_at: datetime


# Define the admin users field contract used when validating or serializing API data.
class AdminUsers(BaseModel):
    total: int
    limit: int
    offset: int
    users: list[AdminUser]


# Define the admin driver profile field contract used when validating or serializing API data.
class AdminDriverProfile(BaseModel):
    approval_status: str
    vehicle_type: str | None
    registration_reference: str | None
    reviewed_by: int | None
    reviewed_at: datetime | None


# Define the admin driver field contract used when validating or serializing API data.
class AdminDriver(AdminUser):
    profile: AdminDriverProfile | None
    verification: 'DriverVerification | None' = None


# Define the document metadata field contract used when validating or serializing API data.
class DocumentMetadata(BaseModel):
    document_type: Literal['DRIVING_LICENCE','VEHICLE_OWNERSHIP_PROOF']
    document_id: str | None
    version: int | None
    review_status: Literal['MISSING','PENDING','APPROVED','REJECTED']
    integrity_valid: bool
    media_type: str | None
    reviewed_by: int | None
    reviewed_at: datetime | None


# Define the driver verification field contract used when validating or serializing API data.
class DriverVerification(BaseModel):
    driver_user_id: int
    legacy_exempt: bool
    approval_ready: bool
    documents: list[DocumentMetadata]


# Define the document decision field contract used when validating or serializing API data.
class DocumentDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    decision: Literal['approve','reject']
    rejection_code: Literal['UNREADABLE','WRONG_DOCUMENT','EXPIRED','OTHER'] | None = None

    # Validate rejection required before the schema accepts the value.
    @model_validator(mode='after')
    def rejection_required(self):
        if self.decision=='reject' and self.rejection_code is None: raise ValueError('Rejection requires a fixed reason code')
        return self

    # Validate code before the schema accepts the value.
    @field_validator('rejection_code')
    @classmethod
    def code(cls,value,info):
        if (info.data.get('decision')=='approve' and value is not None): raise ValueError('Approval cannot include a rejection code')
        return value


AdminDriver.model_rebuild()


# Define the admin drivers field contract used when validating or serializing API data.
class AdminDrivers(BaseModel):
    total: int
    limit: int
    offset: int
    drivers: list[AdminDriver]


# Define the driver decision field contract used when validating or serializing API data.
class DriverDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    decision: Literal['approve','reject']
    review_note: str | None=Field(default=None,max_length=500)
    _note=field_validator('review_note')(safe_text)


# Define the account decision field contract used when validating or serializing API data.
class AccountDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    account_status: AccountStatus
    reason: str=Field(min_length=1,max_length=500)
    _reason=field_validator('reason')(safe_text)


# Define the admin overview field contract used when validating or serializing API data.
class AdminOverview(BaseModel):
    total_shop_owners: int
    total_customers: int
    total_drivers: int
    pending_driver_approvals: int
    approved_drivers: int
    total_businesses: int
    pending_business_approvals: int
    approved_businesses: int
    total_orders: int
    total_delivery_requests: int


# Define the owner business field contract used when validating or serializing API data.
class OwnerBusiness(BaseModel):
    business_id: int
    business_name: str
    approval_status: str
    membership_status: str
    business_role: str


# Define the owner businesses field contract used when validating or serializing API data.
class OwnerBusinesses(BaseModel):
    user_id: int
    total: int
    limit: int
    offset: int
    businesses: list[OwnerBusiness]


# Define the audit event field contract used when validating or serializing API data.
class AuditEvent(BaseModel):
    source: Literal['administrative','business_approval']
    audit_id: int
    admin_user_id: int
    target_type: str
    target_id: int
    action: str
    previous_state: str | None
    new_state: str
    reason: str | None
    created_at: datetime


# Define the audit events field contract used when validating or serializing API data.
class AuditEvents(BaseModel):
    total: int
    limit: int
    offset: int
    events: list[AuditEvent]
