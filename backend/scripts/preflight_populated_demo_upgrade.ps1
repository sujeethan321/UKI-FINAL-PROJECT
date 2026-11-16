# Read-only by default. Execution needs separate authorization and all evidence gates.
param(
    [switch]$Execute,
    [string]$Backup,
    [string]$Sha256,
    [switch]$PauseVerified
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'
$secretFile = Join-Path $repoRoot '.server-logs\private-demo\demo-migrator.dpapi'
if (-not (Test-Path -LiteralPath $python)) { throw 'Backend Python environment missing.' }
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) { throw 'Private demo migrator credential missing.' }
if ($Execute -and (-not $Backup -or -not $Sha256 -or -not $PauseVerified)) {
    throw 'Execution needs pinned backup, checksum and maintained writer pause.'
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
    $arguments = @((Join-Path $repoRoot 'backend\scripts\upgrade_populated_demo_invitation.py'), '--database', 'lankapex_demo_db')
    if ($Backup) { $arguments += @('--backup', $Backup) }
    if ($Sha256) { $arguments += @('--sha256', $Sha256) }
    if ($Execute) {
        $arguments += @('--execute', '--confirm-target', 'lankapex_demo_db', '--pause-verified')
    }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Guarded populated-demo preflight/upgrade stopped.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
}
