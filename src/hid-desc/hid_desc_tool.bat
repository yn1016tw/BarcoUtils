@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

set "PULL_DIR=%~dp0device_files"
for /f %%a in ('copy /Z "%~dpf0" nul') do set "CR=%%a"

echo ============================================================
echo   HID Descriptor Tool - requesting adb root...
echo ============================================================
call :WAIT_FOR_ROOT
echo.

:MAIN_MENU
cls
echo ============================================================
echo         Button HID Descriptor Tool
echo ============================================================
echo.
echo   [1] Enable rootfsoverlay
echo   [2] Remount as RW access
echo   [3] Backup HID descriptor   (hid*.bin -^> hid*.bak)
echo   [4] Recovery HID descriptor (hid*.bak -^> hid*.bin)
echo   [5] Update Usage Page ^& Usage
echo   [6] Reboot Button
echo   [7] Clear backup HID descriptor (delete hid*.bak)
echo   [8] Read HID descriptor (parse and print hid*.bin)
echo   [0] Exit
echo.
echo ============================================================
set /p "CHOICE=Select option: "

if "%CHOICE%"=="1" goto ENABLE_OVERLAY
if "%CHOICE%"=="2" goto REMOUNT_RW
if "%CHOICE%"=="3" goto BACKUP
if "%CHOICE%"=="4" goto RECOVER
if "%CHOICE%"=="5" goto UPDATE_USAGE
if "%CHOICE%"=="6" goto REBOOT
if "%CHOICE%"=="7" goto CLEAR_BACKUP
if "%CHOICE%"=="8" goto READ_DESC
if "%CHOICE%"=="0" goto EXIT
echo Invalid option.
timeout /t 2 >nul
goto MAIN_MENU

:: ---- 1. Enable rootfsoverlay ----
:ENABLE_OVERLAY
echo.
echo [1] Enabling rootfsoverlay...
echo ------------------------------------------------------------
adb shell "touch /store/.enable_rootfsoverlay"
echo   Done. A reboot is required for this to take effect.
echo.
pause
goto MAIN_MENU

:: ---- 2. Remount as RW access ----
:REMOUNT_RW
echo.
echo [2] Remounting as RW access...
echo ------------------------------------------------------------
adb shell "mount -o remount,rw /"
echo.
pause
goto MAIN_MENU

:: ---- 3. Backup HID descriptor ----
:BACKUP
echo.
echo [3] Backing up HID descriptor (hid*.bin -^> hid*.bak)...
echo ------------------------------------------------------------
for /f "usebackq delims=" %%F in (`adb shell "ls /clickshare/hid*.bin" 2^>nul`) do (
    call :CP_ONE_FILE "%%F" ".bin" ".bak"
)
echo   Done.
echo.
pause
goto MAIN_MENU

:: ---- 4. Recovery HID descriptor ----
:RECOVER
echo.
echo [4] Recovering HID descriptor (hid*.bak -^> hid*.bin)...
echo ------------------------------------------------------------
for /f "usebackq delims=" %%F in (`adb shell "ls /clickshare/hid*.bak" 2^>nul`) do (
    call :CP_ONE_FILE "%%F" ".bak" ".bin"
)
echo   Done.
echo.
pause
goto MAIN_MENU

:CP_ONE_FILE
set "SRC_PATH=%~1"
if "!SRC_PATH:~-1!"=="!CR!" set "SRC_PATH=!SRC_PATH:~0,-1!"
set "SRC_EXT=%~2"
set "DST_EXT=%~3"
call set "DST_PATH=%%SRC_PATH:%SRC_EXT%=%DST_EXT%%%"
echo   %SRC_PATH% -^> %DST_PATH%
adb shell "cp '%SRC_PATH%' '%DST_PATH%'"
goto :eof

:: ---- 5. Update Usage Page & Usage ----
:UPDATE_USAGE
echo.
echo [5] Update Usage Page ^& Usage
echo ------------------------------------------------------------
if not exist "%PULL_DIR%" mkdir "%PULL_DIR%"

echo.
echo   Listing /clickshare/hid*.bin on device...
for /f "usebackq delims=" %%F in (`adb shell "ls /clickshare/hid*.bin" 2^>nul`) do (
    call :PATCH_ONE_FILE "%%F"
)
echo.
echo   All files processed.
pause
goto MAIN_MENU

:PATCH_ONE_FILE
set "REMOTE_PATH=%~1"
if "!REMOTE_PATH:~-1!"=="!CR!" set "REMOTE_PATH=!REMOTE_PATH:~0,-1!"
for %%N in ("%REMOTE_PATH%") do set "FILE_NAME=%%~nxN"
if "%FILE_NAME%"=="" goto :eof

echo.
echo   --- %FILE_NAME% ---
set "NEW_USAGE_PAGE="
set "NEW_USAGE="
set /p "NEW_USAGE_PAGE=  New Usage Page (hex, e.g. 0x0081, Enter=skip this file): "
set /p "NEW_USAGE=  New Usage (hex, e.g. 0x83, Enter=skip this file): "

if "%NEW_USAGE_PAGE%"=="" if "%NEW_USAGE%"=="" (
    echo     Nothing entered, skipping %FILE_NAME%.
    goto :eof
)

set "PATCH_ARGS="
if not "%NEW_USAGE_PAGE%"=="" set "PATCH_ARGS=--usage-page %NEW_USAGE_PAGE%"
if not "%NEW_USAGE%"=="" set "PATCH_ARGS=%PATCH_ARGS% --usage %NEW_USAGE%"

adb pull "%REMOTE_PATH%" "%PULL_DIR%\%FILE_NAME%" >nul
if errorlevel 1 (
    echo     [!] Pull failed, skipping.
    goto :eof
)

python "%~dp0patch_hid_desc.py" "%PULL_DIR%\%FILE_NAME%" %PATCH_ARGS% --out "%PULL_DIR%\%FILE_NAME%"
if errorlevel 1 (
    echo     [!] Patch failed, not pushing back.
    goto :eof
)

adb push "%PULL_DIR%\%FILE_NAME%" "%REMOTE_PATH%" >nul
if errorlevel 1 (
    echo     [!] Push failed.
    goto :eof
)
echo     Pushed back to %REMOTE_PATH%
goto :eof

:: ---- 6. Reboot Button ----
:REBOOT
echo.
echo [6] Rebooting Button...
echo ------------------------------------------------------------
adb shell reboot
call :WAIT_FOR_ROOT
echo   Done.
echo.
pause
goto MAIN_MENU

:: ---- 7. Clear backup HID descriptor ----
:CLEAR_BACKUP
echo.
echo [7] Clearing backup HID descriptor (deleting hid*.bak)...
echo ------------------------------------------------------------
for /f "usebackq delims=" %%F in (`adb shell "ls /clickshare/hid*.bak" 2^>nul`) do (
    set "DEL_PATH=%%F"
    if "!DEL_PATH:~-1!"=="!CR!" set "DEL_PATH=!DEL_PATH:~0,-1!"
    echo   Deleting !DEL_PATH!
    adb shell "rm '!DEL_PATH!'"
)
echo   Done.
echo.
pause
goto MAIN_MENU

:: ---- 8. Read HID descriptor ----
:READ_DESC
echo.
echo [8] Reading HID descriptor...
echo ------------------------------------------------------------
if not exist "%PULL_DIR%" mkdir "%PULL_DIR%"
for /f "usebackq delims=" %%F in (`adb shell "ls /clickshare/hid*.bin" 2^>nul`) do (
    call :READ_ONE_FILE "%%F"
)
echo.
pause
goto MAIN_MENU

:READ_ONE_FILE
set "REMOTE_PATH=%~1"
if "!REMOTE_PATH:~-1!"=="!CR!" set "REMOTE_PATH=!REMOTE_PATH:~0,-1!"
for %%N in ("%REMOTE_PATH%") do set "FILE_NAME=%%~nxN"
if "%FILE_NAME%"=="" goto :eof

adb pull "%REMOTE_PATH%" "%PULL_DIR%\%FILE_NAME%" >nul
if errorlevel 1 (
    echo   [!] Pull failed for %FILE_NAME%, skipping.
    goto :eof
)
python "%~dp0parse_hid_desc.py" "%PULL_DIR%\%FILE_NAME%"
goto :eof

:WAIT_FOR_ROOT
echo   Waiting for device...
adb wait-for-device
adb root >nul 2>&1
:WAIT_ROOT_LOOP
timeout /t 2 >nul
adb shell echo connected >nul 2>&1
if errorlevel 1 (
    echo   Waiting for adb to reconnect as root...
    goto WAIT_ROOT_LOOP
)
echo   adb is root.
adb shell "mount -o remount,rw /"
goto :eof

:EXIT
echo Bye!
endlocal
exit /b 0
