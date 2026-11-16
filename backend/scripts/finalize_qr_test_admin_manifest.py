"""Guarded local-only finalization of a reconciled QR test Admin manifest."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import bootstrap_qr_test_admin as bootstrap
import reconcile_qr_test_admin as reconcile
import recover_qr_test_admin as recovery

MANIFEST = recovery.NEW_MANIFEST
BACKUP = bootstrap.PRIVATE_DIR / "qr-browser-admin-recovery-fixture.pending-commit.backup.json"
TEMP = bootstrap.PRIVATE_DIR / "qr-browser-admin-recovery-fixture.replacement.tmp"


def validate_flags(execute, target, admin_id, pause):
    if execute:
        if target != bootstrap.TARGET or admin_id != reconcile.EXPECTED_USER_ID or not pause:
            raise ValueError("exact finalization confirmation missing")
    elif target is not None or admin_id is not None or pause:
        raise ValueError("execution flags require --execute")


def validate_pending(data):
    if (not isinstance(data, dict) or data.get("state") != "pending_commit"
            or data.get("database") != bootstrap.TARGET
            or data.get("account") != bootstrap.USER + "@localhost"
            or data.get("user_id") != reconcile.EXPECTED_USER_ID
            or not isinstance(data.get("audit_id"), int) or data["audit_id"] <= 0):
        raise ValueError("recovery manifest is not the expected pending fixture")


def read_pending(path):
    recovery.require_file(path)
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    validate_pending(data)
    return raw, data


def require_empty_reserved(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != 0:
        raise ValueError("private replacement reservation differs")


def write_fully(path, raw):
    with path.open("r+b") as stream:
        if stream.read(1):
            raise ValueError("private replacement reservation is not empty")
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def finalize_files(manifest=MANIFEST, backup=BACKUP, temp=TEMP, replace=os.replace):
    raw, data = read_pending(manifest)
    require_empty_reserved(backup)
    require_empty_reserved(temp)
    # The original pending bytes remain intact in a distinct, restricted file.
    write_fully(backup, raw)
    committed = {**data, "state": "committed"}
    replacement = json.dumps(committed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    write_fully(temp, replacement)
    if manifest.read_bytes() != raw:
        raise ValueError("manifest changed after reconciliation")
    replace(temp, manifest)  # same directory: atomic on the supported local filesystem
    if bootstrap.read_manifest(manifest) != committed:
        raise ValueError("final manifest verification failed")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-target")
    parser.add_argument("--confirm-admin-id", type=int)
    parser.add_argument("--confirm-writer-pause", action="store_true")
    args = parser.parse_args(argv)
    validate_flags(args.execute, args.confirm_target, args.confirm_admin_id,
                   args.confirm_writer_pause)
    if MANIFEST.is_symlink() or BACKUP.is_symlink() or TEMP.is_symlink():
        raise ValueError("private manifest path is a link")
    raw, data = read_pending(MANIFEST)
    digest = hashlib.sha256(raw).digest()
    if not args.execute and (BACKUP.exists() or TEMP.exists()):
        raise ValueError("previous finalization evidence exists")
    # Same process, fresh exact-target database/account/revision/grants, Admin,
    # audit, password and zero-dependent-row verification before any file write.
    reconcile.main()
    if hashlib.sha256(MANIFEST.read_bytes()).digest() != digest:
        raise ValueError("manifest changed during reconciliation")
    if not args.execute:
        print("PASS: finalization preflight only; manifest remains pending")
        return
    # The Windows wrapper must have created both empty, restricted reservations
    # only after its first read-only reconciliation. No implicit creation here.
    finalize_files()
    print("PASS: exact QR test Admin recovery manifest finalized; original pending bytes preserved privately")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("STOP: Admin manifest finalization failed; preserve all private evidence") from None
