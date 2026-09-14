<#
.SYNOPSIS
    Verify com.barco.clickshare.featureflags.app (Feature Flags apk) via ADB.

.DESCRIPTION
    Three checks, in order:
    1. Installed  - `adb shell pm list packages` contains the package.
    2. Running    - `adb shell pidof` (fallback: `adb shell ps -A | grep`) finds a live process.
    3. All values - `adb shell content call --uri content://<pkg> --method getAllFlags`
       dumps every effective flag (config file value with any ADB override applied on top),
       per FeatureFlagContentProvider.kt / FeatureFlagManager.kt in the feature-flags-apk source.
       Also calls `getAllOverrides` so active overrides are called out separately, since
       getAllFlags alone does not indicate which values are overridden vs. from the config file.
       Finally, for every flag name discovered above, calls the single-flag `getFlag` method
       individually (Bundle[{flag_value=<bool>}]) and compares it against the effective value
       from getAllFlags/getAllOverrides, so a bug isolated to the single-flag read path (as
       opposed to the bulk path) doesn't hide behind a passing getAllFlags call.

    Also reads the on-device apk's versionName/versionCode (`adb shell dumpsys package <pkg>`)
    and stamps it into both the console header and the log file, so a log from an old run can
    be told apart from a run against a newer apk build at a glance.

    Every run is logged (console + a timestamped file under -OutDir), so results can be diffed
    across devices or across apk versions.

.NOTES
    Verified-against APK version: feature-flags-apk v1.7.1 (git tag 1.7.1, commit 0df1e45d,
    2026-09-03), from C:\Project\Wave4\feature-flags-apk. This script hardcodes the authority
    ("com.barco.clickshare.featureflags.app"), method names (getFlag / getAllFlags /
    getAllOverrides), and Bundle key ("flag_value") defined in that version's
    FeatureFlagContentProvider.kt / FeatureFlagConstants.kt / BundleHelper.kt.
    When feature-flags-apk is bumped, diff those three files against this version before
    assuming the script still works, and bump the "Verified-against" line above (and the
    matching note in CLAUDE.md) once confirmed.

.PARAMETER Serial
    Target device serial (use when multiple devices are connected). Maps to `adb -s <serial>`.

.PARAMETER OutDir
    Output folder for the log file. Defaults to a `results` folder next to this script.

.EXAMPLE
    ./verify_featureflags_app.ps1
    ./verify_featureflags_app.ps1 -Serial 1882000501
    ./verify_featureflags_app.ps1 -Serial 1882000501 -OutDir C:\temp\featureflags-verify
#>

param(
    [string]$Serial = "",
    [string]$OutDir = (Join-Path $PSScriptRoot "results")
)

$ErrorActionPreference = "Continue"

$Package = "com.barco.clickshare.featureflags.app"
$Uri = "content://$Package"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $OutDir "featureflags_verify_$timestamp.log"

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

function ConvertFrom-Bundle {
    # Parses adb's "Bundle[{k=v, k2=v2}]" text dump into a list of "k=v" pairs.
    param([string]$Output)
    if ($Output -notmatch '\{(.*)\}') { return @() }
    $content = $Matches[1]
    if ([string]::IsNullOrWhiteSpace($content)) { return @() }
    return ($content -split ', ' | Where-Object { $_ -ne "" })
}

function ConvertTo-PairTable {
    # "k=v" strings -> hashtable, for lookup by flag name.
    param([string[]]$Pairs)
    $table = @{}
    foreach ($pair in $Pairs) {
        $idx = $pair.IndexOf('=')
        if ($idx -lt 0) { continue }
        $table[$pair.Substring(0, $idx)] = $pair.Substring($idx + 1)
    }
    return $table
}

function Get-ApkVersion {
    # Reads the on-device apk's versionName/versionCode via `dumpsys package`, so the log
    # records exactly which apk build was verified (independent of this script's own
    # "Verified-against" source version noted above).
    param([string]$Package)
    $dumpOut = (Invoke-Adb -AdbCmdArgs @("shell", "dumpsys", "package", $Package)) -join "`n"
    $versionName = $null
    $versionCode = $null
    if ($dumpOut -match 'versionName=(\S+)') { $versionName = $Matches[1] }
    if ($dumpOut -match 'versionCode=(\d+)') { $versionCode = $Matches[1] }
    return [pscustomobject]@{ VersionName = $versionName; VersionCode = $versionCode }
}

Write-Log "===================================================================="
Write-Log "Feature Flags apk verification ($Package)"
Write-Log "Run: $timestamp"
if ($Serial) { Write-Log "Device: $Serial" }
Write-Log "===================================================================="

# 1) Installed
Write-Log ""
Write-Log "---- [1] Installed ----"
$pkgOut = Invoke-Adb -AdbCmdArgs @("shell", "pm", "list", "packages", $Package)
$installed = ($pkgOut -join "`n") -match [regex]::Escape("package:$Package")
Write-Log "$(if ($installed) {'[OK]'} else {'[FAIL]'}) installed: $installed"
if (-not $installed) {
    Write-Log ($pkgOut -join "`n")
}

$apkVersion = $null
if ($installed) {
    $apkVersion = Get-ApkVersion -Package $Package
    Write-Log ("On-device apk version: versionName={0} versionCode={1}" -f `
        $(if ($apkVersion.VersionName) { $apkVersion.VersionName } else { "?" }), `
        $(if ($apkVersion.VersionCode) { $apkVersion.VersionCode } else { "?" }))
}

# 2) Running
Write-Log ""
Write-Log "---- [2] Running ----"
$running = $false
$pidOut = ((Invoke-Adb -AdbCmdArgs @("shell", "pidof", $Package)) -join "`n").Trim()
if ($pidOut -match '^\d+') {
    $running = $true
} else {
    $psOut = (Invoke-Adb -AdbCmdArgs @("shell", "ps", "-A")) -join "`n"
    $running = $psOut -match [regex]::Escape($Package)
}
Write-Log "$(if ($running) {'[OK]'} else {'[FAIL]'}) running: $running"
if (-not $running) {
    Write-Log "(process not found - the provider process is started on-demand by the first ADB call below)"
}

# The provider enforces READ_PERMISSION/WRITE_PERMISSION at the OS level for every caller,
# including plain `content query/call` reads - not just the write path guarded in-app by
# enforceAdbCaller(). `adb root` (as documented in feature-flags-apk/docs/AdbCommands.md) is
# required before any `content call`, or the OS itself throws SecurityException before the
# call ever reaches FeatureFlagContentProvider.
Write-Log ""
Write-Log "---- adb root (required for content call - OS-level permission check) ----"
$rootOut = ((Invoke-Adb -AdbCmdArgs @("root")) -join "`n")
Write-Log $rootOut
Start-Sleep -Milliseconds 1500
Invoke-Adb -AdbCmdArgs @("wait-for-device") | Out-Null

# 3) All values
Write-Log ""
Write-Log "---- [3] getAllFlags (effective values: config file + overrides) ----"
$flagsOut = Invoke-Adb -AdbCmdArgs @("shell", "content", "call", "--uri", $Uri, "--method", "getAllFlags")
$flagsJoined = ($flagsOut -join "`n")
Write-Log $flagsJoined
$flagPairs = ConvertFrom-Bundle -Output $flagsJoined
$gotFlags = ($flagPairs.Count -gt 0) -and ($flagsJoined -notmatch "Error|Exception")

Write-Log ""
Write-Log "---- [3b] getAllOverrides (ADB-set overrides only) ----"
$overridesOut = Invoke-Adb -AdbCmdArgs @("shell", "content", "call", "--uri", $Uri, "--method", "getAllOverrides")
$overridesJoined = ($overridesOut -join "`n")
Write-Log $overridesJoined
$overridePairs = ConvertFrom-Bundle -Output $overridesJoined

# 3c) getFlag, tested individually for every flag name discovered above
Write-Log ""
Write-Log "---- [3c] getFlag (single-flag read), tested individually per flag ----"
$flagTable = ConvertTo-PairTable -Pairs $flagPairs
$overrideTable = ConvertTo-PairTable -Pairs $overridePairs
$flagNames = @($flagTable.Keys + $overrideTable.Keys) | Select-Object -Unique | Sort-Object

$getFlagPass = 0
$getFlagFail = 0
foreach ($name in $flagNames) {
    $expected = if ($overrideTable.ContainsKey($name)) { $overrideTable[$name] } else { $flagTable[$name] }

    $out = Invoke-Adb -AdbCmdArgs @("shell", "content", "call", "--uri", $Uri, "--method", "getFlag", "--arg", $name)
    $joined = ($out -join "`n")
    $pairs = ConvertFrom-Bundle -Output $joined
    $table = ConvertTo-PairTable -Pairs $pairs
    $actual = $table["flag_value"]

    $ok = ($null -ne $actual) -and ($actual -eq $expected)
    if ($ok) { $getFlagPass++ } else { $getFlagFail++ }

    Write-Log ("[{0}] getFlag({1}) => {2} (expected {3})" -f $(if ($ok) {"OK"} else {"FAIL"}), $name, $actual, $expected)
    if (-not $ok) {
        Write-Log "  raw output: $joined"
    }
}
if ($flagNames.Count -eq 0) {
    Write-Log "(no flag names discovered from getAllFlags/getAllOverrides - nothing to test individually)"
}

Write-Log ""
Write-Log "===================================================================="
Write-Log "Summary"
Write-Log "===================================================================="
Write-Log "Apk version      : $(if ($apkVersion -and $apkVersion.VersionName) { "$($apkVersion.VersionName) (versionCode $($apkVersion.VersionCode))" } else { "unknown (package not installed?)" })"
Write-Log "Installed        : $installed"
Write-Log "Running          : $running"
Write-Log "getAllFlags      : $gotFlags ($($flagPairs.Count) flag(s), $($overridePairs.Count) override(s))"
Write-Log "getFlag (per-key): $getFlagPass/$($flagNames.Count) passed$(if ($getFlagFail -gt 0) { " ($getFlagFail FAILED)" })"
Write-Log ""
Write-Log "Full log saved to: $logFile"

if ($installed -and $gotFlags -and $getFlagFail -eq 0) {
    exit 0
} else {
    exit 1
}
