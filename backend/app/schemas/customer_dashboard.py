"""Minimal customer-visible read models; LKR amounts are exact decimal strings."""
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Money = Annotated[str, Field(pattern=r"^-?\d+\.\d{2}$")]


class CustomerTransaction(BaseModel):
    entry_id: int
    credit_account_id: int
    business_id: int
    business_name: str
    entry_type: Literal["credit_sale", "repayment", "reversal"]
    recorded_at: datetime
    amount: Money
    balance_delta: Money
    reference: str
    status: Literal["recorded", "reversed", "reversal"]


class CustomerCreditAccount(BaseModel):
    credit_account_id: int
    business_id: int
    business_name: str
    account_status: str
    credit_limit: Money
    outstanding_balance: Money
    advance_balance: Money
    available_credit: Money
    opened_at: datetime


class CustomerShop(BaseModel):
    business_id: int
    business_name: str
    credit_account_count: int
    outstanding_balance: Money


class CustomerSummary(BaseModel):
    currency: Literal["LKR"] = "LKR"
    linked_shop_count: int
    credit_account_count: int
    total_outstanding_balance: Money
    recent_activity: list[CustomerTransaction]
    due_soon_amount: Money | None = None
    overdue_amount: Money | None = None
    due_totals_status: Literal['complete', 'incomplete', 'unavailable'] = 'unavailable'
    due_date_policy: Literal['fifo_database_wall_clock_today_through_7_days'] = 'fifo_database_wall_clock_today_through_7_days'


class CustomerShops(BaseModel):
    currency: Literal["LKR"] = "LKR"
    total: int
    page: int
    page_size: int
    shops: list[CustomerShop]


class CustomerCreditAccounts(BaseModel):
    currency: Literal["LKR"] = "LKR"
    total: int
    page: int
    page_size: int
    credit_accounts: list[CustomerCreditAccount]


class CustomerTransactions(BaseModel):
    currency: Literal["LKR"] = "LKR"
    total: int
    page: int
    page_size: int
    transactions: list[CustomerTransaction]


class CustomerCreditAccountDetail(BaseModel):
    currency: Literal["LKR"] = "LKR"
    account: CustomerCreditAccount


class CustomerStatementEntry(BaseModel):
    entry_id: int
    entry_type: Literal["credit_sale", "repayment", "reversal"]
    recorded_at: datetime
    reference: str
    amount: Money
    debit: Money
    credit: Money
    running_balance: Money
    status: Literal["recorded", "reversed", "reversal"]


class CustomerCreditStatement(BaseModel):
    currency: Literal["LKR"] = "LKR"
    credit_account_id: int
    business_id: int
    business_name: str
    customer_name: str
    start_date: date
    end_date: date
    time_basis: str
    reversal_policy: str
    historical_limitations: str
    opening_balance: Money
    total_credit_sales: Money
    total_repayments: Money
    reversal_impact: Money
    closing_balance: Money
    outstanding_balance: Money
    advance_balance: Money
    transactions: list[CustomerStatementEntry]
