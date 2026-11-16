# Demo migration gate using a locally DPAPI-protected secret.
# Default is read-only. -Execute runs a fresh read-only preflight immediately
# before the separately authorized exact-target migration. No secret is printed.
param([switch]$Execute)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'
$secretFile = Join-Path $repoRoot '.server-logs\private-demo\demo-migrator.dpapi'
if (-not (Test-Path -LiteralPath $python)) { throw 'Backend Python environment missing.' }
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
    throw 'Private demo migrator credential is not provisioned.'
}
$names = @('MYSQL_PASSWORD', 'APP_ENV', 'MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_DATABASE', 'MYSQL_USER')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$secure = ConvertTo-SecureString (Get-Content -LiteralPath $secretFile -Raw)
$pointer = [IntPtr]::Zero
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $env:MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $env:APP_ENV = 'development'
    $env:MYSQL_HOST = 'localhost'
    $env:MYSQL_PORT = '3306'
    $env:MYSQL_DATABASE = 'lankapex_demo_db'
    $env:MYSQL_USER = 'lankapex_demo_migrator'
    Push-Location $repoRoot
    try {
        & $python .\backend\scripts\prepare_demo_database.py --database lankapex_demo_db
        if ($LASTEXITCODE -ne 0) { throw 'Read-only demo preflight failed.' }
        if ($Execute) {
            & $python .\backend\scripts\prepare_demo_database.py --database lankapex_demo_db --execute --confirm-target lankapex_demo_db
            if ($LASTEXITCODE -ne 0) { throw 'Demo migration stopped; preserve the target for diagnosis.' }
        }
    } finally {
        Pop-Location
    }
} finally {
    foreach ($name in $names) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    if ($null -ne $secure) { $secure.Dispose() }
}
