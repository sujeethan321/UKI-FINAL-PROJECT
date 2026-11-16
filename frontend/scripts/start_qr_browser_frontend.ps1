# Test-only local frontend. It never launches the demo API.
param([switch]$PreflightOnly)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$frontend = Join-Path $root 'frontend'
$vite = Join-Path $frontend 'node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $vite -PathType Leaf)) { throw 'STOP: local Vite dependency missing; server not started.' }
$existing = @(Get-ChildItem Env:VITE_* -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne 'VITE_API_URL' })
if ($existing.Count -ne 0) { throw 'STOP: unreviewed public VITE_ variable; server not started.' }
$previous = [Environment]::GetEnvironmentVariable('VITE_API_URL', 'Process')
try {
    $env:VITE_API_URL = 'http://127.0.0.1:8013/api/v1'
    if ($env:VITE_API_URL -ne 'http://127.0.0.1:8013/api/v1') { throw 'STOP: test API URL differs.' }
    if ($PreflightOnly) {
        Write-Output 'PASS: loopback QR frontend points to test-only API; no server started'
        return
    }
    Push-Location $frontend
    try {
        & node $vite --host 127.0.0.1 --port 5174 --strictPort
        if ($LASTEXITCODE -ne 0) { throw 'STOP: test-only frontend exited with an error.' }
    } finally { Pop-Location }
} finally {
    [Environment]::SetEnvironmentVariable('VITE_API_URL', $previous, 'Process')
}
