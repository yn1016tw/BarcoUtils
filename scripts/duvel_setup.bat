@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: Default settings
set "DEVICE_IP=10.102.90.83"
set "PROD_PORT=8085"
set "REST_PORT=4003"
set "ACTIVATE_URL=http://korgrt13.barco.com"
set "SN=1882000501"

call :GET_IP

:MAIN_MENU
cls
echo ============================================================
echo         Wave4 Duvel Device Setup Tool
echo ============================================================
echo.
echo   Device IP : %DEVICE_IP%
echo   SN        : %SN%
echo   SSID      : ClickShare-%SN%
echo.
echo   [1] Enable Manufacturing Mode (activate)
echo   [2] Set Serial Number
echo   [3] Reboot Base Unit
echo   [4] Activate Development Certificate
echo   [5] Create Development Certificate (ClickShare)
echo   [6] Set SSID
echo   [7] Setup (MDEP wizard + Teams sign-in)
echo   [8] Run All Steps (1-6 in sequence)
echo   [9] Run All Steps + Auto Setup (1-6 then wizard)
echo   [A] Refresh Device IP Address (adb)
echo   [B] Change Device IP
echo   [C] Change SN
echo   [0] Exit
echo.
echo ============================================================
set /p "CHOICE=Select option: "

if "%CHOICE%"=="1" goto ENABLE_MFG
if "%CHOICE%"=="2" goto SET_SERIAL
if "%CHOICE%"=="3" goto REBOOT
if "%CHOICE%"=="4" goto ACTIVATE_CERT
if "%CHOICE%"=="5" goto CREATE_CERT
if "%CHOICE%"=="6" goto SET_SSID
if "%CHOICE%"=="7" goto SETUP
if "%CHOICE%"=="8" goto RUN_ALL
if "%CHOICE%"=="9" goto RUN_ALL_SETUP
if /i "%CHOICE%"=="A" goto FIND_IP
if /i "%CHOICE%"=="B" goto CHANGE_IP
if /i "%CHOICE%"=="C" goto CHANGE_SN
if "%CHOICE%"=="0" goto EXIT
echo Invalid option.
timeout /t 2 >nul
goto MAIN_MENU

:: ---- 1. Enable Manufacturing Mode ----
:ENABLE_MFG
echo.
echo [1] Enabling manufacturing mode on %DEVICE_IP%...
echo ------------------------------------------------------------
curl -X PUT -H "Content-Type: application/x-www-form-urlencoded" -d "url=%ACTIVATE_URL%" %DEVICE_IP%:%PROD_PORT%/activate
echo.
echo.
pause
goto MAIN_MENU

:: ---- 2. Set Serial Number ----
:SET_SERIAL
echo.
echo [2] Setting serial number to %SN% on %DEVICE_IP%...
echo ------------------------------------------------------------
curl -X PUT -H "Content-Type: text/plain" -d "%SN%" %DEVICE_IP%:%PROD_PORT%/serial-number
echo.
echo.
pause
goto MAIN_MENU

:: ---- 3. Reboot Base Unit ----
:REBOOT
echo.
echo [3] Rebooting base unit...
echo ------------------------------------------------------------
adb reboot
echo   Waiting for device to come back online...
:WAIT_REBOOT_MENU
timeout /t 5 >nul
curl -s -k -o nul https://%DEVICE_IP%:%REST_PORT%/v3/status >nul 2>&1
if errorlevel 1 (
    echo   Device not ready, retrying...
    goto WAIT_REBOOT_MENU
)
echo   Device is back online!
echo.
pause
goto MAIN_MENU

:: ---- 4. Activate Development Certificate ----
:ACTIVATE_CERT
echo.
echo [4] Activating development certificate on %DEVICE_IP%...
echo ------------------------------------------------------------
curl -X PUT -H "Content-Type: application/x-www-form-urlencoded" -d "url=%ACTIVATE_URL%:80" %DEVICE_IP%:%PROD_PORT%/activate
echo.
echo.
pause
goto MAIN_MENU

:: ---- 5. Create Development Certificate ----
:CREATE_CERT
echo.
echo [5] Creating development certificate (ClickShare) on %DEVICE_IP%...
echo ------------------------------------------------------------
curl -X PUT %DEVICE_IP%:%PROD_PORT%/certificate/clickshare
echo.
echo.
pause
goto MAIN_MENU

:: ---- 6. Set SSID ----
:SET_SSID
echo.
echo [6] Setting SSID to ClickShare-%SN% on %DEVICE_IP%...
echo ------------------------------------------------------------
curl -k -X PATCH "https://%DEVICE_IP%:%REST_PORT%/v3/network/wireless/1" -H "accept: */*" -H "Content-Type: application/json" -d "{\"accessPoint\":{\"ssid\":\"ClickShare-%SN%\"}}"
echo.
echo.
pause
goto MAIN_MENU

:: ---- 8. Run All Steps ----
:RUN_ALL
echo.
echo ============================================================
echo  Running all steps with SN: %SN%  SSID: ClickShare-%SN%
echo  Device IP: %DEVICE_IP%
echo ============================================================
echo.

echo [Step 1/6] Enabling manufacturing mode...
curl -s -X PUT -H "Content-Type: application/x-www-form-urlencoded" -d "url=%ACTIVATE_URL%" %DEVICE_IP%:%PROD_PORT%/activate
echo.

echo [Step 2/6] Setting serial number to %SN%...
curl -s -X PUT -H "Content-Type: text/plain" -d "%SN%" %DEVICE_IP%:%PROD_PORT%/serial-number
echo.

echo [Step 3/6] Rebooting and waiting for device...
adb reboot
echo   Waiting for device to come back online...
:WAIT_REBOOT
timeout /t 5 >nul
curl -s -k -o nul https://%DEVICE_IP%:%REST_PORT%/v3/status >nul 2>&1
if errorlevel 1 (
    echo   Device not ready, retrying...
    goto WAIT_REBOOT
)
echo   Device is back online!
echo.

echo [Step 4/6] Activating development certificate...
curl -s -X PUT -H "Content-Type: application/x-www-form-urlencoded" -d "url=%ACTIVATE_URL%:80" %DEVICE_IP%:%PROD_PORT%/activate
echo.

echo [Step 5/6] Creating ClickShare certificate...
curl -s -X PUT %DEVICE_IP%:%PROD_PORT%/certificate/clickshare
echo.

echo [Step 6/6] Setting SSID to ClickShare-%SN%...
curl -s -k -X PATCH "https://%DEVICE_IP%:%REST_PORT%/v3/network/wireless/1" -H "accept: */*" -H "Content-Type: application/json" -d "{\"accessPoint\":{\"ssid\":\"ClickShare-%SN%\"}}"
echo.

echo.
echo ============================================================
echo  All steps completed!
echo ============================================================
echo.
pause
goto MAIN_MENU

:: ---- 7. Setup (MDEP wizard + Teams sign-in) ----
:SETUP
echo.
echo [7] Running MDEP setup wizard + Teams sign-in for SN: %SN%...
echo ------------------------------------------------------------
python "%~dp0setup_tool.py" --serial %SN%
echo.
pause
goto MAIN_MENU

:: ---- 9. Run All Steps + Auto Setup ----
:RUN_ALL_SETUP
echo.
echo ============================================================
echo  Running all steps + auto setup with SN: %SN%
echo  Device IP: %DEVICE_IP%
echo ============================================================
echo.
echo [Step 1/6] Enabling manufacturing mode...
curl -s -X PUT -H "Content-Type: application/x-www-form-urlencoded" -d "url=%ACTIVATE_URL%" %DEVICE_IP%:%PROD_PORT%/activate
echo.

echo [Step 2/6] Setting serial number to %SN%...
curl -s -X PUT -H "Content-Type: text/plain" -d "%SN%" %DEVICE_IP%:%PROD_PORT%/serial-number
echo.

echo [Step 3/6] Rebooting and waiting for device...
adb reboot
echo   Waiting for device to come back online...
:WAIT_REBOOT2
timeout /t 5 >nul
curl -s -k -o nul https://%DEVICE_IP%:%REST_PORT%/v3/status >nul 2>&1
if errorlevel 1 (
    echo   Device not ready, retrying...
    goto WAIT_REBOOT2
)
echo   Device is back online!
echo.

echo [Step 4/6] Activating development certificate...
curl -s -X PUT -H "Content-Type: application/x-www-form-urlencoded" -d "url=%ACTIVATE_URL%:80" %DEVICE_IP%:%PROD_PORT%/activate
echo.

echo [Step 5/6] Creating ClickShare certificate...
curl -s -X PUT %DEVICE_IP%:%PROD_PORT%/certificate/clickshare
echo.

echo [Step 6/6] Setting SSID to ClickShare-%SN%...
curl -s -k -X PATCH "https://%DEVICE_IP%:%REST_PORT%/v3/network/wireless/1" -H "accept: */*" -H "Content-Type: application/json" -d "{""accessPoint"":{""ssid"":""ClickShare-%SN%""}}"
echo.
echo.
echo [Step 7] Running MDEP setup wizard + Teams sign-in...
python "%~dp0setup_tool.py" --serial %SN%
echo.
echo ============================================================
echo  All steps + setup completed!
echo ============================================================
echo.
pause
goto MAIN_MENU

:: ---- A. Refresh Device IP Address ----
:FIND_IP
call :GET_IP
echo.
echo Device IP refreshed: %DEVICE_IP%
timeout /t 2 >nul
goto MAIN_MENU

:: ---- B. Change Device IP ----
:CHANGE_IP
echo.
echo Current IP: %DEVICE_IP%
set /p "DEVICE_IP=Enter new device IP: "
echo Device IP changed to %DEVICE_IP%
timeout /t 2 >nul
goto MAIN_MENU

:: ---- C. Change SN ----
:CHANGE_SN
echo.
echo Current SN: %SN%  (SSID: ClickShare-%SN%)
set /p "SN=Enter new SN: "
echo SN changed to %SN%  (SSID: ClickShare-%SN%)
timeout /t 2 >nul
goto MAIN_MENU

:EXIT
echo Bye!
endlocal
exit /b 0

:: ---- Subroutine: detect device IP via adb ----
:GET_IP
set "IPCIDR="
for /f "tokens=2" %%A in ('adb shell ip addr show eth0 2^>nul ^| findstr /C:"inet "') do set "IPCIDR=%%A"
if defined IPCIDR (
    for /f "tokens=1 delims=/" %%B in ("%IPCIDR%") do set "DEVICE_IP=%%B"
)
exit /b 0
