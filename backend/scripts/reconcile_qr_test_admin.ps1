# Run read-only under the Windows account that owns the QR test DPAPI files.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$privateDir = Join-Path $root '.server-logs\private-test'
$dbFile = Join-Path $privateDir 'qr-test-runtime.dpapi'
$jwtFile = Join-Path $privateDir 'qr-browser-jwt.dpapi'
$adminFile = Join-Path $privateDir 'qr-browser-admin-recovery-password.dpapi'
foreach ($file in @($python,$dbFile,$jwtFile,$adminFile)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'STOP: QR reconciliation prerequisite missing.' }
}
$names = @('APP_ENV','MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER',
           'MYSQL_PASSWORD','JWT_SECRET_KEY','PYTHONPATH','QR_RECONCILE_ADMIN_PASSWORD')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
$dbSecure=$null; $jwtSecure=$null; $adminSecure=$null
$dbPointer=[IntPtr]::Zero; $jwtPointer=[IntPtr]::Zero; $adminPointer=[IntPtr]::Zero
try {
    $dbSecure = ConvertTo-SecureString (Get-Content -LiteralPath $dbFile -Raw)
    $jwtSecure = ConvertTo-SecureString (Get-Content -LiteralPath $jwtFile -Raw)
    $adminSecure = ConvertTo-SecureString (Get-Content -LiteralPath $adminFile -Raw)
    $dbPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbSecure)
    $jwtPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($jwtSecure)
    $adminPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($adminSecure)
    $env:MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($dbPointer)
    $env:JWT_SECRET_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($jwtPointer)
    $env:QR_RECONCILE_ADMIN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($adminPointer)
    $env:APP_ENV = 'testing'
    $env:MYSQL_HOST = 'localhost'
    $env:MYSQL_PORT = '3306'
    $env:MYSQL_DATABASE = 'lankapex_test_db'
    $env:MYSQL_USER = 'lankapex_qr_test_runtime'
    $env:PYTHONPATH = Join-Path $root 'backend'
    & $python (Join-Path $root 'backend\scripts\check_qr_test_runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'STOP: exact QR runtime preflight failed; no reconciliation queried.' }
    & $python (Join-Path $root 'backend\scripts\reconcile_qr_test_admin.py')
    if ($LASTEXITCODE -ne 0) { throw 'STOP: read-only Admin reconciliation failed.' }
    Write-Output 'READ-ONLY RECONCILIATION COMPLETE; no database or manifest changed'
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
    foreach ($pointer in @($dbPointer,$jwtPointer,$adminPointer)) {
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    }
    foreach ($secure in @($dbSecure,$jwtSecure,$adminSecure)) { if ($null -ne $secure) { $secure.Dispose() } }
}
