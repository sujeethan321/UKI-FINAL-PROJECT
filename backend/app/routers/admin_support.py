# Purpose: Expose admin support HTTP endpoints and connect request validation and dependencies to the application services.
from typing import Annotated
from fastapi import APIRouter,Depends,Path,Query,Request,Response
from app.core.auth_dependencies import require_admin
from app.models import User
from app.schemas.support import Command
from app.services import support_admin_service as service
from app.services.support_service import history as read_history
from app.routers.support import Database,Reference,Selection,perform

router=APIRouter(prefix='/admin/support/cases',tags=['Admin Support'])
Admin=Annotated[User,Depends(require_admin)]

# Handle GET  through the declared request and dependency contract.
@router.get('')
def cases(response:Response,request:Request,user:Admin,db:Database,filters:Selection):
    return perform(db,response,request,user,lambda:service.cases(db,user,filters))

# Handle GET /{reference} through the declared request and dependency contract.
@router.get('/{reference}')
def detail(response:Response,request:Request,user:Admin,db:Database,reference:Reference):
    return perform(db,response,request,user,lambda:service.case(db,user,reference))

# Handle POST /{reference}/actions through the declared request and dependency contract.
@router.post('/{reference}/actions')
def action(response:Response,request:Request,user:Admin,db:Database,reference:Reference,payload:Command):
    return perform(db,response,request,user,lambda:service.update(db,user,reference,payload),True)

# Handle GET /{reference}/history/{kind} through the declared request and dependency contract.
@router.get('/{reference}/history/{kind}')
def history(response:Response,request:Request,user:Admin,db:Database,reference:Reference,kind:Annotated[str,Path(pattern='^(messages|events)$')],limit:Annotated[int,Query(ge=1,le=100)]=100,offset:Annotated[int,Query(ge=0,le=10000)]=0):
    return perform(db,response,request,user,lambda:read_history(db,user,reference,kind,limit,offset,True))
