# Private DPAPI CurrentUser demo-app credential and separate JWT secret.
# No .env file is edited. This script can be invoked from any directory.
param([switch]$PreflightOnly)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'
$secretFile = Join-Path $repoRoot '.server-logs\private-demo\demo-app.dpapi'
$jwtFile = Join-Path $repoRoot '.server-logs\private-demo\demo-jwt.dpapi'
if (-not (Test-Path -LiteralPath $python)) { throw 'Backend virtual environment is missing.' }
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
    throw 'Private demo runtime credential is not provisioned.'
}
if (-not (Test-Path -LiteralPath $jwtFile -PathType Leaf)) {
    throw 'Private demo JWT secret is not provisioned.'
}
$names = @('APP_ENV', 'MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD', 'JWT_SECRET_KEY', 'AI_ENABLED', 'GROQ_API_KEY', 'APP_DEBUG', 'LOG_LEVEL', 'RATE_LIMIT_MODE', 'CORS_ALLOWED_ORIGINS', 'ALLOWED_HOSTS')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$secure = $null
$jwtSecure = $null
if ($null -ne [Environment]::GetEnvironmentVariable('LANKAPEX_DISABLE_DOTENV', 'Process')) { throw 'Unsupported inherited dotenv isolation flag; demo not started.' }
$pointer = [IntPtr]::Zero
$jwtPointer = [IntPtr]::Zero
try {
    $secure = ConvertTo-SecureString (Get-Content -LiteralPath $secretFile -Raw)
    $jwtSecure = ConvertTo-SecureString (Get-Content -LiteralPath $jwtFile -Raw)
    $env:AI_ENABLED = 'false'
    [Environment]::SetEnvironmentVariable('GROQ_API_KEY', $null, 'Process')
    $env:APP_DEBUG = 'false'
    $env:LOG_LEVEL = 'WARNING'
    $env:RATE_LIMIT_MODE = 'local'
    $env:CORS_ALLOWED_ORIGINS = 'http://127.0.0.1:5173'
    $env:ALLOWED_HOSTS = '127.0.0.1,localhost'
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $jwtPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($jwtSecure)
    $env:APP_ENV = 'development'
    $env:MYSQL_HOST = 'localhost'
    $env:MYSQL_PORT = '3306'
    $env:MYSQL_DATABASE = 'lankapex_demo_db'
    $env:MYSQL_USER = 'lankapex_demo_app'
    $env:MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $env:JWT_SECRET_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($jwtPointer)
    Push-Location (Join-Path $repoRoot 'backend')
    try {
        & $python scripts/check_demo_backend.py
        if ($LASTEXITCODE -ne 0) { throw 'Demo API identity gate failed; server not started.' }
        if ($PreflightOnly) {
            Write-Output 'PASS: demo backend preflight only; no server started.'
        } else {
            & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
            if ($LASTEXITCODE -ne 0) { throw 'Demo backend stopped with an error.' }
        }
    } finally {
        Pop-Location
    }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($jwtPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($jwtPointer) }
    if ($null -ne $secure) { $secure.Dispose() }
    if ($null -ne $jwtSecure) { $jwtSecure.Dispose() }
}
