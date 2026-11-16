"""Database-free fail-closed tests for the manifest-only finalizer."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("finalize_qr_test_admin_manifest.py")
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("finalize_qr_test_admin_manifest", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class FinalizationTests(unittest.TestCase):
    def setUp(self):
        self.pending = {"state": "pending_commit", "database": "lankapex_test_db",
                        "account": "lankapex_qr_test_runtime@localhost",
                        "email": "qr-browser-admin-" + "b" * 32 + "@lankapex-test.example.com",
                        "run_id": "b" * 32, "user_id": 124671, "audit_id": 42}

    def test_exact_confirmation_and_default_mode(self):
        module.validate_flags(False, None, None, False)
        module.validate_flags(True, "lankapex_test_db", 124671, True)
        for args in ((True, "lankapex_db", 124671, True),
                     (True, "lankapex_test_db", 1, True),
                     (True, "lankapex_test_db", 124671, False),
                     (False, "lankapex_test_db", None, False)):
            with self.assertRaises(ValueError):
                module.validate_flags(*args)

    def test_invalid_pending_state_id_and_target_stop(self):
        module.validate_pending(self.pending)
        for change in ({"state": "committed"}, {"database": "lankapex_demo_db"},
                       {"user_id": 1}, {"audit_id": None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.validate_pending({**self.pending, **change})

    def test_only_state_changes_and_original_bytes_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, backup, temp = (root / name for name in ("manifest.json", "backup.json", "temp.tmp"))
            raw = json.dumps(self.pending, sort_keys=True).encode("utf-8")
            manifest.write_bytes(raw)
            backup.write_bytes(b"")
            temp.write_bytes(b"")
            module.finalize_files(manifest, backup, temp)
            self.assertEqual(backup.read_bytes(), raw)
            committed = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(committed, {**self.pending, "state": "committed"})
            self.assertFalse(temp.exists())
            with self.assertRaises(ValueError):
                module.finalize_files(manifest, backup, temp)

    def test_atomic_replace_failure_keeps_pending_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, backup, temp = (root / name for name in ("manifest.json", "backup.json", "temp.tmp"))
            raw = json.dumps(self.pending).encode("utf-8")
            manifest.write_bytes(raw)
            backup.write_bytes(b"")
            temp.write_bytes(b"")
            with self.assertRaises(OSError):
                module.finalize_files(manifest, backup, temp,
                                      replace=lambda source, target: (_ for _ in ()).throw(OSError("synthetic")))
            self.assertEqual(manifest.read_bytes(), raw)
            self.assertEqual(backup.read_bytes(), raw)
            self.assertTrue(temp.exists())

    def test_failed_reconciliation_precedes_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(self.pending), encoding="utf-8")
            with patch.object(module, "MANIFEST", manifest), \
                 patch.object(module, "BACKUP", root / "backup.json"), \
                 patch.object(module, "TEMP", root / "temp.tmp"), \
                 patch.object(module.reconcile, "main", side_effect=ValueError("synthetic")):
                with self.assertRaises(ValueError):
                    module.main([])
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8")), self.pending)
            self.assertFalse((root / "backup.json").exists())

    def test_wrapper_has_exact_preflight_and_no_database_write(self):
        wrapper = SCRIPT.with_suffix(".ps1").read_text(encoding="utf-8")
        self.assertIn("check_qr_test_runtime.py", wrapper)
        self.assertIn("--confirm-admin-id 124671", wrapper)
        self.assertIn("[IO.FileMode]::CreateNew", wrapper)
        self.assertLess(wrapper.index("finalize_qr_test_admin_manifest.py"), wrapper.index("[IO.FileMode]::CreateNew"))
        self.assertNotIn("--execute-migration", wrapper)


if __name__ == "__main__":
    unittest.main()
