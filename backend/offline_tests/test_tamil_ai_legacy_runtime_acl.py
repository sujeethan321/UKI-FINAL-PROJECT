"""Synthetic ACL objects only; never reads private file ACLs or credentials."""
import base64
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_acl_profiles_and_exact_path_gate():
    helper = ROOT / "backend/scripts/tamil_ai_private_acl.ps1"
    script = r'''
. 'HELPER'
function Resolve-TamilAiRuleSid { param($Rule) return $Rule.Sid }
$operator='S-1-5-21-111-222-333-1001'
function Rule($sid,$rights='FullControl',$inherited=$false,$kind='Allow') {
    [pscustomobject]@{Sid=$sid;FileSystemRights=[Security.AccessControl.FileSystemRights]$rights;IsInherited=$inherited;AccessControlType=$kind}
}
function Acl($rules,$protected=$true) { [pscustomobject]@{Access=@($rules);AreAccessRulesProtected=$protected} }
$only=Acl @( (Rule $operator) )
$both=Acl @( (Rule $operator), (Rule 'S-1-5-18') )
if((Get-TamilAiPrivateAclAssessment $only $operator).IsSecure){throw 'strict accepted operator-only'}
if(-not(Get-TamilAiPrivateAclAssessment $only $operator -AllowOperatorOnly).IsSecure){throw 'legacy rejected'}
if(-not(Get-TamilAiPrivateAclAssessment $both $operator).IsSecure){throw 'strict rejected'}
if(-not(Get-TamilAiPrivateAclAssessment $both $operator -AllowOperatorOnly).IsSecure){throw 'legacy both rejected'}
foreach($unsafe in @(
    (Acl @((Rule $operator)) $false),
    (Acl @((Rule $operator 'FullControl' $true))),
    (Acl @((Rule 'S-1-5-18'))),
    (Acl @((Rule $operator 'Read'))),
    (Acl @((Rule $operator),(Rule 'S-1-1-0'))),
    (Acl @((Rule $operator 'FullControl' $false 'Deny')))
)) {
    if((Get-TamilAiPrivateAclAssessment $unsafe $operator -AllowOperatorOnly).IsSecure){throw 'unsafe legacy accepted'}
    if((Get-TamilAiPrivateAclAssessment $unsafe $operator).IsSecure){throw 'unsafe strict accepted'}
}
$rejected=$false
try { Assert-TamilAiLegacyRuntimeCredentialAcl 'C:\synthetic\tamil-ai-browser-jwt.dpapi' $operator }
catch { $rejected=$true }
if(-not $rejected){throw 'wrong path accepted'}
Write-Output 'PASS'
'''.replace("HELPER", str(helper))
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-EncodedCommand", encoded],
                            capture_output=True, text=True)
    assert result.returncode == 0, "synthetic ACL tests failed"
    assert result.stdout.strip() == "PASS"


def test_exception_only_used_for_runtime_file():
    wrapper = (ROOT / "backend/scripts/verify_tamil_ai_owner_credential.ps1").read_text()
    assert "Assert-TamilAiLegacyRuntimeCredentialAcl $dbFile $operatorSid" in wrapper
    assert "@($jwtFile,$ownerFile,$reservation,$evidence)" in wrapper
    assert "Assert-TamilAiPrivateFileAcl $file $operatorSid" in wrapper
    assert "Set-TamilAiPrivateFileDaclOnly" not in wrapper
