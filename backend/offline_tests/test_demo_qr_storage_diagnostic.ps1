# Synthetic metadata only. Never invokes native opens, registry reads or real ACLs.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '..\scripts\demo_qr_credential_storage.ps1')
$script:passed=0
$sid='S-1-5-21-1-2-3-1001'
$paths=Get-DemoQrStoragePaths $sid 'C:\Users\synthetic'
function Node {
    [pscustomobject]@{MetadataVerified=$true;Reparse=$false;Owner=$sid;Protected=$true;Directory=$true;
        Handle=(New-Object IO.MemoryStream);Rules=@(
            [pscustomobject]@{Sid=$sid;Mask=0x1F01FF;Type='Allow';Inherited=$false;InheritOnly=$false},
            [pscustomobject]@{Sid='S-1-5-18';Mask=0x1F01FF;Type='Allow';Inherited=$false;InheritOnly=$false})}
}
function Check-Failure {
    param([scriptblock]$Context={param($t) $paths},
          [scriptblock]$Exists={param($p) $true},
          [scriptblock]$Opener={param($p,$t) Node},
          [string]$Stage,[string]$Reason,[string]$Surface)
    $trace=@{Stage='helper_load';Surface='none';NativeError='none'}
    $failed=$false
    try { $lease=Assert-DemoQrCredentialStorage -ContextProvider $Context -Exists $Exists -OpenNode $Opener -Trace $trace; Close-DemoQrStorageLease $lease }
    catch {
        $failed=$true
        $line=Get-DemoQrStorageDiagnosticLine $trace $_.Exception.Message
        if ($line -cnotmatch ('stage='+$Stage+' ') -or $line -cnotmatch ('check='+$Reason+' ') -or
            ($Surface -and $line -cnotmatch ('surface='+$Surface+' '))) { throw 'offline_trace_mismatch' }
        if($line.Contains($sid) -or $line.Contains('C:\') -or $line.Contains('sensitive-marker')) { throw 'offline_redaction_failure' }
    }
    if (-not $failed) { throw 'offline_expected_rejection' }
    $script:passed++
}
Check-Failure -Context {param($t) Set-DemoQrStorageStage $t 'profile_registry_open' 'operator_profile'; throw 'sensitive-marker'} -Stage profile_registry_open -Reason metadata_api_or_runtime_error -Surface operator_profile
Check-Failure -Context {param($t) Set-DemoQrStorageStage $t 'expected_path_construction' 'operator_profile'; throw 'operator_profile'} -Stage expected_path_construction -Reason operator_profile
Check-Failure -Exists {param($p) throw 'sensitive-marker'} -Stage ancestor_existence -Reason metadata_api_or_runtime_error -Surface ancestor_0
Check-Failure -Opener {param($p,$t) Set-DemoQrStorageStage $t 'native_handle_open'; $t.NativeError='sharing_violation'; throw 'metadata_handle'} -Stage native_handle_open -Reason metadata_handle
Check-Failure -Opener {param($p,$t) Set-DemoQrStorageStage $t 'native_final_path'; throw 'metadata_unavailable'} -Stage native_final_path -Reason metadata_unavailable
Check-Failure -Opener {param($p,$t) Set-DemoQrStorageStage $t 'dacl_read'; throw 'metadata_unavailable'} -Stage dacl_read -Reason metadata_unavailable
Check-Failure -Opener {param($p,$t) Set-DemoQrStorageStage $t 'dacl_canonical_order'; throw 'metadata_unavailable'} -Stage dacl_canonical_order -Reason metadata_unavailable
Check-Failure -Opener {param($p,$t) Set-DemoQrStorageStage $t 'ace_metadata_conversion'; throw 'metadata_unavailable'} -Stage ace_metadata_conversion -Reason metadata_unavailable
Check-Failure -Opener {param($p,$t) $n=Node; $n.Directory=$false; $n} -Stage directory_type -Reason ancestor_not_directory
Check-Failure -Opener {param($p,$t) $n=Node; $n.Reparse=$true; $n} -Stage ancestor_acl_policy -Reason metadata_or_reparse
Check-Failure -Opener {param($p,$t) $n=Node; $n.Owner='untrusted'; $n} -Stage ancestor_acl_policy -Reason ancestor_owner
Check-Failure -Opener {param($p,$t) $n=Node; if($p -ceq $paths.Profile){$n.Owner='S-1-5-32-544'}; $n} -Stage profile_owner -Reason operator_profile_owner -Surface operator_profile
Check-Failure -Opener {param($p,$t) $n=Node; $n.Rules[1].Sid='untrusted'; $n} -Stage ancestor_acl_policy -Reason ancestor_mutation_or_delete
Check-Failure -Exists {param($p) $p -cne $paths.Directory} -Stage storage_existence -Reason storage_preparation_required -Surface private_directory
Check-Failure -Opener {param($p,$t) $n=Node; if($p -ceq $paths.Directory){$n.Protected=$false}; $n} -Stage ancestor_acl_policy -Reason private_owner_or_inheritance -Surface private_directory
Check-Failure -Opener {param($p,$t) $n=Node; if($p -ceq $paths.Credential){$n.Directory=$false; $n.Rules[1].Sid=$sid}; $n} -Stage credential_acl_policy -Reason private_dacl -Surface credential_file
$line=Get-DemoQrStorageDiagnosticLine @{Stage='sensitive-marker';Surface='C:\sensitive-marker';NativeError=$sid} 'sensitive-marker'
if($line -cne 'STOP: QR storage diagnostic stage=unknown surface=unknown check=metadata_api_or_runtime_error native_error=unknown') { throw 'offline_formatter_redaction' }
$script:passed++
Write-Output ('PASS: '+$script:passed+' offline diagnostic cases; no live metadata operations')
