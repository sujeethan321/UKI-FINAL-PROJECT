param(
    [switch]$Execute,
    [string]$ConfirmTarget,
    [switch]$ConfirmWriterPause
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$runtimeFile = Join-Path $root '.server-logs\private-test\qr-test-runtime.dpapi'
$privateDir = Join-Path $root '.server-logs\private-test'
$passwordFile = Join-Path $privateDir 'qr-browser-admin-password.dpapi'
$manifestFile = Join-Path $privateDir 'qr-browser-admin-fixture.json'
if ($Execute) {
    if ($ConfirmTarget -cne 'lankapex_test_db' -or -not $ConfirmWriterPause) { throw 'STOP: exact target and maintained writer pause confirmation required.' }
} elseif ($ConfirmTarget -or $ConfirmWriterPause) { throw 'STOP: execution confirmations require -Execute.' }
foreach ($file in @($python, $runtimeFile)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'STOP: private test runtime prerequisite missing.' }
}
if ((Test-Path -LiteralPath $passwordFile) -or (Test-Path -LiteralPath $manifestFile)) {
    throw 'STOP: Admin fixture credential or manifest already exists; preserve evidence and review.'
}
$names = @('APP_ENV','MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD',
           'PYTHONPATH','QR_BOOTSTRAP_EMAIL','QR_BOOTSTRAP_PASSWORD','QR_BOOTSTRAP_RUN_ID')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$runtimeSecure = $null; $runtimePointer = [IntPtr]::Zero
$adminSecure = $null; $adminPointer = [IntPtr]::Zero
$randomBytes = $null
try {
    $runtimeSecure = ConvertTo-SecureString (Get-Content -LiteralPath $runtimeFile -Raw)
    $runtimePointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($runtimeSecure)
    $env:MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($runtimePointer)
    $env:APP_ENV = 'testing'
    $env:MYSQL_HOST = 'localhost'
    $env:MYSQL_PORT = '3306'
    $env:MYSQL_DATABASE = 'lankapex_test_db'
    $env:MYSQL_USER = 'lankapex_qr_test_runtime'
    $env:PYTHONPATH = Join-Path $root 'backend'
    & $python (Join-Path $root 'backend\scripts\check_qr_test_runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'STOP: exact test runtime preflight failed.' }
    & $python (Join-Path $root 'backend\scripts\bootstrap_qr_test_admin.py')
    if ($LASTEXITCODE -ne 0) { throw 'STOP: Admin zero-record preflight failed.' }
    if (-not $Execute) {
        Write-Output 'READ-ONLY ADMIN BOOTSTRAP PREFLIGHT COMPLETE; no account created'
        return
    }
    # Reserve both paths with CreateNew. A partial execution is evidence, not a retry target.
    $runId = [guid]::NewGuid().ToString('N')
    $email = 'qr-browser-admin-' + [guid]::NewGuid().ToString('N') + '@lankapex-test.example.com'
    $randomBytes = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($randomBytes)
    $adminSecure = ConvertTo-SecureString -String ([Convert]::ToBase64String($randomBytes)) -AsPlainText -Force
    $cipher = ConvertFrom-SecureString -SecureString $adminSecure
    $acl = New-Object Security.AccessControl.FileSecurity
    $acl.SetAccessRuleProtection($true, $false)
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'Allow')
    $acl.AddAccessRule($rule)
    foreach ($file in @($passwordFile, $manifestFile)) {
        $stream = New-Object IO.FileStream($file, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $stream.Dispose()
        Set-Acl -LiteralPath $file -AclObject $acl
    }
    [IO.File]::WriteAllText($passwordFile, $cipher, [Text.Encoding]::ASCII)
    $reservation = @{ state='reserved'; database='lankapex_test_db'; account='lankapex_qr_test_runtime@localhost';
                      email=$email; run_id=$runId; user_id=$null; audit_id=$null }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($manifestFile, ($reservation | ConvertTo-Json -Compress), $utf8NoBom)
    $adminPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($adminSecure)
    $env:QR_BOOTSTRAP_EMAIL = $email
    $env:QR_BOOTSTRAP_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($adminPointer)
    $env:QR_BOOTSTRAP_RUN_ID = $runId
    & $python (Join-Path $root 'backend\scripts\bootstrap_qr_test_admin.py') --execute --confirm-target lankapex_test_db --confirm-writer-pause
    if ($LASTEXITCODE -ne 0) { throw 'STOP: Admin bootstrap failed or commit status uncertain; preserve private files.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    if ($runtimePointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($runtimePointer) }
    if ($adminPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($adminPointer) }
    if ($null -ne $runtimeSecure) { $runtimeSecure.Dispose() }
    if ($null -ne $adminSecure) { $adminSecure.Dispose() }
    if ($null -ne $randomBytes) { [Array]::Clear($randomBytes, 0, $randomBytes.Length) }
}
