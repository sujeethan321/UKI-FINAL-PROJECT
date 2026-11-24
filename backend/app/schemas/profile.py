"""Personal display preferences only. No contact, credential or approval writes."""
import unicodedata
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator

class ProfileUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    full_name:str|None=Field(default=None,min_length=2,max_length=150,strict=True)
    preferred_language:Literal['en','ta','si']|None=None

    @field_validator('full_name',mode='before')
    @classmethod
    def display_name(cls,value):
        if not isinstance(value,str) or len(value)>512:raise ValueError('Enter a valid display name')
        if any(unicodedata.category(c).startswith('C') and c not in '\u200c\u200d' for c in value):raise ValueError('Control characters are not allowed')
        if not any(unicodedata.category(c)[0] in ('L','N','S','P') for c in value):raise ValueError('Enter a visible display name')
        return unicodedata.normalize('NFC',' '.join(value.split()))

    @field_validator('preferred_language',mode='before')
    @classmethod
    def language(cls,value):
        if value not in ('en','ta','si'):raise ValueError('Choose English, Tamil or Sinhala')
        return value

    @model_validator(mode='after')
    def nonempty(self):
        if not self.model_fields_set:raise ValueError('Provide at least one editable profile field')
        return self

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
