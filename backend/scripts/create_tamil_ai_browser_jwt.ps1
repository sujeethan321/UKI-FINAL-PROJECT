param(
    [switch]$Execute,
    [string]$ConfirmTarget='',
    [string]$ConfirmRunId='',
    [switch]$ConfirmJwtCreation
)
$ErrorActionPreference='Stop'
$expectedDatabase='lankapex_ai_snapshot_test_db'
$expectedRunId='14405b71b0504036a35ff55c7a9da132'
if($Execute){
    if($ConfirmTarget -cne $expectedDatabase -or $ConfirmRunId -cne $expectedRunId -or -not $ConfirmJwtCreation){
        throw 'STOP: exact target, RunId and JWT-creation confirmation required.'
    }
} elseif($ConfirmTarget -or $ConfirmRunId -or $ConfirmJwtCreation){
    throw 'STOP: JWT creation confirmations require -Execute.'
}
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$helper=Join-Path $PSScriptRoot 'tamil_ai_private_acl.ps1'
$privateDir=Join-Path $root '.server-logs\private-ai-tests'
$target=Join-Path $privateDir 'tamil-ai-browser-jwt.dpapi'
if(-not(Test-Path -LiteralPath $helper -PathType Leaf)){throw 'STOP: private DACL helper missing.'}
if(-not(Test-Path -LiteralPath $privateDir -PathType Container)){throw 'STOP: private AI test directory missing.'}
. $helper
$operatorSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$bytes=$null;$secretSecure=$null;$checkSecure=$null;$checkPointer=[IntPtr]::Zero
$plain=$null;$cipher=$null;$failure=$null
try {
    if(-not $Execute){
        if(-not(Test-Path -LiteralPath $target -PathType Leaf)){
            Write-Output 'PASS: test-only browser JWT credential is absent and creation prerequisites are ready; no file created'
            return
        }
        Assert-TamilAiPrivateFileAcl $target $operatorSid
        $checkSecure=ConvertTo-SecureString (Get-Content -LiteralPath $target -Raw -ErrorAction Stop)
        $checkPointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($checkSecure)
        if([Runtime.InteropServices.Marshal]::PtrToStringBSTR($checkPointer).Length -lt 48){
            throw 'STOP: existing browser JWT secret is shorter than 48 characters.'
        }
        Write-Output 'PASS: test-only browser JWT credential decrypts and has a protected operator/SYSTEM-only DACL; no file changed'
        return
    }
    if(Test-Path -LiteralPath $target){throw 'STOP: browser JWT credential already exists; refusing overwrite.'}
    $bytes=New-Object byte[] 48
    $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
    try{$rng.GetBytes($bytes)}finally{$rng.Dispose()}
    $plain=[Convert]::ToBase64String($bytes)
    if($plain.Length -lt 48){throw 'STOP: generated JWT secret length is invalid.'}
    $secretSecure=ConvertTo-SecureString $plain -AsPlainText -Force
    $cipher=ConvertFrom-SecureString $secretSecure
    $stream=New-Object IO.FileStream($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{
        $writer=New-Object IO.StreamWriter($stream,[Text.Encoding]::ASCII)
        try{$writer.Write($cipher);$writer.Flush()}finally{$writer.Dispose()}
    }finally{if($null -ne $stream){$stream.Dispose()}}
    Set-TamilAiPrivateFileDaclOnly $target $operatorSid
    $checkSecure=ConvertTo-SecureString (Get-Content -LiteralPath $target -Raw -ErrorAction Stop)
    $checkPointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($checkSecure)
    if([Runtime.InteropServices.Marshal]::PtrToStringBSTR($checkPointer).Length -lt 48){
        throw 'STOP: stored browser JWT credential failed minimum-length verification.'
    }
    Assert-TamilAiPrivateFileAcl $target $operatorSid
    Write-Output 'PASS: test-only browser JWT secret stored with CurrentUser DPAPI and protected operator/SYSTEM-only DACL'
} catch {
    $failure='STOP: Tamil AI browser JWT credential gate failed; preserve any created file and do not retry automatically.'
} finally {
    if($checkPointer -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($checkPointer)}
    foreach($secure in @($secretSecure,$checkSecure)){if($null -ne $secure){$secure.Dispose()}}
    if($null -ne $bytes){[Array]::Clear($bytes,0,$bytes.Length)}
    $plain=$null;$cipher=$null
}
if($failure){Write-Output $failure;exit 1}
