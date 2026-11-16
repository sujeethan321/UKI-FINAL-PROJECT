import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import qr_browser_fixture_tracking as fixture  # noqa: E402
from check_qr_test_runtime import validate_identity  # noqa: E402


RUN = "a" * 32


def manifest():
    return {
        "version": 1, "state": "reserved", "database": fixture.TARGET,
        "account": fixture.ACCOUNT, "revision": fixture.REVISION,
        "admin_user_id": fixture.ADMIN_ID, "run_id": RUN,
        "created_utc": "2026-11-14T00:00:00+00:00",
        "identities": fixture.identities(RUN),
        "credential_files": {
            "owner": fixture.expected_path("owner_credential", RUN).name,
            "customer": fixture.expected_path("customer_credential", RUN).name,
        },
    }


def reconciled_rows():
    return {
        "admin": {"user_id": fixture.ADMIN_ID, "platform_role": "admin", "account_status": "active"},
        "admin_audit": {"audit_id": 9, "admin_user_id": fixture.ADMIN_ID,
                        "target_id": fixture.ADMIN_ID, "action": "admin_provisioned"},
        "owner": {"user_id": 201, "platform_role": "shop_owner", "account_status": "active"},
        "customer": {"user_id": 202, "platform_role": "customer", "account_status": "active"},
        "business": {"business_id": 301, "approval_status": "approved"},
        "membership": {"membership_id": 401, "business_id": 301, "user_id": 201,
                       "business_role": "owner", "membership_status": "active"},
        "approval": {"audit_id": 501, "business_id": 301, "admin_user_id": fixture.ADMIN_ID,
                     "decision": "approve", "previous_status": "pending", "new_status": "approved"},
        "notification": {"notification_id": 601, "recipient_user_id": 201, "business_id": 301,
                         "notification_type": "business_approved",
                         "related_entity_type": "business_approval_audit", "related_entity_id": 501},
        "link": {"business_id": 301, "public_code": "A" * 32},
        "request": {"request_id": 701, "business_id": 301, "customer_user_id": 202,
                    "status": "approved", "decided_by": 201, "decided_at": "set"},
        "profiles": [
            {"customer_id": 801, "business_id": 301, "user_id": None},
            {"customer_id": 802, "business_id": 301, "user_id": 202},
        ],
    }


def owner_membership_business():
    return (
        {"user_id": 201, "platform_role": "shop_owner", "account_status": "active"},
        {"membership_id": 401, "user_id": 201, "business_role": "owner",
         "membership_status": "active", "business_id": 301,
         "business_name": fixture.identities(RUN)["business_name"],
         "registration_number": fixture.identities(RUN)["registration_number"],
         "approval_status": "approved"},
    )


def pinned_report():
    return {
        "status": "PASS", "mode": "membership_authoritative",
        "database": fixture.TARGET, "account": fixture.ACCOUNT,
        "revision": fixture.REVISION, "run_id": fixture.PINNED_FINAL_RUN,
        "historical_snapshots": "not captured; not fabricated",
        "business_identity": {
            "business_found_via_exact_owner_membership": True,
            "business_approved": True,
            "business_name_matches_manifest": False,
            "registration_number_matches_manifest": False,
            "both_manifest_identifiers_match": False,
            "identity_discrepancy": True,
        },
        "record_ids": dict(fixture.PINNED_FINAL_IDS),
        "relationships": {
            "unlinked_profile": "same fixture business; user_id is null; no account identity asserted",
            "unlinked_profile_dependents": "zero",
        },
        "join_code_sha256": "c" * 64,
        "financial_records": 0, "orders": 0, "deliveries": 0,
        "unrelated_application_records": 0,
        "financial_and_fulfilment_zero_state": True,
        "database_changed": False, "evidence_file_created": False,
    }


class FixtureTrackingSafetyTests(unittest.TestCase):
    def test_identity_derivation_is_deterministic_and_run_scoped(self):
        one = fixture.identities(RUN)
        two = fixture.identities("b" * 32)
        self.assertNotEqual(one["owner_email"], two["owner_email"])
        self.assertEqual(one["registration_number"], "QR-" + RUN)

    def test_invalid_run_id_is_rejected(self):
        for value in ("", "A" * 32, "a" * 31, "../" + "a" * 29):
            with self.assertRaises(ValueError):
                fixture.identities(value)

    def test_manifest_accepts_only_exact_identity(self):
        fixture.validate_manifest(manifest(), RUN)
        changed = manifest(); changed["database"] = "lankapex_demo_db"
        with self.assertRaises(ValueError):
            fixture.validate_manifest(changed, RUN)

    def test_wrong_database_revision_or_account_fails_runtime_gate(self):
        valid = dict(configured_env="testing", configured_db=fixture.TARGET,
                     engine_db=fixture.TARGET, engine_user="lankapex_qr_test_runtime",
                     actual_db=fixture.TARGET, actual_user=fixture.ACCOUNT,
                     revision=fixture.REVISION,
                     tables={"alembic_version", "business_join_links", "customer_join_requests", *[f"t{i}" for i in range(26)]},
                     grants=["GRANT USAGE ON *.* TO x", "GRANT SELECT, INSERT, UPDATE, DELETE ON `lankapex\\_test\\_db`.* TO x"])
        validate_identity(**valid)
        for key, bad in (("actual_db", "lankapex_db"), ("revision", "old"),
                         ("actual_user", "other@localhost")):
            changed = {**valid, key: bad}
            with self.assertRaises(ValueError):
                validate_identity(**changed)

    def test_stage_counts_reject_missing_and_unexpected_records(self):
        tables = {"users", "admin_audits", "businesses", "business_members",
                  "business_approval_audits", "notifications", "business_join_links",
                  "customer_join_requests", "customer_profiles", "credit_accounts", "alembic_version"}
        counts = {name: 0 for name in tables if name != "alembic_version"}
        counts.update(users=3, admin_audits=1, businesses=1, business_members=1)
        fixture.validate_counts(counts, "business_created", tables)
        counts["credit_accounts"] = 1
        with self.assertRaises(ValueError):
            fixture.validate_counts(counts, "business_created", tables)

    def test_missing_ownership_evidence_is_rejected(self):
        evidence = {"version": 1, "database": fixture.TARGET, "account": fixture.ACCOUNT,
                    "revision": fixture.REVISION, "run_id": RUN, "stage": "join_approved",
                    "admin_user_id": fixture.ADMIN_ID, "record_ids": {}, "table_counts": {},
                    "financial_zero_state": True}
        fixture.validate_evidence(evidence, manifest(), "join_approved")
        with self.assertRaises(ValueError):
            fixture.validate_cleanup(evidence, manifest())

    def test_admin_id_can_never_enter_cleanup_set(self):
        ids = {"owner_user_id": fixture.ADMIN_ID, "customer_user_id": 2, "business_id": 3,
               "membership_id": 4, "approval_audit_id": 5, "approval_notification_id": 6,
               "join_request_id": 7, "customer_profile_id": 8}
        evidence = {"version": 1, "database": fixture.TARGET, "account": fixture.ACCOUNT,
                    "revision": fixture.REVISION, "run_id": RUN, "stage": "join_approved",
                    "admin_user_id": fixture.ADMIN_ID, "record_ids": ids, "table_counts": {},
                    "financial_zero_state": True}
        with self.assertRaises(ValueError):
            fixture.validate_cleanup(evidence, manifest())

    def test_output_path_cannot_escape_private_directory(self):
        with self.assertRaises(ValueError):
            fixture.require_exact_path(Path(tempfile.gettempdir()) / "evidence.json", "manifest", RUN)

    def test_reserved_writer_refuses_nonempty_or_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "reserved.json"
            with self.assertRaises(ValueError):
                fixture.write_reserved_json(path, {"x": 1})
            path.write_text("existing", encoding="utf-8")
            with self.assertRaises(ValueError):
                fixture.write_reserved_json(path, {"x": 1})

    def test_bom_admin_manifest_is_strictly_validated(self):
        value = {"state": "committed", "database": fixture.TARGET, "account": fixture.ACCOUNT,
                 "user_id": fixture.ADMIN_ID, "audit_id": 10}
        fixture.validate_admin_manifest(value)
        value["user_id"] = 999
        with self.assertRaises(ValueError):
            fixture.validate_admin_manifest(value)

    def test_program_contains_no_database_write_statements(self):
        source = Path(fixture.__file__).read_text(encoding="utf-8").upper()
        for forbidden in ("INSERT INTO", "UPDATE USERS", "DELETE FROM", "TRUNCATE ", "DROP TABLE", "ALTER TABLE"):
            self.assertNotIn(forbidden, source)
        self.assertIn("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY", source)

    def test_final_reconciliation_accepts_exact_linked_and_unlinked_pair(self):
        ids = fixture.validate_reconciled_rows(reconciled_rows())
        self.assertEqual(ids["linked_customer_profile_id"], 802)
        self.assertEqual(ids["unlinked_business_profile_id"], 801)

    def test_final_reconciliation_rejects_two_linked_profiles(self):
        rows = reconciled_rows()
        rows["profiles"][0]["user_id"] = 202
        with self.assertRaises(ValueError):
            fixture.validate_reconciled_rows(rows)

    def test_final_reconciliation_rejects_unlinked_profile_from_other_business(self):
        rows = reconciled_rows()
        rows["profiles"][0]["business_id"] = 999
        with self.assertRaises(ValueError):
            fixture.validate_reconciled_rows(rows)

    def test_final_reconciliation_rejects_wrong_owner_decision(self):
        rows = reconciled_rows()
        rows["request"]["decided_by"] = fixture.ADMIN_ID
        with self.assertRaises(ValueError):
            fixture.validate_reconciled_rows(rows)

    def test_reconciled_counts_reject_financial_activity(self):
        tables = {"users", "admin_audits", "businesses", "business_members",
                  "business_approval_audits", "notifications", "business_join_links",
                  "customer_join_requests", "customer_profiles", "credit_accounts"}
        counts = {name: 0 for name in tables}
        counts.update(users=3, admin_audits=1, businesses=1, business_members=1,
                      business_approval_audits=1, notifications=1, business_join_links=1,
                      customer_join_requests=1, customer_profiles=2)
        fixture.validate_reconciled_counts(counts, tables)
        counts["credit_accounts"] = 1
        with self.assertRaises(ValueError):
            fixture.validate_reconciled_counts(counts, tables)

    def test_diagnostic_categories_are_sanitized_and_specific(self):
        cases = {
            "fixture business identity differs": "business_manifest_identity",
            "owner membership relationship differs": "owner_membership",
            "linked/unlinked customer profile pair differs": "customer_profile_pair",
            "business ownership is missing or ambiguous": "business_lookup",
        }
        for message, expected in cases.items():
            self.assertEqual(fixture.diagnostic_code(ValueError(message)), expected)

    def test_unknown_diagnostic_never_echoes_exception_text(self):
        secret = "unreviewed row value sensitive@example.test"
        result = fixture.diagnostic_code(RuntimeError(secret))
        self.assertEqual(result, "unclassified_read_only_failure")
        self.assertNotIn(secret, result)

    def test_diagnostic_runtime_gate_is_generic(self):
        self.assertEqual(
            fixture.diagnostic_code(ValueError("grant includes another or wildcard database")),
            "runtime_safety_gate",
        )

    def test_owner_membership_business_lookup_accepts_exact_manifest_identity(self):
        owner, business = owner_membership_business()
        result = fixture.validate_business_membership_lookup(owner, business, manifest())
        self.assertTrue(result["both_manifest_identifiers_match"])
        self.assertFalse(result["identity_discrepancy"])

    def test_owner_membership_business_lookup_reports_both_mismatches_without_values(self):
        owner, business = owner_membership_business()
        business["business_name"] = "different"
        business["registration_number"] = None
        result = fixture.validate_business_membership_lookup(owner, business, manifest())
        self.assertFalse(result["business_name_matches_manifest"])
        self.assertFalse(result["registration_number_matches_manifest"])
        self.assertTrue(result["identity_discrepancy"])
        self.assertNotIn("different", json.dumps(result))

    def test_owner_membership_business_lookup_rejects_wrong_owner(self):
        owner, business = owner_membership_business()
        business["user_id"] = 999
        with self.assertRaises(ValueError):
            fixture.validate_business_membership_lookup(owner, business, manifest())

    def test_owner_membership_business_lookup_rejects_unapproved_business(self):
        owner, business = owner_membership_business()
        business["approval_status"] = "pending"
        with self.assertRaises(ValueError):
            fixture.validate_business_membership_lookup(owner, business, manifest())

    def test_membership_reconciliation_rejects_duplicate_business_inventory(self):
        tables = {"users", "admin_audits", "businesses", "business_members",
                  "business_approval_audits", "notifications", "business_join_links",
                  "customer_join_requests", "customer_profiles"}
        counts = {name: 0 for name in tables}
        counts.update(users=3, admin_audits=1, businesses=2, business_members=1,
                      business_approval_audits=1, notifications=1, business_join_links=1,
                      customer_join_requests=1, customer_profiles=2)
        with self.assertRaises(ValueError):
            fixture.validate_reconciled_counts(counts, tables)

    def test_membership_reconciliation_rejects_wrong_business_approver(self):
        rows = reconciled_rows()
        rows["approval"]["admin_user_id"] = 999
        with self.assertRaises(ValueError):
            fixture.validate_reconciled_rows(rows)

    def test_membership_reconciliation_rejects_wrong_join_customer(self):
        rows = reconciled_rows()
        rows["request"]["customer_user_id"] = 999
        with self.assertRaises(ValueError):
            fixture.validate_reconciled_rows(rows)

    def test_membership_reconciliation_rejects_ambiguous_unlinked_profiles(self):
        rows = reconciled_rows()
        rows["profiles"] = [
            {"customer_id": 801, "business_id": 301, "user_id": None},
            {"customer_id": 802, "business_id": 301, "user_id": None},
        ]
        with self.assertRaises(ValueError):
            fixture.validate_reconciled_rows(rows)

    def test_final_evidence_accepts_exact_pinned_report_and_integrity_hash(self):
        evidence = fixture.build_final_evidence(
            pinned_report(), b'{"immutable":"reservation"}', "2026-11-14T00:00:00+00:00"
        )
        fixture.validate_final_evidence(evidence)
        self.assertRegex(evidence["evidence_payload_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(evidence["reservation_manifest_sha256"], r"^[0-9a-f]{64}$")

    def test_final_evidence_rejects_wrong_verified_id(self):
        report = pinned_report()
        report["record_ids"]["business_id"] = 999
        with self.assertRaises(ValueError):
            fixture.build_final_evidence(report, b"reservation", "2026-11-14T00:00:00+00:00")

    def test_final_evidence_rejects_business_discrepancy_change(self):
        report = pinned_report()
        report["business_identity"]["business_name_matches_manifest"] = True
        with self.assertRaises(ValueError):
            fixture.validate_pinned_final_report(report, fixture.PINNED_FINAL_RUN)

    def test_final_evidence_detects_tampering(self):
        evidence = fixture.build_final_evidence(
            pinned_report(), b"reservation", "2026-11-14T00:00:00+00:00"
        )
        evidence["captured_utc"] = "changed"
        with self.assertRaises(ValueError):
            fixture.validate_final_evidence(evidence)

    def test_final_evidence_contains_no_raw_fixture_identity_or_secret(self):
        evidence = fixture.build_final_evidence(
            pinned_report(), b"reservation", "2026-11-14T00:00:00+00:00"
        )
        serialized = json.dumps(evidence)
        self.assertNotIn("@lankapex-test.example.com", serialized)
        self.assertNotIn("QR Browser Shop", serialized)
        self.assertNotIn("QR-" + fixture.PINNED_FINAL_RUN, serialized)


if __name__ == "__main__":
    unittest.main()
