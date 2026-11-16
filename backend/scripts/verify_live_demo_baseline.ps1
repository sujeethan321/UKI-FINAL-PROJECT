# Operator-only read-only capture and comparison. Never overwrites a manifest.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$secretFile = Join-Path $root '.server-logs\private-demo\demo-migrator.dpapi'
$private = Join-Path $root '.server-logs\private-demo-backups'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Backend Python environment missing.' }
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) { throw 'Private demo migrator credential missing.' }
if (-not (Test-Path -LiteralPath $private -PathType Container)) { throw 'Private backup directory missing.' }
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffffffZ')
$current = Join-Path $private ('lankapex_demo_live_' + $stamp + '_' + [guid]::NewGuid().ToString('N') + '.json')
if (Test-Path -LiteralPath $current) { throw 'Verification manifest already exists.' }
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
    & $python (Join-Path $root 'backend\scripts\capture_demo_baseline.py') --database lankapex_demo_db --output $current
    if ($LASTEXITCODE -ne 0) { throw 'Read-only demo baseline capture stopped.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
}
& $python (Join-Path $root 'backend\scripts\compare_demo_baseline.py') --current $current
if ($LASTEXITCODE -ne 0) { throw 'Demo baseline mismatch; preserve private evidence.' }
Write-Output 'PASS: live demo baseline matches pinned backup; private manifest retained outside Git'
