"""Read-only financial documents. Amounts are exact decimal strings."""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel


class DocumentBusiness(BaseModel):
    business_id: int
    business_name: str
    phone: str | None
    address: str | None


class DocumentCustomer(BaseModel):
    customer_id: int
    business_id: int
    customer_name: str
    phone: str | None
    address: str | None


class RepaymentReceipt(BaseModel):
    business: DocumentBusiness
    customer: DocumentCustomer
    credit_account_id: int
    entry_id: int
    receipt_identifier: str
    receipt_number: str | None
    reference: str
    amount: str
    currency: Literal["LKR"] = "LKR"
    payment_method: str | None
    recorded_at: datetime
    notes: str | None
    status: Literal["recorded", "reversed"]
    reversal_entry_id: int | None
    reversed_at: datetime | None


class StatementEntry(BaseModel):
    entry_id: int
    entry_type: Literal["credit_sale", "repayment", "reversal"]
    recorded_at: datetime
    reference: str
    amount: str
    debit: str
    credit: str
    running_balance: str
    payment_method: str | None
    notes: str | None
    due_at: datetime | None
    reverses_entry_id: int | None
    status: Literal["recorded", "reversed", "reversal"]


class CustomerStatement(BaseModel):
    business: DocumentBusiness
    customer: DocumentCustomer
    credit_account_id: int | None
    currency: Literal["LKR"] = "LKR"
    start_date: date
    end_date: date
    time_basis: str
    reversal_policy: str
    historical_limitations: str
    opening_balance: str
    total_credit_sales: str
    total_repayments: str
    reversal_impact: str
    closing_balance: str
    outstanding_balance: str
    advance_balance: str
    transactions: list[StatementEntry]


class OutstandingCustomer(BaseModel):
    customer_id: int
    customer_name: str
    phone: str | None
    address: str | None
    credit_account_id: int | None
    credit_limit: str | None
    available_credit: str | None
    outstanding_balance: str
    account_status: str
    overdue_amount: None = None


class OutstandingPayments(BaseModel):
    business_id: int
    currency: Literal["LKR"] = "LKR"
    total_outstanding: str
    customers_with_outstanding: int
    overdue_amount: None = None
    overdue_unavailable_reason: str
    total_customers: int
    filtered_customers: int
    page: int
    page_size: int
    customers: list[OutstandingCustomer]
