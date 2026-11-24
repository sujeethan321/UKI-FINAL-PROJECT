"""Source-only checks; no native, private filesystem, registry or DB access."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DirectoryCreationContractTests(unittest.TestCase):
    def source(self, name):
        return (ROOT / "backend/scripts" / name).read_text(encoding="utf-8")

    def test_default_offline_and_execution_confirmation(self):
        source = self.source("prepare_demo_qr_credential_directory.ps1")
        self.assertLess(source.index("if (-not $PreflightOnly"), source.index("demo_qr_credential_storage.ps1"))
        self.assertIn("$PreflightOnly -and $Execute", source)
        self.assertIn("-not $ConfirmDirectoryCreation", source)
        self.assertIn("ConfirmMissingComponents", source)

    def test_atomic_native_creation_descriptor(self):
        source = self.source("demo_qr_storage_directory_creation.ps1")
        self.assertIn("CreateDirectoryW($Path,[ref]$attributes)", source)
        self.assertIn("$security.SetAccessRuleProtection($true,$false)", source)
        self.assertIn("$security.SetOwner($owner)", source)
        self.assertIn("$attributes.Descriptor=$pointer", source)
        self.assertIn("$code -eq 183", source)
        for forbidden in ("Set-Acl", "Remove-Item", "Directory]::CreateDirectory", "New-Item", "ConvertTo-SecureString", "Get-Content"):
            self.assertNotIn(forbidden, source)

    def test_revalidation_before_create_and_full_postcheck(self):
        source = self.source("demo_qr_storage_directory_creation.ps1")
        self.assertLess(source.index("$fresh=& $PlanProvider"), source.index("& $Creator"))
        self.assertIn("Test-DemoQrStorageNode $node $plan.OperatorSid -Private", source)
        self.assertIn("$State.Stage='complete_path_verification'", source)
        self.assertIn("Assert-DemoQrCredentialStorage -Mode Create", source)
        self.assertIn("Close-DemoQrStorageLease $lease", source)

    def test_shared_validator_defaults_preserved(self):
        source = self.source("demo_qr_credential_storage.ps1")
        self.assertIn("'DirectoryPlan'", source)
        self.assertIn("$Mode='Prepare'", source)
        self.assertIn("if ($missing) { throw 'storage_preparation_required' }", source)
        self.assertIn("if (-not $missing) { throw 'storage_directory_exists' }", source)


if __name__ == "__main__":
    unittest.main()
