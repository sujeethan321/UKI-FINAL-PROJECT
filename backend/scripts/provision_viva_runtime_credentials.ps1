# Operator-only, local Windows credential provisioning. No MySQL operations.
[CmdletBinding()]
param([switch]$ConfirmCredentialProvisioning)
$ErrorActionPreference='Stop'
$stage='CONFIRMATION'; $lease=$null; $secret=$null; $rng=$null; $random=$null
try {
    if (-not $ConfirmCredentialProvisioning -or $PSVersionTable.PSEdition -ne 'Desktop') { throw 'confirmation' }
    . (Join-Path $PSScriptRoot 'viva_runtime_credentials.ps1')
    $stage='PRIVATE_DIRECTORY'
    Initialize-VivaCredentialDirectory
    foreach ($kind in @('runtime','jwt')) {
        $stage='EXISTING_CREDENTIAL_VERIFICATION'
        $lease=Get-VivaCredentialLease $kind Prepare
        if (Test-Path -LiteralPath $lease.Credential) {
            Close-DemoQrStorageLease $lease; $lease=$null
            $lease=Get-VivaCredentialLease $kind Read
            $secret=Read-VivaCredential $lease $kind
            $secret.Dispose(); $secret=$null
            Close-DemoQrStorageLease $lease; $lease=$null
            continue
        }
        Close-DemoQrStorageLease $lease; $lease=$null
        $lease=Get-VivaCredentialLease $kind Create
        $stage='SECURE_INPUT_OR_GENERATION'
        if ($kind -eq 'runtime') {
            $secret=Read-Host 'Existing lankapex_viva_runtime password (never reset)' -AsSecureString
            if ($secret.Length -lt 1) { throw 'empty' }
        } else {
            $random=New-Object byte[] 64
            $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
            $rng.GetBytes($random)
            $secret=New-Object Security.SecureString
            foreach ($value in $random) {
                foreach ($character in $value.ToString('x2').ToCharArray()) { $secret.AppendChar($character) }
            }
            $secret.MakeReadOnly()
            [Array]::Clear($random,0,$random.Length); $random=$null
            $rng.Dispose(); $rng=$null
        }
        $stage='EXCLUSIVE_DPAPI_WRITE'
        Write-VivaCredential $lease $secret
        $secret.Dispose(); $secret=$null
        Close-DemoQrStorageLease $lease; $lease=$null
        $stage='WRITTEN_CREDENTIAL_VERIFICATION'
        $lease=Get-VivaCredentialLease $kind Read
        $secret=Read-VivaCredential $lease $kind
        $secret.Dispose(); $secret=$null
        Close-DemoQrStorageLease $lease; $lease=$null
    }
    Write-Output 'VIVA_CREDENTIALS=PASS; DPAPI=CurrentUser; EXISTING_VALID_SECRETS=PRESERVED; DATABASE_OPERATIONS=0'
} catch {
    Write-Output ('VIVA_CREDENTIALS=STOP; STAGE='+$stage+'; DETAILS=REDACTED; PRESERVE_NO_RETRY_NO_CLEANUP')
    exit 1
} finally {
    if ($null -ne $secret) { $secret.Dispose() }
    if ($null -ne $random) { [Array]::Clear($random,0,$random.Length) }
    if ($null -ne $rng) { $rng.Dispose() }
    if ($null -ne $lease) { Close-DemoQrStorageLease $lease }
}
