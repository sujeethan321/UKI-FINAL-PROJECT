param(
    [switch]$Execute,[switch]$PreflightOnly,
    [string]$ConfirmTarget,[string]$ConfirmRevision,[switch]$ConfirmWriterDdlPause,
    [switch]$ConfirmExistingMigratorPolicy,
    [string]$Baseline,[string]$BaselineSha256,
    [string]$BackupProof,[string]$BackupProofSha256,
    [string]$RehearsalProof,[string]$RehearsalProofSha256,
    [string]$PauseProof,[string]$PauseProofSha256
)
$ErrorActionPreference='Stop'
if (-not $Execute -and -not $PreflightOnly) {
    if ($ConfirmTarget -or $ConfirmRevision -or $ConfirmWriterDdlPause -or $ConfirmExistingMigratorPolicy -or $Baseline -or $BackupProof -or $RehearsalProof -or $PauseProof -or $BaselineSha256 -or $BackupProofSha256 -or $RehearsalProofSha256 -or $PauseProofSha256) {
        Write-Output 'STOP: populated-demo QR wrapper category=flags'; exit 1
    }
    Write-Output 'PASS: offline populated-demo QR preparation only; no evidence, credentials or database accessed'
    exit 0
}
if (($Execute -and $PreflightOnly) -or $ConfirmTarget -cne 'lankapex_demo_db' -or
    -not $ConfirmExistingMigratorPolicy -or
    ($Execute -and ($ConfirmRevision -cne '7b9e4d2c8a15' -or -not $ConfirmWriterDdlPause))) {
    Write-Output 'STOP: populated-demo QR wrapper category=confirmation'; exit 1
}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$private=Join-Path $root '.server-logs\private-demo-qr-migration'
$credential=$null; $storageLease=$null
$python=Join-Path $root 'backend\.venv\Scripts\python.exe'
$names=@('APP_ENV','MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD')
$previous=@{}
foreach ($name in $names) { $previous[$name]=[Environment]::GetEnvironmentVariable($name,'Process') }
$secure=$null; $pointer=[IntPtr]::Zero; $exitCode=1; $stage='prerequisite'
try {
    . (Join-Path $PSScriptRoot 'tamil_ai_private_acl.ps1')
    . (Join-Path $PSScriptRoot 'demo_qr_credential_storage.ps1')
    $operator=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    function Assert-QrPrivatePath {
        param([string]$Path)
        if (-not [IO.Path]::IsPathRooted($Path) -or [IO.Path]::GetFullPath($Path) -cne $Path) { throw 'path' }
        $cursor=$Path
        while ($cursor) {
            $item=Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'path' }
            $cursor=Split-Path -Parent $cursor
        }
        $acl=Get-Acl -LiteralPath $Path
        if (-not (Get-TamilAiPrivateAclAssessment $acl $operator).IsSecure -or
            $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $operator) { throw 'acl' }
    }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'python' }
    $stage='private_evidence'
    Assert-QrPrivatePath $private
    $evidence=@(
        @($Baseline,$BaselineSha256,'baseline'),
        @($BackupProof,$BackupProofSha256,'backup-proof'),
        @($RehearsalProof,$RehearsalProofSha256,'rehearsal-proof'),
        @($PauseProof,$PauseProofSha256,'pause-proof')
    )
    foreach ($entry in $evidence) {
        $path=$entry[0]; $digest=$entry[1]; $prefix=$entry[2]
        if (-not $path -or (Split-Path -Parent $path) -cne $private -or
            (Split-Path -Leaf $path) -cnotmatch ('^'+$prefix+'-[0-9a-f]{32}\.json$') -or
            $digest -cnotmatch '^[0-9a-f]{64}$') { throw 'evidence' }
        Assert-QrPrivatePath $path
        if ((Get-Item -LiteralPath $path).Length -gt 16777216) { throw 'evidence_size' }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $digest) { throw 'checksum' }
    }
    $backup=Get-Content -LiteralPath $BackupProof -Raw | ConvertFrom-Json
    if (-not $backup.dump_path -or (Split-Path -Parent $backup.dump_path) -cne $private -or
        (Split-Path -Leaf $backup.dump_path) -cnotmatch '^source-[0-9a-f]{32}\.sql$') { throw 'backup' }
    Assert-QrPrivatePath $backup.dump_path
    $stage='private_migrator_credential'
    $storageLease=Assert-DemoQrCredentialStorage -Mode Read
    $credential=$storageLease.Credential
    $secure=ConvertTo-SecureString (Get-Content -LiteralPath $credential -Raw)
    $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $env:APP_ENV='development'
    $env:MYSQL_HOST='localhost'; $env:MYSQL_PORT='3306'
    $env:MYSQL_DATABASE='lankapex_demo_db'
    $env:MYSQL_USER='lankapex_demo_migrator'
    $env:MYSQL_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $arguments=@(
        (Join-Path $PSScriptRoot 'upgrade_populated_demo_qr.py'),
        '--confirm-target','lankapex_demo_db',
        '--confirm-existing-migrator-policy',
        '--baseline',$Baseline,'--baseline-sha256',$BaselineSha256,
        '--backup',$BackupProof,'--backup-sha256',$BackupProofSha256,
        '--rehearsal',$RehearsalProof,'--rehearsal-sha256',$RehearsalProofSha256,
        '--pause',$PauseProof,'--pause-sha256',$PauseProofSha256
    )
    if ($Execute) { $arguments+=@('--execute','--confirm-revision','7b9e4d2c8a15','--confirm-writer-ddl-pause') }
    else { $arguments+='--preflight-only' }
    $stage='runner'
    & $python -I @arguments
    $exitCode=$LASTEXITCODE
} catch {
    if ($_.Exception.Message -ceq 'storage_preparation_required') { $stage='storage_preparation_required' }
    Write-Output ('STOP: populated-demo QR wrapper category='+$stage+'; preserve evidence; no retry; maintain writer/DDL pause')
    $exitCode=1
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
    if (Get-Command Close-DemoQrStorageLease -ErrorAction SilentlyContinue) { Close-DemoQrStorageLease $storageLease }
}
exit $exitCode
