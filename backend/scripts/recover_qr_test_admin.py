"""One-time QR test Admin recovery; preserves the failed attempt as evidence."""
import argparse
import re
from pathlib import Path

import bootstrap_qr_test_admin as bootstrap

OLD_MANIFEST = bootstrap.MANIFEST
OLD_PASSWORD = bootstrap.PASSWORD_FILE
NEW_MANIFEST = bootstrap.PRIVATE_DIR / "qr-browser-admin-recovery-fixture.json"
NEW_PASSWORD = bootstrap.PRIVATE_DIR / "qr-browser-admin-recovery-password.dpapi"
EMAIL = re.compile(r"qr-browser-admin-[0-9a-f]{32}@lankapex-test\.example\.com\Z")
RUN_ID = re.compile(r"[0-9a-f]{32}\Z")
MANIFEST_KEYS = {"state", "database", "account", "email", "run_id", "user_id", "audit_id"}


def validate_old_evidence(data, password_exists):
    if (not isinstance(data, dict) or set(data) != MANIFEST_KEYS
            or data.get("state") != "reserved"
            or data.get("database") != bootstrap.TARGET
            or data.get("account") != bootstrap.USER + "@localhost"
            or data.get("user_id") is not None or data.get("audit_id") is not None
            or not isinstance(data.get("email"), str)
            or EMAIL.fullmatch(data["email"]) is None
            or not isinstance(data.get("run_id"), str)
            or RUN_ID.fullmatch(data["run_id"]) is None
            or not password_exists):
        raise ValueError("failed-attempt evidence differs")


def validate_new_attempt(data, old_data, password_exists):
    validate_old_evidence(data, password_exists)
    if data["run_id"] == old_data["run_id"] or data["email"] == old_data["email"]:
        raise ValueError("recovery attempt reuses failed identity")


def require_file(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise ValueError("private evidence file missing or unsafe")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-target")
    parser.add_argument("--confirm-writer-pause", action="store_true")
    args = parser.parse_args(argv)
    bootstrap.validate_execution(args.execute, args.confirm_target, args.confirm_writer_pause)
    require_file(OLD_MANIFEST)
    require_file(OLD_PASSWORD)
    old_data = bootstrap.read_manifest(OLD_MANIFEST)
    validate_old_evidence(old_data, True)
    if args.execute:
        require_file(NEW_MANIFEST)
        require_file(NEW_PASSWORD)
        new_data = bootstrap.read_manifest(NEW_MANIFEST)
        validate_new_attempt(new_data, old_data, True)
        if NEW_PASSWORD.read_bytes() == OLD_PASSWORD.read_bytes():
            raise ValueError("recovery credential file was copied")
    elif NEW_MANIFEST.exists() or NEW_PASSWORD.exists():
        raise ValueError("recovery already reserved; preserve evidence")
    bootstrap.main(argv, manifest_path=NEW_MANIFEST, password_file=NEW_PASSWORD)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("STOP: QR test Admin recovery gate failed or commit state uncertain; preserve both attempts") from None
