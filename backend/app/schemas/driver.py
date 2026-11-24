# Purpose: Define typed driver API payloads so incoming data is validated and outgoing fields have an explicit contract.
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.schemas.customer_address import Destination


# Define the driver profile submission field contract used when validating or serializing API data.
class DriverProfileSubmission(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    vehicle_type: str = Field(min_length=1, max_length=50)
    registration_reference: str = Field(min_length=1, max_length=50)

    # Validate single line before the schema accepts the value.
    @field_validator('vehicle_type', 'registration_reference')
    @classmethod
    def single_line(cls, value):
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('Use single-line vehicle information')
        return value


# Define the driver vehicle field contract used when validating or serializing API data.
class DriverVehicle(BaseModel):
    vehicle_type: str
    registration_reference: str


# Define the driver profile response field contract used when validating or serializing API data.
class DriverProfileResponse(BaseModel):
    driver_user_id: int
    full_name: str
    account_status: str
    approval_status: Literal["not_submitted", "pending", "approved", "rejected", "suspended"]
    eligible_for_jobs: bool
    eligibility_reason: Literal["profile_required", "approval_pending", "approval_rejected", "approval_suspended", "vehicle_required", "eligible"]
    vehicle: DriverVehicle | None
    vehicle_registration_status: Literal['not_registered', 'pending', 'approved', 'rejected', 'suspended'] = 'not_registered'
    document_statuses: dict[Literal['DRIVING_LICENCE', 'VEHICLE_OWNERSHIP_PROOF'], Literal['PENDING', 'APPROVED', 'REJECTED']] = Field(default_factory=dict)
    legacy_document_exempt: bool = False


# Define the driver summary field contract used when validating or serializing API data.
class DriverSummary(BaseModel):
    driver_user_id: int
    available_jobs_count: int = Field(ge=0)
    active_deliveries_count: int = Field(ge=0)
    completed_deliveries_count: int = Field(ge=0)


# Define the driver delivery field contract used when validating or serializing API data.
class DriverDelivery(BaseModel):
    delivery_request_id: int
    reference: str
    business_name: str
    pickup_area: str
    delivery_area: str
    status: Literal["assigned", "picked_up", "in_transit", "delivered", "cancelled"]
    assigned_at: datetime
    finished_at: datetime | None = None
    linked_order_subtotal: str | None = None
    estimated_delivery_earning: str | None = None


# Define the driver deliveries field contract used when validating or serializing API data.
class DriverDeliveries(BaseModel):
    driver_user_id: int
    total: int
    page: int
    page_size: int
    deliveries: list[DriverDelivery]


# Define the available job field contract used when validating or serializing API data.
class AvailableJob(BaseModel):
    delivery_request_id: int
    reference: str
    business_name: str
    pickup_area: str
    delivery_area: str
    status: Literal["available"]
    created_at: datetime


# Define the available jobs field contract used when validating or serializing API data.
class AvailableJobs(BaseModel):
    driver_user_id: int
    total: int
    page: int
    page_size: int
    jobs: list[AvailableJob]


# Define the available job detail field contract used when validating or serializing API data.
class AvailableJobDetail(BaseModel):
    driver_user_id: int
    job: AvailableJob


# Define the operational delivery field contract used when validating or serializing API data.
class OperationalDelivery(BaseModel):
    destination: Destination | None = None
    delivery_request_id: int
    reference: str
    business_name: str
    pickup_area: str
    delivery_area: str
    status: Literal["assigned", "picked_up", "in_transit", "delivered", "cancelled"]
    assigned_at: datetime


# Define the driver assignment detail field contract used when validating or serializing API data.
class DriverAssignmentDetail(BaseModel):
    driver_user_id: int
    assignment_id: int
    delivery: OperationalDelivery


# Define the job acceptance field contract used when validating or serializing API data.
class JobAcceptance(DriverAssignmentDetail):
    pass


# Define the accept job request field contract used when validating or serializing API data.
class AcceptJobRequest(BaseModel):
    # Identity and status always come from authenticated server state.
    model_config = {"extra": "forbid"}


# Define the status update request field contract used when validating or serializing API data.
class StatusUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}
    expected_status: Literal["assigned", "picked_up", "in_transit"]
    status: Literal["picked_up", "in_transit", "delivered"]


# Define the delivery event field contract used when validating or serializing API data.
class DeliveryEvent(BaseModel):
    status: Literal["assigned", "picked_up", "in_transit", "delivered", "cancelled"]
    occurred_at: datetime


# Define the delivery progress field contract used when validating or serializing API data.
class DeliveryProgress(DriverAssignmentDetail):
    events: list[DeliveryEvent]
    allowed_next_status: Literal["picked_up", "in_transit", "delivered"] | None
