"""Database-free fail-closed checks for the QR browser Admin bootstrap."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("bootstrap_qr_test_admin.py")
SPEC = importlib.util.spec_from_file_location("qr_admin_bootstrap", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class BootstrapGuardTests(unittest.TestCase):
    def test_execution_requires_exact_target_and_pause(self):
        for target, pause in ((None, True), ("lankapex_db", True),
                              ("lankapex_demo_db", True), (module.TARGET, False)):
            with self.subTest(target=target, pause=pause), self.assertRaises(ValueError):
                module.validate_execution(True, target, pause)
        module.validate_execution(True, module.TARGET, True)
        module.validate_execution(False, None, False)
        with self.assertRaises(ValueError):
            module.validate_execution(False, module.TARGET, False)

    def test_any_existing_record_or_wrong_inventory_stops(self):
        empty = {f"table_{i}": 0 for i in range(28)}
        module.require_empty(empty)
        for changed in ({**empty, "users": 1}, {**empty, "admin_audits": 1},
                        {**empty, "credit_accounts": 1}, {"users": 0}):
            with self.assertRaises(ValueError):
                module.require_empty(changed)

    def test_manifest_binding_and_duplicate_execution(self):
        data = {"state": "reserved", "database": module.TARGET,
                "email": "qr-browser-admin-x@lankapex-test.example.com", "run_id": "a" * 32,
                "user_id": None, "audit_id": None}
        module.validate_manifest(data, data["email"], data["run_id"])
        for changed in ({**data, "database": "lankapex_demo_db"},
                        {**data, "state": "committed"},
                        {**data, "user_id": 1}, {**data, "audit_id": 1}, {}):
            with self.assertRaises(ValueError):
                module.validate_manifest(changed, data["email"], data["run_id"])

    def test_private_manifest_write_keeps_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_text('{"state":"reserved"}', encoding="utf-8")
            with patch.object(module, "MANIFEST", path):
                module.write_manifest({"state": "pending_commit"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),
                             {"state": "pending_commit"})

    def test_manifest_reader_accepts_bom_and_plain_utf8(self):
        reservation = {"state": "reserved", "database": module.TARGET,
                       "email": "qr-browser-admin-x@lankapex-test.example.com",
                       "run_id": "a" * 32, "user_id": None, "audit_id": None}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            for encoding in ("utf-8", "utf-8-sig"):
                with self.subTest(encoding=encoding):
                    path.write_text(json.dumps(reservation), encoding=encoding)
                    loaded = module.read_manifest(path)
                    module.validate_manifest(loaded, reservation["email"], reservation["run_id"])
                    self.assertEqual(loaded, reservation)

    def test_bom_does_not_relax_manifest_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_text(json.dumps({"state": "reserved", "database": "lankapex_db"}),
                            encoding="utf-8-sig")
            with self.assertRaises(ValueError):
                module.validate_manifest(module.read_manifest(path), "x", "y")

    def test_wrapper_is_exact_target_and_preflight_first(self):
        wrapper = SCRIPT.with_suffix(".ps1").read_text(encoding="utf-8")
        self.assertIn("qr-test-runtime.dpapi", wrapper)
        self.assertIn("check_qr_test_runtime.py", wrapper)
        self.assertIn("qr-browser-admin-password.dpapi", wrapper)
        self.assertIn("[IO.FileMode]::CreateNew", wrapper)
        self.assertIn("$ConfirmWriterPause", wrapper)
        self.assertIn("New-Object System.Text.UTF8Encoding($false)", wrapper)
        self.assertNotIn("[Text.Encoding]::UTF8)", wrapper)
        self.assertNotIn("qr-test-migrator.dpapi", wrapper)
        self.assertNotIn("DROP DATABASE", wrapper.upper())


if __name__ == "__main__":
    unittest.main()
