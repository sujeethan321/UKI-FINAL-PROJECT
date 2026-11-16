# Run only under the Windows account that owns the QR test-runtime DPAPI files.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$dbFile = Join-Path $root '.server-logs\private-test\qr-test-runtime.dpapi'
$jwtFile = Join-Path $root '.server-logs\private-test\qr-browser-jwt.dpapi'
foreach ($file in @($python, $dbFile, $jwtFile)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'STOP: private QR inventory prerequisite missing.' }
}
$names = @('APP_ENV', 'MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_DATABASE', 'MYSQL_USER',
           'MYSQL_PASSWORD', 'JWT_SECRET_KEY', 'PYTHONPATH')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$dbSecure = $null; $jwtSecure = $null
$dbPointer = [IntPtr]::Zero; $jwtPointer = [IntPtr]::Zero
try {
    $dbSecure = ConvertTo-SecureString (Get-Content -LiteralPath $dbFile -Raw)
    $jwtSecure = ConvertTo-SecureString (Get-Content -LiteralPath $jwtFile -Raw)
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
    & $python (Join-Path $root 'backend\scripts\check_qr_test_runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'STOP: exact QR runtime preflight failed; no inventory queried.' }
    & $python (Join-Path $root 'backend\scripts\inventory_qr_browser_test_db.py')
    if ($LASTEXITCODE -ne 0) { throw 'STOP: read-only QR inventory failed.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    if ($dbPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($dbPointer) }
    if ($jwtPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($jwtPointer) }
    if ($null -ne $dbSecure) { $dbSecure.Dispose() }
    if ($null -ne $jwtSecure) { $jwtSecure.Dispose() }
}
