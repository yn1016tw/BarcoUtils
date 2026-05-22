@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: Default ADB target (serial or IP:port)
set "ADB_TARGET="

:CONNECT_MENU
cls
echo ============================================================
echo          Duvel Device Tool
echo ============================================================
echo.
echo  Current target: %ADB_TARGET%
echo.
echo  [1] Connect by IP address
echo  [2] Connect by USB serial
echo  [3] Use already-connected device (no target)
echo  [0] Exit
echo.
echo ============================================================
set /p "CHOICE=Select option: "

if "%CHOICE%"=="1" goto CONNECT_IP
if "%CHOICE%"=="2" goto CONNECT_SERIAL
if "%CHOICE%"=="3" goto MAIN_MENU
if "%CHOICE%"=="0" goto EXIT
echo Invalid option.
timeout /t 2 >nul
goto CONNECT_MENU

:CONNECT_IP
echo.
set /p "DEV_IP=Enter device IP address: "
set "ADB_TARGET=%DEV_IP%:5555"
echo Connecting to %ADB_TARGET%...
adb connect %ADB_TARGET%
echo.
pause
goto MAIN_MENU

:CONNECT_SERIAL
echo.
set /p "ADB_TARGET=Enter USB serial number: "
echo Using serial: %ADB_TARGET%
echo.
pause
goto MAIN_MENU

:: ---- Helper macro to build -s flag ----
:MAIN_MENU
cls

:: Build -s argument string
if "%ADB_TARGET%"=="" (
    set "ADB_S="
) else (
    set "ADB_S=-s %ADB_TARGET%"
)

:: Read current ethernet status
set "ETH_STATUS=unknown"
for /f "tokens=*" %%L in ('adb %ADB_S% shell "ip link show eth0 2^>nul" 2^>nul') do (
    echo %%L | findstr /i "state UP" >nul && set "ETH_STATUS=UP"
    echo %%L | findstr /i "state DOWN" >nul && set "ETH_STATUS=DOWN"
)

echo ============================================================
echo          Duvel Device Tool  -  Ethernet Control
echo ============================================================
echo.
echo  Target  : %ADB_TARGET%
echo  eth0    : %ETH_STATUS%
echo.
echo  [1] Ethernet UP   (ip link set eth0 up)
echo  [2] Ethernet DOWN (ip link set eth0 down)
echo  [3] Show eth0 status
echo  [4] Show all network interfaces
echo  [5] Show IP addresses
echo  [6] List Barco APK versions
echo  [7] Reconnect / change target
echo  [0] Exit
echo.
echo ============================================================
set /p "CHOICE=Select option: "

if "%CHOICE%"=="1" goto ETH_UP
if "%CHOICE%"=="2" goto ETH_DOWN
if "%CHOICE%"=="3" goto ETH_STATUS
if "%CHOICE%"=="4" goto SHOW_IFACES
if "%CHOICE%"=="5" goto SHOW_IPS
if "%CHOICE%"=="6" goto LIST_BARCO_APKS
if "%CHOICE%"=="7" goto CONNECT_MENU
if "%CHOICE%"=="0" goto EXIT
echo Invalid option.
timeout /t 2 >nul
goto MAIN_MENU

:ETH_UP
echo.
echo [1] Bringing eth0 UP...
echo ------------------------------------------------------------
echo   Requesting root...
adb %ADB_S% root >nul 2>&1
timeout /t 2 >nul
adb %ADB_S% shell ip link set eth0 up
echo.
echo Done. Waiting 2 seconds for link...
timeout /t 2 >nul
adb %ADB_S% shell ip link show eth0
echo.
pause
goto MAIN_MENU

:ETH_DOWN
echo.
echo [2] Bringing eth0 DOWN...
echo ------------------------------------------------------------
echo   Requesting root...
adb %ADB_S% root >nul 2>&1
timeout /t 2 >nul
adb %ADB_S% shell ip link set eth0 down
echo.
adb %ADB_S% shell ip link show eth0
echo.
pause
goto MAIN_MENU

:ETH_STATUS
echo.
echo [3] eth0 status:
echo ------------------------------------------------------------
adb %ADB_S% shell ip link show eth0
echo.
adb %ADB_S% shell ip addr show eth0
echo.
pause
goto MAIN_MENU

:SHOW_IFACES
echo.
echo [4] All network interfaces:
echo ------------------------------------------------------------
adb %ADB_S% shell ip link show
echo.
pause
goto MAIN_MENU

:SHOW_IPS
echo.
echo [5] IP addresses:
echo ------------------------------------------------------------
adb %ADB_S% shell ip addr show
echo.
pause
goto MAIN_MENU

:LIST_BARCO_APKS
echo.
echo [6] Barco APK versions:
echo ------------------------------------------------------------
echo.

:: Write PowerShell script to temp file then execute
set "PS1=%TEMP%\barco_apk_list.ps1"
(
  echo $adbS = "%ADB_TARGET%"
  echo if ^($adbS^) { $adbS = "-s $adbS" }
  echo $apks = @^(
  echo   ,@^('mdep-settings-apk',           'com.android.settings'^)
  echo   ,@^('network-manager-apk',         'com.barco.clickshare.networkmanager'^)
  echo   ,@^('compositor-apk',              'com.barco.clickshare.compositor'^)
  echo   ,@^('display-manager-apk',         'com.barco.clickshare.displaymanager'^)
  echo   ,@^('standby-manager-apk',         'com.barco.clickshare.standbymanager'^)
  echo   ,@^('switcher-apk',                'com.barco.clickshare.switcher'^)
  echo   ,@^('configuration-manager-apk',   'com.barco.clickshare.configurationmanager'^)
  echo   ,@^('button-manager-apk',          'com.barco.clickshare.buttonmanager'^)
  echo   ,@^('rd-camera-apk',               'com.barco.clickshare.rdcamera'^)
  echo   ,@^('rd-speakerphone-apk',         'com.barco.clickshare.rdspeakerphone'^)
  echo   ,@^('ui-composer-apk',             'com.barco.clickshare.uicomposer'^)
  echo   ,@^('rest-api-apk',                'com.barco.clickshare.restapi'^)
  echo   ,@^('production-api-apk',          'com.barco.clickshare.productionapi'^)
  echo   ,@^('iot-agent-apk',               'com.barco.clickshare.iotagent'^)
  echo   ,@^('telemetry-service-apk',       'com.barco.clickshare.telemetryservice'^)
  echo   ,@^('firmware-updater-apk',        'com.barco.clickshare.firmwareupdater'^)
  echo   ,@^('led-manager-apk',             'com.barco.clickshare.ledmanager'^)
  echo   ,@^('ingest-service-apk',          'com.barco.clickshare.ingestservice'^)
  echo   ,@^('feature-flags-apk',           'com.barco.clickshare.featureflags.app'^)
  echo   ,@^('up-source-provider-apk',      'com.barco.clickshare.upsourceprovider'^)
  echo ^)
  echo Write-Host ^('  {0,-35} {1,-12} {2}' -f 'APK Name','Version','Package'^)
  echo Write-Host ^('  ' + '-'*35 + ' ' + '-'*12 + ' ' + '-'*40^)
  echo foreach ^($a in $apks^) {
  echo   $name = $a[0]; $pkg = $a[1]
  echo   $raw = ^(adb $adbS shell "dumpsys package $pkg ^| grep versionName" 2^>$null^) -join ''
  echo   $ver = if ^($raw -match 'versionName=^(.+^)'^) { $Matches[1].Trim^(^) } else { '[not installed]' }
  echo   Write-Host ^('  {0,-35} {1,-12} {2}' -f $name, $ver, $pkg^)
  echo }
) > "%PS1%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
del "%PS1%" >nul 2>&1

echo.
pause
goto MAIN_MENU

:EXIT
echo Bye!
endlocal
exit /b 0
