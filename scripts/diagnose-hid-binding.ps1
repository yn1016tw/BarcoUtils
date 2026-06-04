# diagnose-hid-binding.ps1
# Run on the PROBLEM laptop:
#   1. BarcoClickShareAutorunService DISABLED (sc config BarcoClickShareAutorunService start=disabled)
#   2. ClickShare.exe CLOSED
#   3. Button plugged in and WAIT 10 seconds before running

$VID = "0600"
$HidPID = "0185"

Write-Host "=== USB layer - driver service binding ===" -ForegroundColor Cyan

$found = $false
Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Enum\USB" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "*$VID*$HidPID*" } |
    Get-ChildItem -ErrorAction SilentlyContinue |
    ForEach-Object {
        $found = $true
        $svc   = (Get-ItemProperty $_.PSPath -Name "Service"  -ErrorAction SilentlyContinue).Service
        $class = (Get-ItemProperty $_.PSPath -Name "Class"    -ErrorAction SilentlyContinue).Class
        $name  = $_.PSChildName
        $color = if ($svc -eq "HidUsb" -or $svc -eq "usbccgp" -or $svc -eq "USBSTOR" -or $svc -eq "usbaudio2") { "Green" } `
                 elseif ($svc -eq "BarcoClickShareDrv") { "Yellow" } else { "Red" }
        Write-Host ("  {0,-40}  Service={1,-25}  Class={2}" -f $name, $svc, $class) -ForegroundColor $color
    }

if (-not $found) { Write-Host "  [NOT FOUND] Button not connected" -ForegroundColor Red }

Write-Host ""
Write-Host "=== HID layer - device service ===" -ForegroundColor Cyan
Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Enum\HID" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "*$VID*$HidPID*" } |
    Get-ChildItem -ErrorAction SilentlyContinue |
    ForEach-Object {
        $svc   = (Get-ItemProperty $_.PSPath -Name "Service" -ErrorAction SilentlyContinue).Service
        $class = (Get-ItemProperty $_.PSPath -Name "Class"   -ErrorAction SilentlyContinue).Class
        Write-Host ("  {0,-40}  Service={1,-20}  Class={2}" -f $_.PSChildName, $svc, $class)
    }

Write-Host ""
Write-Host "=== CreateFile test (simulating rawhid_open) ===" -ForegroundColor Cyan

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class HidDiag {
    public const uint GENERIC_READ       = 0x80000000u;
    public const uint GENERIC_WRITE      = 0x40000000u;
    public const uint GENERIC_RW         = 0xC0000000u;
    public const uint FILE_SHARE_READ    = 0x00000001u;
    public const uint FILE_SHARE_RW      = 0x00000003u;
    public const uint OPEN_EXISTING      = 3u;
    public const uint FILE_FLAG_OVERLAPPED = 0x40000000u;

    [DllImport("hid.dll")]    public static extern void HidD_GetHidGuid(out Guid g);
    [DllImport("hid.dll")]    public static extern bool HidD_GetPreparsedData(IntPtr h, out IntPtr p);
    [DllImport("hid.dll")]    public static extern bool HidD_FreePreparsedData(IntPtr p);
    [DllImport("hid.dll")]    public static extern int  HidP_GetCaps(IntPtr p, out CAPS c);
    [DllImport("hid.dll")]    public static extern bool HidD_GetAttributes(IntPtr h, ref ATTRIB a);
    [StructLayout(LayoutKind.Sequential)] public struct ATTRIB { public uint Size; public ushort VendorID; public ushort ProductID; public ushort VersionNumber; }
    [DllImport("setupapi.dll", CharSet=CharSet.Auto)] public static extern IntPtr SetupDiGetClassDevs(ref Guid g, IntPtr e, IntPtr w, uint f);
    [DllImport("setupapi.dll")] public static extern bool SetupDiEnumDeviceInterfaces(IntPtr s, IntPtr d, ref Guid g, uint idx, ref IFDATA d2);
    [DllImport("setupapi.dll", CharSet=CharSet.Auto)] public static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr s, ref IFDATA d2, ref DETAIL det, uint sz, out uint req, IntPtr di);
    [DllImport("setupapi.dll", CharSet=CharSet.Auto)] public static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr s, ref IFDATA d2, IntPtr det, uint sz, out uint req, IntPtr di);
    [DllImport("kernel32.dll", CharSet=CharSet.Auto, SetLastError=true)] public static extern IntPtr CreateFile(string n, uint a, uint sh, IntPtr sec, uint cd, uint fl, IntPtr t);
    [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll")] public static extern int GetLastError();
    [StructLayout(LayoutKind.Sequential)] public struct CAPS { public ushort Usage; public ushort UsagePage; public ushort InputLen; public ushort OutputLen; [MarshalAs(UnmanagedType.ByValArray, SizeConst=20)] public ushort[] Rest; }
    [StructLayout(LayoutKind.Sequential)] public struct IFDATA { public int cbSize; public Guid guid; public uint Flags; public IntPtr Reserved; }
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Auto)] public struct DETAIL { public int cbSize; [MarshalAs(UnmanagedType.ByValTStr, SizeConst=512)] public string DevicePath; }
    public static readonly IntPtr INVALID = new IntPtr(-1);
}
"@ -ErrorAction SilentlyContinue

$errorNames = @{ 0="SUCCESS"; 2="FILE_NOT_FOUND"; 5="ACCESS_DENIED"; 32="SHARING_VIOLATION"; 87="INVALID_PARAMETER" }

$g = [Guid]::Empty
[HidDiag]::HidD_GetHidGuid([ref]$g)
$devInfo = [HidDiag]::SetupDiGetClassDevs([ref]$g, [IntPtr]::Zero, [IntPtr]::Zero, [uint32]0x12)

for ($i = 0; $i -lt 500; $i++) {
    $ifd = New-Object HidDiag+IFDATA
    $ifd.cbSize = [Runtime.InteropServices.Marshal]::SizeOf($ifd)
    if (-not [HidDiag]::SetupDiEnumDeviceInterfaces($devInfo, [IntPtr]::Zero, [ref]$g, [uint32]$i, [ref]$ifd)) { break }

    $req = [uint32]0
    [HidDiag]::SetupDiGetDeviceInterfaceDetail($devInfo, [ref]$ifd, [IntPtr]::Zero, [uint32]0, [ref]$req, [IntPtr]::Zero) | Out-Null
    $det = New-Object HidDiag+DETAIL
    $det.cbSize = if ([IntPtr]::Size -eq 8) { 8 } else { 5 }
    [HidDiag]::SetupDiGetDeviceInterfaceDetail($devInfo, [ref]$ifd, [ref]$det, $req, [ref]$req, [IntPtr]::Zero) | Out-Null

    if ($det.DevicePath -notlike "*$VID*$HidPID*") { continue }

    # Attempt 1: RW + share_read (same flags as rawhid_open in raw-hid library)
    $h = [HidDiag]::CreateFile($det.DevicePath, [HidDiag]::GENERIC_RW, [HidDiag]::FILE_SHARE_READ, [IntPtr]::Zero, [HidDiag]::OPEN_EXISTING, [HidDiag]::FILE_FLAG_OVERLAPPED, [IntPtr]::Zero)
    $err1 = [HidDiag]::GetLastError()

    # Attempt 2: Read-only + share_read|write (less restrictive, for diagnosis)
    $h2 = [HidDiag]::CreateFile($det.DevicePath, [HidDiag]::GENERIC_READ, [HidDiag]::FILE_SHARE_RW, [IntPtr]::Zero, [HidDiag]::OPEN_EXISTING, [HidDiag]::FILE_FLAG_OVERLAPPED, [IntPtr]::Zero)
    $err2 = [HidDiag]::GetLastError()

    $usagePage = "?"; $usage = "?"; $inLen = "?"; $outLen = "?"; $actualVid = "?"; $actualPid = "?"
    $hForCaps = if ($h -ne [HidDiag]::INVALID) { $h } elseif ($h2 -ne [HidDiag]::INVALID) { $h2 } else { [IntPtr]::Zero }
    if ($hForCaps -ne [IntPtr]::Zero) {
        $attr = New-Object HidDiag+ATTRIB
        $attr.Size = [Runtime.InteropServices.Marshal]::SizeOf($attr)
        if ([HidDiag]::HidD_GetAttributes($hForCaps, [ref]$attr)) {
            $actualVid = "0x{0:X4}" -f $attr.VendorID
            $actualPid = "0x{0:X4}" -f $attr.ProductID
        }
        $prep = [IntPtr]::Zero
        if ([HidDiag]::HidD_GetPreparsedData($hForCaps, [ref]$prep)) {
            $caps = New-Object HidDiag+CAPS
            [HidDiag]::HidP_GetCaps($prep, [ref]$caps) | Out-Null
            $usagePage = "0x{0:X4}" -f $caps.UsagePage
            $usage     = "0x{0:X4}" -f $caps.Usage
            $inLen = $caps.InputLen; $outLen = $caps.OutputLen
            [HidDiag]::HidD_FreePreparsedData($prep) | Out-Null
        }
    }
    if ($h  -ne [HidDiag]::INVALID) { [HidDiag]::CloseHandle($h)  | Out-Null }
    if ($h2 -ne [HidDiag]::INVALID) { [HidDiag]::CloseHandle($h2) | Out-Null }

    $mi  = if ($det.DevicePath -match "mi_0(\d)") { "MI_0$($Matches[1])" } else { "MI_?" }
    $en1 = if ($errorNames.ContainsKey($err1)) { $errorNames[$err1] } else { "ERR_$err1" }
    $en2 = if ($errorNames.ContainsKey($err2)) { $errorNames[$err2] } else { "ERR_$err2" }
    $s1  = if ($h  -eq [HidDiag]::INVALID) { "FAIL($en1)" } else { "OK" }
    $s2  = if ($h2 -eq [HidDiag]::INVALID) { "FAIL($en2)" } else { "OK(readonly)" }
    $c   = if ($s1 -eq "OK") { "Green" } elseif ($en1 -eq "SHARING_VIOLATION") { "Yellow" } else { "Red" }

    # check if usage values match what ClickShare expects for Gen5 control channel
    $usageMatch = if ($usagePage -eq "0xFF00" -and $usage -eq "0x0002") { "[MATCH:ctrl]" } `
                  elseif ($usagePage -eq "0xFF00" -and $usage -eq "0x0001") { "[MATCH:datapump]" } `
                  elseif ($usagePage -eq "0xFF00" -and $usage -eq "0x0003") { "[MATCH:audio]" } `
                  else { "" }

    Write-Host ("  {0}  RW+SHR:{1,-25}  RO+SHR:{2,-22}  VID:{3} PID:{4}  UsagePage:{5}  Usage:{6} {7}" -f $mi, $s1, $s2, $actualVid, $actualPid, $usagePage, $usage, $usageMatch) -ForegroundColor $c
    Write-Host ("       Path: {0}" -f $det.DevicePath)
}

Write-Host ""
Write-Host "=== What ClickShare (DongleController) expects for Gen5 control ===" -ForegroundColor Cyan
Write-Host "  VID=0x0600 (1536), PID=0x0185 (389)"
Write-Host "  UsagePage=0xFF00, Usage=0x0002  --> [MATCH:ctrl] label above"
Write-Host "  If MI_01 shows FAIL(*) or usage mismatch -> that is the root cause"
Write-Host ""
Write-Host "=== Expected results (service disabled, ClickShare closed) ===" -ForegroundColor Cyan
Write-Host "  MI_00: USB Service=BarcoClickShareDrv (expected)"
Write-Host "  MI_01/02/03: USB Service=HidUsb (expected)"
Write-Host "  MI_01/02/03: CreateFile -> OK (expected when ClickShare is closed)"
Write-Host ""
Write-Host "=== Error meanings ===" -ForegroundColor Cyan
Write-Host "  OK              -> driver binding correct, ClickShare should be able to open"
Write-Host "  SHARING_VIOLATION -> another process holds the handle exclusively"
Write-Host "  ACCESS_DENIED   -> BarcoClickShareDrv may have claimed this HID interface"
Write-Host "  FILE_NOT_FOUND  -> Windows not yet enumerated this interface (race condition)"