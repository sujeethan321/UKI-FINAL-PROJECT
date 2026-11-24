# Purpose: Implement driver vehicle operations behind the HTTP layer so related business rules are shared by their callers.
"""Authenticated vehicle onboarding; existing storage and review semantics."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.models import DriverProfile, DriverVerificationDocument
from app.services.driver_service import actor, driver_profile
from app.services.driver_document_storage import PrivateDocumentStore, UploadBudget, DocumentError
from app.services.driver_document_service import append_version

def rollback_candidates(db,store,candidates,commit_started):
    """No deletion on failed rollback, uncertain commit, or reference lookup."""
    try:
        db.rollback()
        if commit_started or not candidates:return
        keys=[candidate.storage_key for candidate in candidates]
        referenced=set(db.scalars(select(DriverVerificationDocument.storage_key).where(
            DriverVerificationDocument.storage_key.in_(keys)).with_for_update(read=True)))
        db.rollback()  # Finish the read-only reference check before filesystem cleanup.
        store.discard_unsubmitted([candidate for candidate in candidates if candidate.storage_key not in referenced])
    except Exception:
        raise HTTPException(503,'Submission cleanup requires operator review; do not resubmit yet') from None


# Submit vehicle for the driver vehicle workflow.
def submit_vehicle(db, user_id, vehicle, licence, ownership):
    store=None;candidates=[];commit_started=False
    try:
        # Same User -> profile -> documents lock order as Admin review/replacement.
        user = actor(db, user_id, 'driver', lock=True, exclusive=True)
        profile = db.scalar(select(DriverProfile).where(DriverProfile.user_id == user_id)
                            .with_for_update().execution_options(populate_existing=True))
        documents = list(db.scalars(select(DriverVerificationDocument).where(
            DriverVerificationDocument.driver_user_id == user_id,
            DriverVerificationDocument.current_slot == 1).with_for_update()
            .execution_options(populate_existing=True)))
        if profile and (profile.approval_status not in ('pending', 'rejected') or
                        (profile.approval_status == 'pending' and documents and
                         not any(d.review_status == 'REJECTED' for d in documents))):
            raise HTTPException(409, 'Vehicle already submitted; refresh its review status')
        root = getattr(settings, 'DRIVER_DOCUMENT_PRIVATE_ROOT', None)
        if root is None:
            raise HTTPException(503, 'Driver document submission is not configured')
        store, budget = PrivateDocumentStore(root), UploadBudget()
        first = store.stage(licence.file, licence.filename, licence.content_type, budget)
        candidates.append(first)
        second = store.stage(ownership.file, ownership.filename, ownership.content_type, budget)
        candidates.append(second)
        if profile is None:
            profile = DriverProfile(user_id=user_id, approval_status='pending', legacy_document_exempt=False)
            db.add(profile)
        profile.vehicle_type = vehicle.vehicle_type
        profile.registration_reference = vehicle.registration_reference
        profile.approval_status = 'pending'
        profile.legacy_document_exempt = False
        profile.reviewed_by = None
        profile.reviewed_at = None
        db.flush()
        append_version(db, user_id, 'DRIVING_LICENCE', first, store)
        append_version(db, user_id, 'VEHICLE_OWNERSHIP_PROOF', second, store)
        db.flush()
        result = driver_profile(db, user)
        commit_started=True
        db.commit()
        return result
    except DocumentError as error:
        rollback_candidates(db,store,candidates,commit_started)
        unavailable = str(error) in ('PRIVATE_STORAGE_UNAVAILABLE', 'DOCUMENT_STORAGE_OR_PROTECTION_UNAVAILABLE', 'STAGING_CLEANUP_REQUIRES_REVIEW')
        raise HTTPException(503 if unavailable else 422, 'Document submission unavailable' if unavailable else
                            'Documents must be valid JPG, PNG or PDF files, maximum 5 MiB each') from None
    except HTTPException:
        rollback_candidates(db,store,candidates,commit_started)
        raise
    except IntegrityError:
        rollback_candidates(db,store,candidates,commit_started)
        raise HTTPException(409, 'Vehicle submission conflicts; refresh before resubmitting') from None
    except Exception:
        # Commit can be uncertain. Preserve private candidates, never auto-delete/retry.
        rollback_candidates(db,store,candidates,commit_started)
        raise HTTPException(503, 'Submission outcome uncertain; refresh before resubmitting') from None
