@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

set "EMAIL=mtr_p_25@barcomxdev.onmicrosoft.com"
set "PASSWORD=Devel_25"
set "ADMIN_PW=Admin@123"
set "LANGUAGE=English"
set "TIMEZONE=Taipei"

:CONNECT_MENU
cls
echo ============================================================
echo          Duvel Setup Tool
echo ============================================================
echo.
echo  [1] Connect by IP address
echo  [2] Connect by USB serial
echo  [0] Exit
echo.
echo ============================================================
set /p "CHOICE=Select option: "

if "%CHOICE%"=="1" goto CONNECT_IP
if "%CHOICE%"=="2" goto CONNECT_SERIAL
if "%CHOICE%"=="0" goto EXIT
echo Invalid option.
timeout /t 2 >nul
goto CONNECT_MENU

:CONNECT_IP
echo.
set /p "DEV_IP=Enter device IP address: "
set "CONN_ARG=--ip %DEV_IP%"
goto RUN

:CONNECT_SERIAL
echo.
set /p "DEV_SN=Enter USB serial number: "
set "CONN_ARG=--serial %DEV_SN%"
goto RUN

:RUN
cls
echo ============================================================
echo          Duvel Setup Tool
echo ============================================================
echo.
echo  Connection  : %CONN_ARG%
echo  Email       : %EMAIL%
echo  Admin PW    : %ADMIN_PW%
echo  Language    : %LANGUAGE%
echo  Timezone    : %TIMEZONE%
echo.
echo ============================================================
echo.
cd /d "%~dp0.."
python scripts\setup_tool.py %CONN_ARG% --email "%EMAIL%" --password "%PASSWORD%" --admin-password "%ADMIN_PW%" --language "%LANGUAGE%" --timezone "%TIMEZONE%"
echo.
echo ============================================================
echo  Done. Exit code: %ERRORLEVEL%
echo ============================================================
echo.
pause
goto CONNECT_MENU

:EXIT
endlocal
exit /b 0
