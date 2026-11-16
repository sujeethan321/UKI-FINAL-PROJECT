param([switch]$PreflightOnly)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$frontend=Join-Path $root 'frontend';$vite=Join-Path $frontend 'node_modules\vite\bin\vite.js'
if(-not (Test-Path -LiteralPath $vite -PathType Leaf)){throw 'STOP: Vite dependency missing.'}
$existing=@(Get-ChildItem Env:VITE_* -ErrorAction SilentlyContinue | Where-Object {$_.Name -ne 'VITE_API_URL'})
if($existing.Count -ne 0){throw 'STOP: unreviewed public VITE_ variable.'}
$old=[Environment]::GetEnvironmentVariable('VITE_API_URL','Process')
try {
    $env:VITE_API_URL='http://127.0.0.1:8014/api/v1'
    if($PreflightOnly){Write-Output 'PASS: loopback Tamil AI frontend points only to isolated API; no server started';return}
    Push-Location $frontend
    try { & node $vite --host 127.0.0.1 --port 5175 --strictPort
          if($LASTEXITCODE -ne 0){throw 'STOP: isolated frontend exited with an error.'} }
    finally { Pop-Location }
} finally {[Environment]::SetEnvironmentVariable('VITE_API_URL',$old,'Process')}
