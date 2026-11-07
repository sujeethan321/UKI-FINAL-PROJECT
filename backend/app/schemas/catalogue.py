"""Explicit catalogue inputs and separate owner/customer projections."""
from datetime import datetime
from decimal import Decimal
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

Availability = Literal['available', 'unavailable']
Publication = Literal['draft', 'published', 'archived']
Identifier = Annotated[int, Field(gt=0, le=9223372036854775807, strict=True)]
Price = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    @field_validator('name', 'description', check_fields=False)
    @classmethod
    def plain_text(cls, value):
        if value is not None and any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('Use plain text without control characters')
        if value is not None and re.search(r'<\s*(?:/?[A-Za-z][\w:-]*|!)[^>]*>', value):
            raise ValueError('HTML markup is not supported')
        return value

    @model_validator(mode='after')
    def explicit_values(self):
        for key in self.model_fields_set:
            if getattr(self, key) is None and key not in {'description', 'category_id'}:
                raise ValueError(key + ' cannot be null')
        return self


class CategoryCreate(Input):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = Field(default=True, strict=True)


class CategoryUpdate(Input):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = Field(default=None, strict=True)


class ProductInput(Input):
    @field_validator('unit_price', mode='before', check_fields=False)
    @classmethod
    def decimal_price(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError('Send a decimal string for unit_price, never a floating-point number')
        return value


class ProductCreate(ProductInput):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    category_id: Identifier | None = None
    unit_price: Price
    currency: Literal['LKR'] = 'LKR'
    availability_status: Availability = 'available'
    publication_status: Literal['draft', 'published'] = 'draft'


class ProductUpdate(ProductInput):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    category_id: Identifier | None = None
    unit_price: Price | None = None
    availability_status: Availability | None = None
    publication_status: Publication | None = None


class CategoryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    category_id: int
    business_id: int
    name: str
    description: str | None


class CategoryOwner(CategoryPublic):
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    business_id: int
    category_id: int | None
    category_name: str | None = None
    name: str
    description: str | None
    unit_price: Decimal
    currency: Literal['LKR']
    availability_status: Availability

    @field_serializer('unit_price')
    def serialize_price(self, value):
        return format(value, '.2f')


class ProductOwner(ProductPublic):
    publication_status: Publication
    created_at: datetime
    updated_at: datetime


class ShopPublic(BaseModel):
    business_id: int
    business_name: str
    product_count: int


class Page(BaseModel):
    page: int
    page_size: int
    total: int


class OwnerCategories(Page):
    categories: list[CategoryOwner]


class PublicCategories(Page):
    categories: list[CategoryPublic]


class OwnerProducts(Page):
    products: list[ProductOwner]


class PublicProducts(Page):
    products: list[ProductPublic]


class Shops(Page):
    shops: list[ShopPublic]


class CatalogueSummary(BaseModel):
    business_id: int
    total_products_count: int
    available_products_count: int
    categories_count: int
    unpublished_products_count: int
