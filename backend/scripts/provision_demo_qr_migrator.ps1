param(
    [switch]$Execute,
    [string]$ConfirmTarget,
    [string]$ConfirmAccount,
    [switch]$ConfirmCredentialCreation,
    [switch]$ConfirmAccountDdlPause,
    [switch]$ConfirmSecureLogging,
    [string]$DbaUser
)
$ErrorActionPreference='Stop'
if (-not $Execute) {
    Write-Output 'PASS: offline QR migrator provisioning preparation; no credentials, files or database accessed'
    exit 0
}
if ($ConfirmTarget -cne 'lankapex_demo_db' -or
    $ConfirmAccount -cne 'lankapex_demo_qr_migrator@localhost' -or
    -not $ConfirmCredentialCreation -or -not $ConfirmAccountDdlPause -or -not $ConfirmSecureLogging -or
    $DbaUser -cnotmatch '^[A-Za-z0-9_]{1,32}$' -or
    $DbaUser -in @('lankapex_demo_app','lankapex_demo_qr_migrator')) {
    Write-Output 'STOP: QR migrator provisioning category=confirmation'; exit 1
}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$credential=$null; $storageLease=$null; $credentialLease=$null
$python=Join-Path $root 'backend\.venv\Scripts\python.exe'
$previous=[Environment]::GetEnvironmentVariable('LANKAPEX_QR_PROVISION_PASSWORD','Process')
$rng=$null; $secure=$null; $check=$null; $stream=$null
$pointer=[IntPtr]::Zero; $bytes=$null; $cipherBytes=$null; $plain=$null
$stage='prerequisite'; $exitCode=1
try {
    . (Join-Path $PSScriptRoot 'tamil_ai_private_acl.ps1')
    . (Join-Path $PSScriptRoot 'demo_qr_credential_storage.ps1')
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'python' }
    $stage='credential_storage'
    $storageLease=Assert-DemoQrCredentialStorage -Mode Create
    $credential=$storageLease.Credential; $operator=$storageLease.OperatorSid
    $stage='credential_preparation'
    $bytes=New-Object byte[] 32
    $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $plain=[Convert]::ToBase64String($bytes)
    $secure=ConvertTo-SecureString -String $plain -AsPlainText -Force
    $plain=$null
    # ConvertFrom-SecureString without -Key uses Windows CurrentUser DPAPI.
    $cipher=ConvertFrom-SecureString -SecureString $secure
    $cipherBytes=[Text.Encoding]::UTF8.GetBytes($cipher)
    $cipher=$null
    $stage='exclusive_credential_creation'
    # Supply a DACL at exclusive creation, so even non-inheritable parent rules
    # cannot cause a transient token-default ACL. No SACL/owner data is supplied.
    $fileSecurity=New-Object Security.AccessControl.FileSecurity
    $fileSecurity.SetAccessRuleProtection($true,$false)
    foreach ($sid in @($operator,'S-1-5-18')) {
        $identity=New-Object Security.Principal.SecurityIdentifier($sid)
        $rule=New-Object Security.AccessControl.FileSystemAccessRule($identity,'FullControl','Allow')
        [void]$fileSecurity.AddAccessRule($rule)
    }
    $stream=New-Object IO.FileStream($credential,[IO.FileMode]::CreateNew,
        [Security.AccessControl.FileSystemRights]::FullControl,[IO.FileShare]::None,
        4096,[IO.FileOptions]::None,$fileSecurity)
    $stream.Write($cipherBytes,0,$cipherBytes.Length)
    $stream.Flush($true)
    $stream.Dispose(); $stream=$null
    $stage='credential_dacl'
    Set-TamilAiPrivateFileDaclOnly $credential $operator
    $credentialLease=Assert-DemoQrCredentialStorage -Path $credential -Mode Read
    $stage='credential_decryptability'
    $check=ConvertTo-SecureString (Get-Content -LiteralPath $credential -Raw)
    $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($check)
    $plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    if ($plain -cnotmatch '^[A-Za-z0-9+/]{43}=$') { throw 'credential' }
    $env:LANKAPEX_QR_PROVISION_PASSWORD=$plain
    $plain=$null
    $stage='account_provisioning'
    $arguments=@((Join-Path $PSScriptRoot 'provision_demo_qr_migrator.py'),
        '--execute','--confirm-target','lankapex_demo_db',
        '--confirm-account','lankapex_demo_qr_migrator@localhost',
        '--confirm-account-ddl-pause','--confirm-secure-logging','--dba-user',$DbaUser)
    & $python -I @arguments
    if ($LASTEXITCODE -ne 0) { throw 'provisioning' }
    $stage='final_credential_dacl'
    $finalLease=Assert-DemoQrCredentialStorage -Path $credential -Mode Read
    Close-DemoQrStorageLease $finalLease
    Write-Output 'PASS: QR migrator provisioning and protected credential checks complete; no migration performed'
    $exitCode=0
} catch {
    if ($_.Exception.Message -ceq 'storage_preparation_required') { $stage='storage_preparation_required' }
    Write-Output ('STOP: QR migrator wrapper category='+$stage+'; preserve any created credential/account; no retry or automatic repair')
} finally {
    [Environment]::SetEnvironmentVariable('LANKAPEX_QR_PROVISION_PASSWORD',$previous,'Process')
    $plain=$null
    if ($null -ne $stream) { $stream.Dispose() }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $check) { $check.Dispose() }
    if ($null -ne $secure) { $secure.Dispose() }
    if ($null -ne $rng) { $rng.Dispose() }
    if ($null -ne $bytes) { [Array]::Clear($bytes,0,$bytes.Length) }
    if ($null -ne $cipherBytes) { [Array]::Clear($cipherBytes,0,$cipherBytes.Length) }
    if (Get-Command Close-DemoQrStorageLease -ErrorAction SilentlyContinue) {
        Close-DemoQrStorageLease $credentialLease
        Close-DemoQrStorageLease $storageLease
    }
}
exit $exitCode
