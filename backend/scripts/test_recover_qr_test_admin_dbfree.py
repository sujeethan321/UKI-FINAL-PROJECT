"""Database-free safety checks for the one-time QR test Admin recovery."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("recover_qr_test_admin.py")
SPEC = importlib.util.spec_from_file_location("recover_qr_test_admin", SCRIPT)
import sys
sys.path.insert(0, str(SCRIPT.parent))
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.old = {"state": "reserved", "database": "lankapex_test_db",
                    "account": "lankapex_qr_test_runtime@localhost",
                    "email": "qr-browser-admin-" + "a" * 32 + "@lankapex-test.example.com",
                    "run_id": "a" * 32, "user_id": None, "audit_id": None}

    def test_old_evidence_rejects_wrong_state_target_and_existing_ids(self):
        recovery.validate_old_evidence(self.old, True)
        for change in ({"state": "committed"}, {"database": "lankapex_demo_db"},
                       {"account": "lankapex_app@localhost"}, {"user_id": 1},
                       {"audit_id": 1}, {"run_id": None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                recovery.validate_old_evidence({**self.old, **change}, True)
        with self.assertRaises(ValueError):
            recovery.validate_old_evidence({**self.old, "other_fixture_id": 2}, True)

    def test_missing_failed_credential_stops(self):
        with self.assertRaises(ValueError):
            recovery.validate_old_evidence(self.old, False)

    def test_new_attempt_must_not_reuse_old_identity(self):
        with self.assertRaises(ValueError):
            recovery.validate_new_attempt(self.old, self.old, True)
        newer = {**self.old, "email": "qr-browser-admin-" + "b" * 32 + "@lankapex-test.example.com",
                 "run_id": "b" * 32}
        recovery.validate_new_attempt(newer, self.old, True)
        with self.assertRaises(ValueError):
            recovery.validate_new_attempt({**newer, "run_id": self.old["run_id"]}, self.old, True)

    def test_zero_row_and_exact_execution_gates_remain(self):
        recovery.bootstrap.require_empty({f"table_{i}": 0 for i in range(28)})
        with self.assertRaises(ValueError):
            recovery.bootstrap.require_empty({**{f"table_{i}": 0 for i in range(28)}, "users": 1})
        for target, pause in (("lankapex_db", True), ("lankapex_test_db", False)):
            with self.assertRaises(ValueError):
                recovery.bootstrap.validate_execution(True, target, pause)

    def test_duplicate_recovery_and_failed_preparation_stop_before_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_manifest = root / "old.json"
            old_password = root / "old.dpapi"
            new_manifest = root / "new.json"
            new_password = root / "new.dpapi"
            old_manifest.write_text(json.dumps(self.old), encoding="utf-8-sig")
            old_password.write_bytes(b"synthetic-cipher")
            patches = [patch.object(recovery, key, value) for key, value in
                       (("OLD_MANIFEST", old_manifest), ("OLD_PASSWORD", old_password),
                        ("NEW_MANIFEST", new_manifest), ("NEW_PASSWORD", new_password))]
            for item in patches: item.start()
            try:
                with patch.object(recovery.bootstrap, "main") as bootstrap_main:
                    recovery.main([])
                    bootstrap_main.assert_called_once()
                    new_manifest.write_text("{}", encoding="utf-8")
                    with self.assertRaises(ValueError):
                        recovery.main([])
                    bootstrap_main.assert_called_once()
                new_manifest.unlink()
                old_password.unlink()
                with self.assertRaises(ValueError):
                    recovery.main([])
            finally:
                for item in reversed(patches): item.stop()

    def test_wrapper_uses_distinct_create_new_paths_and_no_early_file_write(self):
        wrapper = SCRIPT.with_suffix(".ps1").read_text(encoding="utf-8")
        self.assertIn("qr-browser-admin-recovery-password.dpapi", wrapper)
        self.assertIn("qr-browser-admin-recovery-fixture.json", wrapper)
        self.assertIn("qr-browser-admin-password.dpapi", wrapper)
        self.assertIn("[IO.FileMode]::CreateNew", wrapper)
        self.assertLess(wrapper.index("check_qr_test_runtime.py"), wrapper.index("[IO.FileMode]::CreateNew"))
        self.assertLess(wrapper.index("recover_qr_test_admin.py"), wrapper.index("[IO.FileMode]::CreateNew"))
        self.assertIn("$ConfirmWriterPause", wrapper)
        self.assertIn("New-Object System.Text.UTF8Encoding($false)", wrapper)


if __name__ == "__main__":
    unittest.main()
