"""HTTP hardening without logging request bodies, tokens or exception values."""
import logging
from uuid import uuid4

from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.core.rate_limit import configure_rate_limits
from app.core.request_limits import RequestBodyLimitMiddleware

logger = logging.getLogger("lankapex.security")


def configure_http_security(app, settings):
    logger.setLevel(settings.LOG_LEVEL)
    configure_rate_limits(app, settings)
    app.add_middleware(RequestBodyLimitMiddleware,
                       max_bytes=getattr(settings, 'MAX_REQUEST_BODY_BYTES', 262144))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Default validation responses include submitted input, such as passwords.
        return JSONResponse(status_code=422, content={"detail": [
            {key: error[key] for key in ("type", "loc", "msg")}
            for error in exc.errors()
        ]})

    @app.middleware("http")
    async def safe_errors_and_headers(request, call_next):
        request_id = uuid4().hex
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception as exc:
            # Catch before ServerErrorMiddleware re-raises to ASGI server logging.
            route = request.scope.get("route")
            logger.error("Unhandled %s on %s %s request_id=%s", type(exc).__name__, request.method,
                         getattr(route, "path", "<unmatched>"), request_id)
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers['X-Request-ID'] = request_id
        if 'authorization' in request.headers or request.url.path.startswith('/api/v1/auth/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    if settings.APP_ENV == "production":
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS,
                           www_redirect=False)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=False,  # Authorization: Bearer authentication, no cookies.
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        expose_headers=['Retry-After', 'X-Request-ID'],
    )
