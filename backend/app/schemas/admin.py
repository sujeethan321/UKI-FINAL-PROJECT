"""Explicit minimal Administrator projections; no credentials or ledger fields."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ManagedRole = Literal['shop_owner','customer','driver']
AccountStatus = Literal['active','suspended']
DriverApproval = Literal['pending','approved','rejected','suspended','not_submitted']


def safe_text(value):
    if value is None:
        return None
    value=value.strip()
    if not value or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValueError('Provide nonblank single-line text')
    return value


class AdminUser(BaseModel):
    user_id: int
    full_name: str
    email: str
    platform_role: str
    account_status: str
    created_at: datetime


class AdminUsers(BaseModel):
    total: int
    limit: int
    offset: int
    users: list[AdminUser]


class AdminDriverProfile(BaseModel):
    approval_status: str
    vehicle_type: str | None
    registration_reference: str | None
    reviewed_by: int | None
    reviewed_at: datetime | None


class AdminDriver(AdminUser):
    profile: AdminDriverProfile | None
    verification: 'DriverVerification | None' = None


class DocumentMetadata(BaseModel):
    document_type: Literal['DRIVING_LICENCE','VEHICLE_OWNERSHIP_PROOF']
    document_id: str | None
    version: int | None
    review_status: Literal['MISSING','PENDING','APPROVED','REJECTED']
    integrity_valid: bool
    media_type: str | None
    reviewed_by: int | None
    reviewed_at: datetime | None


class DriverVerification(BaseModel):
    driver_user_id: int
    legacy_exempt: bool
    approval_ready: bool
    documents: list[DocumentMetadata]


class DocumentDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    decision: Literal['approve','reject']
    rejection_code: Literal['UNREADABLE','WRONG_DOCUMENT','EXPIRED','OTHER'] | None = None

    @model_validator(mode='after')
    def rejection_required(self):
        if self.decision=='reject' and self.rejection_code is None: raise ValueError('Rejection requires a fixed reason code')
        return self

    @field_validator('rejection_code')
    @classmethod
    def code(cls,value,info):
        if (info.data.get('decision')=='approve' and value is not None): raise ValueError('Approval cannot include a rejection code')
        return value


AdminDriver.model_rebuild()


class AdminDrivers(BaseModel):
    total: int
    limit: int
    offset: int
    drivers: list[AdminDriver]


class DriverDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    decision: Literal['approve','reject']
    review_note: str | None=Field(default=None,max_length=500)
    _note=field_validator('review_note')(safe_text)


class AccountDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    account_status: AccountStatus
    reason: str=Field(min_length=1,max_length=500)
    _reason=field_validator('reason')(safe_text)


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


class OwnerBusiness(BaseModel):
    business_id: int
    business_name: str
    approval_status: str
    membership_status: str
    business_role: str


class OwnerBusinesses(BaseModel):
    user_id: int
    total: int
    limit: int
    offset: int
    businesses: list[OwnerBusiness]


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


class AuditEvents(BaseModel):
    total: int
    limit: int
    offset: int
    events: list[AuditEvent]
