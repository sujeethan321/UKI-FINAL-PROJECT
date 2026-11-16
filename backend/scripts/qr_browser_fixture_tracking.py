"""Fail-closed ownership tracking for the isolated QR browser fixture.

This program never writes MySQL.  Its only write modes fill paths that the
PowerShell wrapper has already reserved with CreateNew in the private test
directory.  Database work uses one consistent, read-only transaction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

TARGET = "lankapex_test_db"
ACCOUNT = "lankapex_qr_test_runtime@localhost"
REVISION = "7b9e4d2c8a15"
ADMIN_ID = 124671
PINNED_FINAL_RUN = "6d2a5a8c093c48509bbc2878ae50ded3"
PINNED_FINAL_IDS = {
    "protected_admin_user_id": 124671,
    "protected_admin_audit_id": 704,
    "owner_user_id": 124672,
    "customer_user_id": 124673,
    "business_id": 82991,
    "membership_id": 54264,
    "approval_audit_id": 629,
    "approval_notification_id": 26522,
    "join_request_id": 4,
    "linked_customer_profile_id": 62982,
    "unlinked_business_profile_id": 62981,
}
RUN_ID = re.compile(r"[0-9a-f]{32}")
STAGES = (
    "reserved", "users_registered", "business_created", "business_approved",
    "join_link_created", "join_requested", "join_approved",
)
PRIVATE_DIR = (Path(__file__).resolve().parents[2] / ".server-logs" / "private-test").resolve()
ADMIN_MANIFEST = PRIVATE_DIR / "qr-browser-admin-recovery-fixture.json"

DIAGNOSTIC_CODES = {
    "committed Admin ownership evidence differs": "admin_manifest",
    "fixture reservation manifest differs": "fixture_manifest",
    "fixture credential ownership differs": "fixture_manifest_credentials",
    "fixture reservation timestamp missing": "fixture_manifest_timestamp",
    "completed fixture inventory differs": "application_inventory",
    "fixture users are missing or ambiguous": "fixture_user_lookup",
    "fixture user identity differs": "fixture_user_identity",
    "business ownership is missing or ambiguous": "business_lookup",
    "fixture business identity differs": "business_manifest_identity",
    "completed fixture evidence is missing or ambiguous": "relationship_evidence_shape",
    "protected Admin evidence differs": "protected_admin_relationship",
    "fixture user ownership differs": "fixture_user_relationship",
    "fixture business is not approved": "business_approval_state",
    "owner membership relationship differs": "owner_membership",
    "business approval relationship differs": "business_approval_audit",
    "approval notification relationship differs": "approval_notification",
    "permanent join link differs": "permanent_join_link",
    "approved join request relationship differs": "approved_join_request",
    "linked/unlinked customer profile pair differs": "customer_profile_pair",
    "protected Admin entered fixture ownership": "protected_admin_ownership",
    "test target/account changed": "database_identity_changed",
}


def diagnostic_code(error: Exception) -> str:
    """Return a non-sensitive category; never include exception or row values."""
    message = str(error)
    if message in DIAGNOSTIC_CODES:
        return DIAGNOSTIC_CODES[message]
    if message.endswith(" ownership is missing or ambiguous"):
        return "record_lookup_ambiguous"
    if message in {
        "test environment, database or account differs", "QR test revision differs",
        "QR test table inventory differs", "test-runtime privileges differ",
        "configured test target/account differs", "grant includes another or wildcard database",
        "global privilege exceeds USAGE", "unreviewed grant",
    }:
        return "runtime_safety_gate"
    return "unclassified_read_only_failure"


def identities(run_id: str) -> dict[str, str]:
    if RUN_ID.fullmatch(run_id) is None:
        raise ValueError("invalid fixture run identifier")
    return {
        "owner_email": f"qr-owner-{run_id}@lankapex-test.example.com",
        "customer_email": f"qr-customer-{run_id}@lankapex-test.example.com",
        "business_name": f"QR Browser Shop {run_id[:12]}",
        "registration_number": f"QR-{run_id}",
    }


def expected_path(kind: str, run_id: str, stage: str | None = None) -> Path:
    if RUN_ID.fullmatch(run_id) is None:
        raise ValueError("invalid fixture run identifier")
    names = {
        "manifest": f"qr-browser-fixture-{run_id}.json",
        "owner_credential": f"qr-browser-fixture-{run_id}-owner.dpapi",
        "customer_credential": f"qr-browser-fixture-{run_id}-customer.dpapi",
        "evidence": f"qr-browser-fixture-evidence-{run_id}-{stage}.json",
        "final_evidence": f"qr-browser-fixture-final-evidence-{run_id}.json",
    }
    if kind not in names or (kind == "evidence" and stage not in STAGES[1:]):
        raise ValueError("invalid private evidence path request")
    return PRIVATE_DIR / names[kind]


def canonical_json(value: dict) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def validate_pinned_final_report(report: dict, run_id: str) -> None:
    if (run_id != PINNED_FINAL_RUN or report.get("status") != "PASS"
            or report.get("mode") != "membership_authoritative"
            or report.get("database") != TARGET or report.get("account") != ACCOUNT
            or report.get("revision") != REVISION or report.get("run_id") != run_id
            or report.get("record_ids") != PINNED_FINAL_IDS
            or report.get("historical_snapshots") != "not captured; not fabricated"
            or report.get("financial_and_fulfilment_zero_state") is not True
            or report.get("financial_records") != 0 or report.get("orders") != 0
            or report.get("deliveries") != 0 or report.get("unrelated_application_records") != 0
            or report.get("database_changed") is not False
            or report.get("evidence_file_created") is not False):
        raise ValueError("pinned final reconciliation differs")
    identity = report.get("business_identity")
    if (not isinstance(identity, dict)
            or identity.get("business_found_via_exact_owner_membership") is not True
            or identity.get("business_approved") is not True
            or identity.get("business_name_matches_manifest") is not False
            or identity.get("registration_number_matches_manifest") is not False
            or identity.get("both_manifest_identifiers_match") is not False
            or identity.get("identity_discrepancy") is not True):
        raise ValueError("pinned business discrepancy differs")
    relationships = report.get("relationships")
    if (not isinstance(relationships, dict)
            or relationships.get("unlinked_profile") != "same fixture business; user_id is null; no account identity asserted"
            or relationships.get("unlinked_profile_dependents") != "zero"):
        raise ValueError("pinned unlinked-profile evidence differs")


def build_final_evidence(report: dict, manifest_bytes: bytes, captured_utc: str) -> dict:
    validate_pinned_final_report(report, report.get("run_id"))
    evidence = {
        "version": 1,
        "evidence_type": "qr_browser_final_membership_reconciliation",
        "state": "final",
        "captured_utc": captured_utc,
        "reservation_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "reconciliation": report,
    }
    evidence["evidence_payload_sha256"] = hashlib.sha256(canonical_json(evidence)).hexdigest()
    return evidence


def validate_final_evidence(value: dict) -> None:
    expected_keys = {"version", "evidence_type", "state", "captured_utc",
                     "reservation_manifest_sha256", "reconciliation", "evidence_payload_sha256"}
    if (set(value) != expected_keys or value.get("version") != 1
            or value.get("evidence_type") != "qr_browser_final_membership_reconciliation"
            or value.get("state") != "final" or not isinstance(value.get("captured_utc"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", value.get("reservation_manifest_sha256", ""))
            or not re.fullmatch(r"[0-9a-f]{64}", value.get("evidence_payload_sha256", ""))):
        raise ValueError("final evidence format differs")
    fingerprint = value["evidence_payload_sha256"]
    body = {key: item for key, item in value.items() if key != "evidence_payload_sha256"}
    if hashlib.sha256(canonical_json(body)).hexdigest() != fingerprint:
        raise ValueError("final evidence integrity differs")
    validate_pinned_final_report(value["reconciliation"], PINNED_FINAL_RUN)


def require_exact_path(path: Path, kind: str, run_id: str, stage: str | None = None) -> None:
    if path.resolve() != expected_path(kind, run_id, stage).resolve():
        raise ValueError("private output path differs")


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("private evidence format differs")
    return value


def validate_admin_manifest(value: dict) -> None:
    if (value.get("state") != "committed" or value.get("database") != TARGET
            or value.get("account") != ACCOUNT or value.get("user_id") != ADMIN_ID
            or not isinstance(value.get("audit_id"), int) or value["audit_id"] <= 0):
        raise ValueError("committed Admin ownership evidence differs")


def validate_manifest(value: dict, run_id: str) -> None:
    wanted = identities(run_id)
    expected_keys = {
        "version", "state", "database", "account", "revision", "admin_user_id",
        "run_id", "created_utc", "identities", "credential_files",
    }
    if (set(value) != expected_keys or value.get("version") != 1
            or value.get("state") != "reserved" or value.get("database") != TARGET
            or value.get("account") != ACCOUNT or value.get("revision") != REVISION
            or value.get("admin_user_id") != ADMIN_ID or value.get("run_id") != run_id
            or value.get("identities") != wanted):
        raise ValueError("fixture reservation manifest differs")
    expected_credentials = {
        "owner": expected_path("owner_credential", run_id).name,
        "customer": expected_path("customer_credential", run_id).name,
    }
    if value.get("credential_files") != expected_credentials:
        raise ValueError("fixture credential ownership differs")
    if not isinstance(value.get("created_utc"), str):
        raise ValueError("fixture reservation timestamp missing")


def validate_counts(counts: dict[str, int], stage: str, tables: set[str]) -> None:
    expected = {name: 0 for name in tables if name != "alembic_version"}
    expected.update({"users": 1, "admin_audits": 1})
    if stage != "reserved":
        expected["users"] = 3
    if STAGES.index(stage) >= STAGES.index("business_created"):
        expected.update({"businesses": 1, "business_members": 1})
    if STAGES.index(stage) >= STAGES.index("business_approved"):
        expected.update({"business_approval_audits": 1, "notifications": 1})
    if STAGES.index(stage) >= STAGES.index("join_link_created"):
        expected["business_join_links"] = 1
    if STAGES.index(stage) >= STAGES.index("join_requested"):
        expected["customer_join_requests"] = 1
    if stage == "join_approved":
        expected["customer_profiles"] = 1
    if set(counts) != set(expected) or counts != expected:
        raise ValueError("application inventory differs from the selected fixture stage")


def validate_reconciled_counts(counts: dict[str, int], tables: set[str]) -> None:
    """Validate the observed completed run without inventing historical stages."""
    expected = {name: 0 for name in tables if name != "alembic_version"}
    expected.update({
        "users": 3, "admin_audits": 1, "businesses": 1,
        "business_members": 1, "business_approval_audits": 1,
        "notifications": 1, "business_join_links": 1,
        "customer_join_requests": 1, "customer_profiles": 2,
    })
    if set(counts) != set(expected) or counts != expected:
        raise ValueError("completed fixture inventory differs")


def validate_reconciled_rows(rows: dict) -> dict[str, int]:
    """Pure relationship validator used by the live checker and safety tests."""
    required = {"admin", "admin_audit", "owner", "customer", "business", "membership",
                "approval", "notification", "link", "request", "profiles"}
    if set(rows) != required or not isinstance(rows["profiles"], list) or len(rows["profiles"]) != 2:
        raise ValueError("completed fixture evidence is missing or ambiguous")
    admin, admin_audit = rows["admin"], rows["admin_audit"]
    owner, customer, business = rows["owner"], rows["customer"], rows["business"]
    membership, approval, notification = rows["membership"], rows["approval"], rows["notification"]
    link, request = rows["link"], rows["request"]
    if (admin["user_id"] != ADMIN_ID or admin["platform_role"] != "admin" or admin["account_status"] != "active"
            or admin_audit["admin_user_id"] != ADMIN_ID or admin_audit["target_id"] != ADMIN_ID
            or admin_audit["action"] != "admin_provisioned"):
        raise ValueError("protected Admin evidence differs")
    if (owner["platform_role"] != "shop_owner" or owner["account_status"] != "active"
            or customer["platform_role"] != "customer" or customer["account_status"] != "active"
            or ADMIN_ID in {owner["user_id"], customer["user_id"]}
            or owner["user_id"] == customer["user_id"]):
        raise ValueError("fixture user ownership differs")
    if business["approval_status"] != "approved":
        raise ValueError("fixture business is not approved")
    if (membership["business_id"] != business["business_id"] or membership["user_id"] != owner["user_id"]
            or membership["business_role"] != "owner" or membership["membership_status"] != "active"):
        raise ValueError("owner membership relationship differs")
    if (approval["business_id"] != business["business_id"] or approval["admin_user_id"] != ADMIN_ID
            or approval["decision"] != "approve" or approval["previous_status"] != "pending"
            or approval["new_status"] != "approved"):
        raise ValueError("business approval relationship differs")
    if (notification["recipient_user_id"] != owner["user_id"]
            or notification["business_id"] != business["business_id"]
            or notification["notification_type"] != "business_approved"
            or notification["related_entity_type"] != "business_approval_audit"
            or notification["related_entity_id"] != approval["audit_id"]):
        raise ValueError("approval notification relationship differs")
    if link["business_id"] != business["business_id"] or re.fullmatch(r"[A-Za-z0-9_-]{32}", link["public_code"]) is None:
        raise ValueError("permanent join link differs")
    if (request["business_id"] != business["business_id"]
            or request["customer_user_id"] != customer["user_id"] or request["status"] != "approved"
            or request["decided_by"] != owner["user_id"] or request["decided_at"] is None):
        raise ValueError("approved join request relationship differs")
    linked = [row for row in rows["profiles"] if row["user_id"] == customer["user_id"]]
    unlinked = [row for row in rows["profiles"] if row["user_id"] is None]
    if (len(linked) != 1 or len(unlinked) != 1
            or linked[0]["business_id"] != business["business_id"]
            or unlinked[0]["business_id"] != business["business_id"]):
        raise ValueError("linked/unlinked customer profile pair differs")
    ids = {
        "protected_admin_user_id": admin["user_id"],
        "protected_admin_audit_id": admin_audit["audit_id"],
        "owner_user_id": owner["user_id"], "customer_user_id": customer["user_id"],
        "business_id": business["business_id"], "membership_id": membership["membership_id"],
        "approval_audit_id": approval["audit_id"],
        "approval_notification_id": notification["notification_id"],
        "join_request_id": request["request_id"],
        "linked_customer_profile_id": linked[0]["customer_id"],
        "unlinked_business_profile_id": unlinked[0]["customer_id"],
    }
    if ADMIN_ID in {value for key, value in ids.items() if not key.startswith("protected_")}:
        raise ValueError("protected Admin entered fixture ownership")
    return ids


def validate_business_membership_lookup(owner: dict, owned_business: dict, manifest: dict) -> dict[str, bool]:
    """Validate ownership-first lookup and expose only non-sensitive booleans."""
    if (owner.get("platform_role") != "shop_owner" or owner.get("account_status") != "active"
            or owner.get("user_id") == ADMIN_ID):
        raise ValueError("fixture user ownership differs")
    if (owned_business.get("user_id") != owner.get("user_id")
            or owned_business.get("business_role") != "owner"
            or owned_business.get("membership_status") != "active"):
        raise ValueError("owner membership relationship differs")
    if owned_business.get("approval_status") != "approved":
        raise ValueError("fixture business is not approved")
    expected = manifest["identities"]
    name_matches = owned_business.get("business_name") == expected["business_name"]
    registration_matches = owned_business.get("registration_number") == expected["registration_number"]
    return {
        "business_found_via_exact_owner_membership": True,
        "business_approved": True,
        "business_name_matches_manifest": name_matches,
        "registration_number_matches_manifest": registration_matches,
        "both_manifest_identifiers_match": name_matches and registration_matches,
        "identity_discrepancy": not (name_matches and registration_matches),
    }


def validate_evidence(value: dict, manifest: dict, stage: str) -> None:
    if (value.get("version") != 1 or value.get("database") != TARGET
            or value.get("account") != ACCOUNT or value.get("revision") != REVISION
            or value.get("run_id") != manifest["run_id"] or value.get("stage") != stage
            or value.get("admin_user_id") != ADMIN_ID
            or not isinstance(value.get("record_ids"), dict)
            or not isinstance(value.get("table_counts"), dict)
            or not isinstance(value.get("financial_zero_state"), bool)
            or value.get("financial_zero_state") is not True):
        raise ValueError("fixture evidence differs")


def write_reserved_json(path: Path, value: dict) -> None:
    if not path.is_file() or path.is_symlink() or path.stat().st_size != 0:
        raise ValueError("private output was not reserved as an empty regular file")
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    with path.open("r+b", buffering=0) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _one(rows, label: str):
    rows = list(rows)
    if len(rows) != 1:
        raise ValueError(f"{label} ownership is missing or ambiguous")
    return rows[0]


def collect_database_evidence(connection, base, manifest: dict, stage: str) -> dict:
    from sqlalchemy import text

    tables = set(base.metadata.tables)
    counts = {name: int(connection.scalar(text(f"SELECT COUNT(*) FROM `{name}`"))) for name in tables}
    validate_counts(counts, stage, tables)
    admin_manifest = read_json(ADMIN_MANIFEST)
    validate_admin_manifest(admin_manifest)
    admin = _one(connection.execute(text(
        "SELECT user_id, platform_role, account_status FROM users WHERE user_id=:id"
    ), {"id": ADMIN_ID}).mappings(), "Admin")
    admin_audit = _one(connection.execute(text(
        "SELECT audit_id, admin_user_id, action, target_id FROM admin_audits WHERE audit_id=:id"
    ), {"id": admin_manifest["audit_id"]}).mappings(), "Admin audit")
    if (admin["platform_role"] != "admin" or admin["account_status"] != "active"
            or admin_audit["admin_user_id"] != ADMIN_ID
            or admin_audit["target_id"] != ADMIN_ID or admin_audit["action"] != "admin_provisioned"):
        raise ValueError("protected Admin evidence differs")

    ids = {"owner_user_id": None, "customer_user_id": None, "business_id": None,
           "membership_id": None, "approval_audit_id": None, "approval_notification_id": None,
           "join_request_id": None, "customer_profile_id": None}
    qr_hash = None
    names = manifest["identities"]
    if stage != "reserved":
        users = list(connection.execute(text(
            "SELECT user_id,email,platform_role,account_status FROM users WHERE email IN (:owner,:customer)"
        ), {"owner": names["owner_email"], "customer": names["customer_email"]}).mappings())
        if len(users) != 2:
            raise ValueError("fixture user ownership is missing or ambiguous")
        by_email = {row["email"]: row for row in users}
        owner = by_email.get(names["owner_email"]); customer = by_email.get(names["customer_email"])
        if (not owner or owner["platform_role"] != "shop_owner" or owner["account_status"] != "active"
                or not customer or customer["platform_role"] != "customer" or customer["account_status"] != "active"
                or ADMIN_ID in {owner["user_id"], customer["user_id"]}):
            raise ValueError("fixture user roles or states differ")
        ids.update(owner_user_id=owner["user_id"], customer_user_id=customer["user_id"])
    if STAGES.index(stage) >= STAGES.index("business_created"):
        business = _one(connection.execute(text(
            "SELECT business_id,business_name,registration_number,approval_status FROM businesses "
            "WHERE business_name=:name OR registration_number=:registration"
        ), {"name": names["business_name"], "registration": names["registration_number"]}).mappings(), "business")
        expected_status = "pending" if stage == "business_created" else "approved"
        if (business["business_name"] != names["business_name"]
                or business["registration_number"] != names["registration_number"]
                or business["approval_status"] != expected_status):
            raise ValueError("fixture business identity or status differs")
        membership = _one(connection.execute(text(
            "SELECT membership_id,business_id,user_id,business_role,membership_status FROM business_members"
        )).mappings(), "owner membership")
        if (membership["business_id"] != business["business_id"] or membership["user_id"] != ids["owner_user_id"]
                or membership["business_role"] != "owner" or membership["membership_status"] != "active"):
            raise ValueError("owner membership relationship differs")
        ids.update(business_id=business["business_id"], membership_id=membership["membership_id"])
    if STAGES.index(stage) >= STAGES.index("business_approved"):
        approval = _one(connection.execute(text(
            "SELECT audit_id,business_id,admin_user_id,decision,previous_status,new_status "
            "FROM business_approval_audits"
        )).mappings(), "business approval audit")
        if (approval["business_id"] != ids["business_id"] or approval["admin_user_id"] != ADMIN_ID
                or approval["decision"] != "approve" or approval["previous_status"] != "pending"
                or approval["new_status"] != "approved"):
            raise ValueError("business approval ownership differs")
        notification = _one(connection.execute(text(
            "SELECT notification_id,recipient_user_id,business_id,notification_type,related_entity_type,related_entity_id "
            "FROM notifications"
        )).mappings(), "approval notification")
        if (notification["recipient_user_id"] != ids["owner_user_id"]
                or notification["business_id"] != ids["business_id"]
                or notification["notification_type"] != "business_approved"
                or notification["related_entity_type"] != "business_approval_audit"
                or notification["related_entity_id"] != approval["audit_id"]):
            raise ValueError("approval notification ownership differs")
        ids.update(approval_audit_id=approval["audit_id"], approval_notification_id=notification["notification_id"])
    if STAGES.index(stage) >= STAGES.index("join_link_created"):
        link = _one(connection.execute(text(
            "SELECT business_id,public_code FROM business_join_links"
        )).mappings(), "business join link")
        if link["business_id"] != ids["business_id"] or not re.fullmatch(r"[A-Za-z0-9_-]{32}", link["public_code"]):
            raise ValueError("business join link ownership differs")
        qr_hash = hashlib.sha256(link["public_code"].encode()).hexdigest()
    if STAGES.index(stage) >= STAGES.index("join_requested"):
        request = _one(connection.execute(text(
            "SELECT request_id,business_id,customer_user_id,status,decided_by FROM customer_join_requests"
        )).mappings(), "customer join request")
        expected_status = "approved" if stage == "join_approved" else "pending"
        expected_decider = ids["owner_user_id"] if stage == "join_approved" else None
        if (request["business_id"] != ids["business_id"]
                or request["customer_user_id"] != ids["customer_user_id"]
                or request["status"] != expected_status or request["decided_by"] != expected_decider):
            raise ValueError("customer join request ownership differs")
        ids["join_request_id"] = request["request_id"]
    if stage == "join_approved":
        profile = _one(connection.execute(text(
            "SELECT customer_id,business_id,user_id FROM customer_profiles"
        )).mappings(), "linked customer profile")
        if profile["business_id"] != ids["business_id"] or profile["user_id"] != ids["customer_user_id"]:
            raise ValueError("linked customer profile ownership differs")
        ids["customer_profile_id"] = profile["customer_id"]

    financial_tables = {"credit_accounts", "ledger_entries", "payment_reminders", "orders", "order_items",
                        "delivery_requests", "delivery_assignments", "delivery_status_events"}
    if any(counts.get(name, 0) != 0 for name in financial_tables):
        raise ValueError("financial or fulfilment zero-state differs")
    return {"version": 1, "database": TARGET, "account": ACCOUNT, "revision": REVISION,
            "run_id": manifest["run_id"], "stage": stage, "captured_utc": datetime.now(timezone.utc).isoformat(),
            "admin_user_id": ADMIN_ID, "record_ids": ids, "join_code_sha256": qr_hash,
            "table_counts": counts, "financial_zero_state": True}


def verify_previous_evidence(run_id: str, manifest: dict, stage: str) -> None:
    index = STAGES.index(stage)
    if index <= 1:
        return
    previous = STAGES[index - 1]
    value = read_json(expected_path("evidence", run_id, previous))
    validate_evidence(value, manifest, previous)


def validate_cleanup(evidence: dict, manifest: dict) -> list[str]:
    validate_evidence(evidence, manifest, "join_approved")
    ids = evidence["record_ids"]
    required = {"owner_user_id", "customer_user_id", "business_id", "membership_id",
                "approval_audit_id", "approval_notification_id", "join_request_id", "customer_profile_id"}
    if set(ids) != required or any(not isinstance(ids[name], int) or ids[name] <= 0 for name in required):
        raise ValueError("cleanup ownership IDs are incomplete")
    if ADMIN_ID in ids.values():
        raise ValueError("protected Admin cannot be fixture-owned or cleaned")
    return ["notifications", "customer_profiles", "customer_join_requests", "business_join_links",
            "business_approval_audits", "business_members", "businesses", "users(customer)", "users(owner)"]


def live_snapshot(manifest: dict, stage: str) -> dict:
    from sqlalchemy import text
    from app.core.config import settings
    from app.core.database import Base, engine
    from app.models import User  # noqa: F401 - registers all modeled tables
    from check_qr_test_runtime import validate_identity

    with engine.connect() as connection:
        actual_db = connection.scalar(text("SELECT DATABASE()")); actual_user = connection.scalar(text("SELECT CURRENT_USER()"))
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        tables = {row[0] for row in connection.execute(text(
            "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()"))}
        grants = [row[0] for row in connection.execute(text("SHOW GRANTS"))]
        validate_identity(settings.APP_ENV, settings.MYSQL_DATABASE, engine.url.database, engine.url.username,
                          actual_db, actual_user, revision, tables, grants)
        connection.rollback()
        connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        try:
            if connection.scalar(text("SELECT DATABASE()")) != TARGET or connection.scalar(text("SELECT CURRENT_USER()")) != ACCOUNT:
                raise ValueError("test target/account changed")
            return collect_database_evidence(connection, Base, manifest, stage)
        finally:
            connection.rollback()


def reconcile_final_state(manifest: dict) -> dict:
    """Read-only reconciliation when historical stage snapshots were skipped."""
    from sqlalchemy import text
    from app.core.config import settings
    from app.core.database import Base, engine
    from app.models import User  # noqa: F401 - registers all modeled tables
    from check_qr_test_runtime import validate_identity

    admin_manifest = read_json(ADMIN_MANIFEST)
    validate_admin_manifest(admin_manifest)
    names = manifest["identities"]
    with engine.connect() as connection:
        actual_db = connection.scalar(text("SELECT DATABASE()"))
        actual_user = connection.scalar(text("SELECT CURRENT_USER()"))
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        tables = {row[0] for row in connection.execute(text(
            "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()"))}
        grants = [row[0] for row in connection.execute(text("SHOW GRANTS"))]
        validate_identity(settings.APP_ENV, settings.MYSQL_DATABASE, engine.url.database, engine.url.username,
                          actual_db, actual_user, revision, tables, grants)
        connection.rollback()
        connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        try:
            if connection.scalar(text("SELECT DATABASE()")) != TARGET or connection.scalar(text("SELECT CURRENT_USER()")) != ACCOUNT:
                raise ValueError("test target/account changed")
            modeled = set(Base.metadata.tables)
            counts = {name: int(connection.scalar(text(f"SELECT COUNT(*) FROM `{name}`"))) for name in modeled}
            validate_reconciled_counts(counts, modeled)
            users = list(connection.execute(text(
                "SELECT user_id,email,full_name,platform_role,account_status FROM users "
                "WHERE email IN (:owner,:customer)"
            ), {"owner": names["owner_email"], "customer": names["customer_email"]}).mappings())
            if len(users) != 2:
                raise ValueError("fixture users are missing or ambiguous")
            by_email = {row["email"]: row for row in users}
            business = _one(connection.execute(text(
                "SELECT business_id,business_name,registration_number,approval_status FROM businesses "
                "WHERE business_name=:name OR registration_number=:registration"
            ), {"name": names["business_name"], "registration": names["registration_number"]}).mappings(), "business")
            if business["business_name"] != names["business_name"] or business["registration_number"] != names["registration_number"]:
                raise ValueError("fixture business identity differs")
            rows = {
                "admin": _one(connection.execute(text(
                    "SELECT user_id,platform_role,account_status FROM users WHERE user_id=:id"
                ), {"id": ADMIN_ID}).mappings(), "Admin"),
                "admin_audit": _one(connection.execute(text(
                    "SELECT audit_id,admin_user_id,target_id,action FROM admin_audits WHERE audit_id=:id"
                ), {"id": admin_manifest["audit_id"]}).mappings(), "Admin audit"),
                "owner": by_email.get(names["owner_email"]),
                "customer": by_email.get(names["customer_email"]),
                "business": business,
                "membership": _one(connection.execute(text(
                    "SELECT membership_id,business_id,user_id,business_role,membership_status FROM business_members"
                )).mappings(), "membership"),
                "approval": _one(connection.execute(text(
                    "SELECT audit_id,business_id,admin_user_id,decision,previous_status,new_status FROM business_approval_audits"
                )).mappings(), "approval audit"),
                "notification": _one(connection.execute(text(
                    "SELECT notification_id,recipient_user_id,business_id,notification_type,related_entity_type,related_entity_id FROM notifications"
                )).mappings(), "approval notification"),
                "link": _one(connection.execute(text(
                    "SELECT business_id,public_code FROM business_join_links"
                )).mappings(), "join link"),
                "request": _one(connection.execute(text(
                    "SELECT request_id,business_id,customer_user_id,status,decided_by,decided_at FROM customer_join_requests"
                )).mappings(), "join request"),
                "profiles": list(connection.execute(text(
                    "SELECT customer_id,business_id,user_id,customer_name FROM customer_profiles ORDER BY customer_id"
                )).mappings()),
            }
            if rows["owner"] is None or rows["customer"] is None:
                raise ValueError("fixture user identity differs")
            ids = validate_reconciled_rows(rows)
            return {
                "status": "PASS", "database": TARGET, "account": ACCOUNT, "revision": REVISION,
                "run_id": manifest["run_id"], "historical_snapshots": "not captured; not fabricated",
                "record_ids": ids,
                "relationships": {
                    "owner_membership": "verified", "admin_business_approval": "verified",
                    "owner_approval_notification": "verified", "approved_customer_join": "verified",
                    "linked_customer_profile": "verified",
                    "unlinked_profile": "same fixture business; user_id is null; no account identity asserted",
                },
                "join_code_sha256": hashlib.sha256(rows["link"]["public_code"].encode()).hexdigest(),
                "financial_and_fulfilment_zero_state": True,
                "database_changed": False, "evidence_file_created": False,
            }
        finally:
            connection.rollback()


def diagnose_business_lookup(manifest: dict) -> dict:
    """Find the fixture business through exact Owner identity and membership."""
    from sqlalchemy import text
    from app.core.config import settings
    from app.core.database import Base, engine
    from app.models import User  # noqa: F401 - registers all modeled tables
    from check_qr_test_runtime import validate_identity

    admin_manifest = read_json(ADMIN_MANIFEST)
    validate_admin_manifest(admin_manifest)
    names = manifest["identities"]
    with engine.connect() as connection:
        actual_db = connection.scalar(text("SELECT DATABASE()"))
        actual_user = connection.scalar(text("SELECT CURRENT_USER()"))
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        tables = {row[0] for row in connection.execute(text(
            "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()"))}
        grants = [row[0] for row in connection.execute(text("SHOW GRANTS"))]
        validate_identity(settings.APP_ENV, settings.MYSQL_DATABASE, engine.url.database, engine.url.username,
                          actual_db, actual_user, revision, tables, grants)
        connection.rollback()
        connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        try:
            if connection.scalar(text("SELECT DATABASE()")) != TARGET or connection.scalar(text("SELECT CURRENT_USER()")) != ACCOUNT:
                raise ValueError("test target/account changed")
            modeled = set(Base.metadata.tables)
            counts = {name: int(connection.scalar(text(f"SELECT COUNT(*) FROM `{name}`"))) for name in modeled}
            validate_reconciled_counts(counts, modeled)
            admin = _one(connection.execute(text(
                "SELECT user_id,platform_role,account_status FROM users WHERE user_id=:id"
            ), {"id": ADMIN_ID}).mappings(), "Admin")
            admin_audit = _one(connection.execute(text(
                "SELECT audit_id,admin_user_id,target_id,action FROM admin_audits WHERE audit_id=:id"
            ), {"id": admin_manifest["audit_id"]}).mappings(), "Admin audit")
            if (admin["platform_role"] != "admin" or admin["account_status"] != "active"
                    or admin_audit["admin_user_id"] != ADMIN_ID or admin_audit["target_id"] != ADMIN_ID
                    or admin_audit["action"] != "admin_provisioned"):
                raise ValueError("protected Admin evidence differs")
            owner = _one(connection.execute(text(
                "SELECT user_id,platform_role,account_status FROM users WHERE email=:owner_email"
            ), {"owner_email": names["owner_email"]}).mappings(), "fixture Owner")
            owned_business = _one(connection.execute(text(
                "SELECT bm.membership_id,bm.user_id,bm.business_role,bm.membership_status,"
                "b.business_id,b.business_name,b.registration_number,b.approval_status "
                "FROM business_members bm JOIN businesses b ON b.business_id=bm.business_id "
                "WHERE bm.user_id=:owner_id AND bm.business_role='owner' AND bm.membership_status='active'"
            ), {"owner_id": owner["user_id"]}).mappings(), "owner business membership")
            result = validate_business_membership_lookup(owner, owned_business, manifest)
            return {
                "status": "PASS", "database": TARGET, "account": ACCOUNT,
                "revision": REVISION, "run_id": manifest["run_id"],
                **result, "actual_business_values_exposed": False,
                "database_changed": False, "evidence_file_created": False,
            }
        finally:
            connection.rollback()


def reconcile_final_by_membership(manifest: dict) -> dict:
    """Full final reconciliation with Owner membership as business authority."""
    from sqlalchemy import text
    from app.core.config import settings
    from app.core.database import Base, engine
    from app.models import User  # noqa: F401 - registers all modeled tables
    from check_qr_test_runtime import validate_identity

    admin_manifest = read_json(ADMIN_MANIFEST)
    validate_admin_manifest(admin_manifest)
    names = manifest["identities"]
    with engine.connect() as connection:
        actual_db = connection.scalar(text("SELECT DATABASE()"))
        actual_user = connection.scalar(text("SELECT CURRENT_USER()"))
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        tables = {row[0] for row in connection.execute(text(
            "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()"))}
        grants = [row[0] for row in connection.execute(text("SHOW GRANTS"))]
        validate_identity(settings.APP_ENV, settings.MYSQL_DATABASE, engine.url.database, engine.url.username,
                          actual_db, actual_user, revision, tables, grants)
        connection.rollback()
        connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        try:
            if connection.scalar(text("SELECT DATABASE()")) != TARGET or connection.scalar(text("SELECT CURRENT_USER()")) != ACCOUNT:
                raise ValueError("test target/account changed")
            modeled = set(Base.metadata.tables)
            counts = {name: int(connection.scalar(text(f"SELECT COUNT(*) FROM `{name}`"))) for name in modeled}
            validate_reconciled_counts(counts, modeled)

            owner = _one(connection.execute(text(
                "SELECT user_id,email,platform_role,account_status FROM users WHERE email=:owner_email"
            ), {"owner_email": names["owner_email"]}).mappings(), "fixture Owner")
            customer = _one(connection.execute(text(
                "SELECT user_id,email,platform_role,account_status FROM users WHERE email=:customer_email"
            ), {"customer_email": names["customer_email"]}).mappings(), "fixture Customer")
            owned_business = _one(connection.execute(text(
                "SELECT bm.membership_id,bm.user_id,bm.business_role,bm.membership_status,"
                "b.business_id,b.business_name,b.registration_number,b.approval_status "
                "FROM business_members bm JOIN businesses b ON b.business_id=bm.business_id "
                "WHERE bm.user_id=:owner_id AND bm.business_role='owner' AND bm.membership_status='active'"
            ), {"owner_id": owner["user_id"]}).mappings(), "owner business membership")
            discrepancy = validate_business_membership_lookup(owner, owned_business, manifest)

            rows = {
                "admin": _one(connection.execute(text(
                    "SELECT user_id,platform_role,account_status FROM users WHERE user_id=:id"
                ), {"id": ADMIN_ID}).mappings(), "Admin"),
                "admin_audit": _one(connection.execute(text(
                    "SELECT audit_id,admin_user_id,target_id,action FROM admin_audits WHERE audit_id=:id"
                ), {"id": admin_manifest["audit_id"]}).mappings(), "Admin audit"),
                "owner": owner,
                "customer": customer,
                "business": owned_business,
                "membership": owned_business,
                "approval": _one(connection.execute(text(
                    "SELECT audit_id,business_id,admin_user_id,decision,previous_status,new_status FROM business_approval_audits"
                )).mappings(), "approval audit"),
                "notification": _one(connection.execute(text(
                    "SELECT notification_id,recipient_user_id,business_id,notification_type,related_entity_type,related_entity_id FROM notifications"
                )).mappings(), "approval notification"),
                "link": _one(connection.execute(text(
                    "SELECT business_id,public_code FROM business_join_links"
                )).mappings(), "join link"),
                "request": _one(connection.execute(text(
                    "SELECT request_id,business_id,customer_user_id,status,decided_by,decided_at FROM customer_join_requests"
                )).mappings(), "join request"),
                "profiles": list(connection.execute(text(
                    "SELECT customer_id,business_id,user_id FROM customer_profiles ORDER BY customer_id"
                )).mappings()),
            }
            ids = validate_reconciled_rows(rows)
            return {
                "status": "PASS", "mode": "membership_authoritative",
                "database": TARGET, "account": ACCOUNT, "revision": REVISION,
                "run_id": manifest["run_id"],
                "historical_snapshots": "not captured; not fabricated",
                "business_identity": discrepancy,
                "record_ids": ids,
                "relationships": {
                    "owner_identity": "verified from immutable derived email",
                    "business_identity_source": "exact active Owner membership foreign key",
                    "owner_membership": "verified", "admin_business_approval": "verified",
                    "owner_approval_notification": "verified", "permanent_join_link": "verified",
                    "approved_customer_join": "verified", "linked_customer_profile": "verified",
                    "unlinked_profile": "same fixture business; user_id is null; no account identity asserted",
                    "unlinked_profile_dependents": "zero",
                },
                "join_code_sha256": hashlib.sha256(rows["link"]["public_code"].encode()).hexdigest(),
                "financial_records": 0, "orders": 0, "deliveries": 0,
                "unrelated_application_records": 0,
                "financial_and_fulfilment_zero_state": True,
                "actual_business_values_exposed": False,
                "database_changed": False, "evidence_file_created": False,
            }
        finally:
            connection.rollback()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "reserve", "collect", "cleanup-review", "reconcile-final", "diagnose-final", "diagnose-business", "reconcile-final-by-membership", "final-evidence-preflight", "preserve-final-evidence"))
    parser.add_argument("--run-id")
    parser.add_argument("--stage", choices=STAGES[1:])
    parser.add_argument("--output")
    args = parser.parse_args()

    validate_admin_manifest(read_json(ADMIN_MANIFEST))
    if args.mode == "preflight":
        placeholder = {"run_id": "0" * 32, "identities": identities("0" * 32)}
        live_snapshot({**placeholder}, "reserved")
        print("PASS: exact empty fixture baseline and protected Admin evidence; no fixture files created")
        return
    if not args.run_id or RUN_ID.fullmatch(args.run_id) is None:
        raise ValueError("exact run identifier required")
    manifest_path = expected_path("manifest", args.run_id)
    if args.mode == "reserve":
        require_exact_path(Path(args.output), "manifest", args.run_id)
        value = {"version": 1, "state": "reserved", "database": TARGET, "account": ACCOUNT,
                 "revision": REVISION, "admin_user_id": ADMIN_ID, "run_id": args.run_id,
                 "created_utc": datetime.now(timezone.utc).isoformat(), "identities": identities(args.run_id),
                 "credential_files": {"owner": expected_path("owner_credential", args.run_id).name,
                                      "customer": expected_path("customer_credential", args.run_id).name}}
        live_snapshot(value, "reserved")
        write_reserved_json(Path(args.output), value)
        print(f"PASS: private QR browser fixture reserved; run_id={args.run_id}; no database records created")
        return
    manifest = read_json(manifest_path); validate_manifest(manifest, args.run_id)
    if args.mode in {"final-evidence-preflight", "preserve-final-evidence"}:
        report = reconcile_final_by_membership(manifest)
        validate_pinned_final_report(report, args.run_id)
        if args.mode == "final-evidence-preflight":
            print("PASS: fresh pinned membership reconciliation; final evidence preflight only")
            return
        if not args.output:
            raise ValueError("reserved final evidence output required")
        output = Path(args.output)
        require_exact_path(output, "final_evidence", args.run_id)
        evidence = build_final_evidence(
            report,
            manifest_path.read_bytes(),
            datetime.now(timezone.utc).isoformat(),
        )
        write_reserved_json(output, evidence)
        validate_final_evidence(read_json(output))
        print("PASS: immutable private final QR evidence written and integrity-verified")
        return
    if args.mode == "diagnose-business":
        print(json.dumps(diagnose_business_lookup(manifest), sort_keys=True))
        return
    if args.mode == "reconcile-final-by-membership":
        print(json.dumps(reconcile_final_by_membership(manifest), sort_keys=True))
        return
    if args.mode in {"reconcile-final", "diagnose-final"}:
        try:
            result = reconcile_final_state(manifest)
        except Exception as error:
            if args.mode == "diagnose-final":
                raise SystemExit(f"STOP: final-state diagnostic category={diagnostic_code(error)}") from None
            raise
        print(json.dumps(result, sort_keys=True))
        return
    if args.mode == "collect":
        if not args.stage or not args.output:
            raise ValueError("stage and reserved output required")
        require_exact_path(Path(args.output), "evidence", args.run_id, args.stage)
        verify_previous_evidence(args.run_id, manifest, args.stage)
        value = live_snapshot(manifest, args.stage)
        write_reserved_json(Path(args.output), value)
        print(f"PASS: exact fixture evidence captured for stage {args.stage}; database unchanged")
        return
    final = read_json(expected_path("evidence", args.run_id, "join_approved"))
    validate_cleanup(final, manifest)
    current = live_snapshot(manifest, "join_approved")
    if current["record_ids"] != final["record_ids"] or current["table_counts"] != final["table_counts"]:
        raise ValueError("current fixture state differs from final evidence")
    print("PASS: exact-ID cleanup review passed; protected Admin excluded; no cleanup executed")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("STOP: QR browser fixture ownership or evidence check failed") from None
