param([switch]$Execute, [string]$ConfirmTarget, [switch]$ConfirmWriterPause)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$privateDir = Join-Path $root '.server-logs\private-test'
$runtimeFile = Join-Path $privateDir 'qr-test-runtime.dpapi'
$oldPasswordFile = Join-Path $privateDir 'qr-browser-admin-password.dpapi'
$newPasswordFile = Join-Path $privateDir 'qr-browser-admin-recovery-password.dpapi'
$newManifestFile = Join-Path $privateDir 'qr-browser-admin-recovery-fixture.json'
if ($Execute) {
    if ($ConfirmTarget -cne 'lankapex_test_db' -or -not $ConfirmWriterPause) { throw 'STOP: exact target and maintained writer pause confirmation required.' }
} elseif ($ConfirmTarget -or $ConfirmWriterPause) { throw 'STOP: execution confirmations require -Execute.' }
foreach ($file in @($python, $runtimeFile, $oldPasswordFile)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'STOP: protected recovery prerequisite missing.' }
}
if ((Test-Path -LiteralPath $newPasswordFile) -or (Test-Path -LiteralPath $newManifestFile)) {
    throw 'STOP: recovery attempt already reserved; preserve files and review.'
}
$names = @('APP_ENV','MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD',
           'PYTHONPATH','QR_BOOTSTRAP_EMAIL','QR_BOOTSTRAP_PASSWORD','QR_BOOTSTRAP_RUN_ID')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$runtimeSecure = $null; $runtimePointer = [IntPtr]::Zero
$oldSecure = $null; $oldPointer = [IntPtr]::Zero
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
    if ($LASTEXITCODE -ne 0) { throw 'STOP: exact QR runtime preflight failed.' }
    & $python (Join-Path $root 'backend\scripts\recover_qr_test_admin.py')
    if ($LASTEXITCODE -ne 0) { throw 'STOP: read-only recovery evidence or zero-row preflight failed.' }
    if (-not $Execute) {
        Write-Output 'READ-ONLY QR ADMIN RECOVERY PREFLIGHT COMPLETE; no files or database records created'
        return
    }
    $oldSecure = ConvertTo-SecureString (Get-Content -LiteralPath $oldPasswordFile -Raw)
    $oldPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($oldSecure)
    $runId = [guid]::NewGuid().ToString('N')
    $email = 'qr-browser-admin-' + [guid]::NewGuid().ToString('N') + '@lankapex-test.example.com'
    $randomBytes = New-Object byte[] 48
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($randomBytes) } finally { $rng.Dispose() }
    $newPassword = [Convert]::ToBase64String($randomBytes)
    if ([string]::Equals($newPassword, [Runtime.InteropServices.Marshal]::PtrToStringBSTR($oldPointer), [StringComparison]::Ordinal)) {
        throw 'STOP: replacement credential matches failed credential.'
    }
    $adminSecure = ConvertTo-SecureString -String $newPassword -AsPlainText -Force
    $cipher = ConvertFrom-SecureString -SecureString $adminSecure
    $acl = New-Object Security.AccessControl.FileSecurity
    $acl.SetAccessRuleProtection($true, $false)
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'Allow')
    $acl.AddAccessRule($rule)
    foreach ($file in @($newPasswordFile, $newManifestFile)) {
        $stream = New-Object IO.FileStream($file, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $stream.Dispose()
        Set-Acl -LiteralPath $file -AclObject $acl
    }
    [IO.File]::WriteAllText($newPasswordFile, $cipher, [Text.Encoding]::ASCII)
    $reservation = @{ state='reserved'; database='lankapex_test_db'; account='lankapex_qr_test_runtime@localhost';
                      email=$email; run_id=$runId; user_id=$null; audit_id=$null }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($newManifestFile, ($reservation | ConvertTo-Json -Compress), $utf8NoBom)
    $adminPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($adminSecure)
    $env:QR_BOOTSTRAP_EMAIL = $email
    $env:QR_BOOTSTRAP_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($adminPointer)
    $env:QR_BOOTSTRAP_RUN_ID = $runId
    & $python (Join-Path $root 'backend\scripts\recover_qr_test_admin.py') --execute --confirm-target lankapex_test_db --confirm-writer-pause
    if ($LASTEXITCODE -ne 0) { throw 'STOP: recovery failed or commit uncertain; preserve both attempts.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    foreach ($pointer in @($runtimePointer,$oldPointer,$adminPointer)) {
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    }
    foreach ($secure in @($runtimeSecure,$oldSecure,$adminSecure)) { if ($null -ne $secure) { $secure.Dispose() } }
    if ($null -ne $randomBytes) { [Array]::Clear($randomBytes, 0, $randomBytes.Length) }
    $newPassword = $null
}
