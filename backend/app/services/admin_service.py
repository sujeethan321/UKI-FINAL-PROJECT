"""Bounded platform management; no financial writes or impersonation."""
from fastapi import HTTPException
from sqlalchemy import select, func, or_, literal, union_all
from app.models import (User, Business, BusinessMember, DriverProfile, Order,
    DeliveryRequest, DeliveryAssignment, AdminAudit, BusinessApprovalAudit)
from app.services import driver_service
from app.services.notification_service import notify_event


ROLES=('shop_owner','customer','driver')
USER_FIELDS=('user_id','full_name','email','platform_role','account_status','created_at')


def admin_actor(db,user):
    return driver_service.actor(db,user.user_id,'admin',lock=True)


def current(db,query,shared=True):
    return db.scalar(query.with_for_update(read=shared).execution_options(populate_existing=True))


def search(query,fields,q):
    if q is not None:
        value=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        query=query.where(or_(*(field.like('%'+value+'%',escape='\\') for field in fields)))
    return query


def user_data(row):
    return {key:getattr(row,key) for key in USER_FIELDS}


def managed_user(db,ident,role=None):
    row=db.scalar(select(User).where(User.user_id==ident,User.platform_role.in_(ROLES)))
    if row is None or role and row.platform_role!=role:
        raise HTTPException(404,'Managed user not found')
    return row


def user_query(role=None,status=None,q=None):
    query=select(User).where(User.platform_role==role if role else User.platform_role.in_(ROLES))
    if status: query=query.where(User.account_status==status)
    return search(query,[User.full_name,User.email],q)


def users(db,limit,offset,role=None,status=None,q=None):
    query=user_query(role,status,q)
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.scalars(query.order_by(User.created_at.desc(),User.user_id.desc()).limit(limit).offset(offset))
    return dict(total=total,limit=limit,offset=offset,users=[user_data(row) for row in rows])


def profile_data(row):
    return {key:getattr(row,key) for key in ('approval_status','vehicle_type','registration_reference','reviewed_by','reviewed_at')} if row else None


def driver_detail(db,ident):
    user=managed_user(db,ident,'driver')
    from app.services.admin_driver_documents import verification
    profile=current(db,select(DriverProfile).where(DriverProfile.user_id==ident),False)
    return dict(**user_data(user),profile=profile_data(profile),verification=verification(db,ident,profile))


def drivers(db,limit,offset,status=None,approval=None,q=None):
    query=user_query('driver',status,q).outerjoin(DriverProfile,DriverProfile.user_id==User.user_id)
    if approval: query=query.where(DriverProfile.user_id.is_(None) if approval=='not_submitted' else DriverProfile.approval_status==approval)
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.execute(query.add_columns(DriverProfile).order_by(User.created_at.desc(),User.user_id.desc()).limit(limit).offset(offset))
    return dict(total=total,limit=limit,offset=offset,drivers=[dict(**user_data(user),profile=profile_data(profile)) for user,profile in rows])


def owner_businesses(db,ident,limit,offset):
    managed_user(db,ident,'shop_owner')
    query=select(Business,BusinessMember).join(BusinessMember,BusinessMember.business_id==Business.business_id).where(BusinessMember.user_id==ident)
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.execute(query.order_by(Business.business_id).limit(limit).offset(offset))
    return dict(user_id=ident,total=total,limit=limit,offset=offset,businesses=[dict(
        business_id=b.business_id,business_name=b.business_name,approval_status=b.approval_status,
        membership_status=m.membership_status,business_role=m.business_role) for b,m in rows])


def overview(db):
    def count(model,*where): return select(func.count()).select_from(model).where(*where).scalar_subquery()
    fields={
        'total_shop_owners':count(User,User.platform_role=='shop_owner'),
        'total_customers':count(User,User.platform_role=='customer'),
        'total_drivers':count(User,User.platform_role=='driver'),
        'pending_driver_approvals':count(DriverProfile,DriverProfile.approval_status=='pending'),
        'approved_drivers':count(DriverProfile,DriverProfile.approval_status=='approved'),
        'total_businesses':count(Business),
        'pending_business_approvals':count(Business,Business.approval_status=='pending'),
        'approved_businesses':count(Business,Business.approval_status=='approved'),
        'total_orders':count(Order),'total_delivery_requests':count(DeliveryRequest),
    }
    return dict(db.execute(select(*(value.label(key) for key,value in fields.items()))).mappings().one())


def audit(db,actor,target_type,target_id,action,previous,new,reason):
    row=AdminAudit(admin_user_id=actor.user_id,target_type=target_type,target_id=target_id,
        action=action,previous_state=previous,new_state=new,reason=reason)
    db.add(row); db.flush(); return row


def active_assignments(db,ident):
    return db.scalar(select(DeliveryAssignment.assignment_id).join(DeliveryRequest,
        DeliveryRequest.delivery_request_id==DeliveryAssignment.delivery_request_id).where(
        DeliveryAssignment.driver_user_id==ident,DeliveryRequest.status.in_(driver_service.ACTIVE)).limit(1).with_for_update(read=True)) is not None


def decide_driver(db,actor,ident,payload):
    admin_actor(db,actor)
    managed_user(db,ident,'driver')
    driver_service.actor(db,ident,'driver',lock=True,exclusive=True)
    profile=current(db,select(DriverProfile).where(DriverProfile.user_id==ident),False)
    if profile is None: raise HTTPException(409,'Driver application has not been submitted')
    if profile.approval_status!='pending': raise HTTPException(409,'Only pending Driver applications can be reviewed')
    if active_assignments(db,ident): raise HTTPException(409,'Active assignments require an operational review')
    if payload.decision=='approve' and (not profile.vehicle_type or not profile.vehicle_type.strip() or not profile.registration_reference or not profile.registration_reference.strip()):
        raise HTTPException(409,'Stored vehicle type and registration reference are required')
    if payload.decision=='approve':
        from app.services.admin_driver_documents import require_approved
        require_approved(db,ident,profile)
    state='approved' if payload.decision=='approve' else 'rejected'
    driver_service.review_profile(db,actor.user_id,ident,state)
    event=audit(db,actor,'driver',ident,'driver_'+state,'pending',state,payload.review_note)
    notify_event(db,'driver_'+state,event.audit_id)
    return driver_detail(db,ident)


def account_status(db,actor,ident,payload):
    admin_actor(db,actor)
    preview=managed_user(db,ident) # Admins, including self/last Admin, are excluded.
    # Lock business before owner rows, consistent with business review. This
    # serializes attempts to suspend the last two active owners concurrently.
    businesses=[]
    if preview.platform_role=='shop_owner':
        businesses=list(db.scalars(select(Business).where(Business.business_id.in_(select(BusinessMember.business_id).where(
            BusinessMember.user_id==ident,BusinessMember.business_role=='owner',BusinessMember.membership_status=='active')))
            .order_by(Business.business_id).with_for_update().execution_options(populate_existing=True)))
    target=current(db,select(User).where(User.user_id==ident),False)
    if target.platform_role not in ROLES: raise HTTPException(404,'Managed user not found')
    if target.account_status not in {'active','suspended'}: raise HTTPException(409,'Unsupported account state')
    if target.account_status==payload.account_status: return user_data(target) # Idempotent; no new audit.
    if payload.account_status=='suspended':
        if target.platform_role=='driver' and active_assignments(db,ident):
            raise HTTPException(409,'Driver has active assignments; suspension is deferred')
        if target.platform_role=='customer' and current(db,select(Order.order_id).where(
            Order.customer_user_id==ident,Order.status.in_(['submitted','approved','processing'])).limit(1)) is not None:
            raise HTTPException(409,'Customer has active orders; suspension is deferred')
        for business in businesses:
            if business.approval_status=='approved':
                other=current(db,select(User.user_id).join(BusinessMember,BusinessMember.user_id==User.user_id).where(
                    BusinessMember.business_id==business.business_id,BusinessMember.business_role=='owner',
                    BusinessMember.membership_status=='active',User.platform_role=='shop_owner',User.account_status=='active',User.user_id!=ident).limit(1))
                if other is None: raise HTTPException(409,'An approved business must retain an active Shop Owner')
    previous=target.account_status; target.account_status=payload.account_status; db.flush()
    audit(db,actor,'user',ident,'account_suspended' if payload.account_status=='suspended' else 'account_reactivated',previous,payload.account_status,payload.reason)
    return user_data(target)


def audit_events(db,limit,offset,target_type=None):
    administrative=select(literal('administrative').label('source'),AdminAudit.audit_id,AdminAudit.admin_user_id,
        AdminAudit.target_type,AdminAudit.target_id,AdminAudit.action,AdminAudit.previous_state,
        AdminAudit.new_state,AdminAudit.reason,AdminAudit.created_at)
    business=select(literal('business_approval').label('source'),BusinessApprovalAudit.audit_id,BusinessApprovalAudit.admin_user_id,
        literal('business').label('target_type'),BusinessApprovalAudit.business_id.label('target_id'),
        (literal('business_')+BusinessApprovalAudit.new_status).label('action'),BusinessApprovalAudit.previous_status.label('previous_state'),
        BusinessApprovalAudit.new_status.label('new_state'),BusinessApprovalAudit.review_note.label('reason'),BusinessApprovalAudit.created_at)
    records=union_all(administrative,business).subquery()
    query=select(records)
    if target_type: query=query.where(records.c.target_type==target_type)
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    events=db.execute(query.order_by(records.c.created_at.desc(),records.c.source,records.c.audit_id.desc()).limit(limit).offset(offset)).mappings().all()
    return dict(total=total,limit=limit,offset=offset,events=[dict(row) for row in events])
