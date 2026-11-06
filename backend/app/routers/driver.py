"""Driver-scoped reads, atomic job acceptance and guarded progress updates."""
from typing import Annotated
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session
from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.driver import DriverProfileResponse, DriverSummary, DriverDeliveries, AvailableJobs, AvailableJobDetail, DriverAssignmentDetail, JobAcceptance, AcceptJobRequest
from app.services import driver_service as service
from app.schemas.driver import DeliveryProgress, StatusUpdateRequest

router = APIRouter(prefix="/driver", tags=["Driver Dashboard"])
Driver = Annotated[User, Depends(require_roles("driver"))]
Database = Annotated[Session, Depends(get_db)]


def read(response, operation):
    response.headers["Cache-Control"] = "no-store"
    try:
        return operation()
    except SQLAlchemyError:
        raise HTTPException(503, "Driver information is temporarily unavailable") from None


@router.get("/profile", response_model=DriverProfileResponse)
def profile(response: Response, user: Driver, db: Database):
    return read(response, lambda: service.driver_profile(db, user))


@router.get("/dashboard/summary", response_model=DriverSummary)
def summary(response: Response, user: Driver, db: Database):
    return read(response, lambda: service.summary(db, user))


@router.get("/deliveries", response_model=DriverDeliveries)
def deliveries(response: Response, user: Driver, db: Database,
               page: Annotated[int, Query(ge=1, le=1000000)] = 1,
               page_size: Annotated[int, Query(ge=1, le=100)] = 5,
               status: Literal["assigned", "picked_up", "in_transit"] | None = None):
    return read(response, lambda: service.assigned_deliveries(db, user, page, page_size, status))


@router.get("/history", response_model=DriverDeliveries)
def history(response: Response, user: Driver, db: Database,
            page: Annotated[int, Query(ge=1, le=1000000)] = 1,
            page_size: Annotated[int, Query(ge=1, le=100)] = 10,
            status: Literal["delivered", "cancelled"] | None = None):
    return read(response, lambda: service.assigned_deliveries(db, user, page, page_size, status, history=True))


JobId = Annotated[int, Path(gt=0, le=9223372036854775807)]


@router.get("/jobs", response_model=AvailableJobs)
def jobs(response: Response, user: Driver, db: Database,
         page: Annotated[int, Query(ge=1, le=1000000)] = 1,
         page_size: Annotated[int, Query(ge=1, le=100)] = 10):
    return read(response, lambda: service.available_jobs(db, user, page, page_size))


@router.get("/jobs/{job_id}", response_model=AvailableJobDetail)
def job_detail(response: Response, user: Driver, db: Database, job_id: JobId):
    return read(response, lambda: service.available_job_detail(db, user, job_id))


@router.get("/deliveries/{job_id}", response_model=DeliveryProgress)
def assigned_detail(response: Response, user: Driver, db: Database, job_id: JobId):
    return read(response, lambda: service.delivery_progress(db, user, job_id))


@router.post("/deliveries/{job_id}/status", response_model=DeliveryProgress)
def update_status(response: Response, user: Driver, db: Database, job_id: JobId, payload: StatusUpdateRequest):
    response.headers["Cache-Control"] = "no-store"
    try:
        service.transition_delivery(db, user.user_id, job_id, payload.status, payload.expected_status)
        result = DeliveryProgress.model_validate(service.delivery_progress(db, user, job_id, current=True))
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Delivery changed. Refresh before updating its status.") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Update could not be confirmed. Refresh delivery details to check its recorded status.") from None


@router.post("/jobs/{job_id}/accept", response_model=JobAcceptance)
def accept_job(response: Response, user: Driver, db: Database, job_id: JobId, payload: AcceptJobRequest):
    response.headers["Cache-Control"] = "no-store"
    try:
        service.accept_delivery(db, user.user_id, job_id)
        result = JobAcceptance.model_validate(service.assigned_delivery_detail(db, user, job_id, current=True))
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Delivery is no longer available") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Unable to confirm assignment. Retry this same job to check its assignment.") from None
