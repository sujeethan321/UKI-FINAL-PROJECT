# Metadata only; never reads credentials or creates storage.
param([switch]$Diagnostic)
$ErrorActionPreference='Stop'
$lease=$null
$trace=@{Stage='helper_load';Surface='none';NativeError='none'}
try {
    . (Join-Path $PSScriptRoot 'demo_qr_credential_storage.ps1')
    $lease=Assert-DemoQrCredentialStorage -Mode Prepare -Trace $trace
    Write-Output 'PASS: dedicated QR credential storage metadata verified; no credentials read or files changed'
    $exitCode=0
} catch {
    $category='metadata_unverified'
    if ($_.Exception.Message -ceq 'storage_preparation_required') { $category='storage_preparation_required' }
    Write-Output ('STOP: QR credential storage category='+$category)
    if ($Diagnostic) {
        if (Get-Command Get-DemoQrStorageDiagnosticLine -ErrorAction SilentlyContinue) {
            Get-DemoQrStorageDiagnosticLine $trace $_.Exception.Message
        } else {
            Write-Output 'STOP: QR storage diagnostic stage=helper_load surface=none check=helper_or_runtime_error native_error=none'
        }
    }
    $exitCode=1
} finally { if (Get-Command Close-DemoQrStorageLease -ErrorAction SilentlyContinue) { Close-DemoQrStorageLease $lease } }
exit $exitCode
