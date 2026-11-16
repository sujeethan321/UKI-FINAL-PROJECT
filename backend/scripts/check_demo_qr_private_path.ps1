# Read-only ACL metadata validator shared by Python and the operator wrapper.
param([string]$Path)
$ErrorActionPreference='Stop'
$storageLease=$null
try {
    $root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    $private=Join-Path $root '.server-logs\private-demo-qr-migration'
    . (Join-Path $PSScriptRoot 'demo_qr_credential_storage.ps1')
    $credential=(Resolve-DemoQrStoragePaths).Credential
    if (-not $Path -or -not [IO.Path]::IsPathRooted($Path) -or
        [IO.Path]::GetFullPath($Path) -cne $Path -or
        ($Path -cne $private -and (Split-Path -Parent $Path) -cne $private -and $Path -cne $credential)) { throw 'path' }
    if ($Path -ceq $credential) {
        $storageLease=Assert-DemoQrCredentialStorage -Path $Path -Mode Read
        Write-Output 'PASS'
        exit 0
    }
    . (Join-Path $PSScriptRoot 'tamil_ai_private_acl.ps1')
    $operator=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $cursor=$Path
    while ($cursor) {
        if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'path' }
        $cursor=Split-Path -Parent $cursor
    }
    $acl=Get-Acl -LiteralPath $Path
    if (-not (Get-TamilAiPrivateAclAssessment $acl $operator).IsSecure -or
        $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $operator) { throw 'acl' }
    Write-Output 'PASS'
    exit 0
} catch {
    Write-Output 'STOP: private migration path metadata differs'
    exit 1
} finally { if (Get-Command Close-DemoQrStorageLease -ErrorAction SilentlyContinue) { Close-DemoQrStorageLease $storageLease } }
