# Operator-only GroqCloud connection gate. Default mode sends no request.
param(
    [switch]$Execute,
    [string]$ConfirmModel = ''
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$model = 'openai/gpt-oss-120b'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'STOP: backend Python missing.' }
if ($Execute -and $ConfirmModel -cne $model) { throw 'STOP: exact model confirmation required.' }
if (-not $Execute -and $ConfirmModel) { throw 'STOP: model confirmation is execution-only.' }

$names = @('AI_ENABLED','GROQ_BASE_URL','GROQ_MODEL','GROQ_TIMEOUT_SECONDS',
           'GROQ_MAX_OUTPUT_TOKENS','PYTHONPATH')
$old = @{}
foreach ($name in $names) { $old[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    # Process-only enablement. GROQ_API_KEY is loaded by existing backend Settings;
    # this wrapper never reads, decrypts, prints, or copies it.
    $env:AI_ENABLED = 'true'
    $env:GROQ_BASE_URL = 'https://api.groq.com/openai/v1'
    $env:GROQ_MODEL = $model
    $env:GROQ_TIMEOUT_SECONDS = '10'
    # GPT-OSS may spend completion tokens on reasoning before visible content.
    # 256 remains a bounded connection-test budget below the application default.
    $env:GROQ_MAX_OUTPUT_TOKENS = '256'
    $env:PYTHONPATH = Join-Path $root 'backend'
    $runner = Join-Path $root 'backend\scripts\test_groq_connection.py'
    $runnerArgs = @($runner)
    if ($Execute) { $runnerArgs += @('--execute','--confirm-model',$model) }
    & $python @runnerArgs
    if ($LASTEXITCODE -ne 0) { throw 'STOP: guarded GroqCloud connection gate failed.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $old[$name], 'Process') }
}
