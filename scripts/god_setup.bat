@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: Default settings
set "PROD_PORT=8085"
set "ACTIVATE_URL=http://korgrt13.barco.com"
set "SN=9752000162"
set "PART_NUMBER=R9861730WW"
set "MAC_ADDRESS=00:04:A5:B1:50:1E"
set "SPFT_DIR=C:\Tools\SP_Flash_Tool_Selector_exe_Windows_v1.2444.00.000\SP_Flash_Tool_V6"
set "FW_BUILD_DIR=C:\Users\jamyan\OneDrive - Barco N.V\Share\FW\God\2099\debug"

call :SELECT_DEVICE
if errorlevel 1 goto EXIT

echo Switching adb to root...
adb -s %DEVICE_SERIAL% root >nul 2>&1
timeout /t 2 >nul

call :GET_IP

:MAIN_MENU
cls
echo ============================================================
echo         Wave4 God Mode Device Setup Tool
echo ============================================================
echo.
echo   Device Serial : %DEVICE_SERIAL%
echo   Device IP   : %DEVICE_IP%
echo   SN          : %SN%
echo   Part Number : %PART_NUMBER%
echo   MAC Address : %MAC_ADDRESS%
echo   FW Build Dir: %FW_BUILD_DIR%
echo.
echo   [1] Enable Manufacturing Mode (activate)
echo   [2] Get Current Firmware Version
echo   [3] Set Serial Number
echo   [4] Set Part Number
echo   [N] Read Part Number
echo   [5] Set Ethernet MAC Address
echo   [6] Install ClickShare Certificate
echo   [V] Override ClickShare Certificate
echo   [7] Install MDEP Enrollment Certificate
echo   [8] Install MDEP Platform Certificate
echo   [9] Enable Secure Boot (SP Flash Tool write-efuse)
echo   [E] Read Secure Boot Status (SP Flash Tool read-efuse)
echo   [O] Auto Setup OOBE (MDEP wizard)
echo   [A] Run All Steps (1-8 in sequence)
echo   [R] Refresh Device IP (adb)
echo   [D] Select Device (adb)
echo   [I] Change Device IP manually
echo   [S] Change Serial Number
echo   [P] Change Part Number
echo   [M] Change MAC Address
echo   [F] Change FW Build Dir
echo   [0] Exit
echo.
echo ============================================================
set /p "CHOICE=Select option: "

if "%CHOICE%"=="1" goto ENABLE_MFG
if "%CHOICE%"=="2" goto GET_FW
if "%CHOICE%"=="3" goto SET_SERIAL
if "%CHOICE%"=="4" goto SET_PART_NUMBER
if /i "%CHOICE%"=="N" goto READ_PART_NUMBER
if "%CHOICE%"=="5" goto SET_MAC
if "%CHOICE%"=="6" goto CERT_CLICKSHARE
if /i "%CHOICE%"=="V" goto CERT_CLICKSHARE_OVERRIDE
if "%CHOICE%"=="7" goto CERT_MDEP_ENROLLMENT
if "%CHOICE%"=="8" goto CERT_MDEP_PLATFORM
if "%CHOICE%"=="9" goto ENABLE_SECURE_BOOT
if /i "%CHOICE%"=="E" goto READ_SECURE_BOOT
if /i "%CHOICE%"=="O" goto SETUP_OOBE
if /i "%CHOICE%"=="A" goto RUN_ALL
if /i "%CHOICE%"=="R" goto REFRESH_IP
if /i "%CHOICE%"=="D" goto RESELECT_DEVICE
if /i "%CHOICE%"=="I" goto CHANGE_IP
if /i "%CHOICE%"=="S" goto CHANGE_SN
if /i "%CHOICE%"=="P" goto CHANGE_PN
if /i "%CHOICE%"=="M" goto CHANGE_MAC
if /i "%CHOICE%"=="F" goto CHANGE_FW_DIR
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

:: ---- N. Read Part Number ----
:READ_PART_NUMBER
echo.
echo [N] Reading part number from %DEVICE_IP%...
echo ------------------------------------------------------------
curl -X GET %DEVICE_IP%:%PROD_PORT%/article-number
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

:: ---- V. Override ClickShare Certificate ----
:CERT_CLICKSHARE_OVERRIDE
echo.
echo [V] Overriding ClickShare certificate on %DEVICE_IP%...
echo ------------------------------------------------------------
curl -X PUT "%DEVICE_IP%:%PROD_PORT%/certificate/clickshare?override=True"
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

:: ---- 9. Enable Secure Boot ----
:ENABLE_SECURE_BOOT
echo.
echo [9] Enable Secure Boot via SP Flash Tool write-efuse
echo ------------------------------------------------------------
echo   Tool dir  : %SPFT_DIR%
echo   flash.xml : %FW_BUILD_DIR%\download_agent\flash.xml
echo   efuse.img : %FW_BUILD_DIR%\efuse.img
echo.
echo   WARNING: This permanently writes the eFuse (Secure Boot) and
echo   cannot be undone. Device must be connected in USB BROM/download mode.
echo.
set /p "CONFIRM=Type YES to continue: "
if /i not "%CONFIRM%"=="YES" (
    echo Cancelled.
    pause
    goto MAIN_MENU
)
pushd "%SPFT_DIR%"
SPFlashToolV6.exe -f "%FW_BUILD_DIR%\download_agent\flash.xml" -c write-efuse --file "%FW_BUILD_DIR%\efuse.img" -l USB
popd
echo.
echo.
pause
goto MAIN_MENU

:: ---- E. Read Secure Boot Status ----
:READ_SECURE_BOOT
echo.
echo [E] Reading Secure Boot (eFuse) status via SP Flash Tool read-efuse
echo ------------------------------------------------------------
echo   Tool dir  : %SPFT_DIR%
echo   flash.xml : %FW_BUILD_DIR%\download_agent\flash.xml
echo   Log file  : %SPFT_DIR%\read-efuse.log
echo.
echo   Device must be connected in USB BROM/download mode.
echo.
pushd "%SPFT_DIR%"
SPFlashToolV6.exe -f "%FW_BUILD_DIR%\download_agent\flash.xml" -c read-efuse --file read-efuse.log -l USB
echo.
echo ------------------------------------------------------------
echo   read-efuse.log contents:
echo ------------------------------------------------------------
type read-efuse.log
popd
echo.
echo.
pause
goto MAIN_MENU

:: ---- O. Auto Setup OOBE ----
:SETUP_OOBE
echo.
echo [O] Running MDEP setup wizard on %DEVICE_IP%...
echo ------------------------------------------------------------
python "%~dp0setup_tool.py" --ip %DEVICE_IP%
echo.
pause
goto MAIN_MENU

:: ---- A. Run All Steps ----
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

:: ---- D. Select Device ----
:RESELECT_DEVICE
call :SELECT_DEVICE
if errorlevel 1 goto MAIN_MENU
call :GET_IP
echo.
echo Device selected: %DEVICE_SERIAL%  (IP: %DEVICE_IP%)
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

:: ---- F. Change FW Build Dir ----
:CHANGE_FW_DIR
echo.
echo Current FW Build Dir: %FW_BUILD_DIR%
set /p "FW_BUILD_DIR=Enter new FW Build Dir: "
echo FW Build Dir changed to %FW_BUILD_DIR%
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
for /f "tokens=2" %%A in ('adb -s %DEVICE_SERIAL% shell ip addr show eth0 2^>nul ^| findstr /C:"inet "') do set "IPCIDR=%%A"
if defined IPCIDR (
    for /f "tokens=1 delims=/" %%B in ("%IPCIDR%") do set "DEVICE_IP=%%B"
)
exit /b 0

:: ---- Subroutine: check adb devices list, pick a target if multiple ----
:SELECT_DEVICE
set "DEVICE_SERIAL="
set "DEV_COUNT=0"
for /f "skip=1 tokens=1,2" %%A in ('adb devices') do (
    if not "%%A"=="" if /i "%%B"=="device" (
        set /a DEV_COUNT+=1
        set "DEV_!DEV_COUNT!=%%A"
    )
)

if !DEV_COUNT! equ 0 (
    echo.
    echo No ADB devices found. Connect a device ^(authorized^) and try again.
    pause
    exit /b 1
)

if !DEV_COUNT! equ 1 (
    set "DEVICE_SERIAL=!DEV_1!"
    exit /b 0
)

echo.
echo Multiple ADB devices detected:
echo ------------------------------------------------------------
for /l %%I in (1,1,!DEV_COUNT!) do echo   [%%I] !DEV_%%I!
echo ------------------------------------------------------------

:SELECT_DEVICE_PROMPT
set "DEV_CHOICE="
set /p "DEV_CHOICE=Select target device number: "
if not defined DEV_%DEV_CHOICE% (
    echo Invalid selection.
    goto SELECT_DEVICE_PROMPT
)
set "DEVICE_SERIAL=!DEV_%DEV_CHOICE%!"
exit /b 0
