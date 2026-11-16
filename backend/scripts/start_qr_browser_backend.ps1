# Operator-only, loopback QR browser API. No records or schema are created here.
param([switch]$PreflightOnly)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$dbSecretFile = Join-Path $root '.server-logs\private-test\qr-test-runtime.dpapi'
$jwtSecretFile = Join-Path $root '.server-logs\private-test\qr-browser-jwt.dpapi'
foreach ($file in @($python, $dbSecretFile, $jwtSecretFile)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'STOP: QR browser prerequisite missing; server not started.' }
}
$names = @('APP_ENV', 'MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_DATABASE', 'MYSQL_USER',
           'MYSQL_PASSWORD', 'JWT_SECRET_KEY', 'PYTHONPATH', 'APP_DEBUG', 'LOG_LEVEL',
           'CORS_ALLOWED_ORIGINS', 'RATE_LIMIT_MODE')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$dbSecure = $null; $jwtSecure = $null
$dbPointer = [IntPtr]::Zero; $jwtPointer = [IntPtr]::Zero
try {
    $dbSecure = ConvertTo-SecureString (Get-Content -LiteralPath $dbSecretFile -Raw)
    $jwtSecure = ConvertTo-SecureString (Get-Content -LiteralPath $jwtSecretFile -Raw)
    $dbPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbSecure)
    $jwtPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($jwtSecure)
    $env:MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($dbPointer)
    $env:JWT_SECRET_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($jwtPointer)
    $env:APP_ENV = 'testing'
    $env:MYSQL_HOST = 'localhost'
    $env:MYSQL_PORT = '3306'
    $env:MYSQL_DATABASE = 'lankapex_test_db'
    $env:MYSQL_USER = 'lankapex_qr_test_runtime'
    $env:PYTHONPATH = Join-Path $root 'backend'
    $env:APP_DEBUG = 'false'
    $env:LOG_LEVEL = 'WARNING'
    $env:CORS_ALLOWED_ORIGINS = 'http://127.0.0.1:5174'
    $env:RATE_LIMIT_MODE = 'local'

    & $python (Join-Path $root 'backend\scripts\check_qr_browser_config.py')
    if ($LASTEXITCODE -ne 0) { throw 'STOP: browser configuration gate failed; server not started.' }
    & $python (Join-Path $root 'backend\scripts\check_qr_test_runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'STOP: exact-target database preflight failed; server not started.' }
    if ($PreflightOnly) {
        Write-Output 'READ-ONLY QR BROWSER PREFLIGHT COMPLETE; no server started'
        return
    }
    Push-Location (Join-Path $root 'backend')
    try {
        & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8013 --log-level warning --no-access-log
        if ($LASTEXITCODE -ne 0) { throw 'STOP: test-only API exited with an error.' }
    } finally { Pop-Location }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    if ($dbPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($dbPointer) }
    if ($jwtPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($jwtPointer) }
    if ($null -ne $dbSecure) { $dbSecure.Dispose() }
    if ($null -ne $jwtSecure) { $jwtSecure.Dispose() }
}
