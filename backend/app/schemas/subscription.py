from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PlanName = Literal["FREE", "PRO", "BUSINESS"]


class Plan(BaseModel):
    plan: PlanName
    currency: Literal["LKR"]
    monthly_minor: int
    yearly_minor: int
    entitlements: dict[str, bool]
    customer_limit: int | None = None
    ai_limit_multiplier: int = 0


class PlansResponse(BaseModel):
    plans: list[Plan]
    payment_configured: bool = False
    payment_message: str = "Payment integration not configured"
    entitlement_policy: str = "existing_features_preserved"


class SubscriptionResponse(BaseModel):
    business_id: int
    effective_plan: PlanName
    status: Literal["FREE", "TRIALING", "EXPIRED", "ACTIVE"]
    billing_interval: Literal["month", "year"] | None
    trial_started_at: datetime | None
    trial_ends_at: datetime | None
    trial_remaining_seconds: int
    trial_remaining_days: int
    trial_active: bool
    upgrade_required: bool
    paid_through: datetime | None
    entitlements: dict[str, bool]
    entitlement_policy: str
    customer_limit: int | None = None
    ai_limit_multiplier: int = 0
    evaluated_at: datetime
    payment_configured: bool = False
    payment_message: str = "Payment integration not configured"
    payment_failed: bool = False
    portal_available: bool = False
    checkout_available: bool = False


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: Literal["PRO", "BUSINESS"]
    billing_interval: Literal["month", "year"]
    # Reserved for idempotent provider integration; never contains an amount,
    # price ID, customer ID or a user-supplied redirect URL.
    request_id: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
