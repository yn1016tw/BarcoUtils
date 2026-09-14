@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

call :SELECT_DEVICE
if errorlevel 1 goto EXIT

:MAIN_MENU
cls
echo ============================================================
echo         GOD Verification Test Menu
echo ============================================================
echo.
echo   Device Serial : %DEVICE_SERIAL%
echo.
echo   [1] config_manager   - configuration-manager-apk (verify_all_keys.ps1)
echo   [2] feature-flag     - feature-flags-apk (verify_featureflags_app.ps1)
echo   [3] led_manager      - led-manager-apk, full LED behavior sweep (god_verify_led_manager_app.ps1)
echo   [D] Select Device
echo   [0] Exit
echo.
echo ============================================================
set /p "CHOICE=Select option: "

if "%CHOICE%"=="1" goto RUN_CONFIG_MANAGER
if "%CHOICE%"=="2" goto RUN_FEATURE_FLAG
if "%CHOICE%"=="3" goto RUN_LED_MANAGER
if /i "%CHOICE%"=="D" goto RESELECT_DEVICE
if "%CHOICE%"=="0" goto EXIT
echo Invalid option.
timeout /t 2 >nul
goto MAIN_MENU

:: ---- 1. config_manager ----
:RUN_CONFIG_MANAGER
echo.
echo [1] config_manager - running verify_all_keys.ps1 on %DEVICE_SERIAL%...
echo ------------------------------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify_all_keys.ps1" -Serial %DEVICE_SERIAL%
echo.
echo ------------------------------------------------------------
pause
goto MAIN_MENU

:: ---- 2. feature-flag ----
:RUN_FEATURE_FLAG
echo.
echo [2] feature-flag - running verify_featureflags_app.ps1 on %DEVICE_SERIAL%...
echo ------------------------------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify_featureflags_app.ps1" -Serial %DEVICE_SERIAL%
echo.
echo ------------------------------------------------------------
pause
goto MAIN_MENU

:: ---- 3. led_manager ----
:RUN_LED_MANAGER
echo.
echo [3] led_manager - running god_verify_led_manager_app.ps1 on %DEVICE_SERIAL%...
echo     -TriggerScenario is enabled: this briefly overrides the Base Unit's real LED
echo     pattern for each of the 15 tested scenarios, then reverts to Idle automatically.
echo ------------------------------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0god_verify_led_manager_app.ps1" -Serial %DEVICE_SERIAL% -TriggerScenario
echo.
echo ------------------------------------------------------------
pause
goto MAIN_MENU

:: ---- D. Select Device ----
:RESELECT_DEVICE
call :SELECT_DEVICE
if errorlevel 1 goto MAIN_MENU
echo.
echo Device selected: %DEVICE_SERIAL%
timeout /t 2 >nul
goto MAIN_MENU

:EXIT
echo Bye!
endlocal
exit /b 0

:: ---- Subroutine: list all adb devices, let the user pick a target ----
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
    echo No adb devices found. Connect a device ^(authorized^) and try again.
    pause
    exit /b 1
)

echo.
echo Connected devices:
echo ------------------------------------------------------------
for /l %%I in (1,1,!DEV_COUNT!) do (
    call :DETECT_DEVICE_LABEL !DEV_%%I!
    echo   [%%I] !DEV_%%I!  ^(!DEVICE_LABEL!^)
)
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

:: ---- Subroutine: detect device type label (GEN5 Button / God / Duvel) via adb ----
:DETECT_DEVICE_LABEL
set "DEVICE_LABEL=Unknown"
for /f "usebackq delims=" %%G in (`adb -s %1 shell which g5configcli 2^>nul`) do if not "%%G"=="" set "DEVICE_LABEL=GEN5 Button"
if "%DEVICE_LABEL%"=="Unknown" (
    for /f "usebackq delims=" %%P in (`adb -s %1 shell getprop ro.barco.platform 2^>nul`) do (
        if /i "%%P"=="w4god" set "DEVICE_LABEL=God"
        if /i "%%P"=="w4duvel" set "DEVICE_LABEL=Duvel"
    )
)
exit /b 0
