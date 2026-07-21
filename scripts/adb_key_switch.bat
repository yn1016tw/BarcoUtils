@echo off

set "DEST_KEY=C:\barco\wave4\keys\adb_private_key"
set "DUVEL_KEY=C:\barco\wave4\keys\duvel\adb_private_key"
set "FRUITESSE_KEY=C:\barco\wave4\keys\fruitesse\adb_private_key"
set "GOD_KEY=C:\barco\wave4\keys\god\adb_private_key"

:detect
set "CURRENT_KEY=Unknown"
if "%ADB_VENDOR_KEYS%"=="%DUVEL_KEY%;%FRUITESSE_KEY%" (
    set "CURRENT_KEY=Duvel + Fruitesse (GEN5 Button)"
    goto menu
)
if "%ADB_VENDOR_KEYS%"=="%GOD_KEY%;%FRUITESSE_KEY%" (
    set "CURRENT_KEY=God + Fruitesse (GEN5 Button)"
    goto menu
)
if "%ADB_VENDOR_KEYS%"=="%DUVEL_KEY%;%FRUITESSE_KEY%;%GOD_KEY%" (
    set "CURRENT_KEY=All"
    goto menu
)
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
echo  2. Fruitesse (GEN5 Button)
echo  3. God
echo  4. Duvel + Fruitesse (GEN5 Button)
echo  5. God + Fruitesse (GEN5 Button)
echo  6. All
echo  7. Exit
echo ==========================================
set /p "choice=Select option: "

if "%choice%"=="1" goto duvel
if "%choice%"=="2" goto fruitesse
if "%choice%"=="3" goto god
if "%choice%"=="4" goto duvel_fruitesse
if "%choice%"=="5" goto god_fruitesse
if "%choice%"=="6" goto all
if "%choice%"=="7" goto end
echo Invalid option. Try again.
echo.
goto detect

:duvel
copy /Y "%DUVEL_KEY%" "%DEST_KEY%" >nul
reg delete "HKCU\Environment" /v ADB_VENDOR_KEYS /f >nul 2>&1
set "ADB_VENDOR_KEYS="
echo Switched to Duvel key.
adb kill-server >nul 2>&1
adb start-server >nul 2>&1
echo ADB server restarted.
echo.
goto detect

:fruitesse
copy /Y "%FRUITESSE_KEY%" "%DEST_KEY%" >nul
reg delete "HKCU\Environment" /v ADB_VENDOR_KEYS /f >nul 2>&1
set "ADB_VENDOR_KEYS="
echo Switched to Fruitesse key.
adb kill-server >nul 2>&1
adb start-server >nul 2>&1
echo ADB server restarted.
echo.
goto detect

:god
copy /Y "%GOD_KEY%" "%DEST_KEY%" >nul
reg delete "HKCU\Environment" /v ADB_VENDOR_KEYS /f >nul 2>&1
set "ADB_VENDOR_KEYS="
echo Switched to God key.
adb kill-server >nul 2>&1
adb start-server >nul 2>&1
echo ADB server restarted.
echo.
goto detect

:duvel_fruitesse
setx ADB_VENDOR_KEYS "%DUVEL_KEY%;%FRUITESSE_KEY%" >nul
set "ADB_VENDOR_KEYS=%DUVEL_KEY%;%FRUITESSE_KEY%"
echo Set ADB_VENDOR_KEYS to Duvel + Fruitesse (GEN5 Button).
adb kill-server >nul 2>&1
adb start-server >nul 2>&1
echo ADB server restarted.
echo.
goto detect

:god_fruitesse
setx ADB_VENDOR_KEYS "%GOD_KEY%;%FRUITESSE_KEY%" >nul
set "ADB_VENDOR_KEYS=%GOD_KEY%;%FRUITESSE_KEY%"
echo Set ADB_VENDOR_KEYS to God + Fruitesse (GEN5 Button).
adb kill-server >nul 2>&1
adb start-server >nul 2>&1
echo ADB server restarted.
echo.
goto detect

:all
setx ADB_VENDOR_KEYS "%DUVEL_KEY%;%FRUITESSE_KEY%;%GOD_KEY%" >nul
set "ADB_VENDOR_KEYS=%DUVEL_KEY%;%FRUITESSE_KEY%;%GOD_KEY%"
echo Set ADB_VENDOR_KEYS to Duvel + Fruitesse + God (all keys).
adb kill-server >nul 2>&1
adb start-server >nul 2>&1
echo ADB server restarted.
echo.
goto detect

:end
echo Exiting...
