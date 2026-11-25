# Purpose: Expose profile HTTP endpoints and connect request validation and dependencies to the application services.
from typing import Annotated
from fastapi import APIRouter,Depends,Header,HTTPException,Request,Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.core.rate_limit import _consume
from app.models.user import User
from app.schemas.profile import ProfileResponse,ProfileUpdate
from app.services import profile_service as service

router=APIRouter(prefix='/account/profile',tags=['Personal profile'])
Database=Annotated[Session,Depends(get_db)]
Identity=Annotated[User,Depends(get_current_user)]

# Apply shared response headers, request budgets, and transaction/error handling around the service operation.
def operation(db,response,request,user,callback,write=False):
    response.headers.update(service.HEADERS)
    if hasattr(request.app.state,'rate_limit_config'):
        _consume(request,[('personal-profile-write' if write else 'personal-profile-read',str(user.user_id),10 if write else 60)])
    try:
        result=callback()
        # Commit only mutations; service helpers can flush without deciding the transaction outcome themselves.
        if write:db.commit()
        # Return the same opaque revision used by If-Match so a client can base its next edit on the displayed profile.
        response.headers['ETag']='"'+result.revision+'"'
        return result
    except HTTPException:
        db.rollback();raise
    except SQLAlchemyError:
        db.rollback();raise HTTPException(503,'Profile update could not be confirmed. Reload your profile before continuing.',headers=service.HEADERS) from None

# Read /account/profile using the authenticated user dependency rather than an arbitrary user ID.
@router.get('',response_model=ProfileResponse)
def read(response:Response,request:Request,user:Identity,db:Database):
    return operation(db,response,request,user,lambda:service.read(db,user))

# Require a correctly shaped If-Match revision before attempting the authenticated personal-profile update.
@router.patch('',response_model=ProfileResponse)
def update(response:Response,request:Request,user:Identity,db:Database,payload:ProfileUpdate,
           if_match:Annotated[str,Header(min_length=67,max_length=69,pattern=r'^"?p1-[a-f0-9]{64}"?$')]):
    return operation(db,response,request,user,lambda:service.update(db,user,payload,if_match.strip('"')),True)
