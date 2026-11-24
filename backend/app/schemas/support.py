"""Strict commands. Creator/role and financial state are never client authority."""
from datetime import date
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator

Category=Literal['account','credit_sale','repayment','credit_balance','order','delivery','driver_fee','other']
Status=Literal['open','assigned','investigating','awaiting_user','resolved','closed']
Priority=Literal['low','normal','high','urgent']

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    @field_validator('*')
    @classmethod
    def plain(cls,value):
        if isinstance(value,str) and (not value or any(ord(c)<32 and c not in '\n\t' for c in value)):
            raise ValueError('Use nonblank plain text without control characters')
        return value

class Reference(Strict):
    kind:Literal['order','delivery','credit_account','ledger_entry','earning']
    record_id:str=Field(min_length=1,max_length=36)

class CreateCase(Strict):
    category:Category
    subject:str=Field(min_length=3,max_length=120)
    description:str=Field(min_length=10,max_length=4000)
    business_id:int|None=Field(default=None,gt=0,le=9223372036854775807)
    business_shared:bool=False
    related:Reference|None=None
    request_key:str=Field(min_length=16,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')

class Command(Strict):
    action:Literal['message','internal_note','assignment','priority','status','reopen']
    expected_version:int=Field(ge=1)
    request_key:str=Field(min_length=16,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')
    body:str|None=Field(default=None,min_length=1,max_length=4000)
    admin_id:int|None=Field(default=None,gt=0,le=9223372036854775807)
    priority:Priority|None=None
    status:Status|None=None
    reason:str|None=Field(default=None,min_length=3,max_length=2000)

    @model_validator(mode='after')
    def fields_match(self):
        required={'message':{'body'},'internal_note':{'body'},'assignment':{'admin_id'},'priority':{'priority'},'status':{'status','reason'},'reopen':{'reason'}}[self.action]
        present={key for key in ('body','admin_id','priority','status','reason') if getattr(self,key) is not None}
        if present!=required:raise ValueError('Fields do not match this support action')
        return self

class CaseFilters(Strict):
    status:Status|None=None
    category:Category|None=None
    priority:Priority|None=None
    start_date:date|None=None
    end_date:date|None=None
    limit:int=Field(default=20,ge=1,le=100)
    offset:int=Field(default=0,ge=0,le=10000)
