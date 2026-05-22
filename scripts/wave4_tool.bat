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

powershell -NoProfile -Command ^
  "$adbS = '%ADB_TARGET%'; if ($adbS) { $adbS = \"-s $adbS\" }; " ^
  "$apks = @(" ^
  "  @('mdep-settings-apk',           'com.android.settings')," ^
  "  @('network-manager-apk',         'com.barco.clickshare.networkmanager')," ^
  "  @('compositor-apk',              'com.barco.clickshare.compositor')," ^
  "  @('display-manager-apk',         'com.barco.clickshare.displaymanager')," ^
  "  @('standby-manager-apk',         'com.barco.clickshare.standbymanager')," ^
  "  @('switcher-apk',                'com.barco.clickshare.switcher')," ^
  "  @('configuration-manager-apk',   'com.barco.clickshare.configurationmanager')," ^
  "  @('button-manager-apk',          'com.barco.clickshare.buttonmanager')," ^
  "  @('rd-camera-apk',               'com.barco.clickshare.rdcamera')," ^
  "  @('rd-speakerphone-apk',         'com.barco.clickshare.rdspeakerphone')," ^
  "  @('ui-composer-apk',             'com.barco.clickshare.uicomposer')," ^
  "  @('rest-api-apk',                'com.barco.clickshare.restapi')," ^
  "  @('production-api-apk',          'com.barco.clickshare.productionapi')," ^
  "  @('iot-agent-apk',               'com.barco.clickshare.iotagent')," ^
  "  @('telemetry-service-apk',       'com.barco.clickshare.telemetryservice')," ^
  "  @('firmware-updater-apk',        'com.barco.clickshare.firmwareupdater')," ^
  "  @('led-manager-apk',             'com.barco.clickshare.ledmanager')," ^
  "  @('ingest-service-apk',          'com.barco.clickshare.ingestservice')," ^
  "  @('feature-flags-apk',           'com.barco.clickshare.featureflags.app')," ^
  "  @('up-source-provider-apk',      'com.barco.clickshare.upsourceprovider')" ^
  "); " ^
  "Write-Host ('  {0,-35} {1,-10} {2}' -f 'APK Name','Version','Package'); " ^
  "Write-Host ('  ' + '-'*35 + ' ' + '-'*10 + ' ' + '-'*40); " ^
  "foreach ($a in $apks) { " ^
  "  $name = $a[0]; $pkg = $a[1]; " ^
  "  $raw = (Invoke-Expression \"adb $adbS shell 'dumpsys package $pkg ^| grep versionName' 2>`$null\") -join ''; " ^
  "  $ver = if ($raw -match 'versionName=(.+)') { $Matches[1].Trim() } else { '[not installed]' }; " ^
  "  Write-Host ('  {0,-35} {1,-10} {2}' -f $name, $ver, $pkg) " ^
  "}"

echo.
pause
goto MAIN_MENU

:EXIT
echo Bye!
endlocal
exit /b 0
