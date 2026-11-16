"""One-time, exact-target QR browser Admin bootstrap; read-only by default."""
import argparse
import json
import os
from pathlib import Path

from sqlalchemy import func, select, text

TARGET = "lankapex_test_db"
USER = "lankapex_qr_test_runtime"
ROOT = Path(__file__).resolve().parents[2]
PRIVATE_DIR = ROOT / ".server-logs" / "private-test"
MANIFEST = PRIVATE_DIR / "qr-browser-admin-fixture.json"
PASSWORD_FILE = PRIVATE_DIR / "qr-browser-admin-password.dpapi"
LOCK_NAME = "lankapex_qr_test_admin_bootstrap"


def validate_execution(execute, confirm_target, confirm_writer_pause):
    if execute and (confirm_target != TARGET or not confirm_writer_pause):
        raise ValueError("execution confirmation or maintained writer pause missing")
    if not execute and (confirm_target is not None or confirm_writer_pause):
        raise ValueError("execution flags require --execute")


def require_empty(counts):
    if len(counts) != 28 or any(value != 0 for value in counts.values()):
        raise ValueError("unexpected application records or table inventory")


def validate_manifest(data, email, run_id):
    if (not isinstance(data, dict) or data.get("state") != "reserved"
            or data.get("database") != TARGET or data.get("email") != email
            or data.get("run_id") != run_id or data.get("user_id") is not None
            or data.get("audit_id") is not None):
        raise ValueError("private bootstrap reservation differs")


def write_manifest(data, path=None):
    # PowerShell created this file exclusively and restricted its ACL before
    # invoking Python. Never replace it with an inherited-ACL temporary file.
    with (path or MANIFEST).open("r+", encoding="utf-8") as stream:
        stream.seek(0)
        json.dump(data, stream, sort_keys=True)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())


def read_manifest(path):
    # The original operator reservation was written by Windows PowerShell's
    # BOM-emitting UTF-8 encoder. Accept that legacy encoding without relaxing
    # the exact reservation/identity checks that follow.
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify_target(connection, settings, engine, Base, validate_identity):
    if (settings.APP_ENV != "testing" or settings.MYSQL_DATABASE != TARGET
            or settings.MYSQL_USER != USER or engine.url.database != TARGET
            or engine.url.username != USER or engine.url.host != "localhost"
            or engine.url.port != 3306):
        raise ValueError("configured test target/account differs")
    database = connection.scalar(text("SELECT DATABASE()"))
    account = connection.scalar(text("SELECT CURRENT_USER()"))
    revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    tables = {row[0] for row in connection.execute(text(
        "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()"
    ))}
    grants = [row[0] for row in connection.execute(text("SHOW GRANTS"))]
    validate_identity(settings.APP_ENV, settings.MYSQL_DATABASE, engine.url.database,
                      engine.url.username, database, account, revision, tables, grants)
    if set(Base.metadata.tables) != tables - {"alembic_version"}:
        raise ValueError("modeled test table inventory differs")


def application_counts(connection, Base):
    return {name: int(connection.scalar(select(func.count()).select_from(table)) or 0)
            for name, table in Base.metadata.tables.items()}


def main(argv=None, *, manifest_path=None, password_file=None):
    manifest_path = manifest_path or MANIFEST
    password_file = password_file or PASSWORD_FILE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-target")
    parser.add_argument("--confirm-writer-pause", action="store_true")
    args = parser.parse_args(argv)
    validate_execution(args.execute, args.confirm_target, args.confirm_writer_pause)

    # Import the application only after the operator wrapper has installed its
    # private test-only process environment. Never read a password from argv.
    from sqlalchemy.orm import Session
    from app.core.config import settings
    from app.core.database import Base, engine
    from app.models import AdminAudit, User  # noqa: F401: loads all modeled tables
    from app.schemas.auth import ShopOwnerRegister
    from app.services.admin_provisioning import provision_admin
    from check_qr_test_runtime import validate_identity

    if manifest_path.is_symlink() or password_file.is_symlink():
        raise ValueError("private bootstrap paths must not be links")
    if manifest_path.exists() or password_file.exists():
        if not args.execute:
            raise ValueError("Admin bootstrap files already exist; no second attempt")
        if not manifest_path.is_file() or not password_file.is_file():
            raise ValueError("private bootstrap files differ")
    elif args.execute:
        raise ValueError("private bootstrap reservation and password missing")

    with engine.connect() as connection:
        verify_target(connection, settings, engine, Base, validate_identity)
        require_empty(application_counts(connection, Base))
        connection.rollback()
        if not args.execute:
            print("PASS: exact empty QR test target/account/revision/grants; Admin bootstrap preflight only")
            return

        email = os.environ.get("QR_BOOTSTRAP_EMAIL", "")
        password = os.environ.get("QR_BOOTSTRAP_PASSWORD", "")
        run_id = os.environ.get("QR_BOOTSTRAP_RUN_ID", "")
        if (not email.startswith("qr-browser-admin-") or not email.endswith("@lankapex-test.example.com")
                or len(password) < 48 or len(run_id) != 32):
            raise ValueError("private synthetic Admin identity/password missing")
        data = read_manifest(manifest_path)
        validate_manifest(data, email, run_id)
        registration = ShopOwnerRegister(full_name="QR Browser Admin", email=email, password=password)

        # A named lock serializes this bootstrap with another copy of itself.
        # The operator must separately maintain the writer pause for pytest and
        # browser clients. READ COMMITTED makes the second zero-row check fresh.
        connection = connection.execution_options(isolation_level="READ COMMITTED")
        if connection.scalar(text("SELECT GET_LOCK(:name, 0)"), {"name": LOCK_NAME}) != 1:
            raise ValueError("another Admin bootstrap holds the lock")
        try:
            verify_target(connection, settings, engine, Base, validate_identity)
            require_empty(application_counts(connection, Base))
            with Session(bind=connection, join_transaction_mode="rollback_only") as db:
                admin, created = provision_admin(db, registration)
                if not created:
                    raise ValueError("existing account cannot be promoted or reused")
                db.flush()
                audit_id = db.scalar(select(AdminAudit.audit_id).where(
                    AdminAudit.admin_user_id == admin.user_id,
                    AdminAudit.target_id == admin.user_id,
                    AdminAudit.action == "admin_provisioned",
                ))
                if audit_id is None:
                    raise ValueError("Admin audit was not created")
                counts = application_counts(connection, Base)
                if (counts.get("users") != 1 or counts.get("admin_audits") != 1
                        or any(value != 0 for name, value in counts.items()
                               if name not in {"users", "admin_audits"})):
                    raise ValueError("unexpected records before Admin commit")
                data.update(state="pending_commit", user_id=admin.user_id, audit_id=audit_id)
                write_manifest(data, manifest_path)
                connection.commit()
                verified = connection.execute(select(User).where(User.user_id == admin.user_id)).scalar_one_or_none()
                if (verified is None or verified.platform_role != "admin"
                        or verified.account_status != "active"
                        or verified.email != email):
                    raise ValueError("committed Admin verification failed")
                counts = application_counts(connection, Base)
                if (counts.get("users") != 1 or counts.get("admin_audits") != 1
                        or any(value != 0 for name, value in counts.items()
                               if name not in {"users", "admin_audits"})):
                    raise ValueError("committed application inventory differs")
                data["state"] = "committed"
                write_manifest(data, manifest_path)
                print(f"PASS: one active test Admin committed; user_id={admin.user_id}; private fixture manifest retained")
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.scalar(text("SELECT RELEASE_LOCK(:name)"), {"name": LOCK_NAME})
            connection.rollback()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("STOP: QR test Admin bootstrap failed or commit state is uncertain; preserve private files and inspect before any retry") from None
