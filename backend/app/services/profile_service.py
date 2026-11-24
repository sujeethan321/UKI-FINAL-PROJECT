"""No optional-schema dependency. Only full_name/preferred_language may change.

Revision is an opaque HMAC of current editable values and authenticated ID,
not a monotonic version, request log or durable audit. ABA changes cannot be
distinguished without new storage. Stale equal-value retries are safe no-ops;
they never overwrite a different current value. No changes to linked shop
customer aliases, business identities, Driver verification or financial rows.
"""
import hashlib,hmac,json
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import settings
from app.models.user import User
from app.schemas.profile import ProfileResponse

ROLES=frozenset({'customer','shop_owner','driver','admin'})
HEADERS={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}

def current(db,identity,lock=False):
    query=select(User).where(User.user_id==identity.user_id)
    if lock:query=query.with_for_update().execution_options(populate_existing=True)
    row=db.scalar(query)
    if row is None or row.account_status!='active' or row.platform_role not in ROLES:
        raise HTTPException(403,'Profile access denied',headers=HEADERS)
    return row

def revision(row):
    message=json.dumps(['lankapex-personal-profile-v1',row.user_id,row.full_name,row.preferred_language],ensure_ascii=False,separators=(',',':')).encode('utf-8')
    return 'p1-'+hmac.new(settings.JWT_SECRET_KEY.encode(),message,hashlib.sha256).hexdigest()

def response(row):
    if row.preferred_language not in ('en','ta','si'):raise HTTPException(409,'Stored profile language requires operator review',headers=HEADERS)
    return ProfileResponse(user_id=row.user_id,full_name=row.full_name,preferred_language=row.preferred_language,email=row.email,
        phone=row.phone,platform_role=row.platform_role,account_status=row.account_status,revision=revision(row))

def read(db,identity):return response(current(db,identity))

def update(db,identity,payload,expected):
    row=current(db,identity,True)
    changes=payload.model_dump(exclude_unset=True)
    unchanged=all(getattr(row,key)==value for key,value in changes.items())
    if not hmac.compare_digest(revision(row),expected) and not unchanged:
        raise HTTPException(409,detail={'code':'PROFILE_STALE','message':'Profile changed. Reload before saving again.'},headers=HEADERS)
    if not unchanged:
        for field in ('full_name','preferred_language'):
            if field in changes:setattr(row,field,changes[field])
        db.flush()
    return response(row)
