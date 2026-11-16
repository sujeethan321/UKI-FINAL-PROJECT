"""Read-only, exact-target reconciliation of the committed QR test Admin."""
from sqlalchemy import func, select, text

import bootstrap_qr_test_admin as bootstrap
import recover_qr_test_admin as recovery

EXPECTED_USER_ID = 124671


def validate_evidence(old, current):
    recovery.validate_old_evidence(old, True)
    if (not isinstance(current, dict) or set(current) != recovery.MANIFEST_KEYS
            or current.get("state") != "pending_commit"
            or current.get("database") != bootstrap.TARGET
            or current.get("account") != bootstrap.USER + "@localhost"
            or current.get("user_id") != EXPECTED_USER_ID
            or not isinstance(current.get("audit_id"), int)
            or current["audit_id"] <= 0
            or not isinstance(current.get("email"), str)
            or recovery.EMAIL.fullmatch(current["email"]) is None
            or not isinstance(current.get("run_id"), str)
            or recovery.RUN_ID.fullmatch(current["run_id"]) is None
            or current["email"] == old["email"]
            or current["run_id"] == old["run_id"]):
        raise ValueError("recovery evidence differs")


def validate_rows(user, audit, counts, manifest, password, verify_password):
    if (user is None or audit is None or len(counts) != 28
            or counts.get("users") != 1 or counts.get("admin_audits") != 1
            or any(value != 0 for name, value in counts.items()
                   if name not in {"users", "admin_audits"})):
        raise ValueError("committed fixture inventory differs")
    if (user.user_id != EXPECTED_USER_ID or user.email != manifest["email"]
            or user.platform_role != "admin" or user.account_status != "active"
            or audit.audit_id != manifest["audit_id"]
            or audit.admin_user_id != EXPECTED_USER_ID
            or audit.target_type != "user" or audit.target_id != EXPECTED_USER_ID
            or audit.action != "admin_provisioned" or audit.new_state != "active"):
        raise ValueError("Admin or audit ownership differs")
    if not password or not verify_password(password, user.password_hash):
        raise ValueError("private recovery credential does not verify")


def main():
    import os
    from app.core.config import settings
    from app.core.database import Base, engine
    from app.core.security import verify_password
    from app.models import AdminAudit, User  # registers all modeled tables
    from check_qr_test_runtime import validate_identity

    for path in (recovery.OLD_MANIFEST, recovery.OLD_PASSWORD,
                 recovery.NEW_MANIFEST, recovery.NEW_PASSWORD):
        recovery.require_file(path)
    old = bootstrap.read_manifest(recovery.OLD_MANIFEST)
    current = bootstrap.read_manifest(recovery.NEW_MANIFEST)
    validate_evidence(old, current)
    credential = os.environ.get("QR_RECONCILE_ADMIN_PASSWORD", "")
    if len(credential) < 48:
        raise ValueError("private recovery credential unavailable")

    with engine.connect() as connection:
        bootstrap.verify_target(connection, settings, engine, Base, validate_identity)
        connection.rollback()
        connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        try:
            if (connection.scalar(text("SELECT DATABASE()")) != bootstrap.TARGET
                    or connection.scalar(text("SELECT CURRENT_USER()")) != bootstrap.USER + "@localhost"):
                raise ValueError("test target/account changed")
            user = connection.execute(select(
                User.user_id, User.email, User.platform_role, User.account_status,
                User.password_hash,
            ).where(User.user_id == EXPECTED_USER_ID)).one_or_none()
            audit = connection.execute(select(
                AdminAudit.audit_id, AdminAudit.admin_user_id, AdminAudit.target_type,
                AdminAudit.target_id, AdminAudit.action, AdminAudit.new_state,
            ).where(AdminAudit.audit_id == current["audit_id"])).one_or_none()
            counts = bootstrap.application_counts(connection, Base)
            validate_rows(user, audit, counts, current, credential, verify_password)
        finally:
            connection.rollback()
    print("PASS: exact test Admin, matching audit, private credential and zero dependent records; manifest unchanged")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("STOP: QR test Admin reconciliation failed; preserve manifests and credential") from None
