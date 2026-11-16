"""Static, database-free checks for the guarded browser JWT creator."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "backend/scripts/create_tamil_ai_browser_jwt.ps1").read_text()


def test_exact_private_target_and_context_are_pinned():
    assert "tamil-ai-browser-jwt.dpapi" in SCRIPT
    assert "lankapex_ai_snapshot_test_db" in SCRIPT
    assert "14405b71b0504036a35ff55c7a9da132" in SCRIPT


def test_default_is_inspection_only_and_execution_is_explicit():
    assert "[switch]$Execute" in SCRIPT and "[switch]$ConfirmJwtCreation" in SCRIPT
    assert "if(-not $Execute)" in SCRIPT
    assert "confirmations require -Execute" in SCRIPT
    inspection = SCRIPT[SCRIPT.index("if(-not $Execute)"):SCRIPT.index("if(Test-Path -LiteralPath $target)")]
    assert "CreateNew" not in inspection and "Set-TamilAiPrivateFileDaclOnly" not in inspection


def test_cryptographic_generation_dpapi_and_exclusive_creation():
    assert "RandomNumberGenerator]::Create()" in SCRIPT
    assert "New-Object byte[] 48" in SCRIPT
    assert "ConvertFrom-SecureString" in SCRIPT and "ConvertTo-SecureString" in SCRIPT
    assert "[IO.FileMode]::CreateNew" in SCRIPT and "refusing overwrite" in SCRIPT


def test_dacl_only_protection_and_post_write_validation():
    assert ". $helper" in SCRIPT
    assert "Set-TamilAiPrivateFileDaclOnly $target $operatorSid" in SCRIPT
    assert SCRIPT.count("Assert-TamilAiPrivateFileAcl $target $operatorSid") >= 2
    assert "Set-Acl" not in SCRIPT and "FileSecurity" not in SCRIPT


def test_secret_material_is_not_printed_and_is_cleared():
    output_lines = [line for line in SCRIPT.splitlines() if "Write-Output" in line]
    assert all(token not in line for line in output_lines for token in ("$plain", "$cipher", "$bytes", "$checkPointer"))
    assert "ZeroFreeBSTR" in SCRIPT and "[Array]::Clear" in SCRIPT
    assert "$plain=$null;$cipher=$null" in SCRIPT


def test_failure_is_sanitized_and_preserves_partial_file():
    assert "preserve any created file and do not retry automatically" in SCRIPT
    assert "Remove-Item" not in SCRIPT and "File]::Delete" not in SCRIPT and "File.Delete" not in SCRIPT
    assert "exit 1" in SCRIPT


def test_no_database_external_ai_or_persistent_configuration_access():
    lowered = SCRIPT.lower()
    for forbidden in ("mysql", "groq", "http://", "https://", "backend/.env", "backend\\.env"):
        assert forbidden not in lowered
