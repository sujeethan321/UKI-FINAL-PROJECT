
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.role_access import router as role_access_router


# 1. Create the FastAPI application FIRST
app = FastAPI(
    title="LankaPex API",
    description="Backend API for LankaPex",
    version="1.0.0",
)


# 2. Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=[
        "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"
    ],
    allow_headers=[
        "Authorization", "Content-Type", "Accept"
    ],
)


# 3. Register existing routers
app.include_router(
    health_router,
    prefix="/api/v1",
)

app.include_router(
    auth_router,
    prefix="/api/v1",
)

app.include_router(
    role_access_router,
    prefix="/api/v1",
)


# 5. Root endpoint
@app.get("/")
def root():
    return {
        "message": "Welcome to LankaPex API"
    }
