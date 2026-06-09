/**
 * hid_test.cpp
 * Enumerate ClickShare HID devices (VID=0x0600 PID=0x00CE/0x0185) and test open/read/write.
 * Build: see build.bat
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <setupapi.h>
#include <hidsdi.h>
#include <hidpi.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

#pragma comment(lib, "setupapi.lib")
#pragma comment(lib, "hid.lib")

// ---------------------------------------------------------------------------
// Target device
// ---------------------------------------------------------------------------
static const USHORT TARGET_VID      = 0x0600;
static const USHORT TARGET_PID_GEN4 = 0x00CE;
static const USHORT TARGET_PID_GEN5 = 0x0185;

static bool isTargetPID(USHORT pid)
{
    return pid == TARGET_PID_GEN4 || pid == TARGET_PID_GEN5;
}

static const char* genStr(USHORT pid)
{
    switch (pid) {
        case 0x00CE: return "Gen4";
        case 0x0185: return "Gen5";
        default:     return "Unknown";
    }
}

// ---------------------------------------------------------------------------
// Colour helpers (Windows console)
// ---------------------------------------------------------------------------
enum Colour { WHITE = 7, GREEN = 10, RED = 12, YELLOW = 14, CYAN = 11, GRAY = 8 };
static void setColour(Colour c) { SetConsoleTextAttribute(GetStdHandle(STD_OUTPUT_HANDLE), (WORD)c); }
static void resetColour()        { setColour(WHITE); }

// ---------------------------------------------------------------------------
// Error string
// ---------------------------------------------------------------------------
static const char* errStr(DWORD e)
{
    switch (e) {
        case 0:    return "OK";
        case 2:    return "ERROR_FILE_NOT_FOUND (device absent)";
        case 5:    return "ERROR_ACCESS_DENIED";
        case 32:   return "ERROR_SHARING_VIOLATION (held by another process)";
        case 87:   return "ERROR_INVALID_PARAMETER";
        case 997:  return "ERROR_IO_PENDING (device alive / overlapped)";
        case 1168: return "ERROR_NOT_FOUND";
        default:   { static char buf[32]; sprintf_s(buf, "ERROR %lu (0x%lX)", e, e); return buf; }
    }
}

// ---------------------------------------------------------------------------
// Device info
// ---------------------------------------------------------------------------
struct DevInfo {
    wchar_t  path[512];
    USHORT   vid;
    USHORT   pid;
    USHORT   fw;
    USHORT   usagePage;
    USHORT   usage;
    USHORT   inputLen;
    USHORT   outputLen;
    wchar_t  product[256];
};

// ---------------------------------------------------------------------------
// Get device role string from usage
// ---------------------------------------------------------------------------
static const char* roleStr(USHORT usage)
{
    switch (usage) {
        case 0x0002: return "CONTROL   (MI_01)  <-- rawhid target";
        case 0x0001: return "DATAPUMP  (MI_02)";
        case 0x0003: return "AUDIO     (MI_03)";
        default:     return "UNKNOWN";
    }
}

// ---------------------------------------------------------------------------
// Enumerate ALL HID devices; filter to ClickShare, populate out[].
// Returns count found.
// ---------------------------------------------------------------------------
static int enumerateClickShare(DevInfo* out, int maxOut)
{
    GUID hidGuid;
    HidD_GetHidGuid(&hidGuid);

    HDEVINFO di = SetupDiGetClassDevs(&hidGuid, NULL, NULL,
                                       DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (di == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "[!] SetupDiGetClassDevs failed: %lu\n", GetLastError());
        return -1;
    }

    int found = 0;
    SP_DEVICE_INTERFACE_DATA iface;
    iface.cbSize = sizeof(iface);

    for (DWORD idx = 0; ; idx++) {
        if (!SetupDiEnumDeviceInterfaces(di, NULL, &hidGuid, idx, &iface))
            break;                      // ERROR_NO_MORE_ITEMS (GLE=259)

        // Step 1: get required buffer size
        DWORD needed = 0;
        SetupDiGetDeviceInterfaceDetailW(di, &iface, NULL, 0, &needed, NULL);
        if (needed == 0) continue;

        // Step 2: allocate and fill
        SP_DEVICE_INTERFACE_DETAIL_DATA_W* det =
            (SP_DEVICE_INTERFACE_DETAIL_DATA_W*)malloc(needed);
        if (!det) continue;
        det->cbSize = sizeof(*det);     // Must be sizeof the struct (5 bytes ANSI, 6 bytes Unicode)
                                        // On 64-bit Unicode builds: sizeof = 8; but Win32 docs say
                                        // set cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W)
        if (!SetupDiGetDeviceInterfaceDetailW(di, &iface, det, needed, NULL, NULL)) {
            free(det);
            continue;
        }

        // Open with access=0 to query attributes without affecting sharing
        HANDLE h = CreateFileW(det->DevicePath, 0,
                               FILE_SHARE_READ | FILE_SHARE_WRITE,
                               NULL, OPEN_EXISTING, 0, NULL);
        if (h == INVALID_HANDLE_VALUE) {
            free(det);
            continue;
        }

        HIDD_ATTRIBUTES attr = { sizeof(attr) };
        BOOL ok = HidD_GetAttributes(h, &attr);
        if (!ok || attr.VendorID != TARGET_VID || !isTargetPID(attr.ProductID)) {
            CloseHandle(h);
            free(det);
            continue;
        }

        // ClickShare device found -- fill DevInfo
        if (found < maxOut) {
            DevInfo* d = &out[found];
            wcscpy_s(d->path, det->DevicePath);
            d->vid = attr.VendorID;
            d->pid = attr.ProductID;
            d->fw  = attr.VersionNumber;

            PHIDP_PREPARSED_DATA pp = NULL;
            HIDP_CAPS caps = {};
            if (HidD_GetPreparsedData(h, &pp)) {
                HidP_GetCaps(pp, &caps);
                HidD_FreePreparsedData(pp);
            }
            d->usagePage  = caps.UsagePage;
            d->usage      = caps.Usage;
            d->inputLen   = caps.InputReportByteLength;
            d->outputLen  = caps.OutputReportByteLength;

            d->product[0] = 0;
            HidD_GetProductString(h, d->product, sizeof(d->product));
        }
        CloseHandle(h);
        free(det);
        found++;
    }

    SetupDiDestroyDeviceInfoList(di);
    return found;
}

// ---------------------------------------------------------------------------
// Test one device -- open with various flags, then read/write
// ---------------------------------------------------------------------------
static void testDevice(const DevInfo* d, int num)
{
    setColour(CYAN);
    printf("----------------------------------------\n");
    printf("  #%d  %s\n", num, roleStr(d->usage));
    printf("----------------------------------------\n");
    resetColour();
    printf("  Path    : %ls\n", d->path);
    printf("  VID/PID : 0x%04X / 0x%04X (%s)   FW=0x%04X\n", d->vid, d->pid, genStr(d->pid), d->fw);
    printf("  Usage   : Page=0x%04X  Usage=0x%04X\n", d->usagePage, d->usage);
    printf("  Reports : Input=%uB  Output=%uB\n", d->inputLen, d->outputLen);
    if (d->product[0]) printf("  Product : %ls\n", d->product);
    printf("\n");

    HANDLE h;
    DWORD  gle;
    BOOL   ok;

    // ---- [A] access=0  (existence probe, never SHARING_VIOLATION) ----
    h = CreateFileW(d->path, 0,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    NULL, OPEN_EXISTING, 0, NULL);
    gle = GetLastError();
    ok  = (h != INVALID_HANDLE_VALUE);
    setColour(ok ? GREEN : RED);
    printf("  [A] Exist  (access=0)     : %s\n", ok ? "OK -- device present" : errStr(gle));
    resetColour();
    if (ok) CloseHandle(h);

    // ---- [B] Read-only + ShareRW ----
    h = CreateFileW(d->path, GENERIC_READ,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    NULL, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, NULL);
    gle = GetLastError();
    ok  = (h != INVALID_HANDLE_VALUE);
    setColour(ok ? GREEN : RED);
    printf("  [B] RO  + ShareRW         : %s\n", ok ? "OK" : errStr(gle));
    resetColour();
    if (ok) CloseHandle(h);

    // ---- [C] RW + ShareR  (exact rawhid_open flags) ----
    h = CreateFileW(d->path, GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ,
                    NULL, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, NULL);
    gle = GetLastError();
    ok  = (h != INVALID_HANDLE_VALUE);
    if (ok) {
        setColour(GREEN);
        printf("  [C] RW  + ShareR (rawhid) : OK  <-- rawhid_open() will SUCCEED\n");
        CloseHandle(h);
    } else {
        setColour(RED);
        printf("  [C] RW  + ShareR (rawhid) : %s  <-- rawhid_open() FAILS\n", errStr(gle));
    }
    resetColour();

    // ---- [D] RW + ShareRW; send gruutctrl_GetVersionNumber (29) if CONTROL interface ----
    h = CreateFileW(d->path, GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    NULL, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, NULL);
    gle = GetLastError();
    ok  = (h != INVALID_HANDLE_VALUE);
    setColour(ok ? CYAN : YELLOW);
    printf("  [D] RW  + ShareRW         : %s\n", ok ? "OK" : errStr(gle));
    resetColour();
    if (ok) CloseHandle(h);

    // ---- Verdict ----
    printf("\n");
    setColour(WHITE);
    printf("  VERDICT: ");

    // Re-probe [A] and [C] cleanly
    HANDLE hA = CreateFileW(d->path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    DWORD  eA = GetLastError();
    HANDLE hC = CreateFileW(d->path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, NULL);
    DWORD  eC = GetLastError();

    if (hA == INVALID_HANDLE_VALUE) {
        setColour(RED);
        printf("DEVICE NOT FOUND (button not connected, or driver missing)\n");
    } else if (hC == INVALID_HANDLE_VALUE && eC == ERROR_SHARING_VIOLATION) {
        setColour(RED);
        printf("DEVICE BLOCKED (SHARING_VIOLATION)\n");
        resetColour();
        printf("         Another process holds exclusive RW handle.\n");
        printf("         ClickShare Desktop App will report 'device not found'\n");
        printf("         due to rawhid_open() bug (SHARING_VIOLATION silently eaten).\n");
    } else if (hC != INVALID_HANDLE_VALUE) {
        setColour(GREEN);
        printf("OK -- device accessible, rawhid_open() should succeed\n");
    } else {
        setColour(YELLOW);
        printf("UNEXPECTED -- %s\n", errStr(eC));
    }
    resetColour();

    if (hA != INVALID_HANDLE_VALUE) CloseHandle(hA);
    if (hC != INVALID_HANDLE_VALUE) CloseHandle(hC);
    printf("\n");
}

// ---------------------------------------------------------------------------
// Show running ClickShare / Barco processes via WMI (simple approach via tasklist)
// ---------------------------------------------------------------------------
static void showProcesses()
{
    setColour(YELLOW);
    printf("[3] Running ClickShare / Barco processes:\n");
    resetColour();

    // Use CreateProcess to run tasklist /FI and capture output
    SECURITY_ATTRIBUTES sa = { sizeof(sa), NULL, TRUE };
    HANDLE hRead, hWrite;
    if (!CreatePipe(&hRead, &hWrite, &sa, 0)) return;

    STARTUPINFOA si = {};
    si.cb          = sizeof(si);
    si.dwFlags     = STARTF_USESTDHANDLES;
    si.hStdOutput  = hWrite;
    si.hStdError   = hWrite;

    PROCESS_INFORMATION pi = {};
    char cmd[] = "tasklist /FI \"IMAGENAME eq *clickshare*\" /FO CSV /NH";
    // tasklist doesn't support wildcard in IMAGENAME filter; use two calls
    const char* filters[] = {
        "tasklist /FO CSV /NH",
        NULL
    };
    (void)filters;

    // Simpler: just use system() and redirect -- but we need to capture.
    // Use CreateProcess with "cmd /c tasklist /FO CSV /NH"
    char cmd2[] = "cmd /c tasklist /FO CSV /NH 2>nul";
    SetHandleInformation(hRead, HANDLE_FLAG_INHERIT, 0);

    if (CreateProcessA(NULL, cmd2, NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        CloseHandle(hWrite);
        CloseHandle(pi.hThread);

        char buf[4096] = {};
        DWORD n = 0;
        // Read all output
        char line[512] = {};
        int  li = 0;
        bool found = false;

        while (ReadFile(hRead, buf, sizeof(buf)-1, &n, NULL) && n > 0) {
            buf[n] = 0;
            for (DWORD i = 0; i < n; i++) {
                char c = buf[i];
                if (c == '\n' || c == '\r') {
                    line[li] = 0;
                    if (li > 0) {
                        // Check if line contains clickshare or barco (case-insensitive)
                        char lower[512]; int j=0;
                        while (line[j]) { lower[j] = (char)tolower((unsigned char)line[j]); j++; }
                        lower[j]=0;
                        if (strstr(lower, "clickshare") || strstr(lower, "barco")) {
                            setColour(RED);
                            printf("  %s\n", line);
                            resetColour();
                            found = true;
                        }
                    }
                    li = 0;
                } else if (li < (int)sizeof(line)-2) {
                    line[li++] = c;
                }
            }
        }
        WaitForSingleObject(pi.hProcess, 3000);
        CloseHandle(pi.hProcess);
        if (!found) {
            setColour(GREEN);
            printf("  None found\n");
            resetColour();
        }
    } else {
        CloseHandle(hWrite);
        printf("  (could not run tasklist: %lu)\n", GetLastError());
    }
    CloseHandle(hRead);
    printf("\n");
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------
int main()
{
    // Enable ANSI / colour on modern Windows consoles
    HANDLE hCon = GetStdHandle(STD_OUTPUT_HANDLE);
    DWORD  mode = 0;
    GetConsoleMode(hCon, &mode);
    SetConsoleMode(hCon, mode | ENABLE_VIRTUAL_TERMINAL_PROCESSING);

    setColour(CYAN);
    printf("========================================\n");
    printf("  ClickShare HID Device Test\n");
    printf("  Target VID=0x%04X  PID=0x%04X(Gen4)/0x%04X(Gen5)\n",
           TARGET_VID, TARGET_PID_GEN4, TARGET_PID_GEN5);
    printf("========================================\n");
    resetColour();
    printf("\n");

    // ---- [1] Enumerate ----
    setColour(YELLOW);
    printf("[1] Enumerating HID devices...\n");
    resetColour();

    static DevInfo devs[32];
    int cnt = enumerateClickShare(devs, 32);

    if (cnt < 0) {
        setColour(RED);
        printf("    ERROR: enumeration failed (try running as Administrator)\n");
        resetColour();
        return 1;
    }

    if (cnt == 0) {
        setColour(RED);
        printf("    ** NO ClickShare HID devices found **\n");
        resetColour();
        printf("    -> Button not connected, or HidUsb not bound to MI_01/02/03\n\n");
    } else {
        setColour(GREEN);
        printf("    Found %d ClickShare HID interface(s)\n", cnt);
        resetColour();
        printf("\n");

        // ---- [2] Test each device ----
        setColour(YELLOW);
        printf("[2] Testing each device...\n\n");
        resetColour();

        for (int i = 0; i < cnt; i++)
            testDevice(&devs[i], i + 1);
    }

    // ---- [3] Processes ----
    showProcesses();

    printf("Done.\n");
    return 0;
}
