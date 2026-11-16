# Run only under the Windows account that created qr-test-runtime.dpapi.
param([switch]$CompatibilityDiagnostics)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$secretFile = Join-Path $root '.server-logs\private-test\qr-test-runtime.dpapi'
$privateDir = Join-Path $root '.server-logs\private-test'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'STOP: backend Python missing.' }
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) { throw 'STOP: separate test-runtime credential missing.' }

$names = @('APP_ENV', 'MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_DATABASE', 'MYSQL_USER',
           'MYSQL_PASSWORD', 'PYTHONPATH')
$old = @{}
foreach ($name in $names) { $old[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$secure = $null
$pointer = [IntPtr]::Zero
try {
    $secure = ConvertTo-SecureString (Get-Content -LiteralPath $secretFile -Raw)
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $env:MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $env:APP_ENV = 'testing'
    $env:MYSQL_HOST = 'localhost'
    $env:MYSQL_PORT = '3306'
    $env:MYSQL_DATABASE = 'lankapex_test_db'
    $env:MYSQL_USER = 'lankapex_qr_test_runtime'
    $env:PYTHONPATH = Join-Path $root 'backend'

    & $python (Join-Path $root 'backend\scripts\check_qr_test_runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'STOP: exact-target preflight failed; no tests started.' }

    $groups = @(
        @{ Label = 'QR join'; Files = @('tests/test_customer_qr_join.py', 'tests/test_customer_qr_join_concurrency.py') },
        @{ Label = 'invitation and customer dashboard compatibility'; Files = @(
            'tests/test_customer_link.py', 'tests/test_customer_link_concurrency.py',
            'tests/test_customer_dashboard.py', 'tests/test_customer_history.py') }
    )
    if ($CompatibilityDiagnostics) { $groups = @($groups[1]) }
    $backend = Join-Path $root 'backend'
    foreach ($group in $groups) {
        # Suppress detailed pytest output so synthetic tokens and records cannot
        # appear in terminal logs. Print only the official pytest count summary.
        Push-Location $backend
        try {
            if ($CompatibilityDiagnostics) {
                $output = & $python -m pytest @($group.Files) -q --tb=short --show-capture=no -p no:cacheprovider 2>&1 | Out-String
            } else {
                $output = & $python -m pytest @($group.Files) -q --tb=no -p no:cacheprovider 2>&1 | Out-String
            }
            $exitCode = $LASTEXITCODE
        } finally { Pop-Location }
        $summary = [regex]::Matches($output, '(\d+) (passed|failed|skipped|error|errors)')
        $counts = @{ passed = 0; failed = 0; skipped = 0; error = 0; errors = 0 }
        foreach ($match in $summary) { $counts[$match.Groups[2].Value] = [int]$match.Groups[1].Value }
        if ($CompatibilityDiagnostics) {
            if (-not (Test-Path -LiteralPath $privateDir -PathType Container)) {
                throw 'STOP: private diagnostic directory missing.'
            }
            $report = Join-Path $privateDir ('qr-compat-diagnostic-{0}-{1}.txt' -f
                (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'), [guid]::NewGuid().ToString('N'))
            if (Test-Path -LiteralPath $report) { throw 'STOP: diagnostic report already exists.' }
            # Create the destination with an explicit current-user-only ACL
            # before writing any pytest text. No raw traceback reaches stdout.
            $file = New-Item -ItemType File -Path $report -ErrorAction Stop
            $acl = Get-Acl -LiteralPath $file.FullName
            $acl.SetAccessRuleProtection($true, $false)
            foreach ($rule in @($acl.Access)) { [void]$acl.RemoveAccessRuleAll($rule) }
            $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'Allow')
            $acl.AddAccessRule($rule)
            Set-Acl -LiteralPath $file.FullName -AclObject $acl -ErrorAction Stop
            $safeOutput = $output.Replace($env:MYSQL_PASSWORD, '[REDACTED]')
            $safeOutput = [regex]::Replace($safeOutput, '(?i)Bearer\s+[A-Za-z0-9._~+/-]+', 'Bearer [REDACTED]')
            $safeOutput = [regex]::Replace($safeOutput, '(?i)(?:mysql\+pymysql|mysql)://[^\s''"<>]+', '[REDACTED CONNECTION]')
            $safeOutput = [regex]::Replace($safeOutput, '(?i)(password|password_hash|mysql_password|jwt_secret_key|access_token|refresh_token|invitation)\s*[=:]\s*[^\s,}\]]+', '$1=[REDACTED]')
            $safeOutput = [regex]::Replace($safeOutput, '\b[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b', '[REDACTED TOKEN]')
            $safeOutput = [regex]::Replace($safeOutput, '\b[0-9]{6}\b', '[REDACTED CODE]')
            [System.IO.File]::WriteAllText($file.FullName, $safeOutput, [System.Text.Encoding]::UTF8)
            $safeOutput = $null
            Write-Output ('Private compatibility diagnostic report: ' + $file.FullName)
        }
        Write-Output ("{0}: passed={1} failed={2} skipped={3} errors={4}" -f
            $group.Label, $counts.passed, $counts.failed, $counts.skipped,
            ($counts.error + $counts.errors))
        $output = $null
        if ($exitCode -eq 1 -and $counts.failed -gt 0) {
            throw 'STOP: test assertions failed; no later group ran.'
        }
        if ($exitCode -ne 0 -or ($counts.error + $counts.errors) -gt 0 -or
            ($counts.passed + $counts.skipped) -eq 0) {
            throw 'STOP: pytest infrastructure/collection failed or produced no verifiable summary; no later group ran.'
        }
    }
    if ($CompatibilityDiagnostics) { Write-Output 'PASS: isolated compatibility diagnostic group completed.' }
    else { Write-Output 'PASS: both isolated QR and compatibility test groups completed.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $old[$name], 'Process') }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
}
