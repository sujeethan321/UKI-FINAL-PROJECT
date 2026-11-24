# DB-free tests: invoke the real launcher function with credential/child interfaces mocked.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '..\scripts\start_viva_backend.ps1')
$actualReader=(Get-Item Function:Read-VivaCredential).ScriptBlock
$script:checks=0
function Assert-True([bool]$Value,[string]$Message) { if (-not $Value) { throw $Message }; $script:checks++ }
foreach ($badPath in @((Join-Path $PSScriptRoot 'nonexistent-fictional-credential.dpapi'),$PSCommandPath)) {
    $failed=$false
    try { $unused=& $actualReader ([pscustomobject]@{Credential=$badPath}) 'jwt' } catch { $failed=$true; Assert-True ($_.Exception.Message -ceq 'credential_invalid') 'unsafe credential diagnostic' }
    Assert-True $failed 'missing or invalid DPAPI credential accepted'
}
$script:calls=@(); $script:failChild=$false; $script:credentialFailure=$false; $script:failJwt=$false; $script:closed=0
function Get-VivaCredentialLease { param($Kind,$Mode) if ($script:credentialFailure) { throw 'credential_missing' }; [pscustomobject]@{Kind=$Kind} }
function Read-VivaCredential { param($Lease,$Kind) if ($script:credentialFailure -or ($script:failJwt -and $Kind -eq 'jwt')) { throw 'credential_invalid' }; ConvertTo-SecureString ('fictional-only-'+('x'*80)) -AsPlainText -Force }
function Close-DemoQrStorageLease { param($Lease) $script:closed++ }
function Invoke-VivaPython {
    param($Python,$Arguments)
    $script:calls+=,($Arguments -join ' ')
    Assert-True ($env:MYSQL_DATABASE -ceq 'lankapex_viva_db') 'wrong child database'
    Assert-True ($env:MYSQL_USER -ceq 'lankapex_viva_runtime') 'wrong child account'
    Assert-True ($env:AI_ENABLED -ceq 'false' -and $env:STRIPE_SANDBOX_ENABLED -ceq 'false') 'external feature enabled'
    Assert-True ($env:LANKAPEX_VIVA_RUNTIME -ceq 'true') 'dotenv isolation absent'
    Assert-True ($env:CORS_ALLOWED_ORIGINS -ceq 'http://127.0.0.1:5173,http://127.0.0.1:5176') 'VIVA origins differ from approved ports'
    if ($script:failChild) { throw 'secret-child-error-not-for-logs' }
}
# Save and remove only controlled environment settings; never print their values.
$names=@('LANKAPEX_VIVA_RUNTIME','APP_ENV','MYSQL_HOST','MYSQL_PORT','MYSQL_DATABASE','MYSQL_USER','MYSQL_TLS_MODE','MYSQL_SSL_CA','APP_DEBUG','LOG_LEVEL','RATE_LIMIT_MODE','ADDRESS_BOOK_ENABLED','ADDRESS_CHECKOUT_ENABLED','SUPPORT_ENABLED','DRIVER_FINANCE_ENABLED','ADDRESS_DBA_ATTESTED_REVISION','SUPPORT_DBA_ATTESTED_REVISION','DRIVER_FINANCE_DBA_ATTESTED_REVISION','AI_ENABLED','STRIPE_SANDBOX_ENABLED','CORS_ALLOWED_ORIGINS','ALLOWED_HOSTS','LANKAPEX_DISABLE_DOTENV','GROQ_API_KEY','STRIPE_TEST_SECRET_KEY','STRIPE_WEBHOOK_SECRET','DATABASE_URL','SQLALCHEMY_DATABASE_URI','MYSQL_PASSWORD','JWT_SECRET_KEY')
$saved=@{}
try {
    foreach ($name in $names) { $saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process'); [Environment]::SetEnvironmentVariable($name,$null,'Process') }
    $env:LOG_LEVEL='INFO'
    $result=@(Invoke-VivaRuntime -PreflightOnly -ConfirmDbaHeadAttestation)
    Assert-True ($result[-1] -eq 0) 'preflight failed'
    Assert-True ($script:calls.Count -eq 1 -and $script:calls[0] -eq '-B scripts/check_viva_backend.py') 'preflight started service'
    Assert-True ($env:LOG_LEVEL -ceq 'INFO' -and $null -eq $env:MYSQL_PASSWORD -and $null -eq $env:LANKAPEX_VIVA_RUNTIME) 'success environment not restored'
    Assert-True ($script:closed -eq 2) 'credential leases leaked'
    $script:failChild=$true
    $result=@(Invoke-VivaRuntime -PreflightOnly -ConfirmDbaHeadAttestation)
    Assert-True ($result[-1] -eq 1) 'child failure accepted'
    Assert-True (($result -join ' ') -notmatch 'secret-child-error') 'raw failure leaked'
    Assert-True ($null -eq $env:MYSQL_PASSWORD -and $env:LOG_LEVEL -ceq 'INFO') 'failure environment not restored'
    $script:failChild=$false; $script:credentialFailure=$true; $before=$script:calls.Count
    $result=@(Invoke-VivaRuntime -PreflightOnly -ConfirmDbaHeadAttestation)
    Assert-True ($result[-1] -eq 1 -and $script:calls.Count -eq $before) 'missing credentials launched child'
    $script:credentialFailure=$false
    $script:failJwt=$true
    $result=@(Invoke-VivaRuntime -PreflightOnly -ConfirmDbaHeadAttestation)
    Assert-True ($result[-1] -eq 1 -and $script:calls.Count -eq $before) 'partial credential failure launched child'
    Assert-True ($null -eq $env:MYSQL_PASSWORD -and $null -eq $env:JWT_SECRET_KEY) 'partial credential environment leaked'
    $script:failJwt=$false
    $result=@(Invoke-VivaRuntime -ConfirmDbaHeadAttestation)
    Assert-True ($result[-1] -eq 1 -and $script:calls.Count -eq $before) 'active freeze started service'
    $result=@(Invoke-VivaRuntime -PreflightOnly)
    Assert-True ($result[-1] -eq 1 -and $script:calls.Count -eq $before) 'missing DBA attestation accepted'
    $env:MYSQL_DATABASE='lankapex_db'
    $result=@(Invoke-VivaRuntime -PreflightOnly -ConfirmDbaHeadAttestation)
    Assert-True ($result[-1] -eq 1 -and $script:calls.Count -eq $before) 'inherited target accepted'
    [Environment]::SetEnvironmentVariable('MYSQL_DATABASE',$null,'Process')
    $env:GROQ_API_KEY='fictional-not-a-key'
    $result=@(Invoke-VivaRuntime -PreflightOnly -ConfirmDbaHeadAttestation)
    Assert-True ($result[-1] -eq 1 -and $script:calls.Count -eq $before) 'inherited external credential accepted'
    Assert-True ($env:GROQ_API_KEY -ceq 'fictional-not-a-key') 'rejected environment altered'
} finally { foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') } }
Write-Output ('PASS: '+$script:checks+' offline launcher assertions; no service or database operations')
