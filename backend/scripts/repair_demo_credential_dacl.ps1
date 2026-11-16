param([switch]$Execute,[string]$ConfirmTarget,[switch]$ConfirmFileOnlyDacl)
$ErrorActionPreference='Stop'
$expected='C:\Users\admin\Desktop\LankaPex\.server-logs\private-demo\demo-app.dpapi'
if (-not $Execute) {
    if ($ConfirmTarget -or $ConfirmFileOnlyDacl) { Write-Output 'STOP: demo credential DACL stage=confirmation'; exit 1 }
    Write-Output 'PASS: offline DACL procedure preparation only; no private metadata read or permission changed'
    exit 0
}
if ($ConfirmTarget -cne $expected -or -not $ConfirmFileOnlyDacl) { Write-Output 'STOP: demo credential DACL stage=confirmation'; exit 1 }
. (Join-Path $PSScriptRoot 'demo_credential_dacl.ps1')
$backupDirectory=Join-Path (Split-Path -Parent (Split-Path -Parent $expected)) ('demo-dacl-backup-'+[guid]::NewGuid().ToString('N'))
$backupFile=Join-Path $backupDirectory 'original-dacl.json'
$results=@(Invoke-DemoCredentialDaclCorrection $expected $expected $backupDirectory $backupFile)
$exitCode=[int]$results[-1]
$results | Select-Object -SkipLast 1 | Write-Output
exit $exitCode
