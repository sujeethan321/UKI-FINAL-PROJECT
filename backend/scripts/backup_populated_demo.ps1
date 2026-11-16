# Operator-only backup. Uses existing DPAPI CurrentUser migrator credential.
param([switch]$Execute)
$ErrorActionPreference = 'Stop'
if (-not $Execute) { throw 'Backup requires explicit -Execute; no database migration is run.' }
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$secretFile = Join-Path $root '.server-logs\private-demo\demo-migrator.dpapi'
$backupDir = Join-Path $root '.server-logs\private-demo-backups'
if (-not (Test-Path -LiteralPath $python)) { throw 'Backend Python environment missing.' }
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) { throw 'Private demo migrator credential missing.' }
if (-not (Test-Path -LiteralPath $backupDir -PathType Container)) { throw 'Private backup directory missing.' }
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
    & $python (Join-Path $root 'backend\scripts\backup_populated_demo.py') --database lankapex_demo_db
    if ($LASTEXITCODE -ne 0) { throw 'Private demo backup failed; preserve evidence for review.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
}
