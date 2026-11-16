"""Database-free exact-process gate for the loopback Tamil AI browser API."""
from urllib.parse import urlsplit


def validate_config(settings, engine_url, environment):
    expected = {
        "APP_ENV": "ai_snapshot_testing", "MYSQL_HOST": "localhost", "MYSQL_PORT": "3306",
        "MYSQL_DATABASE": "lankapex_ai_snapshot_test_db", "MYSQL_USER": "lankapex_ai_snap_runtime",
        "APP_DEBUG": "false", "LOG_LEVEL": "WARNING", "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:5175",
        "RATE_LIMIT_MODE": "local", "AI_ENABLED": "false", "LANKAPEX_DISABLE_DOTENV": "true",
    }
    if any(environment.get(key) != value for key, value in expected.items()):
        raise ValueError("browser process environment differs")
    if "GROQ_API_KEY" in environment:
        raise ValueError("browser process contains a Groq credential")
    if (settings.APP_ENV != expected["APP_ENV"] or settings.MYSQL_DATABASE != expected["MYSQL_DATABASE"]
            or settings.MYSQL_USER != expected["MYSQL_USER"] or settings.MYSQL_HOST != "localhost"
            or settings.MYSQL_PORT != 3306 or settings.APP_DEBUG or settings.LOG_LEVEL != "WARNING"
            or settings.CORS_ALLOWED_ORIGINS != [expected["CORS_ALLOWED_ORIGINS"]]
            or settings.RATE_LIMIT_MODE != "local" or settings.AI_ENABLED
            or settings.GROQ_API_KEY is not None):
        raise ValueError("effective browser configuration differs")
    if (engine_url.database != expected["MYSQL_DATABASE"] or engine_url.username != expected["MYSQL_USER"]
            or engine_url.host != "localhost" or engine_url.port != 3306):
        raise ValueError("database engine target differs")
    if not environment.get("MYSQL_PASSWORD") or not environment.get("JWT_SECRET_KEY"):
        raise ValueError("private browser credentials missing")
    if settings.JWT_SECRET_KEY != environment["JWT_SECRET_KEY"] or len(settings.JWT_SECRET_KEY) < 48:
        raise ValueError("browser JWT secret differs or is too short")
    if settings.MYSQL_PASSWORD != environment["MYSQL_PASSWORD"]:
        raise ValueError("database credential source differs")
    if urlsplit(expected["CORS_ALLOWED_ORIGINS"]).hostname != "127.0.0.1":
        raise ValueError("browser origin is not loopback")


def main():
    import os
    from app.core.config import settings
    from app.core.database import engine
    validate_config(settings, engine.url, os.environ)
    print("PASS: loopback Tamil AI API uses exact isolated process configuration")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("STOP: Tamil AI browser configuration gate failed") from None
