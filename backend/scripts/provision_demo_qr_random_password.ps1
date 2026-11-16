param(
    [switch]$PreflightOnly,[switch]$Execute,
    [string]$ConfirmTarget,[string]$ConfirmAccount,[string]$DbaUser,
    [string]$ConfirmDbaAccount,[string]$TlsCa,
    [switch]$ConfirmCredentialCreation,[switch]$ConfirmSessionLength64,
    [switch]$AttestRawLoggingDisabled,[switch]$AttestNoSqlTracing,
    [switch]$AttestNoResultCapture,[switch]$AttestSecureOperatorSession,
    [switch]$AttestConfigurationFreeze,[switch]$AttestAccountDdlPause,
    [switch]$AttestBinaryAccountDdlReviewed
)
$ErrorActionPreference='Stop'
if (-not $Execute -and -not $PreflightOnly) {
    Write-Output 'PASS: offline random provisioning preparation; no I/O'; exit 0
}
$lease=$null; $code=1
try {
    if (($Execute -and $PreflightOnly) -or $ConfirmTarget -cne 'lankapex_demo_db' -or
        $ConfirmAccount -cne 'lankapex_demo_qr_migrator@localhost' -or
        $DbaUser -cnotmatch '^[A-Za-z0-9_]{1,32}$' -or
        $DbaUser -in @('lankapex_demo_app','lankapex_demo_qr_migrator') -or
        $ConfirmDbaAccount -cne ($DbaUser+'@localhost') -or -not $TlsCa -or
        -not $AttestRawLoggingDisabled -or -not $AttestNoSqlTracing -or
        -not $AttestNoResultCapture -or -not $AttestSecureOperatorSession -or
        -not $AttestConfigurationFreeze -or -not $AttestAccountDdlPause -or
        -not $AttestBinaryAccountDdlReviewed -or
        ($Execute -and (-not $ConfirmCredentialCreation -or -not $ConfirmSessionLength64))) {
        throw 'confirmation'
    }
    . (Join-Path $PSScriptRoot 'demo_qr_credential_storage.ps1')
    # Holds validated ancestor handles against replacement throughout child run.
    # Metadata only: no existing credential opened or decrypted.
    $lease=Assert-DemoQrCredentialStorage -Mode Create
    $python=Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'python' }
    $arguments=@((Join-Path $PSScriptRoot 'provision_demo_qr_random_password.py'),
        '--confirm-target',$ConfirmTarget,'--confirm-account',$ConfirmAccount,
        '--dba-user',$DbaUser,'--confirm-dba-account',$ConfirmDbaAccount,'--tls-ca',$TlsCa,
        '--attest-raw-logging-disabled','--attest-no-sql-tracing','--attest-no-result-capture',
        '--attest-secure-operator-session','--attest-configuration-freeze',
        '--attest-account-ddl-pause','--attest-binary-account-ddl-reviewed')
    if ($Execute) { $arguments+=@('--execute','--confirm-credential-creation','--confirm-session-length-64') }
    else { $arguments+='--preflight-only' }
    & $python -I @arguments
    if ($LASTEXITCODE -ne 0) { throw 'child_stop' }
    if ($Execute) {
        $final=Assert-DemoQrCredentialStorage -Path $lease.Credential -Mode Read
        Close-DemoQrStorageLease $final
    }
    Write-Output 'PASS: guarded random-password workflow complete; no migration performed'
    $code=0
} catch {
    Write-Output 'STOP: random-password wrapper security gate failed; preserve partial state; no retry'
} finally {
    if (Get-Command Close-DemoQrStorageLease -ErrorAction SilentlyContinue) { Close-DemoQrStorageLease $lease }
}
exit $code
