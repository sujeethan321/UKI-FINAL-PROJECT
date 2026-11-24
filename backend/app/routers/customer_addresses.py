from typing import Annotated
from fastapi import APIRouter,Depends,Response,Request,Query,HTTPException,Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.core.rate_limit import _consume
from app.models.user import User
from app.schemas.customer_address import AddressCreate,AddressUpdate,AddressVersion,DefaultAddress
from app.services import customer_address_service as service

router=APIRouter(prefix='/customer/addresses',tags=['Customer addresses'])
Identity=Annotated[User,Depends(require_roles('customer'))]
Database=Annotated[Session,Depends(get_db)]
AddressId=Annotated[int,Path(gt=0,le=9223372036854775807)]

def operation(db,user,response,request,callback,write=False):
    response.headers.update(service.HEADERS)
    if hasattr(request.app.state,'rate_limit_config'):_consume(request,[('address-write' if write else 'address-read',str(user.user_id),20 if write else 60)])
    try:
        result=callback()
        if write:db.commit()
        return result
    except HTTPException:db.rollback();raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503,'Address operation could not be confirmed. Reload before retrying the same request.',headers=service.HEADERS) from None

@router.get('')
def listing(db:Database,user:Identity,response:Response,request:Request,page:Annotated[int,Query(ge=1,le=1000)]=1,page_size:Annotated[int,Query(ge=1,le=50)]=10,archived:bool=False):
    return operation(db,user,response,request,lambda:service.listing(db,user,page,page_size,archived))

@router.post('')
def create(payload:AddressCreate,db:Database,user:Identity,response:Response,request:Request):
    return operation(db,user,response,request,lambda:service.mutate(db,user,payload,'create'),True)

@router.put('/default')
def default(payload:DefaultAddress,db:Database,user:Identity,response:Response,request:Request):
    return operation(db,user,response,request,lambda:service.mutate(db,user,payload,'default'),True)

@router.patch('/{address_id}')
def edit(address_id:AddressId,payload:AddressUpdate,db:Database,user:Identity,response:Response,request:Request):
    return operation(db,user,response,request,lambda:service.mutate(db,user,payload,'edit',address_id),True)

@router.delete('/{address_id}')
def archive(address_id:AddressId,payload:AddressVersion,db:Database,user:Identity,response:Response,request:Request):
    return operation(db,user,response,request,lambda:service.mutate(db,user,payload,'archive',address_id),True)
