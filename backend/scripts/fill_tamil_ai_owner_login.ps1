param([switch]$Execute,[string]$ConfirmRunId='')
$ErrorActionPreference='Stop'
$runId='14405b71b0504036a35ff55c7a9da132'
if(-not $Execute){Write-Output 'PASS: fill-only preparation; no credential read or browser connection';return}
if($ConfirmRunId -cne $runId){throw 'STOP: exact RunId confirmation required.'}
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ownerFile=Join-Path $root ".server-logs\private-ai-tests\tamil-ai-browser-fixture-$runId-owner.dpapi"
. (Join-Path $PSScriptRoot 'tamil_ai_private_acl.ps1')
Assert-TamilAiPrivateFileAcl $ownerFile ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
$secure=$null;$pointer=[IntPtr]::Zero;$payload=$null
try {
    $secure=ConvertTo-SecureString (Get-Content -LiteralPath $ownerFile -Raw)
    $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $payload=@{password=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)}|ConvertTo-Json -Compress
    $payload | & (Join-Path $root 'backend\.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'fill_tamil_ai_owner_login.py') --execute --confirm-run-id $runId
    if($LASTEXITCODE -ne 0){throw 'STOP: isolated login fill failed; inspect before any retry.'}
} finally {
    $payload=$null
    if($pointer -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}
    if($null -ne $secure){$secure.Dispose()}
}
