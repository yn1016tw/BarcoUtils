<#
Set or clear the "DefaultPassword" LSA private-data secret used by Windows'
autologin path. This is the actual switch that controls whether this machine
auto-logs in on boot -- confirmed by live testing that AutoAdminLogon alone
does NOT gate it for this Microsoft Account: Windows silently signs in
whenever a valid DefaultPassword secret exists for the last logged-on user,
regardless of AutoAdminLogon's value or of DefaultUserName being present.

Usage:
  powershell -NoProfile -ExecutionPolicy Bypass -File lsa_secret.ps1 -Action Set -Password "..."
  powershell -NoProfile -ExecutionPolicy Bypass -File lsa_secret.ps1 -Action Clear
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Set", "Clear")]
    [string]$Action,

    [string]$Password
)

if ($Action -eq "Set" -and -not $Password) {
    Write-Error "Set requires -Password"
    exit 1
}

$code = @'
using System;
using System.Runtime.InteropServices;
public class LsaSecret {
    [StructLayout(LayoutKind.Sequential)]
    public struct LSA_UNICODE_STRING { public ushort Length; public ushort MaximumLength; public IntPtr Buffer; }
    [StructLayout(LayoutKind.Sequential)]
    public struct LSA_OBJECT_ATTRIBUTES { public int Length; public IntPtr RootDirectory; public IntPtr ObjectName; public uint Attributes; public IntPtr SecurityDescriptor; public IntPtr SecurityQualityOfService; }
    [DllImport("advapi32.dll", SetLastError = true)]
    public static extern uint LsaOpenPolicy(IntPtr SystemName, ref LSA_OBJECT_ATTRIBUTES ObjectAttributes, uint DesiredAccess, out IntPtr PolicyHandle);
    [DllImport("advapi32.dll", SetLastError = true)]
    public static extern uint LsaStorePrivateData(IntPtr PolicyHandle, ref LSA_UNICODE_STRING KeyName, IntPtr PrivateData);
    [DllImport("advapi32.dll")]
    public static extern uint LsaClose(IntPtr ObjectHandle);

    private static LSA_UNICODE_STRING ToLsaString(string s) {
        var lus = new LSA_UNICODE_STRING();
        lus.Buffer = Marshal.StringToHGlobalUni(s);
        lus.Length = (ushort)(s.Length * 2);
        lus.MaximumLength = (ushort)((s.Length + 1) * 2);
        return lus;
    }

    public static uint SetSecret(string key, string value) {
        var oa = new LSA_OBJECT_ATTRIBUTES();
        IntPtr h;
        if (LsaOpenPolicy(IntPtr.Zero, ref oa, 0x2, out h) != 0) return 0xFFFFFFFF;
        var keyStr = ToLsaString(key);
        var valStr = ToLsaString(value);
        IntPtr valPtr = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(LSA_UNICODE_STRING)));
        Marshal.StructureToPtr(valStr, valPtr, false);
        uint r = LsaStorePrivateData(h, ref keyStr, valPtr);
        Marshal.FreeHGlobal(keyStr.Buffer);
        Marshal.FreeHGlobal(valStr.Buffer);
        Marshal.FreeHGlobal(valPtr);
        LsaClose(h);
        return r;
    }

    public static uint ClearSecret(string key) {
        var oa = new LSA_OBJECT_ATTRIBUTES();
        IntPtr h;
        if (LsaOpenPolicy(IntPtr.Zero, ref oa, 0x2, out h) != 0) return 0xFFFFFFFF;
        var keyStr = ToLsaString(key);
        uint r = LsaStorePrivateData(h, ref keyStr, IntPtr.Zero);
        Marshal.FreeHGlobal(keyStr.Buffer);
        LsaClose(h);
        return r;
    }
}
'@
Add-Type -TypeDefinition $code -Language CSharp

if ($Action -eq "Set") {
    $result = [LsaSecret]::SetSecret("DefaultPassword", $Password)
} else {
    $result = [LsaSecret]::ClearSecret("DefaultPassword")
}

Write-Output "$Action result: 0x$($result.ToString('X'))"
if ($result -ne 0) { exit 1 }
