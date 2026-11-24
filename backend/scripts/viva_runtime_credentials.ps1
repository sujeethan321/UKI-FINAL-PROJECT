# Functions only. Reuse reviewed held-ancestor and private-DACL policies.
. (Join-Path $PSScriptRoot 'demo_qr_credential_storage.ps1')
. (Join-Path $PSScriptRoot 'demo_credential_dacl.ps1')

function Get-VivaRuntimeContext {
    $base=Resolve-DemoQrStoragePaths
    $directory=Join-Path $base.Profile 'AppData\Local\LankaPex\VivaRuntimeSecrets'
    [pscustomobject]@{OperatorSid=$base.OperatorSid;Profile=$base.Profile;Directory=$directory}
}

function Get-VivaCredentialLease {
    param([ValidateSet('runtime','jwt')][string]$Kind,[ValidateSet('Read','Create','DirectoryPlan','Prepare')][string]$Mode='Read')
    $context=Get-VivaRuntimeContext
    $context | Add-Member NoteProperty Credential (Join-Path $context.Directory ($Kind+'.dpapi'))
    $provider={param($trace) $context}.GetNewClosure()
    Assert-DemoQrCredentialStorage -Path $context.Credential -Mode $Mode -ContextProvider $provider
}

function Read-VivaCredential {
    param($Lease,[ValidateSet('runtime','jwt')][string]$Kind)
    $stream=$null; $reader=$null; $secret=$null
    try {
        $stream=[IO.File]::Open($Lease.Credential,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
        if ($stream.Length -lt 20 -or $stream.Length -gt 32768) { throw 'credential_invalid' }
        $reader=[IO.StreamReader]::new($stream,[Text.Encoding]::UTF8)
        $secret=ConvertTo-SecureString ($reader.ReadToEnd()) -ErrorAction Stop
        if ($secret.Length -lt 1 -or ($Kind -eq 'jwt' -and $secret.Length -lt 64)) { throw 'credential_invalid' }
        return $secret
    } catch {
        if ($null -ne $secret) { $secret.Dispose() }
        throw 'credential_invalid'
    } finally {
        if ($null -ne $reader) { $reader.Dispose() }
        elseif ($null -ne $stream) { $stream.Dispose() }
    }
}

function Write-VivaCredential {
    param($Lease,[Security.SecureString]$Secret)
    $security=New-DemoDaclSecurity $Lease.OperatorSid
    $stream=$null
    try {
        # Windows PowerShell 5.1: atomically CREATE_NEW with protected operator/SYSTEM DACL.
        $stream=[IO.FileStream]::new($Lease.Credential,[IO.FileMode]::CreateNew,[Security.AccessControl.FileSystemRights]::Write,[IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough,$security)
        $bytes=[Text.UTF8Encoding]::new($false).GetBytes((ConvertFrom-SecureString $Secret))
        $stream.Write($bytes,0,$bytes.Length)
        $stream.Flush($true)
    } finally { if ($null -ne $stream) { $stream.Dispose() } }
}

function Initialize-VivaCredentialDirectory {
    $context=Get-VivaRuntimeContext
    if (Test-Path -LiteralPath $context.Directory) {
        $lease=Get-VivaCredentialLease runtime Prepare
        Close-DemoQrStorageLease $lease
        return
    }
    $plan=Get-VivaCredentialLease runtime DirectoryPlan
    try {
        foreach ($directory in $plan.MissingDirectories) {
            # New objects only; never repair/adopt an unsafe existing directory.
            New-DemoDaclBackupDirectory $directory $plan.OperatorSid
        }
        $verified=Get-VivaCredentialLease runtime Prepare
        Close-DemoQrStorageLease $verified
    } finally { Close-DemoQrStorageLease $plan }
}
