"""Two validated documents precede a single caller-owned registration commit."""
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app.core.config import settings
from app.models import DriverProfile, User
from app.services.registration_service import _create_user, EmailAlreadyRegistered
from app.services.driver_document_storage import PrivateDocumentStore, UploadBudget, DocumentError
from app.services.driver_document_service import append_version
from app.models.delivery import utc_now


def register_driver_application(db, data, vehicle, licence, ownership):
    store=None
    try:
        if db.scalar(select(User.user_id).where(User.email==str(data.email).strip().lower())) is not None:
            raise EmailAlreadyRegistered()
        root=getattr(settings,'DRIVER_DOCUMENT_PRIVATE_ROOT',None)
        if root is None:
            raise HTTPException(503,'Driver document submission is not configured')
        store=PrivateDocumentStore(root)
        budget=UploadBudget()
        # No User/Profile writes before BOTH validators succeed. Validated but
        # unattached candidates remain private for explicit orphan review.
        first=store.stage(licence.file,licence.filename,licence.content_type,budget)
        second=store.stage(ownership.file,ownership.filename,ownership.content_type,budget)
        user=_create_user(db,data,'driver')
        db.add(DriverProfile(user_id=user.user_id,vehicle_type=vehicle.vehicle_type,
            registration_reference=vehicle.registration_reference,approval_status='pending',
            legacy_document_exempt=False,created_at=utc_now()))
        db.flush()
        append_version(db,user.user_id,'DRIVING_LICENCE',first,store)
        append_version(db,user.user_id,'VEHICLE_OWNERSHIP_PROOF',second,store)
        db.flush()
        # Materialize ordinary response fields before commit. Never refresh and
        # accidentally turn a committed success into an automatic re-submission.
        result=dict(user_id=user.user_id,full_name=user.full_name,email=user.email,role='driver',
            account_status=user.account_status,message='Registration successful; Driver application pending review')
        db.commit()
        return result
    except EmailAlreadyRegistered:
        db.rollback()
        raise HTTPException(409,'Email address is already registered') from None
    except DocumentError as error:
        db.rollback()
        unavailable=str(error) in ('PRIVATE_STORAGE_UNAVAILABLE','DOCUMENT_STORAGE_OR_PROTECTION_UNAVAILABLE','STAGING_CLEANUP_REQUIRES_REVIEW')
        raise HTTPException(503 if unavailable else 422,'Document submission unavailable' if unavailable else 'Documents must be valid JPG, PNG or PDF files, maximum 5 MiB each') from None
    except HTTPException:
        db.rollback(); raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Registration conflicts with an existing record; verify before resubmitting') from None
    except Exception:
        # A failed COMMIT may have reached the server. Keep every validated file;
        # no retry or deletion, even if rollback subsequently succeeds.
        try: db.rollback()
        except Exception: pass
        raise HTTPException(503,'Registration outcome uncertain; check sign-in or contact the operator before resubmitting') from None
