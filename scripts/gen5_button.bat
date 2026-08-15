@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   Gen5 ClickShare Button Tool
echo ============================================================
echo   Listing connected adb devices...
echo ------------------------------------------------------------

set "DEV_COUNT=0"
for /f "skip=1 tokens=1,2" %%A in ('adb devices') do (
    if "%%B"=="device" (
        set /a DEV_COUNT+=1
        set "DEV_!DEV_COUNT!=%%A"
    )
)

if "%DEV_COUNT%"=="0" (
    echo.
    echo   No adb devices found.
    echo   Make sure the device is connected and authorized ^(check "adb devices"^).
    echo.
    pause
    exit /b 1
)

echo.
for /l %%I in (1,1,%DEV_COUNT%) do (
    echo   [%%I] !DEV_%%I!
)
echo.
set "DEV_CHOICE="
set /p "DEV_CHOICE=Select device: "

set "BTN_SERIAL="
if defined DEV_%DEV_CHOICE% set "BTN_SERIAL=!DEV_%DEV_CHOICE%!"

if "%BTN_SERIAL%"=="" (
    echo Invalid selection.
    pause
    exit /b 1
)

echo   Selected device: %BTN_SERIAL%
echo.
cls

:MAIN_MENU
echo ============================================================
echo   Gen5 Button: %BTN_SERIAL%
echo ============================================================
echo.
echo   [1] Short press
echo   [2] Long press
echo   [0] Exit
echo.
echo ============================================================
set /p "CHOICE=Select option: "

if "%CHOICE%"=="1" goto SHORT_PRESS
if "%CHOICE%"=="2" goto LONG_PRESS
if "%CHOICE%"=="0" goto EXIT
echo Invalid option.
timeout /t 2 >nul
goto MAIN_MENU

:SHORT_PRESS
echo.
echo [1] Sending short press...
echo ------------------------------------------------------------
python "%~dp0gen5_button_press.py" --serial %BTN_SERIAL%
echo.
pause
goto MAIN_MENU

:LONG_PRESS
echo.
echo [2] Sending long press...
echo ------------------------------------------------------------
python "%~dp0gen5_button_press.py" --serial %BTN_SERIAL% --long
echo.
pause
goto MAIN_MENU

:EXIT
echo Bye!
endlocal
exit /b 0
