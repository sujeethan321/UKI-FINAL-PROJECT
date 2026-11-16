# Process-only demo API override. Existing frontend env files are untouched.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$previous = [Environment]::GetEnvironmentVariable('VITE_API_URL', 'Process')
$env:VITE_API_URL = 'http://127.0.0.1:8001/api/v1'
Push-Location (Join-Path $repoRoot 'frontend')
try {
    & npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
} finally {
    Pop-Location
    [Environment]::SetEnvironmentVariable('VITE_API_URL', $previous, 'Process')
}
