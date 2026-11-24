"""Transactional case operations only. Never posts financial corrections.

Routes commit once. Case/actor locks serialize retries and optimistic versions.
Internal changes never increment requester versions or visible timestamps.
"""
from datetime import datetime,timedelta
from hashlib import sha256
import json
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select,func,and_,or_
from app.models import User,BusinessMember
from app.models.support import SupportCase,SupportMessage,SupportEvent,SupportReference
from app.models.catalogue import utc_now
from app.services.support_rollout import require_ready
from app.services.support_reference_service import validate

TRANSITIONS={'open':{'assigned','investigating','awaiting_user','resolved'},'assigned':{'investigating','awaiting_user','resolved'},
    'investigating':{'awaiting_user','resolved'},'awaiting_user':{'investigating','resolved'},'resolved':{'closed'},'closed':set()}
MAX_HISTORY=1000

def actor(db,user,admin=False,lock=False):
    query=select(User).where(User.user_id==user.user_id)
    if lock:query=query.with_for_update().execution_options(populate_existing=True)
    current=db.scalar(query)
    allowed={'admin'} if admin else {'customer','shop_owner','driver'}
    if current is None or current.account_status!='active' or current.platform_role not in allowed:raise HTTPException(403,'Support access denied')
    return current

def visible(user):
    own=SupportCase.creator_id==user.user_id
    if user.platform_role=='shop_owner':
        memberships=select(BusinessMember.business_id).where(BusinessMember.user_id==user.user_id,BusinessMember.business_role=='owner',BusinessMember.membership_status=='active')
        return or_(own,and_(SupportCase.business_shared.is_(True),SupportCase.business_id.in_(memberships)))
    return own

def scoped(db,user,reference,admin=False,lock=False):
    query=select(SupportCase).where(SupportCase.reference==reference)
    if not admin:query=query.where(visible(user))
    if lock:query=query.with_for_update().execution_options(populate_existing=True)
    row=db.scalar(query)
    if row is None:raise HTTPException(404,'Support case not found')
    return row

def digest(payload):return sha256(json.dumps(payload.model_dump(mode='json'),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def case_data(row,admin=False):
    data={key:getattr(row,key) for key in ('reference','business_id','business_shared','category','subject','description','priority','status','resolution','resolved_at','created_at')}
    data.update(version=row.version if admin else row.public_version,updated_at=row.updated_at if admin else row.public_updated_at)
    if admin:data.update(creator_id=row.creator_id,assigned_admin_id=row.assigned_admin_id)
    return data

def list_cases(db,user,filters,admin=False):
    actor(db,user,admin);require_ready(db)
    query=select(SupportCase)
    if not admin:query=query.where(visible(user))
    for key in ('status','category','priority'):
        if getattr(filters,key) is not None:query=query.where(getattr(SupportCase,key)==getattr(filters,key))
    if filters.start_date and filters.end_date and filters.start_date>filters.end_date:raise HTTPException(422,'Invalid support date range')
    if filters.end_date and filters.end_date.year==9999:raise HTTPException(422,'Invalid support end date')
    if filters.start_date:query=query.where(SupportCase.created_at>=datetime.combine(filters.start_date,datetime.min.time()))
    if filters.end_date:query=query.where(SupportCase.created_at<datetime.combine(filters.end_date+timedelta(days=1),datetime.min.time()))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.scalars(query.order_by(SupportCase.created_at.desc(),SupportCase.case_id.desc()).limit(filters.limit).offset(filters.offset))
    return dict(total=total,limit=filters.limit,offset=filters.offset,cases=[case_data(row,admin) for row in rows],financial_links=finance_capability(db))

def _finance_enabled():
    from app.services.driver_finance_rollout import enabled
    return enabled()

def finance_capability(db):
    if not _finance_enabled():return 'unavailable'
    from app.services.driver_finance_rollout import require_ready as finance_ready
    try:finance_ready(db)
    except HTTPException as error:
        if error.status_code==503:return 'unavailable'
        raise
    return 'available'

def history(db,user,reference,kind,limit=100,offset=0,admin=False):
    actor(db,user,admin);require_ready(db);row=scoped(db,user,reference,admin)
    model=SupportMessage if kind=='messages' else SupportEvent
    query=select(model).where(model.case_id==row.case_id)
    if not admin:query=query.where(model.visibility=='public')
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    key=model.message_id if kind=='messages' else model.event_id
    records=list(db.scalars(query.order_by(key).limit(limit).offset(offset)))
    if kind=='messages':
        items=[dict(body=e.body,created_at=e.created_at,from_admin=e.actor_role=='admin',visibility=e.visibility) for e in records]
    else:
        items=[dict(action=e.action,previous_value=e.previous_value,new_value=e.new_value,reason=e.reason,created_at=e.created_at,
            **(dict(actor_id=e.actor_id,sequence=e.sequence,visibility=e.visibility) if admin else {})) for e in records]
    return dict(total=total,limit=limit,offset=offset,items=items)

def detail(db,user,reference,admin=False):
    actor(db,user,admin);require_ready(db);row=scoped(db,user,reference,admin)
    references=[]
    if admin or row.creator_id==user.user_id:
        ref=db.scalar(select(SupportReference).where(SupportReference.case_id==row.case_id))
        if ref:
            references=[dict(kind=key.removesuffix('_id'),record_id=str(getattr(ref,key))) for key in ('order_id','delivery_id','credit_account_id','ledger_entry_id','earning_id') if getattr(ref,key) is not None]
    return dict(case=case_data(row,admin),references=references,
        messages=history(db,user,reference,'messages',admin=admin),events=history(db,user,reference,'events',admin=admin))

def append_event(db,row,user,action,payload,visibility='public',previous=None,new=None,message_id=None):
    event=SupportEvent(case_id=row.case_id,actor_id=user.user_id,actor_role=user.platform_role,sequence=row.version,action=action,visibility=visibility,
        previous_value=previous,new_value=new,reason=getattr(payload,'reason',None),message_id=message_id,
        request_key=payload.request_key,request_hash=digest(payload))
    db.add(event);db.flush();return event

def notify(db,row,event,kind):
    from app.services.notification_service import notify_support_event
    notify_support_event(db,row,event,kind)

def create(db,user,payload):
    user=actor(db,user,lock=True);require_ready(db)
    old=db.scalar(select(SupportCase).where(SupportCase.creator_id==user.user_id,SupportCase.request_key==payload.request_key).with_for_update())
    if old:
        if old.request_hash!=digest(payload):raise HTTPException(409,'Support request key conflicts with an earlier request')
        return detail(db,user,old.reference)
    business,values=validate(db,user,payload)
    row=SupportCase(reference='SUP-'+uuid4().hex,creator_id=user.user_id,business_id=business,business_shared=payload.business_shared,
        category=payload.category,subject=payload.subject,description=payload.description,request_key=payload.request_key,request_hash=digest(payload))
    db.add(row);db.flush()
    if values:db.add(SupportReference(case_id=row.case_id,**values));db.flush()
    event=append_event(db,row,user,'created',payload,new='open');notify(db,row,event,'support_created')
    return detail(db,user,row.reference)

def command_actor(db,user,payload,admin):
    participants={}
    if admin and payload.action=='assignment':
        actor(db,user,True)  # Reject wrong-role callers before locking other users.
        for ident in sorted({user.user_id,payload.admin_id}):
            participants[ident]=db.scalar(select(User).where(User.user_id==ident).with_for_update().execution_options(populate_existing=True))
        user=participants[user.user_id]
        if user is None or user.platform_role!='admin' or user.account_status!='active':raise HTTPException(403,'Support access denied')
    else:user=actor(db,user,admin,lock=True)
    return user,participants

def command(db,user,reference,payload,admin=False):
    user,participants=command_actor(db,user,payload,admin);require_ready(db);row=scoped(db,user,reference,admin,True)
    if not admin and row.creator_id!=user.user_id:
        from app.services.support_reference_service import owner
        if not row.business_shared or not owner(db,user.user_id,row.business_id):raise HTTPException(404,'Support case not found')
    prior=db.scalar(select(SupportEvent).where(SupportEvent.actor_id==user.user_id,SupportEvent.request_key==payload.request_key).with_for_update())
    if prior:
        if prior.case_id!=row.case_id or prior.request_hash!=digest(payload):raise HTTPException(409,'Support request key conflicts with an earlier action')
        return detail(db,user,reference,admin)
    if payload.expected_version!=(row.version if admin else row.public_version):raise HTTPException(409,'Support case changed; refresh before retrying')
    if row.version>=MAX_HISTORY:raise HTTPException(422,'Support case history limit reached; contact an Administrator')
    action=payload.action;old=None;new=None;message_id=None;visibility='public';notification=None
    if not admin and action not in ('message','reopen'):raise HTTPException(403,'Admin support action required')
    if not admin and action=='reopen' and row.creator_id!=user.user_id:raise HTTPException(403,'Only the creator can reopen this case')
    if row.status=='closed':raise HTTPException(409,'Closed cases require a new case or separately authorized review')
    if action in ('message','internal_note'):
        if action=='message' and row.status=='resolved':raise HTTPException(409,'Reopen the case before replying')
        visibility='internal' if action=='internal_note' else 'public'
        message=SupportMessage(case_id=row.case_id,actor_id=user.user_id,actor_role=user.platform_role,visibility=visibility,body=payload.body)
        db.add(message);db.flush();message_id=message.message_id
        if admin and action=='message':notification='support_replied'
    elif action=='assignment':
        eligible=participants.get(payload.admin_id)
        if eligible is None or eligible.platform_role!='admin' or eligible.account_status!='active':raise HTTPException(422,'Assignment requires an active Admin')
        if row.status=='resolved' or row.assigned_admin_id==payload.admin_id:raise HTTPException(409,'Assignment is unchanged or case is resolved')
        old=str(row.assigned_admin_id) if row.assigned_admin_id else None;row.assigned_admin_id=payload.admin_id;new=str(payload.admin_id)
        visibility='internal'  # Assignee identities are never disclosed to requesters.
    elif action=='priority':
        if row.priority==payload.priority:raise HTTPException(409,'Priority is unchanged')
        old=row.priority;row.priority=payload.priority;new=row.priority
    elif action=='status':
        if payload.status not in TRANSITIONS[row.status]:raise HTTPException(409,'Support status transition not permitted')
        if payload.status=='assigned' and row.assigned_admin_id is None:raise HTTPException(409,'Assign an Admin first')
        old=row.status;row.status=payload.status;new=row.status
        if new=='resolved':row.resolution=payload.reason;row.resolved_at=utc_now();notification='support_resolved'
        if new=='awaiting_user':notification='support_awaiting_user'
    elif action=='reopen':
        if row.status!='resolved' or row.resolved_at is None or not timedelta(0)<=utc_now()-row.resolved_at<=timedelta(days=14):raise HTTPException(409,'Reopening requires a resolved case within 14 days')
        old=row.status;row.status='investigating';new=row.status;action='reopened';row.resolution=None;row.resolved_at=None;notification='support_reopened'
    row.version+=1;row.updated_at=utc_now()
    if visibility=='public':row.public_version+=1;row.public_updated_at=row.updated_at
    event=append_event(db,row,user,action,payload,visibility,old,new,message_id)
    if notification:notify(db,row,event,notification)
    db.flush();return detail(db,user,reference,admin)
