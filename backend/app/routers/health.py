
from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "application": "LankaPex",
        "message": "Backend is running successfully"
    }


from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db


@router.get("/health/database", include_in_schema=False)
def database_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from None

    return {
        "status": "ok",
        "database": "connected",
    }
