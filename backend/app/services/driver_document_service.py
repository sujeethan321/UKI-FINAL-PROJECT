"""Transaction-owned metadata foundations, not mounted upload/review endpoints."""
from datetime import datetime, timezone
import hashlib
from uuid import uuid4
from sqlalchemy import select
from app.models import DriverProfile, User
from app.models.driver_document import DriverVerificationDocument, DriverDocumentAudit
from app.services.driver_document_storage import require

DOCUMENT_TYPES={'DRIVING_LICENCE','VEHICLE_OWNERSHIP_PROOF'}


def append_version(db, actor_id, document_type, candidate, store):
    """Caller owns commit; ambiguous commit preserves the staged file.

    Lock Driver first to serialize versions across requests. Existing approved
    accounts cannot silently replace evidence through this foundation.
    """
    require(document_type in DOCUMENT_TYPES)
    user=db.scalar(select(User).where(User.user_id==actor_id).with_for_update().execution_options(populate_existing=True))
    require(user is not None and user.platform_role=='driver' and user.account_status=='active','DOCUMENT_ACCESS_DENIED')
    profile=db.scalar(select(DriverProfile).where(DriverProfile.user_id==actor_id).with_for_update().execution_options(populate_existing=True))
    require(profile is not None and profile.approval_status in ('pending','rejected'),'DOCUMENT_RESUBMISSION_REQUIRES_REVIEW')
    path=store._path(candidate.storage_key)
    require(not path.is_symlink() and path.is_file())
    content=path.read_bytes()
    require(len(content)==candidate.size_bytes and hashlib.sha256(content).hexdigest()==candidate.content_sha256)
    previous=db.scalar(select(DriverVerificationDocument).where(
        DriverVerificationDocument.driver_user_id==actor_id,
        DriverVerificationDocument.document_type==document_type,
        DriverVerificationDocument.current_slot==1).with_for_update())
    version=previous.version+1 if previous else 1
    if previous:
        previous.current_slot=None
        db.flush()
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    row=DriverVerificationDocument(document_id=str(uuid4()),driver_user_id=actor_id,document_type=document_type,
        version=version,current_slot=1,supersedes_id=previous.document_id if previous else None,
        storage_key=candidate.storage_key,content_sha256=candidate.content_sha256,
        media_type=candidate.media_type,size_bytes=candidate.size_bytes,created_at=now,validated_at=now,review_status='PENDING')
    db.add(row); db.flush()
    db.add(DriverDocumentAudit(audit_id=str(uuid4()),document_id=row.document_id,actor_user_id=actor_id,
        action='REPLACED' if previous else 'SUBMITTED',outcome='SUCCESS',created_at=now))
    return row


def application_documents_ready(db, driver_id):
    """For future approval integration; legacy exemption is NOT verification."""
    rows=list(db.scalars(select(DriverVerificationDocument).where(
        DriverVerificationDocument.driver_user_id==driver_id,DriverVerificationDocument.current_slot==1)))
    return {r.document_type for r in rows}==DOCUMENT_TYPES and all(r.review_status=='APPROVED' for r in rows)
