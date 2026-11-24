"""Destination acceptance and minimal purpose-scoped projection.

Call before catalogue/order locks. Never reconstruct historical destinations.
Only trusted order/assignment scoping services call snapshot_projection.
"""
from sqlalchemy import select
from app.models.order_address import OrderDeliveryAddress
from app.services import customer_address_service as addresses
from app.services import customer_address_rollout as rollout

def destination(row):return {k:getattr(row,k) for k in ('recipient_name','phone','address_line','city')}

def acceptance(db,user,payload):
    if not rollout.enabled(True):
        if payload.address_id is not None or payload.address_version is not None:addresses.fail(503,'ADDRESS_CHECKOUT_DISABLED')
        return None
    rollout.require_ready(db,True)
    if payload.fulfilment_mode is None and payload.address_id is None and payload.address_version is None:return None
    if payload.fulfilment_mode=='pickup':
        if payload.address_id is not None or payload.address_version is not None:addresses.fail(422,'PICKUP_ADDRESS_NOT_ALLOWED')
        return None
    if payload.fulfilment_mode!='delivery' or payload.address_id is None or payload.address_version is None:addresses.fail(422,'ADDRESS_REQUIRED')
    row=addresses.selected(db,user,payload.address_id,payload.address_version)
    return dict(row=row,binding=[row.address_id,payload.address_version,addresses.digest(row)])

def persist(db,order,accepted):
    if accepted is None:return
    row=accepted['row']
    db.add(OrderDeliveryAddress(order_id=order.order_id,customer_user_id=order.customer_user_id,
        source_address_id=row.address_id,**destination(row),accepted_version=accepted['binding'][1],address_digest=accepted['binding'][2]))

def snapshot_projection(db,order_id):
    if not rollout.enabled(True):return None
    rollout.require_ready(db,True)
    row=db.scalar(select(OrderDeliveryAddress).where(OrderDeliveryAddress.order_id==order_id))
    return destination(row) if row else None
