"""Authenticated vehicle onboarding; existing storage and review semantics."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.models import DriverProfile, DriverVerificationDocument
from app.services.driver_service import actor, driver_profile
from app.services.driver_document_storage import PrivateDocumentStore, UploadBudget, DocumentError
from app.services.driver_document_service import append_version


def submit_vehicle(db, user_id, vehicle, licence, ownership):
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
        second = store.stage(ownership.file, ownership.filename, ownership.content_type, budget)
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
        db.commit()
        return result
    except DocumentError as error:
        db.rollback()
        unavailable = str(error) in ('PRIVATE_STORAGE_UNAVAILABLE', 'DOCUMENT_STORAGE_OR_PROTECTION_UNAVAILABLE', 'STAGING_CLEANUP_REQUIRES_REVIEW')
        raise HTTPException(503 if unavailable else 422, 'Document submission unavailable' if unavailable else
                            'Documents must be valid JPG, PNG or PDF files, maximum 5 MiB each') from None
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Vehicle submission conflicts; refresh before resubmitting') from None
    except Exception:
        # Commit can be uncertain. Preserve private candidates, never auto-delete/retry.
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(503, 'Submission outcome uncertain; refresh before resubmitting') from None
