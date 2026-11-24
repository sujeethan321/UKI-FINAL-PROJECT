# In-memory synthetic filesystem only. No native create, ACL or registry access.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '..\scripts\demo_qr_credential_storage.ps1')
. (Join-Path $PSScriptRoot '..\scripts\demo_qr_storage_directory_creation.ps1')
$script:passed=0
$sid='S-1-5-21-1-2-3-1001'
function New-Node {
    [pscustomobject]@{MetadataVerified=$true;Directory=$true;Reparse=$false;Owner=$sid;Protected=$true;
        Rules=@([pscustomobject]@{Sid=$sid;Mask=0x1F01FF;Type='Allow';Inherited=$false;InheritOnly=$false},
                [pscustomobject]@{Sid='S-1-5-18';Mask=0x1F01FF;Type='Allow';Inherited=$false;InheritOnly=$false})}
}
function Reset-Fixture([switch]$MissingParent,[switch]$ExistingTarget) {
    $paths=Get-DemoQrStoragePaths $sid 'C:\Users\synthetic'
    $script:fixture=[pscustomobject]@{Context=$paths;Nodes=@{};Creates=0;PlanCalls=0;
        FailCreateAt=0;BadCreatedAcl=$false;BadCreatedOwner=$false;RaceOnCreate=$false;FinalFailure=$false;
        State=@{Stage='start';Created=0}}
    $cursor=Split-Path -Parent $paths.Directory
    if ($MissingParent) { $cursor=Split-Path -Parent $cursor }
    while($cursor) { $script:fixture.Nodes[$cursor]=New-Node; $cursor=Split-Path -Parent $cursor }
    $script:fixture.Nodes[$paths.Profile].Owner='S-1-5-18'
    if ($ExistingTarget) { $script:fixture.Nodes[$paths.Directory]=New-Node }
}
$exists={param($p) $script:fixture.Nodes.ContainsKey($p)}
$context={param($t) $script:fixture.Context}
$opener={param($p,$t)
    if(-not $script:fixture.Nodes.ContainsKey($p)) { throw 'synthetic_missing' }
    $source=$script:fixture.Nodes[$p]
    [pscustomobject]@{MetadataVerified=$source.MetadataVerified;Directory=$source.Directory;
        Reparse=$source.Reparse;Owner=$source.Owner;Protected=$source.Protected;Rules=$source.Rules;
        Handle=(New-Object IO.MemoryStream)}
}
$planner={
    $script:fixture.PlanCalls++
    Assert-DemoQrCredentialStorage -Mode DirectoryPlan -ContextProvider $context -Exists $exists -OpenNode $opener
}
$creator={param($p,$owner)
    $script:fixture.Creates++
    if($script:fixture.RaceOnCreate) { $script:fixture.Nodes[$p]=New-Node; throw 'exclusive_directory_exists' }
    if($script:fixture.Nodes.ContainsKey($p)) { throw 'exclusive_directory_exists' }
    if($script:fixture.Creates -eq $script:fixture.FailCreateAt) { throw 'exclusive_directory_creation_failed' }
    if($owner -cne $sid) { throw 'wrong_operator' }
    $script:fixture.Nodes[$p]=New-Node
    if($script:fixture.BadCreatedAcl) { $script:fixture.Nodes[$p].Protected=$false }
    if($script:fixture.BadCreatedOwner) { $script:fixture.Nodes[$p].Owner='S-1-5-18' }
}
$final={
    if($script:fixture.FinalFailure) { throw 'synthetic_final_verification_failed' }
    Assert-DemoQrCredentialStorage -Mode Create -ContextProvider $context -Exists $exists -OpenNode $opener
}
function Invoke-TestPreparation([switch]$Execute,[string]$Confirm='PrivateDemoQr') {
    Invoke-DemoQrDirectoryPreparation -Execute:$Execute -ConfirmDirectoryCreation:$Execute -ConfirmMissingComponents $Confirm `
        -PlanProvider $planner -Creator $creator -OpenNode $opener -FinalValidator $final -State $script:fixture.State
}
function Pass($Label,[scriptblock]$Body) {
    try { & $Body; $script:passed++ } catch { throw ('offline_case_failed:'+ $Label) }
}
function Reject($Label,[scriptblock]$Body) {
    $failed=$false; try { & $Body } catch { $failed=$true }
    if(-not $failed) { throw ('offline_rejection_failed:'+ $Label) }
    $script:passed++
}
Pass 'preflight_missing_private_no_mutation' {
    Reset-Fixture
    $result=Invoke-TestPreparation
    if($result -cnotmatch 'missing_components=PrivateDemoQr;' -or $script:fixture.Creates -ne 0) { throw 'plan' }
}
Pass 'preflight_missing_parent_exact_plan' {
    Reset-Fixture -MissingParent
    $result=Invoke-TestPreparation
    if($result -cnotmatch 'missing_components=LankaPex,PrivateDemoQr;' -or $script:fixture.Creates -ne 0) { throw 'plan' }
}
Pass 'successful_private_creation_revalidates' {
    Reset-Fixture
    $result=Invoke-TestPreparation -Execute
    if($result -cnotmatch '^PASS:' -or $script:fixture.Creates -ne 1 -or
        $script:fixture.PlanCalls -ne 2 -or $script:fixture.Nodes.ContainsKey($script:fixture.Context.Credential)) { throw 'create' }
}
Pass 'successful_parent_and_private_creation' {
    Reset-Fixture -MissingParent
    $result=Invoke-TestPreparation -Execute -Confirm 'LankaPex,PrivateDemoQr'
    if($result -cnotmatch '^PASS:' -or $script:fixture.Creates -ne 2 -or $script:fixture.PlanCalls -ne 3) { throw 'create' }
}
Reject 'wrong_destination' {
    Reset-Fixture
    $plan=& $planner
    try { $plan.Directory='C:\unexpected'; Get-DemoQrDirectoryPlanLabel $plan | Out-Null } finally { Close-DemoQrStorageLease $plan }
}
Reject 'wrong_confirmation' { Reset-Fixture; Invoke-TestPreparation -Execute -Confirm 'wrong' | Out-Null }
Pass 'missing_confirmation_no_plan_or_write' {
    Reset-Fixture
    try { Invoke-DemoQrDirectoryPreparation -Execute -PlanProvider $planner -Creator $creator | Out-Null; throw 'expected' }
    catch { if($_.Exception.Message -cne 'directory_confirmation') { throw 'confirmation' } }
    if($script:fixture.Creates -ne 0 -or $script:fixture.PlanCalls -ne 0) { throw 'early_write' }
}
Reject 'missing_operating_system_parent' {
    Reset-Fixture -MissingParent
    $script:fixture.Nodes.Remove((Join-Path $script:fixture.Context.Profile 'AppData\Local'))
    Invoke-TestPreparation -Execute -Confirm 'LankaPex,PrivateDemoQr' | Out-Null
}
Reject 'existing_target_even_if_secure' { Reset-Fixture -ExistingTarget; Invoke-TestPreparation -Execute | Out-Null }
Reject 'reparse_ancestor' {
    Reset-Fixture; $script:fixture.Nodes[$script:fixture.Context.Profile].Reparse=$true
    Invoke-TestPreparation -Execute | Out-Null
}
Reject 'wrong_existing_application_parent_owner' {
    Reset-Fixture; $script:fixture.Nodes[(Split-Path -Parent $script:fixture.Context.Directory)].Owner='S-1-5-18'
    Invoke-TestPreparation -Execute | Out-Null
}
Reject 'inherited_application_parent_acl' {
    Reset-Fixture; $script:fixture.Nodes[(Split-Path -Parent $script:fixture.Context.Directory)].Protected=$false
    Invoke-TestPreparation -Execute | Out-Null
}
Reject 'excessive_application_parent_permissions' {
    Reset-Fixture; $script:fixture.Nodes[(Split-Path -Parent $script:fixture.Context.Directory)].Rules+=
        [pscustomobject]@{Sid='S-1-5-32-544';Mask=0x1F01FF;Type='Allow';Inherited=$false;InheritOnly=$false}
    Invoke-TestPreparation -Execute | Out-Null
}
Reject 'unsafe_ancestor_delete_child' {
    Reset-Fixture; $script:fixture.Nodes[$script:fixture.Context.Profile].Rules+=
        [pscustomobject]@{Sid='S-1-5-11';Mask=0x40;Type='Allow';Inherited=$false;InheritOnly=$false}
    Invoke-TestPreparation -Execute | Out-Null
}
Pass 'failed_exclusive_creation_no_retry' {
    Reset-Fixture; $script:fixture.FailCreateAt=1
    try { Invoke-TestPreparation -Execute | Out-Null; throw 'expected' } catch { if($_.Exception.Message -cne 'exclusive_directory_creation_failed'){throw 'failure'} }
    if($script:fixture.Creates -ne 1 -or $script:fixture.State.Created -ne 0) { throw 'retry' }
}
Pass 'post_create_acl_mismatch_preserves_directory' {
    Reset-Fixture; $script:fixture.BadCreatedAcl=$true
    try { Invoke-TestPreparation -Execute | Out-Null; throw 'expected' } catch { if($_.Exception.Message -cne 'private_owner_or_inheritance'){throw 'post_acl'} }
    if(-not $script:fixture.Nodes.ContainsKey($script:fixture.Context.Directory) -or $script:fixture.State.Created -ne 1) { throw 'removed' }
}
Pass 'partial_parent_creation_preserved' {
    Reset-Fixture -MissingParent; $script:fixture.FailCreateAt=2
    try { Invoke-TestPreparation -Execute -Confirm 'LankaPex,PrivateDemoQr' | Out-Null; throw 'expected' } catch { if($_.Exception.Message -cne 'exclusive_directory_creation_failed'){throw 'partial'} }
    if(-not $script:fixture.Nodes.ContainsKey((Split-Path -Parent $script:fixture.Context.Directory)) -or
        $script:fixture.Nodes.ContainsKey($script:fixture.Context.Directory) -or $script:fixture.Creates -ne 2) { throw 'partial_state' }
}
Pass 'existing_target_rejected_without_native_create' {
    Reset-Fixture -ExistingTarget
    try { Invoke-TestPreparation -Execute | Out-Null; throw 'expected' } catch { if($_.Exception.Message -cne 'storage_directory_exists'){throw 'existing'} }
    if($script:fixture.Creates -ne 0) { throw 'overwrite' }
}
Pass 'created_owner_mismatch_preserved' {
    Reset-Fixture; $script:fixture.BadCreatedOwner=$true
    try { Invoke-TestPreparation -Execute | Out-Null; throw 'expected' } catch { if($_.Exception.Message -cne 'private_owner_or_inheritance'){throw 'owner'} }
    if($script:fixture.State.Created -ne 1 -or -not $script:fixture.Nodes.ContainsKey($script:fixture.Context.Directory)) { throw 'preservation' }
}
Pass 'racing_existing_directory_never_adopted' {
    Reset-Fixture; $script:fixture.RaceOnCreate=$true
    try { Invoke-TestPreparation -Execute | Out-Null; throw 'expected' } catch { if($_.Exception.Message -cne 'exclusive_directory_exists'){throw 'race'} }
    if($script:fixture.Creates -ne 1 -or $script:fixture.State.Stage -cne 'exclusive_creation_attempted') { throw 'retry' }
}
Pass 'final_verification_failure_preserves_created_directory' {
    Reset-Fixture; $script:fixture.FinalFailure=$true
    try { Invoke-TestPreparation -Execute | Out-Null; throw 'expected' } catch { if($_.Exception.Message -cne 'synthetic_final_verification_failed'){throw 'final'} }
    if($script:fixture.State.Stage -cne 'complete_path_verification' -or $script:fixture.State.Created -ne 1) { throw 'final_state' }
}
Pass 'plan_discrepancy_no_write' {
    Reset-Fixture -MissingParent
    try { Invoke-TestPreparation -Execute -Confirm 'PrivateDemoQr' | Out-Null; throw 'expected' } catch { if($_.Exception.Message -cne 'directory_plan_confirmation_mismatch'){throw 'plan'} }
    if($script:fixture.Creates -ne 0) { throw 'write' }
}
Pass 'actual_descriptor_in_memory_only' {
    $security=New-DemoQrDirectorySecurity $sid
    if(-not $security.AreAccessRulesProtected -or $security.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne $sid) { throw 'descriptor_owner' }
    $node=New-Node
    $node.Rules=@($security.Access | ForEach-Object {
        [pscustomobject]@{Sid=$_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value;
            Mask=[long]$_.FileSystemRights;Type=[string]$_.AccessControlType;Inherited=$_.IsInherited;
            InheritOnly=[bool]($_.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly)}
    })
    Test-DemoQrStorageNode $node $sid -Private
}
Write-Output ('PASS: '+$script:passed+' mocked directory preparation cases; no real filesystem/ACL/native operations')
