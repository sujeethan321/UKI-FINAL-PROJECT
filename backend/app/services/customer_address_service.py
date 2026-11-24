"""Caller owns transaction. Lock User -> preference -> owned addresses.

Current locking reads avoid stale RR snapshots after waiting on the User lock.
No hard deletion or account-phone synchronization. Never logs address contents.
"""
import hashlib,json
from fastapi import HTTPException
from sqlalchemy import select,func
from app.models import User,CustomerAddress,UserPreference
from app.models.catalogue import utc_now
from app.services import customer_address_rollout as rollout

FIELDS=('label','recipient_name','address_line','city','phone')
HEADERS={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}

def fail(status,code):raise HTTPException(status,detail={'code':code,'message':'Address operation unavailable or changed. Reload your address book.'},headers=HEADERS)

def locked(db,query):return query.with_for_update().execution_options(populate_existing=True)

def book(db,user):
    rollout.require_ready(db)
    row=db.scalar(locked(db,select(User).where(User.user_id==user.user_id)))
    if row is None or row.platform_role!='customer' or row.account_status!='active':fail(403,'ADDRESS_ACCESS_DENIED')
    pref=db.scalar(locked(db,select(UserPreference).where(UserPreference.user_id==user.user_id)))
    # Reads must not create rows. First mutation creates under the User lock.
    return pref

def version(pref):return pref.version if pref else 1

def check(pref,expected):
    if version(pref)!=expected:fail(409,'ADDRESS_BOOK_STALE')

def bump(db,user,pref):
    if pref is None:
        pref=UserPreference(user_id=user.user_id,version=1)
        db.add(pref);db.flush()
    pref.version+=1;pref.updated_at=utc_now()
    return pref

def owned(db,user,address_id,active=True):
    row=db.scalar(locked(db,select(CustomerAddress).where(CustomerAddress.user_id==user.user_id,CustomerAddress.address_id==address_id)))
    if row is None or (active and row.archived_at is not None):fail(404,'ADDRESS_NOT_FOUND')
    return row

def canonical(row):return {key:getattr(row,key) for key in FIELDS}
def digest(row):return hashlib.sha256(json.dumps(canonical(row),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def project(row):return dict(address_id=row.address_id,**canonical(row),archived=row.archived_at is not None)

def listing(db,user,page=1,size=10,archived=False):
    pref=book(db,user)
    query=select(CustomerAddress).where(CustomerAddress.user_id==user.user_id)
    query=query.where(CustomerAddress.archived_at.is_not(None) if archived else CustomerAddress.archived_at.is_(None))
    total=db.scalar(select(func.count(CustomerAddress.address_id)).where(CustomerAddress.user_id==user.user_id,
        CustomerAddress.archived_at.is_not(None) if archived else CustomerAddress.archived_at.is_(None)).with_for_update())
    rows=list(db.scalars(locked(db,query.order_by(CustomerAddress.address_id).offset((page-1)*size).limit(size))))
    return dict(version=version(pref),default_address_id=pref.preferred_address_id if pref else None,addresses=[project(r) for r in rows],total=total,page=page,page_size=size)

def mutate(db,user,payload,operation,address_id=None):
    pref=book(db,user)
    if operation=='create':
        data={key:getattr(payload,key) for key in FIELDS}
        hashed=hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        previous=db.scalar(locked(db,select(CustomerAddress).where(CustomerAddress.user_id==user.user_id,CustomerAddress.create_request_key==payload.request_key)))
        if previous:
            if previous.create_request_hash!=hashed:fail(409,'ADDRESS_REQUEST_CONFLICT')
            return dict(version=version(pref),address=project(previous),replayed=True)
        check(pref,payload.version)
        # Bound current read under the owning User lock; no unbounded allocation.
        active=list(db.scalars(locked(db,select(CustomerAddress.address_id).where(CustomerAddress.user_id==user.user_id,CustomerAddress.archived_at.is_(None)).limit(11))))
        if len(active)>=10:fail(409,'ADDRESS_LIMIT')
        row=CustomerAddress(user_id=user.user_id,**data,create_request_key=payload.request_key,create_request_hash=hashed)
        db.add(row)
    else:
        check(pref,payload.version)
        if operation=='default':
            row=owned(db,user,payload.address_id) if payload.address_id is not None else None
        else:row=owned(db,user,address_id)
        if operation=='edit':
            for key in FIELDS:setattr(row,key,getattr(payload,key))
            row.updated_at=utc_now()
        elif operation=='archive':
            row.archived_at=utc_now();row.updated_at=row.archived_at
    pref=bump(db,user,pref)
    if operation=='default':pref.preferred_address_id=row.address_id if row else None
    elif operation=='archive' and pref.preferred_address_id==row.address_id:pref.preferred_address_id=None
    db.flush()
    return dict(version=pref.version,address=project(row) if row else None,replayed=False)

def selected(db,user,address_id,expected):
    pref=book(db,user);check(pref,expected)
    return owned(db,user,address_id)
