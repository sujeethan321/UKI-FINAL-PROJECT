# Functions only; dot-sourcing does not inspect private files or call native APIs.
function Initialize-DemoDaclNative {
    if ('LankaPexDemoDacl.Native' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
namespace LankaPexDemoDacl {
 public static class Native {
  [StructLayout(LayoutKind.Sequential)] public struct Info {
   public uint Attributes; public System.Runtime.InteropServices.ComTypes.FILETIME Creation, Access, Write;
   public uint Volume, SizeHigh, SizeLow, Links, IndexHigh, IndexLow;
  }
  [StructLayout(LayoutKind.Sequential)] public struct Attributes {
   public int Length; public IntPtr Descriptor; public int Inherit;
  }
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  public static extern SafeFileHandle CreateFile(string name, uint access, uint share, IntPtr security, uint disposition, uint flags, IntPtr template);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool GetFileInformationByHandle(SafeFileHandle handle, out Info info);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  public static extern bool CreateDirectory(string name, ref Attributes security);
  [DllImport("advapi32.dll", SetLastError=true)]
  public static extern bool GetSecurityDescriptorDacl(IntPtr descriptor, out bool present, out IntPtr dacl, out bool defaulted);
  [DllImport("advapi32.dll")]
  public static extern uint SetSecurityInfo(SafeFileHandle handle, uint kind, uint flags, IntPtr owner, IntPtr group, IntPtr dacl, IntPtr sacl);
 }
}
'@ | Out-Null
}

function Assert-DemoDaclPath {
    param([string]$Path,[string]$Expected)
    if ($Expected -cne 'C:\Users\admin\Desktop\LankaPex\.server-logs\private-demo\demo-app.dpapi' -or
        -not [IO.Path]::IsPathRooted($Path) -or
        -not [string]::Equals($Path,$Expected,[StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFullPath($Path) -ne $Expected) { throw 'path' }
}

function Assert-DemoDaclNoReparse {
    param([string]$Path)
    $cursor=$Path
    while ($cursor) {
        $item=Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'reparse' }
        $next=Split-Path -Parent $cursor
        if ($next -eq $cursor) { break }
        $cursor=$next
    }
}

function Get-DemoDaclOperator {
    return [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
}

function Get-DemoDaclMetadata {
    param([string]$Path)
    $acl=Get-Acl -LiteralPath $Path -ErrorAction Stop
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
        [pscustomobject]@{Sid=$_.IdentityReference.Value;Inherited=$_.IsInherited;
            Allow=($_.AccessControlType -eq 'Allow');Rights=$_.FileSystemRights}
    })
    return [pscustomobject]@{Owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;
        Protected=$acl.AreAccessRulesProtected;Rules=$rules;
        Sddl=$acl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access)}
}

function Assert-DemoDaclPrivate {
    param($Metadata,[string]$Operator)
    if (-not $Metadata.Protected -or $Metadata.Owner -ne $Operator) { throw 'private_acl' }
    $operatorFull=$false; $systemFull=$false
    foreach ($rule in $Metadata.Rules) {
        $full=($rule.Rights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl
        if ($rule.Inherited -or -not $rule.Allow -or -not $full) { throw 'private_acl' }
        if ($rule.Sid -eq $Operator) { $operatorFull=$true }
        elseif ($rule.Sid -eq 'S-1-5-18') { $systemFull=$true }
        else { throw 'private_acl' }
    }
    if (-not $operatorFull -or -not $systemFull) { throw 'private_acl' }
}

function New-DemoDaclSecurity {
    param([string]$Operator,[switch]$Directory,[string]$RestoreSddl)
    $security=if ($Directory) { New-Object Security.AccessControl.DirectorySecurity } else { New-Object Security.AccessControl.FileSecurity }
    if ($RestoreSddl) {
        $security.SetSecurityDescriptorSddlForm($RestoreSddl,[Security.AccessControl.AccessControlSections]::Access)
    } else {
        # Applied at creation to NEW backup objects only; the target update
        # never requests owner/group security information.
        $security.SetOwner([Security.Principal.SecurityIdentifier]::new($Operator))
        $security.SetAccessRuleProtection($true,$false)
        foreach ($sid in @($Operator,'S-1-5-18')) {
            $identity=New-Object Security.Principal.SecurityIdentifier($sid)
            $inheritance=if ($Directory) { [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit' } else { [Security.AccessControl.InheritanceFlags]::None }
            $rule=New-Object Security.AccessControl.FileSystemAccessRule($identity,[Security.AccessControl.FileSystemRights]::FullControl,$inheritance,[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)
            $security.AddAccessRule($rule)
        }
    }
    return $security
}

function Open-DemoDaclTarget {
    param([string]$Path)
    Initialize-DemoDaclNative
    # READ_CONTROL | WRITE_DAC, no read/write-data rights. Share read only:
    # reject existing writers and prevent data writes, deletion and replacement.
    $handle=[LankaPexDemoDacl.Native]::CreateFile($Path,0x60000,1,[IntPtr]::Zero,3,0x200000,[IntPtr]::Zero)
    if ($handle.IsInvalid) { $handle.Dispose(); throw 'handle' }
    return $handle
}

function Get-DemoDaclIdentity {
    param($Handle)
    $info=New-Object LankaPexDemoDacl.Native+Info
    if (-not [LankaPexDemoDacl.Native]::GetFileInformationByHandle($Handle,[ref]$info)) { throw 'identity' }
    if (($info.Attributes -band 0x410) -ne 0 -or $info.Links -ne 1) { throw 'identity' }
    return ('{0}:{1}:{2}:{3}:{4}:{5}:{6}' -f $info.Volume,$info.IndexHigh,$info.IndexLow,$info.SizeHigh,$info.SizeLow,$info.Write.dwHighDateTime,$info.Write.dwLowDateTime)
}

function Open-DemoDaclBackupDirectory {
    param([string]$Path)
    Initialize-DemoDaclNative
    $handle=[LankaPexDemoDacl.Native]::CreateFile($Path,0x20000,3,[IntPtr]::Zero,3,0x2200000,[IntPtr]::Zero)
    if ($handle.IsInvalid) { $handle.Dispose(); throw 'backup_handle' }
    $info=New-Object LankaPexDemoDacl.Native+Info
    if (-not [LankaPexDemoDacl.Native]::GetFileInformationByHandle($handle,[ref]$info) -or
        ($info.Attributes -band 0x400) -ne 0 -or ($info.Attributes -band 0x10) -eq 0) {
        $handle.Dispose(); throw 'backup_handle'
    }
    return $handle
}

function New-DemoDaclBackupDirectory {
    param([string]$Path,[string]$Operator)
    Initialize-DemoDaclNative
    $bytes=(New-DemoDaclSecurity $Operator -Directory).GetSecurityDescriptorBinaryForm()
    $pin=[Runtime.InteropServices.GCHandle]::Alloc($bytes,[Runtime.InteropServices.GCHandleType]::Pinned)
    try {
        $attributes=New-Object LankaPexDemoDacl.Native+Attributes
        $attributes.Length=[Runtime.InteropServices.Marshal]::SizeOf($attributes)
        $attributes.Descriptor=$pin.AddrOfPinnedObject()
        # Exclusive creation with protected DACL; an existing directory fails.
        if (-not [LankaPexDemoDacl.Native]::CreateDirectory($Path,[ref]$attributes)) { throw 'backup_directory' }
    } finally { $pin.Free() }
}

function Write-DemoDaclBackup {
    param([string]$Path,[string]$Operator,$Backup)
    $security=New-DemoDaclSecurity $Operator
    # .NET Framework/Windows PowerShell 5.1: exclusive creation with protected DACL.
    $stream=[IO.FileStream]::new($Path,[IO.FileMode]::CreateNew,[Security.AccessControl.FileSystemRights]::Write,[IO.FileShare]::None,4096,[IO.FileOptions]::None,$security)
    try {
        $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Backup | ConvertTo-Json -Compress))
        $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true)
    } finally { $stream.Dispose() }
}

function Read-DemoDaclBackup {
    param([string]$Path)
    # Only the separate ACL-metadata backup is read, never credential contents.
    return ([IO.File]::ReadAllText($Path,[Text.Encoding]::UTF8) | ConvertFrom-Json)
}

function Set-DemoDaclOnHandle {
    param($Handle,[string]$Operator,[string]$RestoreSddl)
    $security=New-DemoDaclSecurity $Operator -RestoreSddl $RestoreSddl
    $bytes=$security.GetSecurityDescriptorBinaryForm()
    $pin=[Runtime.InteropServices.GCHandle]::Alloc($bytes,[Runtime.InteropServices.GCHandleType]::Pinned)
    try {
        $present=$false; $defaulted=$false; $dacl=[IntPtr]::Zero
        if (-not [LankaPexDemoDacl.Native]::GetSecurityDescriptorDacl($pin.AddrOfPinnedObject(),[ref]$present,[ref]$dacl,[ref]$defaulted) -or -not $present -or $dacl -eq [IntPtr]::Zero) { throw 'dacl' }
        # DACL_SECURITY_INFORMATION plus PROTECTED/UNPROTECTED_DACL only.
        $flags=if ($security.AreAccessRulesProtected) { [uint32]2147483652 } else { [uint32]536870916 }
        if ([LankaPexDemoDacl.Native]::SetSecurityInfo($Handle,1,$flags,[IntPtr]::Zero,[IntPtr]::Zero,$dacl,[IntPtr]::Zero) -ne 0) { throw 'dacl' }
    } finally { $pin.Free() }
}

function Invoke-DemoCredentialDaclCorrection {
    param([string]$Target,[string]$Expected,[string]$BackupDirectory,[string]$BackupFile)
    $stage='target_path'; $handle=$null; $backupHandle=$null; $mutationStarted=$false; $backupVerified=$false
    try {
        Assert-DemoDaclPath $Target $Expected
        $stage='target_metadata'
        Assert-DemoDaclNoReparse $Target
        if (-not (Test-Path -LiteralPath $Target -PathType Leaf)) { throw 'missing' }
        $operator=Get-DemoDaclOperator
        $before=Get-DemoDaclMetadata $Target
        $parentBefore=Get-DemoDaclMetadata (Split-Path -Parent $Target)
        $stage='owner'
        if ($before.Owner -ne $operator) { throw 'owner' }
        $stage='existing_dacl'
        if ($before.Protected) { throw 'already_protected_requires_review' }
        foreach ($rule in $before.Rules) {
            if (-not $rule.Inherited -and (-not $rule.Allow -or $rule.Sid -notin @($operator,'S-1-5-18'))) { throw 'explicit_rule' }
        }
        $stage='target_handle'
        $handle=Open-DemoDaclTarget $Target
        $identity=Get-DemoDaclIdentity $handle
        $stage='backup_directory'
        $backupParent=Split-Path -Parent $BackupDirectory
        $expectedParent=Split-Path -Parent (Split-Path -Parent $Target)
        if ($backupParent -ne $expectedParent -or (Split-Path -Leaf $BackupDirectory) -cnotmatch '^demo-dacl-backup-[0-9a-f]{32}$') { throw 'backup_path' }
        Assert-DemoDaclNoReparse $backupParent
        if (Test-Path -LiteralPath $BackupDirectory) { throw 'backup_exists' }
        New-DemoDaclBackupDirectory $BackupDirectory $operator
        $backupHandle=Open-DemoDaclBackupDirectory $BackupDirectory
        Assert-DemoDaclNoReparse $BackupDirectory
        Assert-DemoDaclPrivate (Get-DemoDaclMetadata $BackupDirectory) $operator
        $stage='backup_filename'
        if ($BackupFile -ne (Join-Path $BackupDirectory 'original-dacl.json') -or (Test-Path -LiteralPath $BackupFile)) { throw 'backup_exists' }
        $backup=[ordered]@{Format=1;Target=$Expected;Owner=$before.Owner;Identity=$identity;OriginalDacl=$before.Sddl;ParentDacl=$parentBefore.Sddl;CapturedUtc=[DateTime]::UtcNow.ToString('o')}
        $stage='backup_write'
        Write-DemoDaclBackup $BackupFile $operator $backup
        $stage='backup_verification'
        Assert-DemoDaclNoReparse $BackupFile
        Assert-DemoDaclPrivate (Get-DemoDaclMetadata $BackupFile) $operator
        $saved=Read-DemoDaclBackup $BackupFile
        if ($saved.Format -ne 1 -or $saved.Target -ne $Expected -or $saved.Owner -ne $before.Owner -or $saved.Identity -ne $identity -or $saved.OriginalDacl -cne $before.Sddl -or $saved.ParentDacl -cne $parentBefore.Sddl) { throw 'backup_mismatch' }
        $backupVerified=$true
        $stage='prechange_recheck'
        Assert-DemoDaclNoReparse $Target
        $current=Get-DemoDaclMetadata $Target
        if ($current.Owner -ne $before.Owner -or $current.Sddl -cne $before.Sddl -or (Get-DemoDaclIdentity $handle) -ne $identity) { throw 'target_changed' }
        if ((Get-DemoDaclMetadata (Split-Path -Parent $Target)).Sddl -cne $parentBefore.Sddl) { throw 'parent_changed' }
        $stage='dacl_correction'
        $mutationStarted=$true
        Set-DemoDaclOnHandle $handle $operator
        $stage='post_verification'
        Assert-DemoDaclNoReparse $Target
        Assert-DemoDaclPrivate (Get-DemoDaclMetadata $Target) $operator
        if ((Get-DemoDaclMetadata (Split-Path -Parent $Target)).Sddl -cne $parentBefore.Sddl) { throw 'parent_changed' }
        $pathHandle=$null
        try {
            $pathHandle=Open-DemoDaclTarget $Target
            if ((Get-DemoDaclIdentity $pathHandle) -ne $identity -or (Get-DemoDaclIdentity $handle) -ne $identity) { throw 'identity_changed' }
        } finally { if ($null -ne $pathHandle) { $pathHandle.Dispose() } }
        Write-Output 'PASS: exact credential file DACL corrected and verified; owner/identity preserved; credential contents unread'
        return 0
    } catch {
        Write-Output ('STOP: demo credential DACL stage='+$stage+' backup_verified='+$backupVerified.ToString().ToLowerInvariant()+' target_change_attempted='+$mutationStarted.ToString().ToLowerInvariant()+'; preserve state; no automatic rollback')
        return 1
    } finally {
        if ($null -ne $backupHandle) { $backupHandle.Dispose() }
        if ($null -ne $handle) { $handle.Dispose() }
    }
}

# Separate operator-reviewed operation; never invoked by the correction wrapper.
function Invoke-DemoCredentialDaclRollback {
    param([string]$BackupFile,[switch]$ConfirmRollback,[switch]$ConfirmOriginalBroaderAccess)
    $stage='rollback_confirmation'; $handle=$null; $backupHandle=$null
    try {
        if (-not $ConfirmRollback -or -not $ConfirmOriginalBroaderAccess) { throw 'confirmation' }
        $expected='C:\Users\admin\Desktop\LankaPex\.server-logs\private-demo\demo-app.dpapi'
        $directory=Split-Path -Parent $BackupFile
        $stage='rollback_backup_path'
        if ($BackupFile -ne (Join-Path $directory 'original-dacl.json') -or
            (Split-Path -Parent $directory) -ne (Split-Path -Parent (Split-Path -Parent $expected)) -or
            (Split-Path -Leaf $directory) -cnotmatch '^demo-dacl-backup-[0-9a-f]{32}$') { throw 'backup_path' }
        Assert-DemoDaclNoReparse $BackupFile
        Assert-DemoDaclNoReparse $expected
        $operator=Get-DemoDaclOperator
        $backupHandle=Open-DemoDaclBackupDirectory $directory
        Assert-DemoDaclPrivate (Get-DemoDaclMetadata $directory) $operator
        Assert-DemoDaclPrivate (Get-DemoDaclMetadata $BackupFile) $operator
        $saved=Read-DemoDaclBackup $BackupFile
        $stage='rollback_ownership'
        if ($saved.Format -ne 1 -or $saved.Target -cne $expected -or $saved.Owner -ne $operator -or
            -not $saved.OriginalDacl -or -not $saved.Identity -or -not $saved.ParentDacl) { throw 'backup' }
        $current=Get-DemoDaclMetadata $expected
        if ($current.Sddl -ceq $saved.OriginalDacl) { throw 'already_restored' }
        if ($current.Owner -ne $operator -or
            (Get-DemoDaclMetadata (Split-Path -Parent $expected)).Sddl -cne $saved.ParentDacl) { throw 'ownership' }
        $handle=Open-DemoDaclTarget $expected
        if ((Get-DemoDaclIdentity $handle) -ne $saved.Identity) { throw 'identity' }
        $stage='rollback_dacl'
        Set-DemoDaclOnHandle $handle $operator -RestoreSddl $saved.OriginalDacl
        $stage='rollback_verification'
        $after=Get-DemoDaclMetadata $expected
        if ($after.Owner -ne $saved.Owner -or $after.Sddl -cne $saved.OriginalDacl -or
            (Get-DemoDaclIdentity $handle) -ne $saved.Identity -or
            (Get-DemoDaclMetadata (Split-Path -Parent $expected)).Sddl -cne $saved.ParentDacl) { throw 'verification' }
        Write-Output 'PASS: original DACL restored; original broader access reintroduced; credential contents unread'
        return 0
    } catch {
        Write-Output ('STOP: demo credential DACL stage='+$stage+'; preserve state; no retry or automatic repair')
        return 1
    } finally {
        if ($null -ne $handle) { $handle.Dispose() }
        if ($null -ne $backupHandle) { $backupHandle.Dispose() }
    }
}
