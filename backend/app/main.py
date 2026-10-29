
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.health import router as health_router

app = FastAPI(
    title="LankaPex API",
    description="Backend API for LankaPex",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(
    health_router,
    prefix="/api/v1",
)


@app.get("/")
def root():
    return {
        "message": "Welcome to LankaPex API"
    }
