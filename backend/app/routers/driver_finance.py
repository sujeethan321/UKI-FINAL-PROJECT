"""Scoped, no-store finance reads and transactional direct-collection events."""
from decimal import Decimal
from typing import Literal, Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Response, HTTPException, Query, Path
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.core.auth_dependencies import require_roles, require_admin
from app.core.database import get_db
from app.models import User
from app.services import driver_finance_service as service

router=APIRouter(tags=['Driver direct finance'])


class Command(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_key:str=Field(min_length=16,max_length=100,pattern=r'^[A-Za-z0-9._:-]+$')
    evidence:str=Field(min_length=10,max_length=1000)
    @field_validator('evidence')
    @classmethod
    def clean(cls,value):
        value=value.strip()
        if len(value)<10 or any(ord(c)<32 for c in value):raise ValueError('Provide a printable evidence reference or review note')
        return value


class Collection(Command):
    kind:Literal['declared','exception']
    amount:Decimal=Field(ge=0,max_digits=14,decimal_places=2)


class Verification(Command):
    kind:Literal['direct_settled','disputed','reversed','refund_confirmed']
    collection_id:UUID|None=None


def run(db,response,action,write=False):
    response.headers['Cache-Control']='no-store'
    try:
        result=action()
        if write:db.commit()
        return result
    except HTTPException as error:
        db.rollback()
        error.headers={**(error.headers or {}),'Cache-Control':'no-store'}
        raise
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Financial operation conflicts; refresh recorded history before retrying',headers={'Cache-Control':'no-store'}) from None
    except SQLAlchemyError:
        db.rollback();raise HTTPException(503,'Driver accounting unavailable; required schema or connection must be verified',headers={'Cache-Control':'no-store'}) from None


@router.get('/driver/earnings')
def earnings(response:Response,page:int=Query(1,ge=1,le=100000),page_size:int=Query(20,ge=1,le=50),period:Literal['day','week','month']='month',
             user:User=Depends(require_roles('driver')),db:Session=Depends(get_db)):
    return run(db,response,lambda:service.history(db,user,page,page_size,period=period))


@router.post('/driver/earnings/{earning_id}/collections')
def declare(earning_id:UUID,payload:Collection,response:Response,user:User=Depends(require_roles('driver')),db:Session=Depends(get_db)):
    return run(db,response,lambda:service.operation(db,user,str(earning_id),payload),True)


@router.get('/admin/drivers/{driver_id}/earnings')
def admin_history(driver_id:Annotated[int,Path(gt=0,le=9223372036854775807)],response:Response,page:int=Query(1,ge=1,le=100000),page_size:int=Query(20,ge=1,le=50),
                  user:User=Depends(require_admin),db:Session=Depends(get_db)):
    return run(db,response,lambda:service.history(db,user,page,page_size,driver_id))


@router.post('/admin/driver-earnings/{earning_id}/verification')
def verify(earning_id:UUID,payload:Verification,response:Response,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    return run(db,response,lambda:service.operation(db,user,str(earning_id),payload,admin=True),True)
