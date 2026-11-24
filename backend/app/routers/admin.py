# Purpose: Expose admin HTTP endpoints and connect request validation and dependencies to the application services.
"""Administrator-only foundation using existing JWT and transaction conventions."""
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Response
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session
from uuid import UUID
from app.schemas.admin import DriverVerification, DocumentDecision
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


# Wrap the service call at the HTTP boundary with cache policy and transaction/error handling.
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


# Validate search text and translate malformed input into a client error before building the query.
def query_text(q):
    try: return safe_text(q)
    except ValueError: raise HTTPException(422,'Search must be nonblank single-line text') from None


# Handle GET /overview through the declared request and dependency contract.
@router.get('/overview',response_model=AdminOverview)
def overview(response:Response,db:Database):
    return operation(db,response,lambda:service.overview(db),AdminOverview)


# Handle GET /users through the declared request and dependency contract.
@router.get('/users',response_model=AdminUsers)
def users(response:Response,db:Database,limit:Limit=20,offset:Offset=0,role:ManagedRole|None=None,status:AccountStatus|None=None,q:Search=None):
    q=query_text(q)
    return operation(db,response,lambda:service.users(db,limit,offset,role,status,q),AdminUsers)


# Handle GET /users/{user_id} through the declared request and dependency contract.
@router.get('/users/{user_id}',response_model=AdminUser)
def user_details(response:Response,db:Database,user_id:Id):
    return operation(db,response,lambda:service.user_data(service.managed_user(db,user_id)),AdminUser)


# Handle GET /users/{user_id}/businesses through the declared request and dependency contract.
@router.get('/users/{user_id}/businesses',response_model=OwnerBusinesses)
def user_businesses(response:Response,db:Database,user_id:Id,limit:Limit=20,offset:Offset=0):
    return operation(db,response,lambda:service.owner_businesses(db,user_id,limit,offset),OwnerBusinesses)


# Handle PATCH /users/{user_id}/status through the declared request and dependency contract.
@router.patch('/users/{user_id}/status',response_model=AdminUser)
def user_status(response:Response,user:Admin,db:Database,user_id:Id,payload:AccountDecision):
    return operation(db,response,lambda:service.account_status(db,user,user_id,payload),AdminUser,True)


# Handle GET /drivers through the declared request and dependency contract.
@router.get('/drivers',response_model=AdminDrivers)
def drivers(response:Response,db:Database,limit:Limit=20,offset:Offset=0,status:AccountStatus|None=None,approval_status:DriverApproval|None=None,q:Search=None):
    q=query_text(q)
    return operation(db,response,lambda:service.drivers(db,limit,offset,status,approval_status,q),AdminDrivers)


# Handle GET /drivers/{user_id} through the declared request and dependency contract.
@router.get('/drivers/{user_id}',response_model=AdminDriver)
def driver_details(response:Response,db:Database,user_id:Id):
    return operation(db,response,lambda:service.driver_detail(db,user_id),AdminDriver)


DOCUMENT_HEADERS={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
    'Content-Security-Policy':"default-src 'none'; sandbox; frame-ancestors 'none'",'Referrer-Policy':'no-referrer'}


# Translate document-service failures at the HTTP boundary without exposing private storage details.
def document_operation(db,callback):
    try:
        result=callback()
        db.commit()  # access/review audit is part of the operation
        return result
    except HTTPException as error:
        db.rollback();error.headers={**(error.headers or {}),**DOCUMENT_HEADERS};raise
    except Exception:
        try: db.rollback()
        except Exception: pass
        raise HTTPException(503,'Document operation could not be confirmed; refresh before proceeding',headers=DOCUMENT_HEADERS) from None


# Retrieve the authorized document bytes through the bounded document-response path.
def document_bytes(db,user,user_id,document_id,preview):
    from app.services.admin_driver_documents import retrieve
    data,media=document_operation(db,lambda:retrieve(db,user,user_id,str(document_id),'PREVIEWED' if preview else 'DOWNLOADED'))
    extension={'application/pdf':'pdf','image/png':'png','image/jpeg':'jpg'}[media]
    return Response(data,media_type=media,headers={**DOCUMENT_HEADERS,
        'Content-Disposition':f'{"inline" if preview else "attachment"}; filename="driver-document-{document_id}.{extension}"'})


# Handle GET /drivers/{user_id}/documents/{document_id}/preview through the declared request and dependency contract.
@router.get('/drivers/{user_id}/documents/{document_id}/preview')
def document_preview(user:Admin,db:Database,user_id:Id,document_id:UUID):
    return document_bytes(db,user,user_id,document_id,True)


# Handle GET /drivers/{user_id}/documents/{document_id}/download through the declared request and dependency contract.
@router.get('/drivers/{user_id}/documents/{document_id}/download')
def document_download(user:Admin,db:Database,user_id:Id,document_id:UUID):
    return document_bytes(db,user,user_id,document_id,False)


# Handle PATCH /drivers/{user_id}/documents/{document_id}/review through the declared request and dependency contract.
@router.patch('/drivers/{user_id}/documents/{document_id}/review',response_model=DriverVerification)
def document_review(response:Response,user:Admin,db:Database,user_id:Id,document_id:UUID,payload:DocumentDecision):
    from app.services.admin_driver_documents import review
    response.headers.update(DOCUMENT_HEADERS)
    return document_operation(db,lambda:DriverVerification.model_validate(review(db,user,user_id,str(document_id),payload.decision,payload.rejection_code)))


# Handle PATCH /drivers/{user_id}/decision through the declared request and dependency contract.
@router.patch('/drivers/{user_id}/decision',response_model=AdminDriver)
def driver_decision(response:Response,user:Admin,db:Database,user_id:Id,payload:DriverDecision):
    return operation(db,response,lambda:service.decide_driver(db,user,user_id,payload),AdminDriver,True)


# Handle GET /audit-events through the declared request and dependency contract.
@router.get('/audit-events',response_model=AuditEvents)
def audits(response:Response,db:Database,limit:Limit=20,offset:Offset=0,target_type:Literal['user','driver','business']|None=None):
    return operation(db,response,lambda:service.audit_events(db,limit,offset,target_type),AuditEvents)
