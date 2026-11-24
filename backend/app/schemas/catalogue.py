# Purpose: Define typed catalogue API payloads so incoming data is validated and outgoing fields have an explicit contract.
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


# Define the input field contract used when validating or serializing API data.
class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    # Validate plain text before the schema accepts the value.
    @field_validator('name', 'description', check_fields=False)
    @classmethod
    def plain_text(cls, value):
        if value is not None and any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('Use plain text without control characters')
        if value is not None and re.search(r'<\s*(?:/?[A-Za-z][\w:-]*|!)[^>]*>', value):
            raise ValueError('HTML markup is not supported')
        return value

    # Validate explicit values before the schema accepts the value.
    @model_validator(mode='after')
    def explicit_values(self):
        for key in self.model_fields_set:
            if getattr(self, key) is None and key not in {'description', 'category_id'}:
                raise ValueError(key + ' cannot be null')
        return self


# Define the category create field contract used when validating or serializing API data.
class CategoryCreate(Input):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = Field(default=True, strict=True)


# Define the category update field contract used when validating or serializing API data.
class CategoryUpdate(Input):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = Field(default=None, strict=True)


# Define the product input field contract used when validating or serializing API data.
class ProductInput(Input):
    # Validate decimal price before the schema accepts the value.
    @field_validator('unit_price', mode='before', check_fields=False)
    @classmethod
    def decimal_price(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError('Send a decimal string for unit_price, never a floating-point number')
        return value


# Define the product create field contract used when validating or serializing API data.
class ProductCreate(ProductInput):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    category_id: Identifier | None = None
    unit_price: Price
    currency: Literal['LKR'] = 'LKR'
    availability_status: Availability = 'available'
    publication_status: Literal['draft', 'published'] = 'draft'


# Define the product update field contract used when validating or serializing API data.
class ProductUpdate(ProductInput):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    category_id: Identifier | None = None
    unit_price: Price | None = None
    availability_status: Availability | None = None
    publication_status: Publication | None = None


# Define the category public field contract used when validating or serializing API data.
class CategoryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    category_id: int
    business_id: int
    name: str
    description: str | None


# Define the category owner field contract used when validating or serializing API data.
class CategoryOwner(CategoryPublic):
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Define the product public field contract used when validating or serializing API data.
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

    # Serialize price for the catalogue workflow.
    @field_serializer('unit_price')
    def serialize_price(self, value):
        return format(value, '.2f')


# Define the product owner field contract used when validating or serializing API data.
class ProductOwner(ProductPublic):
    publication_status: Publication
    created_at: datetime
    updated_at: datetime


# Define the shop public field contract used when validating or serializing API data.
class ShopPublic(BaseModel):
    business_id: int
    business_name: str
    product_count: int


# Define the page field contract used when validating or serializing API data.
class Page(BaseModel):
    page: int
    page_size: int
    total: int


# Define the owner categories field contract used when validating or serializing API data.
class OwnerCategories(Page):
    categories: list[CategoryOwner]


# Define the public categories field contract used when validating or serializing API data.
class PublicCategories(Page):
    categories: list[CategoryPublic]


# Define the owner products field contract used when validating or serializing API data.
class OwnerProducts(Page):
    products: list[ProductOwner]


# Define the public products field contract used when validating or serializing API data.
class PublicProducts(Page):
    products: list[ProductPublic]


# Define the shops field contract used when validating or serializing API data.
class Shops(Page):
    shops: list[ShopPublic]


# Define the catalogue summary field contract used when validating or serializing API data.
class CatalogueSummary(BaseModel):
    business_id: int
    total_products_count: int
    available_products_count: int
    categories_count: int
    unpublished_products_count: int
