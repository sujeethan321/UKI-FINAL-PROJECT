"""Read-only QR browser inventory. Run only through the private operator wrapper."""
import json

from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.database import Base, engine
from app.models import Business, CustomerJoinRequest, CustomerProfile, User  # noqa: F401: registers metadata
from check_qr_test_runtime import TARGET, USER, validate_identity


def summary(connection, statement):
    return {str(key): int(count) for key, count in connection.execute(statement)}


def main():
    if (settings.APP_ENV != "testing" or settings.MYSQL_DATABASE != TARGET
            or settings.MYSQL_USER != USER or engine.url.database != TARGET
            or engine.url.username != USER or engine.url.host != "localhost"
            or engine.url.port != 3306):
        raise ValueError("configured test target/account differs")

    with engine.connect() as connection:
        actual_db = connection.scalar(text("SELECT DATABASE()"))
        actual_user = connection.scalar(text("SELECT CURRENT_USER()"))
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        tables = {row[0] for row in connection.execute(text(
            "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()"
        ))}
        grants = [row[0] for row in connection.execute(text("SHOW GRANTS"))]
        validate_identity(settings.APP_ENV, settings.MYSQL_DATABASE, engine.url.database,
                          engine.url.username, actual_db, actual_user, revision, tables, grants)
        modeled = set(Base.metadata.tables)
        if modeled != tables - {"alembic_version"}:
            raise ValueError("test table inventory differs from modeled application tables")

        # End the preflight's implicit transaction. Start a consistent, explicitly
        # read-only MySQL snapshot on the same verified connection.
        connection.rollback()
        connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        try:
            if connection.scalar(text("SELECT DATABASE()")) != TARGET or \
                    connection.scalar(text("SELECT CURRENT_USER()")) != USER + "@localhost":
                raise ValueError("test target/account changed before inventory")
            role_counts = summary(connection, select(User.platform_role, func.count()).group_by(User.platform_role))
            user_status = summary(connection, select(User.account_status, func.count()).group_by(User.account_status))
            active_role_counts = summary(connection, select(User.platform_role, func.count()).where(
                User.account_status == "active").group_by(User.platform_role))
            business_status = summary(connection, select(Business.approval_status, func.count()).group_by(Business.approval_status))
            join_status = summary(connection, select(CustomerJoinRequest.status, func.count()).group_by(CustomerJoinRequest.status))
            active_admin_ids = list(connection.scalars(select(User.user_id).where(
                User.platform_role == "admin", User.account_status == "active"
            ).order_by(User.user_id).limit(21)))
            linked_profiles = connection.scalar(select(func.count()).select_from(CustomerProfile).where(
                CustomerProfile.user_id.is_not(None))) or 0
            row_counts = {name: int(connection.scalar(select(func.count()).select_from(Base.metadata.tables[name])) or 0)
                          for name in sorted(modeled)}
            evidence = {
                "database": actual_db,
                "account": actual_user,
                "revision": revision,
                "total_tables": len(tables),
                "grant_scope": "exact test database; global USAGE and DML only",
                "role_counts": role_counts,
                "user_status_counts": user_status,
                "active_role_counts": active_role_counts,
                "active_admin_count": active_role_counts.get("admin", 0),
                "active_admin_ids_sample": active_admin_ids[:20],
                "active_admin_ids_truncated": len(active_admin_ids) > 20,
                "business_status_counts": business_status,
                "customer_profiles_linked": int(linked_profiles),
                "customer_profiles_unlinked": row_counts["customer_profiles"] - int(linked_profiles),
                "join_request_status_counts": join_status,
                "application_row_counts": row_counts,
                "ownership": "unverified; all existing rows are protected until exact fixture evidence is reviewed",
            }
            print("PASS: exact QR test database/account/revision/tables/grants; read-only inventory")
            print(json.dumps(evidence, sort_keys=True))
        finally:
            connection.rollback()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("STOP: QR test inventory gate or read-only query failed; no application counts released") from None
