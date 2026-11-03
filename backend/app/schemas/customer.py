
import re
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class CustomerCreate(BaseModel):
    customer_name: str = Field(max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")

    @field_validator("customer_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = " ".join(value.split())

        if len(name) < 2:
            raise ValueError(
                "Customer name must contain at least 2 characters"
            )

        return name

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None

        phone = re.sub(r"[\s()-]", "", value)

        # Sri Lankan mobile numbers:
        # 0771234567 or +94771234567
        if re.fullmatch(r"07[0-9]{8}", phone):
            return phone

        if re.fullmatch(r"\+947[0-9]{8}", phone):
            return "0" + phone[3:]

        raise ValueError(
            "Enter a valid Sri Lankan mobile number"
        )

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return " ".join(value.split()) or None


class CustomerCreateResponse(BaseModel):
    customer_id: int
    business_id: int
    customer_name: str
    phone: str | None
    address: str | None
    message: str


class CustomerUpdate(CustomerCreate):
    customer_name: str = Field(default=None, max_length=150)

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one customer field")
        return self


class CreditAccountCreate(BaseModel):
    credit_limit: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    payment_term_days: int = Field(default=30, gt=0, le=2147483647, strict=True)
    account_status: Literal["active", "suspended", "closed"] = "active"

    model_config = ConfigDict(extra="forbid")


class CreditAccountUpdate(CreditAccountCreate):
    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one credit account field")
        return self
