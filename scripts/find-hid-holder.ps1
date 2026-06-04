# find-hid-holder.ps1
# Find which process holds the Gen5 button HID handles
# Run on the PROBLEM laptop

$VID = "0600"
$HidPID = "0185"

Write-Host "=== Running processes (Barco/ClickShare related) ===" -ForegroundColor Cyan
Get-Process | Where-Object {
    $_.Name -like "*clickshare*" -or $_.Name -like "*barco*" -or $_.Name -like "*ClickShare*"
} | Select-Object Id, Name, @{N="StartTime";E={$_.StartTime}}, @{N="Path";E={try{$_.Path}catch{"(access denied)"}}} | Format-Table -AutoSize

Write-Host "=== All processes with open handles (using handle enumeration) ===" -ForegroundColor Cyan

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Collections.Generic;
using System.Text;

public class HandleFinder {
    [DllImport("ntdll.dll")] static extern int NtQuerySystemInformation(int cls, IntPtr buf, uint sz, out uint ret);
    [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint acc, bool inh, uint pid);
    [DllImport("kernel32.dll")] static extern bool DuplicateHandle(IntPtr sp, IntPtr sh, IntPtr tp, out IntPtr th, uint acc, bool inh, uint opt);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll", CharSet=CharSet.Auto)] static extern uint GetFinalPathNameByHandle(IntPtr h, StringBuilder buf, uint sz, uint flags);
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();

    const int SystemHandleInformation = 16;
    const uint PROCESS_DUP_HANDLE = 0x0040;
    const uint FILE_GENERIC_READ = 0x80000000;

    [StructLayout(LayoutKind.Sequential, Pack=1)]
    struct SYSTEM_HANDLE { public uint PID; public byte Type; public byte Flags; public ushort Value; public IntPtr Addr; public uint Access; }

    [StructLayout(LayoutKind.Sequential)]
    struct SYSTEM_HANDLE_INFO { public uint Count; }

    public static List<string> FindHolders(string vidpid) {
        var results = new List<string>();
        uint sz = 0x10000;
        IntPtr buf = IntPtr.Zero;
        int status;
        uint needed;
        try {
            while (true) {
                buf = Marshal.AllocHGlobal((int)sz);
                status = NtQuerySystemInformation(SystemHandleInformation, buf, sz, out needed);
                if (status == 0) break;
                Marshal.FreeHGlobal(buf); buf = IntPtr.Zero;
                if (status == unchecked((int)0xC0000004)) { sz = needed + 0x1000; continue; }
                return results;
            }
            uint count = (uint)Marshal.ReadInt32(buf);
            int baseOffset = 4;
            int handleSize = Marshal.SizeOf(typeof(SYSTEM_HANDLE));
            IntPtr self = GetCurrentProcess();
            uint lastPid = 0; IntPtr hProc = IntPtr.Zero;

            for (uint i = 0; i < count; i++) {
                var h = (SYSTEM_HANDLE)Marshal.PtrToStructure(new IntPtr(buf.ToInt64() + baseOffset + i * handleSize), typeof(SYSTEM_HANDLE));
                if (h.PID == 0 || h.PID == 4) continue;
                if ((h.Access & 0x0012019F) == 0) continue;
                if (h.PID != lastPid) {
                    if (hProc != IntPtr.Zero) CloseHandle(hProc);
                    hProc = OpenProcess(PROCESS_DUP_HANDLE, false, h.PID);
                    lastPid = h.PID;
                }
                if (hProc == IntPtr.Zero) continue;
                IntPtr dup;
                if (!DuplicateHandle(hProc, new IntPtr(h.Value), self, out dup, 0, false, 2)) continue;
                try {
                    var sb = new StringBuilder(512);
                    uint r = GetFinalPathNameByHandle(dup, sb, 512, 0);
                    if (r > 0) {
                        string path = sb.ToString().ToLower();
                        if (path.Contains(vidpid)) {
                            results.Add(string.Format("PID={0}  handle=0x{1:X4}  path={2}", h.PID, h.Value, sb.ToString()));
                        }
                    }
                } finally { CloseHandle(dup); }
            }
            if (hProc != IntPtr.Zero) CloseHandle(hProc);
        } finally { if (buf != IntPtr.Zero) Marshal.FreeHGlobal(buf); }
        return results;
    }
}
"@ -ErrorAction SilentlyContinue

$holders = [HandleFinder]::FindHolders("vid_0600&pid_0185")
if ($holders.Count -eq 0) {
    Write-Host "  No process found holding VID_0600&PID_0185 handles (try running as Admin)" -ForegroundColor Yellow
} else {
    foreach ($entry in $holders) {
        $pid2 = ($entry -replace "PID=(\d+).*",'$1')
        $proc = Get-Process -Id ([int]$pid2) -ErrorAction SilentlyContinue
        $procName = if ($proc) { $proc.Name } else { "?" }
        Write-Host ("  [$procName]  $entry") -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Quick check: is ClickShare in system tray? ===" -ForegroundColor Cyan
$cs = Get-Process -Name "ClickShare" -ErrorAction SilentlyContinue
if ($cs) {
    Write-Host "  ClickShare.exe IS running (PID=$($cs.Id)) - app is in system tray!" -ForegroundColor Red
    Write-Host "  Right-click tray icon -> Exit, then re-run diagnose-hid-binding.ps1" -ForegroundColor Yellow
} else {
    Write-Host "  ClickShare.exe is NOT running" -ForegroundColor Green
}

$svc = Get-Service "BarcoClickShareSvc" -ErrorAction SilentlyContinue
if ($svc) {
    Write-Host ("  BarcoClickShareSvc: Status={0}" -f $svc.Status) -ForegroundColor $(if($svc.Status -eq "Running"){"Red"}else{"Green"})
} else {
    Write-Host "  BarcoClickShareSvc: not installed" -ForegroundColor Green
}

$svc2 = Get-Service "BarcoClickShareService" -ErrorAction SilentlyContinue
if ($svc2) {
    Write-Host ("  BarcoClickShareService: Status={0}" -f $svc2.Status) -ForegroundColor $(if($svc2.Status -eq "Running"){"Red"}else{"Green"})
}