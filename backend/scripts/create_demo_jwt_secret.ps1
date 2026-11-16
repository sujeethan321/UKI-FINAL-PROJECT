# One-time local secret creation; no value is printed or passed on argv.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$target = Join-Path $repoRoot '.server-logs\private-demo\demo-jwt.dpapi'
if (Test-Path -LiteralPath $target) { throw 'Demo JWT secret already exists; refusing overwrite.' }
$directory = Split-Path -Parent $target
if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
    throw 'Private demo directory missing.'
}
$bytes = New-Object byte[] 48
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$plain = [Convert]::ToBase64String($bytes)
$secure = ConvertTo-SecureString $plain -AsPlainText -Force
try {
    $encrypted = ConvertFrom-SecureString $secure
    [IO.File]::WriteAllText($target, $encrypted)
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe $target /inheritance:r /grant:r ($identity + ':(F)') 'SYSTEM:(F)' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Private file ACL setup failed.' }
    $acl = Get-Acl -LiteralPath $target
    $unexpected = @($acl.Access | Where-Object {
        $_.IdentityReference.Value -ne $identity -and
        $_.IdentityReference.Value -ne 'NT AUTHORITY\SYSTEM' -and
        $_.IdentityReference.Value -ne 'SYSTEM'
    })
    if ($unexpected.Count -gt 0) { throw 'Unexpected file ACL principal.' }
    Write-Output 'PASS: random demo JWT secret stored with Windows DPAPI and restricted local ACL; value not displayed'
} finally {
    $secure.Dispose()
    [Array]::Clear($bytes, 0, $bytes.Length)
    $plain = $null
    $encrypted = $null
}
