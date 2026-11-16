# Synthetic ACLs and in-memory handles only. No filesystem/native validation.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '..\scripts\demo_qr_credential_storage.ps1')
$script:passed=0
$sid='S-1-5-21-1-2-3-1001'
$paths=Get-DemoQrStoragePaths $sid 'C:\Users\synthetic'
function Ace($Principal,$Mask=0x1F01FF,$Type='Allow',$Inherited=$false,$InheritOnly=$false) {
    [pscustomobject]@{Sid=$Principal;Mask=$Mask;Type=$Type;Inherited=$Inherited;InheritOnly=$InheritOnly}
}
function Node {
    [pscustomobject]@{MetadataVerified=$true;Reparse=$false;Owner=$sid;Protected=$true;
        Directory=$true;Handle=(New-Object IO.MemoryStream);
        Rules=@((Ace $sid),(Ace 'S-1-5-18'))}
}
function Pass($Label,[scriptblock]$Body) {
    try { & $Body; $script:passed++ } catch { throw ('offline_case_failed:'+ $Label) }
}
function Reject($Label,[scriptblock]$Body) {
    $failed=$false
    try { & $Body } catch { $failed=$true }
    if(-not $failed) { throw ('offline_rejection_failed:'+ $Label) }
    $script:passed++
}
Pass 'correct_identity' { if($paths.OperatorSid -cne $sid) { throw 'identity' } }
Reject 'invalid_identity' { Get-DemoQrStoragePaths 'S-1-5-18' 'C:\Users\synthetic' | Out-Null }
Reject 'relative_profile' { Get-DemoQrStoragePaths $sid '..\synthetic' | Out-Null }
Pass 'ignore_localappdata' {
    $previous=[Environment]::GetEnvironmentVariable('LOCALAPPDATA','Process')
    try {
        $env:LOCALAPPDATA='C:\untrusted'
        $p=Get-DemoQrStoragePaths $sid 'C:\Users\synthetic'
        if($p.Credential -cne 'C:\Users\synthetic\AppData\Local\LankaPex\PrivateDemoQr\demo-qr-migrator.dpapi') { throw 'override' }
    } finally { [Environment]::SetEnvironmentVariable('LOCALAPPDATA',$previous,'Process') }
}
Pass 'private_directory' { Test-DemoQrStorageNode (Node) $sid -Private }
Pass 'credential_file' { Test-DemoQrStorageNode (Node) $sid -Private -File }
Reject 'wrong_private_owner' { $n=Node; $n.Owner='S-1-5-18'; Test-DemoQrStorageNode $n $sid -Private }
Reject 'unprotected_private' { $n=Node; $n.Protected=$false; Test-DemoQrStorageNode $n $sid -Private }
Reject 'inherited_private' { $n=Node; $n.Rules[0].Inherited=$true; Test-DemoQrStorageNode $n $sid -Private }
Reject 'extra_private_principal' { $n=Node; $n.Rules+=Ace 'S-1-5-32-544'; Test-DemoQrStorageNode $n $sid -Private }
Reject 'missing_system' { $n=Node; $n.Rules=@((Ace $sid)); Test-DemoQrStorageNode $n $sid -Private }
Reject 'untrusted_owner' { $n=Node; $n.Owner='S-1-5-21-9-9-9-99'; Test-DemoQrStorageNode $n $sid }
Reject 'reparse' { $n=Node; $n.Reparse=$true; Test-DemoQrStorageNode $n $sid }
Reject 'metadata_missing' { $n=Node; $n.MetadataVerified=$false; Test-DemoQrStorageNode $n $sid }
Reject 'empty_or_null_dacl' { $n=Node; $n.Rules=@(); Test-DemoQrStorageNode $n $sid }
foreach($mask in @(0x10000,0x40,0x40000,0x80000,0x100,0x10,0x40000000,-268435456)) {
    Reject 'untrusted_delete_or_mutation' { $n=Node; $n.Rules+=Ace 'S-1-5-11' $mask; Test-DemoQrStorageNode $n $sid }
}
Pass 'system_admin_ancestor' { $n=Node; $n.Owner='S-1-5-32-544'; $n.Rules+=Ace 'S-1-5-32-544'; Test-DemoQrStorageNode $n $sid }
Pass 'servicing_ancestor' { $n=Node; $n.Owner='S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464'; Test-DemoQrStorageNode $n $sid }
Pass 'safe_read_traverse' { $n=Node; $n.Rules+=Ace 'S-1-5-11' 0x1200A9; Test-DemoQrStorageNode $n $sid }
Pass 'safe_generic_read' { $n=Node; $n.Rules+=Ace 'S-1-5-11' 0x80000000L; Test-DemoQrStorageNode $n $sid }
Pass 'unrelated_sibling_creation' { $n=Node; $n.Rules+=Ace 'S-1-5-11' 6; Test-DemoQrStorageNode $n $sid }
Pass 'inherit_only_not_applicable' { $n=Node; $n.Rules+=Ace 'S-1-5-11' 0x1F01FF 'Allow' $false $true; Test-DemoQrStorageNode $n $sid }
Reject 'deny_not_used_to_cancel_group_allow' {
    $n=Node; $n.Rules+=Ace 'S-1-5-11' 0x10000 'Deny'; $n.Rules+=Ace 'S-1-5-11' 0x10000
    Test-DemoQrStorageNode $n $sid
}
$context={ $paths }
$exists={ param($p) $true }
$opener={ param($p) $n=Node; if($p -ceq $paths.Credential) { $n.Directory=$false }; $n }
Pass 'shared_lease' {
    $lease=Assert-DemoQrCredentialStorage -Mode Read -ContextProvider $context -Exists $exists -OpenNode $opener
    if($lease.Credential -cne $paths.Credential -or $lease.Handles.Count -lt 5) { throw 'lease' }
    Close-DemoQrStorageLease $lease
    foreach($handle in $lease.Handles) { if($handle.CanRead) { throw 'not_closed' } }
}
foreach($profileOwner in @($sid,'S-1-5-18')) {
    Pass 'registered_profile_operator_or_system_owner' {
        $lease=Assert-DemoQrCredentialStorage -Mode Read -ContextProvider $context -Exists $exists -OpenNode {
            param($p) $n=Node
            if($p -ceq $paths.Profile) { $n.Owner=$profileOwner }
            if($p -ceq $paths.Credential) { $n.Directory=$false }
            $n
        }
        Close-DemoQrStorageLease $lease
    }
}
foreach($profileOwner in @('S-1-5-32-544','S-1-5-21-9-9-9-99',$null,'')) {
    Pass 'registered_profile_other_or_unavailable_owner_rejected' {
        try {
            $lease=Assert-DemoQrCredentialStorage -ContextProvider $context -Exists $exists -OpenNode {
                param($p) $n=Node; if($p -ceq $paths.Profile) { $n.Owner=$profileOwner }; $n
            }
            Close-DemoQrStorageLease $lease
            throw 'expected_rejection'
        } catch { if($_.Exception.Message -cne 'operator_profile_owner') { throw 'wrong_rejection' } }
    }
}
Reject 'system_profile_does_not_allow_system_private_owner' {
    Assert-DemoQrCredentialStorage -ContextProvider $context -Exists $exists -OpenNode {
        param($p) $n=Node
        if($p -ceq $paths.Profile -or $p -ceq $paths.Directory) { $n.Owner='S-1-5-18' }
        $n
    } | Out-Null
}
Reject 'system_profile_does_not_allow_system_credential_owner' {
    Assert-DemoQrCredentialStorage -ContextProvider $context -Exists $exists -OpenNode {
        param($p) $n=Node
        if($p -ceq $paths.Profile -or $p -ceq $paths.Credential) { $n.Owner='S-1-5-18' }
        if($p -ceq $paths.Credential) { $n.Directory=$false }
        $n
    } | Out-Null
}
Reject 'system_profile_reparse_still_rejected' {
    Assert-DemoQrCredentialStorage -ContextProvider $context -Exists $exists -OpenNode {
        param($p) $n=Node
        if($p -ceq $paths.Profile) { $n.Owner='S-1-5-18'; $n.Reparse=$true }
        $n
    } | Out-Null
}
Reject 'system_profile_unsafe_group_permissions_still_rejected' {
    Assert-DemoQrCredentialStorage -ContextProvider $context -Exists $exists -OpenNode {
        param($p) $n=Node
        if($p -ceq $paths.Profile) { $n.Owner='S-1-5-18'; $n.Rules+=Ace 'S-1-5-11' 0x10000 }
        $n
    } | Out-Null
}
Reject 'wrong_destination' { Assert-DemoQrCredentialStorage -Path 'C:\wrong' -ContextProvider $context -Exists $exists -OpenNode $opener | Out-Null }
Pass 'missing_directory_distinct_status' {
    try {
        Assert-DemoQrCredentialStorage -ContextProvider $context -Exists {param($p) $p -cne $paths.Directory} -OpenNode $opener | Out-Null
        throw 'expected_rejection'
    } catch { if($_.Exception.Message -cne 'storage_preparation_required') { throw 'wrong_category' } }
}
Reject 'existing_credential_creation' { Assert-DemoQrCredentialStorage -Mode Create -ContextProvider $context -Exists $exists -OpenNode $opener | Out-Null }
Reject 'missing_read_credential' { Assert-DemoQrCredentialStorage -Mode Read -ContextProvider $context -Exists {param($p) $p -cne $paths.Credential} -OpenNode $opener | Out-Null }
Reject 'metadata_provider_failure' { Assert-DemoQrCredentialStorage -ContextProvider $context -Exists $exists -OpenNode {param($p) throw 'synthetic'} | Out-Null }
Reject 'credential_wrong_owner' {
    Assert-DemoQrCredentialStorage -ContextProvider $context -Exists $exists -OpenNode {
        param($p) $n=Node; if($p -ceq $paths.Credential) { $n.Directory=$false; $n.Owner='S-1-5-18' }; $n
    } | Out-Null
}
Write-Output ('PASS: '+$script:passed+' offline storage policy cases; no real filesystem/ACL/native operations')
