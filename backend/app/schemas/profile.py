# Purpose: Define typed profile API payloads so incoming data is validated and outgoing fields have an explicit contract.
"""Personal display preferences only. No contact, credential or approval writes."""
import unicodedata
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator

# Define the profile update field contract used when validating or serializing API data.
class ProfileUpdate(BaseModel):
    # Reject unexpected keys instead of silently accepting attempts to change contact details or account privileges.
    model_config=ConfigDict(extra='forbid')
    full_name:str|None=Field(default=None,min_length=2,max_length=150,strict=True)
    preferred_language:Literal['en','ta','si']|None=None

    # Validate display name before the schema accepts the value.
    @field_validator('full_name',mode='before')
    @classmethod
    def display_name(cls,value):
        if not isinstance(value,str) or len(value)>512:raise ValueError('Enter a valid display name')
        # Keep joiners needed by some writing systems while rejecting other invisible control characters.
        if any(unicodedata.category(c).startswith('C') and c not in '\u200c\u200d' for c in value):raise ValueError('Control characters are not allowed')
        if not any(unicodedata.category(c)[0] in ('L','N','S','P') for c in value):raise ValueError('Enter a visible display name')
        # Normalize equivalent Unicode spellings and whitespace so stored names and revision comparisons are consistent.
        return unicodedata.normalize('NFC',' '.join(value.split()))

    # Validate language before the schema accepts the value.
    @field_validator('preferred_language',mode='before')
    @classmethod
    def language(cls,value):
        if value not in ('en','ta','si'):raise ValueError('Choose English, Tamil or Sinhala')
        return value

    # Validate nonempty before the schema accepts the value.
    @model_validator(mode='after')
    def nonempty(self):
        if not self.model_fields_set:raise ValueError('Provide at least one editable profile field')
        return self

# Define the profile response field contract used when validating or serializing API data.
class ProfileResponse(BaseModel):
    model_config=ConfigDict(extra='forbid')
    user_id:int
    full_name:str
    preferred_language:Literal['en','ta','si']
    email:str
    phone:str|None
    platform_role:str
    account_status:str
    revision:str
