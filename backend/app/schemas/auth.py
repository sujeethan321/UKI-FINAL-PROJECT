
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


# Common fields for all public registration types
class RegistrationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    phone: str | None = Field(default=None, max_length=20)
    preferred_language: Literal["en", "ta", "si"] = "en"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 1024:
            raise ValueError("Password is too long")
        return value


# Customer registration
class CustomerRegister(RegistrationBase):
    pass


# Delivery Driver registration
class DriverRegister(RegistrationBase):
    pass


# Shop Owner registration
class ShopOwnerRegister(RegistrationBase):
    business_name: str = Field(min_length=2, max_length=200)
    business_type: str = Field(min_length=2, max_length=50)
    business_address: str = Field(min_length=5, max_length=500)

    business_phone: str | None = Field(
        default=None,
        max_length=20,
    )

    registration_number: str | None = Field(
        default=None,
        max_length=100,
    )


# Data returned after successful registration
class RegistrationResponse(BaseModel):
    user_id: int
    full_name: str
    email: EmailStr
    role: str
    account_status: str
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    user_id: int
    full_name: str
    email: EmailStr
    platform_role: str
    account_status: str
