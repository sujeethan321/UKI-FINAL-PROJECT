# Purpose: Define typed admin reports API payloads so incoming data is validated and outgoing fields have an explicit contract.
"""Aggregate-only Admin reporting contracts. No customer identities or raw events."""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


# Define the filters field contract used when validating or serializing API data.
class Filters(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start_date: date | None = None
    end_date: date | None = None
    business_id: int | None = Field(default=None, gt=0, le=9223372036854775807)
    approval_status: Literal['pending','approved','rejected','suspended'] | None = None
    order_status: Literal['submitted','approved','rejected','processing','completed','cancelled'] | None = None
    sort: Literal['business_id','orders','outstanding'] = 'business_id'
    direction: Literal['asc','desc'] = 'asc'


# Define the domain field contract used when validating or serializing API data.
class Domain(BaseModel):
    counts: dict[str, int]
    amounts: dict[str, str] = Field(default_factory=dict)
    daily: list[dict[str, str | int]] = Field(default_factory=list)


# Define the business row field contract used when validating or serializing API data.
class BusinessRow(BaseModel):
    business_id: int
    business_name: str
    approval_status: str
    orders: int
    product_order_total: str
    credit_sales: str
    repayments: str
    outstanding: str
    advances: str


# Define the overview field contract used when validating or serializing API data.
class Overview(BaseModel):
    generated_at: datetime
    database_today: date
    start_date: date
    end_date: date
    business_id: int | None
    approval_status: str | None
    order_status: str | None
    reporting_clocks: dict[str, str]
    snapshot: str
    coverage: dict[str, str | int]
    limitations: list[str]
    unavailable: dict[str, str]
    businesses: Domain
    users: Domain
    orders: Domain
    deliveries: Domain
    credit: Domain


# Define the comparisons field contract used when validating or serializing API data.
class Comparisons(BaseModel):
    report: Overview
    total: int
    limit: int
    offset: int
    sort: str
    direction: str
    rows: list[BusinessRow]
