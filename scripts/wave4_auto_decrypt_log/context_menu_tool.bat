@echo off
REM context_menu_tool.bat
REM Interactive launcher for install_context_menu.py — adds/removes the
REM "Wave4 Log Decrypt" right-click menu entry for .zip files (HKCU, no
REM admin rights required).

setlocal
cd /d "%~dp0"

:MENU
cls
echo ============================================
echo   Wave4 Log Decrypt - Context Menu Setup
echo ============================================
echo.
echo   [1] Install context menu
echo   [2] Uninstall context menu
echo   [Q] Quit
echo.
set /p CHOICE="Select an option: "

if /i "%CHOICE%"=="1" goto INSTALL
if /i "%CHOICE%"=="2" goto UNINSTALL
if /i "%CHOICE%"=="Q" goto END
echo Invalid choice.
pause
goto MENU

:INSTALL
echo.
python install_context_menu.py
echo.
pause
goto MENU

:UNINSTALL
echo.
python install_context_menu.py uninstall
echo.
pause
goto MENU

:END
endlocal
