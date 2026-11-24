# Dedicated operator launcher. Preflight is read-only; server startup requires release.
[CmdletBinding()]
param([switch]$PreflightOnly,[switch]$ConfirmDbaHeadAttestation,[switch]$ConfirmMaintenanceReleased)
. (Join-Path $PSScriptRoot 'viva_runtime_credentials.ps1')
function Invoke-VivaPython {
    param([string]$Python,[string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'child_failed' }
}
function Invoke-VivaRuntime {
param([switch]$PreflightOnly,[switch]$ConfirmDbaHeadAttestation,[switch]$ConfirmMaintenanceReleased)
$ErrorActionPreference='Stop'
$stage='CONFIRMATION'; $previous=@{}; $leases=@(); $secrets=@(); $pointers=@(); $locationPushed=$false
try {
    if ($PSVersionTable.PSEdition -ne 'Desktop' -or -not $ConfirmDbaHeadAttestation) { throw 'confirmation' }
    if (-not $PreflightOnly -and -not $ConfirmMaintenanceReleased) { throw 'freeze_active' }
    $repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $python=Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'python_missing' }
    $configuration=@{
        LANKAPEX_VIVA_RUNTIME='true'; APP_ENV='development'; MYSQL_HOST='127.0.0.1'; MYSQL_PORT='3306';
        MYSQL_DATABASE='lankapex_viva_db'; MYSQL_USER='lankapex_viva_runtime'; MYSQL_TLS_MODE='local_viva_required';
        MYSQL_SSL_CA='C:\Program Files\LankaPex-TLS-Trust\ca.pem'; APP_DEBUG='false'; LOG_LEVEL='INFO'; RATE_LIMIT_MODE='local';
        ADDRESS_BOOK_ENABLED='true'; ADDRESS_CHECKOUT_ENABLED='true'; SUPPORT_ENABLED='true'; DRIVER_FINANCE_ENABLED='true';
        ADDRESS_DBA_ATTESTED_REVISION='d15a8c902e64'; SUPPORT_DBA_ATTESTED_REVISION='d15a8c902e64'; DRIVER_FINANCE_DBA_ATTESTED_REVISION='d15a8c902e64';
        AI_ENABLED='false'; STRIPE_SANDBOX_ENABLED='false'; CORS_ALLOWED_ORIGINS='http://127.0.0.1:5173,http://127.0.0.1:5176'; ALLOWED_HOSTS='127.0.0.1,localhost'
    }
    $forbidden=@('LANKAPEX_DISABLE_DOTENV','GROQ_API_KEY','STRIPE_TEST_SECRET_KEY','STRIPE_WEBHOOK_SECRET','DATABASE_URL','SQLALCHEMY_DATABASE_URI','MYSQL_PASSWORD','JWT_SECRET_KEY')
    $stage='INHERITED_CONFIGURATION'
    foreach ($name in $forbidden) {
        if ($null -ne [Environment]::GetEnvironmentVariable($name,'Process')) { throw 'inherited_conflict' }
    }
    foreach ($name in $configuration.Keys) {
        $value=[Environment]::GetEnvironmentVariable($name,'Process')
        if ($null -ne $value -and $value -cne $configuration[$name]) { throw 'inherited_conflict' }
    }
    # Explicitly snapshot every variable this launcher changes, including absent values.
    foreach ($name in @($configuration.Keys)+@('MYSQL_PASSWORD','JWT_SECRET_KEY')) {
        $previous[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
    }
    $stage='PRIVATE_CREDENTIALS'
    foreach ($kind in @('runtime','jwt')) {
        $lease=Get-VivaCredentialLease $kind Read; $leases+=,$lease
        $secure=Read-VivaCredential $lease $kind; $secrets+=,$secure
        $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure); $pointers+=,$pointer
        $name=if ($kind -eq 'runtime') { 'MYSQL_PASSWORD' } else { 'JWT_SECRET_KEY' }
        [Environment]::SetEnvironmentVariable($name,[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer),'Process')
    }
    foreach ($name in $configuration.Keys) { [Environment]::SetEnvironmentVariable($name,$configuration[$name],'Process') }
    Push-Location (Join-Path $repoRoot 'backend'); $locationPushed=$true
    $stage='READ_ONLY_PREFLIGHT'
    Invoke-VivaPython $python @('-B','scripts/check_viva_backend.py')
    if ($PreflightOnly) {
        Write-Output 'VIVA_RUNTIME=PASS_PREFLIGHT_ONLY; SERVER_STARTED=no; FREEZE_UNCHANGED=yes'
    } else {
        $stage='UVICORN'
        Invoke-VivaPython $python @('-B','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001','--log-level','info','--no-access-log')
    }
    return 0
} catch {
    Write-Output ('VIVA_RUNTIME=STOP; STAGE='+$stage+'; DETAILS=REDACTED; NO_AUTOMATIC_RETRY')
    return 1
} finally {
    foreach ($name in $previous.Keys) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
    if ($locationPushed) { Pop-Location }
    foreach ($pointer in $pointers) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    foreach ($secret in $secrets) { $secret.Dispose() }
    foreach ($lease in $leases) { Close-DemoQrStorageLease $lease }
}
}
if ($MyInvocation.InvocationName -ne '.') {
    $result=@(Invoke-VivaRuntime -PreflightOnly:$PreflightOnly -ConfirmDbaHeadAttestation:$ConfirmDbaHeadAttestation -ConfirmMaintenanceReleased:$ConfirmMaintenanceReleased)
    $code=$result[-1]
    $result | Select-Object -SkipLast 1 | Write-Output
    exit $code
}
