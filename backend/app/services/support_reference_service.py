# Purpose: Check access to records attached to a support case so a guessed identifier cannot disclose another account record.
"""Validate references using current ownership; no financial mutations or documents."""
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.models import Business,BusinessMember,CustomerProfile,CreditAccount,LedgerEntry,Order,DeliveryRequest,DeliveryAssignment

# Return the same unavailable-record error for inaccessible or missing support references.
def missing():raise HTTPException(404,'Related record is unavailable for this account')

# Resolve owner using a row lock so the caller can coordinate concurrent changes.
def owner(db,user_id,business_id):
    return db.scalar(select(BusinessMember.business_id).where(BusinessMember.business_id==business_id,
        BusinessMember.user_id==user_id,BusinessMember.business_role=='owner',BusinessMember.membership_status=='active').with_for_update(read=True)) is not None

# Query business access data for the support reference workflow.
def business_access(db,user,business_id):
    if user.platform_role=='shop_owner':return owner(db,user.user_id,business_id)
    if user.platform_role=='customer':
        return db.scalar(select(CustomerProfile.customer_id).where(CustomerProfile.business_id==business_id,CustomerProfile.user_id==user.user_id).limit(1)) is not None
    return False

# Query account access data for the support reference workflow.
def account_access(db,user,account):
    if account is None:missing()
    if user.platform_role=='shop_owner' and owner(db,user.user_id,account.creditor_business_id):return account.creditor_business_id
    if user.platform_role=='customer':
        profile=db.scalar(select(CustomerProfile).where(CustomerProfile.customer_id==account.customer_id,CustomerProfile.user_id==user.user_id,
            CustomerProfile.business_id==account.creditor_business_id))
        if profile:return account.creditor_business_id
    missing()

# Query validate data for the support reference workflow.
def validate(db,user,payload):
    related=payload.related;derived=None;values={}
    if related:
        if related.kind=='earning':
            from app.services.driver_finance_rollout import require_ready
            require_ready(db)  # Before any optional finance-table SELECT.
            from app.models.driver_finance import DriverEarning
            try:ident=str(UUID(related.record_id))
            except ValueError:missing()
            earning=db.scalar(select(DriverEarning).where(DriverEarning.earning_id==ident,DriverEarning.driver_user_id==user.user_id)) if user.platform_role=='driver' else None
            if earning is None:missing()
            delivery=db.get(DeliveryRequest,earning.delivery_request_id)
            derived=delivery.business_id;values={'earning_id':ident}
        else:
            try:
                ident=int(related.record_id)
                if not 0<ident<=9223372036854775807 or str(ident)!=related.record_id:missing()
            except ValueError:missing()
            if related.kind=='order':
                row=db.get(Order,ident)
                if row is None:missing()
                allowed=(user.platform_role=='customer' and row.customer_user_id==user.user_id) or (user.platform_role=='shop_owner' and owner(db,user.user_id,row.business_id))
                if user.platform_role=='driver' and row.delivery_request_id:
                    allowed=db.scalar(select(DeliveryAssignment.assignment_id).where(DeliveryAssignment.delivery_request_id==row.delivery_request_id,DeliveryAssignment.driver_user_id==user.user_id)) is not None
                if not allowed:missing()
                derived=row.business_id;values={'order_id':ident}
            elif related.kind=='delivery':
                row=db.get(DeliveryRequest,ident)
                if row is None:missing()
                allowed=user.platform_role=='shop_owner' and owner(db,user.user_id,row.business_id)
                if user.platform_role=='customer':allowed=db.scalar(select(Order.order_id).where(Order.delivery_request_id==ident,Order.customer_user_id==user.user_id)) is not None
                if user.platform_role=='driver':allowed=db.scalar(select(DeliveryAssignment.assignment_id).where(DeliveryAssignment.delivery_request_id==ident,DeliveryAssignment.driver_user_id==user.user_id)) is not None
                if not allowed:missing()
                derived=row.business_id;values={'delivery_id':ident}
            else:
                if related.kind=='ledger_entry':
                    entry=db.get(LedgerEntry,ident)
                    if entry is None:missing()
                    account=db.get(CreditAccount,entry.credit_account_id);values={'ledger_entry_id':ident}
                else:account=db.get(CreditAccount,ident);values={'credit_account_id':ident}
                derived=account_access(db,user,account)
    if payload.business_id is not None:
        if derived is not None and derived!=payload.business_id:missing()
        if derived is None:
            if not business_access(db,user,payload.business_id):missing()
            derived=payload.business_id
    if payload.business_shared and derived is None:raise HTTPException(422,'Business sharing requires an authorized business reference')
    return derived,values
