from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LedgerOperationCreate(BaseModel):
    customer_id: int = Field(gt=0, le=9223372036854775807, strict=True)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)
    idempotency_key: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")

    model_config = ConfigDict(extra="forbid")

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value):
        return value.strip() or None if value is not None else None


class LedgerTransactionResponse(BaseModel):
    entry_id: int
    business_id: int
    customer_id: int
    credit_account_id: int
    currency: str = "LKR"
    amount: str
    outstanding_balance: str
    advance_balance: str
    available_credit: str
    recorded_at: datetime
    due_at: datetime | None
    receipt_number: str | None
    reference: str
    notes: str | None
    replayed: bool


class CreditSaleCreate(LedgerOperationCreate):
    pass


class CreditSaleResponse(LedgerTransactionResponse):
    pass


class RepaymentCreate(LedgerOperationCreate):
    # Approved manual recording methods; the database column is String(30).
    payment_method: Literal["cash", "bank_transfer", "card"]
    receipt_number: str | None = Field(default=None, max_length=60)

    @field_validator("payment_method", mode="before")
    @classmethod
    def normalize_method(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("receipt_number")
    @classmethod
    def validate_receipt(cls, value):
        if value is None or not value.strip():
            return None
        value = value.strip()
        if value.upper().startswith(("CS-", "RP-")):
            raise ValueError("CS- and RP- receipt prefixes are reserved for server-generated references")
        if not value.isprintable():
            raise ValueError("Receipt reference must not contain control characters")
        return value


class RepaymentResponse(LedgerTransactionResponse):
    payment_method: Literal["cash", "bank_transfer", "card"]
