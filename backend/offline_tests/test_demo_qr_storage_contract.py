"""Source-only consistency and fingerprint checks; no private metadata accessed."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/scripts"))
import demo_qr_migration_guard as guard


class StorageContractTests(unittest.TestCase):
    def test_shared_consumers(self):
        for name in ("provision_demo_qr_migrator.ps1", "upgrade_populated_demo_qr.ps1",
                     "check_demo_qr_private_path.ps1"):
            source = (ROOT / "backend/scripts" / name).read_text(encoding="utf-8")
            self.assertIn("demo_qr_credential_storage.ps1", source)
            self.assertIn("Assert-DemoQrCredentialStorage", source)
            self.assertNotIn("private-demo\\demo-qr-migrator.dpapi", source)
            self.assertIn("Close-DemoQrStorageLease", source)

    def test_source_fingerprint_covers_helper_and_wrapper(self):
        hashes = guard.source_hashes()
        for name in ("demo_qr_credential_storage.ps1", "upgrade_populated_demo_qr.ps1",
                     "check_demo_qr_private_path.ps1"):
            self.assertEqual(len(hashes["backend/scripts/" + name]), 64)

    def test_runtime_launcher_unchanged_contract(self):
        source = (ROOT / "backend/scripts/start_demo_backend.ps1").read_text(encoding="utf-8")
        self.assertIn("private-demo\\demo-app.dpapi", source)
        self.assertIn("private-demo\\demo-jwt.dpapi", source)
        self.assertNotIn("demo_qr_credential_storage", source)

    def test_native_open_is_readonly_and_pins_ancestors(self):
        source = (ROOT / "backend/scripts/demo_qr_credential_storage.ps1").read_text(encoding="utf-8")
        self.assertIn("CreateFileW($Path,0x20080,3", source)
        self.assertIn("GetFinalPathNameByHandleW", source)
        self.assertIn("$handles.Add($node.Handle)", source)
        self.assertIn("$handle.Dispose()", source)
        self.assertNotIn("Set-Acl", source)
        self.assertNotIn("New-Item", source)
        self.assertNotIn("Get-Content", source)


if __name__ == "__main__":
    unittest.main()
