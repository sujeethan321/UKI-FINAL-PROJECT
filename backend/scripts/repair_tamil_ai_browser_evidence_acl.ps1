param(
    [Parameter(Mandatory=$true)][string]$RunId,
    [switch]$Execute,
    [string]$ConfirmRunId='',
    [switch]$ConfirmAclRepair
)
$ErrorActionPreference='Stop'
if($RunId -cnotmatch '^[0-9a-f]{32}$'){throw 'STOP: exact lowercase 128-bit run ID required.'}
if($Execute){
    if($ConfirmRunId -cne $RunId -or -not $ConfirmAclRepair){throw 'STOP: exact RunId and ACL-repair confirmation required.'}
} elseif($ConfirmRunId -or $ConfirmAclRepair){throw 'STOP: repair confirmations require -Execute.'}
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'tamil_ai_private_acl.ps1')
$privateDir=Join-Path $root '.server-logs\private-ai-tests'
$required=@(
    (Join-Path $privateDir "tamil-ai-browser-fixture-$RunId.json"),
    (Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-owner.dpapi"),
    (Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-pending.json"),
    (Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-created.json")
)
$forbidden=@(
    (Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-cleanup-pending.json"),
    (Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-cleaned.json")
)
foreach($path in $required){if(-not(Test-Path -LiteralPath $path -PathType Leaf)){throw 'STOP: expected fixture evidence file missing.'}}
foreach($path in $forbidden){if(Test-Path -LiteralPath $path){throw 'STOP: cleanup evidence exists; ACL repair scope differs.'}}
$operatorSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if(-not $Execute){
    $failed=$false
    foreach($path in $required){
        $assessment=Get-TamilAiPrivateAclAssessment (Get-Acl -LiteralPath $path -ErrorAction Stop) $operatorSid
        if(-not $assessment.IsSecure){$failed=$true}
    }
    if($failed){throw 'STOP: one or more fixture DACLs require separately authorized repair.'}
    Write-Output 'PASS: exact fixture files use protected operator/SYSTEM-only DACLs; no file changed'
    return
}
foreach($path in $required){Set-TamilAiPrivateFileDaclOnly $path $operatorSid}
Write-Output 'PASS: exact existing fixture files now use protected operator/SYSTEM-only DACLs'
