function Get-TamilAiPrivateAclArguments {
    param([Parameter(Mandatory=$true)][string]$Path,
          [Parameter(Mandatory=$true)][string]$OperatorSid)
    if ($OperatorSid -notmatch '^S-1-[0-9-]+$') { throw 'STOP: invalid operator SID.' }
    return @($Path, '/inheritance:r', '/grant:r', ('*' + $OperatorSid + ':(F)'), '*S-1-5-18:(F)')
}

function Assert-TamilAiIcaclsExitCode {
    param([Parameter(Mandatory=$true)][int]$ExitCode)
    if($ExitCode -ne 0){throw 'STOP: DACL-only icacls operation failed.'}
}

function Resolve-TamilAiRuleSid {
    param($Rule)
    try {
        return $Rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
    } catch {
        throw 'STOP: private ACL contains an unresolvable principal.'
    }
}

function Get-TamilAiPrivateAclAssessment {
    param([Parameter(Mandatory=$true)]$Acl,
          [Parameter(Mandatory=$true)][string]$OperatorSid,
          [switch]$AllowOperatorOnly)
    $systemSid = 'S-1-5-18'
    $operatorFull = $false; $systemFull = $false; $unexpected = 0
    foreach ($rule in @($Acl.Access)) {
        $sid = Resolve-TamilAiRuleSid $rule
        $full = (($rule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq
                 [Security.AccessControl.FileSystemRights]::FullControl)
        if ($rule.IsInherited -or $rule.AccessControlType -ne 'Allow') { $unexpected++; continue }
        if ($sid -eq $OperatorSid -and $full) { $operatorFull = $true; continue }
        if ($sid -eq $systemSid -and $full) { $systemFull = $true; continue }
        $unexpected++
    }
    [pscustomobject]@{
        IsSecure = [bool]($Acl.AreAccessRulesProtected -and $operatorFull -and
                         ($systemFull -or $AllowOperatorOnly) -and $unexpected -eq 0)
        InheritanceProtected = [bool]$Acl.AreAccessRulesProtected
        OperatorFullControl = $operatorFull
        SystemFullControl = $systemFull
        UnexpectedRuleCount = $unexpected
    }
}

function Assert-TamilAiLegacyRuntimeCredentialAcl {
    param([Parameter(Mandatory=$true)][string]$Path,
          [Parameter(Mandatory=$true)][string]$OperatorSid)
    $expected = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\.server-logs\private-ai-tests\ai-snapshot-test-runtime.dpapi'))
    if (-not [string]::Equals([IO.Path]::GetFullPath($Path), $expected, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'STOP: legacy credential ACL exception requires the exact runtime path.'
    }
    $item = Get-Item -LiteralPath $Path -ErrorAction Stop
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'STOP: legacy runtime credential must be a regular file.'
    }
    $assessment = Get-TamilAiPrivateAclAssessment (Get-Acl -LiteralPath $Path -ErrorAction Stop) $OperatorSid -AllowOperatorOnly
    if (-not $assessment.IsSecure) { throw 'STOP: legacy runtime credential DACL is unsafe.' }
}

function Assert-TamilAiPrivateFileAcl {
    param([Parameter(Mandatory=$true)][string]$Path,
          [Parameter(Mandatory=$true)][string]$OperatorSid)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw 'STOP: required private fixture file missing.' }
    $assessment = Get-TamilAiPrivateAclAssessment (Get-Acl -LiteralPath $Path -ErrorAction Stop) $OperatorSid
    if (-not $assessment.IsSecure) { throw 'STOP: private fixture DACL is not operator/SYSTEM-only.' }
}

function Set-TamilAiPrivateFileDaclOnly {
    param([Parameter(Mandatory=$true)][string]$Path,
          [Parameter(Mandatory=$true)][string]$OperatorSid)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw 'STOP: private fixture file missing during DACL setup.' }
    # Refuse to erase an explicit principal we did not create. Inherited rules
    # may be removed by /inheritance:r; no SACL or owner operation is requested.
    $existing = Get-Acl -LiteralPath $Path -ErrorAction Stop
    foreach ($rule in @($existing.Access)) {
        $sid = Resolve-TamilAiRuleSid $rule
        if (-not $rule.IsInherited -and ($sid -notin @($OperatorSid, 'S-1-5-18') -or
                $rule.AccessControlType -ne 'Allow')) {
            throw 'STOP: refusing DACL repair with an unexpected explicit principal.'
        }
    }
    $arguments = Get-TamilAiPrivateAclArguments $Path $OperatorSid
    & icacls.exe @arguments | Out-Null
    Assert-TamilAiIcaclsExitCode $LASTEXITCODE
    Assert-TamilAiPrivateFileAcl $Path $OperatorSid
}
