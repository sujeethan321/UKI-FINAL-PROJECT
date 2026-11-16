param(
    [ValidateSet('Preflight','Reserve','Create','Verify','CleanupReview','Cleanup')][string]$Mode='Preflight',
    [string]$RunId='', [switch]$Execute, [string]$ConfirmTarget='',
    [switch]$ConfirmWriterPause, [switch]$ConfirmEmpty
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python=Join-Path $root 'backend\.venv\Scripts\python.exe'
$privateDir=Join-Path $root '.server-logs\private-ai-tests'
$dbFile=Join-Path $privateDir 'ai-snapshot-test-runtime.dpapi'
$target='lankapex_ai_snapshot_test_db'
$script=Join-Path $root 'backend\scripts\tamil_ai_browser_fixture.py'
$aclScript=Join-Path $root 'backend\scripts\tamil_ai_private_acl.ps1'
foreach($path in @($python,$dbFile,$script,$aclScript)){if(-not(Test-Path -LiteralPath $path -PathType Leaf)){throw 'STOP: guarded fixture prerequisite missing.'}}
. $aclScript

$names=@('APP_ENV','MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD','AI_ENABLED','GROQ_API_KEY','PYTHONPATH','TAMIL_AI_FIXTURE_OWNER_PASSWORD')
$old=@{};foreach($name in $names){$old[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
$dbSecure=$null;$ownerSecure=$null;$dbPointer=[IntPtr]::Zero;$ownerPointer=[IntPtr]::Zero
$operatorSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
try {
    $dbSecure=ConvertTo-SecureString (Get-Content -LiteralPath $dbFile -Raw)
    $dbPointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbSecure)
    $env:MYSQL_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($dbPointer)
    $env:APP_ENV='ai_snapshot_testing';$env:MYSQL_HOST='localhost';$env:MYSQL_PORT='3306'
    $env:MYSQL_DATABASE=$target;$env:MYSQL_USER='lankapex_ai_snap_runtime'
    $env:AI_ENABLED='false';$env:GROQ_API_KEY='';$env:PYTHONPATH=Join-Path $root 'backend'

    if($Mode -in @('Preflight','Reserve','Create')){
        & $python (Join-Path $root 'backend\scripts\check_ai_snapshot_test_runtime.py')
        if($LASTEXITCODE -ne 0){throw 'STOP: exact empty-schema preflight failed.'}
    }
    if($Mode -eq 'Preflight') { Write-Output 'READ-ONLY TAMIL AI FIXTURE PREFLIGHT COMPLETE; no files or records changed'; return }
    if($RunId -eq '' -and $Mode -eq 'Reserve'){$RunId=([guid]::NewGuid().ToString('N'))}
    if($RunId -cnotmatch '^[0-9a-f]{32}$'){throw 'STOP: exact lowercase 128-bit run ID required.'}
    $reservation=Join-Path $privateDir "tamil-ai-browser-fixture-$RunId.json"
    $ownerFile=Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-owner.dpapi"
    $pending=Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-pending.json"
    $evidence=Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-created.json"
    $cleanupPending=Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-cleanup-pending.json"
    $cleanupEvidence=Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-cleaned.json"
    if($Mode -eq 'Reserve') {
        if(-not $Execute -or $ConfirmTarget -cne $target -or -not $ConfirmEmpty -or -not $ConfirmWriterPause){throw 'STOP: reservation authorization gates incomplete.'}
        foreach($path in @($reservation,$ownerFile)){if(Test-Path -LiteralPath $path){throw 'STOP: private fixture path already exists.'}}
        if(-not(Test-Path -LiteralPath $privateDir)){New-Item -ItemType Directory -Path $privateDir -ErrorAction Stop | Out-Null}
        $bytes=New-Object byte[] 48;[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $plain=[Convert]::ToBase64String($bytes);$ownerSecure=ConvertTo-SecureString $plain -AsPlainText -Force
        $ownerSecure|ConvertFrom-SecureString|Set-Content -LiteralPath $ownerFile -Encoding ASCII -NoNewline
        Set-TamilAiPrivateFileDaclOnly $ownerFile $operatorSid
        $reserveOutput=$null;$reserveExit=1
        try {$reserveOutput=& $python $script reserve --run-id $RunId --reservation $reservation;$reserveExit=$LASTEXITCODE}
        finally {if(Test-Path -LiteralPath $reservation -PathType Leaf){Set-TamilAiPrivateFileDaclOnly $reservation $operatorSid}}
        if($reserveExit -ne 0){throw 'STOP: reservation failed; preserve any private file.'}
        Assert-TamilAiPrivateFileAcl $ownerFile $operatorSid;Assert-TamilAiPrivateFileAcl $reservation $operatorSid
        $reserveOutput|Write-Output
        Write-Output "PASS: fixture reserved and DACL-verified; record RunId=$RunId privately"
        return
    }
    foreach($path in @($reservation)){if(-not(Test-Path -LiteralPath $path -PathType Leaf)){throw 'STOP: immutable reservation missing.'}}
    if($Mode -eq 'Create') {
        if(-not $Execute -or $ConfirmTarget -cne $target -or -not $ConfirmEmpty -or -not $ConfirmWriterPause){throw 'STOP: creation authorization gates incomplete.'}
        foreach($path in @($ownerFile)){if(-not(Test-Path -LiteralPath $path -PathType Leaf)){throw 'STOP: private owner credential missing.'}}
        foreach($path in @($pending,$evidence)){if(Test-Path -LiteralPath $path){throw 'STOP: fixture evidence already exists; never retry automatically.'}}
        Assert-TamilAiPrivateFileAcl $reservation $operatorSid;Assert-TamilAiPrivateFileAcl $ownerFile $operatorSid
        $ownerSecure=ConvertTo-SecureString (Get-Content -LiteralPath $ownerFile -Raw)
        $ownerPointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($ownerSecure)
        $env:TAMIL_AI_FIXTURE_OWNER_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ownerPointer)
        $createOutput=$null;$createExit=1
        try {$createOutput=& $python $script create --run-id $RunId --reservation $reservation --pending $pending --evidence $evidence;$createExit=$LASTEXITCODE}
        finally {foreach($path in @($pending,$evidence)){if(Test-Path -LiteralPath $path -PathType Leaf){Set-TamilAiPrivateFileDaclOnly $path $operatorSid}}}
        if($createExit -ne 0){throw 'STOP: fixture commit status may be uncertain; preserve evidence and do not retry.'}
        Assert-TamilAiPrivateFileAcl $pending $operatorSid;Assert-TamilAiPrivateFileAcl $evidence $operatorSid
        $createOutput|Write-Output
        Write-Output 'PASS: fixture creation wrapper completed with protected private evidence'
        return
    }
    if(-not(Test-Path -LiteralPath $evidence -PathType Leaf)){throw 'STOP: committed fixture evidence missing.'}
    if($Mode -in @('Verify','CleanupReview')) {
        foreach($path in @($reservation,$ownerFile,$pending,$evidence)){Assert-TamilAiPrivateFileAcl $path $operatorSid}
        & $python $script $(if($Mode -eq 'Verify'){'verify'}else{'cleanup-review'}) --run-id $RunId --reservation $reservation --evidence $evidence
        if($LASTEXITCODE -ne 0){throw 'STOP: read-only fixture verification failed.'}
        if($Mode -eq 'CleanupReview'){Write-Output 'READ-ONLY CLEANUP REVIEW COMPLETE; no record, file or DACL changed'}
        else{Write-Output 'PASS: read-only fixture wrapper verified database evidence and private DACLs; nothing changed'}
        return
    }
    if(-not $Execute -or $ConfirmTarget -cne $target -or -not $ConfirmWriterPause){throw 'STOP: cleanup authorization gates incomplete.'}
    foreach($path in @($cleanupPending,$cleanupEvidence)){if(Test-Path -LiteralPath $path){throw 'STOP: cleanup evidence already exists; never retry automatically.'}}
    foreach($path in @($reservation,$ownerFile,$pending,$evidence)){Assert-TamilAiPrivateFileAcl $path $operatorSid}
    $cleanupOutput=$null;$cleanupExit=1
    try {$cleanupOutput=& $python $script cleanup --run-id $RunId --reservation $reservation --evidence $evidence --cleanup-pending $cleanupPending --cleanup-evidence $cleanupEvidence;$cleanupExit=$LASTEXITCODE}
    finally {foreach($path in @($cleanupPending,$cleanupEvidence)){if(Test-Path -LiteralPath $path -PathType Leaf){Set-TamilAiPrivateFileDaclOnly $path $operatorSid}}}
    if($cleanupExit -ne 0){throw 'STOP: cleanup commit state may be uncertain; preserve evidence and do not retry.'}
    $cleanupOutput|Write-Output
    Write-Output 'PASS: cleanup wrapper completed with protected private evidence'
} finally {
    foreach($name in $names){[Environment]::SetEnvironmentVariable($name,$old[$name],'Process')}
    foreach($pointer in @($dbPointer,$ownerPointer)){if($pointer -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}}
    foreach($secure in @($dbSecure,$ownerSecure)){if($null -ne $secure){$secure.Dispose()}}
}
