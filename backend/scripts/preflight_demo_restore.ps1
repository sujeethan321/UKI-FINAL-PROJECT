# Exact-target restore rehearsal. Default is read-only and never creates a DB.
param(
    [Parameter(Mandatory=$true)][string]$Manifest,
    [switch]$Execute,
    [switch]$Diagnose
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$secretFile = Join-Path $root '.server-logs\private-demo\demo-restore-b.dpapi'
if (-not (Test-Path -LiteralPath $python)) { throw 'Backend Python environment missing.' }
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) { throw 'Private restore credential not provisioned.' }
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
    $env:MYSQL_DATABASE = 'lankapex_demo_restore_verify_20261110b'
    $env:MYSQL_USER = 'lankapex_demo_restore_b'
    $arguments = @((Join-Path $root 'backend\scripts\rehearse_demo_backup_restore.py'),
                   '--database', 'lankapex_demo_restore_verify_20261110b', '--manifest', $Manifest)
    if ($Execute) { $arguments += @('--execute', '--confirm-target', 'lankapex_demo_restore_verify_20261110b') }
    if ($Diagnose) { $arguments += '--diagnose' }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Exact-target restore rehearsal stopped; preserve partial state.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
}
