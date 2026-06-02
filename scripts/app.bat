@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

::
:: ClickShare Desktop App — Log 啟用方式說明
:: ============================================================
::
:: 方法一：按住 Shift 啟動
::   啟動前按住左 Shift 鍵。
::
:: 方法二：環境變數 CLICKSHARE_DEBUG
::   src/main.cpp:201-207
::     const char *envDebugClient = getenv("CLICKSHARE_DEBUG");
::     return (std::string(envDebugClient) == "ON");
::   設定方式（當前 session）：
::     set CLICKSHARE_DEBUG=ON
::   永久生效（使用者環境變數）：
::     setx CLICKSHARE_DEBUG ON
::   本工具即用來管理此環境變數。
::
:: 方法三：命令列參數
::   -enablelogging          啟用 logging
::   -debuglogging           啟用 debug level log
::   -loglevel <level>       指定 log 等級（如 debug, info）
::   -logmaxsize <bytes>     設定 log 檔案最大大小
::   -debughandler           啟用 debug handler
::   範例：
::     ClickShare.exe -enablelogging -debuglogging
::     ClickShare.exe -enablelogging -loglevel debug
:: ============================================================

:MAIN_MENU
cls

:: Read current CLICKSHARE_DEBUG value from user environment (registry)
set "CURRENT_VALUE="
for /f "tokens=3" %%V in ('reg query "HKCU\Environment" /v CLICKSHARE_DEBUG 2^>nul') do (
    set "CURRENT_VALUE=%%V"
)
if "!CURRENT_VALUE!"=="" set "CURRENT_VALUE=(not set)"

echo ============================================================
echo          ClickShare App Tool
echo ============================================================
echo.
echo  CLICKSHARE_DEBUG : !CURRENT_VALUE!
echo.
echo  [1] Enable  debug log  (CLICKSHARE_DEBUG=ON)
echo  [2] Disable debug log  (CLICKSHARE_DEBUG=OFF)
echo  [3] Clear   debug log  (remove variable)
echo  [0] Exit
echo.
echo  Note: restart the ClickShare app after changing the value.
echo ============================================================
set /p "CHOICE=Select option: "

if "!CHOICE!"=="1" goto SET_ON
if "!CHOICE!"=="2" goto SET_OFF
if "!CHOICE!"=="3" goto CLEAR_VAR
if "!CHOICE!"=="0" goto EXIT
echo Invalid option.
timeout /t 2 >nul
goto MAIN_MENU

:SET_ON
echo.
echo [1] Setting CLICKSHARE_DEBUG=ON ...
setx CLICKSHARE_DEBUG ON
echo.
echo Done. Restart the ClickShare app to apply.
echo.
pause
goto MAIN_MENU

:SET_OFF
echo.
echo [2] Setting CLICKSHARE_DEBUG=OFF ...
setx CLICKSHARE_DEBUG OFF
echo.
echo Done. Restart the ClickShare app to apply.
echo.
pause
goto MAIN_MENU

:CLEAR_VAR
echo.
echo [3] Removing CLICKSHARE_DEBUG ...
reg delete "HKCU\Environment" /v CLICKSHARE_DEBUG /f >nul 2>&1
echo Variable removed.
echo.
echo Done. Restart the ClickShare app to apply.
echo.
pause
goto MAIN_MENU

:EXIT
echo Bye!
endlocal
exit /b 0
