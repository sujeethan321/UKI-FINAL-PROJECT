# Purpose: Define typed order API payloads so incoming data is validated and outgoing fields have an explicit contract.
from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.customer_address import Destination

Status = Literal['submitted','approved','rejected','processing','completed','cancelled']
PositiveId = Annotated[int, Field(strict=True,gt=0,le=9223372036854775807)]
# Define the input field contract used when validating or serializing API data.
class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
# Define the cart item field contract used when validating or serializing API data.
class CartItem(Input):
    product_id: PositiveId
    quantity: int = Field(strict=True,ge=1,le=99)
# Define the cart field contract used when validating or serializing API data.
class Cart(Input):
    address_id: PositiveId | None = None
    address_version: PositiveId | None = None
    fulfilment_mode: Literal['delivery','pickup'] | None = None
    business_id: PositiveId
    items: list[CartItem] = Field(min_length=1,max_length=50)
    # Validate unique products before the schema accepts the value.
    @model_validator(mode='after')
    def unique_products(self):
        if len({i.product_id for i in self.items}) != len(self.items):
            raise ValueError('Duplicate products are not allowed')
        return self
# Define the order create field contract used when validating or serializing API data.
class OrderCreate(Cart):
    quote_token: str | None = Field(default=None,min_length=20,max_length=100)
    payment_method: Literal['cash','credit']
    request_key: str = Field(min_length=16,max_length=100,pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]*$')
# Define the decision field contract used when validating or serializing API data.
class Decision(Input):
    action: Literal['approve','reject','process','complete','cancel']
# Define the line field contract used when validating or serializing API data.
class Line(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price: str
    line_total: str
# Define the quote field contract used when validating or serializing API data.
class Quote(BaseModel):
    address_checkout_enabled: bool = False
    address_id: int | None = None
    address_version: int | None = None
    destination: Destination | None = None
    finance_enabled: bool = False
    fulfilment_mode: Literal['delivery','pickup'] | None = None
    delivery_fee: str | None = None
    customer_total: str | None = None
    fee_policy: str | None = None
    quote_token: str | None = None
    business_id: int
    business_name: str
    currency: Literal['LKR'] = 'LKR'
    items: list[Line]
    subtotal: str
    total: str
    estimated_delivery_fee: str
    estimated_total_with_delivery: str
    credit_available: bool
    credit_guidance: str
# Define the order response field contract used when validating or serializing API data.
class OrderResponse(BaseModel):
    destination: Destination | None = None
    finance_enabled: bool = False
    fulfilment_mode: Literal['delivery','pickup'] | None = None
    delivery_fee: str | None = None
    customer_total: str | None = None
    fee_policy: str | None = None
    order_id: int
    reference: str
    business_id: int
    business_name: str
    customer_name: str
    payment_method: Literal['cash','credit']
    payment_status: Literal['unpaid','pending','posted']
    status: Status
    currency: Literal['LKR'] = 'LKR'
    subtotal: str
    total: str
    credit_sale_id: int | None
    created_at: datetime
    updated_at: datetime
    items: list[Line]
# Define the orders field contract used when validating or serializing API data.
class Orders(BaseModel):
    page: int
    page_size: int
    total: int
    orders: list[OrderResponse]
