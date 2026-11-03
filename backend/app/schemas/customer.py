
import re

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
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
