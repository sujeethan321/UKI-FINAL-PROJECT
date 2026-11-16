# Operator-only, one-time Admin bootstrap for the exact empty demo database.
# Run as the Windows account that owns the DPAPI CurrentUser blobs.
param(
    [string]$Email = 'demo.admin@example.com',
    [string]$Name = 'LankaPex Demo Admin',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'
$secretFile = Join-Path $repoRoot '.server-logs\private-demo\demo-app.dpapi'
$jwtFile = Join-Path $repoRoot '.server-logs\private-demo\demo-jwt.dpapi'
foreach ($path in @($python, $secretFile, $jwtFile)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Required private demo runtime file is missing.' }
}
$names = @('APP_ENV', 'MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD', 'JWT_SECRET_KEY')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$secure = $null
$jwtSecure = $null
$pointer = [IntPtr]::Zero
$jwtPointer = [IntPtr]::Zero
try {
    $secure = ConvertTo-SecureString (Get-Content -LiteralPath $secretFile -Raw)
    $jwtSecure = ConvertTo-SecureString (Get-Content -LiteralPath $jwtFile -Raw)
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
        if ($LASTEXITCODE -ne 0) { throw 'Read-only demo runtime gate failed; Admin not provisioned.' }
        $arguments = @('-m', 'scripts.provision_admin', '--email', $Email, '--name', $Name,
            '--confirm-database', 'lankapex_demo_db', '--demo-only')
        if ($CheckOnly) { $arguments += '--demo-check-only' }
        & $python @arguments
        if ($LASTEXITCODE -ne 0) { throw 'Demo Admin provisioning or verification failed; stop and inspect before retrying.' }
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
