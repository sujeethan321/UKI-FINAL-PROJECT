# Purpose: Implement admin driver documents operations behind the HTTP layer so related business rules are shared by their callers.
"""Active Admin access to current, integrity-checked sanitized documents."""
from datetime import datetime, timezone
import hashlib
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import settings
from app.models import User, DriverProfile, DriverVerificationDocument, DriverDocumentAudit
from app.services.driver_document_storage import PrivateDocumentStore, DocumentError, MAX_FILE

KINDS=('DRIVING_LICENCE','VEHICLE_OWNERSHIP_PROOF')


# Lock profile rows before the calling operation proceeds.
def locked_profile(db, actor, driver_id):
    from app.services.driver_service import actor as checked_actor
    checked_actor(db,actor.user_id,'admin',lock=True)
    # Same exclusive User lock as document replacement, before profile/doc locks.
    user=db.scalar(select(User).where(User.user_id==driver_id).with_for_update().execution_options(populate_existing=True))
    if user is None or user.platform_role!='driver': raise HTTPException(404,'Driver application not found')
    profile=db.scalar(select(DriverProfile).where(DriverProfile.user_id==driver_id).with_for_update().execution_options(populate_existing=True))
    if profile is None: raise HTTPException(404,'Driver application not found')
    return profile


# Resolve current documents using a row lock so the caller can coordinate concurrent changes.
def current_documents(db,driver_id):
    return list(db.scalars(select(DriverVerificationDocument).where(
        DriverVerificationDocument.driver_user_id==driver_id,DriverVerificationDocument.current_slot==1)
        .order_by(DriverVerificationDocument.document_type).with_for_update().execution_options(populate_existing=True)))


# Resolve stored document content through the private-document service.
def content(row):
    try:
        root=getattr(settings,'DRIVER_DOCUMENT_PRIVATE_ROOT',None)
        if root is None: raise DocumentError()
        store=PrivateDocumentStore(root);path=store._path(row.storage_key)
        if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=MAX_FILE: raise DocumentError()
        with path.open('rb') as stream: data=stream.read(MAX_FILE+1)
        if len(data)!=row.size_bytes or hashlib.sha256(data).hexdigest()!=row.content_sha256: raise DocumentError()
        signatures={'image/jpeg':b'\xff\xd8\xff','image/png':b'\x89PNG\r\n\x1a\n','application/pdf':b'%PDF-'}
        if row.media_type not in signatures or not data.startswith(signatures[row.media_type]): raise DocumentError()
        return data
    except Exception:
        raise HTTPException(409,'Document unavailable or integrity check failed') from None


# Build current driver verification state from the retained document versions.
def verification(db,driver_id,profile):
    rows=current_documents(db,driver_id)
    documents=[]
    for kind in KINDS:
        row=next((r for r in rows if r.document_type==kind),None)
        valid=False
        if row:
            try: content(row);valid=True
            except HTTPException: pass
        documents.append(dict(document_type=kind,document_id=row.document_id if row else None,
            version=row.version if row else None,review_status=row.review_status if row else 'MISSING',
            integrity_valid=valid,media_type=row.media_type if row else None,
            reviewed_by=row.reviewed_by if row else None,reviewed_at=row.reviewed_at if row else None))
    legacy=bool(profile and profile.legacy_document_exempt and profile.approval_status=='approved')
    return dict(driver_user_id=driver_id,legacy_exempt=legacy,approval_ready=bool(profile and profile.approval_status=='pending' and
        all(d['review_status']=='APPROVED' and d['integrity_valid'] for d in documents)),documents=documents)


# Append the administrative decision to the audit trail so the actor and change remain traceable.
def audit(db,actor,row,action):
    db.add(DriverDocumentAudit(audit_id=str(uuid4()),document_id=row.document_id,actor_user_id=actor.user_id,
        action=action,outcome='SUCCESS',created_at=datetime.now(timezone.utc).replace(tzinfo=None)))


# Get current for the admin driver documents workflow.
def get_current(db,actor,driver_id,document_id):
    profile=locked_profile(db,actor,driver_id)
    row=next((r for r in current_documents(db,driver_id) if r.document_id==document_id),None)
    if row is None: raise HTTPException(404,'Current document not found')
    return profile,row


# Resolve the authorized current document, read its content, and record the administrative access.
def retrieve(db,actor,driver_id,document_id,action):
    _,row=get_current(db,actor,driver_id,document_id)
    data=content(row)
    audit(db,actor,row,action)
    return data,row.media_type


# Accept a document review only for a pending driver application after confirming the current evidence.
def review(db,actor,driver_id,document_id,decision,rejection_code):
    profile,row=get_current(db,actor,driver_id,document_id)
    if profile.approval_status!='pending': raise HTTPException(409,'Only pending Driver applications can be reviewed')
    content(row)
    target='APPROVED' if decision=='approve' else 'REJECTED'
    if row.review_status!='PENDING':
        if row.review_status==target and row.rejection_code==rejection_code: return verification(db,driver_id,profile)
        raise HTTPException(409,'Document already reviewed; refresh before proceeding')
    row.review_status=target;row.rejection_code=rejection_code
    row.reviewed_by=actor.user_id;row.reviewed_at=datetime.now(timezone.utc).replace(tzinfo=None)
    audit(db,actor,row,'REVIEWED');db.flush()
    return verification(db,driver_id,profile)


# Check approved and stop callers when the required conditions are not met.
def require_approved(db,driver_id,profile):
    if not verification(db,driver_id,profile)['approval_ready']:
        raise HTTPException(409,'Both current Driver documents must pass integrity checks and be approved')
