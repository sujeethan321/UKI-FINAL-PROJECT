# Functions only. Entry point must load demo_qr_credential_storage.ps1 first.
function Get-DemoQrDirectoryPlanLabel {
    param($Plan)
    $expected=Get-DemoQrStoragePaths $Plan.OperatorSid $Plan.Profile
    if ($Plan.Directory -cne $expected.Directory -or $Plan.Credential -cne $expected.Credential) { throw 'directory_destination' }
    $missing=@($Plan.MissingDirectories)
    $parent=Split-Path -Parent $expected.Directory
    if ($missing.Count -eq 1 -and $missing[0] -ceq $expected.Directory) { return 'PrivateDemoQr' }
    if ($missing.Count -eq 2 -and $missing[0] -ceq $parent -and $missing[1] -ceq $expected.Directory) { return 'LankaPex,PrivateDemoQr' }
    # Never recreate profile, AppData or Local, even if unexpectedly absent.
    throw 'unsupported_missing_components'
}

function Initialize-DemoQrDirectoryCreationNative {
    if ('DemoQrDirectoryCreationNative' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class DemoQrDirectoryCreationNative {
 [StructLayout(LayoutKind.Sequential)]
 public struct SecurityAttributes {
  public int Length;
  public IntPtr Descriptor;
  [MarshalAs(UnmanagedType.Bool)] public bool InheritHandle;
 }
 [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
 [return: MarshalAs(UnmanagedType.Bool)]
 public static extern bool CreateDirectoryW(string path,ref SecurityAttributes attributes);
}
'@
}

function New-DemoQrDirectorySecurity {
    param([string]$OperatorSid)
    $security=New-Object Security.AccessControl.DirectorySecurity
    $security.SetAccessRuleProtection($true,$false)
    $owner=New-Object Security.Principal.SecurityIdentifier($OperatorSid)
    $security.SetOwner($owner)
    foreach ($sid in @($OperatorSid,'S-1-5-18')) {
        $identity=New-Object Security.Principal.SecurityIdentifier($sid)
        $rule=New-Object Security.AccessControl.FileSystemAccessRule(
            $identity,'FullControl','ContainerInherit, ObjectInherit','None','Allow')
        [void]$security.AddAccessRule($rule)
    }
    return $security
}

function New-DemoQrExclusiveDirectory {
    param([string]$Path,[string]$OperatorSid)
    $context=Resolve-DemoQrStoragePaths
    if ($OperatorSid -cne $context.OperatorSid -or
        $Path -cnotin @($context.Directory,(Split-Path -Parent $context.Directory))) { throw 'directory_destination' }
    Initialize-DemoQrDirectoryCreationNative
    $security=New-DemoQrDirectorySecurity $OperatorSid
    # DACL + owner are supplied to native CREATE, never applied after creation.
    # No SACL or change to an existing object's ownership/permissions is used.
    $binary=$security.GetSecurityDescriptorBinaryForm()
    $pointer=[IntPtr]::Zero
    try {
        $pointer=[Runtime.InteropServices.Marshal]::AllocHGlobal($binary.Length)
        [Runtime.InteropServices.Marshal]::Copy($binary,0,$pointer,$binary.Length)
        $attributes=New-Object 'DemoQrDirectoryCreationNative+SecurityAttributes'
        $attributes.Length=[Runtime.InteropServices.Marshal]::SizeOf($attributes)
        $attributes.Descriptor=$pointer; $attributes.InheritHandle=$false
        $created=[DemoQrDirectoryCreationNative]::CreateDirectoryW($Path,[ref]$attributes)
        if (-not $created) {
            $code=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
            if ($code -eq 183) { throw 'exclusive_directory_exists' }
            throw 'exclusive_directory_creation_failed'
        }
    } finally {
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::FreeHGlobal($pointer) }
        [Array]::Clear($binary,0,$binary.Length)
    }
}

function Invoke-DemoQrDirectoryPreparation {
    param([switch]$Execute,[switch]$ConfirmDirectoryCreation,[string]$ConfirmMissingComponents,
          [scriptblock]$PlanProvider={Assert-DemoQrCredentialStorage -Mode DirectoryPlan},
          [scriptblock]$Creator={param($p,$sid) New-DemoQrExclusiveDirectory $p $sid},
          [scriptblock]$OpenNode={param($p) Open-DemoQrStorageNode $p},
          [scriptblock]$FinalValidator={Assert-DemoQrCredentialStorage -Mode Create},$State)
    if ($null -eq $State) { $State=@{Stage='confirmation';Created=0} }
    if ($Execute -and (-not $ConfirmDirectoryCreation -or
        $ConfirmMissingComponents -cnotin @('PrivateDemoQr','LankaPex,PrivateDemoQr'))) { throw 'directory_confirmation' }
    $leases=New-Object 'Collections.Generic.List[object]'
    $createdHandles=New-Object 'Collections.Generic.List[IDisposable]'
    try {
        $State.Stage='directory_plan'
        $plan=& $PlanProvider
        $leases.Add($plan)
        $label=Get-DemoQrDirectoryPlanLabel $plan
        if (-not $Execute) {
            return ('PASS: QR storage directory plan missing_components='+$label+'; no directories or credentials created')
        }
        if ($label -cne $ConfirmMissingComponents) { throw 'directory_plan_confirmation_mismatch' }
        $planned=@($plan.MissingDirectories)
        for ($index=0; $index -lt $planned.Count; $index++) {
            # Revalidate all ancestors immediately before EVERY exclusive create,
            # retaining all prior leases and newly created directory handles.
            $State.Stage='ancestor_revalidation'
            $fresh=& $PlanProvider
            $leases.Add($fresh)
            [void](Get-DemoQrDirectoryPlanLabel $fresh)
            if ($fresh.OperatorSid -cne $plan.OperatorSid -or $fresh.Profile -cne $plan.Profile -or
                $fresh.Directory -cne $plan.Directory) { throw 'directory_identity_changed' }
            $remaining=@($planned[$index..($planned.Count-1)])
            if (@($fresh.MissingDirectories).Count -ne $remaining.Count) { throw 'directory_plan_changed' }
            for ($n=0; $n -lt $remaining.Count; $n++) {
                if ($fresh.MissingDirectories[$n] -cne $remaining[$n]) { throw 'directory_plan_changed' }
            }
            $State.Stage='exclusive_creation_attempted'
            & $Creator $planned[$index] $plan.OperatorSid
            $State.Created++
            $State.Stage='created_directory_verification'
            $node=& $OpenNode $planned[$index]
            $createdHandles.Add($node.Handle)
            if (-not $node.Directory) { throw 'created_directory_type' }
            Test-DemoQrStorageNode $node $plan.OperatorSid -Private
        }
        $State.Stage='complete_path_verification'
        $final=& $FinalValidator
        $leases.Add($final)
        if ($final.Directory -cne $plan.Directory -or $final.OperatorSid -cne $plan.OperatorSid -or
            $final.Credential -cne $plan.Credential) { throw 'final_directory_identity' }
        $State.Stage='complete'
        return 'PASS: dedicated QR credential directories created and metadata verified; no credential or database operation performed'
    } finally {
        foreach ($handle in $createdHandles) { $handle.Dispose() }
        foreach ($lease in $leases) { Close-DemoQrStorageLease $lease }
    }
}
