@echo off
chcp 65001 >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0record_tool.ps1"
if %errorlevel% neq 0 (
    echo.
    echo  Script exited with error code %errorlevel%
    pause
)
