# Purpose: Expose support HTTP endpoints and connect request validation and dependencies to the application services.
"""Support endpoints commit only support evidence and in-app notifications."""
from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException,Path,Query,Request,Response
from sqlalchemy.exc import SQLAlchemyError,IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_dependencies import require_roles
from app.core.rate_limit import _consume
from app.models import User
from app.schemas.support import CreateCase,Command,CaseFilters
from app.services import support_service as service
from app.services.support_rollout import HEADERS

router=APIRouter(prefix='/support/cases',tags=['Support'])
Database=Annotated[Session,Depends(get_db)]
Requester=Annotated[User,Depends(require_roles('customer','shop_owner','driver'))]
Reference=Annotated[str,Path(pattern=r'^SUP-[a-f0-9]{32}$')]
Selection=Annotated[CaseFilters,Depends()]

# Apply support request budgets and commit or roll back the case operation at the HTTP boundary.
def perform(db,response,request,user,callback,write=False):
    response.headers.update(HEADERS)
    if hasattr(request.app.state,'rate_limit_config'):
        _consume(request,[('support-write' if write else 'support-read',str(user.user_id),10 if write else 60)])
    try:
        result=callback()
        if write:db.commit()
        return result
    except HTTPException as error:
        db.rollback();error.headers={**(error.headers or {}),**HEADERS};raise
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Support request conflicted; refresh and retry the same request',headers=HEADERS) from None
    except SQLAlchemyError:
        db.rollback();raise HTTPException(503,'Support result could not be confirmed. Refresh before retrying the same request.',headers=HEADERS) from None

# Handle POST  through the declared request and dependency contract.
@router.post('')
def create(response:Response,request:Request,user:Requester,db:Database,payload:CreateCase):
    return perform(db,response,request,user,lambda:service.create(db,user,payload),True)

# Handle GET  through the declared request and dependency contract.
@router.get('')
def cases(response:Response,request:Request,user:Requester,db:Database,filters:Selection):
    return perform(db,response,request,user,lambda:service.list_cases(db,user,filters))

# Handle GET /{reference} through the declared request and dependency contract.
@router.get('/{reference}')
def detail(response:Response,request:Request,user:Requester,db:Database,reference:Reference):
    return perform(db,response,request,user,lambda:service.detail(db,user,reference))

# Handle POST /{reference}/actions through the declared request and dependency contract.
@router.post('/{reference}/actions')
def action(response:Response,request:Request,user:Requester,db:Database,reference:Reference,payload:Command):
    return perform(db,response,request,user,lambda:service.command(db,user,reference,payload),True)

# Handle GET /{reference}/history/{kind} through the declared request and dependency contract.
@router.get('/{reference}/history/{kind}')
def history(response:Response,request:Request,user:Requester,db:Database,reference:Reference,kind:Annotated[str,Path(pattern='^(messages|events)$')],limit:Annotated[int,Query(ge=1,le=100)]=100,offset:Annotated[int,Query(ge=0,le=10000)]=0):
    return perform(db,response,request,user,lambda:service.history(db,user,reference,kind,limit,offset))
