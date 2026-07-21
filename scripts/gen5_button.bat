@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   Gen5 ClickShare Button Tool
echo ============================================================
echo   Detecting Gen5 Button over adb...
echo ------------------------------------------------------------

set "BTN_SERIAL="
for /f "skip=1 tokens=1,2" %%A in ('adb devices') do (
    if "%%B"=="device" (
        for /f "usebackq delims=" %%P in (`adb -s %%A shell "which g5configcli" 2^>nul`) do (
            if not "%%P"=="" set "BTN_SERIAL=%%A"
        )
    )
)

if "%BTN_SERIAL%"=="" (
    echo.
    echo   No Gen5 ClickShare Button detected via adb.
    echo   Make sure the button is connected and authorized ^(check "adb devices"^).
    echo.
    pause
    exit /b 1
)

echo   Found Gen5 Button: %BTN_SERIAL%
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
