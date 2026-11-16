# Internal stdin-only handoff. Never accepts a password in argv or environment.
param([switch]$StoreFromPrivatePipe,[switch]$MetadataOnly,[string]$ConfirmAccount)
$ErrorActionPreference='Stop'
if ($MetadataOnly -and -not $StoreFromPrivatePipe -and $ConfirmAccount -ceq 'lankapex_demo_qr_migrator@localhost') {
    $metadataLease=$null
    try {
        . (Join-Path $PSScriptRoot 'demo_qr_credential_storage.ps1')
        $metadataLease=Assert-DemoQrCredentialStorage -Mode Create
        Write-Output 'PASS: absent credential and protected storage verified'
        exit 0
    } catch { Write-Output 'STOP: credential storage metadata unverified'; exit 1 }
    finally { if (Get-Command Close-DemoQrStorageLease -ErrorAction SilentlyContinue) { Close-DemoQrStorageLease $metadataLease } }
}
if ($MetadataOnly -or -not $StoreFromPrivatePipe -or $ConfirmAccount -cne 'lankapex_demo_qr_migrator@localhost') {
    Write-Output 'STOP: private pipe storage confirmation required'; exit 1
}
$lease=$null; $fileLease=$null; $stream=$null; $secure=$null; $check=$null
$bytes=$null; $plain=$null; $cipher=$null; $roundtrip=$null
$pointer=[IntPtr]::Zero; $code=1
try {
    if (-not [Console]::IsInputRedirected) { throw 'private_pipe_required' }
    . (Join-Path $PSScriptRoot 'demo_qr_credential_storage.ps1')
    $lease=Assert-DemoQrCredentialStorage -Mode Create
    # Exact length is bounded before conversion. No line terminator is appended.
    $plain=[Console]::In.ReadToEnd()
    if ($plain.Length -ne 64 -or $plain -cmatch '[^1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ,\.\-;:_+*!%&/(){}\[\]<>@]') {
        throw 'sensitive_input_shape'
    }
    $secure=ConvertTo-SecureString -String $plain -AsPlainText -Force
    $cipher=ConvertFrom-SecureString -SecureString $secure
    $check=ConvertTo-SecureString -String $cipher
    $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($check)
    $roundtrip=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    if ($roundtrip -cne $plain) { throw 'dpapi_roundtrip' }
    $plain=$null; $roundtrip=$null
    $bytes=[Text.Encoding]::UTF8.GetBytes($cipher); $cipher=$null
    $security=New-Object Security.AccessControl.FileSecurity
    $security.SetAccessRuleProtection($true,$false)
    $operatorIdentity=New-Object Security.Principal.SecurityIdentifier($lease.OperatorSid)
    $security.SetOwner($operatorIdentity)
    foreach ($sid in @($lease.OperatorSid,'S-1-5-18')) {
        $identity=New-Object Security.Principal.SecurityIdentifier($sid)
        $rule=New-Object Security.AccessControl.FileSystemAccessRule($identity,'FullControl','Allow')
        [void]$security.AddAccessRule($rule)
    }
    # DACL-only at exclusive creation: no inherited exposure, SACL or Set-Acl.
    $stream=New-Object IO.FileStream($lease.Credential,[IO.FileMode]::CreateNew,
        [Security.AccessControl.FileSystemRights]::FullControl,[IO.FileShare]::None,
        4096,[IO.FileOptions]::None,$security)
    $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true)
    $stream.Dispose(); $stream=$null
    $fileLease=Assert-DemoQrCredentialStorage -Path $lease.Credential -Mode Read
    $code=0
} catch {
    # Never render ErrorRecord, exception message, input or ciphertext.
    $code=1
} finally {
    $plain=$null; $roundtrip=$null; $cipher=$null
    if ($null -ne $stream) { $stream.Dispose() }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $check) { $check.Dispose() }
    if ($null -ne $secure) { $secure.Dispose() }
    if ($null -ne $bytes) { [Array]::Clear($bytes,0,$bytes.Length) }
    if (Get-Command Close-DemoQrStorageLease -ErrorAction SilentlyContinue) {
        Close-DemoQrStorageLease $fileLease; Close-DemoQrStorageLease $lease
    }
}
if ($code -eq 0) { Write-Output 'PASS: server-generated credential stored and verified' }
else { Write-Output 'STOP: credential storage failed; preserve account and any partial file' }
exit $code
