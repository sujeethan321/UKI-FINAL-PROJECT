param([switch]$PreflightOnly, [Parameter(Mandatory=$true)][string]$RunId)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$privateDir = Join-Path $root '.server-logs\private-ai-tests'
$dbFile = Join-Path $privateDir 'ai-snapshot-test-runtime.dpapi'
$jwtFile = Join-Path $privateDir 'tamil-ai-browser-jwt.dpapi'
$reservation = Join-Path $privateDir "tamil-ai-browser-fixture-$RunId.json"
$evidence = Join-Path $privateDir "tamil-ai-browser-fixture-$RunId-created.json"
if ($RunId -cnotmatch '^[0-9a-f]{32}$') { throw 'STOP: exact lowercase 128-bit run ID required.' }
foreach ($file in @($python,$dbFile,$jwtFile,$reservation,$evidence)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'STOP: Tamil AI browser prerequisite missing.' }
}
$names = @('APP_ENV','MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD','JWT_SECRET_KEY',
           'PYTHONPATH','APP_DEBUG','LOG_LEVEL','CORS_ALLOWED_ORIGINS','RATE_LIMIT_MODE','AI_ENABLED','GROQ_API_KEY',
           'LANKAPEX_DISABLE_DOTENV')
$old=@{}; foreach($name in $names){$old[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
$dbSecure=$null;$jwtSecure=$null;$dbPointer=[IntPtr]::Zero;$jwtPointer=[IntPtr]::Zero
try {
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
    & $python (Join-Path $root 'backend\scripts\check_tamil_ai_browser_config.py')
    if($LASTEXITCODE -ne 0){throw 'STOP: browser configuration gate failed.'}
    & $python (Join-Path $root 'backend\scripts\tamil_ai_browser_fixture.py') verify --run-id $RunId --reservation $reservation --evidence $evidence
    if($LASTEXITCODE -ne 0){throw 'STOP: exact fixture verification failed.'}
    if($PreflightOnly){Write-Output 'READ-ONLY TAMIL AI BROWSER PREFLIGHT COMPLETE; no server started';return}
    Push-Location (Join-Path $root 'backend')
    try { & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8014 --log-level warning --no-access-log
          if($LASTEXITCODE -ne 0){throw 'STOP: isolated Tamil AI API exited with an error.'} }
    finally { Pop-Location }
} finally {
    foreach($name in $names){[Environment]::SetEnvironmentVariable($name,$old[$name],'Process')}
    foreach($pointer in @($dbPointer,$jwtPointer)){if($pointer -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}}
    foreach($secure in @($dbSecure,$jwtSecure)){if($null -ne $secure){$secure.Dispose()}}
}
