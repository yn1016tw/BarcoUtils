<#
.SYNOPSIS
    Verify configuration-manager-apk's three data repositories (clickshare / system / mdep)
    via ADB, useful for regression testing when comparing old vs new mdep builds.

.DESCRIPTION
    Read tests (always run):
    - clickshare repo: (1) uses the ContentProvider custom "export_config" method to dump all
      key/value pairs at once (ConfigExportManager.export(), schema defined by ProtoSchemaWalker),
      AND (2) additionally queries each individual key listed in ClickshareDefaultPreferences.kt
      one by one via content://<authority>/clickshare/<key>, so a single bad field can't hide
      behind an overall "success=true" from the bulk export.
    - system repo: queries each known key listed in SystemKeys.kt
    - mdep repo: queries each known key listed in MdepPropertyType.kt (this repo goes straight
      into mdep-sdk, so it's the most important group for validating new mdep compatibility)

    Write round-trip tests (always run for the "safe" set, opt-in for "disruptive" set):
    For each writable key: read original value -> write a new test value -> read back to
    confirm the write took effect -> write the original value back -> read back to confirm
    restoration. Keys whose set() always returns false (read-only, e.g. Properties.*,
    SelectedProvider, MSTeamsVersion, BluetoothState, BluetoothMacAddress) are excluded.
    Keys with side effects that are harder to fully reverse or are disruptive to the device
    (Bluetooth radio toggle, Language, NarratorEnabled/accessibility service, TimeZone,
    Settings.SetupWizardHasRun) are skipped unless -IncludeDisruptiveTests is specified.

    Every result is logged as success/failure, both to console and to a timestamped log file,
    so you can diff two runs (old mdep vs new mdep) easily.

.PARAMETER Serial
    Target device serial (use when multiple devices are connected). Maps to `adb -s <serial>`.

.PARAMETER OutDir
    Output folder for the log file. Defaults to a `results` folder next to this script.

.PARAMETER IncludeDisruptiveTests
    Also run write round-trip tests for keys that have disruptive side effects
    (Bluetooth radio, Language, Narrator/accessibility, TimeZone, SetupWizardHasRun).
    Off by default.

.EXAMPLE
    ./verify_all_keys.ps1
    ./verify_all_keys.ps1 -Serial 1234567890ABCDEF -OutDir C:\temp\mdep2026-verify
    ./verify_all_keys.ps1 -IncludeDisruptiveTests
#>

param(
    [string]$Serial = "",
    [string]$OutDir = (Join-Path $PSScriptRoot "results"),
    [switch]$IncludeDisruptiveTests
)

$ErrorActionPreference = "Continue"

$Authority = "com.barco.clickshare.configurationmanager.provider"

# --- clickshare repo: keys from ClickshareDefaultPreferences.kt ---
# This repo has far more keys (68) than system/mdep, and most of them are runtime state
# (WiFi/Ethernet status, firmware update progress, connected-button counters, etc.) rather
# than user-configurable settings, which is why it was originally only smoke-tested via the
# bulk "export_config" call above. This per-key loop closes that gap for read coverage.
$ClickshareKeys = @(
    "BaseUnit.Audio.Enabled",
    "BaseUnit.DeviceInfo.UnboxedState",
    "BaseUnit.DeviceInfo.Hostname",
    "BaseUnit.DeviceInfo.HardwareVersion",
    "BaseUnit.DeviceInfo.ServiceProvider",
    "BaseUnit.DeviceInfo.MtrSharingSource",
    "BaseUnit.Ethernet.InterfaceNumberOfEntries",
    "BaseUnit.Ethernet.Interface.1.IPv4AddressNumberOfEntries",
    "BaseUnit.Ethernet.Interface.1.IPv4Address.1.IPAddress",
    "BaseUnit.Ethernet.Interface.1.IPv4Address.1.AddressingType",
    "BaseUnit.Ethernet.Interface.1.IPv4Address.1.SubnetMask",
    "BaseUnit.Ethernet.Interface.1.IPv4Address.1.GatewayIPAddress",
    "BaseUnit.Ethernet.Interface.1.IPv4Address.1.DNSServers",
    "BaseUnit.Ethernet.Interface.1.IPv4Address.1.Domain",
    "BaseUnit.Ethernet.Interface.1.IPv4Address.1.LinkStatus",
    "BaseUnit.Software.AlwaysUpdateButtons",
    "BaseUnit.Standby.StandbyState",
    "BaseUnit.Standby.StandbyTime",
    "BaseUnit.Standby.StandbyMode",
    "BaseUnit.WiFi.AccessPointNumberOfEntries",
    "BaseUnit.WiFi.AccessPoint.1.Enable",
    "BaseUnit.WiFi.AccessPoint.1.Status",
    "BaseUnit.WiFi.AccessPoint.1.SupportedFrequencyBand",
    "BaseUnit.WiFi.AccessPoint.1.CurrentFrequencyBand",
    "BaseUnit.WiFi.AccessPoint.1.2gChannel",
    "BaseUnit.WiFi.AccessPoint.1.5gChannel",
    "BaseUnit.WiFi.AccessPoint.1.6gChannel",
    "BaseUnit.WiFi.AccessPoint.1.CurrentChannel",
    "BaseUnit.WiFi.AccessPoint.1.Security.ModesSupported",
    "BaseUnit.WiFi.AccessPoint.1.Security.ModeEnabled",
    "BaseUnit.WiFi.AccessPoint.1.Security.PreSharedKey",
    "BaseUnit.WiFi.AccessPoint.1.Security.KeyPassphrase",
    "BaseUnit.WiFi.AccessPoint.1.SSIDBroadcastEnabled",
    "BaseUnit.WiFi.AccessPoint.1.CountryCode",
    "BaseUnit.WiFi.AccessPoint.1.IPv4AddressNumberOfEntries",
    "BaseUnit.WiFi.AccessPoint.1.IPv4Address.1.AddressingType",
    "BaseUnit.WiFi.AccessPoint.1.IPv4Address.1.SubnetMask",
    "BaseUnit.WiFi.AccessPoint.1.IPv4Address.1.IPAddress",
    "BaseUnit.WiFi.AccessPoint.1.AutoChannelSelection",
    "BaseUnit.WiFi.AccessPoint.1.SetApSignalStrength",
    "BaseUnit.WiFi.AccessPoint.1.NumberOfConnectedClients",
    "BaseUnit.WiFi.AccessPoint.1.MACAddress",
    "BaseUnit.WiFi.AccessPoint.1.CurrentDeviceOperationMode",
    "BaseUnit.WiFi.AccessPoint.1.SupportedDeviceOperationMode",
    "BaseUnit.WiFi.TLVVersion",
    "BaseUnit.Pairing.Streaming",
    "BaseUnit.Firmware.AllowUpdateOverUSB",
    "BaseUnit.Firmware.DownloadProgress",
    "BaseUnit.Firmware.IsDownloading",
    "BaseUnit.Firmware.IsSuccessful",
    "BaseUnit.Firmware.IsInstalling",
    "BaseUnit.Firmware.InstallProgress",
    "BaseUnit.Firmware.LastUpdateTime",
    "BaseUnit.Firmware.UpdateInProgress",
    "BaseUnit.Firmware.UpdateMessage",
    "BaseUnit.Firmware.UpdateStatus",
    "BaseUnit.Firmware.AutoUpdate.Enabled",
    "BaseUnit.Firmware.AutoUpdate.UpdateTime",
    "BaseUnit.Displays.ShowWallpaper",
    "BaseUnit.AssociatedButtons.ButtonNumberOfEntries",
    "BaseUnit.AssociatedButtons.NumButtonsNotConnectedToClient",
    "BaseUnit.AssociatedButtons.NumberOfConnectedButtons",
    "BaseUnit.AssociatedButtons.UpdateOverWiFi",
    "BaseUnit.Proxy.Enable",
    "BaseUnit.XMS.Instance",
    "BaseUnit.XMS.DeviceClaimed",
    "BaseUnit.XMS.Tenant",
    "BaseUnit.XMS.FactoryReset"
)

# --- system repo: keys from SystemManager.kt (SystemKeys) ---
$SystemKeys = @(
    "Settings.ScreenOffTimeout",
    "Properties.SystemBuildDate",
    "Properties.SystemBuildVersion",
    "Properties.SystemBuildMinimalVersion",
    "Properties.ProductName",
    "Properties.ModelName",
    "Properties.DeviceName",
    "Properties.Barco.ArticleNumber",
    "Properties.Barco.BuildType",
    "Properties.Barco.BuildReleaseChannel",
    "Properties.Barco.PlatformName",
    "Properties.Barco.ProductName",
    "Properties.Barco.FirstBoot",
    "Properties.Brand",
    "Properties.Manufacturer",
    "Properties.SerialNumber",
    "Properties.Barco.DefaultSerialNumber",
    "Properties.Barco.CountryCode",
    "Properties.Barco.Platform",
    "Properties.Sys.Wlan0.Mac",
    "Properties.Mdep.BuildId",
    "Settings.SetupWizardHasRun"
)

# --- mdep repo: keys from MdepPropertyType.kt, hits mdep-sdk (ISystemManager etc.) directly ---
$MdepKeys = @(
    "MdepProperties.TextSize",
    "MdepProperties.ColorCorrection",
    "MdepProperties.MSTeamsVersion",
    "MdepProperties.HighContrastMode",
    "MdepProperties.NarratorEnabled",
    "MdepProperties.Bluetooth",
    "MdepProperties.BluetoothState",
    "MdepProperties.BluetoothDeviceName",
    "MdepProperties.BluetoothMacAddress",
    "MdepProperties.Language",
    "MdepProperties.TimeZone",
    "MdepProperties.TimeFormat",
    "MdepProperties.NtpEnabled",
    "MdepProperties.NtpServer",
    "MdepProperties.SelectedProvider"
)

# --- write round-trip test definitions ---
# NextValue is a scriptblock: given the current value, returns a different, valid test value.
# Disruptive = $true means the write has a real, harder-to-fully-undo side effect on the
# device (radio toggle, UI language, accessibility service, timezone, OOBE flag) and is only
# run when -IncludeDisruptiveTests is passed.
$WriteTests = @(
    @{ Repo = "system"; Key = "Settings.ScreenOffTimeout"; Disruptive = $false
       NextValue = { param($cur) if ($cur -eq "600000") { "300000" } else { "600000" } } }

    @{ Repo = "mdep"; Key = "MdepProperties.TextSize"; Disruptive = $false
       NextValue = {
           param($cur)
           $opts = @("Small", "Default", "Large", "Largest")
           $idx = [array]::IndexOf($opts, $cur)
           $opts[($idx + 1) % $opts.Count]
       } }

    @{ Repo = "mdep"; Key = "MdepProperties.ColorCorrection"; Disruptive = $false
       NextValue = {
           param($cur)
           $opts = @("Off", "Protanomaly", "Deuteranomaly", "Tritanomaly")
           $idx = [array]::IndexOf($opts, $cur)
           if ($idx -lt 0) { $idx = 0 }
           $opts[($idx + 1) % $opts.Count]
       } }

    @{ Repo = "mdep"; Key = "MdepProperties.HighContrastMode"; Disruptive = $false
       NextValue = { param($cur) if ($cur -eq "1") { "0" } else { "1" } } }

    @{ Repo = "mdep"; Key = "MdepProperties.TimeFormat"; Disruptive = $false
       NextValue = { param($cur) if ($cur -eq "true") { "false" } else { "true" } } }

    @{ Repo = "mdep"; Key = "MdepProperties.NtpEnabled"; Disruptive = $false
       NextValue = { param($cur) if ($cur -eq "true") { "false" } else { "true" } } }

    # MdepProperties.NtpServer is intentionally excluded from the automated write test.
    # NtpServerProperty.set() validates input against android.util.Patterns.WEB_URL, which
    # only accepts http(s):// scheme values. The value observed on real devices uses an
    # "ntp://" scheme, so set() always rejects it (isValidNtpServer returns false) no matter
    # what test value the script picks. Writing an https:// test value would succeed, but
    # restoring the original "ntp://" value afterwards would then fail the same validation,
    # permanently changing the device value. Verify this key manually with adb if needed:
    #   adb shell content query --uri content://<authority>/mdep/MdepProperties.NtpServer
    #   adb shell content update --uri content://<authority>/mdep/MdepProperties.NtpServer --bind value:s:https://time.google.com
    #   adb shell content query --uri content://<authority>/mdep/MdepProperties.NtpServer

    @{ Repo = "mdep"; Key = "MdepProperties.BluetoothDeviceName"; Disruptive = $false
       NextValue = { param($cur) "$cur-VerifyTest" } }

    # --- clickshare repo: safe, purely local settings with no network/cloud/update side effects ---
    @{ Repo = "clickshare"; Key = "BaseUnit.Audio.Enabled"; Disruptive = $false
       NextValue = { param($cur) if ($cur -eq "true") { "false" } else { "true" } } }

    @{ Repo = "clickshare"; Key = "BaseUnit.Software.AlwaysUpdateButtons"; Disruptive = $false
       NextValue = { param($cur) if ($cur -eq "true") { "false" } else { "true" } } }

    @{ Repo = "clickshare"; Key = "BaseUnit.Displays.ShowWallpaper"; Disruptive = $false
       NextValue = { param($cur) if ($cur -eq "true") { "false" } else { "true" } } }

    @{ Repo = "clickshare"; Key = "BaseUnit.Firmware.AllowUpdateOverUSB"; Disruptive = $false
       NextValue = { param($cur) if ($cur -eq "true") { "false" } else { "true" } } }

    @{ Repo = "clickshare"; Key = "BaseUnit.AssociatedButtons.UpdateOverWiFi"; Disruptive = $false
       NextValue = { param($cur) if ($cur -eq "true") { "false" } else { "true" } } }

    @{ Repo = "clickshare"; Key = "BaseUnit.Standby.StandbyTime"; Disruptive = $false
       NextValue = { param($cur) if ($cur -eq "10") { "15" } else { "10" } } }

    # --- clickshare repo, disruptive: touches the AP's own WiFi broadcast / proxy path.
    # Since this script talks to the device over adb (possibly over the same WiFi/TCP link,
    # e.g. -Serial 10.102.90.60:5555), a bad write here could cut off the adb session itself.
    # Only run with -IncludeDisruptiveTests, and prefer a wired/USB adb session when doing so.
    @{ Repo = "clickshare"; Key = "BaseUnit.WiFi.AccessPoint.1.SSIDBroadcastEnabled"; Disruptive = $true
       NextValue = { param($cur) if ($cur -eq "true") { "false" } else { "true" } } }

    @{ Repo = "clickshare"; Key = "BaseUnit.Proxy.Enable"; Disruptive = $true
       NextValue = { param($cur) if ($cur -eq "true") { "false" } else { "true" } } }

    # NOTE: The following clickshare keys are intentionally excluded from ALL write testing,
    # even under -IncludeDisruptiveTests:
    # - BaseUnit.XMS.FactoryReset: writing "true" is expected to trigger an actual factory
    #   reset action, not just store a flag. Must never be automated.
    # - BaseUnit.WiFi.AccessPoint.1.Enable / Security.* / IPv4Address.* / Ethernet.*:
    #   can disable the device's own AP or change its IP/security config, permanently
    #   dropping any adb-over-WiFi session with no way to reconnect without physical access.
    # - BaseUnit.Firmware.DownloadProgress / IsDownloading / IsSuccessful / IsInstalling /
    #   InstallProgress / UpdateInProgress / UpdateStatus / UpdateMessage / LastUpdateTime:
    #   these mirror the real, in-progress firmware update state machine; overwriting them
    #   manually can desync the UI/update logic from what's actually happening on device.
    # - BaseUnit.XMS.DeviceClaimed / BaseUnit.XMS.Tenant: changes the device's cloud
    #   claim/tenant association, which is not trivially reversible via adb alone.
    # - BaseUnit.Pairing.Streaming: side effect on an active screen-sharing session is
    #   unclear and was not verified to be safely reversible.
    # Verify these manually with adb if needed, e.g.:
    #   adb shell content query --uri content://<authority>/clickshare/BaseUnit.XMS.FactoryReset

    # --- Disruptive: only run with -IncludeDisruptiveTests ---
    @{ Repo = "mdep"; Key = "MdepProperties.Bluetooth"; Disruptive = $true
       NextValue = { param($cur) if ($cur -eq "true") { "false" } else { "true" } } }

    @{ Repo = "mdep"; Key = "MdepProperties.NarratorEnabled"; Disruptive = $true
       NextValue = { param($cur) if ($cur -eq "Enabled") { "Disabled" } else { "Enabled" } } }

    @{ Repo = "system"; Key = "Settings.SetupWizardHasRun"; Disruptive = $true
       NextValue = { param($cur) if ($cur -eq "1") { "0" } else { "1" } } }

    # NOTE: Language and TimeZone are intentionally NOT included even under
    # -IncludeDisruptiveTests. get() returns a display label (not necessarily the raw
    # value set() expects), so an automated round-trip cannot safely guarantee restoration.
    # Verify these two manually if needed.
)

function Get-AdbArgs {
    if ($Serial) { return @("-s", $Serial) }
    return @()
}

function Invoke-Adb {
    # NOTE: parameter must NOT be named $Args - that collides with PowerShell's
    # built-in automatic $args variable and silently breaks splatting.
    param([string[]]$AdbCmdArgs)
    $adbArgs = (Get-AdbArgs) + $AdbCmdArgs
    return (& adb @adbArgs 2>&1)
}

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $OutDir "config_manager_verify_$timestamp.log"

$readResults = New-Object System.Collections.Generic.List[object]
$writeResults = New-Object System.Collections.Generic.List[object]

function Write-Log {
    param([string]$Line)
    Write-Host $Line
    Add-Content -Path $logFile -Value $Line
}

function Test-QueryResult {
    param([string]$Output)
    # Typical failure markers from ADB content query output.
    # NOTE: "Exception" alone already catches "SecurityException" as a substring, so there's
    # no need for a separate "Security" keyword - which would otherwise false-positive on real
    # clickshare keys that legitimately contain "Security" in their name (e.g.
    # BaseUnit.WiFi.AccessPoint.1.Security.ModeEnabled).
    if ($Output -match "Error|Exception|no such provider") { return $false }
    if ([string]::IsNullOrWhiteSpace($Output)) { return $false }
    return $true
}

function Get-KeyValue {
    param([string]$Repo, [string]$Key)
    $uri = "content://$Authority/$Repo/$Key"
    $out = Invoke-Adb -AdbCmdArgs @("shell", "content", "query", "--uri", $uri)
    $joined = ($out -join "`n")
    if (-not (Test-QueryResult $joined)) { return $null }
    if ($joined -match "value=(.*)$") { return $matches[1].Trim() }
    return $null
}

function Set-KeyValue {
    param([string]$Repo, [string]$Key, [string]$Value)
    $uri = "content://$Authority/$Repo/$Key"
    return (Invoke-Adb -AdbCmdArgs @("shell", "content", "update", "--uri", $uri, "--bind", "value:s:$Value"))
}

Write-Log "===================================================================="
Write-Log "Configuration-Manager-Apk ADB verification  |  $timestamp"
Write-Log "Authority: $Authority"
if ($Serial) { Write-Log "Device: $Serial" }
if ($IncludeDisruptiveTests) { Write-Log "Disruptive write tests: ENABLED" } else { Write-Log "Disruptive write tests: disabled (use -IncludeDisruptiveTests to enable)" }
Write-Log "===================================================================="

# ================= READ TESTS =================

# 1) clickshare repo: export everything at once
Write-Log ""
Write-Log "---- [READ][clickshare] export_config (covers all clickshare repo keys) ----"
$exportOut = Invoke-Adb -AdbCmdArgs @("shell", "content", "call", "--uri", "content://$Authority/", "--method", "export_config")
$exportOk = ($exportOut -join "`n") -match 'success=true'
Write-Log ($exportOut -join "`n")
$readResults.Add([pscustomobject]@{ Repo = "clickshare"; Key = "(export_config)"; Success = $exportOk })
Write-Log "Result: $(if ($exportOk) {'OK'} else {'FAIL'})"

# 1b) clickshare repo: also query each key individually, so one broken field
#     can't hide behind the aggregate "success=true" of export_config above.
Write-Log ""
Write-Log "---- [READ][clickshare] querying ClickshareDefaultPreferences keys individually ----"
foreach ($key in $ClickshareKeys) {
    $uri = "content://$Authority/clickshare/$key"
    $out = Invoke-Adb -AdbCmdArgs @("shell", "content", "query", "--uri", $uri)
    $ok = Test-QueryResult ($out -join "`n")
    $readResults.Add([pscustomobject]@{ Repo = "clickshare"; Key = $key; Success = $ok })
    Write-Log ("[{0}] clickshare/{1} => {2}" -f $(if ($ok) {"OK"} else {"FAIL"}), $key, (($out -join ' ') -replace '\s+', ' '))
}

# 2) system repo: query each key
Write-Log ""
Write-Log "---- [READ][system] querying SystemKeys ----"
foreach ($key in $SystemKeys) {
    $uri = "content://$Authority/system/$key"
    $out = Invoke-Adb -AdbCmdArgs @("shell", "content", "query", "--uri", $uri)
    $ok = Test-QueryResult ($out -join "`n")
    $readResults.Add([pscustomobject]@{ Repo = "system"; Key = $key; Success = $ok })
    Write-Log ("[{0}] system/{1} => {2}" -f $(if ($ok) {"OK"} else {"FAIL"}), $key, (($out -join ' ') -replace '\s+', ' '))
}

# 3) mdep repo: query each key (key group for validating new mdep compatibility)
Write-Log ""
Write-Log "---- [READ][mdep] querying MdepPropertyType (primary validation target) ----"
foreach ($key in $MdepKeys) {
    $uri = "content://$Authority/mdep/$key"
    $out = Invoke-Adb -AdbCmdArgs @("shell", "content", "query", "--uri", $uri)
    $ok = Test-QueryResult ($out -join "`n")
    $readResults.Add([pscustomobject]@{ Repo = "mdep"; Key = $key; Success = $ok })
    Write-Log ("[{0}] mdep/{1} => {2}" -f $(if ($ok) {"OK"} else {"FAIL"}), $key, (($out -join ' ') -replace '\s+', ' '))
}

# ================= WRITE ROUND-TRIP TESTS =================

Write-Log ""
Write-Log "---- [WRITE] round-trip tests (write -> read back -> restore -> read back) ----"
foreach ($test in $WriteTests) {
    if ($test.Disruptive -and -not $IncludeDisruptiveTests) {
        Write-Log ("[SKIP] {0}/{1} (disruptive, use -IncludeDisruptiveTests to enable)" -f $test.Repo, $test.Key)
        $writeResults.Add([pscustomobject]@{ Repo = $test.Repo; Key = $test.Key; Success = $null; Skipped = $true })
        continue
    }

    $repo = $test.Repo
    $key = $test.Key

    $original = Get-KeyValue -Repo $repo -Key $key
    if ($null -eq $original) {
        Write-Log ("[FAIL] {0}/{1} => could not read baseline value, skipping write test" -f $repo, $key)
        $writeResults.Add([pscustomobject]@{ Repo = $repo; Key = $key; Success = $false; Skipped = $false })
        continue
    }

    $testValue = & $test.NextValue $original

    Set-KeyValue -Repo $repo -Key $key -Value $testValue | Out-Null
    Start-Sleep -Milliseconds 500
    $afterWrite = Get-KeyValue -Repo $repo -Key $key
    $writeOk = ($afterWrite -eq $testValue)

    # Always attempt to restore, even if the write verification above failed.
    Set-KeyValue -Repo $repo -Key $key -Value $original | Out-Null
    Start-Sleep -Milliseconds 500
    $afterRestore = Get-KeyValue -Repo $repo -Key $key
    $restoreOk = ($afterRestore -eq $original)

    $ok = $writeOk -and $restoreOk
    $writeResults.Add([pscustomobject]@{ Repo = $repo; Key = $key; Success = $ok; Skipped = $false })

    Write-Log ("[{0}] {1}/{2} original='{3}' -> test='{4}' (write {5}) -> restored='{6}' (restore {7})" -f `
        $(if ($ok) { "OK" } else { "FAIL" }), $repo, $key, $original, $testValue, `
        $(if ($writeOk) { "OK" } else { "FAIL" }), $afterRestore, $(if ($restoreOk) { "OK" } else { "FAIL" }))

    if (-not $restoreOk) {
        Write-Log ("  *** WARNING: restore FAILED for {0}/{1}. Expected '{2}' but got '{3}'. Manual check recommended. ***" -f $repo, $key, $original, $afterRestore)
    }
}

# --- Summary ---
Write-Log ""
Write-Log "===================================================================="
Write-Log "Summary"
Write-Log "===================================================================="

Write-Log ""
Write-Log "-- Read tests --"
$groupedRead = $readResults | Group-Object Repo
foreach ($g in $groupedRead) {
    $pass = ($g.Group | Where-Object Success).Count
    $total = $g.Group.Count
    Write-Log ("{0,-12}: {1}/{2} passed" -f $g.Name, $pass, $total)
}

Write-Log ""
Write-Log "-- Write round-trip tests --"
$writeRun = $writeResults | Where-Object { -not $_.Skipped }
$writeSkipped = $writeResults | Where-Object { $_.Skipped }
$writePass = ($writeRun | Where-Object Success).Count
Write-Log ("write       : {0}/{1} passed ({2} skipped)" -f $writePass, $writeRun.Count, $writeSkipped.Count)

$failedRead = $readResults | Where-Object { -not $_.Success }
$failedWrite = $writeRun | Where-Object { -not $_.Success }

if ($failedRead.Count -gt 0 -or $failedWrite.Count -gt 0) {
    Write-Log ""
    Write-Log "Failed items:"
    foreach ($f in $failedRead) {
        Write-Log ("  - [READ][{0}] {1}" -f $f.Repo, $f.Key)
    }
    foreach ($f in $failedWrite) {
        Write-Log ("  - [WRITE][{0}] {1}" -f $f.Repo, $f.Key)
    }
} else {
    Write-Log ""
    Write-Log "All keys verified successfully."
}

Write-Log ""
Write-Log "Full log saved to: $logFile"

# Exit code for CI / caller: non-zero if any failure
if ($failedRead.Count -gt 0 -or $failedWrite.Count -gt 0) {
    exit 1
} else {
    exit 0
}
