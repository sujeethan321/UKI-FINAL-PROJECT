"""PowerShell mocks/in-memory security descriptors only; no real ACL changes."""
import base64
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "backend/scripts/demo_credential_dacl.ps1"
WRAPPER = ROOT / "backend/scripts/repair_demo_credential_dacl.ps1"


def powershell(code):
    encoded = base64.b64encode(code.encode("utf-16le")).decode("ascii")
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
        capture_output=True, text=True, check=False,
    )


class DemoCredentialDaclTests(unittest.TestCase):
    def test_mocked_correction_gates(self):
        code = r"""
$ErrorActionPreference='Stop'
. 'HELPER'
$expected='C:\Users\admin\Desktop\LankaPex\.server-logs\private-demo\demo-app.dpapi'
$directory='C:\Users\admin\Desktop\LankaPex\.server-logs\demo-dacl-backup-11111111111111111111111111111111'
$backupFile=Join-Path $directory 'original-dacl.json'
$operator='S-1-5-21-111-222-333-1001'

function Get-DemoDaclOperator { return $operator }
function Get-Item {
    param($LiteralPath,[switch]$Force,$ErrorAction)
    if ($script:scenario -eq 'missing' -and $LiteralPath -eq $expected) { throw 'synthetic' }
    $attributes=if ($script:scenario -eq 'reparse' -and $LiteralPath -eq $expected) {
        [IO.FileAttributes]::ReparsePoint
    } else { [IO.FileAttributes]::Normal }
    return [pscustomobject]@{Attributes=$attributes}
}
function Test-Path {
    param($LiteralPath,$PathType)
    if ($LiteralPath -eq $expected) { return $true }
    if ($LiteralPath -eq $directory) { return $script:scenario -eq 'existing_directory' }
    if ($LiteralPath -eq $backupFile) { return $script:scenario -eq 'existing_backup' }
    return $true
}
function Rule($sid) {
    return [pscustomobject]@{Sid=$sid;Inherited=$false;Allow=$true;Rights=[Security.AccessControl.FileSystemRights]::FullControl}
}
function Get-DemoDaclMetadata {
    param($Path)
    $owner=$operator; $protected=$true
    $rules=@((Rule $operator),(Rule 'S-1-5-18'))
    $sddl='synthetic-original'
    if ($Path -eq $expected) {
        $protected=$script:mutated
        if ($script:scenario -eq 'already_corrected') { $protected=$true }
        if ($script:scenario -eq 'wrong_owner') { $owner='S-1-5-21-111-222-333-9999' }
        if ($script:mutated) { $sddl='synthetic-corrected' }
        if ($script:scenario -eq 'unexpected_principal' -and $script:mutated) { $rules+=Rule 'S-1-1-0' }
        if ($script:scenario -eq 'owner_changed' -and $script:mutated) { $owner='S-1-5-18' }
        if ($script:scenario -eq 'explicit_unexpected') { $rules+=Rule 'S-1-1-0' }
    }
    if ($Path -eq $directory -and $script:scenario -eq 'unsafe_directory') { $protected=$false }
    if ($Path -eq $backupFile -and $script:scenario -eq 'backup_acl_failed') { $protected=$false }
    if ($Path -eq (Split-Path -Parent $expected) -and $script:scenario -eq 'parent_changed' -and $script:mutated) { $sddl='changed-parent' }
    return [pscustomobject]@{Owner=$owner;Protected=$protected;Rules=$rules;Sddl=$sddl}
}
function NewHandle {
    $h=[pscustomobject]@{}
    $h | Add-Member ScriptMethod Dispose { $script:closed++ }
    return $h
}
function Open-DemoDaclTarget { param($Path) return (NewHandle) }
function Open-DemoDaclBackupDirectory { param($Path) return (NewHandle) }
function Get-DemoDaclIdentity {
    param($Handle)
    if ($script:scenario -eq 'replaced' -and $script:mutated) { return 'changed-file' }
    return 'original-file'
}
function New-DemoDaclBackupDirectory {
    param($Path,$Operator)
    if ($script:scenario -eq 'directory_creation_failed') { throw 'synthetic' }
    $script:directoryCreated=$true
}
function Write-DemoDaclBackup {
    param($Path,$Operator,$Backup)
    if ($script:scenario -eq 'backup_write_failed') { throw 'synthetic' }
    $script:written=$true; $script:saved=$Backup
}
function Read-DemoDaclBackup {
    param($Path)
    if ($script:scenario -eq 'backup_read_failed') { throw 'synthetic' }
    if ($script:scenario -eq 'backup_mismatch') { return [pscustomobject]@{Format=99} }
    $script:readBack=$true
    return $script:saved
}
function Set-DemoDaclOnHandle {
    param($Handle,$Operator,$RestoreSddl)
    if (-not $script:written -or -not $script:readBack) { throw 'mutation-before-backup' }
    $script:mutated=$true
    if ($script:scenario -eq 'correction_failed') { throw 'synthetic' }
}

$cases=@{
    wrong_path='target_path'; wrong_owner='owner'; reparse='target_metadata';
    missing='target_metadata'; unsafe_directory='backup_directory';
    existing_directory='backup_directory'; existing_backup='backup_filename';
    directory_creation_failed='backup_directory'; backup_write_failed='backup_write';
    backup_acl_failed='backup_verification'; backup_read_failed='backup_verification';
    backup_mismatch='backup_verification'; correction_failed='dacl_correction';
    unexpected_principal='post_verification'; owner_changed='post_verification';
    replaced='post_verification'; parent_changed='post_verification';
    explicit_unexpected='existing_dacl'; already_corrected='existing_dacl'; success=''
}
$count=0
foreach ($case in $cases.GetEnumerator()) {
    $script:scenario=$case.Key; $script:mutated=$false; $script:written=$false
    $script:readBack=$false; $script:closed=0; $script:directoryCreated=$false
    $path=if ($case.Key -eq 'wrong_path') { $expected.Replace('LankaPex\.server','LankaPex.server') } else { $expected }
    $result=@(Invoke-DemoCredentialDaclCorrection $path $expected $directory $backupFile)
    $exit=[int]$result[-1]; $message=($result | Select-Object -SkipLast 1) -join ''
    if ($case.Key -eq 'success') {
        if ($exit -ne 0 -or -not $message.StartsWith('PASS:') -or -not $script:mutated -or $script:closed -ne 3) { throw 'success-case' }
    } else {
        if ($exit -ne 1 -or $message -notlike ('STOP:*stage='+$case.Value+' *')) { throw ('wrong-stage-'+$case.Key) }
        if ($case.Value -notin @('dacl_correction','post_verification') -and $script:mutated) { throw 'early-mutation' }
    }
    if ($message.Contains($operator) -or $message.Contains($expected) -or $message.Contains('synthetic-original')) { throw 'disclosure' }
    $count++
}
Write-Output ('PASS: '+$count+' mocked correction scenarios')
""".replace("HELPER", str(HELPER))
        result = powershell(code)
        self.assertEqual(result.returncode, 0, "mocked correction gates failed: " + result.stderr)
        self.assertEqual(result.stdout.strip(), "PASS: 20 mocked correction scenarios")

    def test_in_memory_descriptor_and_private_profiles(self):
        code = r"""
$ErrorActionPreference='Stop'
. 'HELPER'
$operator='S-1-5-21-111-222-333-1001'
foreach ($directory in @($false,$true)) {
    $security=New-DemoDaclSecurity $operator -Directory:$directory
    if (-not $security.AreAccessRulesProtected) { throw 'protection' }
    if ($security.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $operator) { throw 'owner' }
    $rules=@($security.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 2) { throw 'rules' }
    $metadata=[pscustomobject]@{Owner=$operator;Protected=$true;Rules=@(
        [pscustomobject]@{Sid=$operator;Inherited=$false;Allow=$true;Rights=[Security.AccessControl.FileSystemRights]::FullControl},
        [pscustomobject]@{Sid='S-1-5-18';Inherited=$false;Allow=$true;Rights=[Security.AccessControl.FileSystemRights]::FullControl}
    )}
    Assert-DemoDaclPrivate $metadata $operator
    foreach ($bad in @('inherited','deny','missing_system','unexpected')) {
        $copy=$metadata | ConvertTo-Json -Depth 5 | ConvertFrom-Json
        if ($bad -eq 'inherited') {$copy.Rules[0].Inherited=$true}
        if ($bad -eq 'deny') {$copy.Rules[0].Allow=$false}
        if ($bad -eq 'missing_system') {$copy.Rules=@($copy.Rules[0])}
        if ($bad -eq 'unexpected') {$copy.Rules[1].Sid='S-1-1-0'}
        $rejected=$false
        try { Assert-DemoDaclPrivate $copy $operator } catch { $rejected=$true }
        if (-not $rejected) { throw 'unsafe-profile' }
    }
}
Write-Output 'PASS'
""".replace("HELPER", str(HELPER))
        result = powershell(code)
        self.assertEqual(result.returncode, 0, "in-memory security descriptor checks failed: " + result.stderr)
        self.assertEqual(result.stdout.strip(), "PASS")

    def test_native_structure_layout_only(self):
        # Compile declarations only; no native entry point is invoked.
        result = powershell(
            "$ErrorActionPreference='Stop'; . '"
            + str(HELPER)
            + "'; Initialize-DemoDaclNative; "
            + "if ([Runtime.InteropServices.Marshal]::SizeOf([type]'LankaPexDemoDacl.Native+Info') -ne 52) {throw 'layout'}; 'PASS'"
        )
        self.assertEqual(result.returncode, 0, "native declaration compilation failed: " + result.stderr)
        self.assertEqual(result.stdout.strip(), "PASS")

    def test_mocked_separate_rollback(self):
        code = r"""
$ErrorActionPreference='Stop'
. 'HELPER'
$operator='S-1-5-21-111-222-333-1001'
$expected='C:\Users\admin\Desktop\LankaPex\.server-logs\private-demo\demo-app.dpapi'
$backup='C:\Users\admin\Desktop\LankaPex\.server-logs\demo-dacl-backup-11111111111111111111111111111111\original-dacl.json'
function Assert-DemoDaclNoReparse { param($Path) }
function Get-DemoDaclOperator { return $operator }
function Assert-DemoDaclPrivate { param($Metadata,$Operator) }
function Get-DemoDaclMetadata {
    param($Path)
    $sddl=if ($Path -eq $expected -and -not $script:restored) {'corrected'} else {'original'}
    return [pscustomobject]@{Owner=$operator;Sddl=$sddl}
}
function Open-DemoDaclTarget {
    param($Path)
    $h=[pscustomobject]@{}
    $h | Add-Member ScriptMethod Dispose {}
    return $h
}
function Open-DemoDaclBackupDirectory { param($Path) return (Open-DemoDaclTarget $Path) }
function Get-DemoDaclIdentity { param($Handle) return 'identity' }
function Read-DemoDaclBackup {
    param($Path)
    $owner=if ($script:scenario -eq 'wrong_owner') {'other'} else {$operator}
    return [pscustomobject]@{Format=1;Target=$expected;Owner=$owner;Identity='identity';OriginalDacl='original';ParentDacl='original'}
}
function Set-DemoDaclOnHandle {
    param($Handle,$Operator,$RestoreSddl)
    if ($RestoreSddl -cne 'original') {throw 'wrong-restore'}
    $script:touched=$true
    if ($script:scenario -eq 'native_failure') {throw 'synthetic'}
    $script:restored=$true
}
foreach ($case in @('missing_confirmation','wrong_owner','native_failure','success','duplicate')) {
    $script:scenario=$case; $script:restored=($case -eq 'duplicate'); $script:touched=$false
    $confirm=$case -ne 'missing_confirmation'
    $result=@(Invoke-DemoCredentialDaclRollback $backup -ConfirmRollback:$confirm -ConfirmOriginalBroaderAccess:$confirm)
    $exit=[int]$result[-1]
    if ($case -eq 'success') {
        if ($exit -ne 0 -or -not $script:touched) {throw 'restore-success'}
    } else {
        if ($exit -ne 1) {throw 'unsafe-restore'}
        if ($case -ne 'native_failure' -and $script:touched) {throw 'early-restore'}
    }
}
Write-Output 'PASS: 5 mocked rollback scenarios'
""".replace("HELPER", str(HELPER))
        result = powershell(code)
        self.assertEqual(result.returncode, 0, "mocked rollback gates failed: " + result.stderr)
        self.assertEqual(result.stdout.strip(), "PASS: 5 mocked rollback scenarios")

    def test_wrapper_defaults_and_confirmation(self):
        for args, expected in [
            ([], 0),
            (["-Execute"], 1),
            (["-Execute", "-ConfirmTarget", "C:\\wrong", "-ConfirmFileOnlyDacl"], 1),
        ]:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(WRAPPER), *args],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, expected)
            self.assertIn("PASS:" if expected == 0 else "STOP:", result.stdout)

    def test_source_scope(self):
        source = HELPER.read_text(encoding="utf-8-sig")
        wrapper = WRAPPER.read_text(encoding="utf-8-sig")
        for forbidden in ("ConvertTo-SecureString", "SecureStringToBSTR", "Get-Content", "Set-Acl", "Remove-Item", "SetOwner($before", "icacls", "mysql", "http"):
            self.assertNotIn(forbidden, source)
        self.assertIn("[IO.FileMode]::CreateNew", source)
        self.assertIn("SetSecurityInfo($Handle,1,$flags,[IntPtr]::Zero,[IntPtr]::Zero,$dacl,[IntPtr]::Zero)", source)
        self.assertIn("CreateFile($Path,0x60000,1", source)
        self.assertLess(source.index("$backupVerified=$true"), source.index("Set-DemoDaclOnHandle $handle $operator"))
        self.assertIn("no automatic rollback", source)
        self.assertIn("finally", source)
        self.assertNotIn("Rollback", wrapper)


if __name__ == "__main__":
    unittest.main()
