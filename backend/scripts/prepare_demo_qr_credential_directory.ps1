param([switch]$PreflightOnly,[switch]$Execute,[switch]$ConfirmDirectoryCreation,
      [string]$ConfirmMissingComponents)
$ErrorActionPreference='Stop'
if (-not $PreflightOnly -and -not $Execute) {
    if ($ConfirmDirectoryCreation -or $ConfirmMissingComponents) {
        Write-Output 'STOP: QR directory preparation category=confirmation'; exit 1
    }
    Write-Output 'PASS: offline QR directory preparation only; no filesystem metadata or credentials accessed'
    exit 0
}
if (($PreflightOnly -and $Execute) -or
    ($PreflightOnly -and ($ConfirmDirectoryCreation -or $ConfirmMissingComponents)) -or
    ($Execute -and (-not $ConfirmDirectoryCreation -or
        $ConfirmMissingComponents -cnotin @('PrivateDemoQr','LankaPex,PrivateDemoQr')))) {
    Write-Output 'STOP: QR directory preparation category=confirmation'; exit 1
}
$state=@{Stage='helper_load';Created=0}
try {
    . (Join-Path $PSScriptRoot 'demo_qr_credential_storage.ps1')
    . (Join-Path $PSScriptRoot 'demo_qr_storage_directory_creation.ps1')
    Invoke-DemoQrDirectoryPreparation -Execute:$Execute -ConfirmDirectoryCreation:$ConfirmDirectoryCreation -ConfirmMissingComponents $ConfirmMissingComponents -State $state
    $exitCode=0
} catch {
    $check='metadata_or_runtime_unverified'
    $allowed=@('directory_confirmation','directory_destination','unsupported_missing_components',
        'directory_plan_confirmation_mismatch','directory_identity_changed','directory_plan_changed',
        'exclusive_directory_exists','exclusive_directory_creation_failed','created_directory_type',
        'final_directory_identity','storage_directory_exists')
    if ($_.Exception.Message -cin $allowed) { $check=$_.Exception.Message }
    elseif (Get-Command Get-DemoQrStorageFailureCheck -ErrorAction SilentlyContinue) {
        $check=Get-DemoQrStorageFailureCheck $_.Exception.Message
    }
    Write-Output ('STOP: QR directory preparation category='+$state.Stage+' check='+$check+' created_components='+$state.Created+'; preserve partial state; no retry or automatic repair')
    $exitCode=1
}
exit $exitCode
