from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class DriverProfileSubmission(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    vehicle_type: str = Field(min_length=1, max_length=50)
    registration_reference: str = Field(min_length=1, max_length=50)

    @field_validator('vehicle_type', 'registration_reference')
    @classmethod
    def single_line(cls, value):
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('Use single-line vehicle information')
        return value


class DriverVehicle(BaseModel):
    vehicle_type: str
    registration_reference: str


class DriverProfileResponse(BaseModel):
    driver_user_id: int
    full_name: str
    account_status: str
    approval_status: Literal["not_submitted", "pending", "approved", "rejected", "suspended"]
    eligible_for_jobs: bool
    eligibility_reason: Literal["profile_required", "approval_pending", "approval_rejected", "approval_suspended", "vehicle_required", "eligible"]
    vehicle: DriverVehicle | None


class DriverSummary(BaseModel):
    driver_user_id: int
    available_jobs_count: int = Field(ge=0)
    active_deliveries_count: int = Field(ge=0)
    completed_deliveries_count: int = Field(ge=0)


class DriverDelivery(BaseModel):
    delivery_request_id: int
    reference: str
    business_name: str
    pickup_area: str
    delivery_area: str
    status: Literal["assigned", "picked_up", "in_transit", "delivered", "cancelled"]
    assigned_at: datetime
    finished_at: datetime | None = None


class DriverDeliveries(BaseModel):
    driver_user_id: int
    total: int
    page: int
    page_size: int
    deliveries: list[DriverDelivery]


class AvailableJob(BaseModel):
    delivery_request_id: int
    reference: str
    business_name: str
    pickup_area: str
    delivery_area: str
    status: Literal["available"]
    created_at: datetime


class AvailableJobs(BaseModel):
    driver_user_id: int
    total: int
    page: int
    page_size: int
    jobs: list[AvailableJob]


class AvailableJobDetail(BaseModel):
    driver_user_id: int
    job: AvailableJob


class OperationalDelivery(BaseModel):
    delivery_request_id: int
    reference: str
    business_name: str
    pickup_area: str
    delivery_area: str
    status: Literal["assigned", "picked_up", "in_transit", "delivered", "cancelled"]
    assigned_at: datetime


class DriverAssignmentDetail(BaseModel):
    driver_user_id: int
    assignment_id: int
    delivery: OperationalDelivery


class JobAcceptance(DriverAssignmentDetail):
    pass


class AcceptJobRequest(BaseModel):
    # Identity and status always come from authenticated server state.
    model_config = {"extra": "forbid"}


class StatusUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}
    expected_status: Literal["assigned", "picked_up", "in_transit"]
    status: Literal["picked_up", "in_transit", "delivered"]


class DeliveryEvent(BaseModel):
    status: Literal["assigned", "picked_up", "in_transit", "delivered", "cancelled"]
    occurred_at: datetime


class DeliveryProgress(DriverAssignmentDetail):
    events: list[DeliveryEvent]
    allowed_next_status: Literal["picked_up", "in_transit", "delivered"] | None
