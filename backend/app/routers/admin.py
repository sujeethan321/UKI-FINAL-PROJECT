"""Administrator-only foundation using existing JWT and transaction conventions."""
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Response
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session
from app.core.auth_dependencies import require_admin
from app.core.database import get_db
from app.models import User
from app.schemas.admin import (AdminUser,AdminUsers,AdminDriver,AdminDrivers,AdminOverview,
    OwnerBusinesses,AuditEvents,DriverDecision,AccountDecision,ManagedRole,AccountStatus,DriverApproval,safe_text)
from app.services import admin_service as service

router=APIRouter(prefix='/admin',tags=['Administrator'],dependencies=[Depends(require_admin)])
Admin=Annotated[User,Depends(require_admin)]
Database=Annotated[Session,Depends(get_db)]
Limit=Annotated[int,Query(ge=1,le=100)]
Offset=Annotated[int,Query(ge=0,le=1000000)]
Id=Annotated[int,Path(gt=0,le=9223372036854775807)]
Search=Annotated[str|None,Query(min_length=1,max_length=100)]


def operation(db,response,action,schema,write=False):
    response.headers['Cache-Control']='no-store'
    try:
        result=schema.model_validate(action())
        if write: db.commit()
        return result
    except HTTPException:
        db.rollback(); raise
    except IntegrityError:
        db.rollback(); raise HTTPException(409,'Administrator operation conflicted; refresh the target') from None
    except SQLAlchemyError as error:
        db.rollback()
        # MySQL ER_NO_SUCH_TABLE: distinguish missing schema from connectivity
        # without returning database/table names, SQL, parameters or financial data.
        if getattr(getattr(error,'orig',None),'args',())[0:1] == (1146,):
            raise HTTPException(503,detail={
                'code':'ADMIN_SCHEMA_UNAVAILABLE',
                'message':'Required Administrator database structures are unavailable. Contact the platform operator.',
            }) from None
        raise HTTPException(503,'Administrator operation could not be confirmed; refresh before retrying') from None


def query_text(q):
    try: return safe_text(q)
    except ValueError: raise HTTPException(422,'Search must be nonblank single-line text') from None


@router.get('/overview',response_model=AdminOverview)
def overview(response:Response,db:Database):
    return operation(db,response,lambda:service.overview(db),AdminOverview)


@router.get('/users',response_model=AdminUsers)
def users(response:Response,db:Database,limit:Limit=20,offset:Offset=0,role:ManagedRole|None=None,status:AccountStatus|None=None,q:Search=None):
    q=query_text(q)
    return operation(db,response,lambda:service.users(db,limit,offset,role,status,q),AdminUsers)


@router.get('/users/{user_id}',response_model=AdminUser)
def user_details(response:Response,db:Database,user_id:Id):
    return operation(db,response,lambda:service.user_data(service.managed_user(db,user_id)),AdminUser)


@router.get('/users/{user_id}/businesses',response_model=OwnerBusinesses)
def user_businesses(response:Response,db:Database,user_id:Id,limit:Limit=20,offset:Offset=0):
    return operation(db,response,lambda:service.owner_businesses(db,user_id,limit,offset),OwnerBusinesses)


@router.patch('/users/{user_id}/status',response_model=AdminUser)
def user_status(response:Response,user:Admin,db:Database,user_id:Id,payload:AccountDecision):
    return operation(db,response,lambda:service.account_status(db,user,user_id,payload),AdminUser,True)


@router.get('/drivers',response_model=AdminDrivers)
def drivers(response:Response,db:Database,limit:Limit=20,offset:Offset=0,status:AccountStatus|None=None,approval_status:DriverApproval|None=None,q:Search=None):
    q=query_text(q)
    return operation(db,response,lambda:service.drivers(db,limit,offset,status,approval_status,q),AdminDrivers)


@router.get('/drivers/{user_id}',response_model=AdminDriver)
def driver_details(response:Response,db:Database,user_id:Id):
    return operation(db,response,lambda:service.driver_detail(db,user_id),AdminDriver)


@router.patch('/drivers/{user_id}/decision',response_model=AdminDriver)
def driver_decision(response:Response,user:Admin,db:Database,user_id:Id,payload:DriverDecision):
    return operation(db,response,lambda:service.decide_driver(db,user,user_id,payload),AdminDriver,True)


@router.get('/audit-events',response_model=AuditEvents)
def audits(response:Response,db:Database,limit:Limit=20,offset:Offset=0,target_type:Literal['user','driver','business']|None=None):
    return operation(db,response,lambda:service.audit_events(db,limit,offset,target_type),AuditEvents)
