$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'tamil_ai_private_acl.ps1')

class FakeIdentityReference {
    [string]$Value
    FakeIdentityReference([string]$value){$this.Value=$value}
    [object] Translate([type]$targetType){return [pscustomobject]@{Value=$this.Value}}
}
class FakeRule {
    [object]$IdentityReference;[object]$FileSystemRights;[string]$AccessControlType;[bool]$IsInherited
    FakeRule([string]$sid,[object]$rights,[string]$kind,[bool]$inherited){
        $this.IdentityReference=[FakeIdentityReference]::new($sid);$this.FileSystemRights=$rights
        $this.AccessControlType=$kind;$this.IsInherited=$inherited
    }
}
class FakeAcl {
    [bool]$AreAccessRulesProtected;[object[]]$Access
    FakeAcl([bool]$protected,[object[]]$rules){$this.AreAccessRulesProtected=$protected;$this.Access=$rules}
}
function Assert-True([bool]$value,[string]$message){if(-not $value){throw $message}}
$operator='S-1-5-21-1000'
$full=[Security.AccessControl.FileSystemRights]::FullControl
$good=[FakeAcl]::new($true,@([FakeRule]::new($operator,$full,'Allow',$false),[FakeRule]::new('S-1-5-18',$full,'Allow',$false)))
Assert-True (Get-TamilAiPrivateAclAssessment $good $operator).IsSecure 'secure DACL rejected'
$inherited=[FakeAcl]::new($false,@([FakeRule]::new($operator,$full,'Allow',$true),[FakeRule]::new('S-1-5-18',$full,'Allow',$false)))
Assert-True (-not (Get-TamilAiPrivateAclAssessment $inherited $operator).IsSecure) 'inherited DACL accepted'
$missing=[FakeAcl]::new($true,@([FakeRule]::new($operator,$full,'Allow',$false)))
Assert-True (-not (Get-TamilAiPrivateAclAssessment $missing $operator).IsSecure) 'missing SYSTEM accepted'
$unexpected=[FakeAcl]::new($true,@([FakeRule]::new($operator,$full,'Allow',$false),[FakeRule]::new('S-1-5-18',$full,'Allow',$false),[FakeRule]::new('S-1-5-32-545',$full,'Allow',$false)))
Assert-True (-not (Get-TamilAiPrivateAclAssessment $unexpected $operator).IsSecure) 'unexpected principal accepted'
$arguments=Get-TamilAiPrivateAclArguments 'X:\private\evidence.json' $operator
Assert-True ($arguments.Count -eq 5 -and $arguments[1] -ceq '/inheritance:r' -and $arguments[2] -ceq '/grant:r') 'DACL arguments differ'
Assert-True ($arguments[3] -ceq ('*'+$operator+':(F)') -and $arguments[4] -ceq '*S-1-5-18:(F)') 'SID grants differ'
$failed=$false;try{Assert-TamilAiIcaclsExitCode 5}catch{$failed=$true}
Assert-True $failed 'nonzero icacls exit accepted'
Assert-TamilAiIcaclsExitCode 0
Write-Output 'PASS: 7 database-free DACL construction, classification and failure checks'
