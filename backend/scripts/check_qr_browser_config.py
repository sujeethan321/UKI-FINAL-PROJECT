"""Database-free configuration gate for the loopback QR browser API."""
from urllib.parse import urlsplit


def validate_config(settings, engine_url, environment):
    expected = {
        "APP_ENV": "testing",
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "MYSQL_DATABASE": "lankapex_test_db",
        "MYSQL_USER": "lankapex_qr_test_runtime",
        "APP_DEBUG": "false",
        "LOG_LEVEL": "WARNING",
        "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:5174",
        "RATE_LIMIT_MODE": "local",
    }
    if any(environment.get(key) != value for key, value in expected.items()):
        raise ValueError("browser-test process environment differs")
    if (settings.APP_ENV != "testing" or settings.MYSQL_DATABASE != "lankapex_test_db"
            or settings.MYSQL_USER != "lankapex_qr_test_runtime"
            or settings.MYSQL_HOST != "localhost" or settings.MYSQL_PORT != 3306
            or settings.APP_DEBUG or settings.LOG_LEVEL != "WARNING"
            or settings.CORS_ALLOWED_ORIGINS != ["http://127.0.0.1:5174"]
            or settings.RATE_LIMIT_MODE != "local"):
        raise ValueError("effective browser-test configuration differs")
    if (engine_url.database != "lankapex_test_db" or
            engine_url.username != "lankapex_qr_test_runtime" or
            engine_url.host != "localhost" or engine_url.port != 3306):
        raise ValueError("database engine target differs")
    if not environment.get("MYSQL_PASSWORD") or not environment.get("JWT_SECRET_KEY"):
        raise ValueError("private browser-test credentials missing")
    if settings.JWT_SECRET_KEY != environment["JWT_SECRET_KEY"] or len(settings.JWT_SECRET_KEY) < 48:
        raise ValueError("browser-test JWT secret differs or is too short")
    if settings.MYSQL_PASSWORD != environment["MYSQL_PASSWORD"]:
        raise ValueError("database credential was not taken from process environment")
    if urlsplit(environment["CORS_ALLOWED_ORIGINS"]).hostname != "127.0.0.1":
        raise ValueError("browser-test origin is not loopback")


def main():
    import os
    from app.core.config import settings
    from app.core.database import engine
    validate_config(settings, engine.url, os.environ)
    print("PASS: loopback QR browser API uses exact test-only process configuration")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("STOP: QR browser configuration gate failed; server not started") from None
