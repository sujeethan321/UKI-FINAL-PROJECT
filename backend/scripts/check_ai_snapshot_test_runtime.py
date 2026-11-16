"""Fail-closed exact-target gate for the dedicated AI snapshot test schema."""
import re

TARGET = "lankapex_ai_snapshot_test_db"
USER = "lankapex_ai_snap_runtime"
REVISION = "7b9e4d2c8a15"
SCOPE = r"`lankapex\_ai\_snapshot\_test\_db`.*"
PRIVILEGES = {"SELECT", "INSERT", "UPDATE", "DELETE"}
EXPECTED_TABLES = {
    "alembic_version", "admin_audits", "business_approval_audits", "business_join_links",
    "business_members", "business_settings", "businesses", "communication_attempts",
    "communication_consents", "credit_accounts", "customer_addresses",
    "customer_join_requests", "customer_link_invitations", "customer_profiles",
    "delivery_assignments", "delivery_requests", "delivery_status_events", "driver_profiles",
    "ledger_entries", "notifications", "order_items", "orders", "payment_reminders",
    "product_categories", "products", "user_preferences", "users", "vehicle_documents",
    "vehicles",
}


def validate_grants(grants):
    scoped, usage = set(), False
    for grant in grants:
        match = re.fullmatch(r"GRANT (.*?) ON (.*?) TO (.*)", grant, re.IGNORECASE)
        if not match or "GRANT OPTION" in grant.upper():
            raise ValueError("unreviewed grant")
        privileges = {item.strip().upper() for item in match.group(1).split(",")}
        if match.group(2) == "*.*":
            if privileges != {"USAGE"}:
                raise ValueError("global privilege exceeds USAGE")
            usage = True
        elif match.group(2) == SCOPE:
            scoped.update(privileges)
        else:
            raise ValueError("grant includes another or wildcard database")
    if not usage or scoped != PRIVILEGES:
        raise ValueError("runtime privileges differ")


def validate_runtime(environment, configured_db, configured_user, engine_db, engine_user,
                     actual_db, actual_user, revision, tables, grants, row_counts):
    expected = ("ai_snapshot_testing", TARGET, USER, TARGET, USER, TARGET, USER + "@localhost")
    if (environment, configured_db, configured_user, engine_db, engine_user,
            actual_db, actual_user) != expected:
        raise ValueError("test environment, database or account differs")
    if revision != REVISION:
        raise ValueError("schema revision differs")
    if tables != EXPECTED_TABLES:
        raise ValueError("table inventory differs")
    if set(row_counts) != tables - {"alembic_version"} or any(row_counts.values()):
        raise ValueError("dedicated test schema is not empty")
    validate_grants(grants)


def main():
    from sqlalchemy import text
    from app.core.config import settings
    from app.core.database import engine

    with engine.connect() as connection:
        actual_db = connection.scalar(text("SELECT DATABASE()"))
        actual_user = connection.scalar(text("SELECT CURRENT_USER()"))
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        tables = {row[0] for row in connection.execute(text(
            "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()"
        ))}
        grants = [row[0] for row in connection.execute(text("SHOW GRANTS"))]
        if tables != EXPECTED_TABLES:
            raise ValueError("table inventory differs")
        counts = {table: connection.scalar(text(f"SELECT COUNT(*) FROM `{table}`"))
                  for table in tables if table != "alembic_version"}
    validate_runtime(settings.APP_ENV, settings.MYSQL_DATABASE, settings.MYSQL_USER,
                     engine.url.database, engine.url.username, actual_db, actual_user,
                     revision, tables, grants, counts)
    print("PASS: exact empty AI snapshot test schema, revision, inventory and DML-only grant")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("STOP: AI snapshot test preflight failed; no tests started") from None
