param(
    [switch]$Execute,
    [string]$ConfirmTarget = ''
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$secretFile = Join-Path $root '.server-logs\private-ai-tests\ai-snapshot-test-runtime.dpapi'
$target = 'lankapex_ai_snapshot_test_db'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'STOP: backend Python missing.' }
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) { throw 'STOP: dedicated credential missing.' }

$names = @('APP_ENV','MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD',
           'AI_ENABLED','GROQ_API_KEY','PYTHONPATH')
$old = @{}
foreach ($name in $names) { $old[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$secure = $null; $pointer = [IntPtr]::Zero
try {
    $secure = ConvertTo-SecureString (Get-Content -LiteralPath $secretFile -Raw)
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $env:MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $env:APP_ENV = 'ai_snapshot_testing'
    $env:MYSQL_HOST = 'localhost'; $env:MYSQL_PORT = '3306'
    $env:MYSQL_DATABASE = $target
    $env:MYSQL_USER = 'lankapex_ai_snap_runtime'
    $env:AI_ENABLED = 'false'; $env:GROQ_API_KEY = ''
    $env:PYTHONPATH = Join-Path $root 'backend'

    & $python (Join-Path $root 'backend\scripts\check_ai_snapshot_test_runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'STOP: exact-target preflight failed; no tests started.' }
    if (-not $Execute) {
        Write-Output 'READ-ONLY PREFLIGHT COMPLETE; no fixture writes or tests executed'
        return
    }
    if ($ConfirmTarget -cne $target) { throw 'STOP: exact target confirmation differs.' }
    Push-Location (Join-Path $root 'backend')
    try {
        & $python -m pytest ai_snapshot_integration -q --tb=short -p no:cacheprovider --confcutdir=ai_snapshot_integration
        $testExit = $LASTEXITCODE
    } finally { Pop-Location }
    # Always re-prove the exact schema is empty after the test process exits.
    # The checker performs read-only metadata/count queries and never cleans up.
    & $python (Join-Path $root 'backend\scripts\check_ai_snapshot_test_runtime.py')
    $postflightExit = $LASTEXITCODE
    if ($postflightExit -ne 0) {
        throw 'STOP: post-test empty-schema verification failed; preserve state and evidence.'
    }
    if ($testExit -ne 0) {
        throw 'STOP: isolated integration tests failed; rollback and empty-schema postflight passed.'
    }
    Write-Output 'PASS: isolated AI snapshot MySQL integration tests completed with rollback cleanup'
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $old[$name], 'Process') }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
}
