# Purpose: Expose health HTTP endpoints and connect request validation and dependencies to the application services.

from fastapi import APIRouter, HTTPException, Response, status

router = APIRouter(tags=["Health"])


# Handle GET /health through the declared request and dependency contract.
@router.get("/health")
def health_check(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return {
        "status": "ok",
        "application": "LankaPex",
        "message": "Backend is running successfully"
    }


# Handle GET /health/database through the declared request and dependency contract.
@router.get("/health/database", include_in_schema=False)
async def database_health(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    from app.services.readiness import probe
    if not await probe.check():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
            headers={'Cache-Control': 'no-store'},
        ) from None

    return {
        "status": "ok",
        "database": "connected",
    }
