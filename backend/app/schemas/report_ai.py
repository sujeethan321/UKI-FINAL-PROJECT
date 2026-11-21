from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReportAIRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str = Field(min_length=3, max_length=1500)
    language: Literal['en', 'ta', 'si'] = 'en'
    start_date: date
    end_date: date

    @field_validator('prompt')
    @classmethod
    def safe_prompt(cls, value):
        value=value.strip()
        if len(value)<3 or len(value.encode('utf-8'))>6000 or any(ord(c)<32 and c not in '\n\t' for c in value):
            raise ValueError('Enter a valid analysis question')
        return value
