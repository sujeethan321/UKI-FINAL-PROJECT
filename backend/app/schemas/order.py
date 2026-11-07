from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal['submitted','approved','rejected','processing','completed','cancelled']
PositiveId = Annotated[int, Field(strict=True,gt=0,le=9223372036854775807)]
class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
class CartItem(Input):
    product_id: PositiveId
    quantity: int = Field(strict=True,ge=1,le=99)
class Cart(Input):
    business_id: PositiveId
    items: list[CartItem] = Field(min_length=1,max_length=50)
    @model_validator(mode='after')
    def unique_products(self):
        if len({i.product_id for i in self.items}) != len(self.items):
            raise ValueError('Duplicate products are not allowed')
        return self
class OrderCreate(Cart):
    payment_method: Literal['cash','credit']
    request_key: str = Field(min_length=16,max_length=100,pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]*$')
class Decision(Input):
    action: Literal['approve','reject','process','complete','cancel']
class Line(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price: str
    line_total: str
class Quote(BaseModel):
    business_id: int
    business_name: str
    currency: Literal['LKR'] = 'LKR'
    items: list[Line]
    subtotal: str
    total: str
    credit_available: bool
    credit_guidance: str
class OrderResponse(BaseModel):
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
class Orders(BaseModel):
    page: int
    page_size: int
    total: int
    orders: list[OrderResponse]
