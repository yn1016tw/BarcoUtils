@echo off
setlocal enabledelayedexpansion

:: Default scrcpy.exe path (same default as testcases/common/utils.py SCRCPY_DEFAULT)
set "SCRCPY_EXE=C:\Tools\scrcpy-win64-v3.3.3\scrcpy.exe"

if not exist "%SCRCPY_EXE%" (
    echo [ERROR] scrcpy.exe not found: %SCRCPY_EXE%
    pause
    exit /b 1
)

call :SELECT_DEVICE
if errorlevel 1 goto END

echo.
echo Launching scrcpy for device: %DEVICE_SERIAL%
echo ------------------------------------------------------------
"%SCRCPY_EXE%" -s %DEVICE_SERIAL%

:END
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
    echo   [%%I] !DEV_%%I!
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
