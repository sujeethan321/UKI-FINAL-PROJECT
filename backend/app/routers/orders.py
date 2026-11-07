"""Customer-scoped and approved-owner-scoped order routes."""
from fastapi import APIRouter, Response, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.routers.catalogue import Customer, Owner, Database, BusinessId, Id, Page, Size
from app.schemas.order import Cart, OrderCreate, Decision, Quote, OrderResponse, Orders, Status
from app.services import order_service as service
customer_router=APIRouter(prefix='/customer/orders',tags=['Customer Orders'])
owner_router=APIRouter(prefix='/shop-owner/orders',tags=['Shop Owner Orders'])
def operation(db,response,action,schema,write=False):
    response.headers['Cache-Control']='no-store'
    try:
        result=schema.model_validate(action())
        if write:db.commit()
        return result
    except HTTPException:
        db.rollback();raise
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Order conflict. Retry the same request or refresh the order') from None
    except SQLAlchemyError:
        db.rollback();raise HTTPException(503,'Order operation unconfirmed. Retry with the same request key or refresh') from None
@customer_router.post('/quote',response_model=Quote)
def quote(response:Response,user:Customer,db:Database,payload:Cart):
    return operation(db,response,lambda:service.quote(db,user,payload),Quote)
@customer_router.post('',response_model=OrderResponse,status_code=201)
def create(response:Response,user:Customer,db:Database,payload:OrderCreate):
    return operation(db,response,lambda:service.create(db,user,payload),OrderResponse,True)
@customer_router.get('',response_model=Orders)
def customer_list(response:Response,user:Customer,db:Database,page:Page=1,page_size:Size=10,status:Status|None=None):
    return operation(db,response,lambda:service.listing(db,user,page,page_size,status),Orders)
@customer_router.get('/{order_id}',response_model=OrderResponse)
def customer_detail(response:Response,user:Customer,db:Database,order_id:Id):
    return operation(db,response,lambda:service.detail(db,user,order_id),OrderResponse)
@customer_router.post('/{order_id}/decision',response_model=OrderResponse)
def customer_decision(response:Response,user:Customer,db:Database,order_id:Id,payload:Decision):
    return operation(db,response,lambda:service.decide(db,user,order_id,payload.action),OrderResponse,True)
@owner_router.get('',response_model=Orders)
def owner_list(response:Response,user:Owner,db:Database,business_id:BusinessId,page:Page=1,page_size:Size=10,status:Status|None=None):
    return operation(db,response,lambda:service.listing(db,user,page,page_size,status,business_id),Orders)
@owner_router.get('/{order_id}',response_model=OrderResponse)
def owner_detail(response:Response,user:Owner,db:Database,business_id:BusinessId,order_id:Id):
    return operation(db,response,lambda:service.detail(db,user,order_id,business_id),OrderResponse)
@owner_router.post('/{order_id}/decision',response_model=OrderResponse)
def owner_decision(response:Response,user:Owner,db:Database,business_id:BusinessId,order_id:Id,payload:Decision):
    return operation(db,response,lambda:service.decide(db,user,order_id,payload.action,business_id),OrderResponse,True)
