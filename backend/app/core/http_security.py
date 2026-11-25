# Purpose: Apply CORS, host checks, request limits, and safe HTTP error handling consistently across API routes.
"""HTTP hardening without logging request bodies, tokens or exception values."""
import logging
from uuid import uuid4

from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.exc import DBAPIError
from app.core.rate_limit import configure_rate_limits
from app.core.request_limits import RequestBodyLimitMiddleware

logger = logging.getLogger("lankapex.security")


def database_failure_diagnostic(exc):
    """Numeric driver code only; never inspect/render SQL, params or messages."""
    if not isinstance(exc, DBAPIError):
        return 'UNAVAILABLE', 'NOT_DBAPI_ERROR'
    args = getattr(exc.orig, 'args', ())
    code = args[0] if isinstance(args, tuple) and args else None
    if type(code) is not int or not 1000 <= code <= 9999:
        return 'UNAVAILABLE', 'DATABASE_ERROR_UNCLASSIFIED'
    categories = {
        1040: 'CONNECTION_LIMIT', 1044: 'DATABASE_ACCESS_DENIED',
        1045: 'AUTHENTICATION_FAILED', 1054: 'SCHEMA_COLUMN_MISMATCH',
        1142: 'STATEMENT_PERMISSION_DENIED', 1143: 'COLUMN_PERMISSION_DENIED',
        1146: 'SCHEMA_TABLE_MISSING', 1205: 'LOCK_WAIT_TIMEOUT',
        1213: 'DEADLOCK', 1290: 'SERVER_RESTRICTION',
        2002: 'CONNECTION_FAILED', 2003: 'CONNECTION_FAILED',
        2006: 'CONNECTION_LOST', 2013: 'CONNECTION_LOST',
        2026: 'TLS_CONNECTION_FAILED', 2055: 'CONNECTION_LOST',
        3024: 'QUERY_TIMEOUT',
    }
    return code, categories.get(code, 'DATABASE_ERROR_UNCLASSIFIED')


# Configure http security for the http security workflow.
def configure_http_security(app, settings):
    logger.setLevel(settings.LOG_LEVEL)
    configure_rate_limits(app, settings)
    app.add_middleware(RequestBodyLimitMiddleware,
                       max_bytes=getattr(settings, 'MAX_REQUEST_BODY_BYTES', 262144),
                       read_timeout=getattr(settings,'REQUEST_BODY_TIMEOUT_SECONDS',15))

    # Return the safe validation-error representation used at the HTTP boundary.
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Default validation responses include submitted input, such as passwords.
        return JSONResponse(status_code=422, content={"detail": [
            {key: error[key] for key in ("type", "loc", "msg")}
            for error in exc.errors()
        ]})

    # Apply safe response headers and sanitize error responses at the shared HTTP boundary.
    @app.middleware("http")
    async def safe_errors_and_headers(request, call_next):
        request_id = uuid4().hex
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception as exc:
            # Catch before ServerErrorMiddleware re-raises to ASGI server logging.
            route = request.scope.get("route")
            mysql_code, category = database_failure_diagnostic(exc)
            logger.error("Unhandled %s on %s %s request_id=%s mysql_code=%s diagnostic=%s",
                         type(exc).__name__, request.method,
                         getattr(route, "path", "<unmatched>"), request_id, mysql_code, category)
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
        allow_headers=["Authorization", "Content-Type", "Accept", "If-Match"],
        expose_headers=['Retry-After', 'X-Request-ID', 'ETag'],
    )
