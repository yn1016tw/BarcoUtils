@echo off

set "DEST_KEY=C:\barco\wave4\keys\adb_private_key"
set "DUVEL_KEY=C:\barco\wave4\keys\adb_private_key_duvel"
set "FRUITESSE_KEY=C:\barco\wave4\keys\adb_private_key-fruitesse"

:detect
set "CURRENT_KEY=Unknown"
if not exist "%DEST_KEY%" (
    set "CURRENT_KEY=None"
    goto menu
)
fc /b "%DEST_KEY%" "%DUVEL_KEY%" >nul 2>&1
if %errorlevel%==0 set "CURRENT_KEY=Duvel"
fc /b "%DEST_KEY%" "%FRUITESSE_KEY%" >nul 2>&1
if %errorlevel%==0 set "CURRENT_KEY=Fruitesse"

:menu
cls
echo ==========================================
echo         ADB Vendor Key Switcher
echo ==========================================
echo  Current: %CURRENT_KEY%
echo.
echo  1. Duvel
echo  2. Fruitesse
echo  3. Exit
echo ==========================================
set /p "choice=Select option: "

if "%choice%"=="1" goto duvel
if "%choice%"=="2" goto fruitesse
if "%choice%"=="3" goto end
echo Invalid option. Try again.
echo.
goto detect

:duvel
copy /Y "%DUVEL_KEY%" "%DEST_KEY%" >nul
echo Switched to Duvel key.
adb kill-server >nul 2>&1
adb start-server >nul 2>&1
echo ADB server restarted.
echo.
goto detect

:fruitesse
copy /Y "%FRUITESSE_KEY%" "%DEST_KEY%" >nul
echo Switched to Fruitesse key.
adb kill-server >nul 2>&1
adb start-server >nul 2>&1
echo ADB server restarted.
echo.
goto detect

:end
echo Exiting...
