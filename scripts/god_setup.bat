@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: Default settings
set "PROD_PORT=8085"
set "ACTIVATE_URL=http://korgrt13.barco.com"
set "SN=9752000162"
set "PART_NUMBER=R9861730WW"
set "MAC_ADDRESS=00:04:A5:B1:50:1E"

call :GET_IP

:MAIN_MENU
cls
echo ============================================================
echo         Wave4 God Mode Device Setup Tool
echo ============================================================
echo.
echo   Device IP   : %DEVICE_IP%
echo   SN          : %SN%
echo   Part Number : %PART_NUMBER%
echo   MAC Address : %MAC_ADDRESS%
echo.
echo   [1] Enable Manufacturing Mode (activate)
echo   [2] Get Current Firmware Version
echo   [3] Set Serial Number
echo   [4] Set Part Number
echo   [5] Set Ethernet MAC Address
echo   [6] Install ClickShare Certificate
echo   [7] Install MDEP Enrollment Certificate
echo   [8] Install MDEP Platform Certificate
echo   [9] Run All Steps (1-8 in sequence)
echo   [R] Refresh Device IP (adb)
echo   [I] Change Device IP manually
echo   [S] Change Serial Number
echo   [P] Change Part Number
echo   [M] Change MAC Address
echo   [0] Exit
echo.
echo ============================================================
set /p "CHOICE=Select option: "

if "%CHOICE%"=="1" goto ENABLE_MFG
if "%CHOICE%"=="2" goto GET_FW
if "%CHOICE%"=="3" goto SET_SERIAL
if "%CHOICE%"=="4" goto SET_PART_NUMBER
if "%CHOICE%"=="5" goto SET_MAC
if "%CHOICE%"=="6" goto CERT_CLICKSHARE
if "%CHOICE%"=="7" goto CERT_MDEP_ENROLLMENT
if "%CHOICE%"=="8" goto CERT_MDEP_PLATFORM
if "%CHOICE%"=="9" goto RUN_ALL
if /i "%CHOICE%"=="R" goto REFRESH_IP
if /i "%CHOICE%"=="I" goto CHANGE_IP
if /i "%CHOICE%"=="S" goto CHANGE_SN
if /i "%CHOICE%"=="P" goto CHANGE_PN
if /i "%CHOICE%"=="M" goto CHANGE_MAC
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

:: ---- 2. Get Current Firmware Version ----
:GET_FW
echo.
echo [2] Getting current firmware version from %DEVICE_IP%...
echo ------------------------------------------------------------
curl %DEVICE_IP%:%PROD_PORT%/firmware/current
echo.
echo.
pause
goto MAIN_MENU

:: ---- 3. Set Serial Number ----
:SET_SERIAL
echo.
echo [3] Setting serial number to %SN% on %DEVICE_IP%...
echo ------------------------------------------------------------
curl -X PUT -H "Content-Type: text/plain" -d "%SN%" %DEVICE_IP%:%PROD_PORT%/serial-number
echo.
echo.
pause
goto MAIN_MENU

:: ---- 4. Set Part Number ----
:SET_PART_NUMBER
echo.
echo [4] Setting part number to %PART_NUMBER% on %DEVICE_IP%...
echo ------------------------------------------------------------
curl -X PUT -H "Content-Type: text/plain" -d "%PART_NUMBER%" %DEVICE_IP%:%PROD_PORT%/article-number
echo.
echo.
pause
goto MAIN_MENU

:: ---- 5. Set Ethernet MAC Address ----
:SET_MAC
echo.
echo [5] Setting Ethernet MAC address to %MAC_ADDRESS% on %DEVICE_IP%...
echo ------------------------------------------------------------
curl -X PUT -H "Content-Type: text/plain" -d "%MAC_ADDRESS%" %DEVICE_IP%:%PROD_PORT%/mac-address
echo.
echo.
pause
goto MAIN_MENU

:: ---- 6. Install ClickShare Certificate ----
:CERT_CLICKSHARE
echo.
echo [6] Installing ClickShare certificate on %DEVICE_IP%...
echo ------------------------------------------------------------
curl -X PUT %DEVICE_IP%:%PROD_PORT%/certificate/clickshare
echo.
echo.
pause
goto MAIN_MENU

:: ---- 7. Install MDEP Enrollment Certificate ----
:CERT_MDEP_ENROLLMENT
echo.
echo [7] Installing MDEP enrollment certificate on %DEVICE_IP%...
echo ------------------------------------------------------------
curl -X PUT %DEVICE_IP%:%PROD_PORT%/certificate/mdep_enrollment
echo.
echo.
pause
goto MAIN_MENU

:: ---- 8. Install MDEP Platform Certificate ----
:CERT_MDEP_PLATFORM
echo.
echo [8] Installing MDEP platform certificate on %DEVICE_IP%...
echo ------------------------------------------------------------
curl -X PUT %DEVICE_IP%:%PROD_PORT%/certificate/mdep_platform
echo.
echo.
pause
goto MAIN_MENU

:: ---- 9. Run All Steps ----
:RUN_ALL
echo.
echo ============================================================
echo  Running all steps on %DEVICE_IP%
echo  SN: %SN%  Part Number: %PART_NUMBER%  MAC: %MAC_ADDRESS%
echo ============================================================
echo.

echo [Step 1/8] Enabling manufacturing mode...
curl -s -X PUT -H "Content-Type: application/x-www-form-urlencoded" -d "url=%ACTIVATE_URL%" %DEVICE_IP%:%PROD_PORT%/activate
echo.

echo [Step 2/8] Getting current firmware version...
curl -s %DEVICE_IP%:%PROD_PORT%/firmware/current
echo.

echo [Step 3/8] Setting serial number to %SN%...
curl -s -X PUT -H "Content-Type: text/plain" -d "%SN%" %DEVICE_IP%:%PROD_PORT%/serial-number
echo.

echo [Step 4/8] Setting part number to %PART_NUMBER%...
curl -s -X PUT -H "Content-Type: text/plain" -d "%PART_NUMBER%" %DEVICE_IP%:%PROD_PORT%/article-number
echo.

echo [Step 5/8] Setting Ethernet MAC address to %MAC_ADDRESS%...
curl -s -X PUT -H "Content-Type: text/plain" -d "%MAC_ADDRESS%" %DEVICE_IP%:%PROD_PORT%/mac-address
echo.

echo [Step 6/8] Installing ClickShare certificate...
curl -s -X PUT %DEVICE_IP%:%PROD_PORT%/certificate/clickshare
echo.

echo [Step 7/8] Installing MDEP enrollment certificate...
curl -s -X PUT %DEVICE_IP%:%PROD_PORT%/certificate/mdep_enrollment
echo.

echo [Step 8/8] Installing MDEP platform certificate...
curl -s -X PUT %DEVICE_IP%:%PROD_PORT%/certificate/mdep_platform
echo.

echo.
echo ============================================================
echo  All steps completed!
echo ============================================================
echo.
pause
goto MAIN_MENU

:: ---- R. Refresh Device IP ----
:REFRESH_IP
call :GET_IP
echo.
echo Device IP refreshed: %DEVICE_IP%
timeout /t 2 >nul
goto MAIN_MENU

:: ---- I. Change Device IP manually ----
:CHANGE_IP
echo.
echo Current IP: %DEVICE_IP%
set /p "DEVICE_IP=Enter new device IP: "
echo Device IP changed to %DEVICE_IP%
timeout /t 2 >nul
goto MAIN_MENU

:: ---- S. Change Serial Number ----
:CHANGE_SN
echo.
echo Current SN: %SN%
set /p "SN=Enter new SN: "
echo SN changed to %SN%
timeout /t 2 >nul
goto MAIN_MENU

:: ---- P. Change Part Number ----
:CHANGE_PN
echo.
echo Current Part Number: %PART_NUMBER%
set /p "PART_NUMBER=Enter new Part Number: "
echo Part Number changed to %PART_NUMBER%
timeout /t 2 >nul
goto MAIN_MENU

:: ---- M. Change MAC Address ----
:CHANGE_MAC
echo.
echo Current MAC Address: %MAC_ADDRESS%
set /p "MAC_ADDRESS=Enter new MAC Address: "
echo MAC Address changed to %MAC_ADDRESS%
timeout /t 2 >nul
goto MAIN_MENU

:EXIT
echo Bye!
endlocal
exit /b 0

:: ---- Subroutine: detect device IP via adb ----
:GET_IP
set "DEVICE_IP=Unknown"
set "IPCIDR="
for /f "tokens=2" %%A in ('adb shell ip addr show eth0 2^>nul ^| findstr "inet "') do set "IPCIDR=%%A"
if defined IPCIDR (
    for /f "tokens=1 delims=/" %%B in ("%IPCIDR%") do set "DEVICE_IP=%%B"
)
exit /b 0
