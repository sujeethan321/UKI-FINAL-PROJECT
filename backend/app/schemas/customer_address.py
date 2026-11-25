# Purpose: Define typed customer address API payloads so incoming data is validated and outgoing fields have an explicit contract.
"""Customer-owned address book; no client ownership or verification claims."""
import unicodedata
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator

Positive = Annotated[int, Field(strict=True, gt=0, le=9223372036854775807)]

# Define the address fields field contract used when validating or serializing API data.
class AddressFields(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str = Field(min_length=1, max_length=50)
    recipient_name: str = Field(min_length=1, max_length=150)
    address_line: str = Field(min_length=1, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=20)

    # Validate clean before the schema accepts the value.
    @field_validator('label','recipient_name','address_line','city','phone', mode='before')
    @classmethod
    def clean(cls, value, info):
        if value is None and info.field_name in ('city','phone'): return None
        if not isinstance(value,str): raise ValueError('Text required')
        value=unicodedata.normalize('NFC',value.replace('\r\n','\n')).strip()
        for char in value:
            if char=='\n' and info.field_name=='address_line': continue
            if unicodedata.category(char).startswith('C') and char not in ('\u200c','\u200d'):
                raise ValueError('Unsupported control character')
        if not any(not ch.isspace() and unicodedata.category(ch)[0] not in ('C','M') for ch in value):
            if info.field_name in ('city','phone'): return None
            raise ValueError('Visible text required')
        return value

# Define the address create field contract used when validating or serializing API data.
class AddressCreate(AddressFields):
    version: Positive
    request_key: str = Field(min_length=16,max_length=100,pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]*$')

# Define the address update field contract used when validating or serializing API data.
class AddressUpdate(AddressFields):
    # Full editable projection on PATCH avoids ambiguous null/omission behavior.
    version: Positive

# Define the address version field contract used when validating or serializing API data.
class AddressVersion(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version: Positive

# Define the default address field contract used when validating or serializing API data.
class DefaultAddress(AddressVersion):
    address_id: Positive | None

# Define the destination field contract used when validating or serializing API data.
class Destination(BaseModel):
    recipient_name: str
    phone: str | None
    address_line: str
    city: str | None
