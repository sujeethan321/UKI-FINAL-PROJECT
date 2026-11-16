# Exact-target QR test migration gate. Default action is read-only.
# The Windows operator must first provision a separate DPAPI CurrentUser blob.
param(
    [switch]$Execute,
    [string]$ConfirmTarget,
    [switch]$PauseVerified,
    [string]$Backup,
    [string]$Sha256,
    [switch]$DisposableTestDataApproved
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$secretFile = Join-Path $root '.server-logs\private-test\qr-test-migrator.dpapi'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Backend Python environment missing.' }
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) { throw 'Private QR test migrator credential missing.' }
if ($Execute -and ($ConfirmTarget -cne 'lankapex_test_db' -or -not $PauseVerified)) {
    throw 'Execution requires exact target confirmation and maintained writer/DDL pause.'
}
if ($Execute -and (($DisposableTestDataApproved -and ($Backup -or $Sha256)) -or
                   (-not $DisposableTestDataApproved -and (-not $Backup -or -not $Sha256)))) {
    throw 'Execution needs exactly one approved recovery policy.'
}
if (-not $Execute -and ($ConfirmTarget -or $PauseVerified -or $DisposableTestDataApproved)) {
    throw 'Execution-only flags require -Execute.'
}

$names = @('APP_ENV', 'MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD')
$old = @{}
foreach ($name in $names) { $old[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$secure = $null
$pointer = [IntPtr]::Zero
try {
    $secure = ConvertTo-SecureString (Get-Content -LiteralPath $secretFile -Raw)
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $env:MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $env:APP_ENV = 'testing'
    $env:MYSQL_HOST = 'localhost'
    $env:MYSQL_PORT = '3306'
    $env:MYSQL_DATABASE = 'lankapex_test_db'
    $env:MYSQL_USER = 'lankapex_qr_test_migrator'
    $runner = Join-Path $root 'backend\scripts\upgrade_qr_test_schema.py'
    $runnerArgs = @($runner, '--database', 'lankapex_test_db')
    if ($Backup) { $runnerArgs += @('--backup', $Backup) }
    if ($Sha256) { $runnerArgs += @('--sha256', $Sha256) }
    # The execution run repeats its complete preflight immediately before DDL.
    if ($Execute) {
        $runnerArgs += @('--execute', '--confirm-target', 'lankapex_test_db', '--pause-verified')
        if ($DisposableTestDataApproved) { $runnerArgs += '--disposable-test-data-approved' }
    }
    & $python @runnerArgs
    if ($LASTEXITCODE -ne 0) { throw 'QR test schema gate stopped; preserve state and evidence.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $old[$name], 'Process') }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
}
