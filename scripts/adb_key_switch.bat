@echo off

set "DEST_KEY=C:\barco\wave4\keys\adb_private_key"
set "DUVEL_KEY=C:\barco\wave4\keys\duvel\adb_private_key"
set "FRUITESSE_KEY=C:\barco\wave4\keys\fruitesse\adb_private_key"
set "GOD_KEY=C:\barco\wave4\keys\god\adb_private_key"

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
fc /b "%DEST_KEY%" "%GOD_KEY%" >nul 2>&1
if %errorlevel%==0 set "CURRENT_KEY=God"

:menu
cls
echo ==========================================
echo         ADB Vendor Key Switcher
echo ==========================================
echo  Current: %CURRENT_KEY%
echo.
echo  1. Duvel
echo  2. Fruitesse
echo  3. God
echo  4. Exit
echo ==========================================
set /p "choice=Select option: "

if "%choice%"=="1" goto duvel
if "%choice%"=="2" goto fruitesse
if "%choice%"=="3" goto god
if "%choice%"=="4" goto end
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

:god
copy /Y "%GOD_KEY%" "%DEST_KEY%" >nul
echo Switched to God key.
adb kill-server >nul 2>&1
adb start-server >nul 2>&1
echo ADB server restarted.
echo.
goto detect

:end
echo Exiting...
