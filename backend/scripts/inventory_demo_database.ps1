# Offline by default; explicit execution is a read-only database operation.
param([switch]$Execute, [string]$ConfirmTarget)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$script = Join-Path $PSScriptRoot 'inventory_demo_database.py'
if (-not $Execute) {
    Write-Output 'PASS: offline inventory preparation only; no credentials loaded or database connected'
    exit 0
}
if ($ConfirmTarget -cne 'lankapex_demo_db') { Write-Output 'STOP: demo inventory category=confirmation'; exit 1 }
$secretFile = Join-Path $root '.server-logs\private-demo\demo-app.dpapi'
$names = @('APP_ENV','MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
$secure = $null
$pointer = [IntPtr]::Zero
$exitCode = 1
try {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or -not (Test-Path -LiteralPath $secretFile -PathType Leaf)) { throw 'prerequisite' }
    if ((Get-Item -LiteralPath $secretFile).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'private_acl' }
    $acl = Get-Acl -LiteralPath $secretFile
    if (-not $acl.AreAccessRulesProtected) { throw 'private_acl' }
    $operatorSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $operatorFull = $false
    foreach ($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
        if ($rule.IsInherited -or $rule.AccessControlType -ne 'Allow' -or $rule.IdentityReference.Value -notin @($operatorSid,'S-1-5-18')) { throw 'private_acl' }
        if ($rule.IdentityReference.Value -eq $operatorSid -and ($rule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl) { $operatorFull = $true }
    }
    if (-not $operatorFull) { throw 'private_acl' }
    $secure = ConvertTo-SecureString (Get-Content -LiteralPath $secretFile -Raw)
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $env:APP_ENV = 'development'
    $env:MYSQL_HOST = 'localhost'
    $env:MYSQL_PORT = '3306'
    $env:MYSQL_DATABASE = 'lankapex_demo_db'
    $env:MYSQL_USER = 'lankapex_demo_app'
    $env:MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    & $python $script --execute --confirm-target lankapex_demo_db
    $exitCode = $LASTEXITCODE
} catch {
    Write-Output 'STOP: demo inventory category=private_credential_or_wrapper_prerequisite'
    $exitCode = 1
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
}
exit $exitCode
