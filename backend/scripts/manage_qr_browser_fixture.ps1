param(
    [ValidateSet('Preflight','Reserve','Collect','CleanupReview','ReconcileFinal','DiagnoseFinal','DiagnoseBusiness','ReconcileFinalByMembership','FinalEvidencePreflight','PreserveFinalEvidence')][string]$Mode = 'Preflight',
    [ValidateSet('users_registered','business_created','business_approved','join_link_created','join_requested','join_approved')][string]$Stage,
    [string]$RunId,
    [switch]$Execute,
    [string]$ConfirmTarget,
    [int]$ConfirmAdminId,
    [switch]$ConfirmWriterPause
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$privateDir = Join-Path $root '.server-logs\private-test'
$runtimeFile = Join-Path $privateDir 'qr-test-runtime.dpapi'
$jwtFile = Join-Path $privateDir 'qr-browser-jwt.dpapi'
$tracker = Join-Path $root 'backend\scripts\qr_browser_fixture_tracking.py'

if ($Mode -in @('Reserve','Collect','PreserveFinalEvidence')) {
    if (-not $Execute -or $ConfirmTarget -cne 'lankapex_test_db' -or $ConfirmAdminId -ne 124671 -or -not $ConfirmWriterPause) {
        throw 'STOP: private-file creation requires execution, exact target/Admin and maintained writer pause confirmation.'
    }
} elseif ($Execute -or $ConfirmTarget -or $ConfirmAdminId -or $ConfirmWriterPause) {
    throw 'STOP: execution confirmations are valid only for Reserve or Collect.'
}
if ($Mode -eq 'Collect' -and (-not $RunId -or -not $Stage)) { throw 'STOP: exact run ID and stage are required.' }
if ($Mode -in @('CleanupReview','ReconcileFinal','DiagnoseFinal','DiagnoseBusiness','ReconcileFinalByMembership','FinalEvidencePreflight','PreserveFinalEvidence') -and -not $RunId) { throw 'STOP: exact run ID is required.' }
if ($Mode -eq 'Reserve' -and ($RunId -or $Stage)) { throw 'STOP: Reserve generates its own unpredictable run ID.' }
foreach ($file in @($python,$runtimeFile,$jwtFile,$tracker)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'STOP: guarded fixture prerequisite missing.' }
}

$names = @('APP_ENV','MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD','JWT_SECRET_KEY','PYTHONPATH')
$previous = @{}; foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
$dbSecure=$null; $jwtSecure=$null; $dbPointer=[IntPtr]::Zero; $jwtPointer=[IntPtr]::Zero
$ownerSecure=$null; $customerSecure=$null; $randomBytes=$null
try {
    $dbSecure = ConvertTo-SecureString (Get-Content -LiteralPath $runtimeFile -Raw)
    $jwtSecure = ConvertTo-SecureString (Get-Content -LiteralPath $jwtFile -Raw)
    $dbPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbSecure)
    $jwtPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($jwtSecure)
    $env:MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($dbPointer)
    $env:JWT_SECRET_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($jwtPointer)
    $env:APP_ENV='testing'; $env:MYSQL_HOST='localhost'; $env:MYSQL_PORT='3306'
    $env:MYSQL_DATABASE='lankapex_test_db'; $env:MYSQL_USER='lankapex_qr_test_runtime'
    $env:PYTHONPATH = Join-Path $root 'backend'
    & $python (Join-Path $root 'backend\scripts\check_qr_test_runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'STOP: exact QR test runtime preflight failed.' }

    if ($Mode -eq 'Preflight') {
        & $python $tracker preflight
        if ($LASTEXITCODE -ne 0) { throw 'STOP: fixture baseline preflight failed.' }
        Write-Output 'READ-ONLY FIXTURE PREFLIGHT COMPLETE; no private files or database records created'
        return
    }
    if ($Mode -eq 'Reserve') {
        $RunId = [guid]::NewGuid().ToString('N')
        $manifest = Join-Path $privateDir "qr-browser-fixture-$RunId.json"
        $ownerFile = Join-Path $privateDir "qr-browser-fixture-$RunId-owner.dpapi"
        $customerFile = Join-Path $privateDir "qr-browser-fixture-$RunId-customer.dpapi"
        foreach ($path in @($manifest,$ownerFile,$customerFile)) {
            if (Test-Path -LiteralPath $path) { throw 'STOP: generated private fixture path already exists.' }
        }
        $acl = New-Object Security.AccessControl.FileSecurity
        $acl.SetAccessRuleProtection($true,$false)
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($identity,'FullControl','Allow')))
        foreach ($path in @($manifest,$ownerFile,$customerFile)) {
            $stream = New-Object IO.FileStream($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
            $stream.Dispose(); Set-Acl -LiteralPath $path -AclObject $acl
        }
        $randomBytes = New-Object byte[] 48
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $rng.GetBytes($randomBytes); $ownerSecure = ConvertTo-SecureString ([Convert]::ToBase64String($randomBytes)) -AsPlainText -Force
            [Array]::Clear($randomBytes,0,$randomBytes.Length)
            $rng.GetBytes($randomBytes); $customerSecure = ConvertTo-SecureString ([Convert]::ToBase64String($randomBytes)) -AsPlainText -Force
        } finally { $rng.Dispose() }
        [IO.File]::WriteAllText($ownerFile,(ConvertFrom-SecureString $ownerSecure),[Text.Encoding]::ASCII)
        [IO.File]::WriteAllText($customerFile,(ConvertFrom-SecureString $customerSecure),[Text.Encoding]::ASCII)
        & $python $tracker reserve --run-id $RunId --output $manifest
        if ($LASTEXITCODE -ne 0) { throw 'STOP: reservation failed; preserve partial private evidence and do not retry.' }
        return
    }
    if ($RunId -cnotmatch '^[0-9a-f]{32}$') { throw 'STOP: exact lowercase 128-bit run ID required.' }
    if ($Mode -eq 'Collect') {
        $evidence = Join-Path $privateDir "qr-browser-fixture-evidence-$RunId-$Stage.json"
        if (Test-Path -LiteralPath $evidence) { throw 'STOP: stage evidence already exists; never overwrite it.' }
        $acl = New-Object Security.AccessControl.FileSecurity; $acl.SetAccessRuleProtection($true,$false)
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($identity,'FullControl','Allow')))
        $stream = New-Object IO.FileStream($evidence,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        $stream.Dispose(); Set-Acl -LiteralPath $evidence -AclObject $acl
        & $python $tracker collect --run-id $RunId --stage $Stage --output $evidence
        if ($LASTEXITCODE -ne 0) { throw 'STOP: evidence collection failed; preserve the reserved evidence file.' }
        return
    }
    if ($Mode -eq 'ReconcileFinal') {
        & $python $tracker reconcile-final --run-id $RunId
        if ($LASTEXITCODE -ne 0) { throw 'STOP: final-state reconciliation failed; no evidence was created.' }
        Write-Output 'READ-ONLY FINAL-STATE RECONCILIATION COMPLETE; no record or private file changed'
        return
    }
    if ($Mode -eq 'DiagnoseFinal') {
        & $python $tracker diagnose-final --run-id $RunId
        if ($LASTEXITCODE -ne 0) { throw 'STOP: sanitized final-state diagnostic reported a failed category; no evidence was created.' }
        Write-Output 'READ-ONLY FINAL-STATE DIAGNOSTIC COMPLETE; no record or private file changed'
        return
    }
    if ($Mode -eq 'DiagnoseBusiness') {
        & $python $tracker diagnose-business --run-id $RunId
        if ($LASTEXITCODE -ne 0) { throw 'STOP: ownership-first business diagnostic failed; no evidence was created.' }
        Write-Output 'READ-ONLY BUSINESS LOOKUP DIAGNOSTIC COMPLETE; no record or private file changed'
        return
    }
    if ($Mode -eq 'ReconcileFinalByMembership') {
        & $python $tracker reconcile-final-by-membership --run-id $RunId
        if ($LASTEXITCODE -ne 0) { throw 'STOP: membership-based final reconciliation failed; no evidence was created.' }
        Write-Output 'READ-ONLY MEMBERSHIP-BASED FINAL RECONCILIATION COMPLETE; no record or private file changed'
        return
    }
    if ($Mode -eq 'FinalEvidencePreflight') {
        & $python $tracker final-evidence-preflight --run-id $RunId
        if ($LASTEXITCODE -ne 0) { throw 'STOP: final evidence preflight failed; no file was created.' }
        Write-Output 'READ-ONLY FINAL EVIDENCE PREFLIGHT COMPLETE; no record or private file changed'
        return
    }
    if ($Mode -eq 'PreserveFinalEvidence') {
        # First pass occurs before reserving any output path. The Python write
        # pass repeats the complete reconciliation immediately before content.
        & $python $tracker final-evidence-preflight --run-id $RunId
        if ($LASTEXITCODE -ne 0) { throw 'STOP: fresh final evidence preflight failed; no file was created.' }
        $evidence = Join-Path $privateDir "qr-browser-fixture-final-evidence-$RunId.json"
        if (Test-Path -LiteralPath $evidence) { throw 'STOP: immutable final evidence already exists; never overwrite it.' }
        $acl = New-Object Security.AccessControl.FileSecurity; $acl.SetAccessRuleProtection($true,$false)
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($identity,'FullControl','Allow')))
        $stream = New-Object IO.FileStream($evidence,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        $stream.Dispose(); Set-Acl -LiteralPath $evidence -AclObject $acl
        & $python $tracker preserve-final-evidence --run-id $RunId --output $evidence
        if ($LASTEXITCODE -ne 0) { throw 'STOP: final evidence write or verification failed; preserve partial private evidence.' }
        return
    }
    & $python $tracker cleanup-review --run-id $RunId
    if ($LASTEXITCODE -ne 0) { throw 'STOP: exact-ID cleanup review failed; no cleanup authorized.' }
    Write-Output 'READ-ONLY CLEANUP REVIEW COMPLETE; no record or private file changed'
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
    foreach ($pointer in @($dbPointer,$jwtPointer)) { if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) } }
    foreach ($secure in @($dbSecure,$jwtSecure,$ownerSecure,$customerSecure)) { if ($null -ne $secure) { $secure.Dispose() } }
    if ($null -ne $randomBytes) { [Array]::Clear($randomBytes,0,$randomBytes.Length) }
}
