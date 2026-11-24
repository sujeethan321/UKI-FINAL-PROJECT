# Purpose: Define typed ai summary API payloads so incoming data is validated and outgoing fields have an explicit contract.
"""Public contracts for explanatory AI credit summaries."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Money = str


# Define the tamil credit summary response field contract used when validating or serializing API data.
class TamilCreditSummaryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: str = Field(min_length=1, max_length=2000)
    source: Literal["generated", "fallback"]
    provider_status: Literal["available", "unavailable"]
    failure_category: Literal[
        "configuration", "invalid_request", "authentication", "rate_limited",
        "timeout", "connection", "provider_error", "invalid_response",
    ] | None = None
    currency: Literal["LKR"]
    total_credit_purchases: Money = Field(pattern=r"^\d+\.\d{2}$")
    total_repayments: Money = Field(pattern=r"^\d+\.\d{2}$")
    outstanding_balance: Money = Field(pattern=r"^\d+\.\d{2}$")
    advance_balance: Money = Field(default='0.00', pattern=r"^\d+\.\d{2}$")
    overdue_balance: Money | None = Field(default=None, pattern=r"^\d+\.\d{2}$")
    captured_at: datetime
