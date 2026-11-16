# Exact-target AI snapshot test migration gate. Default mode is read-only.
param(
    [switch]$Execute,
    [string]$ConfirmTarget,
    [switch]$ConfirmEmpty,
    [switch]$PauseVerified
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$secretFile = Join-Path $root '.server-logs\private-ai-tests\ai-snapshot-test-migrator.dpapi'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Backend Python environment missing.' }
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) { throw 'Private AI snapshot migrator credential missing.' }
if ($Execute -and ($ConfirmTarget -cne 'lankapex_ai_snapshot_test_db' -or -not $ConfirmEmpty -or -not $PauseVerified)) {
    throw 'Execution requires exact target, empty-schema, and maintained writer/DDL-pause confirmation.'
}
if (-not $Execute -and ($ConfirmTarget -or $ConfirmEmpty -or $PauseVerified)) {
    throw 'Execution-only confirmations require -Execute.'
}
$names = @('APP_ENV','MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD','AI_ENABLED','GROQ_API_KEY')
$old = @{}
foreach ($name in $names) { $old[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$secure = $null; $pointer = [IntPtr]::Zero
try {
    $secure = ConvertTo-SecureString (Get-Content -LiteralPath $secretFile -Raw)
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $env:MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $env:APP_ENV = 'ai_snapshot_migration'
    $env:MYSQL_HOST = 'localhost'; $env:MYSQL_PORT = '3306'
    $env:MYSQL_DATABASE = 'lankapex_ai_snapshot_test_db'
    $env:MYSQL_USER = 'lankapex_ai_snap_migrator'
    $env:AI_ENABLED = 'false'; $env:GROQ_API_KEY = ''
    $runner = Join-Path $root 'backend\scripts\migrate_ai_snapshot_test_database.py'
    $runnerArgs = @($runner, '--database', 'lankapex_ai_snapshot_test_db')
    if ($Execute) { $runnerArgs += @('--execute','--confirm-target','lankapex_ai_snapshot_test_db','--confirm-empty','--pause-verified') }
    & $python @runnerArgs
    if ($LASTEXITCODE -ne 0) { throw 'AI snapshot migration gate stopped; preserve target state and evidence.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $old[$name], 'Process') }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
}
