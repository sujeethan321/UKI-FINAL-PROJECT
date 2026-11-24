# Purpose: Define typed business API payloads so incoming data is validated and outgoing fields have an explicit contract.

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Define the business create field contract used when validating or serializing API data.
class BusinessCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(min_length=2, max_length=200)
    business_type: Literal[
        "retail",
        "grocery",
        "pharmacy",
        "hardware",
        "wholesale",
        "other",
    ]
    registration_number: str | None = Field(
        default=None,
        max_length=100,
    )
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)

    # Validate clean text before the schema accepts the value.
    @field_validator("business_name", "registration_number",
                     "phone", "address")
    @classmethod
    def clean_text(cls, value):
        if value is None:
            return None

        cleaned = value.strip()

        if not cleaned:
            raise ValueError("Field cannot be blank")

        return cleaned


# Define the business create response field contract used when validating or serializing API data.
class BusinessCreateResponse(BaseModel):
    business_id: int
    business_name: str
    business_type: str
    approval_status: str
    message: str
