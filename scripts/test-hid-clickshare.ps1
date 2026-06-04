# test-hid-clickshare.ps1 - ASCII encoding
# List all ClickShare HID devices and test open/read/write
# VID=0x0600 PID=0x0185
# Run as Administrator

if (-not ([System.Management.Automation.PSTypeName]"HidCsV4").Type) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class HidCsV4 {
    [DllImport("hid.dll")]
    public static extern void HidD_GetHidGuid(out Guid g);

    [DllImport("hid.dll", SetLastError=true)]
    public static extern bool HidD_GetAttributes(IntPtr dev, ref HIDD_ATTRIBUTES a);

    [DllImport("hid.dll", SetLastError=true)]
    public static extern bool HidD_GetPreparsedData(IntPtr dev, out IntPtr data);

    [DllImport("hid.dll", SetLastError=true)]
    public static extern bool HidD_FreePreparsedData(IntPtr data);

    [DllImport("hid.dll", CharSet=CharSet.Auto, SetLastError=true)]
    public static extern bool HidD_GetProductString(IntPtr dev, StringBuilder buf, uint len);

    [DllImport("hid.dll", SetLastError=true)]
    public static extern int HidP_GetCaps(IntPtr data, ref HIDP_CAPS caps);

    [DllImport("setupapi.dll", CharSet=CharSet.Auto, SetLastError=true)]
    public static extern IntPtr SetupDiGetClassDevs(ref Guid cls, IntPtr en, IntPtr hw, uint f);

    [DllImport("setupapi.dll", SetLastError=true)]
    public static extern bool SetupDiEnumDeviceInterfaces(IntPtr di, IntPtr dd, ref Guid g, uint idx, ref SDIFD d);

    // Both calls use IntPtr for the ifaceData arg - avoids boxing issues from PS
    [DllImport("setupapi.dll", CharSet=CharSet.Auto, SetLastError=true, EntryPoint="SetupDiGetDeviceInterfaceDetailW")]
    public static extern bool GetDetailSize(IntPtr di, IntPtr ifaceData, IntPtr detail, uint sz, ref uint needed, IntPtr devdata);

    [DllImport("setupapi.dll", CharSet=CharSet.Auto, SetLastError=true, EntryPoint="SetupDiGetDeviceInterfaceDetailW")]
    public static extern bool GetDetailBuf(IntPtr di, IntPtr ifaceData, IntPtr detail, uint sz, ref uint needed, IntPtr devdata);

    [DllImport("setupapi.dll", SetLastError=true)]
    public static extern bool SetupDiDestroyDeviceInfoList(IntPtr di);

    [DllImport("kernel32.dll", CharSet=CharSet.Auto, SetLastError=true)]
    public static extern IntPtr CreateFile(string p, uint acc, uint share, IntPtr sec, uint disp, uint fl, IntPtr tmpl);

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool ReadFile(IntPtr h, byte[] b, uint n, out uint r, IntPtr ov);

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool WriteFile(IntPtr h, byte[] b, uint n, out uint w, IntPtr ov);

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool CloseHandle(IntPtr h);

    [DllImport("kernel32.dll")]
    public static extern uint GetLastError();

    public static readonly IntPtr INVALID = new IntPtr(-1);
    public const uint GEN_R   = 0x80000000;
    public const uint GEN_W   = 0x40000000;
    public const uint SHR_R   = 0x00000001;
    public const uint SHR_W   = 0x00000002;
    public const uint OPEN    = 3;
    public const uint OVLP    = 0x40000000;
    public const uint PRESENT = 0x00000002;
    public const uint IFACE   = 0x00000010;

    [StructLayout(LayoutKind.Sequential)]
    public struct SDIFD {
        public uint  cbSize;
        public Guid  InterfaceClassGuid;
        public uint  Flags;
        public IntPtr Reserved;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct HIDD_ATTRIBUTES {
        public uint   Size;
        public ushort VendorID;
        public ushort ProductID;
        public ushort VersionNumber;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct HIDP_CAPS {
        public ushort Usage;
        public ushort UsagePage;
        public ushort InputReportByteLength;
        public ushort OutputReportByteLength;
        public ushort FeatureReportByteLength;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst=17)]
        public ushort[] Reserved;
        public ushort NumberLinkCollectionNodes;
        public ushort NumberInputButtonCaps;
        public ushort NumberInputValueCaps;
        public ushort NumberInputDataIndices;
        public ushort NumberOutputButtonCaps;
        public ushort NumberOutputValueCaps;
        public ushort NumberOutputDataIndices;
        public ushort NumberFeatureButtonCaps;
        public ushort NumberFeatureValueCaps;
        public ushort NumberFeatureDataIndices;
    }
}
"@
}

$T = [HidCsV4]
$M = [Runtime.InteropServices.Marshal]

function Get-HidDevicePath($di, $iface) {
    # Serialize struct to unmanaged buffer so cbSize is preserved (avoids PS boxing issue)
    $structSize = $M::SizeOf($iface)
    $pIface = $M::AllocHGlobal($structSize)
    try {
        $M::StructureToPtr($iface, $pIface, $false)
        $needed = [uint32]0
        $T::GetDetailSize($di, $pIface, [IntPtr]::Zero, 0, [ref]$needed, [IntPtr]::Zero) | Out-Null
        if ($needed -lt 6) { return $null }

        $pBuf = $M::AllocHGlobal([int]$needed)
        try {
            $M::WriteInt32($pBuf, 0, 6)  # cbSize = 6 (Unicode)
            $dummy = [uint32]$needed
            if (-not $T::GetDetailBuf($di, $pIface, $pBuf, $needed, [ref]$dummy, [IntPtr]::Zero)) {
                return $null
            }
            # DevicePath starts at offset +4 (after DWORD cbSize), Unicode string
            return $M::PtrToStringUni([IntPtr]($pBuf.ToInt64() + 4))
        } finally { $M::FreeHGlobal($pBuf) }
    } finally { $M::FreeHGlobal($pIface) }
}

function Win-Error($c) {
    switch ($c) {
        0    { "OK" }
        2    { "ERROR_FILE_NOT_FOUND (device absent)" }
        5    { "ERROR_ACCESS_DENIED" }
        32   { "ERROR_SHARING_VIOLATION (held by another process)" }
        87   { "ERROR_INVALID_PARAMETER" }
        997  { "ERROR_IO_PENDING (overlapped - device is responsive)" }
        1168 { "ERROR_NOT_FOUND" }
        default { "ERROR $c (0x$("{0:X}" -f $c))" }
    }
}

$VidTarget = [uint16]0x0600
$PidTarget = [uint16]0x0185

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ClickShare HID Device Test" -ForegroundColor Cyan
Write-Host "  Target: VID=0x0600 PID=0x0185" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---- [1] Enumerate all HID devices ----
Write-Host "[1] Enumerating all HID devices..." -ForegroundColor Yellow

$hidGuid = New-Object Guid
$T::HidD_GetHidGuid([ref]$hidGuid)
Write-Host "    HID class GUID : $hidGuid"

$di = $T::SetupDiGetClassDevs([ref]$hidGuid, [IntPtr]::Zero, [IntPtr]::Zero, ($T::PRESENT -bor $T::IFACE))
if ($di -eq $T::INVALID -or $di -eq [IntPtr]::Zero) {
    Write-Host "    ERROR: SetupDiGetClassDevs failed GLE=$($T::GetLastError())" -ForegroundColor Red
    exit 1
}

$allPaths = @()
$enumIdx = [uint32]0
while ($true) {
    $iface = New-Object HidCsV4+SDIFD
    $iface.cbSize = [uint32]$M::SizeOf($iface)

    if (-not $T::SetupDiEnumDeviceInterfaces($di, [IntPtr]::Zero, [ref]$hidGuid, $enumIdx, [ref]$iface)) {
        break
    }

    $path = Get-HidDevicePath $di $iface
    if ($path) { $allPaths += $path }

    $enumIdx++
}
$T::SetupDiDestroyDeviceInfoList($di) | Out-Null

Write-Host "    Total HID interfaces : $($allPaths.Count)"

if ($allPaths.Count -eq 0) {
    Write-Host "    ERROR: 0 HID devices - not running as Admin or enum failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ---- [2] Filter ClickShare VID=0600 PID=0185 ----
Write-Host "[2] Scanning for VID=0x0600 PID=0x0185..." -ForegroundColor Yellow

$csDevices = @()
foreach ($path in $allPaths) {
    $h = $T::CreateFile($path, 0, ($T::SHR_R -bor $T::SHR_W), [IntPtr]::Zero, $T::OPEN, 0, [IntPtr]::Zero)
    if ($h -eq $T::INVALID) { continue }

    $attr = New-Object HidCsV4+HIDD_ATTRIBUTES
    $attr.Size = [uint32]$M::SizeOf($attr)
    $ok = $T::HidD_GetAttributes($h, [ref]$attr)

    if (-not $ok -or $attr.VendorID -ne $VidTarget -or $attr.ProductID -ne $PidTarget) {
        $T::CloseHandle($h) | Out-Null
        continue
    }

    $caps = New-Object HidCsV4+HIDP_CAPS
    $pp = [IntPtr]::Zero
    if ($T::HidD_GetPreparsedData($h, [ref]$pp)) {
        $T::HidP_GetCaps($pp, [ref]$caps) | Out-Null
        $T::HidD_FreePreparsedData($pp) | Out-Null
    }

    $sb = New-Object System.Text.StringBuilder 256
    $T::HidD_GetProductString($h, $sb, 256) | Out-Null
    $T::CloseHandle($h) | Out-Null

    $role = switch ($caps.Usage) {
        0x0002 { "CONTROL   (MI_01) <- rawhid target" }
        0x0001 { "DATAPUMP  (MI_02)" }
        0x0003 { "AUDIO     (MI_03)" }
        default { "UNKNOWN   usage=0x$("{0:X4}" -f $caps.Usage)" }
    }

    $csDevices += [PSCustomObject]@{
        Path    = $path
        Vid     = "0x$("{0:X4}" -f $attr.VendorID)"
        Pid2    = "0x$("{0:X4}" -f $attr.ProductID)"
        FW      = $attr.VersionNumber
        UP      = "0x$("{0:X4}" -f $caps.UsagePage)"
        Usage   = "0x$("{0:X4}" -f $caps.Usage)"
        InLen   = $caps.InputReportByteLength
        OutLen  = $caps.OutputReportByteLength
        Product = $sb.ToString()
        Role    = $role
    }
}

if ($csDevices.Count -eq 0) {
    Write-Host "    ** NO ClickShare HID devices found **" -ForegroundColor Red
    Write-Host "    -> Button not connected, or HidUsb not bound to MI_01/02/03" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "    Found $($csDevices.Count) ClickShare HID interface(s)" -ForegroundColor Green
    Write-Host ""
}

# ---- [3] Open/Read/Write tests ----
$n = 0
foreach ($dev in $csDevices) {
    $n++
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host "  #$n  $($dev.Role)" -ForegroundColor White
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host "  Path     : $($dev.Path)"
    Write-Host "  VID/PID  : $($dev.Vid) / $($dev.Pid2)   FW=0x$("{0:X4}" -f $dev.FW)"
    Write-Host "  Usage    : Page=$($dev.UP)  Usage=$($dev.Usage)"
    Write-Host "  Reports  : Input=$($dev.InLen)B  Output=$($dev.OutLen)B"
    if ($dev.Product) { Write-Host "  Product  : $($dev.Product)" }
    Write-Host ""

    # [A] access=0 : device existence probe
    $hA = $T::CreateFile($dev.Path, 0, ($T::SHR_R -bor $T::SHR_W), [IntPtr]::Zero, $T::OPEN, 0, [IntPtr]::Zero)
    $eA = $T::GetLastError()
    $okA = $hA -ne $T::INVALID
    Write-Host ("  [A] Exist (access=0)      : {0}" -f $(if ($okA) { "OK - device exists" } else { "FAIL - $(Win-Error $eA)" })) -ForegroundColor $(if ($okA) { "Green" } else { "Red" })
    if ($okA) { $T::CloseHandle($hA) | Out-Null }

    # [B] Read-only + ShareRW
    $hB = $T::CreateFile($dev.Path, $T::GEN_R, ($T::SHR_R -bor $T::SHR_W), [IntPtr]::Zero, $T::OPEN, $T::OVLP, [IntPtr]::Zero)
    $eB = $T::GetLastError()
    $okB = $hB -ne $T::INVALID
    Write-Host ("  [B] Read-only + ShareRW   : {0}" -f $(if ($okB) { "OK" } else { "FAIL - $(Win-Error $eB)" })) -ForegroundColor $(if ($okB) { "Green" } else { "Red" })
    if ($okB) { $T::CloseHandle($hB) | Out-Null }

    # [C] RW + ShareR  <-- exact rawhid_open() flags
    $hC = $T::CreateFile($dev.Path, ($T::GEN_R -bor $T::GEN_W), $T::SHR_R, [IntPtr]::Zero, $T::OPEN, $T::OVLP, [IntPtr]::Zero)
    $eC = $T::GetLastError()
    $okC = $hC -ne $T::INVALID
    if ($okC) {
        Write-Host "  [C] RW + ShareR (rawhid)  : OK  <- rawhid_open() will SUCCEED" -ForegroundColor Green
    } else {
        Write-Host ("  [C] RW + ShareR (rawhid)  : FAIL - $(Win-Error $eC)  <- rawhid_open() FAILS") -ForegroundColor Red
    }

    if ($okC) {
        # [D] ReadFile
        if ($dev.InLen -gt 0) {
            $buf = New-Object byte[] $dev.InLen
            $nr = [uint32]0
            $rOk = $T::ReadFile($hC, $buf, [uint32]$dev.InLen, [ref]$nr, [IntPtr]::Zero)
            $eR = $T::GetLastError()
            if ($rOk) {
                $hex = ($buf[0..([Math]::Min(7,$buf.Length-1))] | ForEach-Object { "{0:X2}" -f $_ }) -join " "
                Write-Host ("  [D] ReadFile              : OK  bytes={0}  [{1}...]" -f $nr, $hex) -ForegroundColor Green
            } elseif ($eR -eq 997) {
                Write-Host "  [D] ReadFile              : OK (IO_PENDING - device alive)" -ForegroundColor Green
            } else {
                Write-Host ("  [D] ReadFile              : FAIL - $(Win-Error $eR)") -ForegroundColor Red
            }
        } else {
            Write-Host "  [D] ReadFile              : SKIP (InLen=0)" -ForegroundColor Gray
        }

        # [E] WriteFile
        if ($dev.OutLen -gt 0) {
            $wbuf = New-Object byte[] $dev.OutLen
            $nw = [uint32]0
            $wOk = $T::WriteFile($hC, $wbuf, [uint32]$dev.OutLen, [ref]$nw, [IntPtr]::Zero)
            $eW = $T::GetLastError()
            if ($wOk) {
                Write-Host ("  [E] WriteFile             : OK  bytes={0}" -f $nw) -ForegroundColor Green
            } elseif ($eW -eq 997) {
                Write-Host "  [E] WriteFile             : OK (IO_PENDING - device alive)" -ForegroundColor Green
            } else {
                Write-Host ("  [E] WriteFile             : FAIL - $(Win-Error $eW)") -ForegroundColor Red
            }
        } else {
            Write-Host "  [E] WriteFile             : SKIP (OutLen=0)" -ForegroundColor Gray
        }

        $T::CloseHandle($hC) | Out-Null
    }

    # [F] RW + ShareRW  (can two processes coexist?)
    $hF = $T::CreateFile($dev.Path, ($T::GEN_R -bor $T::GEN_W), ($T::SHR_R -bor $T::SHR_W), [IntPtr]::Zero, $T::OPEN, $T::OVLP, [IntPtr]::Zero)
    $eF = $T::GetLastError()
    $okF = $hF -ne $T::INVALID
    Write-Host ("  [F] RW + ShareRW          : {0}" -f $(if ($okF) { "OK" } else { "FAIL - $(Win-Error $eF)" })) -ForegroundColor $(if ($okF) { "Cyan" } else { "Yellow" })
    if ($okF) { $T::CloseHandle($hF) | Out-Null }

    Write-Host ""
    Write-Host "  VERDICT:" -ForegroundColor White
    if (-not $okA) {
        Write-Host "  -> DEVICE NOT FOUND (button not connected or driver missing)" -ForegroundColor Red
    } elseif (-not $okC) {
        Write-Host "  -> DEVICE EXISTS but BLOCKED (SHARING_VIOLATION)" -ForegroundColor Red
        Write-Host "     Another process holds exclusive RW handle" -ForegroundColor Yellow
        Write-Host "     ClickShare reports 'device not found' due to rawhid_open bug" -ForegroundColor Yellow
        if ($okB) {
            Write-Host "     Read-only OK -> holder opened with FILE_SHARE_READ (same as rawhid_open)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  -> OK: device accessible, rawhid_open should work" -ForegroundColor Green
    }
    Write-Host ""
}

# ---- [4] Processes ----
Write-Host "========================================"
Write-Host "[4] Running ClickShare / Barco processes:" -ForegroundColor Yellow
$procs = Get-Process | Where-Object { $_.Name -match "(?i)clickshare|barco" } |
    Select-Object Id, Name, @{N="Exe";E={try{$_.Path}catch{"(denied)"}}}
if ($procs) {
    $procs | ForEach-Object { Write-Host ("  PID={0,-6} {1,-40} {2}" -f $_.Id, $_.Name, $_.Exe) -ForegroundColor Red }
} else {
    Write-Host "  None running" -ForegroundColor Green
}
$svc = Get-Service "BarcoClickShareAutorunService" -ErrorAction SilentlyContinue
if ($svc) {
    $c = if ($svc.Status -eq "Running") { "Red" } else { "Green" }
    Write-Host ("  Service BarcoClickShareAutorunService: {0}  StartType={1}" -f $svc.Status, $svc.StartType) -ForegroundColor $c
}
Write-Host ""
Write-Host "Done." -ForegroundColor Cyan
