param([switch]$Execute, [Parameter(Mandatory=$true)][string]$RunId, [string]$ConfirmTarget='')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$privateDir = Join-Path $root '.server-logs\private-ai-tests'
$dbFile = Join-Path $privateDir 'ai-snapshot-test-runtime.dpapi'
$jwtFile = Join-Path $privateDir 'tamil-ai-browser-jwt.dpapi'
$reservation = Join-Path $privateDir "tamil-ai-browser-fixture-$RunId.json"
$evidence = Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-created.json"
$ownerFile = Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-owner.dpapi"
if ($RunId -cne '14405b71b0504036a35ff55c7a9da132') { throw 'STOP: exact reviewed RunId required.' }
if (-not $Execute) {
    Write-Output 'PASS: Owner credential verifier preparation; no credentials decrypted or database connected'
    return
}
if ($ConfirmTarget -cne 'lankapex_ai_snapshot_test_db') { throw 'STOP: exact database confirmation required.' }
. (Join-Path $PSScriptRoot 'tamil_ai_private_acl.ps1')
$operatorSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
Assert-TamilAiLegacyRuntimeCredentialAcl $dbFile $operatorSid
foreach ($file in @($jwtFile,$ownerFile,$reservation,$evidence)) {
    Assert-TamilAiPrivateFileAcl $file $operatorSid
}
$names = @('APP_ENV','MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD','JWT_SECRET_KEY',
           'PYTHONPATH','APP_DEBUG','LOG_LEVEL','CORS_ALLOWED_ORIGINS','RATE_LIMIT_MODE','AI_ENABLED','GROQ_API_KEY',
           'LANKAPEX_DISABLE_DOTENV','TAMIL_AI_OWNER_VERIFY_PASSWORD')
$old=@{}; foreach($name in $names){$old[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
$ownerSecure=$null;$ownerPointer=[IntPtr]::Zero;$dbSecure=$null;$jwtSecure=$null;$dbPointer=[IntPtr]::Zero;$jwtPointer=[IntPtr]::Zero
try {
    $ownerSecure=ConvertTo-SecureString (Get-Content -LiteralPath $ownerFile -Raw)
    $ownerPointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($ownerSecure)
    $env:TAMIL_AI_OWNER_VERIFY_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ownerPointer)
    $dbSecure=ConvertTo-SecureString (Get-Content -LiteralPath $dbFile -Raw)
    $jwtSecure=ConvertTo-SecureString (Get-Content -LiteralPath $jwtFile -Raw)
    $dbPointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbSecure)
    $jwtPointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($jwtSecure)
    $env:MYSQL_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($dbPointer)
    $env:JWT_SECRET_KEY=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($jwtPointer)
    $env:APP_ENV='ai_snapshot_testing';$env:MYSQL_HOST='localhost';$env:MYSQL_PORT='3306'
    $env:MYSQL_DATABASE='lankapex_ai_snapshot_test_db';$env:MYSQL_USER='lankapex_ai_snap_runtime'
    $env:PYTHONPATH=Join-Path $root 'backend';$env:APP_DEBUG='false';$env:LOG_LEVEL='WARNING'
    $env:CORS_ALLOWED_ORIGINS='http://127.0.0.1:5175';$env:RATE_LIMIT_MODE='local'
    $env:AI_ENABLED='false';$env:LANKAPEX_DISABLE_DOTENV='true'
    Remove-Item Env:GROQ_API_KEY -ErrorAction SilentlyContinue
    & $python (Join-Path $PSScriptRoot 'verify_tamil_ai_owner_credential.py') --execute --run-id $RunId --confirm-target $ConfirmTarget
    if($LASTEXITCODE -ne 0){throw 'STOP: guarded Owner credential verification failed.'}
} finally {
    foreach($name in $names){[Environment]::SetEnvironmentVariable($name,$old[$name],'Process')}
    foreach($pointer in @($dbPointer,$jwtPointer,$ownerPointer)){if($pointer -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}}
    foreach($secure in @($dbSecure,$jwtSecure,$ownerSecure)){if($null -ne $secure){$secure.Dispose()}}
}
