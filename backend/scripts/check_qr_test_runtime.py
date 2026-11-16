"""Read-only, exact-target gate for the QR integration-test launcher."""
import re

TARGET = "lankapex_test_db"
USER = "lankapex_qr_test_runtime"
REVISION = "7b9e4d2c8a15"
SCOPE = r"`lankapex\_test\_db`.*"
PRIVILEGES = {"SELECT", "INSERT", "UPDATE", "DELETE"}


def validate_grants(grants):
    scoped = set()
    usage = False
    for grant in grants:
        match = re.fullmatch(r"GRANT (.*?) ON (.*?) TO (.*)", grant, re.IGNORECASE)
        if not match or "GRANT OPTION" in grant.upper():
            raise ValueError("unreviewed grant")
        privileges = {part.strip().upper() for part in match.group(1).split(",")}
        if match.group(2) == "*.*":
            if privileges != {"USAGE"}:
                raise ValueError("global privilege exceeds USAGE")
            usage = True
        elif match.group(2) == SCOPE:
            scoped.update(privileges)
        else:
            raise ValueError("grant includes another or wildcard database")
    if not usage or scoped != PRIVILEGES:
        raise ValueError("test-runtime privileges differ")


def validate_identity(configured_env, configured_db, engine_db, engine_user,
                      actual_db, actual_user, revision, tables, grants):
    if (configured_env, configured_db, engine_db, engine_user, actual_db, actual_user) != (
        "testing", TARGET, TARGET, USER, TARGET, USER + "@localhost"
    ):
        raise ValueError("test environment, database or account differs")
    if revision != REVISION:
        raise ValueError("QR test revision differs")
    if len(tables) != 29 or not {"alembic_version", "business_join_links",
                                    "customer_join_requests"}.issubset(tables):
        raise ValueError("QR test table inventory differs")
    validate_grants(grants)


def main():
    # Import configuration only after the parent process has installed the
    # test-only environment and privately decrypted its credential.
    from sqlalchemy import text
    from app.core.config import settings
    from app.core.database import engine

    if (settings.APP_ENV != "testing" or settings.MYSQL_DATABASE != TARGET
            or settings.MYSQL_USER != USER or engine.url.database != TARGET
            or engine.url.username != USER):
        raise ValueError("configured test target/account differs")
    with engine.connect() as connection:
        actual_db = connection.scalar(text("SELECT DATABASE()"))
        actual_user = connection.scalar(text("SELECT CURRENT_USER()"))
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        tables = {row[0] for row in connection.execute(text(
            "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()"
        ))}
        grants = [row[0] for row in connection.execute(text("SHOW GRANTS"))]
    validate_identity(settings.APP_ENV, settings.MYSQL_DATABASE,
                      engine.url.database, engine.url.username,
                      actual_db, actual_user, revision, tables, grants)
    print("PASS: isolated QR test runtime identity, revision, 29 tables and DML-only grant")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("STOP: QR test runtime preflight failed; no tests started") from None
