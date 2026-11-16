"""Database-free checks for exact QR test Admin reconciliation."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).with_name("reconcile_qr_test_admin.py")
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("reconcile_qr_test_admin", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.old = {"state": "reserved", "database": "lankapex_test_db",
                    "account": "lankapex_qr_test_runtime@localhost",
                    "email": "qr-browser-admin-" + "a" * 32 + "@lankapex-test.example.com",
                    "run_id": "a" * 32, "user_id": None, "audit_id": None}
        self.current = {**self.old, "state": "pending_commit", "user_id": 124671,
                        "audit_id": 42,
                        "email": "qr-browser-admin-" + "b" * 32 + "@lankapex-test.example.com",
                        "run_id": "b" * 32}
        self.user = SimpleNamespace(user_id=124671, email=self.current["email"],
                                    platform_role="admin", account_status="active",
                                    password_hash="synthetic-hash")
        self.audit = SimpleNamespace(audit_id=42, admin_user_id=124671,
                                     target_type="user", target_id=124671,
                                     action="admin_provisioned", new_state="active")
        self.counts = {f"table_{i}": 0 for i in range(26)}
        self.counts.update(users=1, admin_audits=1)

    def test_matching_evidence_and_credential(self):
        module.validate_evidence(self.old, self.current)
        module.validate_rows(self.user, self.audit, self.counts,
                             self.current, "private-synthetic", lambda plain, hashed: plain == "private-synthetic")

    def test_manifest_mismatch_or_uncommitted_state_stops(self):
        for change in ({"state": "reserved"}, {"database": "lankapex_db"},
                       {"user_id": 2}, {"audit_id": None},
                       {"email": self.old["email"]}, {"run_id": self.old["run_id"]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.validate_evidence(self.old, {**self.current, **change})

    def test_role_audit_dependent_rows_and_password_mismatch_stop(self):
        cases = [({**vars(self.user), "platform_role": "customer"}, self.audit, self.counts, True),
                 (vars(self.user), SimpleNamespace(**{**vars(self.audit), "audit_id": 99}), self.counts, True),
                 (vars(self.user), self.audit, {**self.counts, "credit_accounts": 1}, True),
                 (vars(self.user), self.audit, self.counts, False)]
        for fields, audit, counts, matches in cases:
            with self.assertRaises(ValueError):
                module.validate_rows(SimpleNamespace(**fields), audit, counts, self.current,
                                     "private-synthetic", lambda plain, hashed: matches)

    def test_wrapper_is_read_only_and_test_scoped(self):
        wrapper = SCRIPT.with_suffix(".ps1").read_text(encoding="utf-8")
        self.assertIn("qr-test-runtime.dpapi", wrapper)
        self.assertIn("qr-browser-admin-recovery-password.dpapi", wrapper)
        self.assertIn("check_qr_test_runtime.py", wrapper)
        self.assertIn("lankapex_test_db", wrapper)
        self.assertNotIn("--execute", wrapper)
        self.assertNotIn("Set-Content", wrapper)
        self.assertNotIn("WriteAllText", wrapper)


if __name__ == "__main__":
    unittest.main()
