# Purpose: Define typed auth API payloads so incoming data is validated and outgoing fields have an explicit contract.

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

    # Trim and lowercase the address so registration and login use the same email identity.
    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    # Validate password before the schema accepts the value.
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
    # Validate driver name before the schema accepts the value.
    @field_validator('full_name')
    @classmethod
    def driver_name(cls, value):
        value = value.strip()
        if not 2 <= len(value) <= 150:
            raise ValueError('Enter a valid full name')
        return value


# Shop Owner registration
class ShopOwnerRegister(RegistrationBase):
    pass

# Data returned after successful registration
class RegistrationResponse(BaseModel):
    user_id: int
    full_name: str
    email: EmailStr
    role: str
    account_status: str
    message: str


# Define the token response field contract used when validating or serializing API data.
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Define the current user response field contract used when validating or serializing API data.
class CurrentUserResponse(BaseModel):
    user_id: int
    full_name: str
    email: EmailStr
    platform_role: str
    account_status: str
    phone: str | None = None
    preferred_language: Literal['en','ta','si'] = 'en'
