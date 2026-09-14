<#
.SYNOPSIS
    GOD-specific: verify com.barco.clickshare.ledmanager (Led Manager apk) via ADB, including a
    full sweep of every LED behavior reachable over ADB, cross-checked against the GOD LED
    behaviors wiki.

.DESCRIPTION
    Platform scope: this script targets GOD (w4god, MT8189, ClickShare-only) specifically - the
    LED behavior spec it checks against (the wiki linked below) is titled "GOD | LED behaviors"
    and was written/verified against a w4god device (ClickShare Conference / C_100B). Duvel may
    use the same led-manager-apk and LED-related classes, but its LED behavior spec/hardware
    have not been confirmed to match this script's expectations - do not assume this script is
    valid on a w4duvel device without re-checking against Duvel's own LED behavior documentation.

    led-manager-apk has no ContentProvider/AIDL-over-adb surface of its own (its only external
    interfaces are a bound AIDL service and a dynamically-registered broadcast receiver for
    ACTION_PAIRING_BUTTON) - see LedManagerService.kt / LedManagerBroadcastReceiver.kt. What IS
    directly observable over ADB is:
    - the LED state it reports into configuration-manager-apk: LedManager.updateLedStateInConfig
      urationManager() writes the active scenario's LedType name into the ContentProvider key
      "BaseUnit.Led.State" (authority com.barco.clickshare.configurationmanager.provider) every
      time the active scenario changes.
    - the actual color/brightness/blink parameters programmed into the LED HAL, logged by the
      vendor PAL as `LedManager: setLedState enable=... brightness=... onTime=... offTime=...
      mode=...` (one call per color channel; the pattern's own start() call is always the LAST
      one logged, so grepping the tail of a fresh logcat window after a transition gives the
      final, meaningful state).

    Checks, in order:
    1. Installed - `adb shell pm list packages` contains the package; also reads the on-device
       apk's versionName/versionCode via `dumpsys package`.
    2. Running   - `adb shell pidof` (fallback: `adb shell ps -A | grep`) finds a live process.
       led-manager-apk is `android:persistent="true"`, so it should always be running once booted.
    3. Baseline value - reads "BaseUnit.Led.State" to confirm LedManager is actively reporting
       its state (proves the config-write path works, without touching real device state).
    4. (Opt-in, -TriggerScenario) Full LED behavior sweep - see below.

    Full LED behavior sweep (step 4):
    LedPatternFactory.kt maps all 16 LedType values to a concrete pattern (BlinkRed/BlinkWhite/
    StaticRed/StaticWhite/BreathWhite/off), and those patterns' setRedLedState/setWhiteLedState
    calls (see patterns/*.kt) match the GOD LED behaviors wiki
    (https://barco-nv.atlassian.net/wiki/spaces/wovcs/pages/1895432429/GOD+LED+behaviors)
    one-for-one: e.g. Error/UpdatingButtonFailed/PairingButtonFailed -> blinking red,
    Pairing/UpdatingButton -> blinking white, *Success -> static white ("ON"), Idle -> static
    white, BaseUnitInUse -> static red, BaseUnitStandbyEco -> breathing white, etc.

    Of those 16 LedType values, only the 7 reachable through LedManagerBroadcastReceiver's
    ButtonStatus -> LedType mapping (ButtonStatus.kt) can be triggered purely over ADB, by
    broadcasting synthetic ACTION_PAIRING_BUTTON events for a fake test button serial - the
    same event shape buttonmanager-apk sends during real pairing/firmware-sync flows:
        PairingButton, PairingButtonFailed, PairingButtonSuccess,
        UpdatingButton, UpdatingButtonFailed, UpdatingButtonSuccess, Idle
    For each, this script broadcasts the ButtonStatus event(s) that produce it (some need a
    preceding "Successful" status first, since LedManagerBroadcastReceiver tracks a private
    isFwUpdateSuccessful flag to disambiguate Pairing-success from Updating-success on
    "Finished.Successful" - see mapIntentToScenario), then verifies BOTH:
      (a) BaseUnit.Led.State reports the expected LedType name, and
      (b) the last `setLedState` logcat line matches the exact enable/brightness/onTime/
          offTime/mode the corresponding pattern class calls with.
    Every scenario is followed by "Finished.ButtonDetached" to clear it and a check that the
    state reverts to Idle before the next scenario starts.

    Of the remaining 9 LedType values, 8 (Error, UpdatingBaseUnit, UpdatingBaseUnitSuccess,
    UpdatingBaseUnitFailed, SoftwareReboot, BaseUnitStandbyEco, BaseUnitStandbyDeepSleep,
    BaseUnitInUse) are only ever set via the AIDL
    ILedManager.startScenario() call from other system apps (firmware updater, standby
    manager, base-unit-manager, etc.) - grep confirms led-manager-apk's own source never
    calls addScenario() with any of them, and there is no generic `adb shell` command to
    drive an AIDL bind+call directly. Instead, this script drives them through
    led-manager-apk's own `TestLedClient` test app (test-led-client module; UI-only, no
    exported components - see its README/MainActivity.kt), via
    scripts/test_led_client_cli.py, which wraps
    testcases/common/test_led_client.py's `TestLedClient` class (uiautomator-dump-based
    toggle-button control, same approach as ui_mtr.py). For each of the 8 types: taps
    TestLedClient's Client1 toggle for that LedType (start_scenario), confirms
    BaseUnit.Led.State and the setLedState pattern (same two checks as the button sweep
    above), then taps it again to stop and confirms revert to Idle.
    TestLedClient must already be installed (`./gradlew :test-led-client:assembleDebug` in
    C:\Project\Wave4\led-manager-apk, then `adb install -r -g`) - if it isn't, this part of
    the sweep is skipped (not counted as a failure) with a note to install it.
    The 9th value, ResetToDefaults, is intentionally skipped by this script - the wiki
    itself flags its LED indication as removed/dead (the underlying event only lasted
    ~5s), even though LedPatternFactory's mapping and TestLedClient's button for it are
    still present in code.

    "Booting" (wiki: Booting -> blinking white, red off; CS-100/CSE-200 instead sequence
    Off -> static red -> blinking white) is NOT covered and cannot be, by design: grep
    confirms it is not a LedType in led-manager-apk at all (no ButtonStatus mapping, no
    LedPatternFactory entry, no TestLedClient button) - it is real device boot LED
    behavior driven before/independently of led-manager-apk (bootloader/kernel/early-init
    level), so there is no ContentProvider key, AIDL call, or broadcast this script (or
    TestLedClient) could use to observe or trigger it. Verify it only by power-cycling the
    real hardware and watching the LED, or by finding whichever early-boot component
    actually drives it (outside this repo's and led-manager-apk's scope).

.NOTES
    Verified-against APK version: led-manager-apk v0.10.3 (git tag 0.10.3, commit 9143b09b,
    2026-09-04), from C:\Project\Wave4\led-manager-apk. This script hardcodes: the package
    name; the ACTION_PAIRING_BUTTON broadcast contract (session/data extras, JSON buttonList
    schema) from LedManagerBroadcastReceiver.kt; the ButtonStatus string values from
    ButtonStatus.kt; the configuration-manager-apk key "BaseUnit.Led.State" from LedManager.kt
    (KEY_LED_STATE); and the full LedType -> pattern -> (enable,brightness,onTime,offTime,mode)
    table from LedPatternFactory.kt / patterns/*.kt. The AIDL-only sweep additionally depends
    on test-led-client's MainActivity.kt/activity_main.xml resource-id naming (mirrored in
    testcases/common/test_led_client.py's LED_TYPE_BUTTON_IDS) staying in sync with LedType -
    that module is versioned together with led-manager-apk itself (same repo/tag). When
    led-manager-apk is bumped, diff those files against this version before assuming the
    script still works, and bump the "Verified-against" line above (and the matching note in
    CLAUDE.md) once confirmed. Also re-check the GOD LED behaviors wiki page (linked above) for
    any LED-behavior spec changes that might not yet be reflected in code, or vice versa.

.PARAMETER Serial
    Target device serial (use when multiple devices are connected). Maps to `adb -s <serial>`.

.PARAMETER OutDir
    Output folder for the log file. Defaults to a `results` folder next to this script.

.PARAMETER TriggerScenario
    Also run the disruptive full LED behavior sweep (see step 4 above): all 7 button-related
    scenarios via ACTION_PAIRING_BUTTON broadcasts, plus all 9 AIDL-only scenarios via
    TestLedClient (skipped with a note if TestLedClient isn't installed). Off by default,
    since it briefly overrides the Base Unit's real LED pattern for each scenario - safe to
    enable when the device is not actively demoing a specific LED look, since every scenario
    always cleans up and verifies the revert to Idle before continuing.

.EXAMPLE
    ./god_verify_led_manager_app.ps1
    ./god_verify_led_manager_app.ps1 -Serial 1882000501
    ./god_verify_led_manager_app.ps1 -Serial 1882000501 -TriggerScenario
#>

param(
    [string]$Serial = "",
    [string]$OutDir = (Join-Path $PSScriptRoot "results"),
    [switch]$TriggerScenario
)

$ErrorActionPreference = "Continue"

$LedPackage = "com.barco.clickshare.ledmanager"
$ConfigAuthority = "com.barco.clickshare.configurationmanager.provider"
$LedStateUri = "content://$ConfigAuthority/clickshare/BaseUnit.Led.State"
$PairingAction = "com.barco.clickshare.buttonmanager.PAIRING_BUTTON"
$TestSerialNumber = "VERIFYTEST01"

# Scenarios reachable via ACTION_PAIRING_BUTTON, from LedManagerBroadcastReceiver.kt's
# ButtonStatus -> LedType mapping. TriggerStatuses are sent in order (as separate broadcasts)
# for the same fake button serial; the LAST one is what actually produces ExpectedState.
# ExpectedPattern is the exact (Enable,Brightness,OnTime,OffTime,Mode) the LedType's pattern
# class (LedPatternFactory.kt) calls setRedLedState/setWhiteLedState with - all 7 (the 6
# button-scenario types plus Idle itself, exercised via "Finished.ButtonDetached" - the same
# broadcast that already resolves to LedType.Idle) confirmed empirically against a real
# device while writing this script.
$ButtonScenarios = @(
    @{ Name = "PairingButton"; TriggerStatuses = @("Pairing.Started")
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "500"; OffTime = "500"; Mode = "timer" }
       Remark = "wiki: Pairing in progress -> blinking white" }
    @{ Name = "PairingButtonFailed"; TriggerStatuses = @("Pairing.Error.PairingLockTaken")
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "500"; OffTime = "500"; Mode = "timer" }
       Remark = "wiki: Pairing error -> blinking red" }
    @{ Name = "PairingButtonSuccess"; TriggerStatuses = @("Pairing.Started", "Pairing.Successful", "Finished.Successful")
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "0"; OffTime = "0"; Mode = "none" }
       Remark = "wiki: Pairing done -> static white (ON)" }
    @{ Name = "UpdatingButton"; TriggerStatuses = @("FirmwareSync.Started")
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "250"; OffTime = "250"; Mode = "timer" }
       Remark = "wiki: Updating Button -> blinking white 250ms" }
    @{ Name = "UpdatingButtonFailed"; TriggerStatuses = @("FirmwareSync.Error.ConnectionLost")
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "250"; OffTime = "250"; Mode = "timer" }
       Remark = "wiki: Updating Button Failed -> blinking red 250ms" }
    @{ Name = "UpdatingButtonSuccess"; TriggerStatuses = @("IsoSync.Successful", "Finished.Successful")
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "0"; OffTime = "0"; Mode = "none" }
       Remark = "wiki: Updating Button Success -> static white (ON)" }
    @{ Name = "Idle"; TriggerStatuses = @("Pairing.Started", "Finished.ButtonDetached")
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "0"; OffTime = "0"; Mode = "none" }
       Remark = "wiki: Idle -> static white (ON); default resting scenario, always present in the waiting queue" }
)

# Reachable only via the AIDL ILedManager.startScenario() call from other system apps - no
# generic ADB `shell` path exists to invoke it directly, so these are driven through
# TestLedClient's Client1 toggle buttons instead (see Test-AidlScenario below).
# ExpectedPattern per LedPatternFactory.kt / patterns/*.kt - same shape as $ButtonScenarios,
# confirmed empirically for Error and BaseUnitInUse while adding this sweep.
# NOTE: ResetToDefaults is intentionally NOT included here - the wiki marks its LED
# indication as REMOVED/dead (the underlying event only lasted ~5s), so skip testing it
# even though LedPatternFactory.kt's mapping and TestLedClient's button for it still exist.
$AidlOnlyTypes = @(
    @{ Name = "Error"
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "500"; OffTime = "500"; Mode = "timer" }
       Remark = "wiki: High priority; number of error-sets tracked" }
    @{ Name = "UpdatingBaseUnit"
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "500"; OffTime = "500"; Mode = "timer" }
       Remark = "wiki: Updating Base Unit -> blinking white" }
    @{ Name = "UpdatingBaseUnitSuccess"
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "0"; OffTime = "0"; Mode = "none" }
       Remark = "wiki: turns off after 15s (see Oct 30 2025 update)" }
    @{ Name = "UpdatingBaseUnitFailed"
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "500"; OffTime = "500"; Mode = "timer" }
       Remark = "wiki: Updating Base Unit Failed -> blinking red, for 15s" }
    @{ Name = "SoftwareReboot"
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "500"; OffTime = "500"; Mode = "timer" }
       Remark = "wiki: Software reboot -> blinking white" }
    @{ Name = "BaseUnitStandbyEco"
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "7"; OffTime = "0"; Mode = "eco" }
       Remark = "wiki: Eco mode -> fading white 750ms/95% duty (BreathWhiteLedPattern's own onTime/offTime encoding)" }
    @{ Name = "BaseUnitStandbyDeepSleep"
       ExpectedPattern = @{ Enable = "false"; Brightness = "0"; OnTime = "0"; OffTime = "0"; Mode = "none" }
       Remark = "wiki: Deep sleep -> OFF" }
    @{ Name = "BaseUnitInUse"
       ExpectedPattern = @{ Enable = "true"; Brightness = "255"; OnTime = "0"; OffTime = "0"; Mode = "none" }
       Remark = "wiki: Baseunit in use -> static red" }
)

$TestLedClientCli = Join-Path $PSScriptRoot "test_led_client_cli.py"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $OutDir "god_led_manager_verify_$timestamp.log"

function Write-Log {
    param([string]$Line)
    Write-Host $Line
    Add-Content -Path $logFile -Value $Line
}

function Get-AdbArgs {
    if ($Serial) { return @("-s", $Serial) }
    return @()
}

function Invoke-Adb {
    param([string[]]$AdbCmdArgs)
    $adbArgs = (Get-AdbArgs) + $AdbCmdArgs
    return (& adb @adbArgs 2>&1)
}

function Get-ApkVersion {
    param([string]$Package)
    $dumpOut = (Invoke-Adb -AdbCmdArgs @("shell", "dumpsys", "package", $Package)) -join "`n"
    $versionName = $null
    $versionCode = $null
    if ($dumpOut -match 'versionName=(\S+)') { $versionName = $Matches[1] }
    if ($dumpOut -match 'versionCode=(\d+)') { $versionCode = $Matches[1] }
    return [pscustomobject]@{ VersionName = $versionName; VersionCode = $versionCode }
}

function Get-LedState {
    $out = (Invoke-Adb -AdbCmdArgs @("shell", "content", "query", "--uri", $LedStateUri)) -join "`n"
    if ($out -match 'value=([^\s,]+)') { return $Matches[1].Trim() }
    return $null
}

function Send-PairingBroadcast {
    param([string]$SerialNumber, [string]$Status)
    $data = "{`"buttonList`":[{`"serialNumber`":`"$SerialNumber`",`"status`":`"$Status`",`"progress`":0}]}"
    return (Invoke-Adb -AdbCmdArgs @("shell", "am", "broadcast", "-a", $PairingAction, `
        "--es", "session", "verify-test", "--es", "data", $data)) -join "`n"
}

function Wait-ForLedState {
    param([string]$Expected, [int]$TimeoutSeconds = 5)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $last = $null
    while ((Get-Date) -lt $deadline) {
        $last = Get-LedState
        if ($last -eq $Expected) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Get-LastSetLedStateLine {
    # Reads the current logcat buffer and returns the last "LedManager: setLedState ..." line,
    # parsed into its enable/brightness/onTime/offTime/mode fields - the pattern class's own
    # start() call is always logged last, after the two "turn everything off" calls every
    # pattern makes via BaseLedPattern.start().
    $out = (Invoke-Adb -AdbCmdArgs @("logcat", "-d")) -join "`n"
    $matches = [regex]::Matches($out, 'LedManager: setLedState enable=(\S+) brightness=(\d+) onTime=(\d+) offTime=(\d+) mode=(\S+)')
    if ($matches.Count -eq 0) { return $null }
    $m = $matches[$matches.Count - 1]
    return [pscustomobject]@{
        Enable = $m.Groups[1].Value
        Brightness = $m.Groups[2].Value
        OnTime = $m.Groups[3].Value
        OffTime = $m.Groups[4].Value
        Mode = $m.Groups[5].Value
    }
}

function Test-PatternMatch {
    param($Actual, $Expected)
    if ($null -eq $Actual) { return $false }
    return ($Actual.Enable -eq $Expected.Enable) -and ($Actual.Brightness -eq $Expected.Brightness) -and `
        ($Actual.OnTime -eq $Expected.OnTime) -and ($Actual.OffTime -eq $Expected.OffTime) -and ($Actual.Mode -eq $Expected.Mode)
}

function Format-Pattern {
    param($Pattern)
    if ($null -eq $Pattern) { return "(none)" }
    return "enable=$($Pattern.Enable) brightness=$($Pattern.Brightness) onTime=$($Pattern.OnTime) offTime=$($Pattern.OffTime) mode=$($Pattern.Mode)"
}

function Invoke-TestLedClient {
    # Runs test_led_client_cli.py and returns $true if it printed "OK" and exited 0.
    param([string[]]$CliArgs)
    $pyArgs = @($TestLedClientCli, "--serial", $Serial) + $CliArgs
    $out = (& python @pyArgs 2>&1) -join "`n"
    return @{ Ok = ($LASTEXITCODE -eq 0); Output = $out }
}

Write-Log "===================================================================="
Write-Log "GOD Led Manager apk verification ($LedPackage)"
Write-Log "Run: $timestamp"
if ($Serial) { Write-Log "Device: $Serial" }
Write-Log "===================================================================="

# 1) Installed
Write-Log ""
Write-Log "---- [1] Installed ----"
$pkgOut = Invoke-Adb -AdbCmdArgs @("shell", "pm", "list", "packages", $LedPackage)
$installed = ($pkgOut -join "`n") -match [regex]::Escape("package:$LedPackage")
Write-Log "$(if ($installed) {'[OK]'} else {'[FAIL]'}) installed: $installed"
if (-not $installed) {
    Write-Log ($pkgOut -join "`n")
}

$apkVersion = $null
if ($installed) {
    $apkVersion = Get-ApkVersion -Package $LedPackage
    Write-Log ("On-device apk version: versionName={0} versionCode={1}" -f `
        $(if ($apkVersion.VersionName) { $apkVersion.VersionName } else { "?" }), `
        $(if ($apkVersion.VersionCode) { $apkVersion.VersionCode } else { "?" }))
}

# 2) Running
Write-Log ""
Write-Log "---- [2] Running (persistent app - should always be running once booted) ----"
$running = $false
$pidOut = ((Invoke-Adb -AdbCmdArgs @("shell", "pidof", $LedPackage)) -join "`n").Trim()
if ($pidOut -match '^\d+') {
    $running = $true
} else {
    $psOut = (Invoke-Adb -AdbCmdArgs @("shell", "ps", "-A")) -join "`n"
    $running = $psOut -match [regex]::Escape($LedPackage)
}
Write-Log "$(if ($running) {'[OK]'} else {'[FAIL]'}) running: $running"

# LedManager reports its state into configuration-manager-apk's ContentProvider, which enforces
# its own permission on writers but query reads have been observed to need adb root on this
# device as well - run it up front like the featureflags/configuration-manager scripts do.
Write-Log ""
Write-Log "---- adb root (required for content query against configuration-manager-apk) ----"
$rootOut = ((Invoke-Adb -AdbCmdArgs @("root")) -join "`n")
Write-Log $rootOut
Start-Sleep -Milliseconds 1500
Invoke-Adb -AdbCmdArgs @("wait-for-device") | Out-Null

# 3) Baseline LED state
Write-Log ""
Write-Log "---- [3] BaseUnit.Led.State (reported by LedManager into configuration-manager-apk) ----"
$baselineState = Get-LedState
$gotBaseline = $null -ne $baselineState
Write-Log "$(if ($gotBaseline) {'[OK]'} else {'[FAIL]'}) BaseUnit.Led.State = $baselineState"

# 4) Optional full LED behavior sweep
$scenarioPass = 0
$scenarioFail = 0
$scenarioResults = @()
if ($TriggerScenario) {
    Write-Log ""
    Write-Log "---- [4] Full LED behavior sweep (button-related scenarios reachable via ACTION_PAIRING_BUTTON) ----"

    foreach ($scenario in $ButtonScenarios) {
        Write-Log ""
        Write-Log "-- Scenario: $($scenario.Name) ($($scenario.Remark)) --"

        Invoke-Adb -AdbCmdArgs @("logcat", "-c") | Out-Null
        foreach ($status in $scenario.TriggerStatuses) {
            Write-Log "Broadcasting $status for serial=$TestSerialNumber ..."
            $bcOut = Send-PairingBroadcast -SerialNumber $TestSerialNumber -Status $status
            if ($bcOut -notmatch "Broadcast completed") { Write-Log $bcOut }
            Start-Sleep -Milliseconds 800
        }

        $stateOk = Wait-ForLedState -Expected $scenario.Name -TimeoutSeconds 5
        $actualState = Get-LedState
        $actualPattern = Get-LastSetLedStateLine
        $patternOk = Test-PatternMatch -Actual $actualPattern -Expected $scenario.ExpectedPattern

        Write-Log "$(if ($stateOk) {'[OK]'} else {'[FAIL]'}) BaseUnit.Led.State = $actualState (expected $($scenario.Name))"
        Write-Log "$(if ($patternOk) {'[OK]'} else {'[FAIL]'}) setLedState = $(Format-Pattern $actualPattern) (expected $(Format-Pattern $scenario.ExpectedPattern))"

        Write-Log "Broadcasting Finished.ButtonDetached for serial=$TestSerialNumber (cleanup) ..."
        Send-PairingBroadcast -SerialNumber $TestSerialNumber -Status "Finished.ButtonDetached" | Out-Null
        $reverted = Wait-ForLedState -Expected "Idle" -TimeoutSeconds 5
        $stateAfterCleanup = Get-LedState
        Write-Log "$(if ($reverted) {'[OK]'} else {'[FAIL]'}) reverted to Idle: $stateAfterCleanup"

        $ok = $stateOk -and $patternOk -and $reverted
        $scenarioResults += [pscustomobject]@{ Name = $scenario.Name; Ok = $ok; Remark = $scenario.Remark }
        if ($ok) { $scenarioPass++ } else {
            $scenarioFail++
            Write-Log "  *** WARNING: scenario $($scenario.Name) did not fully pass. Manual check recommended. ***"
        }
    }

    Write-Log ""
    Write-Log "---- [5] AIDL-only LED behavior sweep (via TestLedClient) ----"
    $tlcInstalled = (Invoke-TestLedClient -CliArgs @("is-installed")).Ok
    if (-not $tlcInstalled) {
        Write-Log "[SKIP] TestLedClient not installed - build with '.\gradlew :test-led-client:assembleDebug' in"
        Write-Log "       C:\Project\Wave4\led-manager-apk, then 'adb install -r -g <apk>'. Skipping AIDL-only sweep"
        Write-Log "       (not counted as a failure)."
    } else {
        Invoke-TestLedClient -CliArgs @("launch") | Out-Null
        Start-Sleep -Milliseconds 500

        foreach ($aidlType in $AidlOnlyTypes) {
            Write-Log ""
            Write-Log "-- Scenario: $($aidlType.Name) ($($aidlType.Remark)) --"

            Invoke-Adb -AdbCmdArgs @("logcat", "-c") | Out-Null
            $startResult = Invoke-TestLedClient -CliArgs @("start", "--client", "1", "--led-type", $aidlType.Name)
            if (-not $startResult.Ok) { Write-Log $startResult.Output }

            $stateOk = Wait-ForLedState -Expected $aidlType.Name -TimeoutSeconds 5
            $actualState = Get-LedState
            $actualPattern = Get-LastSetLedStateLine
            $patternOk = Test-PatternMatch -Actual $actualPattern -Expected $aidlType.ExpectedPattern

            Write-Log "$(if ($startResult.Ok) {'[OK]'} else {'[FAIL]'}) TestLedClient toggle start_scenario(1, $($aidlType.Name))"
            Write-Log "$(if ($stateOk) {'[OK]'} else {'[FAIL]'}) BaseUnit.Led.State = $actualState (expected $($aidlType.Name))"
            Write-Log "$(if ($patternOk) {'[OK]'} else {'[FAIL]'}) setLedState = $(Format-Pattern $actualPattern) (expected $(Format-Pattern $aidlType.ExpectedPattern))"

            $stopResult = Invoke-TestLedClient -CliArgs @("stop", "--client", "1", "--led-type", $aidlType.Name)
            if (-not $stopResult.Ok) { Write-Log $stopResult.Output }
            $reverted = Wait-ForLedState -Expected "Idle" -TimeoutSeconds 5
            $stateAfterCleanup = Get-LedState
            Write-Log "$(if ($reverted) {'[OK]'} else {'[FAIL]'}) reverted to Idle: $stateAfterCleanup"

            $ok = $startResult.Ok -and $stateOk -and $patternOk -and $stopResult.Ok -and $reverted
            $scenarioResults += [pscustomobject]@{ Name = $aidlType.Name; Ok = $ok; Remark = $aidlType.Remark }
            if ($ok) { $scenarioPass++ } else {
                $scenarioFail++
                Write-Log "  *** WARNING: scenario $($aidlType.Name) did not fully pass. Manual check recommended. ***"
            }
        }
    }
} else {
    Write-Log ""
    Write-Log "---- [4] Full LED behavior sweep: skipped (use -TriggerScenario to enable) ----"
}

Write-Log ""
Write-Log "===================================================================="
Write-Log "Summary"
Write-Log "===================================================================="
Write-Log "Apk version         : $(if ($apkVersion -and $apkVersion.VersionName) { "$($apkVersion.VersionName) (versionCode $($apkVersion.VersionCode))" } else { "unknown (package not installed?)" })"
Write-Log "Installed           : $installed"
Write-Log "Running             : $running"
Write-Log "Baseline Led.State  : $gotBaseline ($baselineState)"
if ($TriggerScenario) {
    $totalScenarios = $ButtonScenarios.Count + $(if ($tlcInstalled) { $AidlOnlyTypes.Count } else { 0 })
    Write-Log "LED behavior sweep  : $scenarioPass/$totalScenarios passed$(if ($scenarioFail -gt 0) { " ($scenarioFail FAILED)" })"
    foreach ($r in $scenarioResults) {
        Write-Log ("  [{0}] {1,-25} ({2})" -f $(if ($r.Ok) {"OK"} else {"FAIL"}), $r.Name, $r.Remark)
    }
    if (-not $tlcInstalled) {
        Write-Log "  ($($AidlOnlyTypes.Count) AIDL-only LedTypes skipped - TestLedClient not installed)"
    }
} else {
    Write-Log "LED behavior sweep  : skipped"
}
Write-Log ""
Write-Log "Full log saved to: $logFile"

if ($installed -and $running -and $gotBaseline -and (-not $TriggerScenario -or $scenarioFail -eq 0)) {
    exit 0
} else {
    exit 1
}
