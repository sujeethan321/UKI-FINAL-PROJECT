# Functions only. Dot-sourcing performs no filesystem/native/credential operation.
function Set-DemoQrStorageStage {
    param($Trace,[string]$Stage,[string]$Surface)
    if ($null -ne $Trace) {
        $Trace.Stage=$Stage
        if ($Surface) { $Trace.Surface=$Surface }
    }
}

function Get-DemoQrStorageFailureCheck {
    param([string]$Message)
    $allowed=@('operator_profile','operator_identity','metadata_or_reparse','acl_metadata',
        'ancestor_owner','private_owner_or_inheritance','private_dacl',
        'ancestor_mutation_or_delete','metadata_handle','handle_identity','metadata_unavailable',
        'credential_destination','ancestor_not_directory','operator_profile_owner',
        'storage_preparation_required','credential_exists','credential_missing','credential_not_file')
    if ($Message -cin $allowed) { return $Message }
    return 'metadata_api_or_runtime_error'
}

function Get-DemoQrStorageDiagnosticLine {
    param($Trace,[string]$Message)
    $stages=@('helper_load','operator_identity','profile_registry_open','profile_registry_value',
        'expected_path_construction','native_initialization','native_handle_open','native_final_path',
        'item_metadata','dacl_read','dacl_canonical_order','ace_metadata_conversion','owner_metadata',
        'operator_context','destination_validation','ancestor_enumeration','ancestor_existence',
        'ancestor_open','directory_type','profile_owner','ancestor_acl_policy','storage_existence',
        'credential_existence','credential_open','credential_type','credential_acl_policy')
    $stage='unknown'; $surface='unknown'; $native='unknown'
    if ($Trace.Stage -cin $stages) { $stage=$Trace.Stage }
    if ($Trace.Surface -cin @('none','operator','operator_profile','credential_destination','ancestors','private_directory','credential_file') -or
        $Trace.Surface -cmatch '^ancestor_[0-9]{1,3}$') { $surface=$Trace.Surface }
    if ($Trace.NativeError -cin @('none','not_found','path_not_found','access_denied','sharing_violation','invalid_parameter','other')) { $native=$Trace.NativeError }
    $check=Get-DemoQrStorageFailureCheck $Message
    return ('STOP: QR storage diagnostic stage='+$stage+' surface='+$surface+' check='+$check+' native_error='+$native)
}

function Get-DemoQrStoragePaths {
    param([string]$OperatorSid,[string]$Profile)
    if ($OperatorSid -cnotmatch '^S-1-5-21-[0-9-]+$' -or
        $Profile -cnotmatch '^[A-Za-z]:\\' -or $Profile.Contains('%') -or
        [IO.Path]::GetFullPath($Profile) -cne $Profile -or
        $Profile.Substring(2).Contains(':')) { throw 'operator_profile' }
    $directory=Join-Path $Profile 'AppData\Local\LankaPex\PrivateDemoQr'
    [pscustomobject]@{OperatorSid=$OperatorSid;Profile=$Profile;Directory=$directory;
        Credential=(Join-Path $directory 'demo-qr-migrator.dpapi')}
}

function Resolve-DemoQrStoragePaths {
    param($Trace)
    Set-DemoQrStorageStage $Trace 'operator_identity' 'operator'
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    if ($identity.IsSystem -or -not $identity.IsAuthenticated) { throw 'operator_identity' }
    $sid=$identity.User.Value
    Set-DemoQrStorageStage $Trace 'profile_registry_open' 'operator_profile'
    $key=[Microsoft.Win32.Registry]::LocalMachine.OpenSubKey(
        ('SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$sid))
    if ($null -eq $key) { throw 'operator_profile' }
    try {
        Set-DemoQrStorageStage $Trace 'profile_registry_value' 'operator_profile'
        $profile=$key.GetValue('ProfileImagePath',$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    } finally { $key.Dispose() }
    # Never use LOCALAPPDATA, USERPROFILE or expand attacker-controlled variables.
    Set-DemoQrStorageStage $Trace 'expected_path_construction' 'operator_profile'
    Get-DemoQrStoragePaths $sid $profile
}

function ConvertTo-DemoQrAccessMask {
    param([long]$Mask)
    $value=$Mask -band 4294967295L
    if ($value -band 0x10000000L) { $value=$value -bor 0x1F01FFL }
    if ($value -band 0x40000000L) { $value=$value -bor 0x120116L }
    if ($value -band 0x80000000L) { $value=$value -bor 0x120089L }
    if ($value -band 0x20000000L) { $value=$value -bor 0x1200A0L }
    return $value
}

function Test-DemoQrStorageNode {
    param($Node,[string]$OperatorSid,[switch]$Private,[switch]$File)
    # Administrators/SYSTEM and Windows servicing owner are trusted on ordinary
    # ancestors, not allowed extra principals on the private directory/file.
    $trusted=@($OperatorSid,'S-1-5-18','S-1-5-32-544',
        'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464')
    if (-not $Node.MetadataVerified -or $Node.Reparse) { throw 'metadata_or_reparse' }
    if ($null -eq $Node.Rules -or @($Node.Rules).Count -eq 0) { throw 'acl_metadata' }
    if ($Node.Owner -notin $trusted) { throw 'ancestor_owner' }
    if ($Private -and ($Node.Owner -cne $OperatorSid -or -not $Node.Protected)) { throw 'private_owner_or_inheritance' }
    $operatorFull=0; $systemFull=0; $count=0
    foreach ($ace in $Node.Rules) {
        if (-not $ace.Sid -or $ace.Type -notin @('Allow','Deny')) { throw 'acl_metadata' }
        $mask=ConvertTo-DemoQrAccessMask $ace.Mask
        if ($Private) {
            # Exactly two explicit, applicable, complete access rules.
            if ($ace.Inherited -or $ace.InheritOnly -or $ace.Type -cne 'Allow' -or
                $ace.Sid -notin @($OperatorSid,'S-1-5-18') -or
                $mask -ne 0x1F01FFL) { throw 'private_dacl' }
            $count++
            if ($ace.Sid -ceq $OperatorSid) { $operatorFull++ } else { $systemFull++ }
        } elseif (-not $ace.InheritOnly -and $ace.Type -ceq 'Allow' -and $ace.Sid -notin $trusted) {
            # All non-trusted identities/groups are assessed as potentially
            # usable by an untrusted token. Deny ACEs never cancel this test.
            # DELETE on object, WRITE_DAC/OWNER, attribute/EA alteration, and
            # parent DELETE_CHILD can compromise path identity. Ordinary
            # read/traverse and creation of unrelated siblings are permitted.
            $danger=0xD0150L
            if ($File) { $danger=$danger -bor 0x6L }
            if ($mask -band $danger) { throw 'ancestor_mutation_or_delete' }
        }
    }
    if ($Private -and ($count -ne 2 -or $operatorFull -ne 1 -or $systemFull -ne 1)) { throw 'private_dacl' }
}

function Initialize-DemoQrStorageNative {
    if ('DemoQrStorageNative' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
using System.Text;
public static class DemoQrStorageNative {
 [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
 public static extern SafeFileHandle CreateFileW(string p,uint a,uint s,IntPtr sec,uint mode,uint flags,IntPtr template);
 [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
 public static extern uint GetFinalPathNameByHandleW(SafeFileHandle h,StringBuilder b,uint n,uint flags);
}
'@
}

function Open-DemoQrStorageNode {
    param([string]$Path,$Trace)
    Set-DemoQrStorageStage $Trace 'native_initialization'
    Initialize-DemoQrStorageNative
    # READ_CONTROL + READ_ATTRIBUTES, share read/write but NOT delete. Pin every
    # existing ancestor until the consumer finishes; never open for mutation.
    Set-DemoQrStorageStage $Trace 'native_handle_open'
    $handle=[DemoQrStorageNative]::CreateFileW($Path,0x20080,3,[IntPtr]::Zero,3,0x02200000,[IntPtr]::Zero)
    if ($handle.IsInvalid) {
        $nativeCode=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
        if ($null -ne $Trace) {
            $Trace.NativeError=switch($nativeCode) { 2 {'not_found'} 3 {'path_not_found'} 5 {'access_denied'} 32 {'sharing_violation'} 87 {'invalid_parameter'} default {'other'} }
        }
        $handle.Dispose(); throw 'metadata_handle'
    }
    try {
        Set-DemoQrStorageStage $Trace 'native_final_path'
        $buffer=New-Object Text.StringBuilder 32768
        $length=[DemoQrStorageNative]::GetFinalPathNameByHandleW($handle,$buffer,32768,0)
        if ($length -eq 0 -or $length -ge 32768 -or
            $buffer.ToString().Substring(4).TrimEnd('\') -ine $Path.TrimEnd('\')) { throw 'handle_identity' }
        Set-DemoQrStorageStage $Trace 'item_metadata'
        $item=Get-Item -LiteralPath $Path -Force -ErrorAction Stop
        Set-DemoQrStorageStage $Trace 'dacl_read'
        $acl=Get-Acl -LiteralPath $Path -ErrorAction Stop
        Set-DemoQrStorageStage $Trace 'dacl_canonical_order'
        if (-not $acl.AreAccessRulesCanonical) { throw 'acl_metadata' }
        $rules=@()
        Set-DemoQrStorageStage $Trace 'ace_metadata_conversion'
        foreach ($rule in $acl.Access) {
            $rules += [pscustomobject]@{Sid=$rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value;
                Mask=[long]$rule.FileSystemRights;Type=[string]$rule.AccessControlType;
                Inherited=$rule.IsInherited;
                InheritOnly=[bool]($rule.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly)}
        }
        Set-DemoQrStorageStage $Trace 'owner_metadata'
        [pscustomobject]@{Handle=$handle;Directory=$item.PSIsContainer;MetadataVerified=$true;
            Reparse=[bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint);
            Owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;
            Protected=$acl.AreAccessRulesProtected;Rules=$rules}
    } catch { $handle.Dispose(); throw 'metadata_unavailable' }
}

function Close-DemoQrStorageLease {
    param($Lease)
    if ($null -ne $Lease) { foreach ($handle in $Lease.Handles) { $handle.Dispose() } }
}

function Assert-DemoQrCredentialStorage {
    param([string]$Path,[ValidateSet('Prepare','Create','Read','DirectoryPlan')][string]$Mode='Prepare',
          [scriptblock]$ContextProvider={param($t) Resolve-DemoQrStoragePaths -Trace $t},
          [scriptblock]$Exists={param($p) Test-Path -LiteralPath $p -ErrorAction Stop},
          [scriptblock]$OpenNode={param($p,$t) Open-DemoQrStorageNode $p -Trace $t},$Trace)
    Set-DemoQrStorageStage $Trace 'operator_context' 'operator'
    $context=& $ContextProvider $Trace
    Set-DemoQrStorageStage $Trace 'destination_validation' 'credential_destination'
    if (-not $Path) { $Path=$context.Credential }
    if ($Path -cne $context.Credential) { throw 'credential_destination' }
    $handles=New-Object 'Collections.Generic.List[IDisposable]'
    try {
        Set-DemoQrStorageStage $Trace 'ancestor_enumeration' 'ancestors'
        $ancestors=New-Object 'Collections.Generic.List[string]'
        $cursor=$context.Directory
        while ($cursor) { $ancestors.Insert(0,$cursor); $cursor=Split-Path -Parent $cursor }
        $missing=$false
        $missingDirectories=New-Object 'Collections.Generic.List[string]'
        $index=0
        foreach ($part in $ancestors) {
            $surface='ancestor_'+$index
            if ($part -ceq $context.Profile) { $surface='operator_profile' }
            if ($part -ceq $context.Directory) { $surface='private_directory' }
            $index++
            Set-DemoQrStorageStage $Trace 'ancestor_existence' $surface
            if ($missing -or -not (& $Exists $part)) {
                $missing=$true; $missingDirectories.Add($part); continue
            }
            Set-DemoQrStorageStage $Trace 'ancestor_open' $surface
            $node=& $OpenNode $part $Trace
            $handles.Add($node.Handle)
            Set-DemoQrStorageStage $Trace 'directory_type' $surface
            if (-not $node.Directory) { throw 'ancestor_not_directory' }
            Set-DemoQrStorageStage $Trace 'profile_owner' $surface
            # Only the exact registered profile may also be SYSTEM-owned.
            # Private storage below it still requires exact operator ownership.
            if ($part -ceq $context.Profile -and
                $node.Owner -cnotin @($context.OperatorSid,'S-1-5-18')) { throw 'operator_profile_owner' }
            Set-DemoQrStorageStage $Trace 'ancestor_acl_policy' $surface
            Test-DemoQrStorageNode $node $context.OperatorSid -Private:($part -ceq $context.Directory)
            # Creation must not silently adopt a broadly accessible existing
            # application parent. No existing ACL is modified to satisfy this.
            if ($Mode -ceq 'DirectoryPlan' -and $part -ceq (Split-Path -Parent $context.Directory)) {
                Test-DemoQrStorageNode $node $context.OperatorSid -Private
            }
        }
        Set-DemoQrStorageStage $Trace 'storage_existence' 'private_directory'
        if ($Mode -ceq 'DirectoryPlan') {
            if (-not $missing) { throw 'storage_directory_exists' }
            return [pscustomobject]@{Credential=$context.Credential;Directory=$context.Directory;
                Profile=$context.Profile;OperatorSid=$context.OperatorSid;Handles=$handles;
                MissingDirectories=$missingDirectories}
        }
        if ($missing) { throw 'storage_preparation_required' }
        Set-DemoQrStorageStage $Trace 'credential_existence' 'credential_file'
        $hasCredential=& $Exists $Path
        if ($Mode -ceq 'Create' -and $hasCredential) { throw 'credential_exists' }
        if ($Mode -ceq 'Read' -and -not $hasCredential) { throw 'credential_missing' }
        if ($hasCredential) {
            Set-DemoQrStorageStage $Trace 'credential_open' 'credential_file'
            $node=& $OpenNode $Path $Trace
            $handles.Add($node.Handle)
            Set-DemoQrStorageStage $Trace 'credential_type' 'credential_file'
            if ($node.Directory) { throw 'credential_not_file' }
            Set-DemoQrStorageStage $Trace 'credential_acl_policy' 'credential_file'
            Test-DemoQrStorageNode $node $context.OperatorSid -Private -File
        }
        return [pscustomobject]@{Credential=$Path;Directory=$context.Directory;OperatorSid=$context.OperatorSid;Handles=$handles}
    } catch {
        foreach ($handle in $handles) { $handle.Dispose() }
        throw
    }
}
